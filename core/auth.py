"""Authentication, session persistence and account deletion.

Three things live here that a job-search product cannot ship without: a way
back in when someone forgets their password, a session that survives a browser
refresh, and a route for a person to remove everything Telos holds about them.
"""
import os
import secrets
import hashlib
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Minimum password length. Six was the old floor, which is thin for a document
# holding somebody's full employment history, address and salary expectations.
MIN_PASSWORD = 10

# How long a remembered session stays valid before requiring a fresh sign-in.
SESSION_DAYS = 30


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


def _site_url() -> str:
    """Where Supabase should send a user after they click an emailed link."""
    try:
        import streamlit as st
        return st.secrets["SITE_URL"]
    except Exception:
        return os.getenv("SITE_URL", "https://app.usetelosapp.com")


# ---------------------------------------------------------------- validation

def password_problem(password: str) -> str:
    """Return a human explanation of why a password is unacceptable, or ''.

    Length does most of the work. A long passphrase beats a short password with
    a symbol bolted on, so the rules stay simple enough that people follow them.
    """
    if len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters. Longer beats complicated."
    if password.lower() in {
        "password12", "password123", "1234567890", "qwertyuiop",
        "letmein123", "welcome123", "iloveyou12", "administrator",
    }:
        return "That is one of the most guessed passwords in use. Pick another."
    if len(set(password)) < 5:
        return "Too few distinct characters. Try a short phrase instead."
    return ""


# ------------------------------------------------------------------ accounts

def sign_up(email: str, password: str) -> dict:
    """Register a new user. Returns {'ok', 'error', 'user', 'needs_confirmation'}."""
    problem = password_problem(password)
    if problem:
        return {"ok": False, "error": problem, "user": None, "needs_confirmation": False}

    client = get_client()
    try:
        res = client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"email_redirect_to": _site_url()},
        })
        if res.user is None:
            return {"ok": False, "error": "Sign-up did not return a user. Try logging in.",
                    "user": None, "needs_confirmation": False}

        # When email confirmation is switched on in Supabase, the new user comes
        # back without a confirmation timestamp and no session. Telling the user
        # to check their inbox is the difference between a working signup and a
        # silent dead end.
        confirmed = getattr(res.user, "email_confirmed_at", None) or getattr(res.user, "confirmed_at", None)
        needs_confirmation = confirmed is None and getattr(res, "session", None) is None

        return {"ok": True, "error": None, "user": res.user,
                "needs_confirmation": needs_confirmation, "session": getattr(res, "session", None)}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(str(e)), "user": None, "needs_confirmation": False}


def sign_in(email: str, password: str) -> dict:
    """Log a user in. Returns {'ok', 'error', 'user', 'session'}."""
    client = get_client()
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.user is None:
            return {"ok": False, "error": "Invalid email or password.", "user": None, "session": None}
        return {"ok": True, "error": None, "user": res.user, "session": getattr(res, "session", None)}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(str(e)), "user": None, "session": None}


def send_password_reset(email: str) -> dict:
    """Email a password reset link.

    Always reports success to the caller. Confirming whether an address is
    registered lets anyone test whether a given person uses Telos, which for a
    job-search tool is genuinely sensitive - it reveals that someone is looking.
    """
    try:
        client = get_client()
        client.auth.reset_password_for_email(
            email.strip().lower(),
            {"redirect_to": _site_url()},
        )
    except Exception:
        pass
    return {"ok": True, "error": None}


def verify_recovery(token_hash: str) -> dict:
    """Exchange a recovery token from a reset email for a usable session.

    Supabase can deliver the token either in the URL fragment or the query
    string. A fragment never reaches the server, and Streamlit renders entirely
    server-side, so this app depends on the query-string form. That requires the
    recovery email template to use {{ .TokenHash }} - see DEPLOY-AWS.md.
    """
    try:
        client = get_client()
        res = client.auth.verify_otp({"token_hash": token_hash, "type": "recovery"})
        email = getattr(getattr(res, "user", None), "email", None)
        if not email:
            return {"ok": False, "error": "That reset link is no longer valid. Request a new one.", "client": None, "email": None}
        return {"ok": True, "error": None, "client": client, "email": email}
    except Exception as e:
        low = str(e).lower()
        if "expired" in low or "invalid" in low:
            return {"ok": False, "error": "That reset link has expired. Request a new one.", "client": None, "email": None}
        return {"ok": False, "error": _friendly_error(str(e)), "client": None, "email": None}


