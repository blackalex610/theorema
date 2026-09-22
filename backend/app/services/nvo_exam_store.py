"""Read/write path for generated NVO exams and generation jobs.

Every entry is written to the database *and* kept in a small in-process cache.
The cache is the hot path (same instance, same exam, a few seconds apart); the
database is what makes the data survive a serverless cold start, which the
previous module-level dicts did not.

Failure policy is deliberately asymmetric:

* **Reads** that fail fall back to the in-memory cache — a database blip should
  not 404 an exam this instance is still holding.
* **Writes** that fail are logged at ERROR with a traceback but do not abort the
  request. Raising here would throw away a generation run that already spent 60
  seconds and real OpenAI credits, and the client keeps a copy of the questions
  it can post back to ``/nvo/submit``. The log line is the signal that
  persistence is broken; it is never silent.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.nvo_exam import GeneratedExam, NVOGenerationJob

logger = logging.getLogger(__name__)

# An exam is a single sitting; a day is plenty and keeps the table small.
EXAM_TTL = timedelta(hours=24)
# A job is only polled while the client waits on the generation call.
JOB_TTL = timedelta(hours=6)

# Bound the hot cache so a long-lived (non-serverless) process cannot grow
# without limit. Entries are cheap to lose — the database is the source of truth.
_MAX_CACHED = 128

_exam_cache: dict[str, tuple[datetime, dict]] = {}
_job_cache: dict[str, tuple[datetime, dict]] = {}


def _cache_put(cache: dict[str, tuple[datetime, dict]], key: str, expires_at: datetime, payload: dict) -> None:
    cache[key] = (expires_at, payload)
    if len(cache) <= _MAX_CACHED:
        return
    now = datetime.utcnow()
    for stale in [k for k, (exp, _) in cache.items() if exp <= now]:
        cache.pop(stale, None)
    # Still over budget: drop oldest-inserted entries (dicts keep insertion order).
    while len(cache) > _MAX_CACHED:
        cache.pop(next(iter(cache)), None)


def _cache_get(cache: dict[str, tuple[datetime, dict]], key: str) -> dict | None:
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
    down a dead connection carries no new information and must not be allowed
    to turn a logged degradation into a 500.
    """
    for step in (session.rollback, session.close):
        try:
            step()
        except Exception:  # noqa: BLE001 - teardown of an already-broken session
            logger.debug("Ignoring error while discarding a failed session", exc_info=True)


# ─── Exams ───────────────────────────────────────────────────────────────────

def save_exam(exam_id: str, exam_payload: dict) -> None:
    """Persist a generated exam. Overwrites an existing row with the same id."""
    expires_at = datetime.utcnow() + EXAM_TTL
    _cache_put(_exam_cache, exam_id, expires_at, exam_payload)

    session = SessionLocal()
    try:
        _purge_expired(session, GeneratedExam)
        session.merge(
            GeneratedExam(
                exam_id=exam_id,
                questions_json=json.dumps(exam_payload, ensure_ascii=False),
                created_at=datetime.utcnow(),
                expires_at=expires_at,
            )
        )
        session.commit()
        session.close()
    except SQLAlchemyError:
        logger.error(
            "Failed to persist generated NVO exam %s; it will be lost on a cold start",
            exam_id,
            exc_info=True,
        )
        _discard(session)


