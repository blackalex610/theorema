"""Time-limited retention for uploaded homework photos.

Students photograph their handwritten working during an exam; the image goes
to OpenAI vision for grading and is written to disk under a uuid filename.
Access to those files is already gated behind an HMAC-signed, expiring token
(see the /media route in main.py) — but nothing ever deleted them, so a
child's handwriting accumulated indefinitely. For a product aimed at 11-14
year olds that is a retention problem, not a disk-space one.

The window only has to outlive the grading it exists for: an exam runs at
most 150 minutes and the generated-exam store keeps its own rows for 24h, so
MEDIA_RETENTION_HOURS defaults to the same 24.

There is no scheduler in this deployment, so the sweep runs opportunistically
on upload (a directory scan is cheap at this scale) as well as from the
admin endpoint, rather than depending on an external cron nobody has set up.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Same directory mobile_uploads.py writes to and main.py serves from.
from app.services.upload_storage import UPLOAD_DIR


def purge_expired_uploads(max_age_hours: int | None = None) -> int:
    """Delete uploads older than the retention window. Returns the count.

    Never raises: this runs inline on the upload path, and a retention sweep
    failing must not fail the student's upload. One unremovable file (locked
    by another process, a permissions quirk) is logged and skipped so the
    rest of the sweep still happens.
    """
    window_hours = max_age_hours if max_age_hours is not None else settings.MEDIA_RETENTION_HOURS
    cutoff = time.time() - window_hours * 3600

    try:
        entries = list(UPLOAD_DIR.iterdir())
    except (FileNotFoundError, NotADirectoryError, OSError):
        return 0

    removed = 0
    for entry in entries:
        try:
            if not entry.is_file() or entry.stat().st_mtime >= cutoff:
                continue
            entry.unlink()
            removed += 1
        except OSError:
            logger.warning("Could not purge expired upload %s", entry.name, exc_info=True)
            continue

    if removed:
        logger.info("Purged %s upload(s) older than %sh", removed, window_hours)
    return removed
