import os, sys, json, pathlib
os.environ.setdefault("DATABASE_URL","postgresql://postgres:postgres@localhost:5432/telos_test")
os.environ["ANTHROPIC_API_KEY"]="sk-test"
os.environ["TELOS_AI_MONTHLY_CAP"]="1.00"
# Locate the repo from this file rather than a fixed absolute path. The suites
# were written against /home/claude/Telos and could only ever run there; a
# checkout on any other machine failed at the first open().
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.database import init_db, get_connection
init_db()
conn=get_connection(); cur=conn.cursor(); cur.execute("DELETE FROM ai_spend"); conn.commit(); cur.close(); conn.close()

import importlib
from core import spend, errors
importlib.reload(spend)

passed=failed=0
def check(n,c,e=""):
    global passed,failed
    if c: passed+=1; print(f"  PASS  {n}")
    else: failed+=1; print(f"  FAIL  {n} -> {e}")

print("\n[1] pricing is right for the model actually in use")
check("opus 4.5 output priced at $25/MTok", abs(spend.cost_of("claude-opus-4-5", 0, 1_000_000) - 25.0) < 1e-9,
      spend.cost_of("claude-opus-4-5",0,1_000_000))
check("opus 4.5 input priced at $5/MTok", abs(spend.cost_of("claude-opus-4-5", 1_000_000, 0) - 5.0) < 1e-9)
check("unknown model priced at the top tier, not the cheap one",
      spend.cost_of("some-future-model", 1_000_000, 0) == 15.0, spend.cost_of("some-future-model",1_000_000,0))
check("cache reads billed at 10 percent",
      abs(spend.cost_of("claude-opus-4-5", cache_read_tokens=1_000_000) - 0.50) < 1e-9)
check("web search billed at $10 per 1000",
      abs(spend.cost_of("claude-opus-4-5", web_searches=100) - 1.00) < 1e-9)

print("\n[2] the ledger accumulates and the cap binds")
class Usage:
    input_tokens=20_000; output_tokens=5_000
    cache_creation_input_tokens=0; cache_read_input_tokens=0; server_tool_use=None
check("starts under cap", not spend.cap_reached(), spend.spend_this_month())
c = spend.record_usage_cost("claude-opus-4-5", Usage(), action="match", tester_name="u1")
check("one call priced correctly", abs(c - (20_000*5/1e6 + 5_000*25/1e6)) < 1e-9, c)
for _ in range(5):
    spend.record_usage_cost("claude-opus-4-5", Usage(), action="match", tester_name="u1")
check("cap reached after enough calls", spend.cap_reached(), spend.spend_summary())
try:
    spend.guard(); check("guard refuses past the cap", False, "no exception")
except spend.SpendCapReached as e:
    check("guard refuses past the cap", True)
    check("message is written for a person, not a log",
          "budget" in str(e).lower() and "Traceback" not in str(e), str(e))

print("\n[3] _invoke cannot be bypassed and never bills a failed call")
src=(ROOT / "core" / "ai_engine.py").read_text(encoding="utf-8")
import re
direct=[l for l in src.split("\n") if "client.messages.create" in l and "_invoke" not in l]
check("only one direct SDK call, inside _invoke", len(direct)==1, direct)
check("all six features route through _invoke", src.count("= _invoke(") == 6, src.count("= _invoke("))
check("spend.guard runs before the request",
      src.index("spend.guard()") < src.index("message = client.messages.create(**kwargs)"))

print("\n[4] failures read like sentences")
class RateLimitError(Exception): pass
class APIConnectionError(Exception): pass
class AuthenticationError(Exception): pass
cases = [
    (RateLimitError("429 too many requests"), "busy"),
    (APIConnectionError("connection reset"), "network blip"),
    (AuthenticationError("invalid x-api-key"), "temporarily unavailable"),
    (json.JSONDecodeError("Expecting value","",0), "could not read"),
    (KeyError("overall_score"), "incomplete result"),
    (spend.SpendCapReached(), "budget"),
]
for exc, expect in cases:
    msg = errors.friendly(exc, "scoring your match")
    check(f"{type(exc).__name__} -> readable", expect in msg.lower(), msg)
    check(f"{type(exc).__name__} leaks no internals",
          not any(t in msg for t in ("Traceback","x-api-key","psycopg2","supabase","sk-")), msg)

