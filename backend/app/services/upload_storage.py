"""Where uploaded student photos live on disk — the one place that decides.

mobile_uploads.py writes here, main.py's /media route serves from here and
media_retention.py purges from here; all three import UPLOAD_DIR from this
module so they cannot drift apart.

On Vercel the deployment bundle (/var/task) is read-only and only the temp
dir is writable, so uploads go there. That storage is per-instance and
ephemeral: a photo written by one instance is not visible to another. It
is enough for the upload -> grade round trip; durable storage would need
object storage (e.g. Vercel Blob).
"""
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_upload_dir() -> Path:
    if os.getenv("VERCEL"):
        return Path(tempfile.gettempdir()) / "uploads"
    return Path(__file__).resolve().parent.parent / "uploads"


UPLOAD_DIR = resolve_upload_dir()


def ensure_upload_dir() -> bool:
    """Create UPLOAD_DIR if needed. Never raises.

    This runs at import time: an exception here used to fail the import of
    the whole app, taking every route (login included) down with it.
    """
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        logger.warning("Could not create upload dir %s", UPLOAD_DIR, exc_info=True)
        return False


ensure_upload_dir()