def set_password_with_client(client, new_password: str) -> dict:
    """Set a new password on an already-verified recovery session."""
    problem = password_problem(new_password)
    if problem:
        return {"ok": False, "error": problem}
    try:
        client.auth.update_user({"password": new_password})
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(str(e))}


def update_password(new_password: str, access_token: str) -> dict:
    """Set a new password using the token from a reset email link."""
    problem = password_problem(new_password)
    if problem:
        return {"ok": False, "error": problem}
    try:
        client = get_client()
        client.auth.set_session(access_token, access_token)
        client.auth.update_user({"password": new_password})
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(str(e))}


def _friendly_error(raw: str) -> str:
    """Turn raw Supabase error text into something readable for the user."""
    low = raw.lower()
    if "invalid login" in low or "invalid credentials" in low:
        return "Invalid email or password."
    if "already registered" in low or "already been registered" in low:
        return "That email is already registered. Try logging in instead."
    if "email not confirmed" in low or "not confirmed" in low:
        return "Confirm your email address first. Check your inbox for the link we sent."
    if "password should be" in low or ("password" in low and "least" in low):
        return f"Password is too short. Use at least {MIN_PASSWORD} characters."
    if "unable to validate email" in low or "invalid email" in low:
        return "That doesn't look like a valid email address."
    if "rate limit" in low or "too many" in low:
        return "Too many attempts. Wait a minute and try again."
    return "Something went wrong signing you in. Try again in a moment."


# --------------------------------------------------------- session behaviour

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def remember_session(email: str) -> str:
    """Issue a durable token for this account and return it.

    Streamlit's session_state is discarded on browser refresh, so it cannot be
    the only place a login lives. The token goes in the URL query string, which
    survives reloads and bookmarks; only its hash is stored, so the database
    never holds anything that grants access on its own.
    """
    from core.database import store_session_token
    token = secrets.token_urlsafe(32)
    store_session_token(email, _token_hash(token), SESSION_DAYS)
    return token


def resume_session(token: str):
    """Return the email a remembered token belongs to, or None."""
    from core.database import lookup_session_token
    if not token:
        return None
    return lookup_session_token(_token_hash(token))


def forget_session(token: str):
    from core.database import revoke_session_token
    if token:
        revoke_session_token(_token_hash(token))


def require_login():
    """Guard a page: stop unless the user is signed in.

    Restores a remembered session from the URL when session_state is empty,
    which is what makes a refresh survivable.
    """
    import streamlit as st
    from core.plans import DEMO_TESTER

    if not st.session_state.get("user_email"):
        token = st.query_params.get("s")
        email = resume_session(token) if token else None
        if email:
            st.session_state.user_email = email
            st.session_state.tester_name = email
            st.session_state.session_token = token

    if not st.session_state.get("user_email"):
        st.warning("Please sign in to use Telos.")
        st.page_link("app.py", label="Go to the sign-in page")
        st.stop()

    # Keep the identity key in sync for the rest of the page, but never clobber
    # the demo identity. The demo account is keyed on DEMO_TESTER, not on an
    # email, and overwriting it here would drop demo visitors into an empty
    # account with the demo write-guard disarmed.
    if st.session_state.get("tester_name") != DEMO_TESTER:
        st.session_state.tester_name = st.session_state.user_email


# ------------------------------------------------------------------ deletion

def delete_account(email: str) -> dict:
    """Erase everything Telos holds for this account.

    Removes the application's own rows. The Supabase auth record needs a service
    key to delete and this app deliberately only holds the anon key, so the
    login itself is disabled rather than removed, and the address is reported
    for manual removal.
    """
    from core.database import purge_user_data
    from core.plans import DEMO_TESTER

    if not email or email == DEMO_TESTER:
        return {"ok": False, "error": "That account cannot be deleted.", "removed": {}}

    try:
        removed = purge_user_data(email)
        return {"ok": True, "error": None, "removed": removed}
    except Exception as e:
        return {"ok": False, "error": str(e), "removed": {}}
