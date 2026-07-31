from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from pydantic import BaseModel, Field

from app.services.error_logger import append_error_log, allow_log_for_key, read_recent_logs
from app.auth.dependencies import require_admin


router = APIRouter(tags=["error-logging"])


class ErrorLogPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    stack: Optional[str] = Field(default=None, max_length=20000)
    route: Optional[str] = Field(default=None, max_length=1000)
    user_id: Optional[str] = Field(default=None, max_length=255)
    timestamp: str
    level: Literal["info", "warning", "error"] = "error"


@router.post("/log-error")
async def log_error(payload: ErrorLogPayload, request: Request):
    # Basic anti-spam: per-IP + user bucket
    ip = request.client.host if request.client else "unknown"
    rate_key = f"{ip}:{payload.user_id or 'anon'}"
    if not allow_log_for_key(rate_key):
        raise HTTPException(status_code=429, detail="Too many log submissions")

    entry = payload.model_dump()
    entry["received_at"] = datetime.utcnow().isoformat()
    entry["ip"] = ip
    try:
        append_error_log(entry)
        return {"success": True}
    except OSError:
        # In some deployment targets the local filesystem may be read-only.
        return {"success": False, "stored": False}


@router.get("/log-error/recent")
async def get_recent_logs(
    _admin=Depends(require_admin),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Admin-only: recent error logs. Requires admin role."""
    return {"items": read_recent_logs(limit=limit)}
