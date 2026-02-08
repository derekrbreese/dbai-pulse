"""
Account authentication router for dbAI Pulse API.
"""

import logging
import re
import sqlite3
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from models.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
    AuthUser,
)
from services.passwords import hash_password, verify_password
from services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter()

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
