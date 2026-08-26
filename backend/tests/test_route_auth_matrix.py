"""Route-level audit of the endpoints that cost money or expose PII.

The per-dependency tests in test_auth_limit_gate.py prove the gates work. This
file proves they are actually *wired to the routes* — the original bugs were
not broken gates but missing ones (an unauthenticated /nvo/submit, an
unauthenticated /admin/migrate, and so on).
"""
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.auth.dependencies import (
    enforce_ai_examples_generation,
    enforce_ai_exercise_generation,
    enforce_ai_theory_generation,
    get_current_user,
    require_admin,
    require_ai_chat,
    require_image_scan,
    require_nvo_exam,
)
from app.main import app

# Any of these proves the route cannot be reached anonymously.
AUTH_DEPENDENCIES = {
    get_current_user,
    require_admin,
    require_ai_chat,
    require_image_scan,
    require_nvo_exam,
}

# Routes that reach OpenAI with caller-influenced text or images.
SPENDING_ROUTES = [
    ("POST", "/ai/chat"),
    ("POST", "/ai/diagram"),
    ("POST", "/nvo/generate"),
    ("POST", "/nvo/generate-job"),
    ("POST", "/nvo/submit"),
    ("POST", "/mobile/uploads"),
    ("POST", "/mobile/analyze-math"),
    ("POST", "/mobile/tasks/context"),
    ("POST", "/mobile/tasks/grade"),
    ("POST", "/mobile/tasks/grade-photo"),
    # Uncached AI call on every request — no cache layer to hide behind.
    ("GET", "/curriculum/lessons/{lesson_id}/video-search-queries"),
]

# Routes that mutate global state or return other people's data.
ADMIN_ROUTES = [
    ("POST", "/admin/migrate"),
    ("GET", "/log-error/recent"),
    ("GET", "/bug-report/recent"),
    ("POST", "/nvo/admin/reset-all-xp"),
    # Both of these had NO auth dependency at all until fixed alongside the
    # guest-account work — an anonymous caller could wipe every user's XP
    # profile, or destroy every user's exercise attempts for a lesson, with
    # one request. This allowlist is what let them slip through originally
    # (see the module docstring); they are pinned here explicitly.
    ("POST", "/progress/admin/reset-all-xp"),
    ("DELETE", "/curriculum/lessons/{lesson_id}/exercises/reset"),
    ("POST", "/auth/admin/purge-guests"),
]


def _flatten(dependant) -> set:
    found = set()
    for sub in dependant.dependencies:
        if sub.call is not None:
            found.add(sub.call)
        found |= _flatten(sub)
    return found


def _dependencies_of(method: str, path: str) -> set:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return _flatten(route.dependant)
    raise AssertionError(f"Route {method} {path} not found — did it move or get renamed?")


@pytest.mark.parametrize("method,path", SPENDING_ROUTES)
def test_openai_spending_routes_require_authentication(method, path):
    assert _dependencies_of(method, path) & AUTH_DEPENDENCIES, (
        f"{method} {path} reaches OpenAI without any auth dependency"
    )


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_privileged_routes_require_admin(method, path):
    assert require_admin in _dependencies_of(method, path), (
        f"{method} {path} is privileged but does not require an admin"
    )


def test_self_service_upgrade_cannot_grant_premium(db, make_user):
    """POST /plan/upgrade used to set plan='premium' with no payment at all."""
    import asyncio

    from app.routers.plan import upgrade_plan

    user = make_user()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(upgrade_plan(current_user=user, db=db))

    assert exc.value.status_code == 402
    db.refresh(user)
    assert user.plan == "free"


# ─── Header-enforced curriculum gates ────────────────────────────────────────
# These two do the check inside the handler (they must serve cached content to
# anyone, and only meter a *fresh* generation), so the route-dependency audit
# above cannot see them.

@pytest.mark.parametrize("enforce", [
    enforce_ai_examples_generation,
    enforce_ai_exercise_generation,
    enforce_ai_theory_generation,
])
@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer nonsense"])
def test_curriculum_generation_rejects_anonymous_callers(enforce, header, db):
    with pytest.raises(HTTPException) as exc:
        enforce(authorization=header, db=db)
    assert exc.value.status_code == 401


@pytest.mark.parametrize("enforce,feature", [
    (enforce_ai_examples_generation, "ai_theory"),
    (enforce_ai_exercise_generation, "ai_exercises"),
    (enforce_ai_theory_generation, "ai_theory"),
])
def test_curriculum_generation_consumes_a_credit(enforce, feature, db, make_user):
    from jose import jwt

    from app.config import settings

    user = make_user()
    token = jwt.encode({"sub": str(user.id)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    enforce(authorization=f"Bearer {token}", db=db)

    db.refresh(user)
    assert getattr(user, f"{feature}_today") == 1
