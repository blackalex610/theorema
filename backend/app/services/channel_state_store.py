"""Read/write path for the desktop<->phone channel's shared state.

Every entry is written to the database *and* kept in a small in-process cache.
The cache is the hot path (same instance, same channel, seconds apart); the
database is what makes the data survive a serverless cold start — and, more to
the point here, what lets the *other device's* request find it at all. See
``app.models.mobile_channel`` for why the previous module-level dicts could
never work on Vercel.

Failure policy is deliberately asymmetric, matching ``nvo_exam_store``:

* **Reads** that fail fall back to the in-memory cache — a database blip should
  not 404 a task context this instance is still holding.
* **Writes** that fail are logged at ERROR with a traceback but do not abort the
  request. Raising would throw away a photo the student already uploaded (and
  an image-scan credit already charged). The log line is the signal that
  persistence is broken; it is never silent.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.models.mobile_channel import MobileTaskContext, MobileUploadRecord

logger = logging.getLogger(__name__)


def _ttl() -> timedelta:
    """How long channel state outlives the photo it describes: exactly as long.

    The uploaded file is purged at MEDIA_RETENTION_HOURS, so a longer window
    would only ever leave rows pointing at a deleted photo.
    """
    return timedelta(hours=getattr(settings, "MEDIA_RETENTION_HOURS", 24))


# Bound the hot caches so a long-lived (non-serverless) process cannot grow
# without limit. Entries are cheap to lose — the database is the truth.
_MAX_CACHED_CHANNELS = 64

_uploads_cache: dict[str, tuple[datetime, list[dict]]] = {}
_contexts_cache: dict[str, tuple[datetime, dict[int, dict]]] = {}


def _cache_put(cache: dict, key: str, expires_at: datetime, payload) -> None:
    cache[key] = (expires_at, payload)
    if len(cache) <= _MAX_CACHED_CHANNELS:
        return
    now = datetime.utcnow()
    for stale in [k for k, (exp, _) in cache.items() if exp <= now]:
        cache.pop(stale, None)
    # Still over budget: drop oldest-inserted entries (dicts keep insertion order).
    while len(cache) > _MAX_CACHED_CHANNELS:
        cache.pop(next(iter(cache)), None)


def _cache_get(cache: dict, key: str):
    entry = cache.get(key)
    if entry is None:
        return None
    expires_at, payload = entry
    if expires_at <= datetime.utcnow():
        cache.pop(key, None)
        return None
    return payload


def _purge_expired(session, model) -> None:
    """Drop rows nobody can read any more. Cheap, indexed, best-effort."""
    session.query(model).filter(model.expires_at <= datetime.utcnow()).delete(
        synchronize_session=False
    )


def _discard(session) -> None:
    """Roll back and close a session that has already failed.

    The original error is logged by the caller; a second failure while tearing
    down a dead connection carries no new information and must not turn a
    logged degradation into a 500.
    """
    for step in (session.rollback, session.close):
        try:
            step()
        except Exception:  # noqa: BLE001 - teardown of an already-broken session
            logger.debug("Ignoring error while discarding a failed session", exc_info=True)


# ─── Uploads ─────────────────────────────────────────────────────────────────

def record_upload(channel_id: str, event: dict, history_limit: int) -> None:
    """Append one upload event to a channel's history, newest first."""
    now = datetime.utcnow()
    expires_at = now + _ttl()

    cached = _cache_get(_uploads_cache, channel_id) or []
    _cache_put(_uploads_cache, channel_id, expires_at, [event, *cached][:history_limit])

    session = SessionLocal()
    try:
        _purge_expired(session, MobileUploadRecord)
        session.add(
            MobileUploadRecord(
                channel_id=channel_id,
                payload_json=json.dumps(event, ensure_ascii=False),
                uploaded_at=now,
                expires_at=expires_at,
            )
        )
        session.flush()
        # Keep the channel's history bounded the way the old dict did, rather
        # than letting a long session accumulate rows until the TTL sweeps them.
        stale_ids = [
            row[0]
            for row in session.query(MobileUploadRecord.id)
            .filter(MobileUploadRecord.channel_id == channel_id)
            .order_by(MobileUploadRecord.uploaded_at.desc(), MobileUploadRecord.id.desc())
            .offset(history_limit)
            .all()
        ]
        if stale_ids:
            session.query(MobileUploadRecord).filter(
                MobileUploadRecord.id.in_(stale_ids)
            ).delete(synchronize_session=False)
        session.commit()
        session.close()
    except SQLAlchemyError:
        logger.error(
            "Failed to persist upload event for channel %s; the paired desktop will not see it",
            channel_id,
            exc_info=True,
        )
        _discard(session)


