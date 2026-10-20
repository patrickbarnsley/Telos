"""Request-scoped dependencies: identity, quota, and error translation.

The single most important rule in this package is here. The account is resolved
from the session cookie and from nowhere else. No handler accepts an account
identifier from a request body, path or query string. The cross-account defects
found before launch were all the same mistake in different shapes: trusting the
caller to say who they were.
"""
from fastapi import Cookie, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

SESSION_COOKIE = "telos_session"


def _resolve(token: str | None) -> str:
    from core.auth import resume_session

    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    email = resume_session(token)
    if not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "That session has expired. Sign in again.")
    return email


async def current_account(telos_session: str | None = Cookie(default=None)) -> str:
    """The signed-in account, or 401. The only source of identity in the API.

    Async on purpose. It also names the account for AI spend attribution, and a
    ContextVar set in a sync dependency never reaches the handler: FastAPI runs
    sync dependencies in a worker thread that gets a copy of the context, and
    the write dies with the copy. Every AI call made through this API was being
    recorded against an empty tester_name because _current_user reads Streamlit
    session state, which does not exist here.

    The session lookup is a blocking database call, so it stays on the
    threadpool rather than stalling the event loop.
    """
    from core.ai_engine import set_request_user

    email = await run_in_threadpool(_resolve, telos_session)
    set_request_user(email)
    return email


def optional_account(telos_session: str | None = Cookie(default=None)) -> str | None:
    from core.auth import resume_session
    return resume_session(telos_session) if telos_session else None


def require_quota(action: str):
    """Refuse before the work happens, with the numbers the caller needs.

    Deliberately not core.plans.quota_gate: that function renders Streamlit
    widgets. It calls the same check_quota underneath, so the counting is not
    reimplemented here, only the response is.
    """
    def dep(account: str = Depends(current_account)) -> str:
        from core.plans import DEMO_TESTER, check_quota, get_plan
        if account == DEMO_TESTER:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "The demo account is read only. Create a free account to run this.")
        allowed, used, limit = check_quota(account, action)
        if not allowed:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                f"Monthly limit reached: {used} of {limit} used on the "
                f"{get_plan(account)} plan. This resets on the 1st.")
        return account
    return dep


def fail(exc: Exception, doing: str) -> HTTPException:
    """Translate any exception into a safe, human message.

    core.errors.friendly never leaks a traceback or an API key, which is the
    property being preserved across the move off Streamlit.
    """
    from core.errors import friendly
    from core.spend import SpendCapReached

    code = status.HTTP_502_BAD_GATEWAY if isinstance(exc, SpendCapReached) \
        else status.HTTP_400_BAD_REQUEST
    return HTTPException(code, friendly(exc, doing))
