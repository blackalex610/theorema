"""Premium as a Stripe subscription (app/services/billing.py, routers/plan.py).

Stripe itself is replaced by a fake client, but webhook signatures are real:
each test event is signed exactly as Stripe signs it and goes through
stripe.Webhook.construct_event, so the check that keeps anyone from posting
"you are premium now" is exercised, not mocked.
"""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

import pytest
import stripe
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.routers.auth import _make_jwt
from app.services import billing

client = TestClient(app)
WEBHOOK_SECRET = "whsec_test_secret"
PERIOD_END = int(time.time()) + 30 * 86400


class FakeStripe:
    """The slice of StripeClient billing.py uses, recording what it was asked."""

    def __init__(self):
        self.checkouts: list[dict] = []
        self.portals: list[dict] = []
        self.subscriptions: dict[str, dict] = {}
        self.fail_with: Exception | None = None
        outer = self

        class _Sessions:
            def __init__(self, kind):
                self.kind = kind

            def create(self, params):
                (outer.checkouts if self.kind == "checkout" else outer.portals).append(params)
                return type("S", (), {"url": f"https://stripe.test/{self.kind}/1"})()

        class _Subscriptions:
            def retrieve(self, subscription_id):
                if outer.fail_with:
                    raise outer.fail_with
                # Real Stripe objects, not dicts: since stripe-python v15
                # they have no .get(), which plain dicts here once hid.
                return stripe.Subscription.construct_from(outer.subscriptions[subscription_id], "sk_test_x")

        class _Prices:
            def retrieve(self, price_id):
                return stripe.Price.construct_from(
                    {"unit_amount": 499, "currency": "eur", "recurring": {"interval": "month"}}, "sk_test_x"
                )

        class _Namespace:
            pass

        self.v1 = _Namespace()
        self.v1.checkout = _Namespace()
        self.v1.checkout.sessions = _Sessions("checkout")
        self.v1.billing_portal = _Namespace()
        self.v1.billing_portal.sessions = _Sessions("portal")
        self.v1.subscriptions = _Subscriptions()
        self.v1.prices = _Prices()


