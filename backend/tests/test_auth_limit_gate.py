"""Regression tests for the plan-limit gate.

The gate used to return `None` (i.e. full free access) whenever the caller
simply omitted the Authorization header, which made every paid limit opt-in.
These tests pin the corrected behaviour so it cannot silently regress.
"""
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

from app.auth.dependencies import (
    FREE_LIMITS,
    increment_usage,
    require_admin,
    require_ai_chat,
    require_image_scan,
    require_nvo_exam,
    require_nvo_exam_capacity,
)
from app.config import settings


def _token_for(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _bearer(user) -> str:
    return f"Bearer {_token_for(user.id)}"


GATES = [
    pytest.param(require_ai_chat, "ai_chat", id="ai_chat"),
    pytest.param(require_nvo_exam, "nvo_exams", id="nvo_exams"),
    pytest.param(require_image_scan, "image_scans", id="image_scans"),
]


# ─── The bypass that used to exist ───────────────────────────────────────────

@pytest.mark.parametrize("gate,feature", GATES)
def test_missing_authorization_header_is_rejected(gate, feature, db):
    """No header must be a 401, never a free pass."""
    with pytest.raises(HTTPException) as exc:
        gate(authorization=None, db=db)
    assert exc.value.status_code == 401


@pytest.mark.parametrize("gate,feature", GATES)
@pytest.mark.parametrize("header", ["", "Basic abc", "Bearer", "Bearer not-a-jwt"])
def test_malformed_or_invalid_token_is_rejected(gate, feature, header, db):
    with pytest.raises(HTTPException) as exc:
        gate(authorization=header, db=db)
    assert exc.value.status_code == 401


# ─── Metering ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("gate,feature", GATES)
def test_valid_token_consumes_exactly_one_credit(gate, feature, db, make_user):
    user = make_user()
    before = getattr(user, f"{feature}_today")

    gate(authorization=_bearer(user), db=db)

    db.refresh(user)
    assert getattr(user, f"{feature}_today") == before + 1


@pytest.mark.parametrize("gate,feature", GATES)
def test_free_user_is_blocked_at_the_daily_limit(gate, feature, db, make_user):
    limit = FREE_LIMITS[feature]
    user = make_user(**{f"{feature}_today": limit, "usage_reset_date": date.today()})

    with pytest.raises(HTTPException) as exc:
        gate(authorization=_bearer(user), db=db)

    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "LIMIT_REACHED"
    assert exc.value.detail["feature"] == feature


def test_the_limit_payload_has_no_dead_upgrade_url(db, make_user):
    """`upgrade_url` used to hardcode a domain and a `/settings#upgrade`
    fragment that isn't a route — settings is a modal, not a page — and no
    frontend code ever read the field. Pinning its absence so it can't creep
    back in without someone actually wiring it to something real.
    """
    user = make_user(ai_chat_today=FREE_LIMITS["ai_chat"], usage_reset_date=date.today())

    with pytest.raises(HTTPException) as exc:
        require_ai_chat(authorization=_bearer(user), db=db)

    assert "upgrade_url" not in exc.value.detail


@pytest.mark.parametrize("gate,feature", GATES)
def test_premium_user_passes_the_free_limit(gate, feature, db, make_user):
    user = make_user(
        plan="premium",
        **{f"{feature}_today": FREE_LIMITS[feature], "usage_reset_date": date.today()},
    )
    # Must not raise: premium is not bound by the free ceiling.
    gate(authorization=_bearer(user), db=db)


@pytest.mark.parametrize("gate,feature", GATES)
def test_counters_reset_on_a_new_calendar_day(gate, feature, db, make_user):
    """A user who hit the cap yesterday starts today at 1, not blocked."""
    user = make_user(
        **{f"{feature}_today": FREE_LIMITS[feature],
           "usage_reset_date": date.today() - timedelta(days=1)},
    )

    gate(authorization=_bearer(user), db=db)

    db.refresh(user)
    assert getattr(user, f"{feature}_today") == 1
    assert user.usage_reset_date == date.today()


def test_token_signed_with_the_wrong_secret_is_rejected(db, make_user):
    user = make_user()
    forged = jwt.encode({"sub": str(user.id)}, "attacker-secret", algorithm=settings.ALGORITHM)

    with pytest.raises(HTTPException) as exc:
        require_ai_chat(authorization=f"Bearer {forged}", db=db)
    assert exc.value.status_code == 401


# ─── Admin gate ──────────────────────────────────────────────────────────────

def test_require_admin_rejects_anonymous(db):
    with pytest.raises(HTTPException) as exc:
        require_admin(authorization=None, db=db)
    assert exc.value.status_code == 401


def test_require_admin_rejects_a_normal_logged_in_user(db, make_user):
    """Being logged in must not be enough for /admin/* or reset-all-xp."""
    user = make_user(is_admin=0)

    with pytest.raises(HTTPException) as exc:
        require_admin(authorization=_bearer(user), db=db)
    assert exc.value.status_code == 403


def test_require_admin_allows_an_admin(db, make_user):
    admin = make_user(is_admin=1)
    assert require_admin(authorization=_bearer(admin), db=db).id == admin.id


# ─── require_nvo_exam_capacity: check without charging ──────────────────────
#
# POST /nvo/generate-job used to charge the daily nvo_exams credit via
# require_nvo_exam (check-and-increment) before generation ever ran, so a
# student whose generation failed (AI error and the pool fallback both
# failing) lost their one-exam-per-day allowance for nothing. This gate only
# verifies capacity; nvo.py charges it via increment_usage once an exam
# actually exists.

def test_capacity_check_does_not_charge_a_credit(db, make_user):
    user = make_user()
    before = user.nvo_exams_today

    require_nvo_exam_capacity(authorization=_bearer(user), db=db)

    db.refresh(user)
    assert user.nvo_exams_today == before  # unchanged


def test_capacity_check_still_blocks_at_the_daily_limit(db, make_user):
    limit = FREE_LIMITS["nvo_exams"]
    user = make_user(nvo_exams_today=limit, usage_reset_date=date.today())

    with pytest.raises(HTTPException) as exc:
        require_nvo_exam_capacity(authorization=_bearer(user), db=db)
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "LIMIT_REACHED"


def test_capacity_check_rejects_anonymous_callers(db):
    with pytest.raises(HTTPException) as exc:
        require_nvo_exam_capacity(authorization=None, db=db)
    assert exc.value.status_code == 401


def test_increment_usage_actually_charges_the_credit(db, make_user):
    user = make_user()
    before = user.nvo_exams_today

    increment_usage(user, db, "nvo_exams")

    db.refresh(user)
    assert user.nvo_exams_today == before + 1


def test_increment_usage_refuses_past_the_limit(db, make_user):
    """Re-checked at charge time too, in case capacity was spent elsewhere
    between the check and the credit actually being charged."""
    limit = FREE_LIMITS["nvo_exams"]
    user = make_user(nvo_exams_today=limit, usage_reset_date=date.today())

    with pytest.raises(HTTPException) as exc:
        increment_usage(user, db, "nvo_exams")
    assert exc.value.status_code == 429
