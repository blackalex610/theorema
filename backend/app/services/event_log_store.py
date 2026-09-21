"""Read/write path for analytics events, bug reports, feedback submissions
and error logs — a shared, DB-backed replacement for backend/logs/*.jsonl.

See app.models.event_log.EventLog for why: the old JSONL files lived inside
the deployment bundle, which is read-only on Vercel, so every write there
silently failed in production.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.database import SessionLocal
from app.models.event_log import EventLog

logger = logging.getLogger(__name__)


def append_log(log_type: str, entry: dict[str, Any]) -> bool:
    """Persist one entry. Never raises — a logging outage must not break the
    request it was attached to. Returns False (and logs) on failure so a
    caller can still report degraded storage the way the old
    `except OSError: return {"success": False}` did, except now the failure
    is an actual DB error worth knowing about, not an expected read-only-fs
    no-op.
    """
    db = SessionLocal()
    try:
        db.add(EventLog(log_type=log_type, payload_json=json.dumps(entry, ensure_ascii=False)))
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.error("Failed to persist %s log entry", log_type, exc_info=True)
        return False
    finally:
        db.close()


def read_recent(log_type: str, limit: int = 100) -> list[dict[str, Any]]:
    """The most recent `limit` entries for one log_type, newest first."""
    db = SessionLocal()
    try:
        rows = (
            db.query(EventLog)
            .filter(EventLog.log_type == log_type)
            .order_by(EventLog.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(json.loads(row.payload_json))
            except json.JSONDecodeError:
                continue
        return out
    finally:
        db.close()


def count_all(log_type: str) -> int:
    db = SessionLocal()
    try:
        return db.query(EventLog).filter(EventLog.log_type == log_type).count()
    finally:
        db.close()
