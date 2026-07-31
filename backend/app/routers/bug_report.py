from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from pydantic import BaseModel, Field
from app.auth.dependencies import require_admin

router = APIRouter(tags=["bug-report"])

# ─── Storage ─────────────────────────────────────────────────────────────────

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_BUG_FILE = _LOG_DIR / "bug_reports.jsonl"
_LOCK = threading.Lock()

# ─── Rate limiting (per IP, max 5 reports / 10 min) ─────────────────────────

_RATE_LOCK = threading.Lock()
_RATE_BUCKET: dict[str, list[float]] = {}
_RATE_LIMIT_COUNT = 5
_RATE_LIMIT_WINDOW = 600  # 10 minutes


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


_SENSITIVE_KEYS = {"password", "token", "access_token", "authorization", "api_key", "secret", "cookie"}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k.lower() in _SENSITIVE_KEYS else _sanitize(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str) and len(value) > 4000:
        return value[:4000] + "..."
    return value


def _append(entry: dict[str, Any]) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_sanitize(entry), ensure_ascii=False)
    with _LOCK:
        with _BUG_FILE.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")


# ─── Schema ───────────────────────────────────────────────────────────────────

class BugReportPayload(BaseModel):
    message: str = Field(..., min_length=5, max_length=2000)
    category: Literal["bug", "suggestion", "wrong_answer", "other"] = "bug"

    # Auto-collected context from frontend
    route: Optional[str] = Field(default=None, max_length=500)
    user_id: Optional[str] = Field(default=None, max_length=128)
    timestamp: str = Field(..., max_length=40)

    # Device / browser info
    user_agent: Optional[str] = Field(default=None, max_length=500)
    screen_size: Optional[str] = Field(default=None, max_length=50)
    language: Optional[str] = Field(default=None, max_length=20)

    # Optional extras
    screenshot_base64: Optional[str] = Field(default=None, max_length=500_000)  # ~375KB
    console_errors: Optional[list[str]] = Field(default=None, max_items=20)
    extra: Optional[dict[str, Any]] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/bug-report", status_code=201)
async def submit_bug_report(payload: BugReportPayload, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _allow(ip):
        raise HTTPException(status_code=429, detail="Too many reports. Please wait a few minutes.")

    entry = payload.model_dump()
    entry["received_at"] = datetime.utcnow().isoformat()
    entry["ip"] = ip

    _append(entry)
    return {"success": True, "message": "Докладът е изпратен. Благодарим ти!"}


@router.get("/bug-report/recent")
async def get_recent_bug_reports(
    _admin=Depends(require_admin),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Admin-only. Returns recent bug reports (without raw screenshot blobs)."""
    if not _BUG_FILE.exists():
        return {"items": [], "total": 0}

    lines = _BUG_FILE.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    recent = lines[-min(limit, 500):]
    items: list[dict[str, Any]] = []
    for line in reversed(recent):
        try:
            entry = json.loads(line)
            # Strip large screenshot blobs — never return student screen data
            entry.pop("screenshot_base64", None)
            items.append(entry)
        except Exception:
            pass

    return {"items": items, "total": total}
