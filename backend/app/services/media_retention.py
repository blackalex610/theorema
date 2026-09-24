"""Time-limited retention for uploaded homework photos.

Students photograph their handwritten working during an exam; the image goes
to OpenAI vision for grading and is stored under a uuid name (see
media_storage.py). Access is gated behind an HMAC-signed, expiring token —
but nothing ever deleted the photos, so a child's handwriting accumulated
indefinitely. For a product aimed at 11-14 year olds that is a retention
problem, not a disk-space one.

The window only has to outlive the grading it exists for: an exam runs at
most 150 minutes and the generated-exam store keeps its own rows for 24h, so
MEDIA_RETENTION_HOURS defaults to the same 24.

There is no scheduler in this deployment, so the sweep runs opportunistically
on upload as well as from the admin endpoint. With remote storage a sweep is
a list request, so the opportunistic path runs at most once per
SWEEP_INTERVAL_SECONDS per process instead of on every single upload.
"""
from __future__ import annotations

import logging
import time

from app.services.media_storage import (
    MediaStorageUnavailable,
    get_media_storage,
    retention_cutoff,
)

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 600
_last_sweep: float | None = None


def purge_expired_uploads(max_age_hours: int | None = None, *, force: bool = True) -> int:
    """Delete uploads older than the retention window. Returns the count.

    Never raises: this runs inline on the upload path, and a retention sweep
    failing must not fail the student's upload. `force=False` is the
    opportunistic call from the upload path, which skips the sweep if this
    process ran one recently.
    """
    global _last_sweep
    now = time.monotonic()
    if not force and _last_sweep is not None and now - _last_sweep < SWEEP_INTERVAL_SECONDS:
        return 0
    _last_sweep = now

    try:
        storage = get_media_storage()
    except MediaStorageUnavailable:
        return 0

    try:
        removed = storage.purge_older_than(retention_cutoff(max_age_hours))
    except Exception:
        logger.warning("Upload retention sweep failed", exc_info=True)
        return 0

    if removed:
        logger.info("Purged %s upload(s) past the retention window", removed)
    return removed