def load_uploads(channel_id: str, limit: int) -> list[dict]:
    """Return a channel's most recent upload events, newest first."""
    session = SessionLocal()
    try:
        rows = (
            session.query(MobileUploadRecord.payload_json)
            .filter(
                MobileUploadRecord.channel_id == channel_id,
                MobileUploadRecord.expires_at > datetime.utcnow(),
            )
            .order_by(MobileUploadRecord.uploaded_at.desc(), MobileUploadRecord.id.desc())
            .limit(limit)
            .all()
        )
        stored = [row[0] for row in rows]
        session.close()
    except SQLAlchemyError:
        logger.error("Failed to load uploads for channel %s", channel_id, exc_info=True)
        _discard(session)
        return list(_cache_get(_uploads_cache, channel_id) or [])[:limit]

    events: list[dict] = []
    for payload_json in stored:
        try:
            events.append(json.loads(payload_json))
        except json.JSONDecodeError:
            logger.error(
                "Stored upload event for channel %s is not valid JSON; skipping",
                channel_id,
                exc_info=True,
            )
    return events


def clear_uploads(channel_id: str) -> None:
    """Forget a channel's upload history (the student reset the session)."""
    _uploads_cache.pop(channel_id, None)

    session = SessionLocal()
    try:
        session.query(MobileUploadRecord).filter(
            MobileUploadRecord.channel_id == channel_id
        ).delete(synchronize_session=False)
        session.commit()
        session.close()
    except SQLAlchemyError:
        logger.error("Failed to clear uploads for channel %s", channel_id, exc_info=True)
        _discard(session)


# ─── Task contexts ───────────────────────────────────────────────────────────

def save_task_context(channel_id: str, problem_number: int, context: dict) -> None:
    """Store the statement/answer key a later grade call will read back."""
    expires_at = datetime.utcnow() + _ttl()

    cached = dict(_cache_get(_contexts_cache, channel_id) or {})
    cached[problem_number] = context
    _cache_put(_contexts_cache, channel_id, expires_at, cached)

    session = SessionLocal()
    try:
        _purge_expired(session, MobileTaskContext)
        row = (
            session.query(MobileTaskContext)
            .filter(
                MobileTaskContext.channel_id == channel_id,
                MobileTaskContext.problem_number == problem_number,
            )
            .one_or_none()
        )
        if row is None:
            row = MobileTaskContext(channel_id=channel_id, problem_number=problem_number)
            session.add(row)
        row.payload_json = json.dumps(context, ensure_ascii=False)
        row.updated_at = datetime.utcnow()
        row.expires_at = expires_at
        session.commit()
        session.close()
    except SQLAlchemyError:
        logger.error(
            "Failed to persist task context for channel %s problem %s; "
            "grading from the paired phone will 404",
            channel_id,
            problem_number,
            exc_info=True,
        )
        _discard(session)


def load_task_context(channel_id: str, problem_number: int) -> dict | None:
    """Return one problem's stored context, or None if unknown or expired."""
    session = SessionLocal()
    try:
        row = (
            session.query(MobileTaskContext.payload_json)
            .filter(
                MobileTaskContext.channel_id == channel_id,
                MobileTaskContext.problem_number == problem_number,
                MobileTaskContext.expires_at > datetime.utcnow(),
            )
            .one_or_none()
        )
        stored = row[0] if row is not None else None
        session.close()
    except SQLAlchemyError:
        logger.error(
            "Failed to load task context for channel %s problem %s",
            channel_id,
            problem_number,
            exc_info=True,
        )
        _discard(session)
        return (_cache_get(_contexts_cache, channel_id) or {}).get(problem_number)

    if stored is None:
        return None
    try:
        return json.loads(stored)
    except json.JSONDecodeError:
        logger.error(
            "Stored task context for channel %s problem %s is not valid JSON; discarding",
            channel_id,
            problem_number,
            exc_info=True,
        )
        return None


def load_task_contexts(channel_id: str) -> list[dict]:
    """Every stored context for a channel, ordered by problem number."""
    session = SessionLocal()
    try:
        rows = (
            session.query(MobileTaskContext.problem_number, MobileTaskContext.payload_json)
            .filter(
                MobileTaskContext.channel_id == channel_id,
                MobileTaskContext.expires_at > datetime.utcnow(),
            )
            .order_by(MobileTaskContext.problem_number.asc())
            .all()
        )
        stored = [(row[0], row[1]) for row in rows]
        session.close()
    except SQLAlchemyError:
        logger.error("Failed to load task contexts for channel %s", channel_id, exc_info=True)
        _discard(session)
        cached = _cache_get(_contexts_cache, channel_id) or {}
        return [cached[key] for key in sorted(cached)]

    contexts: list[dict] = []
    for problem_number, payload_json in stored:
        try:
            contexts.append(json.loads(payload_json))
        except json.JSONDecodeError:
            logger.error(
                "Stored task context for channel %s problem %s is not valid JSON; skipping",
                channel_id,
                problem_number,
                exc_info=True,
            )
    return contexts
