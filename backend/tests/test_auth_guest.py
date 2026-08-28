"""End-to-end coverage for the guest account flow.

Guest mode used to be entirely broken: the frontend deliberately discarded
its token and the route guard bounced it straight back to login (see
frontend/src/components/RequireAuth.tsx history). These tests exercise the
new real, durable guest account through the actual HTTP layer — a guest gets
a real user_id and a normal JWT, so every DB-backed feature must work for it
exactly like a signed-in user.
"""
import itertools

from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User

client = TestClient(app)

# Every test uses its own fake client IP (via X-Forwarded-For) so the per-IP
# guest cap counts each test in isolation, regardless of execution order or
# how many guest rows earlier tests in this session created.
_ip_counter = itertools.count()


def _from_ip() -> dict:
    return {"X-Forwarded-For": f"203.0.113.{next(_ip_counter) % 254 + 1}"}


def test_guest_login_creates_a_real_user(db):
    res = client.post("/auth/guest", headers=_from_ip())
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["user"]["is_guest"] is True
    assert body["user"]["email"] is None

    user = db.query(User).filter(User.id == body["user"]["id"]).first()
    assert user is not None
    assert user.is_guest is True
    assert user.google_sub is None


def test_repeated_guest_login_reuses_the_same_row(db):
    """A caller that already holds a guest token gets a fresh token for the
    SAME row, not a new one — the flood-prevention path."""
    ip = _from_ip()
    first = client.post("/auth/guest", headers=ip).json()
    second = client.post(
        "/auth/guest",
        headers={**ip, "Authorization": f"Bearer {first['access_token']}"},
    ).json()
    # The property that matters is the row, not the token bytes — two tokens
    # minted within the same second are legitimately identical (same sub,
    # iat, exp), so asserting token inequality would be a flaky, meaningless
    # check.
    assert second["user"]["id"] == first["user"]["id"]


def test_guest_token_grants_access_to_progress_endpoints(db):
    """The real proof guest progress persists: a DB-backed route that 401s
    without a user must succeed for a guest."""
    token = client.post("/auth/guest", headers=_from_ip()).json()["access_token"]
    res = client.get("/progress/xp-summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_auth_me_reports_guest_status(db):
    token = client.post("/auth/guest", headers=_from_ip()).json()["access_token"]
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["is_guest"] is True


def test_guest_cap_returns_429_past_the_per_ip_limit(db, monkeypatch):
    import app.routers.auth as auth_router

    monkeypatch.setattr(auth_router, "GUEST_CAP_PER_IP", 2)
    ip = _from_ip()
    for _ in range(2):
        assert client.post("/auth/guest", headers=ip).json()

    res = client.post("/auth/guest", headers=ip)
    assert res.status_code == 429
    assert res.json()["detail"]["code"] == "RATE_LIMITED"
