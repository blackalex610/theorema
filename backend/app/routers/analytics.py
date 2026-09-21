from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.event_log_store import append_log

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsEventPayload(BaseModel):
    event_type: Literal[
        "login",
        "logout",
        "lesson_started",
        "lesson_completed",
        "exercise_completed",
        "ai_request",
        "nvo_started",
        "nvo_completed",
        "premium_clicked",
    ]
    user_id: Optional[str] = Field(default=None, max_length=128)
    timestamp: str = Field(..., max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/events", status_code=201)
async def create_analytics_event(payload: AnalyticsEventPayload):
    entry = payload.model_dump()
    entry["received_at"] = datetime.utcnow().isoformat()
    if append_log("analytics", entry):
        return {"success": True}
    # A DB write failure here must not surface as a 500 to a fire-and-forget
    # telemetry call — the caller just gets told it wasn't stored.
    return {"success": False, "stored": False}
