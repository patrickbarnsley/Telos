"""Attempt throttling for the endpoints an attacker gets to call for free.

Database-backed on purpose. An in-process counter dies with the container, does
not hold across more than one worker, and resets every deploy, which makes it a
comfort rather than a control. The table is cheap: one narrow row per attempt,
pruned on write.

Keyed twice for every sign-in. Limiting only by email lets one host spray a
thousand different accounts; limiting only by address lets a distributed attempt
walk straight through. Either key tripping is enough to refuse.
"""
import os
from datetime import datetime, timedelta, timezone

# Deliberately generous. This exists to make automated guessing expensive, not
# to punish someone who mistypes a password twice on a phone.
LOGIN_LIMIT = int(os.getenv("TELOS_LOGIN_LIMIT", "10"))
LOGIN_WINDOW_SECONDS = int(os.getenv("TELOS_LOGIN_WINDOW", "900"))   # 15 minutes
SIGNUP_LIMIT = int(os.getenv("TELOS_SIGNUP_LIMIT", "5"))
SIGNUP_WINDOW_SECONDS = int(os.getenv("TELOS_SIGNUP_WINDOW", "3600"))

RETENTION_HOURS = 24


def _table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_attempts (
            id SERIAL PRIMARY KEY,
            bucket TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_attempts ON auth_attempts (bucket, created_at)")
    # This table is created on the first sign-in attempt, which may be long
    # after init_db last ran, so it hardens itself rather than waiting.
    from core.database import protect_public_schema
    protect_public_schema(cursor)


def record_attempt(bucket: str) -> None:
    """Note one attempt. Never raises: throttling must not break signing in."""
    if not bucket:
        return
    from core.database import get_connection
    try:
        conn = get_connection(); cur = conn.cursor()
        _table(cur)
        cur.execute("INSERT INTO auth_attempts (bucket) VALUES (%s)", (bucket,))
        cur.execute("DELETE FROM auth_attempts WHERE created_at < %s",
                    (datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS),))
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass


def attempts_since(bucket: str, window_seconds: int) -> int:
    if not bucket:
        return 0
    from core.database import get_connection
    try:
        conn = get_connection(); cur = conn.cursor()
        _table(cur)
        cur.execute(
            "SELECT count(*) FROM auth_attempts WHERE bucket = %s AND created_at > %s",
            (bucket, datetime.now(timezone.utc) - timedelta(seconds=window_seconds)))
        n = cur.fetchone()[0]
        cur.close(); conn.close()
        return int(n or 0)
    except Exception:
        # Fail open. A database wobble must not lock every user out of the product.
        return 0


def check(buckets: list[str], limit: int, window_seconds: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds). Any bucket over the limit refuses."""
    for b in buckets:
        if attempts_since(b, window_seconds) >= limit:
            return False, window_seconds
    return True, 0


def clear(bucket: str) -> None:
    """Forget a bucket's attempts. Called on a successful sign-in, so a person
    who eventually remembers their password is not still throttled."""
    if not bucket:
        return
    from core.database import get_connection
    try:
        conn = get_connection(); cur = conn.cursor()
        _table(cur)
        cur.execute("DELETE FROM auth_attempts WHERE bucket = %s", (bucket,))
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass
