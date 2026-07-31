from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.auth.dependencies import get_current_user, FREE_LIMITS
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("/status")
async def plan_status(current_user: User = Depends(get_current_user)):
    """Return current plan + daily usage counters + account age."""
    is_premium = current_user.plan == "premium"
    limits = {k: 999_999 for k in FREE_LIMITS} if is_premium else FREE_LIMITS

    def _slot(used: int, feature: str):
        limit = limits[feature]
        return {"used": used, "limit": limit, "remaining": max(0, limit - used)}

    now = datetime.now(timezone.utc)
    created = current_user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    days_since_signup = (now - created).days

    return {
        "plan": current_user.plan,
        "is_premium": is_premium,
        "days_since_signup": days_since_signup,
        "usage": {
            "ai_exercises":  _slot(current_user.ai_exercises_today,  "ai_exercises"),
            "ai_chat":       _slot(current_user.ai_chat_today,        "ai_chat"),
            "ai_theory":     _slot(current_user.ai_theory_today,      "ai_theory"),
            "nvo_exams":     _slot(current_user.nvo_exams_today,      "nvo_exams"),
            "image_scans":   _slot(current_user.image_scans_today,    "image_scans"),
        },
    }


@router.post("/upgrade")
async def upgrade_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Premium upgrade endpoint.

    SECURITY: previously set plan="premium" unconditionally with no payment
    check. That let any logged-in user grant themselves unlimited AI. Now the
    endpoint requires a real payment integration before any plan change.
    """
    # TODO: integrate Stripe / payment provider, then upgrade only after a
    # successful, verified payment event. Until then, reject the request.
    raise HTTPException(
        status_code=402,
        detail="Премиум ъпгрейдът все още не е активен. Моля, опитайте по-късно.",
    )
