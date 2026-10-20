"""Sign up, sign in, sign out, password reset.

The session cookie carries the same token core.auth already issues, so the
Streamlit app and the API share one session table and one revocation path.
"""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr

from api.deps import SESSION_COOKIE, current_account, fail

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE = dict(httponly=True, secure=True, samesite="lax", path="/",
              max_age=60 * 60 * 24 * 30)


def _client_ip(request: Request) -> str:
    """The address Caddy saw, not the socket, which is Caddy itself.

    Only the first hop of X-Forwarded-For is trusted, and only because this app
    is never exposed except behind its own proxy. A value a client sets itself
    is not identity, it is a hint, which is why the email bucket exists too.
    """
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else ""))


def _throttle(request: Request, email: str, limit: int, window: int, doing: str):
    from core.ratelimit import check, record_attempt
    buckets = [f"{doing}:email:{email.lower()}", f"{doing}:ip:{_client_ip(request)}"]
    allowed, retry = check(buckets, limit, window)
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Wait about 15 minutes and try again.",
            headers={"Retry-After": str(retry)})
    for b in buckets:
        record_attempt(b)
    return buckets


class Credentials(BaseModel):
    email: EmailStr
    password: str


class EmailOnly(BaseModel):
    email: EmailStr


class NewPassword(BaseModel):
    token_hash: str
    password: str


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: Credentials, request: Request, response: Response):
    from core.ratelimit import SIGNUP_LIMIT, SIGNUP_WINDOW_SECONDS
    from core.auth import password_problem, remember_session, sign_up
    _throttle(request, body.email, SIGNUP_LIMIT, SIGNUP_WINDOW_SECONDS, "signup")
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    try:
        sign_up(body.email, body.password)
    except Exception as exc:
        raise fail(exc, "creating your account")
    response.set_cookie(SESSION_COOKIE, remember_session(body.email), **COOKIE)
    return {"email": body.email}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    from core.ratelimit import LOGIN_LIMIT, LOGIN_WINDOW_SECONDS, clear
    from core.auth import remember_session, sign_in
    buckets = _throttle(request, body.email, LOGIN_LIMIT, LOGIN_WINDOW_SECONDS, "login")
    try:
        sign_in(body.email, body.password)
    except Exception as exc:
        raise fail(exc, "signing you in")
    # Someone who eventually remembers their password should not stay throttled.
    for b in buckets:
        clear(b)
    response.set_cookie(SESSION_COOKIE, remember_session(body.email), **COOKIE)
    return {"email": body.email}


@router.post("/logout")
def logout(response: Response, telos_session: str | None = Cookie(default=None)):
    """Revoke the token, not just the browser's copy of it.

    Without the explicit Cookie() this parameter is read as a query string, so
    the endpoint answered 200, cleared the cookie, and left the session valid
    server-side for its full 30 days. Signing out has to mean the token stops
    working, or it means nothing.
    """
    from core.auth import forget_session
    if telos_session:
        forget_session(telos_session)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.post("/reset")
def reset(body: EmailOnly, request: Request):
    """Always the same answer, whether or not the address exists.

    Telling the caller which addresses have accounts turns this endpoint into a
    membership oracle. The Streamlit flow is enumeration-safe and so is this.
    """
    from core.ratelimit import SIGNUP_LIMIT, SIGNUP_WINDOW_SECONDS
    from core.auth import send_password_reset
    _throttle(request, body.email, SIGNUP_LIMIT, SIGNUP_WINDOW_SECONDS, "reset")
    try:
        send_password_reset(body.email)
    except Exception:
        pass
    return {"sent": True}


@router.post("/reset/confirm")
def reset_confirm(body: NewPassword):
    from core.auth import password_problem, set_password_with_client, verify_recovery
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    try:
        client = verify_recovery(body.token_hash)
        set_password_with_client(client, body.password)
    except Exception as exc:
        raise fail(exc, "setting your new password")
    return {"ok": True}


@router.get("/session")
def whoami(account: str = Depends(current_account)):
    return {"email": account}
