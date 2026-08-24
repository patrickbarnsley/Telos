"""Plan tiers, usage metering, and quota enforcement.

Every AI call in Telos costs real money against the app's Anthropic key.
This module is the single place that decides whether a given user is allowed
to make one, and the single place that records that they did.

Design notes:
  - Quotas reset on the first of each calendar month (UTC).
  - Tracking (jobs, notes, pipeline metrics) is deliberately never metered.
    Only AI actions are, because only AI actions have a marginal cost.
  - The demo account has a zero quota on everything, so demo traffic is
    free by construction rather than by trust.
"""
import os
from typing import Tuple

# Metered actions
MATCH = "match"
ROADMAP = "roadmap"
ADVISOR = "advisor"
SCAM_CHECK = "scam_check"
JD_EXTRACT = "jd_extract"

ACTION_LABELS = {
    MATCH: "match score",
    ROADMAP: "career roadmap",
    ADVISOR: "advisor message",
    SCAM_CHECK: "employer check",
    JD_EXTRACT: "screenshot extraction",
}

UNLIMITED = -1

PLANS = {
    "free": {
        "label": "Free",
        "limits": {MATCH: 10, ROADMAP: 1, ADVISOR: 0, SCAM_CHECK: 10, JD_EXTRACT: 10},
    },
    "pro": {
        "label": "Pro",
        "limits": {MATCH: 200, ROADMAP: 10, ADVISOR: 500, SCAM_CHECK: 200, JD_EXTRACT: 200},
    },
    "owner": {
        "label": "Owner",
        "limits": {MATCH: UNLIMITED, ROADMAP: UNLIMITED, ADVISOR: UNLIMITED,
                   SCAM_CHECK: UNLIMITED, JD_EXTRACT: UNLIMITED},
    },
    "demo": {
        "label": "Demo",
        "limits": {MATCH: 0, ROADMAP: 0, ADVISOR: 0, SCAM_CHECK: 0, JD_EXTRACT: 0},
    },
}

DEMO_TESTER = "__demo__"


def _owner_emails() -> set:
    """Emails that get an unmetered plan. Set OWNER_EMAILS as a comma-separated list."""
    raw = ""
    try:
        import streamlit as st
        raw = st.secrets["OWNER_EMAILS"]
    except Exception:
        raw = os.getenv("OWNER_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def get_plan(tester_name: str) -> str:
    """Resolve a user's plan key. Demo and owner are implicit; everyone else is
    whatever user_plans says, defaulting to free."""
    if tester_name == DEMO_TESTER:
        return "demo"
    if tester_name and tester_name.lower() in _owner_emails():
        return "owner"

    from core.database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT plan FROM user_plans WHERE tester_name = %s", (tester_name,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    plan = row[0] if row else "free"
    return plan if plan in PLANS else "free"


def is_owner(tester_name: str) -> bool:
    """True only for accounts listed in OWNER_EMAILS. The demo account never
    qualifies, whatever it is called."""
    if not tester_name or tester_name == DEMO_TESTER:
        return False
    return tester_name.lower() in _owner_emails()


def plan_label(tester_name: str) -> str:
    return PLANS[get_plan(tester_name)]["label"]


def limit_for(tester_name: str, action: str) -> int:
    return PLANS[get_plan(tester_name)]["limits"].get(action, 0)


def used_this_month(tester_name: str, action: str) -> int:
    from core.database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT COUNT(*) FROM usage_events
           WHERE tester_name = %s AND action = %s
             AND created_at >= date_trunc('month', NOW())""",
        (tester_name, action),
    )
    n = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return int(n or 0)


def check_quota(tester_name: str, action: str) -> Tuple[bool, int, int]:
    """Return (allowed, used, limit). limit == UNLIMITED means no cap."""
    limit = limit_for(tester_name, action)
    if limit == UNLIMITED:
        return True, 0, UNLIMITED
    used = used_this_month(tester_name, action)
    return used < limit, used, limit


def record_usage(tester_name: str, action: str):
    """Log one metered AI call. Call this only after the call succeeds."""
    from core.database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO usage_events (tester_name, action, created_at) VALUES (%s, %s, NOW())",
        (tester_name, action),
    )
    conn.commit()
    cursor.close()
    conn.close()


def set_plan(tester_name: str, plan: str):
    if plan not in PLANS:
        raise ValueError(f"Unknown plan: {plan}")
    from core.database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO user_plans (tester_name, plan, updated_at)
           VALUES (%s, %s, NOW())
           ON CONFLICT (tester_name) DO UPDATE SET plan = EXCLUDED.plan, updated_at = NOW()""",
        (tester_name, plan),
    )
    conn.commit()
    cursor.close()
    conn.close()


def join_waitlist(email: str, note: str = "") -> bool:
    from core.database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO waitlist (email, note, created_at) VALUES (%s, %s, NOW()) ON CONFLICT DO NOTHING",
        (email.strip().lower(), note),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True


def quota_gate(tester_name: str, action: str) -> bool:
    """Streamlit-aware guard. Returns True if the caller may proceed.
    Renders the appropriate blocking message if not."""
    import streamlit as st

    if tester_name == DEMO_TESTER:
        st.info(
            "**This is the demo account.** Everything you see is real product output, "
            "pre-generated so the demo stays free to run. "
            "Create a free account to run this on your own resume."
        )
        return False

    allowed, used, limit = check_quota(tester_name, action)
    if allowed:
        return True

    label = ACTION_LABELS.get(action, action)
    plan = get_plan(tester_name)
    if plan == "free":
        st.warning(
            f"**You've used all {limit} {label}s on the Free plan this month.** "
            f"Your quota resets on the 1st. Pro raises this limit substantially. "
            f"it isn't taking payments yet, but you can join the waitlist on the home page."
        )
    else:
        st.warning(
            f"**Monthly limit reached**: {used}/{limit} {label}s used on the "
            f"{PLANS[plan]['label']} plan. This resets on the 1st."
        )
    return False


def quota_caption(tester_name: str, action: str) -> str:
    """Small 'x of y used this month' string for under a button."""
    limit = limit_for(tester_name, action)
    if limit == UNLIMITED:
        return ""
    if tester_name == DEMO_TESTER:
        return "Demo account: AI actions are pre-generated"
    used = used_this_month(tester_name, action)
    label = ACTION_LABELS.get(action, action)
    return f"{used} of {limit} {label}s used this month · {PLANS[get_plan(tester_name)]['label']} plan"
