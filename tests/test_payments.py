"""Payments: the webhook, the founding-seat cap, and what deletion does to money.

Every event here is signed the way Stripe signs one, using the library's own
signature scheme rather than hand-written JSON, so a change in how Stripe frames
a payload fails this suite instead of production.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TELOS_TEST", "1")
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret_for_the_suite"
os.environ["STRIPE_PRICE_FOUNDING"] = "price_founding_12"
os.environ["STRIPE_PRICE_MONTHLY"] = "price_monthly_19"
os.environ["STRIPE_PRICE_ANNUAL"] = "price_annual_190"

import stripe                                       # noqa: E402
from fastapi.testclient import TestClient           # noqa: E402
from api.main import app                            # noqa: E402
import core.billing as billing                      # noqa: E402
from core.database import get_connection, init_db, purge_user_data   # noqa: E402
from core.plans import get_plan, set_plan           # noqa: E402

# The module read these at import time, before the suite set them.
billing.PRICE_FOUNDING = os.environ["STRIPE_PRICE_FOUNDING"]
billing.PRICE_MONTHLY = os.environ["STRIPE_PRICE_MONTHLY"]
billing.PRICE_ANNUAL = os.environ["STRIPE_PRICE_ANNUAL"]

SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
passed = failed = 0
failures = []


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")          # run_all.py counts these lines
    else:
        failed += 1
        failures.append(label)
        print(f"  FAIL  {label}   {detail}")


def signed(event: dict, secret: str = SECRET, ts: int | None = None):
    """Build the Stripe-Signature header the way Stripe does."""
    body = json.dumps(event)
    ts = ts or int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{body}", secret)
    return body, {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


def event(kind: str, obj: dict, eid: str) -> dict:
    return {"id": eid, "type": kind, "data": {"object": obj}}


def wipe(*accounts):
    conn = get_connection(); cur = conn.cursor()
    for a in accounts:
        for t in ("billing", "user_plans", "jobs", "profile"):
            cur.execute(f"DELETE FROM {t} WHERE tester_name = %s", (a,))
    cur.execute("DELETE FROM stripe_events")
    conn.commit(); cur.close(); conn.close()


init_db()
c = TestClient(app)
PAYER = "payer@example.com"
wipe(PAYER)

# ------------------------------------------------------------- 1. signatures
print("\n[1] an unsigned or forged webhook changes nothing")
ev = event("checkout.session.completed",
           {"client_reference_id": PAYER, "customer": "cus_1", "subscription": "sub_1"}, "evt_x1")

r = c.post("/api/stripe/webhook", content=json.dumps(ev),
           headers={"content-type": "application/json"})
check("a webhook with no signature is refused", r.status_code == 400, r.status_code)
check("and did not grant a plan", get_plan(PAYER) == "free", get_plan(PAYER))

body, hdr = signed(ev, secret="whsec_the_wrong_secret")
r = c.post("/api/stripe/webhook", content=body, headers=hdr)
check("a wrongly-signed webhook is refused", r.status_code == 400, r.status_code)
check("and still did not grant a plan", get_plan(PAYER) == "free", get_plan(PAYER))

body, hdr = signed(ev, ts=int(time.time()) - 3600)
r = c.post("/api/stripe/webhook", content=body, headers=hdr)
check("a replayed old signature is refused", r.status_code == 400, r.status_code)

check("the refusal explains nothing useful to a forger",
      "Invalid signature." == r.json().get("detail"), r.text[:120])

# ------------------------------------------------------------- 2. the happy path
print("\n[2] a completed checkout moves the account to pro")
body, hdr = signed(ev)
r = c.post("/api/stripe/webhook", content=body, headers=hdr)
check("a correctly signed webhook is accepted", r.status_code == 200, r.text[:120])
check("the account is now pro", get_plan(PAYER) == "pro", get_plan(PAYER))
row = billing.get_billing(PAYER) or {}
check("the customer id was stored", row.get("stripe_customer_id") == "cus_1", row)
check("the subscription id was stored", row.get("stripe_subscription_id") == "sub_1", row)

# ------------------------------------------------------------- 3. idempotency
print("\n[3] Stripe retrying the same event does not double-apply")
set_plan(PAYER, "free")
body, hdr = signed(ev)
r = c.post("/api/stripe/webhook", content=body, headers=hdr)
check("the retry is answered 200 so Stripe stops", r.status_code == 200, r.status_code)
check("it is reported as a duplicate", r.json().get("duplicate") is True, r.json())
check("and it changed nothing the second time", get_plan(PAYER) == "free", get_plan(PAYER))

# ------------------------------------------------------------- 4. downgrades
print("\n[4] losing a subscription shrinks the allowance, it does not delete data")
conn = get_connection(); cur = conn.cursor()
cur.execute("INSERT INTO jobs (tester_name, company, role, status) VALUES (%s,'Acme','PM','applied')",
            (PAYER,))
conn.commit(); cur.close(); conn.close()

body, hdr = signed(event("checkout.session.completed",
                         {"client_reference_id": PAYER, "customer": "cus_1",
                          "subscription": "sub_1"}, "evt_x2"))
c.post("/api/stripe/webhook", content=body, headers=hdr)
check("back on pro before the test", get_plan(PAYER) == "pro", get_plan(PAYER))

body, hdr = signed(event("customer.subscription.deleted",
                         {"customer": "cus_1", "id": "sub_1"}, "evt_x3"))
r = c.post("/api/stripe/webhook", content=body, headers=hdr)
check("a cancelled subscription returns the account to free",
      get_plan(PAYER) == "free", get_plan(PAYER))

conn = get_connection(); cur = conn.cursor()
cur.execute("SELECT count(*) FROM jobs WHERE tester_name = %s", (PAYER,))
kept = cur.fetchone()[0]; cur.close(); conn.close()
check("and their pipeline is untouched", kept == 1, kept)

print("\n[4b] a failed payment only downgrades on the final attempt")
body, hdr = signed(event("checkout.session.completed",
                         {"client_reference_id": PAYER, "customer": "cus_1",
                          "subscription": "sub_1"}, "evt_x4"))
c.post("/api/stripe/webhook", content=body, headers=hdr)

body, hdr = signed(event("invoice.payment_failed",
                         {"customer": "cus_1", "next_payment_attempt": int(time.time()) + 86400},
                         "evt_x5"))
c.post("/api/stripe/webhook", content=body, headers=hdr)
check("a retryable failure leaves them on pro", get_plan(PAYER) == "pro", get_plan(PAYER))

body, hdr = signed(event("invoice.payment_failed",
                         {"customer": "cus_1", "next_payment_attempt": None}, "evt_x6"))
c.post("/api/stripe/webhook", content=body, headers=hdr)
check("the final failure downgrades", get_plan(PAYER) == "free", get_plan(PAYER))

conn = get_connection(); cur = conn.cursor()
cur.execute("SELECT count(*) FROM jobs WHERE tester_name = %s", (PAYER,))
check("and still deleted nothing", cur.fetchone()[0] == 1)
cur.close(); conn.close()

# ------------------------------------------------------------- 5. the seat cap
print("\n[5] the founding-seat cap is counted in the database, not the UI")
conn = get_connection(); cur = conn.cursor()
cur.execute("DELETE FROM billing WHERE tester_name LIKE 'seat%%'")
conn.commit(); cur.close(); conn.close()

check("a founding price is offered while seats remain",
      billing.price_for_new_subscriber() == billing.PRICE_FOUNDING,
      billing.price_for_new_subscriber())

conn = get_connection(); cur = conn.cursor()
for i in range(billing.FOUNDING_SEATS):
    cur.execute("""INSERT INTO billing (tester_name, status, price_id)
                   VALUES (%s, 'active', %s)""", (f"seat{i}@example.com", billing.PRICE_FOUNDING))
conn.commit(); cur.close(); conn.close()

check(f"all {billing.FOUNDING_SEATS} seats read as taken",
      billing.founding_seats_taken() == billing.FOUNDING_SEATS, billing.founding_seats_taken())
check("the next subscriber is quoted the standard price",
      billing.price_for_new_subscriber() == billing.PRICE_MONTHLY,
      billing.price_for_new_subscriber())

# Ten simultaneous checkouts at the boundary must all be quoted standard, since
# the count is read at the moment of asking rather than cached.
quotes = [billing.price_for_new_subscriber() for _ in range(10)]
check("concurrent checkouts at the cap all get the standard price",
      all(q == billing.PRICE_MONTHLY for q in quotes), set(quotes))

# A cancelled founding seat frees up again; only active ones count.
conn = get_connection(); cur = conn.cursor()
cur.execute("UPDATE billing SET status='canceled' WHERE tester_name = 'seat0@example.com'")
conn.commit(); cur.close(); conn.close()
check("a cancelled seat is released",
      billing.founding_seats_taken() == billing.FOUNDING_SEATS - 1,
      billing.founding_seats_taken())
check("and the freed seat is offered again",
      billing.price_for_new_subscriber() == billing.PRICE_FOUNDING)

check("annual never consumes a founding seat",
      billing.price_for_new_subscriber(annual=True) == billing.PRICE_ANNUAL)

# ------------------------------------------------------------- 6. deletion
print("\n[6] deleting an account keeps the money and drops the person")
body, hdr = signed(event("checkout.session.completed",
                         {"client_reference_id": PAYER, "customer": "cus_del",
                          "subscription": "sub_del"}, "evt_x7"))
c.post("/api/stripe/webhook", content=body, headers=hdr)
check("payer has a billing row", (billing.get_billing(PAYER) or {}).get("stripe_customer_id") == "cus_del")

purge_user_data(PAYER)
check("the billing row no longer belongs to them", billing.get_billing(PAYER) is None)

conn = get_connection(); cur = conn.cursor()
cur.execute("SELECT count(*) FROM billing WHERE stripe_customer_id = 'cus_del'")
still_linked = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM billing WHERE tester_name LIKE 'deleted:%%'")
anonymised = cur.fetchone()[0]
cur.close(); conn.close()
check("the row survives for reconciliation", anonymised >= 1, anonymised)
check("but the pointer back to Stripe is gone", still_linked == 0, still_linked)

# ------------------------------------------------------------- 7. endpoints
print("\n[7] the billing endpoints refuse an unauthenticated caller")
for method, path in (("GET", "/api/billing"), ("POST", "/api/billing/checkout"),
                     ("POST", "/api/billing/portal")):
    r = c.request(method, path, json={})
    check(f"{method} {path} needs a session", r.status_code == 401, r.status_code)

conn = get_connection(); cur = conn.cursor()
cur.execute("DELETE FROM billing WHERE tester_name LIKE 'seat%%' OR tester_name LIKE 'deleted:%%'")
cur.execute("DELETE FROM stripe_events")
conn.commit(); cur.close(); conn.close()
wipe(PAYER)

print(f"\n  {passed} passed, {failed} failed")
if failures:
    print("  FAILURES: " + "; ".join(failures))
sys.exit(1 if failed else 0)
