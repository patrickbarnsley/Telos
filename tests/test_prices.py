"""offered_prices: what the upgrade screen is allowed to quote.

Runs with no database and no Stripe account. Both are stubbed, because the
logic under test is about which prices are offerable, not about storage or the
network.
"""
import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["STRIPE_PRICE_FOUNDING"] = "price_f"
os.environ["STRIPE_PRICE_MONTHLY"]  = "price_m"
os.environ["STRIPE_PRICE_ANNUAL"]   = "price_a"
os.environ["STRIPE_SECRET_KEY"]     = "sk_test_suite"

import core.billing as b
b.PRICE_FOUNDING, b.PRICE_MONTHLY, b.PRICE_ANNUAL = "price_f", "price_m", "price_a"

CAT = {
    "price_f": {"unit_amount": 1200, "currency": "usd", "recurring": {"interval": "month", "interval_count": 1}},
    "price_m": {"unit_amount": 1900, "currency": "usd", "recurring": {"interval": "month", "interval_count": 1}},
    "price_a": {"unit_amount": 19000, "currency": "usd", "recurring": {"interval": "year", "interval_count": 1}},
}
BROKEN = set()
def fake_retrieve(pid, **kw):
    if pid in BROKEN: raise RuntimeError("stripe is having a day")
    return CAT[pid]
stripe = types.ModuleType("stripe")
stripe.Price = types.SimpleNamespace(retrieve=fake_retrieve)
stripe.api_key = None
sys.modules["stripe"] = stripe

passed = failed = 0; failures = []
def check(label, ok, detail=""):
    global passed, failed
    if ok: passed += 1; print(f"  PASS  {label}")
    else:
        failed += 1; failures.append(label); print(f"  FAIL  {label}   {detail}")

def kinds(seats_taken=0):
    b.founding_seats_taken = lambda: seats_taken
    return [p["kind"] for p in b.offered_prices()]

# 1. the screen must never quote a price the checkout would refuse to use
k = kinds(seats_taken=0)
check("founding seats left: founding and annual offered, monthly hidden",
      k == ["founding", "annual"], k)
check("the hidden monthly is the one price_for_new_subscriber would not return",
      b.price_for_new_subscriber(False) == "price_f", b.price_for_new_subscriber(False))

# 2. seats gone: founding disappears and monthly takes over, together
k = kinds(seats_taken=b.FOUNDING_SEATS)
check("seats exhausted: monthly and annual offered, founding gone",
      k == ["monthly", "annual"], k)
check("and the checkout agrees", b.price_for_new_subscriber(False) == "price_m")

# 3. amounts are Stripe's, not ours
b.founding_seats_taken = lambda: 0
p = b.offered_prices()[0]
check("amount comes from the Price object", p["amount_cents"] == 1200, p)
check("currency is normalised for Intl", p["currency"] == "USD", p)
check("cadence is carried through", (p["interval"], p["interval_count"]) == ("month", 1), p)

# 4. one unreachable price must not blank the screen
BROKEN.add("price_f")
k = kinds(seats_taken=0)
check("a failing price drops only itself", k == ["annual"], k)
BROKEN.clear()

# 5. no Stripe key means no paywall, which is how "free" is expressed
os.environ["STRIPE_SECRET_KEY"] = ""
check("no key: empty list, so the client renders no paywall", b.offered_prices() == [])
os.environ["STRIPE_SECRET_KEY"] = "sk_test_suite"

# 6. no configured price ids: same
b.PRICE_FOUNDING = b.PRICE_MONTHLY = b.PRICE_ANNUAL = ""
check("no price ids: empty list", b.offered_prices() == [])

print(f"\n  {passed} passed, {failed} failed")
if failures: print("  FAILURES: " + "; ".join(failures))
sys.exit(1 if failed else 0)
