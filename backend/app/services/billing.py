"""Premium as a monthly Stripe subscription.

`POST /plan/upgrade` used to either grant premium for free (fixed long ago) or
refuse with 402 because no payment provider existed. Now:

* /plan/upgrade opens a Stripe Checkout session for STRIPE_PRICE_ID and
  returns its URL; the browser pays on Stripe's page.
* Stripe tells us the outcome through a signed webhook (/plan/webhook). The
  plan only ever changes there — never on the strength of the browser coming
  back to a success URL, which anyone can visit.
* /plan/portal opens Stripe's customer portal to change the card or cancel.

Every webhook re-reads the subscription from Stripe instead of trusting the
event body, so events arriving late or out of order cannot move the plan
backwards. `premium_until` holds the paid-through date: `is_premium()` stops
honouring the plan a few days after it, so a missed cancellation webhook
cannot leave an account on Premium forever.

Everything here is inert until STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET and
STRIPE_PRICE_ID are all set; until then /plan/upgrade keeps answering 402.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import stripe
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

# Stripe retries a failed renewal for several days while the subscription is
# past_due; keep Premium through that window rather than cutting a paying
# family off on the first declined card.
PREMIUM_GRACE = timedelta(days=3)

# Statuses in which the subscription is paid for (or being retried).
PAID_STATUSES = {"active", "trialing", "past_due"}

_PRICE_CACHE_SECONDS = 3600
_price_cache: tuple[float, dict | None] | None = None


class BillingNotConfigured(RuntimeError):
    pass


def _plain(obj: Any) -> dict:
    """A Stripe object as a plain dict.

    Since stripe-python v15, StripeObject is no longer a dict: `.get()`
    raises. Everything below reads fields with `.get()`, so objects from the
    API or a verified webhook are converted once, here, at the boundary.
    """
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


def billing_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET and settings.STRIPE_PRICE_ID)


def _utcnow() -> datetime:
    # The users table stores naive UTC datetimes.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_premium(user: User) -> bool:
    """The one place that decides whether an account gets Premium limits."""
    if user.plan != "premium":
        return False
    until = user.premium_until
    return until is None or until + PREMIUM_GRACE > _utcnow()


@lru_cache(maxsize=2)
def _client(api_key: str) -> stripe.StripeClient:
    return stripe.StripeClient(
        api_key,
        max_network_retries=1,
        # The SDK default is 80 s; every call here sits on a request path.
        http_client=stripe.RequestsClient(timeout=20),
    )


def stripe_client() -> stripe.StripeClient:
    if not billing_enabled():
        raise BillingNotConfigured("Stripe is not configured")
    return _client(settings.STRIPE_SECRET_KEY)


# ─── Checkout and portal ─────────────────────────────────────────────────────

def create_checkout_url(user: User, app_url: str) -> str:
    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        "success_url": f"{app_url}/dashboard?upgrade=success",
        "cancel_url": f"{app_url}/dashboard?upgrade=cancelled",
        # All three carry the account id so whichever event arrives first can
        # be tied back to it.
        "client_reference_id": str(user.id),
        "metadata": {"user_id": str(user.id)},
        "subscription_data": {"metadata": {"user_id": str(user.id)}},
        "allow_promotion_codes": True,
        "locale": "bg",
    }
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    elif user.email:
        params["customer_email"] = user.email
    session = stripe_client().v1.checkout.sessions.create(params=params)
    return session.url


def create_portal_url(user: User, app_url: str) -> str:
    session = stripe_client().v1.billing_portal.sessions.create(
        params={"customer": user.stripe_customer_id, "return_url": f"{app_url}/dashboard"}
    )
    return session.url


def price_summary() -> dict | None:
    """Amount, currency and interval of STRIPE_PRICE_ID, for the upgrade card.

    Read from Stripe (cached for an hour) so the page shows what Checkout will
    actually charge. None when billing is off or Stripe cannot be reached.
    """
    global _price_cache
    if not billing_enabled():
        return None
    now = time.monotonic()
    if _price_cache and now - _price_cache[0] < _PRICE_CACHE_SECONDS:
        return _price_cache[1]
    try:
        price = _plain(stripe_client().v1.prices.retrieve(settings.STRIPE_PRICE_ID))
        recurring = price.get("recurring") or {}
        summary = {
            "amount": price.get("unit_amount"),
            "currency": price.get("currency"),
            "interval": recurring.get("interval"),
        }
    except stripe.StripeError:
        logger.warning("Could not read the Stripe price for the upgrade card", exc_info=True)
        summary = None
    _price_cache = (now, summary)
    return summary


# ─── Webhook ─────────────────────────────────────────────────────────────────

def parse_event(payload: bytes, signature: str | None) -> stripe.Event:
    """Verify the Stripe-Signature header. Raises stripe.SignatureVerificationError."""
    return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)


def _period_end(subscription: Any) -> datetime | None:
    # Newer API versions moved current_period_end from the subscription onto
    # its items; read whichever this account's API version sends.
    end = subscription.get("current_period_end")
    if end is None:
        items = (subscription.get("items") or {}).get("data") or []
        ends = [item.get("current_period_end") for item in items if item.get("current_period_end")]
        end = max(ends) if ends else None
    return datetime.fromtimestamp(end, tz=timezone.utc).replace(tzinfo=None) if end else None


def _find_user(db: Session, *, user_id: Any = None, subscription_id: str | None = None,
               customer_id: str | None = None) -> User | None:
    if user_id:
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
        except (TypeError, ValueError):
            user = None
        if user:
            return user
    if subscription_id:
        user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
        if user:
            return user
    if customer_id:
        return db.query(User).filter(User.stripe_customer_id == customer_id).first()
    return None


def _apply_subscription(db: Session, subscription: Any, user_id_hint: Any = None) -> User | None:
    subscription = _plain(subscription)
    metadata = subscription.get("metadata") or {}
    customer_id = subscription.get("customer")
    user = _find_user(
        db,
        user_id=metadata.get("user_id") or user_id_hint,
        subscription_id=subscription.get("id"),
        customer_id=customer_id,
    )
    if user is None:
        logger.error("Stripe subscription %s matches no account", subscription.get("id"))
        return None

    status = subscription.get("status")
    user.stripe_customer_id = customer_id or user.stripe_customer_id
    user.stripe_subscription_id = subscription.get("id")
    user.subscription_status = status
    user.premium_until = _period_end(subscription)
    if status in PAID_STATUSES:
        if user.plan != "premium":
            user.upgraded_at = user.upgraded_at or _utcnow()
        user.plan = "premium"
    else:
        # canceled, unpaid, incomplete, incomplete_expired, paused
        user.plan = "free"
    db.commit()
    logger.info("Account %s subscription %s is %s", user.id, subscription.get("id"), status)
    return user


def handle_event(db: Session, event: stripe.Event) -> str:
    """Apply one verified event. Returns a short outcome for the log/response."""
    event = _plain(event)
    event_type = event["type"]
    obj = event["data"]["object"]
    client = stripe_client()

    if event_type == "checkout.session.completed":
        subscription_id = obj.get("subscription")
        if not subscription_id:
            return "ignored: not a subscription checkout"
        subscription = client.v1.subscriptions.retrieve(subscription_id)
        user = _apply_subscription(db, subscription, user_id_hint=obj.get("client_reference_id"))
        return "applied" if user else "unmatched"

    if event_type.startswith("customer.subscription."):
        # Re-read rather than trust the event body: deliveries can arrive out
        # of order, and the current state is what should win.
        subscription = client.v1.subscriptions.retrieve(obj["id"])
        user = _apply_subscription(db, subscription)
        return "applied" if user else "unmatched"

    return "ignored"
