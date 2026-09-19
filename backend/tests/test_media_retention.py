"""Uploaded homework photos must not live forever.

Students photograph their handwritten working; the image is sent to OpenAI
vision for grading and written to disk under a uuid filename. Access is
already gated behind an HMAC-signed, expiring token (main.py's /media route)
— but nothing ever deleted the files, so a child's handwriting accumulated
on disk indefinitely with no retention policy at all.
"""
import os
import time
from datetime import timedelta

import pytest

from app.services import media_retention


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(media_retention, "UPLOAD_DIR", tmp_path)
    return tmp_path


def _write(dir_path, name: str, age_hours: float) -> "os.PathLike":
    path = dir_path / name
    path.write_bytes(b"jpeg-bytes")
    old = time.time() - age_hours * 3600
    os.utime(path, (old, old))
    return path


def test_purges_a_file_past_the_retention_window(upload_dir):
    stale = _write(upload_dir, "old.jpg", age_hours=48)

    removed = media_retention.purge_expired_uploads(max_age_hours=24)

    assert removed == 1
    assert not stale.exists()


def test_keeps_a_file_inside_the_retention_window(upload_dir):
    fresh = _write(upload_dir, "recent.jpg", age_hours=1)

    removed = media_retention.purge_expired_uploads(max_age_hours=24)

    assert removed == 0
    assert fresh.exists()


def test_purges_only_what_is_actually_expired(upload_dir):
    _write(upload_dir, "old1.jpg", age_hours=30)
    _write(upload_dir, "old2.jpg", age_hours=99)
    fresh = _write(upload_dir, "new.jpg", age_hours=0.5)

    removed = media_retention.purge_expired_uploads(max_age_hours=24)

    assert removed == 2
    assert fresh.exists()


def test_a_missing_upload_directory_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(media_retention, "UPLOAD_DIR", tmp_path / "does-not-exist")

    assert media_retention.purge_expired_uploads(max_age_hours=24) == 0


def test_one_unremovable_file_does_not_abort_the_whole_sweep(upload_dir, monkeypatch):
    """A file locked by another process must not leave the rest un-purged."""
    _write(upload_dir, "a.jpg", age_hours=48)
    _write(upload_dir, "b.jpg", age_hours=48)

    real_unlink = media_retention.Path.unlink
    calls = {"n": 0}

    def flaky_unlink(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError("file is locked")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(media_retention.Path, "unlink", flaky_unlink)

    removed = media_retention.purge_expired_uploads(max_age_hours=24)

    assert removed == 1  # the one that could be removed still was
    assert calls["n"] == 2  # and the sweep carried on to the second file


def test_default_retention_comes_from_settings(upload_dir):
    """Operators tune retention by config, not by editing the call site."""
    from app.config import settings

    assert isinstance(settings.MEDIA_RETENTION_HOURS, int)
    assert settings.MEDIA_RETENTION_HOURS > 0

    _write(upload_dir, "ancient.jpg", age_hours=settings.MEDIA_RETENTION_HOURS + 10)

    assert media_retention.purge_expired_uploads() == 1
