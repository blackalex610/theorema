import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, FREE_LIMITS
from app.config import is_allowed_origin, settings
from app.database import get_db
from app.models.user import User
from app.services import billing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan", tags=["plan"])

BILLING_UNAVAILABLE = "Премиум ъпгрейдът все още не е активен. Моля, опитайте по-късно."


@router.get("/status")
async def plan_status(current_user: User = Depends(get_current_user)):
    """Return current plan + daily usage counters + account age."""
    is_premium = billing.is_premium(current_user)
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
        "plan": "premium" if is_premium else "free",
        "is_premium": is_premium,
        "days_since_signup": days_since_signup,
        "billing": {
            "enabled": billing.billing_enabled(),
            # Guests can't subscribe: a lost guest session would strand the
            # subscription on an account nobody can sign back into.
            "can_subscribe": billing.billing_enabled() and not current_user.is_guest and not is_premium,
            "can_manage": billing.billing_enabled() and bool(current_user.stripe_customer_id),
            "price": await run_in_threadpool(billing.price_summary),
            "premium_until": current_user.premium_until.isoformat() if current_user.premium_until else None,
            "status": current_user.subscription_status,
        },
        "usage": {
            "ai_exercises":  _slot(current_user.ai_exercises_today,  "ai_exercises"),
            "ai_chat":       _slot(current_user.ai_chat_today,        "ai_chat"),
            "ai_theory":     _slot(current_user.ai_theory_today,      "ai_theory"),
            "nvo_exams":     _slot(current_user.nvo_exams_today,      "nvo_exams"),
            "image_scans":   _slot(current_user.image_scans_today,    "image_scans"),
        },
    }


def _app_url(request: Request) -> str:
    """Where Stripe should send the browser back to."""
    if settings.APP_URL:
        return settings.APP_URL.rstrip("/")
    origin = (request.headers.get("origin") or "").rstrip("/")
    # Only the site itself or an allow-listed origin: a return URL is a
    # redirect target, and this one would carry a paying customer.
    if origin and (is_allowed_origin(origin) or urlsplit(origin).netloc == request.url.netloc):
        return origin
    raise HTTPException(status_code=500, detail="APP_URL is not configured")


@router.post("/upgrade")
async def upgrade_plan(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a Premium subscription: returns a Stripe Checkout URL to open.

    SECURITY: this used to set plan="premium" with no payment at all. It
    never changes the plan itself — only the verified webhook does, once
    Stripe reports the subscription paid. Answers 402 until Stripe is
    configured.
    """
    if not billing.billing_enabled():
        raise HTTPException(status_code=402, detail=BILLING_UNAVAILABLE)
    if current_user.is_guest:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "GUEST_CANNOT_SUBSCRIBE",
                "message": "Влез с Google, за да купиш Premium — така абонаментът остава към твоя профил.",
            },
        )
    if billing.is_premium(current_user):
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_PREMIUM", "message": "Premium вече е активен."},
        )

    app_url = _app_url(request)
    try:
        url = await run_in_threadpool(billing.create_checkout_url, current_user, app_url)
    except stripe.StripeError as exc:
        logger.exception("Creating a Stripe Checkout session failed")
        raise HTTPException(status_code=502, detail="Плащането временно не е достъпно.") from exc
    return {"checkout_url": url}


@router.post("/portal")
async def billing_portal(request: Request, current_user: User = Depends(get_current_user)):
    """Stripe's customer portal: change the card, see invoices, or cancel."""
    if not billing.billing_enabled():
        raise HTTPException(status_code=402, detail=BILLING_UNAVAILABLE)
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_SUBSCRIPTION", "message": "Няма абонамент за управление."},
        )
    app_url = _app_url(request)
    try:
        url = await run_in_threadpool(billing.create_portal_url, current_user, app_url)
    except stripe.StripeError as exc:
        logger.exception("Creating a Stripe billing portal session failed")
        raise HTTPException(status_code=502, detail="Плащането временно не е достъпно.") from exc
    return {"portal_url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe's subscription events. Unauthenticated by design — the
    Stripe-Signature header, checked against STRIPE_WEBHOOK_SECRET, is the
    authentication. Anything unverified is rejected before it is read."""
    if not billing.billing_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    payload = await request.body()
    try:
        event = billing.parse_event(payload, request.headers.get("stripe-signature"))
    except (ValueError, stripe.SignatureVerificationError):
        logger.warning("Rejected a Stripe webhook with a bad signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        outcome = await run_in_threadpool(billing.handle_event, db, event)
    except stripe.StripeError as exc:
        # A non-2xx makes Stripe retry the delivery later.
        logger.exception("Handling Stripe event %s failed", event.id)
        raise HTTPException(status_code=502, detail="Retry later") from exc
    return {"received": True, "outcome": outcome}
