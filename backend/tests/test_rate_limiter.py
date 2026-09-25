"""The per-IP limiter counts in the database, shared by every instance.

Its counts used to live in a dict per process; on Vercel each serverless
instance is its own process, so a burst spread across instances was never
limited at all.
"""
import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.main import app
from app.middleware import ip_rate_limiter as limiter

client = TestClient(app)
_ip = itertools.count(1)
NOW = 1_900_000_000  # pinned so a test never straddles a window boundary


@pytest.fixture(autouse=True)
def _pinned_clock(monkeypatch):
    monkeypatch.setattr(limiter, "_epoch", lambda: NOW)


def _fresh_ip() -> str:
    return f"100.64.{next(_ip) // 250}.{next(_ip) % 250 + 1}"


def test_counts_are_shared_across_instances():
    """Two processes that each forget their local state still see one count."""
    bucket = f"{_fresh_ip()}:default"
    assert limiter._hit_shared(bucket, 60)[0] == 1
    limiter._buckets.clear()  # a different instance, as far as memory goes
    assert limiter._hit_shared(bucket, 60)[0] == 2


def test_a_new_window_starts_from_zero(monkeypatch):
    bucket = f"{_fresh_ip()}:default"
    limiter._hit_shared(bucket, 60)
    monkeypatch.setattr(limiter, "_epoch", lambda: NOW + 60)
    assert limiter._hit_shared(bucket, 60)[0] == 1


def test_the_guest_tier_is_enforced_end_to_end():
    headers = {"X-Forwarded-For": _fresh_ip()}
    codes = [client.post("/auth/guest", headers=headers).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429


def test_each_ip_has_its_own_count():
    first, second = _fresh_ip(), _fresh_ip()
    for _ in range(5):
        client.post("/auth/guest", headers={"X-Forwarded-For": first})
    assert client.post("/auth/guest", headers={"X-Forwarded-For": second}).status_code == 200


def test_the_limiter_falls_back_to_local_counts_when_the_database_is_down(monkeypatch):
    def down(bucket, window):
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(limiter, "_hit_shared", down)
    headers = {"X-Forwarded-For": _fresh_ip()}
    codes = [client.post("/auth/guest", headers=headers).status_code for _ in range(6)]
    assert codes[5] == 429, "still limited, from this process's own counts"


def test_an_absurd_forwarded_header_does_not_break_the_key():
    res = client.post("/auth/guest", headers={"X-Forwarded-For": "9" * 5000})
    assert res.status_code in (200, 429)


def test_old_windows_are_pruned(monkeypatch):
    bucket = f"{_fresh_ip()}:default"
    monkeypatch.setattr(limiter, "_epoch", lambda: NOW - 10_000)
    limiter._hit_shared(bucket, 60)
    monkeypatch.setattr(limiter, "_epoch", lambda: NOW)
    monkeypatch.setattr(limiter, "_PRUNE_PROBABILITY", 1.0)
    limiter._hit_shared(bucket, 60)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT window_start FROM rate_limit_counters WHERE bucket = :b"), {"b": bucket}
        ).scalars().all()
    assert rows == [NOW - NOW % 60]
