"""Short-lived signed URLs for uploaded student media.

Uploads land in `backend/app/uploads` named only by `uuid4().hex`, and used to
be served by an unauthenticated StaticFiles mount — anyone who ever saw (or
guessed) a filename could fetch a child's homework photo forever, and the
filename leaked through several unauthenticated events.

There is no per-file ownership record in the schema, so ownership checks are
not possible yet. Until there is one, access is gated by an HMAC token bound to
the exact filename and an expiry, signed with SECRET_KEY. That keeps `<img src>`
working (a browser cannot attach an Authorization header to an image request)
while making the URLs unguessable and self-expiring.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote

from app.config import settings

# Long enough to outlive a practice session, short enough that a leaked URL
# from a screenshot or chat log stops working the same day.
MEDIA_TOKEN_TTL_SECONDS = 24 * 60 * 60


def _signature(filename: str, expires_at: int) -> str:
    message = f"{filename}:{expires_at}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()


def sign_media_token(filename: str, ttl_seconds: int = MEDIA_TOKEN_TTL_SECONDS) -> str:
    """Return an `<expiry>.<signature>` token authorising reads of `filename`."""
    expires_at = int(time.time()) + ttl_seconds
    return f"{expires_at}.{_signature(filename, expires_at)}"


def verify_media_token(filename: str, token: str | None) -> bool:
    """True when `token` is a valid, unexpired signature for `filename`."""
    if not token or "." not in token:
        return False
    raw_expiry, _, signature = token.partition(".")
    try:
        expires_at = int(raw_expiry)
    except ValueError:
        return False
    if expires_at < int(time.time()):
        return False
    # compare_digest: constant time, so the signature can't be brute-forced
    # one byte at a time by timing the response.
    return hmac.compare_digest(signature, _signature(filename, expires_at))


def build_media_url(filename: str, base_url: str = "") -> str:
    """Build a signed media URL. `base_url` empty yields a site-relative URL."""
    token = sign_media_token(filename)
    prefix = base_url.rstrip("/") if base_url else ""
    return f"{prefix}/media/{quote(filename)}?token={token}"
