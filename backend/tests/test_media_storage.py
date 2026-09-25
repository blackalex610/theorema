"""Photo storage: the backends, the backend choice, and the HTTP flow on top.

Photos used to go to `backend/app/uploads/` on local disk, which is read-only
on Vercel and not shared between instances — so in production an upload
either 500'd or landed on a disk the next request could not see.
"""
import itertools
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import channel_state_store, media_storage
from app.services.media_storage import (
    LocalMediaStorage,
    MediaStorageError,
    MediaStorageUnavailable,
    SupabaseMediaStorage,
    get_media_storage,
)
from app.services.media_tokens import build_media_url

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64

client = TestClient(app)
_ip = itertools.count()


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    storage = LocalMediaStorage(tmp_path)
    monkeypatch.setattr(media_storage, "_storage", storage)
    return storage


@pytest.fixture
def fresh_choice(monkeypatch):
    """Let get_media_storage() choose from settings again."""
    monkeypatch.setattr(media_storage, "_storage", None)
    for name in ("MEDIA_STORAGE_BACKEND", "MEDIA_LOCAL_DIR", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.setattr(media_storage.settings, name, "")
    monkeypatch.delenv("VERCEL", raising=False)
    yield
    media_storage.reset_media_storage()


def _session() -> dict:
    res = client.post("/auth/guest", headers={"X-Forwarded-For": f"198.51.100.{next(_ip) % 254 + 1}"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _upload(headers, data=JPEG, channel="channel_test_01"):
    return client.post(
        "/mobile/uploads",
        headers=headers,
        data={"channel_id": channel, "problem_number": "34"},
        files={"file": ("photo.jpg", data, "image/jpeg")},
    )


# ─── LocalMediaStorage ───────────────────────────────────────────────────────

def test_local_round_trip(local_storage):
    local_storage.save("a.jpg", JPEG, "image/jpeg")
    assert local_storage.read("a.jpg") == JPEG
    assert local_storage.read("missing.jpg") is None
    assert local_storage.signed_url("a.jpg", 60) is None, "local media is streamed by /media"


def test_local_creates_its_directory_on_first_write_not_at_import(tmp_path):
    storage = LocalMediaStorage(tmp_path / "later")
    assert not (tmp_path / "later").exists()
    storage.save("a.jpg", JPEG, "image/jpeg")
    assert (tmp_path / "later" / "a.jpg").is_file()


@pytest.mark.parametrize("key", ["../escape.jpg", "sub/dir.jpg", ""])
def test_local_keys_cannot_leave_the_directory(local_storage, key):
    with pytest.raises(ValueError):
        local_storage.save(key, JPEG, "image/jpeg")
    assert local_storage.read(key) is None


# ─── Backend choice ──────────────────────────────────────────────────────────

def test_defaults_to_local_disk_in_development(fresh_choice):
    assert isinstance(get_media_storage(), LocalMediaStorage)


def test_refuses_local_disk_on_vercel(fresh_choice, monkeypatch):
    """Working on one request and losing the photo on the next is worse than a clear 503."""
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(MediaStorageUnavailable):
        get_media_storage()


def test_supabase_is_chosen_automatically_once_configured(fresh_choice, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(media_storage.settings, "SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(media_storage.settings, "SUPABASE_SERVICE_ROLE_KEY", "service-key")
    storage = get_media_storage()
    assert isinstance(storage, SupabaseMediaStorage)
    assert storage.bucket == "homework-photos"


def test_explicit_supabase_without_credentials_is_unavailable(fresh_choice, monkeypatch):
    monkeypatch.setattr(media_storage.settings, "MEDIA_STORAGE_BACKEND", "supabase")
    with pytest.raises(MediaStorageUnavailable):
        get_media_storage()


def test_an_unknown_backend_name_is_unavailable(fresh_choice, monkeypatch):
    monkeypatch.setattr(media_storage.settings, "MEDIA_STORAGE_BACKEND", "s3")
    with pytest.raises(MediaStorageUnavailable):
        get_media_storage()


# ─── SupabaseMediaStorage over a fake HTTP session ───────────────────────────

class _Response:
    def __init__(self, status_code=200, json_body=None, content=b"", text=""):
        self.status_code = status_code
        self._json = json_body
        self.content = content
        self.text = text

    def json(self):
        return self._json


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def _supabase(responses):
    storage = SupabaseMediaStorage("https://proj.supabase.co/", "service-key", "homework-photos")
    fake = _FakeSession(responses)
    fake.headers.update(storage._session.headers)
    storage._session = fake
    return storage, fake


def test_supabase_authenticates_with_the_service_key():
    storage = SupabaseMediaStorage("https://proj.supabase.co", "service-key", "b")
    assert storage._session.headers["Authorization"] == "Bearer service-key"
    assert storage._session.headers["apikey"] == "service-key"


def test_supabase_save_posts_the_object_without_overwriting():
    storage, fake = _supabase([_Response(200, {"Key": "homework-photos/a.jpg"})])
    storage.save("a.jpg", JPEG, "image/jpeg")
    method, url, kwargs = fake.calls[0]
    assert (method, url) == ("POST", "https://proj.supabase.co/storage/v1/object/homework-photos/a.jpg")
    assert kwargs["headers"]["x-upsert"] == "false"
    assert kwargs["files"]["file"] == ("a.jpg", JPEG, "image/jpeg")


def test_supabase_save_failure_raises():
    storage, _ = _supabase([_Response(403, text="new row violates row-level security policy")])
    with pytest.raises(MediaStorageError):
        storage.save("a.jpg", JPEG, "image/jpeg")


def test_supabase_read_treats_missing_as_none():
    storage, _ = _supabase([_Response(200, content=JPEG), _Response(400), _Response(404)])
    assert storage.read("a.jpg") == JPEG
    assert storage.read("gone.jpg") is None
    assert storage.read("gone.jpg") is None


def test_supabase_signed_url_is_made_absolute():
    storage, fake = _supabase([_Response(200, {"signedURL": "/object/sign/homework-photos/a.jpg?token=abc"})])
    url = storage.signed_url("a.jpg", 600)
    assert url == "https://proj.supabase.co/storage/v1/object/sign/homework-photos/a.jpg?token=abc"
    method, called, kwargs = fake.calls[0]
    assert called == "https://proj.supabase.co/storage/v1/object/sign/homework-photos/a.jpg"
    assert kwargs["json"] == {"expiresIn": 600}


def test_supabase_network_errors_become_storage_errors():
    import requests

    storage = SupabaseMediaStorage("https://proj.supabase.co", "k", "b")

    class Down:
        headers = {}

        def request(self, *args, **kwargs):
            raise requests.ConnectionError("no route to host")

    storage._session = Down()
    with pytest.raises(MediaStorageError):
        storage.read("a.jpg")


def _iso(age_hours: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(time.time() - age_hours * 3600, tz=timezone.utc).isoformat()


def test_supabase_purge_deletes_only_expired_objects():
    listing = [
        {"id": "1", "name": "old.jpg", "created_at": _iso(48)},
        {"id": None, "name": "folder", "created_at": None},
        {"id": "2", "name": "new.jpg", "created_at": _iso(1)},
    ]
    storage, fake = _supabase([_Response(200, listing), _Response(200, [])])
    removed = storage.purge_older_than(time.time() - 24 * 3600)
    assert removed == 1
    method, url, kwargs = fake.calls[1]
    assert (method, url) == ("DELETE", "https://proj.supabase.co/storage/v1/object/homework-photos")
    assert kwargs["json"] == {"prefixes": ["old.jpg"]}


def test_supabase_purge_pages_through_a_full_listing():
    page_size = SupabaseMediaStorage._PAGE
    first = [{"id": str(i), "name": f"o{i}.jpg", "created_at": _iso(72)} for i in range(page_size)]
    second = [{"id": "x", "name": "last-old.jpg", "created_at": _iso(30)}]
    storage, fake = _supabase([_Response(200, first), _Response(200, second), _Response(200, []), _Response(200, [])])
    assert storage.purge_older_than(time.time() - 24 * 3600) == page_size + 1
    assert fake.calls[1][2]["json"]["offset"] == page_size


def test_supabase_purge_with_nothing_expired_deletes_nothing():
    storage, fake = _supabase([_Response(200, [{"id": "1", "name": "new.jpg", "created_at": _iso(1)}])])
    assert storage.purge_older_than(time.time() - 24 * 3600) == 0
    assert len(fake.calls) == 1


# ─── The HTTP flow ───────────────────────────────────────────────────────────

def test_upload_then_view_round_trip(local_storage):
    res = _upload(_session())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["content_type"] == "image/jpeg"
    assert local_storage.read(body["file_name"]) == JPEG

    path = body["file_url"].split("testserver", 1)[-1]
    media = client.get(path)
    assert media.status_code == 200
    assert media.content == JPEG
    assert media.headers["content-type"] == "image/jpeg"
    assert media.headers["x-content-type-options"] == "nosniff"


def test_the_stored_type_comes_from_the_bytes_not_the_filename(local_storage):
    res = _upload(_session(), data=PNG)
    assert res.status_code == 200, res.text
    assert res.json()["file_name"].endswith(".png")
    assert res.json()["content_type"] == "image/png"


def test_webp_is_accepted(local_storage):
    res = _upload(_session(), data=WEBP)
    assert res.status_code == 200, res.text
    assert res.json()["file_name"].endswith(".webp")


@pytest.mark.parametrize("payload", [HEIC, b"<html><script>alert(1)</script></html>"])
def test_anything_that_is_not_a_supported_image_is_refused(local_storage, payload):
    """HEIC can't be read by the grader, and anything stored is later served
    back as an image — so the content decides, not the label."""
    res = _upload(_session(), data=payload)
    assert res.status_code == 415
    assert list(local_storage.directory.iterdir()) == []


def test_upload_without_configured_storage_is_a_clear_503(monkeypatch):
    monkeypatch.setattr(media_storage, "_storage", None)
    monkeypatch.setattr(media_storage.settings, "MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setenv("VERCEL", "1")
    res = _upload(_session())
    assert res.status_code == 503


def test_a_failing_bucket_is_a_503_not_a_500(monkeypatch):
    class Broken(LocalMediaStorage):
        def save(self, key, data, content_type):
            raise MediaStorageError("bucket down")

    monkeypatch.setattr(media_storage, "_storage", Broken(media_storage.DEFAULT_LOCAL_DIR))
    assert _upload(_session()).status_code == 503


def test_media_redirects_to_the_bucket_when_it_can_sign(monkeypatch):
    class Signing(LocalMediaStorage):
        def signed_url(self, key, expires_in):
            return f"https://proj.supabase.co/storage/v1/object/sign/b/{key}?token=t"

    monkeypatch.setattr(media_storage, "_storage", Signing(media_storage.DEFAULT_LOCAL_DIR))
    url = build_media_url("a.jpg")
    res = client.get(url, follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"].startswith("https://proj.supabase.co/")


def test_media_still_requires_a_valid_token(local_storage):
    local_storage.save("a.jpg", JPEG, "image/jpeg")
    assert client.get("/media/a.jpg").status_code == 403
    assert client.get("/media/a.jpg?token=1.forged").status_code == 403


def test_grade_photo_only_accepts_a_photo_uploaded_to_that_channel(local_storage):
    """Any signed-in user used to be able to name any stored file."""
    headers = _session()
    local_storage.save("someone-elses.jpg", JPEG, "image/jpeg")
    context = client.post(
        "/mobile/tasks/context",
        headers=headers,
        json={"channel_id": "channel_grade_01", "problem_number": 34, "a": 1, "b": 2,
              "correct_xy": "x=1", "updated_at": "now"},
    )
    assert context.status_code == 200, context.text

    res = client.post(
        "/mobile/tasks/grade-photo",
        headers=headers,
        json={"channel_id": "channel_grade_01", "problem_number": 34, "file_name": "someone-elses.jpg"},
    )
    assert res.status_code == 404
    channel_state_store.clear_uploads("channel_grade_01")


# ─── The scan credit is charged only for a scan that happened ────────────────

def _session_with_id() -> tuple[int, dict]:
    res = client.post("/auth/guest", headers={"X-Forwarded-For": f"198.51.100.{next(_ip) % 254 + 1}"})
    assert res.status_code == 200, res.text
    body = res.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


def _scans_used(db, user_id: int) -> int:
    from app.models.user import User

    db.expire_all()
    return db.query(User).filter(User.id == user_id).one().image_scans_today


def test_a_stored_upload_costs_one_scan(local_storage, db):
    user_id, headers = _session_with_id()
    assert _upload(headers).status_code == 200
    assert _scans_used(db, user_id) == 1


def test_a_refused_file_costs_nothing(local_storage, db):
    """The free plan has two scans a day; a file the server refuses must not spend one."""
    user_id, headers = _session_with_id()
    assert _upload(headers, data=HEIC).status_code == 415
    assert _scans_used(db, user_id) == 0


def test_a_storage_failure_costs_nothing(monkeypatch, db):
    class Broken(LocalMediaStorage):
        def save(self, key, data, content_type):
            raise MediaStorageError("bucket down")

    monkeypatch.setattr(media_storage, "_storage", Broken(media_storage.DEFAULT_LOCAL_DIR))
    user_id, headers = _session_with_id()
    assert _upload(headers).status_code == 503
    assert _scans_used(db, user_id) == 0


def test_the_daily_limit_still_applies(local_storage, db):
    user_id, headers = _session_with_id()
    assert _upload(headers).status_code == 200
    assert _upload(headers).status_code == 200
    res = _upload(headers)
    assert res.status_code == 429, "the free plan's two scans a day"
    assert _scans_used(db, user_id) == 2


# ─── The desktop polls; grades are stored where it will find them ────────────

def test_a_photo_grade_is_kept_on_the_task_for_the_desktop_to_poll(local_storage, monkeypatch):
    """Grades used to exist only as SSE events, held in one process's memory:
    on serverless a desktop on another instance never saw them."""
    from app.routers import mobile_uploads

    monkeypatch.setattr(mobile_uploads, "_grade_photo_with_ai", lambda *a: (True, "x=1", "Вярно!"))
    headers = _session()
    channel = "channel_poll_grade_01"
    context = {"channel_id": channel, "problem_number": 34, "a": 1, "b": 2, "correct_xy": "x=1", "updated_at": "now"}
    assert client.post("/mobile/tasks/context", headers=headers, json=context).status_code == 200
    uploaded = _upload(headers, channel=channel).json()

    graded = client.post(
        "/mobile/tasks/grade-photo",
        headers=headers,
        json={"channel_id": channel, "problem_number": 34, "file_name": uploaded["file_name"]},
    )
    assert graded.status_code == 200, graded.text

    contexts = client.get("/mobile/tasks/contexts", headers=headers, params={"channel_id": channel}).json()
    assert contexts[0]["last_grade"]["is_correct"] is True
    assert contexts[0]["last_grade"]["feedback"] == "Вярно!"
    channel_state_store.clear_uploads(channel)


def test_registering_a_task_again_clears_its_old_grade(local_storage):
    headers = _session()
    context = {"channel_id": "channel_poll_grade_02", "problem_number": 35, "a": 1, "b": 2,
               "correct_xy": "x=2", "updated_at": "now"}
    client.post("/mobile/tasks/context", headers=headers, json=context)
    contexts = client.get("/mobile/tasks/contexts", headers=headers,
                          params={"channel_id": "channel_poll_grade_02"}).json()
    assert contexts[0]["last_grade"] is None


def test_the_sse_stream_is_gone():
    """It was the last channel route that needed nothing but the channel id."""
    assert client.get("/mobile/uploads/stream", params={"channel_id": "channel_test_01"}).status_code == 404
