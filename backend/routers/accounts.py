"""
Account authentication router for dbAI Pulse API.
"""

import logging
import re
import sqlite3
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import get_settings
from models.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
    AuthUser,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from services.email import send_password_reset_email
from services.passwords import hash_password, verify_password
from services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(email: str) -> str:
    """Normalize user email for lookup and storage."""
    return email.strip().lower()


def _validate_email(email: str) -> bool:
    """Return True if email is a minimally valid address."""
    return bool(EMAIL_PATTERN.match(email))


def _to_auth_user(row: dict) -> AuthUser:
    """Map storage row dictionary into API-safe user model."""
    return AuthUser(
        id=str(row["id"]),
        email=str(row["email"]),
        created_at=int(row["created_at"]),
        last_login_at=int(row["last_login_at"]) if row.get("last_login_at") is not None else None,
    )


@router.get("/me", response_model=AuthSessionResponse)
async def auth_me(request: Request):
    """Return authenticated user for current session."""
    user_id = request.session.get("auth_user_id")
    if not user_id:
        return AuthSessionResponse(authenticated=False, user=None)

    storage = get_storage()
    row = storage.get_user_by_id(str(user_id))
    if not row:
        request.session.pop("auth_user_id", None)
        return AuthSessionResponse(authenticated=False, user=None)

    return AuthSessionResponse(authenticated=True, user=_to_auth_user(row))


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_account(payload: AuthRegisterRequest, request: Request):
    """Create a local user account and start an authenticated session."""
    email = _normalize_email(payload.email)
    if not _validate_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    storage = get_storage()
    if storage.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account already exists for that email.")

    user_id = str(uuid4())
    password_hash = hash_password(payload.password)

    try:
        row = storage.create_user(user_id=user_id, email=email, password_hash=password_hash)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account already exists for that email.")

    request.session["auth_user_id"] = user_id
    request.session.pop("yahoo_oauth", None)

    logger.info("Registered new account user_id=%s", user_id)
    return AuthSessionResponse(authenticated=True, user=_to_auth_user(row))


@router.post("/login", response_model=AuthSessionResponse)
@limiter.limit("5/minute")
async def login_account(payload: AuthLoginRequest, request: Request):
    """Authenticate an existing account and start session."""
    email = _normalize_email(payload.email)
    if not _validate_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    storage = get_storage()
    row = storage.get_user_by_email(email)
    if not row or not verify_password(payload.password, str(row["password_hash"])):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user_id = str(row["id"])
    storage.update_user_last_login(user_id)
    refreshed = storage.get_user_by_id(user_id) or row

    request.session["auth_user_id"] = user_id
    request.session.pop("yahoo_oauth", None)

    logger.info("Account login user_id=%s", user_id)
    return AuthSessionResponse(authenticated=True, user=_to_auth_user(refreshed))


@router.post("/logout", response_model=AuthSessionResponse)
async def logout_account(request: Request):
    """Clear authenticated session for current browser."""
    user_id = request.session.get("auth_user_id")
    request.session.clear()
    logger.info("Account logout user_id=%s", user_id)
    return AuthSessionResponse(authenticated=False, user=None)


# --- Password reset (forgot password) ---

RESET_TOKEN_MAX_AGE = 3600  # 1 hour


def _get_reset_serializer() -> URLSafeTimedSerializer:
    """Serializer for password reset tokens, keyed on session secret."""
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret_key, salt="password-reset")


def _build_reset_url(request: Request, token: str) -> str:
    """Build the frontend reset URL from the request origin."""
    settings = get_settings()
    origins = settings.frontend_origin_list
    origin = request.headers.get("origin") or request.headers.get("referer", "")

    # Use the first matching frontend origin, fallback to first configured
    base = origins[0] if origins else "http://localhost:5173"
    for o in origins:
        if origin.startswith(o):
            base = o
            break

    return f"{base}/#/reset-password?token={token}"


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    """Send a password reset email if the account exists."""
    email = _normalize_email(payload.email)

    # Always return success to prevent email enumeration
    storage = get_storage()
    row = storage.get_user_by_email(email)

    if row:
        serializer = _get_reset_serializer()
        token = serializer.dumps(email)
        reset_url = _build_reset_url(request, token)
        send_password_reset_email(email, reset_url)
        logger.info("Password reset requested for %s", email)

    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(payload: ResetPasswordRequest, request: Request):
    """Verify reset token and set a new password."""
    serializer = _get_reset_serializer()

    try:
        email = serializer.loads(payload.token, max_age=RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid reset link.")

    email = _normalize_email(email)
    storage = get_storage()
    row = storage.get_user_by_email(email)

    if not row:
        raise HTTPException(status_code=400, detail="Account not found.")

    new_hash = hash_password(payload.password)
    storage.update_user_password(str(row["id"]), new_hash)

    logger.info("Password reset completed for %s", email)
    return {"message": "Password has been reset. You can now sign in."}


# --- Change password (logged in) ---


@router.put("/change-password")
async def change_password(payload: ChangePasswordRequest, request: Request):
    """Change password for the currently authenticated user."""
    user_id = request.session.get("auth_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required.")

    storage = get_storage()
    row = storage.get_user_by_id(str(user_id))

    if not row:
        raise HTTPException(status_code=401, detail="Account not found.")

    if not verify_password(payload.current_password, str(row["password_hash"])):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    new_hash = hash_password(payload.new_password)
    storage.update_user_password(str(user_id), new_hash)

    logger.info("Password changed for user_id=%s", user_id)
    return {"message": "Password updated successfully."}
