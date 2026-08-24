"""Global spend ceiling for the Claude API.

Per-user quotas in core.plans stop one person burning the budget. They do not
stop a thousand people each staying inside their quota on the same day, and
they do not stop a bug that retries a call in a loop. This module is the
backstop: one hard monthly ceiling across every user, enforced at the moment
of the API call, with the running total kept in the database so it survives
restarts and holds across more than one app server.

The cap is a refusal, not a warning. A product that quietly keeps spending is
a product that can generate a bill nobody approved.

Prices are per million tokens, from the published Claude API price list
(checked 2026-08-24). Cache writes bill at 1.25x input, cache reads at 0.1x
input, and each server-side web search is $10 per 1,000 searches.
"""

import os
from datetime import datetime

PRICES = {
    "claude-opus-4-5":   {"in": 5.00,  "out": 25.00},
    "claude-opus-4-6":   {"in": 5.00,  "out": 25.00},
    "claude-opus-4-1":   {"in": 15.00, "out": 75.00},
    "claude-sonnet-4-5": {"in": 3.00,  "out": 15.00},
    "claude-sonnet-4-6": {"in": 3.00,  "out": 15.00},
    "claude-haiku-4-5":  {"in": 1.00,  "out": 5.00},
}

# An unrecognised model is priced at the most expensive tier we know about.
# Guessing low would let the cap fail open, which is the wrong direction when
# the thing being capped is money.
DEFAULT_PRICE = {"in": 15.00, "out": 75.00}

CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10
WEB_SEARCH_COST = 10.00 / 1000  # USD per search


def monthly_cap() -> float:
    """Hard ceiling in USD for a calendar month. Set TELOS_AI_MONTHLY_CAP to change."""
    try:
        return float(os.getenv("TELOS_AI_MONTHLY_CAP", "40"))
    except ValueError:
        return 40.0


def _price_for(model: str) -> dict:
    for key, price in PRICES.items():
        if model and model.startswith(key):
            return price
    return DEFAULT_PRICE


def cost_of(model: str, input_tokens: int = 0, output_tokens: int = 0,
            cache_write_tokens: int = 0, cache_read_tokens: int = 0,
            web_searches: int = 0) -> float:
    p = _price_for(model)
    per_in = p["in"] / 1_000_000
    return (
        input_tokens * per_in
        + output_tokens * (p["out"] / 1_000_000)
        + cache_write_tokens * per_in * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * per_in * CACHE_READ_MULTIPLIER
        + web_searches * WEB_SEARCH_COST
    )


def cost_of_usage(model: str, usage) -> float:
    """Price an anthropic SDK usage object, including cache and server tools."""
    def field(name, default=0):
        try:
            value = getattr(usage, name, None)
            if value is None and isinstance(usage, dict):
                value = usage.get(name)
            return int(value) if value is not None else default
        except Exception:
            return default

    searches = 0
    try:
        server = getattr(usage, "server_tool_use", None) or {}
        searches = int(getattr(server, "web_search_requests", None)
                       or (server.get("web_search_requests") if isinstance(server, dict) else 0)
                       or 0)
    except Exception:
        searches = 0

    return cost_of(
        model,
        input_tokens=field("input_tokens"),
        output_tokens=field("output_tokens"),
        cache_write_tokens=field("cache_creation_input_tokens"),
        cache_read_tokens=field("cache_read_input_tokens"),
        web_searches=searches,
    )


def spend_this_month() -> float:
    from core.database import get_connection
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT COALESCE(SUM(cost_usd), 0) FROM ai_spend
               WHERE created_at >= date_trunc('month', NOW())"""
        )
        total = float(cursor.fetchone()[0] or 0)
        cursor.close()
        conn.close()
        return total
    except Exception:
        # If we cannot read the ledger we cannot prove we are under the cap.
        # Returning the cap fails closed, which is the safe direction for money.
        return monthly_cap()


def headroom() -> float:
    return max(0.0, monthly_cap() - spend_this_month())


def cap_reached() -> bool:
    return spend_this_month() >= monthly_cap()


def record_usage_cost(model: str, usage, action: str = "", tester_name: str = "") -> float:
    """Write one call to the ledger and return its cost. Never raises: a failed
    ledger write must not break a call the user already waited for."""
    cost = cost_of_usage(model, usage)
    def field(name):
        try:
            v = getattr(usage, name, None)
            if v is None and isinstance(usage, dict):
                v = usage.get(name)
            return int(v or 0)
        except Exception:
            return 0

    from core.database import get_connection
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO ai_spend
               (model, action, tester_name, input_tokens, output_tokens, cost_usd, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
            (model, action, tester_name,
             field("input_tokens") + field("cache_creation_input_tokens") + field("cache_read_input_tokens"),
             field("output_tokens"), cost),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass
    return cost


class SpendCapReached(RuntimeError):
    """Raised instead of calling the API once the monthly ceiling is hit."""

    def __init__(self):
        super().__init__(
            "Telos has reached its AI budget for this month. Everything that does not "
            "need AI still works, and AI features return at the start of next month."
        )


def guard():
    """Call immediately before any billable API request."""
    if cap_reached():
        raise SpendCapReached()


def spend_summary() -> dict:
    used = spend_this_month()
    cap = monthly_cap()
    return {
        "used": round(used, 2),
        "cap": round(cap, 2),
        "remaining": round(max(0.0, cap - used), 2),
        "percent": round(100 * used / cap, 1) if cap else 0.0,
        "month": datetime.now().strftime("%B %Y"),
    }
