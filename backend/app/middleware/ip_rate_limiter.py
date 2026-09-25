"""
Per-IP rate limiter for AI-heavy endpoints.

Strategy:
- Counts live in the database (rate_limit_counters), one row per bucket per
  fixed window, bumped with a single atomic upsert. They used to live in a
  dict in each process, and on Vercel every serverless instance has its own
  process, so a burst spread over instances was never limited at all.
- If the database can't be reached, the old in-process sliding window takes
  over for that request: a limiter outage must not become an API outage.
- Applied to routes that cost money (AI, NVO, uploads, theory generation)
- Trusted proxies: reads X-Forwarded-For if set (Vercel overwrites it)
"""
import logging
import random
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Endpoints the rate limiter protects (prefix match on actual API paths)
_GUARDED_PREFIXES = (
    "/ai/",
    "/nvo/",
    "/mobile/",
    "/curriculum/lessons/",
    # Reaches OpenAI (_ai_equivalence_check) and was previously unguarded.
    "/exercises/",
)

# Stricter limits for expensive one-shot AI generation endpoints
_STRICT_PATH_FRAGMENTS = (
    "/generated-theory",
    "/generated-examples",
    "/ai-exercises",
    # No cache at all behind this one — every call is a fresh OpenAI request.
    "/video-search-queries",
)

# Named tiers, checked in order (first match wins), each an
# (window_seconds, max_requests) pair. Exact-path entries take priority over
# prefix-guarded traffic so a specific endpoint can have its own budget
# without joining _GUARDED_PREFIXES's broader match.
_EXACT_PATH_TIERS: Dict[str, tuple[int, int]] = {
    # Creates a DB row per call; the per-IP DB cap in auth.py is the real
    # backstop, this just keeps a burst from ever reaching it.
    "/auth/guest": (600, 5),
}

# Default limits (general AI traffic)
WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 60

# Stricter limits (theory / examples generation)
STRICT_WINDOW_SECONDS = 60
STRICT_MAX_REQUESTS_PER_WINDOW = 15

# Fallback store when the database is unreachable {bucket_key: deque[timestamp]}
_buckets: Dict[str, Deque[float]] = defaultdict(deque)

logger = logging.getLogger(__name__)

# One statement on both PostgreSQL and SQLite (3.35+): create the window's
# row or bump it, and read the new count back atomically.
_UPSERT = text(
    "INSERT INTO rate_limit_counters (bucket, window_start, hits) "
    "VALUES (:bucket, :window_start, 1) "
    "ON CONFLICT (bucket, window_start) DO UPDATE "
    "SET hits = rate_limit_counters.hits + 1 "
    "RETURNING hits"
)
_PRUNE = text("DELETE FROM rate_limit_counters WHERE window_start < :cutoff")
# Rows only matter for their own window; clear old ones now and then.
_PRUNE_PROBABILITY = 0.01
_PRUNE_AGE_SECONDS = 3600


def _epoch() -> int:
    return int(time.time())


def _hit_shared(bucket: str, window_seconds: int) -> tuple[int, int]:
    """Count one hit in the current window. Returns (hits, seconds left)."""
    from app.database import engine

    now = _epoch()
    window_start = now - now % window_seconds
    with engine.begin() as conn:
        hits = conn.execute(_UPSERT, {"bucket": bucket, "window_start": window_start}).scalar_one()
        if random.random() < _PRUNE_PROBABILITY:
            conn.execute(_PRUNE, {"cutoff": now - _PRUNE_AGE_SECONDS})
    return int(hits), max(1, window_start + window_seconds - now)


def _hit_local(bucket: str, window_seconds: int) -> tuple[int, int]:
    """In-process sliding window: the fallback when the database is down."""
    now = time.monotonic()
    queue = _buckets[bucket]
    while queue and queue[0] < now - window_seconds:
        queue.popleft()
    queue.append(now)
    return len(queue), int(window_seconds - (now - queue[0])) + 1


def _get_client_ip(request: Request) -> str:
    """Return the real IP, respecting X-Forwarded-For from a reverse proxy."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_guarded(path: str) -> bool:
    return path in _EXACT_PATH_TIERS or any(path.startswith(prefix) for prefix in _GUARDED_PREFIXES)


def _is_strict(path: str) -> bool:
    return any(fragment in path for fragment in _STRICT_PATH_FRAGMENTS)


def _rate_limit_response(retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "code": "RATE_LIMITED",
                "message": "Прекалено много заявки. Моля, изчакайте малко.",
                "retry_after": retry_after,
            }
        },
        headers={"Retry-After": str(retry_after)},
    )


class IPRateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not _is_guarded(path):
            return await call_next(request)

        # Capped: the header is caller-supplied wherever a proxy doesn't
        # overwrite it, and this becomes part of a database key.
        ip = _get_client_ip(request)[:64]
        if path in _EXACT_PATH_TIERS:
            window_seconds, max_requests = _EXACT_PATH_TIERS[path]
            bucket_key = f"{ip}:{path}"
        elif _is_strict(path):
            bucket_key = f"{ip}:strict"
            window_seconds = STRICT_WINDOW_SECONDS
            max_requests = STRICT_MAX_REQUESTS_PER_WINDOW
        else:
            bucket_key = f"{ip}:default"
            window_seconds = WINDOW_SECONDS
            max_requests = MAX_REQUESTS_PER_WINDOW

        try:
            hits, retry_after = await run_in_threadpool(_hit_shared, bucket_key, window_seconds)
        except Exception:
            logger.warning("Shared rate limiter unavailable; using this process's counts", exc_info=True)
            hits, retry_after = _hit_local(bucket_key, window_seconds)

        if hits > max_requests:
            return _rate_limit_response(retry_after)

        return await call_next(request)