def extend_exam_expiry(exam_id: str, expires_at: datetime) -> bool:
    """Keep a stored exam alive until ``expires_at``. Never shortens it.

    Generated exams are disposable 24h cache rows, purged on every write. An
    assigned paper is not disposable: the class has to be able to open it
    until the assignment is due, and a paper that vanished mid-week is worse
    than never having assigned one.

    Returns False when there is no such exam, so the caller can refuse to
    create an assignment pointing at a paper that is already gone rather than
    discovering it when the first student opens it.
    """
    session = SessionLocal()
    try:
        row = (
            session.query(GeneratedExam)
            .filter(GeneratedExam.exam_id == exam_id)
            .one_or_none()
        )
        if row is None:
            session.close()
            return False
        if row.expires_at < expires_at:
            row.expires_at = expires_at
            session.commit()
        # Keep the hot cache in step, or this instance would go on believing
        # the old expiry and 404 a paper the database is still holding.
        cached = _exam_cache.get(exam_id)
        if cached is not None:
            _cache_put(_exam_cache, exam_id, max(cached[0], expires_at), cached[1])
        session.close()
        return True
    except SQLAlchemyError:
        logger.error("Failed to extend expiry for NVO exam %s", exam_id, exc_info=True)
        _discard(session)
        return False


def load_exam(exam_id: str) -> dict | None:
    """Return the stored exam payload, or None if it is unknown or expired."""
    cached = _cache_get(_exam_cache, exam_id)
    if cached is not None:
        return cached

    session = SessionLocal()
    try:
        row = (
            session.query(GeneratedExam)
            .filter(
                GeneratedExam.exam_id == exam_id,
                GeneratedExam.expires_at > datetime.utcnow(),
            )
            .one_or_none()
        )
        # Read the columns out before closing; the row is detached afterwards.
        stored = (row.questions_json, row.expires_at) if row is not None else None
        session.close()
    except SQLAlchemyError:
        logger.error("Failed to load generated NVO exam %s", exam_id, exc_info=True)
        _discard(session)
        return None

    if stored is None:
        return None

    questions_json, expires_at = stored
    try:
        payload = json.loads(questions_json)
    except json.JSONDecodeError:
        logger.error("Stored NVO exam %s is not valid JSON; discarding", exam_id, exc_info=True)
        return None

    _cache_put(_exam_cache, exam_id, expires_at, payload)
    return payload


# ─── Generation jobs ─────────────────────────────────────────────────────────

def save_job(job_id: str, job_payload: dict) -> None:
    """Persist the current state of a generation job (called on every tick)."""
    expires_at = datetime.utcnow() + JOB_TTL
    _cache_put(_job_cache, job_id, expires_at, job_payload)

    session = SessionLocal()
    try:
        _purge_expired(session, NVOGenerationJob)
        session.merge(
            NVOGenerationJob(
                job_id=job_id,
                status=str(job_payload.get("status", "")),
                progress=int(job_payload.get("progress", 0)),
                message=str(job_payload.get("message", "")),
                exam_id=job_payload.get("exam_id"),
                created_at=datetime.utcnow(),
                expires_at=expires_at,
            )
        )
        session.commit()
        session.close()
    except SQLAlchemyError:
        logger.error("Failed to persist NVO generation job %s", job_id, exc_info=True)
        _discard(session)


def load_job(job_id: str) -> dict | None:
    """Return the stored job state, or None if it is unknown or expired."""
    cached = _cache_get(_job_cache, job_id)
    if cached is not None:
        return cached

    session = SessionLocal()
    try:
        row = (
            session.query(NVOGenerationJob)
            .filter(
                NVOGenerationJob.job_id == job_id,
                NVOGenerationJob.expires_at > datetime.utcnow(),
            )
            .one_or_none()
        )
        # Read the columns out before closing; the row is detached afterwards.
        stored = (
            {
                "job_id": row.job_id,
                "status": row.status,
                "progress": row.progress,
                "message": row.message,
                "exam_id": row.exam_id,
            },
            row.expires_at,
        ) if row is not None else None
        session.close()
    except SQLAlchemyError:
        logger.error("Failed to load NVO generation job %s", job_id, exc_info=True)
        _discard(session)
        return None

    if stored is None:
        return None

    payload, expires_at = stored
    _cache_put(_job_cache, job_id, expires_at, payload)
    return payload


def clear_cache() -> None:
    """Drop the in-process caches. Used by tests to exercise the database path."""
    _exam_cache.clear()
    _job_cache.clear()
