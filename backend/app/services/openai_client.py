"""The one place an OpenAI client is built.

Every call site used to construct `OpenAI(api_key=...)` itself, per request,
and all but two passed no timeout — so the SDK default applied: 600 seconds
per attempt, retried twice. A stalled completion could hold a request for half
an hour on a long-running server, and on Vercel it simply ran into the
function's own limit and surfaced as a gateway timeout with nothing logged.
Building a client per call also threw away the connection pool every time.

`openai_client()` returns a shared client configured from settings:
OPENAI_TIMEOUT_SECONDS per attempt and OPENAI_MAX_RETRIES retries, with an
optional OPENAI_BASE_URL (e.g. OpenRouter) so the provider is a config
change. A caller with a known-long job passes its own `timeout`.

The client is synchronous. Callers on the async request path must run it via
`run_in_threadpool` — calling it directly from an `async def` endpoint blocks
the event loop, and with it every other request the process is serving.
"""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from app.config import settings


@lru_cache(maxsize=8)
def _build(api_key: str, base_url: str, timeout: float, max_retries: int) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=base_url or None,
        timeout=timeout,
        max_retries=max_retries,
    )


def openai_client(timeout: float | None = None) -> OpenAI:
    """A configured client. Callers still check OPENAI_API_KEY themselves,
    since each maps a missing key to its own error."""
    return _build(
        settings.OPENAI_API_KEY,
        settings.OPENAI_BASE_URL,
        float(timeout if timeout is not None else settings.OPENAI_TIMEOUT_SECONDS),
        int(settings.OPENAI_MAX_RETRIES),
    )
