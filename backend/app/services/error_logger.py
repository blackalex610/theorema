from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.config import settings
from app.services.event_log_store import append_log, read_recent

logger = logging.getLogger(__name__)

_RATE_LOCK = threading.Lock()
_RATE_BUCKET: dict[str, list[float]] = {}
_RATE_LIMIT_COUNT = 20
_RATE_LIMIT_WINDOW_SECONDS = 60

_SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "secret",
    "cookie",
}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k.lower() in _SENSITIVE_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = _sanitize_value(v)
        return out
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, str):
        lowered = value.lower()
        if "bearer " in lowered or "api_key" in lowered or "password" in lowered:
            return "[REDACTED]"
        if len(value) > 4000:
            return value[:4000] + "..."
        return value
    return value


def _minimal_for_production(entry: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "level": entry.get("level", "error"),
        "message": entry.get("message", ""),
        "route": entry.get("route"),
        "user_id": entry.get("user_id"),
        "timestamp": entry.get("timestamp"),
    }
    stack = entry.get("stack")
    if stack and isinstance(stack, str):
        compact["stack"] = stack.splitlines()[0][:500]
    return compact


def allow_log_for_key(rate_key: str) -> bool:
    now = time.time()
    with _RATE_LOCK:
        timestamps = _RATE_BUCKET.setdefault(rate_key, [])
        cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
        timestamps[:] = [t for t in timestamps if t >= cutoff]
        if len(timestamps) >= _RATE_LIMIT_COUNT:
            return False
        timestamps.append(now)
        return True


def _forward_to_sentry(entry: dict[str, Any]) -> None:
    """Best-effort: also surface a frontend error report in Sentry.

    Never raises — this runs on the same path as every /log-error POST, and
    a Sentry hiccup must not turn a client's error report into a 500 of its
    own. No-ops entirely when SENTRY_DSN isn't set (see main.py).
    """
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("source", "frontend")
            scope.set_context("report", {
                "route": entry.get("route"),
                "user_id": entry.get("user_id"),
            })
            level = entry.get("level") if entry.get("level") in ("info", "warning", "error") else "error"
            sentry_sdk.capture_message(str(entry.get("message", "Frontend error")), level=level)
    except Exception:
        logger.debug("Failed to forward frontend error report to Sentry", exc_info=True)


def append_error_log(entry: dict[str, Any]) -> None:
    safe_entry = _sanitize_value(entry)
    if settings.ENVIRONMENT.lower() == "production":
        safe_entry = _minimal_for_production(safe_entry)
    append_log("error", safe_entry)
    _forward_to_sentry(safe_entry)


def read_recent_logs(limit: int = 100) -> list[dict[str, Any]]:
    return read_recent("error", limit=limit)