@pytest.fixture
def fake_stripe(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr(billing.settings, "STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setattr(billing.settings, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(billing.settings, "STRIPE_PRICE_ID", "price_monthly")
    monkeypatch.setattr(billing.settings, "APP_URL", "https://smartnvo.example")
    monkeypatch.setattr(billing, "stripe_client", lambda: fake)
    monkeypatch.setattr(billing, "_price_cache", None)
    return fake


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {_make_jwt(user.id)}"}


def _subscription(sub_id: str, user: User, status: str = "active", *, legacy_shape=False) -> dict:
    sub = {"id": sub_id, "customer": f"cus_{user.id}", "status": status, "metadata": {"user_id": str(user.id)}}
    if legacy_shape:
        sub["current_period_end"] = PERIOD_END
    else:
        sub["items"] = {"object": "list", "data": [{"object": "subscription_item", "current_period_end": PERIOD_END}]}
    return sub


def _post_event(event_type: str, obj: dict, secret: str = WEBHOOK_SECRET, signature: str | None = None):
    payload = json.dumps({"id": "evt_1", "object": "event", "type": event_type, "data": {"object": obj}})
    if signature is None:
        timestamp = int(time.time())
        digest = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
        signature = f"t={timestamp},v1={digest}"
    return client.post("/plan/webhook", content=payload, headers={"Stripe-Signature": signature})


def _reload(db, user: User) -> User:
    db.expire_all()
    return db.query(User).get(user.id)


# ─── Off until configured ────────────────────────────────────────────────────

def test_upgrading_is_refused_until_stripe_is_configured(make_user):
    assert client.post("/plan/upgrade", headers=_headers(make_user())).status_code == 402


def test_the_webhook_does_not_exist_until_configured():
    assert client.post("/plan/webhook", content=b"{}").status_code == 404


# ─── Checkout ────────────────────────────────────────────────────────────────

def test_upgrade_opens_a_checkout_for_the_monthly_price(fake_stripe, make_user):
    user = make_user()
    res = client.post("/plan/upgrade", headers=_headers(user))
    assert res.status_code == 200, res.text
    assert res.json() == {"checkout_url": "https://stripe.test/checkout/1"}

    params = fake_stripe.checkouts[0]
    assert params["mode"] == "subscription"
    assert params["line_items"] == [{"price": "price_monthly", "quantity": 1}]
    assert params["client_reference_id"] == str(user.id)
    assert params["subscription_data"]["metadata"] == {"user_id": str(user.id)}
    assert params["customer_email"] == user.email
    assert params["success_url"].startswith("https://smartnvo.example/")


def test_opening_checkout_does_not_grant_premium(fake_stripe, make_user, db):
    """Only the verified webhook changes the plan."""
    user = make_user()
    client.post("/plan/upgrade", headers=_headers(user))
    assert _reload(db, user).plan == "free"


def test_a_guest_must_sign_in_before_subscribing(fake_stripe, make_user):
    guest = make_user(is_guest=True)
    res = client.post("/plan/upgrade", headers=_headers(guest))
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "GUEST_CANNOT_SUBSCRIBE"


def test_a_premium_account_is_not_sold_premium_again(fake_stripe, make_user):
    res = client.post("/plan/upgrade", headers=_headers(make_user(plan="premium")))
    assert res.status_code == 409


def test_without_app_url_only_this_site_can_be_the_return_address(fake_stripe, make_user, monkeypatch):
    monkeypatch.setattr(billing.settings, "APP_URL", "")
    user = make_user()
    evil = client.post("/plan/upgrade", headers={**_headers(user), "Origin": "https://evil.example"})
    assert evil.status_code == 500
    ours = client.post("/plan/upgrade", headers={**_headers(user), "Origin": "http://testserver"})
    assert ours.status_code == 200
    assert fake_stripe.checkouts[-1]["success_url"].startswith("http://testserver/")


# ─── Webhook ─────────────────────────────────────────────────────────────────

def test_an_unsigned_or_forged_event_is_rejected(fake_stripe, make_user, db):
    user = make_user()
    fake_stripe.subscriptions["sub_1"] = _subscription("sub_1", user)
    event = {"id": "sub_1", "object": "subscription"}
    assert _post_event("customer.subscription.updated", event, signature="").status_code == 400
    assert _post_event("customer.subscription.updated", event, secret="whsec_attacker").status_code == 400
    assert _reload(db, user).plan == "free"


def test_a_completed_checkout_makes_the_account_premium(fake_stripe, make_user, db):
    user = make_user()
    fake_stripe.subscriptions["sub_1"] = _subscription("sub_1", user)
    res = _post_event("checkout.session.completed", {
        "id": "cs_1", "object": "checkout.session", "subscription": "sub_1",
        "customer": f"cus_{user.id}", "client_reference_id": str(user.id),
    })
    assert res.status_code == 200, res.text

    user = _reload(db, user)
    assert user.plan == "premium"
    assert user.stripe_customer_id == f"cus_{user.id}"
    assert user.subscription_status == "active"
    assert user.premium_until is not None
    assert billing.is_premium(user)


def test_the_older_api_shape_of_the_period_end_is_read_too(fake_stripe, make_user, db):
    user = make_user()
    fake_stripe.subscriptions["sub_2"] = _subscription("sub_2", user, legacy_shape=True)
    _post_event("customer.subscription.created", {"id": "sub_2", "object": "subscription"})
    assert _reload(db, user).premium_until is not None


def test_cancelling_ends_premium(fake_stripe, make_user, db):
    user = make_user()
    fake_stripe.subscriptions["sub_3"] = _subscription("sub_3", user)
    _post_event("customer.subscription.created", {"id": "sub_3", "object": "subscription"})
    fake_stripe.subscriptions["sub_3"] = _subscription("sub_3", user, status="canceled")
    _post_event("customer.subscription.deleted", {"id": "sub_3", "object": "subscription"})
    assert _reload(db, user).plan == "free"


def test_a_late_stale_event_cannot_move_the_plan_backwards(fake_stripe, make_user, db):
    """The event body says active; Stripe says canceled now. Now wins."""
    user = make_user()
    fake_stripe.subscriptions["sub_4"] = _subscription("sub_4", user, status="canceled")
    _post_event("customer.subscription.updated", {"id": "sub_4", "object": "subscription", "status": "active"})
    assert _reload(db, user).plan == "free"


def test_a_failing_renewal_keeps_premium_while_stripe_retries(fake_stripe, make_user, db):
    user = make_user()
    fake_stripe.subscriptions["sub_5"] = _subscription("sub_5", user, status="past_due")
    _post_event("customer.subscription.updated", {"id": "sub_5", "object": "subscription"})
    assert _reload(db, user).plan == "premium"


def test_stripe_being_down_asks_stripe_to_retry(fake_stripe, make_user):
    fake_stripe.fail_with = stripe.APIConnectionError("stripe unreachable")
    res = _post_event("customer.subscription.updated", {"id": "sub_x", "object": "subscription"})
    assert res.status_code == 502


def test_unrelated_events_are_acknowledged_and_ignored(fake_stripe):
    res = _post_event("invoice.paid", {"id": "in_1", "object": "invoice"})
    assert res.status_code == 200
    assert res.json()["outcome"] == "ignored"


# ─── Expiry and status ───────────────────────────────────────────────────────

@pytest.mark.parametrize("days_past,expected", [(None, True), (-10, True), (1, True), (4, False)])
def test_premium_lapses_a_grace_period_after_the_paid_through_date(make_user, days_past, expected):
    until = None if days_past is None else datetime.utcnow() - timedelta(days=days_past)
    user = make_user(plan="premium", premium_until=until)
    assert billing.is_premium(user) is expected


def test_a_lapsed_premium_account_gets_free_limits(make_user):
    user = make_user(plan="premium", premium_until=datetime.utcnow() - timedelta(days=30))
    body = client.get("/plan/status", headers=_headers(user)).json()
    assert body["is_premium"] is False
    assert body["usage"]["nvo_exams"]["limit"] == 1


def test_status_shows_the_real_price_and_what_the_account_can_do(fake_stripe, make_user):
    body = client.get("/plan/status", headers=_headers(make_user())).json()
    assert body["billing"]["enabled"] is True
    assert body["billing"]["can_subscribe"] is True
    assert body["billing"]["can_manage"] is False
    assert body["billing"]["price"] == {"amount": 499, "currency": "eur", "interval": "month"}


def test_the_portal_needs_a_subscription(fake_stripe, make_user):
    assert client.post("/plan/portal", headers=_headers(make_user())).status_code == 409


def test_the_portal_opens_for_a_subscriber(fake_stripe, make_user):
    user = make_user(stripe_customer_id="cus_portal_1")
    res = client.post("/plan/portal", headers=_headers(user))
    assert res.status_code == 200
    assert fake_stripe.portals[0]["customer"] == "cus_portal_1"
