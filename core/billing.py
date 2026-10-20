"""Stripe linkage, kept out of the routers on purpose.

Two rules shape this module. Stripe state never becomes a second source of truth
about what a user may do: every subscription change ends in a `set_plan` call, so
`core/plans.py` stays the only thing that decides quotas. And every webhook is
treated as something a stranger may have sent, because the endpoint is public.
"""
import os
from datetime import datetime, timezone

FOUNDING_SEATS = int(os.getenv("TELOS_FOUNDING_SEATS", "50"))

PRICE_FOUNDING = os.getenv("STRIPE_PRICE_FOUNDING", "")
PRICE_MONTHLY = os.getenv("STRIPE_PRICE_MONTHLY", "")
PRICE_ANNUAL = os.getenv("STRIPE_PRICE_ANNUAL", "")

# Stripe statuses that mean "this person is paying". Anything else is free.
ACTIVE = {"active", "trialing"}


def init_billing_tables(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS billing (
            tester_name TEXT PRIMARY KEY,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            status TEXT,
            price_id TEXT,
            current_period_end TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_customer "
                   "ON billing (stripe_customer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_status ON billing (status, price_id)")
    # Idempotency. Stripe retries, and will deliver the same event more than
    # once. The primary key is the whole mechanism: a duplicate insert fails and
    # the handler stops before applying anything twice.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stripe_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT,
            received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Called from five places, not only init_db, so a billing table can appear
    # long after the schema was last hardened. It protects itself on creation
    # rather than relying on whoever happened to call it.
    from core.database import protect_public_schema
    protect_public_schema(cursor)

def _conn():
    from core.database import get_connection
    return get_connection()


def already_handled(event_id: str, event_type: str = "") -> bool:
    """Claim this event. True means someone already did, so stop."""
    if not event_id:
        return False
    conn = _conn(); cur = conn.cursor()
    init_billing_tables(cur)
    cur.execute("SELECT 1 FROM stripe_events WHERE event_id = %s", (event_id,))
    seen = cur.fetchone() is not None
    if not seen:
        cur.execute("INSERT INTO stripe_events (event_id, event_type) VALUES (%s, %s)",
                    (event_id, event_type))
        conn.commit()
    cur.close(); conn.close()
    return seen


def founding_seats_taken() -> int:
    """Counted in the database at the moment of asking.

    Not cached and never checked in the browser. A cap that can be beaten by
    refreshing the page is not a cap.
    """
    if not PRICE_FOUNDING:
        return 0
    conn = _conn(); cur = conn.cursor()
    init_billing_tables(cur)
    cur.execute(
        "SELECT count(*) FROM billing WHERE price_id = %s AND status = ANY(%s)",
        (PRICE_FOUNDING, list(ACTIVE)))
    n = cur.fetchone()[0]
    cur.close(); conn.close()
    return int(n or 0)


def price_for_new_subscriber(annual: bool = False) -> str:
    """The founding price while seats remain, otherwise the standard one."""
    if annual:
        return PRICE_ANNUAL
    if PRICE_FOUNDING and founding_seats_taken() < FOUNDING_SEATS:
        return PRICE_FOUNDING
    return PRICE_MONTHLY


def offered_prices() -> list[dict]:
    """What a new subscriber would actually be charged, asked of Stripe.

    The amounts are never written down here and never sent from the browser.
    The screen that quotes a price and the checkout that charges it now read the
    same Stripe Price object, so they cannot drift apart. They had drifted:
    Upgrade.tsx carried 12, 19 and 190 in its markup while this module resolved
    whatever the environment pointed at.

    Not cached. A stale amount is exactly the bug this function exists to close,
    and the billing screen is not hot enough to be worth the risk.

    Returns an empty list when Stripe is not configured, which is also how
    "Telos does not charge yet" is expressed: no price ids, no paywall, no code
    change.
    """
    key = os.getenv("STRIPE_SECRET_KEY", "")
    wanted = [("founding", PRICE_FOUNDING), ("monthly", PRICE_MONTHLY),
              ("annual", PRICE_ANNUAL)]
    wanted = [(k, pid) for k, pid in wanted if pid]
    if not key or not wanted:
        return []

    import stripe
    stripe.api_key = key

    seats_left = 0
    if PRICE_FOUNDING:
        seats_left = max(0, FOUNDING_SEATS - founding_seats_taken())

    # While founding seats remain, price_for_new_subscriber returns the founding
    # price, so the standard monthly one is not actually purchasable. Offering
    # both would quote a price the checkout refuses to use.
    if PRICE_FOUNDING and seats_left > 0:
        wanted = [(k, pid) for k, pid in wanted if k != "monthly"]

    out = []
    for kind, price_id in wanted:
        # One unreachable price must not blank the whole screen, so each is
        # fetched on its own and a failure drops just that option.
        try:
            price = stripe.Price.retrieve(price_id)
        except Exception:
            continue
        recurring = price.get("recurring") or {}
        if kind == "founding" and seats_left <= 0:
            continue
        out.append({
            "kind": kind,
            "amount_cents": price.get("unit_amount"),
            "currency": (price.get("currency") or "usd").upper(),
            "interval": recurring.get("interval"),
            "interval_count": recurring.get("interval_count") or 1,
        })
    return out


def get_billing(tester_name: str) -> dict | None:
    conn = _conn(); cur = conn.cursor()
    init_billing_tables(cur)
    cur.execute("""SELECT tester_name, stripe_customer_id, stripe_subscription_id,
                          status, price_id, current_period_end
                     FROM billing WHERE tester_name = %s""", (tester_name,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return None
    keys = ("tester_name", "stripe_customer_id", "stripe_subscription_id",
            "status", "price_id", "current_period_end")
    return dict(zip(keys, row))


def upsert_billing(tester_name: str, **fields) -> None:
    if not tester_name:
        return
    allowed = ("stripe_customer_id", "stripe_subscription_id", "status",
               "price_id", "current_period_end")
    sets = {k: v for k, v in fields.items() if k in allowed}
    conn = _conn(); cur = conn.cursor()
    init_billing_tables(cur)
    cur.execute("INSERT INTO billing (tester_name) VALUES (%s) ON CONFLICT DO NOTHING",
                (tester_name,))
    if sets:
        clause = ", ".join(f"{k} = %s" for k in sets)
        cur.execute(f"UPDATE billing SET {clause}, updated_at = NOW() WHERE tester_name = %s",
                    (*sets.values(), tester_name))
    conn.commit(); cur.close(); conn.close()


def account_for_customer(customer_id: str) -> str | None:
    if not customer_id:
        return None
    conn = _conn(); cur = conn.cursor()
    init_billing_tables(cur)
    cur.execute("SELECT tester_name FROM billing WHERE stripe_customer_id = %s LIMIT 1",
                (customer_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row[0] if row else None


def apply_subscription_state(tester_name: str, status: str, *, price_id: str = "",
                             subscription_id: str = "", period_end=None) -> str:
    """Record Stripe's view, then let core.plans decide what it means.

    Returns the plan the account ended on. A downgrade never deletes anything:
    the allowance shrinks and the data stays, because nobody should lose a job
    search because a card expired.
    """
    from core.plans import set_plan
    fields = {"status": status}
    if price_id:
        fields["price_id"] = price_id
    if subscription_id:
        fields["stripe_subscription_id"] = subscription_id
    if period_end:
        fields["current_period_end"] = (
            datetime.fromtimestamp(period_end, tz=timezone.utc)
            if isinstance(period_end, (int, float)) else period_end)
    upsert_billing(tester_name, **fields)

    plan = "pro" if status in ACTIVE else "free"
    set_plan(tester_name, plan)
    return plan
