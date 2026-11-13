"""Invite-only account, session and CSRF handling for the first beta."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from psycopg import errors

from . import db

SESSION_COOKIE = "spoonfuls_session"
CSRF_COOKIE = "spoonfuls_csrf"
SESSION_MAX_AGE = 30 * 24 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_FAILURE_LIMIT = 5
SHORT_RATE_WINDOW_SECONDS = 60
GLOBAL_ATTEMPT_LIMIT = 60
SIGNUP_ATTEMPT_LIMIT = 5
INVITE_ATTEMPT_LIMIT = 10
PASSWORD_HASHER = PasswordHasher()
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$FWmkcCulh2OixrVDCVNQqA$"
    "a2TvrvCymRfXedbR+PAS4ovBNOqaflfAHngPCL8P6I0"
)
COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "password12",
        "password123",
        "qwertyuiop",
        "letmein123",
        "welcome123",
        "iloveyou123",
    }
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# In-memory limits are intentionally simple for the single-worker beta.
_rate_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_login_lock = threading.Lock()

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str
    invite_code: str | None = None
    bootstrap_code: str | None = None


class InviteRequest(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=30)


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    session_id: UUID
    email: str
    is_admin: bool
    csrf_token_hash: str | None


def _normalise_email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 254 or not EMAIL_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail={"field": "email", "message": "Enter a valid email address."})
    return value


def _validate_password(password: str) -> None:
    if len(password) < 10:
        raise HTTPException(
            status_code=400,
            detail={"field": "password", "message": "Use at least 10 characters."},
        )
    if password.casefold() in COMMON_PASSWORDS:
        raise HTTPException(
            status_code=400,
            detail={"field": "password", "message": "Choose a less common password."},
        )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _cookie_secure() -> bool:
    return os.environ.get("SPOONFULS_COOKIE_SECURE", "1") != "0"


def _set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=SESSION_MAX_AGE,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _check_rate(bucket: str, key: str, limit: int, window: int) -> None:
    now = time.monotonic()
    with _login_lock:
        attempts = _rate_events[(bucket, key)]
        while attempts and now - attempts[0] >= window:
            attempts.popleft()
        if len(attempts) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Try again later.",
                headers={"Retry-After": str(window)},
            )
        attempts.append(now)


def _record_login_failure(key: str) -> None:
    now = time.monotonic()
    with _login_lock:
        attempts = _rate_events[("login-failure", key)]
        while attempts and now - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        attempts.append(now)


def _clear_login_failures(key: str) -> None:
    with _login_lock:
        _rate_events.pop(("login-failure", key), None)


def _set_request_identity(conn, user_id: UUID, session_hash: str | None = None) -> None:
    conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
    if session_hash is not None:
        conn.execute("SELECT set_config('app.session_hash', %s, true)", (session_hash,))


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user(request: Request) -> AuthContext:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise _unauthorized()
    token_hash = _hash_token(token)
    with db.connection() as cleanup_conn:
        cleanup_conn.execute("SELECT spoonfuls_prune_expired_sessions()")
    with db.connection() as conn:
        conn.execute("SELECT set_config('app.session_hash', %s, true)", (token_hash,))
        session = conn.execute(
            "SELECT id, user_id, csrf_token_hash FROM sessions "
            "WHERE token_hash = %s AND expires_at > now()",
            (token_hash,),
        ).fetchone()
        if session is None:
            raise _unauthorized()
        session_id, user_id, csrf_token_hash = session
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
        user = conn.execute(
            "SELECT id, email, is_admin FROM users WHERE id = %s", (user_id,)
        ).fetchone()
    if user is None:
        raise _unauthorized()
    return AuthContext(
        user_id=user[0],
        session_id=session_id,
        email=user[1],
        is_admin=user[2],
        csrf_token_hash=csrf_token_hash,
    )


def require_csrf(request: Request, auth: AuthContext = Depends(current_user)) -> AuthContext:
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get("X-CSRF-Token")
    if (
        not csrf_cookie
        or not csrf_header
        or not hmac.compare_digest(csrf_cookie, csrf_header)
        or not auth.csrf_token_hash
        or not hmac.compare_digest(_hash_token(csrf_cookie), auth.csrf_token_hash)
    ):
        raise HTTPException(status_code=403, detail="CSRF token is required.")
    return auth


def _create_session(conn, user_id: UUID) -> tuple[str, str]:
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    _set_request_identity(conn, user_id)
    conn.execute(
        "INSERT INTO sessions (user_id, token_hash, csrf_token_hash, expires_at) "
        "VALUES (%s, %s, %s, now() + interval '30 days')",
        (user_id, _hash_token(session_token), _hash_token(csrf_token)),
    )
    return session_token, csrf_token


@router.get("/me")
def me(auth: AuthContext = Depends(current_user)):
    return {"id": str(auth.user_id), "email": auth.email, "is_admin": auth.is_admin}


@router.post("/signup", status_code=201)
def signup(payload: Credentials, response: Response):
    email = _normalise_email(payload.email)
    _check_rate("global", "auth", GLOBAL_ATTEMPT_LIMIT, SHORT_RATE_WINDOW_SECONDS)
    _check_rate("signup", email, SIGNUP_ATTEMPT_LIMIT, SHORT_RATE_WINDOW_SECONDS)
    _validate_password(payload.password)
    password_hash = PASSWORD_HASHER.hash(payload.password)
    try:
        with db.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('spoonfuls-signup', 0))")
            has_users = conn.execute("SELECT spoonfuls_has_users()").fetchone()[0]
            if not has_users:
                bootstrap_code = os.environ.get("SPOONFULS_BOOTSTRAP_CODE")
                if (
                    not bootstrap_code
                    or not payload.bootstrap_code
                    or not hmac.compare_digest(payload.bootstrap_code, bootstrap_code)
                ):
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "field": "bootstrap_code",
                            "message": "The first account needs the owner-provided bootstrap code.",
                        },
                    )
            if has_users:
                if not payload.invite_code:
                    raise HTTPException(status_code=400, detail={"field": "invite_code", "message": "An invite code is required."})
                valid_invite = conn.execute(
                    "SELECT spoonfuls_consume_invite(%s)", (_hash_token(payload.invite_code),)
                ).fetchone()[0]
                if not valid_invite:
                    raise HTTPException(status_code=400, detail={"field": "invite_code", "message": "That invite code is expired or already used."})
            user_id = uuid4()
            _set_request_identity(conn, user_id)
            conn.execute(
                "INSERT INTO users (id, email, password_hash, is_admin) VALUES (%s, %s, %s, %s)",
                (user_id, email, password_hash, not has_users),
            )
            session_token, csrf_token = _create_session(conn, user_id)
    except errors.UniqueViolation:
        raise HTTPException(status_code=409, detail={"field": "email", "message": "An account already uses that email."}) from None
    _set_auth_cookies(response, session_token, csrf_token)
    return {"id": str(user_id), "email": email, "is_admin": not has_users}


@router.post("/signin")
def signin(payload: Credentials, response: Response):
    email = _normalise_email(payload.email)
    key = email
    _check_rate("global", "auth", GLOBAL_ATTEMPT_LIMIT, SHORT_RATE_WINDOW_SECONDS)
    _check_rate("login", email, LOGIN_FAILURE_LIMIT, LOGIN_WINDOW_SECONDS)
    with db.connection() as conn:
        row = conn.execute(
            "SELECT user_id, password_hash FROM lookup_user_for_login(%s)", (email,)
        ).fetchone()
        valid = False
        stored_hash = row[1] if row is not None else DUMMY_PASSWORD_HASH
        try:
            valid = PASSWORD_HASHER.verify(stored_hash, payload.password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            valid = False
        if not valid:
            _record_login_failure(key)
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        _clear_login_failures(key)
        session_token, csrf_token = _create_session(conn, row[0])
    _set_auth_cookies(response, session_token, csrf_token)
    return {"id": str(row[0]), "email": email}


@router.post("/signout", status_code=204)
def signout(response: Response, auth: AuthContext = Depends(require_csrf)):
    with db.connection() as conn:
        _set_request_identity(conn, auth.user_id)
        conn.execute("DELETE FROM sessions WHERE id = %s", (auth.session_id,))
    _clear_auth_cookies(response)


@router.post("/signout-everywhere", status_code=204)
def signout_everywhere(response: Response, auth: AuthContext = Depends(require_csrf)):
    with db.connection() as conn:
        _set_request_identity(conn, auth.user_id)
        conn.execute("DELETE FROM sessions WHERE user_id = %s", (auth.user_id,))
    _clear_auth_cookies(response)


@router.post("/invites", status_code=201)
def create_invite(
    payload: InviteRequest,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
):
    if not auth.is_admin:
        raise HTTPException(status_code=403, detail="Only an admin can create invites.")
    _check_rate("global", "auth", GLOBAL_ATTEMPT_LIMIT, SHORT_RATE_WINDOW_SECONDS)
    _check_rate("invite", str(auth.user_id), INVITE_ATTEMPT_LIMIT, SHORT_RATE_WINDOW_SECONDS)
    code = secrets.token_urlsafe(18)
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
    with db.connection() as conn:
        _set_request_identity(conn, auth.user_id)
        conn.execute(
            "INSERT INTO invites (code_hash, created_by, expires_at) VALUES (%s, %s, %s)",
            (_hash_token(code), auth.user_id, expires_at),
        )
    return {"code": code, "expires_at": expires_at.isoformat()}
