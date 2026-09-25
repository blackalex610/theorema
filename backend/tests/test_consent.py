"""Age check and recorded consent (app/services/consent.py).

Signing in used to show one line of small print — "if you are under 14, ask a
parent" — and record nothing. Every account now answers once, and the answer
is stored where an export, a deletion and an audit can all find it.
"""
import itertools
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.event_log import EventLog
from app.models.user import User
from app.services import consent
from app.services.user_data import delete_user_account, export_user_data

client = TestClient(app)
_ip = itertools.count()


def _session() -> tuple[int, dict]:
    res = client.post("/auth/guest", headers={"X-Forwarded-For": f"203.0.113.{next(_ip) % 254 + 1}"})
    assert res.status_code == 200, res.text
    body = res.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


def test_a_new_account_is_asked_for_consent():
    _, headers = _session()
    assert client.get("/auth/me", headers=headers).json()["consent_required"] is True


def test_the_sign_in_payload_carries_the_flag_too():
    res = client.post("/auth/guest", headers={"X-Forwarded-For": "203.0.113.250"})
    assert res.json()["user"]["consent_required"] is True


def test_consent_requires_a_session():
    assert client.post("/auth/consent", json={"age_group": "14_plus", "confirmed": True}).status_code == 401


def test_a_student_of_14_or_over_consents_for_themselves(db):
    user_id, headers = _session()
    res = client.post("/auth/consent", headers=headers, json={"age_group": "14_plus", "confirmed": True})
    assert res.status_code == 200, res.text
    assert res.json()["user"]["consent_required"] is False

    db.expire_all()
    user = db.query(User).get(user_id)
    assert user.age_group == "14_plus"
    assert user.parental_consent is False
    assert user.consent_version == consent.CONSENT_VERSION
    assert user.consent_recorded_at is not None
    assert client.get("/auth/me", headers=headers).json()["consent_required"] is False


def test_an_under_14_account_records_parental_consent(db):
    user_id, headers = _session()
    res = client.post("/auth/consent", headers=headers, json={"age_group": "under_14", "confirmed": True})
    assert res.status_code == 200, res.text

    db.expire_all()
    assert db.query(User).get(user_id).parental_consent is True


@pytest.mark.parametrize("age_group", ["14_plus", "under_14"])
def test_an_unticked_box_records_nothing(db, age_group):
    user_id, headers = _session()
    res = client.post("/auth/consent", headers=headers, json={"age_group": age_group, "confirmed": False})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "CONSENT_NOT_CONFIRMED"

    db.expire_all()
    assert db.query(User).get(user_id).consent_version is None


def test_an_unknown_age_group_is_rejected():
    _, headers = _session()
    res = client.post("/auth/consent", headers=headers, json={"age_group": "12", "confirmed": True})
    assert res.status_code == 422


def test_changed_documents_ask_again(monkeypatch):
    _, headers = _session()
    client.post("/auth/consent", headers=headers, json={"age_group": "14_plus", "confirmed": True})
    monkeypatch.setattr(consent, "CONSENT_VERSION", "2099-01-01")
    assert client.get("/auth/me", headers=headers).json()["consent_required"] is True


def _consent_logs(db, user_id: int) -> list[dict]:
    rows = db.query(EventLog).filter(EventLog.log_type == "consent").all()
    return [p for p in (json.loads(r.payload_json) for r in rows) if p.get("user_id") == user_id]


def test_every_answer_is_kept_as_an_audit_trail(db):
    user_id, headers = _session()
    client.post("/auth/consent", headers=headers, json={"age_group": "under_14", "confirmed": True})
    client.post("/auth/consent", headers=headers, json={"age_group": "14_plus", "confirmed": True})

    trail = _consent_logs(db, user_id)
    assert [entry["age_group"] for entry in trail] == ["under_14", "14_plus"]
    assert all(entry["consent_version"] == consent.CONSENT_VERSION for entry in trail)


def test_the_record_is_exported_and_deleted_with_the_account(db):
    user_id, headers = _session()
    client.post("/auth/consent", headers=headers, json={"age_group": "under_14", "confirmed": True})
    db.expire_all()
    user = db.query(User).get(user_id)

    exported = export_user_data(db, user)
    assert exported["account"]["age_group"] == "under_14"
    assert exported["account"]["parental_consent"] is True
    assert any(log.get("age_group") == "under_14" for log in exported["submitted_logs"])

    delete_user_account(db, user)
    assert _consent_logs(db, user_id) == []
