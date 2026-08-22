import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def _get_credentials():
    """Read Supabase URL + publishable key from Streamlit secrets first, then .env."""
    url = None
    key = None
    try:
        import streamlit as st
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
    except Exception:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
    return url, key


def get_client() -> Client:
    """Create a Supabase client using the publishable (anon) key."""
    url, key = _get_credentials()
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials are missing. Check SUPABASE_URL and "
            "SUPABASE_ANON_KEY in your secrets / .env."
        )
    return create_client(url, key)


def sign_up(email: str, password: str) -> dict:
    """Register a new user. Returns {'ok': bool, 'error': str|None, 'user': obj|None}."""
    client = get_client()
    try:
        res = client.auth.sign_up({"email": email, "password": password})
        if res.user is None:
            return {"ok": False, "error": "Sign-up did not return a user. Try logging in.", "user": None}
        return {"ok": True, "error": None, "user": res.user}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(str(e)), "user": None}


def sign_in(email: str, password: str) -> dict:
    """Log a user in. Returns {'ok': bool, 'error': str|None, 'user': obj|None}."""
    client = get_client()
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.user is None:
            return {"ok": False, "error": "Invalid email or password.", "user": None}
        return {"ok": True, "error": None, "user": res.user}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(str(e)), "user": None}


def _friendly_error(raw: str) -> str:
    """Turn raw Supabase error text into something readable for the user."""
    low = raw.lower()
    if "invalid login" in low or "invalid credentials" in low:
        return "Invalid email or password."
    if "already registered" in low or "already been registered" in low:
        return "That email is already registered. Try logging in instead."
    if "password should be" in low or "password" in low and "least" in low:
        return "Password is too short. Use at least 6 characters."
    if "unable to validate email" in low or "invalid email" in low:
        return "That doesn't look like a valid email address."
    return raw


def require_login():
    """Guard a page: stop and show a sign-in prompt unless the user is logged in.
    Call this near the top of every protected page."""
    import streamlit as st
    from core.plans import DEMO_TESTER

    if not st.session_state.get("user_email"):
        st.warning("Please log in to use Telos.")
        st.page_link("app.py", label="→ Go to the login page")
        st.stop()

    # Keep the identity key in sync for the rest of the page — but never clobber
    # the demo identity. The demo account is keyed on DEMO_TESTER, not on an
    # email, and overwriting it here would drop demo visitors into an empty
    # account with the demo write-guard disarmed.
    if st.session_state.get("tester_name") != DEMO_TESTER:
        st.session_state.tester_name = st.session_state.user_email