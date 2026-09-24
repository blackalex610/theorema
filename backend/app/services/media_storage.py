"""Where uploaded homework photos live.

Photos used to be written to `backend/app/uploads/` on the server's own disk.
On Vercel that directory is read-only, and even /tmp would not do: the phone's
upload, the desktop's /media read and the grade-photo call each land on
whichever serverless instance is free, and no instance can see another's
disk. So the upload path 500'd in production, and would have lost photos even
if it hadn't.

Two backends, one interface:

* `LocalMediaStorage` — a directory on disk. Local development, and any
  single-server deployment with a persistent disk.
* `SupabaseMediaStorage` — a private Supabase Storage bucket, spoken to over
  its REST API with the service-role key (no extra dependency: `requests` is
  already required for Google sign-in).

`get_media_storage()` picks one from config. On Vercel with no bucket
configured it raises `MediaStorageUnavailable` rather than returning a local
backend that would appear to work on one request and lose the photo on the
next — the endpoints turn that into a clear 503.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import requests

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_DIR = Path(__file__).resolve().parent.parent / "uploads"


class MediaStorageError(RuntimeError):
    """The storage backend failed (network, auth, quota)."""


class MediaStorageUnavailable(MediaStorageError):
    """No storage backend that works in this environment is configured."""


class MediaStorage(Protocol):
    name: str

    def save(self, key: str, data: bytes, content_type: str) -> None: ...

    def read(self, key: str) -> bytes | None: ...

    def signed_url(self, key: str, expires_in: int) -> str | None:
        """A direct, time-limited URL for the object, or None if the backend
        has none and /media must stream the bytes itself."""
        ...

    def purge_older_than(self, cutoff_epoch: float) -> int: ...


class LocalMediaStorage:
    name = "local"

    def __init__(self, directory: Path):
        self.directory = directory

    def _path(self, key: str) -> Path:
        # Keys are generated server-side (uuid4 hex + extension), but never
        # let one escape the directory regardless.
        safe = Path(key).name
        if safe != key or not safe:
            raise ValueError(f"Invalid media key: {key!r}")
        return self.directory / safe

    def save(self, key: str, data: bytes, content_type: str) -> None:
        # Created on first write, not at import: a read-only filesystem must
        # not stop the app from booting just because this backend exists.
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(key).write_bytes(data)

    def read(self, key: str) -> bytes | None:
        try:
            path = self._path(key)
        except ValueError:
            return None
        return path.read_bytes() if path.is_file() else None

    def signed_url(self, key: str, expires_in: int) -> str | None:
        return None

    def purge_older_than(self, cutoff_epoch: float) -> int:
        try:
            entries = list(self.directory.iterdir())
        except (FileNotFoundError, NotADirectoryError, OSError):
            return 0

        removed = 0
        for entry in entries:
            try:
                if not entry.is_file() or entry.stat().st_mtime >= cutoff_epoch:
                    continue
                entry.unlink()
                removed += 1
            except OSError:
                # One locked or unremovable file must not stop the sweep.
                logger.warning("Could not purge expired upload %s", entry.name, exc_info=True)
        return removed


class SupabaseMediaStorage:
    name = "supabase"

    # The list endpoint's page size; the sweep walks pages oldest-first.
    _PAGE = 100

    def __init__(self, url: str, service_key: str, bucket: str, timeout: float = 15.0):
        self.base = url.rstrip("/") + "/storage/v1"
        self.bucket = bucket
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
        })

    def _object_url(self, *parts: str) -> str:
        return "/".join([self.base, *(quote(part, safe="") for part in parts)])

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        try:
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise MediaStorageError(f"Storage request failed: {exc}") from exc
        return response

    def save(self, key: str, data: bytes, content_type: str) -> None:
        response = self._request(
            "POST",
            self._object_url("object", self.bucket, key),
            files={"file": (key, data, content_type)},
            headers={"x-upsert": "false"},
        )
        if response.status_code >= 400:
            raise MediaStorageError(f"Upload failed ({response.status_code}): {response.text[:200]}")

    def read(self, key: str) -> bytes | None:
        response = self._request("GET", self._object_url("object", self.bucket, key))
        # Storage answers a missing object with 400 or 404 depending on version.
        if response.status_code in (400, 404):
            return None
        if response.status_code >= 400:
            raise MediaStorageError(f"Download failed ({response.status_code})")
        return response.content

    def signed_url(self, key: str, expires_in: int) -> str | None:
        response = self._request(
            "POST",
            self._object_url("object", "sign", self.bucket, key),
            json={"expiresIn": int(expires_in)},
        )
        if response.status_code in (400, 404):
            return None
        if response.status_code >= 400:
            raise MediaStorageError(f"Signing failed ({response.status_code})")
        signed = (response.json() or {}).get("signedURL")
        # The API returns a path relative to /storage/v1, e.g.
        # "/object/sign/<bucket>/<key>?token=...".
        return f"{self.base}{signed}" if signed else None

    def _list_page(self, offset: int) -> list[dict]:
        response = self._request(
            "POST",
            self._object_url("object", "list", self.bucket),
            json={
                "prefix": "",
                "limit": self._PAGE,
                "offset": offset,
                "sortBy": {"column": "created_at", "order": "asc"},
            },
        )
        if response.status_code >= 400:
            raise MediaStorageError(f"List failed ({response.status_code})")
        return response.json() or []

    def purge_older_than(self, cutoff_epoch: float) -> int:
        expired: list[str] = []
        offset = 0
        while True:
            page = self._list_page(offset)
            for item in page:
                created = _parse_timestamp(item.get("created_at"))
                # Folder placeholders have no id; only real objects expire.
                if item.get("id") is None or created is None:
                    continue
                if created < cutoff_epoch:
                    expired.append(item["name"])
            # Sorted oldest-first: once a page reaches past the cutoff, every
            # later page is newer still.
            newest = _parse_timestamp(page[-1].get("created_at")) if page else None
            if len(page) < self._PAGE or (newest is not None and newest >= cutoff_epoch):
                break
            offset += self._PAGE

        removed = 0
        for start in range(0, len(expired), self._PAGE):
            batch = expired[start:start + self._PAGE]
            response = self._request(
                "DELETE", self._object_url("object", self.bucket), json={"prefixes": batch}
            )
            if response.status_code >= 400:
                raise MediaStorageError(f"Delete failed ({response.status_code})")
            removed += len(batch)
        return removed


def _parse_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _on_serverless() -> bool:
    return bool(os.getenv("VERCEL"))


_storage: MediaStorage | None = None


def configured_backend() -> str:
    backend = (settings.MEDIA_STORAGE_BACKEND or "").strip().lower()
    if backend:
        return backend
    return "supabase" if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY else "local"


def get_media_storage() -> MediaStorage:
    """The configured backend. Raises MediaStorageUnavailable when none works here."""
    global _storage
    if _storage is not None:
        return _storage

    backend = configured_backend()
    if backend == "supabase":
        if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
            raise MediaStorageUnavailable(
                "MEDIA_STORAGE_BACKEND=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY"
            )
        _storage = SupabaseMediaStorage(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, settings.SUPABASE_STORAGE_BUCKET
        )
    elif backend == "local":
        if _on_serverless():
            raise MediaStorageUnavailable(
                "Photo storage is not configured: local disk does not persist on Vercel. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (see DEPLOYMENT.md)."
            )
        directory = Path(settings.MEDIA_LOCAL_DIR) if settings.MEDIA_LOCAL_DIR else DEFAULT_LOCAL_DIR
        _storage = LocalMediaStorage(directory)
    else:
        raise MediaStorageUnavailable(f"Unknown MEDIA_STORAGE_BACKEND: {backend!r}")
    return _storage


def reset_media_storage() -> None:
    """Forget the cached backend (tests, and after a config change)."""
    global _storage
    _storage = None


def retention_cutoff(max_age_hours: int | None = None) -> float:
    window = max_age_hours if max_age_hours is not None else settings.MEDIA_RETENTION_HOURS
    return time.time() - window * 3600
