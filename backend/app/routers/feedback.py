from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import require_admin
from app.services.event_log_store import append_log, read_recent

router = APIRouter(tags=["feedback"])

# ─── Rate limiting (per IP, 60 feedback/min) ─────────────────────────────────

_RATE_LOCK = threading.Lock()
_RATE_BUCKET: dict[str, list[float]] = {}
_RATE_LIMIT_COUNT = 60
_RATE_LIMIT_WINDOW = 60


def _allow(ip: str) -> bool:
    now = time.time()
    with _RATE_LOCK:
        bucket = _RATE_BUCKET.setdefault(ip, [])
        cutoff = now - _RATE_LIMIT_WINDOW
        bucket[:] = [t for t in bucket if t >= cutoff]
        if len(bucket) >= _RATE_LIMIT_COUNT:
            return False
        bucket.append(now)
        return True


# ─── Schema ───────────────────────────────────────────────────────────────────

class FeedbackPayload(BaseModel):
    is_helpful: bool
    content_type: Literal["exercise", "explanation", "chat", "lesson", "nvo_exam"]
    content_id: Optional[str] = Field(default=None, max_length=255)

    # Optional reason (only for 👎)
    reason: Optional[Literal["too_hard", "too_confusing", "wrong_answer", "not_helpful", "other"]] = None
    reason_text: Optional[str] = Field(default=None, max_length=500)

    # Auto-collected context
    user_id: Optional[str] = Field(default=None, max_length=128)
    timestamp: str = Field(..., max_length=40)
    topic: Optional[str] = Field(default=None, max_length=255)
    difficulty: Optional[str] = Field(default=None, max_length=50)
    route: Optional[str] = Field(default=None, max_length=500)


# ─── Endpoint ────────────────────────────────────────────────────────────────

@router.post("/feedback", status_code=201)
async def submit_feedback(payload: FeedbackPayload, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _allow(ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    entry = payload.model_dump()
    entry["received_at"] = datetime.utcnow().isoformat()
    entry["ip"] = ip

    if append_log("feedback", entry):
        return {"success": True}
    return {"success": False, "stored": False}


@router.get("/feedback/summary")
async def get_feedback_summary(
    _admin=Depends(require_admin),
    content_type: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    """Admin-only: helpful/not-helpful ratio per content_type.

    SECURITY: this had no auth at all until now — anyone who found the route
    could read every feedback submission (user_id, topic, free-text reasons
    included), the same class of bug as the admin routes fixed earlier.
    """
    items: list[dict[str, Any]] = [
        item for item in read_recent("feedback", limit=limit)
        if not content_type or item.get("content_type") == content_type
    ]

    summary: dict[str, Any] = {}
    for item in items:
        ct = item.get("content_type", "unknown")
        if ct not in summary:
            summary[ct] = {"helpful": 0, "not_helpful": 0, "reasons": {}}
        if item.get("is_helpful"):
            summary[ct]["helpful"] += 1
        else:
            summary[ct]["not_helpful"] += 1
            reason = item.get("reason") or "unspecified"
            summary[ct]["reasons"][reason] = summary[ct]["reasons"].get(reason, 0) + 1

    return {"items": items[:100], "summary": summary}
