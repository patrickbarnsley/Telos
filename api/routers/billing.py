"""Checkout, the customer portal, and the Stripe webhook.

The webhook is the only endpoint in the whole API that is deliberately public,
which makes signature verification the thing holding it up. An unverified
webhook endpoint lets anyone POST themselves a subscription.
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from api.deps import current_account, fail

log = logging.getLogger("telos.billing")
router = APIRouter(prefix="/api", tags=["billing"])

SITE_URL = os.getenv("SITE_URL", "https://app.usetelosapp.com")


def _stripe():
    import stripe
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Payments are not set up yet.")
    stripe.api_key = key
    return stripe


class CheckoutIn(BaseModel):
    annual: bool = False


@router.get("/billing")
def billing_state(account: str = Depends(current_account)):
    """What the user is on, and whether a founding seat is still available."""
    from core.billing import FOUNDING_SEATS, founding_seats_taken, get_billing
    from core.plans import get_plan, plan_label
    row = get_billing(account) or {}
    taken = founding_seats_taken()
    return {
        "plan": get_plan(account),
        "plan_label": plan_label(account),
        "status": row.get("status"),
        "current_period_end": row.get("current_period_end"),
        "founding_seats_left": max(0, FOUNDING_SEATS - taken),
        "has_subscription": bool(row.get("stripe_subscription_id")),
    }


@router.post("/billing/checkout")
def checkout(body: CheckoutIn, account: str = Depends(current_account)):
    from core.billing import get_billing, price_for_new_subscriber, upsert_billing
    from core.plans import get_plan

    if get_plan(account) == "pro":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You are already on Pro. Manage your plan from the billing portal.")

    stripe = _stripe()
    # The price is resolved server-side, from a live count. The client says only
    # whether it wants annual; it never names a price.
    price_id = price_for_new_subscriber(annual=body.annual)
    if not price_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Payments are not set up yet.")

    row = get_billing(account) or {}
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{SITE_URL}/account?checkout=done",
            cancel_url=f"{SITE_URL}/account?checkout=cancelled",
            customer=row.get("stripe_customer_id") or None,
            customer_email=None if row.get("stripe_customer_id") else account,
            client_reference_id=account,
            allow_promotion_codes=True,
            automatic_tax={"enabled": True},
            subscription_data={"metadata": {"tester_name": account}},
            metadata={"tester_name": account},
        )
    except Exception as exc:
        raise fail(exc, "starting checkout")

    upsert_billing(account, price_id=price_id)
    return {"url": session.url}


@router.post("/billing/portal")
def portal(account: str = Depends(current_account)):
    """Stripe's hosted portal. Cancellation must never require emailing anyone."""
    from core.billing import get_billing
    row = get_billing(account) or {}
    customer = row.get("stripe_customer_id")
    if not customer:
        raise HTTPException(status.HTTP_409_CONFLICT, "No billing account yet.")
    stripe = _stripe()
    try:
        sess = stripe.billing_portal.Session.create(
            customer=customer, return_url=f"{SITE_URL}/account")
    except Exception as exc:
        raise fail(exc, "opening the billing portal")
    return {"url": sess.url}


@router.post("/stripe/webhook", include_in_schema=False)
async def webhook(request: Request):
    import stripe
    from core.billing import (account_for_customer, already_handled,
                              apply_subscription_state, upsert_billing)

    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Not configured.")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        # .to_dict() matters: construct_event returns a stripe.Event, which
        # raises on .get() rather than behaving like the mapping it looks like.
        # Without this the first real webhook 500s instead of granting a plan.
        event = stripe.Webhook.construct_event(payload, sig, secret).to_dict()
    except HTTPException:
        raise
    except Exception:
        # Deliberately says nothing about why. A verification oracle helps only
        # the person forging the signature. The body is never logged.
        log.warning("rejected a webhook with a bad or missing signature")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature.")

    event_id = event.get("id", "")
    event_type = event.get("type", "")
    if already_handled(event_id, event_type):
        # Stripe retries. Answer 200 so it stops, but change nothing.
        return {"received": True, "duplicate": True}

    obj = (event.get("data") or {}).get("object") or {}

    def account_of() -> str | None:
        return (obj.get("client_reference_id")
                or (obj.get("metadata") or {}).get("tester_name")
                or account_for_customer(obj.get("customer") or ""))

    if event_type == "checkout.session.completed":
        account = account_of()
        if account:
            upsert_billing(account,
                           stripe_customer_id=obj.get("customer"),
                           stripe_subscription_id=obj.get("subscription"))
            apply_subscription_state(account, "active",
                                     subscription_id=obj.get("subscription") or "")

    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        account = account_of()
        if account:
            price = ""
            items = (obj.get("items") or {}).get("data") or []
            if items:
                price = ((items[0].get("price") or {}).get("id")) or ""
            apply_subscription_state(account, obj.get("status") or "active",
                                     price_id=price,
                                     subscription_id=obj.get("id") or "",
                                     period_end=obj.get("current_period_end"))

    elif event_type == "customer.subscription.deleted":
        account = account_of()
        if account:
            # Back to free. Their rows are untouched: the allowance shrinks,
            # the job search does not disappear.
            apply_subscription_state(account, "canceled")

    elif event_type == "invoice.payment_failed":
        account = account_of()
        # Stripe retries on its own schedule. Only the final failure downgrades.
        if account and obj.get("next_payment_attempt") in (None, 0):
            apply_subscription_state(account, "past_due")

    elif event_type == "invoice.payment_succeeded":
        account = account_of()
        if account:
            apply_subscription_state(account, "active")

    return {"received": True}
