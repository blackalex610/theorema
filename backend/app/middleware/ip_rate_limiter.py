"""
Per-IP sliding-window rate limiter for AI-heavy endpoints.

Strategy:
- In-memory dict: ip -> deque of UTC timestamps
- Sliding window per bucket
- Applied to routes that cost money (AI, NVO, uploads, theory generation)
- Trusted proxies: reads X-Forwarded-For if set
- No Redis required — resets on server restart (acceptable for MVP)
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request, Response
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

# Global in-memory store  {bucket_key: deque[timestamp_float]}
_buckets: Dict[str, Deque[float]] = defaultdict(deque)


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

        ip = _get_client_ip(request)
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

        now = time.monotonic()
        window_start = now - window_seconds

        bucket = _buckets[bucket_key]

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= max_requests:
            oldest = bucket[0]
            retry_after = int(window_seconds - (now - oldest)) + 1
            return _rate_limit_response(retry_after)

        bucket.append(now)
        return await call_next(request)
