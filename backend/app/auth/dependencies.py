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

def _check_and_increment(user: User, db: Session, feature: str) -> User:
    limits = _get_limits(user)
    used: int = getattr(user, f"{feature}_today")
    limit: int = limits[feature]
    label = FEATURE_LABELS.get(feature, feature)

    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "LIMIT_REACHED",
                "feature": feature,
                "limit": limit,
                "used": used,
                "plan": user.plan,
                "remaining": 0,
                "upgrade_url": "https://smartnvo.vercel.app/settings#upgrade",
                "message": (
                    f"Достигнахте дневния лимит от {limit} {label}. "
                    "Надградете до Premium за неограничен достъп."
                ),
            },
        )

    setattr(user, f"{feature}_today", used + 1)
    db.commit()
    return user


def _optional_limit_check(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    feature: str = "",
) -> User:
    """Enforce limits for any caller. No valid JWT -> 401, never free pass.

    SECURITY: previously returned None when no Authorization header was sent,
    which let anyone bypass every plan limit. Now a missing/invalid token is a
    hard 401 so the monetization gating cannot be skipped.
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


def require_ai_chat(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    return _optional_limit_check(authorization, db, "ai_chat")


def require_nvo_exam(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    return _optional_limit_check(authorization, db, "nvo_exams")


def require_image_scan(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    return _optional_limit_check(authorization, db, "image_scans")


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
