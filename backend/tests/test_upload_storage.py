"""The upload directory must never take the whole API down.

On 25 Sep 2026 every backend route on all four Vercel projects returned
FUNCTION_INVOCATION_FAILED, login included. mobile_uploads.py and main.py
both ran ``(app/uploads).mkdir()`` at import time. Vercel's /var/task is
read-only; the directory only existed in earlier bundles because stray
photos had been committed into it, so deleting them made the mkdir run —
and raise — on every cold start:

    OSError: [Errno 30] Read-only file system: '/var/task/app/uploads'
"""
import tempfile
from pathlib import Path

from app.services import upload_storage


def test_uses_the_writable_temp_dir_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")

    assert upload_storage.resolve_upload_dir() == Path(tempfile.gettempdir()) / "uploads"


def test_keeps_the_app_dir_off_vercel(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)

    expected = Path(upload_storage.__file__).resolve().parent.parent / "uploads"
    assert upload_storage.resolve_upload_dir() == expected


def test_ensure_upload_dir_does_not_raise_on_a_read_only_filesystem(monkeypatch):
    def read_only_mkdir(self, *args, **kwargs):
        raise OSError(30, "Read-only file system", str(self))

    monkeypatch.setattr(Path, "mkdir", read_only_mkdir)

    assert upload_storage.ensure_upload_dir() is False


def test_ensure_upload_dir_creates_the_directory(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "uploads"
    monkeypatch.setattr(upload_storage, "UPLOAD_DIR", target)

    assert upload_storage.ensure_upload_dir() is True
    assert target.is_dir()


def test_writer_server_and_purger_share_one_directory():
    import app.main as main
    from app.routers import mobile_uploads
    from app.services import media_retention

    assert mobile_uploads.UPLOAD_DIR == upload_storage.UPLOAD_DIR
    assert main.MEDIA_DIR == upload_storage.UPLOAD_DIR
    assert media_retention.UPLOAD_DIR == upload_storage.UPLOAD_DIR
