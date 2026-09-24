"""
Auth dependencies: JWT decoding, plan limit enforcement.
"""
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

# ─── Plan limits ──────────────────────────────────────────────────────────────

FREE_LIMITS = {
    "ai_exercises":   5,   # 5 AI exercises / day
    "ai_chat":       10,   # 10 chat messages / day
    "ai_theory":     12,   # 12 AI theory generations / day (uncached only)
    "nvo_exams":      1,   # 1 NVO simulation / day
    "image_scans":    2,   # 2 photo uploads / day
}

PREMIUM_LIMITS = {
    "ai_exercises":  999_999,
    "ai_chat":       999_999,
    "ai_theory":     999_999,
    "nvo_exams":     999_999,
    "image_scans":   999_999,
}

FEATURE_LABELS = {
    "ai_exercises": "AI задачи",
    "ai_chat":      "AI съобщения",
    "ai_theory":    "AI теория",
    "nvo_exams":    "НВО изпита",
    "image_scans":  "снимки",
}


def _get_limits(user: User) -> dict:
    return PREMIUM_LIMITS if user.plan == "premium" else FREE_LIMITS


def _reset_if_new_day(user: User) -> None:
    """Reset daily counters if the calendar day has changed."""
    today = date.today()
    if user.usage_reset_date != today:
        user.ai_exercises_today = 0
        user.ai_chat_today = 0
        user.ai_theory_today = 0
        user.nvo_exams_today = 0
        user.image_scans_today = 0
        user.usage_reset_date = today


# ─── Core dependency ──────────────────────────────────────────────────────────

def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _reset_if_new_day(user)
    db.commit()
    return user


def get_optional_user(
    authorization: str = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns user or None — for endpoints accessible to both auth'd and anon users."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return get_current_user(authorization=authorization, db=db)
    except HTTPException:
        return None


def require_admin(
    authorization: str = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Require an authenticated user with the admin role.

    SECURITY: used to gate sensitive endpoints (/admin/migrate, admin log
    viewers, reset-all-xp). Raises 401 without a valid token and 403 without
    the admin flag.
    """
    user = get_current_user(authorization=authorization, db=db)
    is_admin = getattr(user, "is_admin", False)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


# ─── Limit-gated dependencies ─────────────────────────────────────────────────

def _has_capacity(user: User, feature: str) -> bool:
    limits = _get_limits(user)
    used: int = getattr(user, f"{feature}_today")
    return used < limits[feature]


def _raise_limit_reached(user: User, feature: str) -> None:
    limits = _get_limits(user)
    used: int = getattr(user, f"{feature}_today")
    limit: int = limits[feature]
    label = FEATURE_LABELS.get(feature, feature)
    raise HTTPException(
        status_code=429,
        detail={
            "code": "LIMIT_REACHED",
            "feature": feature,
            "limit": limit,
            "used": used,
            "plan": user.plan,
            "remaining": 0,
            # No `upgrade_url` here on purpose: it used to hardcode
            # https://smartnvo.vercel.app/settings#upgrade, a route that
            # never existed (Settings is a modal, not a page) on a domain
            # nothing confirms is even the real deployment — and no
            # frontend code ever read the field. The actual upgrade path
            # is UpgradePrompt.tsx dispatching OPEN_SETTINGS_MODAL_EVENT,
            # which needs no URL at all.
            "message": (
                f"Достигнахте дневния лимит от {limit} {label}. "
                "Надградете до Premium за неограничен достъп."
            ),
        },
    )


def _check_and_increment(user: User, db: Session, feature: str) -> User:
    if not _has_capacity(user, feature):
        _raise_limit_reached(user, feature)
    setattr(user, f"{feature}_today", getattr(user, f"{feature}_today") + 1)
    db.commit()
    return user


def _check_capacity_only(user: User, feature: str) -> User:
    """Verify the daily limit isn't already exhausted, without spending it.

    Used where the credit must only be charged after the paid-for work
    actually succeeds — see require_nvo_exam_capacity / increment_usage
    below and nvo.py's create_nvo_generation_job. Charging up front made a
    student whose generation failed lose their one-exam-per-day credit for
    nothing.
    """
    if not _has_capacity(user, feature):
        _raise_limit_reached(user, feature)
    return user


def increment_usage(user: User, db: Session, feature: str) -> None:
    """Charge one credit for `feature` after the work it pays for succeeded.

    Re-checks capacity rather than trusting the earlier _check_capacity_only
    call: defends against a race where the same user's other credit-consuming
    request spent the last slot in between the check and this call.
    """
    if not _has_capacity(user, feature):
        _raise_limit_reached(user, feature)
    setattr(user, f"{feature}_today", getattr(user, f"{feature}_today") + 1)
    db.commit()


def _require_auth_and_limit(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    feature: str = "",
) -> User:
    """Enforce auth + the per-feature daily limit. No valid JWT -> 401.

    SECURITY: this used to be `_optional_limit_check`, which returned None when
    no Authorization header was sent and thereby let anyone bypass every plan
    limit. A missing/invalid token is now a hard 401 and the credit is always
    metered, so the monetization gating cannot be skipped. There is deliberately
    no "skip limit" path here: any endpoint that must bypass metering has to opt
    out explicitly by depending on something other than this helper.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required to use this feature.",
        )
    return _check_and_increment(get_current_user(authorization=authorization, db=db), db, feature)


def get_limit_warning(user: Optional[User], feature: str) -> Optional[dict]:
    """
    Check if user is approaching their limit (80%+ used).
    Returns warning info or None if no warning needed.
    Only for authenticated users (returns None if user is None).
    """
    if not user or not user.plan:
        return None
    
    limits = _get_limits(user)
    used: int = getattr(user, f"{feature}_today", 0)
    limit: int = limits[feature]
    label = FEATURE_LABELS.get(feature, feature)
    
    if user.plan == "premium":
        return None  # Premium users have no limits
    
    percentage = (used / limit * 100) if limit > 0 else 0
    
    if percentage >= 80:  # Warn at 80% usage
        remaining = max(0, limit - used)
        return {
            "warning": True,
            "feature": feature,
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percentage": round(percentage, 0),
            "label": label,
            "message": f"Вече сте използвали {used}/{limit} {label} днес. Остават {remaining}."
        }
    
    return None


def enforce_ai_exercise_generation(
    authorization: Optional[str],
    db: Session,
) -> User:
    """Require auth + daily limit before generating uncached AI exercises."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REQUIRED",
                "message": "Влезте в профил, за да генерирате AI упражнения.",
            },
        )
    user = get_current_user(authorization=authorization, db=db)
    return _check_and_increment(user, db, "ai_exercises")


def enforce_ai_examples_generation(
    authorization: Optional[str],
    db: Session,
) -> User:
    """Require auth + daily limit before generating uncached AI example problems.

    Shares the ai_theory budget (examples are lesson content), but deliberately
    skips check_theory_cooldown: the lesson page fires the theory and examples
    requests concurrently, so applying the theory cooldown here would 429 the
    examples request every time a lesson is opened.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REQUIRED",
                "message": "Влезте в профил, за да генерирате AI примери.",
            },
        )
    user = get_current_user(authorization=authorization, db=db)
    return _check_and_increment(user, db, "ai_theory")


