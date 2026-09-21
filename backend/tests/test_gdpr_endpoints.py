"""HTTP layer for GDPR access/portability/erasure.

A student (or their parent) must be able to take their data and to leave.
Neither was possible before: there was no export endpoint and no deletion
endpoint at all, for a product whose users are 11-14 year olds in the EU.
"""
import itertools

from fastapi.testclient import TestClient

from app.main import app
from app.models.progress import XpEvent
from app.models.user import User

client = TestClient(app)

_ip_counter = itertools.count()


def _from_ip() -> dict:
    return {"X-Forwarded-For": f"198.51.100.{next(_ip_counter) % 254 + 1}"}


def _new_session() -> tuple[int, dict]:
    """A real guest account + its auth header, through the real HTTP flow."""
    res = client.post("/auth/guest", headers=_from_ip())
    assert res.status_code == 200, res.text
    body = res.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


# ─── Export ──────────────────────────────────────────────────────────────────

def test_export_requires_authentication():
    assert client.get("/auth/me/export").status_code == 401


def test_export_returns_the_callers_own_data():
    user_id, headers = _new_session()

    res = client.get("/auth/me/export", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["account"]["id"] == user_id
    assert "progress" in body
    assert "submitted_logs" in body


def test_export_is_offered_as_a_download():
    """Portability means a file the student can keep, not a page to squint at."""
    _, headers = _new_session()

    res = client.get("/auth/me/export", headers=headers)

    assert "attachment" in res.headers.get("content-disposition", "")


# ─── Erasure ─────────────────────────────────────────────────────────────────

def test_delete_requires_authentication():
    assert client.delete("/auth/me").status_code == 401


def test_delete_removes_the_account_and_its_rows(db):
    user_id, headers = _new_session()
    db.add(XpEvent(user_id=user_id, source_type="test", xp_amount=10, reason="test"))
    db.commit()

    res = client.delete("/auth/me", headers=headers)

    assert res.status_code == 200
    assert res.json()["deleted"] is True
    db.expire_all()
    assert db.query(User).filter(User.id == user_id).one_or_none() is None
    assert db.query(XpEvent).filter(XpEvent.user_id == user_id).count() == 0


def test_the_token_stops_working_after_deletion():
    """The account is gone, so the JWT it issued must resolve to nobody."""
    _, headers = _new_session()
    assert client.delete("/auth/me", headers=headers).status_code == 200

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_deleting_twice_is_not_a_500():
    _, headers = _new_session()
    assert client.delete("/auth/me", headers=headers).status_code == 200

    assert client.delete("/auth/me", headers=headers).status_code == 401