print("\n[5] the API key never reaches the user")
check("auth error does not echo the key", "invalid x-api-key" not in errors.friendly(AuthenticationError("invalid x-api-key"), "x"))

print("\n[6] per-action model routing keeps the margin real")
from core import ai_engine
importlib.reload(ai_engine)

check("match runs on haiku", ai_engine.model_for("match") == "claude-haiku-4-5", ai_engine.model_for("match"))
check("scam_check runs on haiku", ai_engine.model_for("scam_check") == "claude-haiku-4-5")
check("jd_extract runs on haiku", ai_engine.model_for("jd_extract") == "claude-haiku-4-5")
check("roadmap runs on sonnet", ai_engine.model_for("roadmap") == "claude-sonnet-4-5", ai_engine.model_for("roadmap"))
check("advisor runs on sonnet", ai_engine.model_for("advisor") == "claude-sonnet-4-5")
check("an unknown action falls back to MODEL",
      ai_engine.model_for("something_new") == ai_engine.MODEL, ai_engine.model_for("something_new"))
check("an empty action falls back to MODEL", ai_engine.model_for("") == ai_engine.MODEL)

# Cost tuning has to be possible without a deploy, so every entry takes an
# environment override on its own.
os.environ["TELOS_AI_MODEL_MATCH"] = "claude-opus-4-5"
check("TELOS_AI_MODEL_MATCH overrides one action",
      ai_engine.model_for("match") == "claude-opus-4-5", ai_engine.model_for("match"))
check("the override does not leak into other actions",
      ai_engine.model_for("roadmap") == "claude-sonnet-4-5")
del os.environ["TELOS_AI_MODEL_MATCH"]
check("removing the override restores the default", ai_engine.model_for("match") == "claude-haiku-4-5")

# An action routed to a model the ledger cannot price silently bills at the
# DEFAULT_PRICE top tier, which makes the spend cap and the margin maths lie.
unpriced = [m for m in ai_engine.ACTION_MODELS.values() if spend._price_for(m) is spend.DEFAULT_PRICE]
check("every routed model is priced in the ledger", not unpriced, unpriced)

# The whole point of the routing change: cheap actions must actually be cheap.
check("routing match to haiku costs a fifth of opus on output",
      spend.cost_of(ai_engine.model_for("match"), 0, 1_000_000) == 5.0,
      spend.cost_of(ai_engine.model_for("match"), 0, 1_000_000))
check("sonnet output is cheaper than opus output",
      spend.cost_of(ai_engine.model_for("roadmap"), 0, 1_000_000)
      < spend.cost_of("claude-opus-4-5", 0, 1_000_000))

print("\n[7] the spend ceiling is a runaway guard, not a growth cap")
saved_cap = os.environ.pop("TELOS_AI_MONTHLY_CAP", None)
importlib.reload(spend)
check("default monthly cap is $150", spend.monthly_cap() == 150.0, spend.monthly_cap())
os.environ["TELOS_AI_MONTHLY_CAP"] = "not-a-number"
check("an unreadable cap falls back to $150, not to zero", spend.monthly_cap() == 150.0, spend.monthly_cap())
if saved_cap is not None:
    os.environ["TELOS_AI_MONTHLY_CAP"] = saved_cap
importlib.reload(spend)

print("\n[8] Pro allowances are numbers Telos can actually serve")
from core import plans
check("pro match scores capped at 100", plans.PLANS["pro"]["limits"][plans.MATCH] == 100,
      plans.PLANS["pro"]["limits"][plans.MATCH])
check("pro advisor messages capped at 200", plans.PLANS["pro"]["limits"][plans.ADVISOR] == 200,
      plans.PLANS["pro"]["limits"][plans.ADVISOR])
check("pro roadmaps unchanged at 10", plans.PLANS["pro"]["limits"][plans.ROADMAP] == 10)
check("no Pro allowance is unlimited",
      plans.UNLIMITED not in plans.PLANS["pro"]["limits"].values(),
      plans.PLANS["pro"]["limits"])
check("the free tier is untouched",
      plans.PLANS["free"]["limits"][plans.MATCH] == 10
      and plans.PLANS["free"]["limits"][plans.ROADMAP] == 1,
      plans.PLANS["free"]["limits"])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