def require_ai_chat(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    return _require_auth_and_limit(authorization, db, "ai_chat")


def require_nvo_exam(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    return _require_auth_and_limit(authorization, db, "nvo_exams")


def require_nvo_exam_capacity(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Like require_nvo_exam, but only verifies the daily limit — it does not
    spend the credit. NVO generation charges it only once an exam actually
    exists (see nvo.py's create_nvo_generation_job + increment_usage), so a
    generation failure (AI error and the pool fallback both failing) does not
    cost the student their one-exam-per-day allowance for nothing.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required to use this feature.",
        )
    return _check_capacity_only(get_current_user(authorization=authorization, db=db), "nvo_exams")


def require_image_scan(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    return _require_auth_and_limit(authorization, db, "image_scans")


def require_image_scan_capacity(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Like require_image_scan, but only verifies the daily limit.

    The free plan gets two scans a day. Charging up front meant a photo the
    server then refused (not an image, storage down) or a model call that
    failed still cost one of them; the endpoints charge via increment_usage
    once the scan has actually happened, as NVO generation does.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required to use this feature.",
        )
    return _check_capacity_only(get_current_user(authorization=authorization, db=db), "image_scans")


def enforce_ai_theory_generation(
    authorization: Optional[str],
    db: Session,
) -> User:
    """Require auth + daily limit + cooldown before generating uncached AI theory."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REQUIRED",
                "message": "Влезте в профил, за да генерирате AI теория.",
            },
        )
    user = get_current_user(authorization=authorization, db=db)
    check_theory_cooldown(user, db)
    return _check_and_increment(user, db, "ai_theory")


# ─── AI chat cooldown (2 seconds between messages) ────────────────────────────

CHAT_COOLDOWN_SECONDS = 2


def check_chat_cooldown(user: User, db: Session) -> None:
    """Raise 429 if the user sent a chat message less than CHAT_COOLDOWN_SECONDS ago."""
    if user.last_ai_chat_at is None:
        return
    now = datetime.now(timezone.utc)
    last = (
        user.last_ai_chat_at.replace(tzinfo=timezone.utc)
        if user.last_ai_chat_at.tzinfo is None
        else user.last_ai_chat_at
    )
    elapsed = (now - last).total_seconds()
    if elapsed < CHAT_COOLDOWN_SECONDS:
        wait = round(CHAT_COOLDOWN_SECONDS - elapsed, 1)
        raise HTTPException(
            status_code=429,
            detail={
                "code": "COOLDOWN",
                "wait_seconds": wait,
                "message": f"Изчакайте {wait}s преди следващото съобщение.",
            },
        )


def update_last_chat_at(user: User, db: Session) -> None:
    user.last_ai_chat_at = datetime.now(timezone.utc)
    db.commit()


# ─── AI theory cooldown (5 seconds between generations) ───────────────────────

THEORY_COOLDOWN_SECONDS = 5


def check_theory_cooldown(user: User, db: Session) -> None:
    """Raise 429 if the user generated theory less than THEORY_COOLDOWN_SECONDS ago."""
    last_at = getattr(user, "last_ai_theory_at", None)
    if last_at is None:
        return
    now = datetime.now(timezone.utc)
    last = last_at.replace(tzinfo=timezone.utc) if last_at.tzinfo is None else last_at
    elapsed = (now - last).total_seconds()
    if elapsed < THEORY_COOLDOWN_SECONDS:
        wait = round(THEORY_COOLDOWN_SECONDS - elapsed, 1)
        raise HTTPException(
            status_code=429,
            detail={
                "code": "COOLDOWN",
                "wait_seconds": wait,
                "message": f"Изчакайте {wait}s преди следващото генериране на теория.",
            },
        )


def update_last_theory_at(user: User, db: Session) -> None:
    user.last_ai_theory_at = datetime.now(timezone.utc)
    db.commit()
