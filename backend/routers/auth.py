"""
Authentication router for dbAI Pulse API.
Handles Yahoo Fantasy OAuth 2.0 flow.
"""

import base64
import hashlib
import logging
import secrets
import time
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from config import get_settings
from routers.session_utils import get_authenticated_user_id
from services.oauth_config import (
    get_missing_yahoo_oauth_fields,
    get_yahoo_oauth_config,
    get_yahoo_oauth_status,
    save_yahoo_oauth_config,
)
from services.yahoo import get_yahoo_service
from services.yahoo_token_manager import get_yahoo_token_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Yahoo OAuth endpoints
YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


class YahooOAuthConfigUpdate(BaseModel):
    """Request model for in-app Yahoo OAuth setup."""

    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    redirect_uri: Optional[str] = None
    scope: Optional[str] = None


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE verifier and SHA256 challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def _is_allowed_redirect_url(redirect_url: str, allowed_origins: list[str]) -> bool:
    """Validate redirect URL origin against configured allowlist."""
    parsed = urlparse(redirect_url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False

    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin in allowed_origins


def _append_query_params(url: str, params: Dict[str, str]) -> str:
    """Append query params to a URL while preserving existing params."""
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(params)
    updated = parsed._replace(query=urlencode(query))
    return urlunparse(updated)


def _is_valid_https_callback(redirect_uri: str) -> bool:
    """Validate Yahoo callback URL format and HTTPS requirement."""
    parsed = urlparse(redirect_uri)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _map_oauth_error(error_code: str, error_description: str) -> HTTPException:
    """Map Yahoo OAuth provider errors to user-safe HTTP responses."""
    lower_error = error_code.lower()

    if lower_error in {"invalid_grant", "invalid_token"}:
        return HTTPException(
            status_code=401,
            detail="Yahoo authorization code was rejected or expired. Please try connecting again.",
        )

    if lower_error == "invalid_scope":
        return HTTPException(
            status_code=400,
            detail="Yahoo OAuth scope rejected. Verify app scope includes Fantasy read access.",
        )

    if lower_error == "invalid_redirect_uri":
        return HTTPException(
            status_code=500,
            detail="Yahoo redirect URI mismatch. Verify YAHOO_REDIRECT_URI configuration.",
        )

    if lower_error == "access_denied":
        return HTTPException(status_code=400, detail="Yahoo authorization was denied.")

    if error_description:
        return HTTPException(status_code=400, detail=f"Yahoo authorization failed: {error_description}")

    return HTTPException(status_code=400, detail=f"Yahoo authorization failed: {error_code}")


@router.get("/yahoo/login")
async def yahoo_login(
    request: Request,
    redirect_url: Optional[str] = Query(None),
):
    """
    Initiate Yahoo OAuth flow.
    Redirects user to Yahoo consent screen.
    """
    get_authenticated_user_id(request)
    settings = get_settings()
    oauth_config = get_yahoo_oauth_config()
    missing_fields = get_missing_yahoo_oauth_fields(oauth_config)
    if missing_fields:
        raise HTTPException(
            status_code=500,
            detail=(
                "Yahoo OAuth not configured. "
                f"Missing: {', '.join(missing_fields)}."
            ),
        )
    if not _is_valid_https_callback(oauth_config["redirect_uri"]):
        raise HTTPException(
            status_code=400,
            detail=(
                "Yahoo callback must be HTTPS. Set redirect_uri to an https:// URL, "
                "then use that same exact URL in Yahoo app settings."
            ),
        )

    allowed_origins = settings.frontend_origin_list
    resolved_redirect = redirect_url or (allowed_origins[0] if allowed_origins else "http://localhost:5173")

    if not _is_allowed_redirect_url(resolved_redirect, allowed_origins):
        raise HTTPException(
            status_code=400,
            detail="Invalid redirect_url. Redirect must match configured frontend origins.",
        )

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce_pair()

    request.session["yahoo_oauth"] = {
        "state": state,
        "code_verifier": code_verifier,
        "redirect_url": resolved_redirect,
        "created_at": int(time.time()),
    }

    params = {
        "client_id": oauth_config["client_id"],
        "redirect_uri": oauth_config["redirect_uri"],
        "response_type": "code",
        "scope": oauth_config["scope"],
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{YAHOO_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/yahoo/callback")
async def yahoo_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    Handle Yahoo OAuth callback.
    Exchanges auth code for access token.
    """
    if error:
        logger.warning("Yahoo OAuth returned error=%s", error)
        raise _map_oauth_error(error, error_description or "")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization code or state")

    oauth_session = request.session.pop("yahoo_oauth", None)
    if not oauth_session:
        raise HTTPException(status_code=400, detail="Missing OAuth session context. Please reconnect.")

    if oauth_session.get("state") != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter. Possible CSRF attack.")

    created_at = oauth_session.get("created_at")
    if isinstance(created_at, int):
        if int(time.time()) - created_at > 15 * 60:
            raise HTTPException(status_code=400, detail="Yahoo OAuth session expired. Please reconnect.")

    code_verifier = oauth_session.get("code_verifier")
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier in session. Please reconnect.")

    redirect_url = oauth_session.get("redirect_url") or "http://localhost:5173"

    oauth_config = get_yahoo_oauth_config()
    missing_fields = get_missing_yahoo_oauth_fields(oauth_config)
    if missing_fields:
        raise HTTPException(
            status_code=500,
            detail=(
                "Yahoo OAuth not configured. "
                f"Missing: {', '.join(missing_fields)}."
            ),
        )

    user_id = get_authenticated_user_id(request)

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(
                YAHOO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": oauth_config["redirect_uri"],
                    "code_verifier": code_verifier,
                },
                auth=(oauth_config["client_id"], oauth_config["client_secret"]),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.RequestError as exc:
            logger.error("Yahoo token exchange request failed: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Failed to communicate with Yahoo OAuth server.",
            )

    if response.status_code != 200:
        error_code = ""
        error_text = response.text
        try:
            error_payload = response.json()
            error_code = str(error_payload.get("error", ""))
            error_text = str(error_payload.get("error_description", error_text))
        except Exception:
            pass
        logger.warning("Yahoo token exchange failed: status=%s error=%s", response.status_code, error_code)
        raise _map_oauth_error(error_code or "token_exchange_failed", error_text)

    token_payload = response.json()
    token_manager = get_yahoo_token_manager()
    token_manager.save_token(user_id, token_payload)

    logger.info("Yahoo OAuth completed for user_id=%s", user_id)
    return RedirectResponse(url=_append_query_params(redirect_url, {"yahoo_connected": "true"}))


@router.get("/yahoo/status")
async def yahoo_status(request: Request):
    """
    Check Yahoo connection status.
    """
    user_id = get_authenticated_user_id(request)
    status_payload = get_yahoo_oauth_status()
    configured = bool(status_payload.get("configured"))

    if not configured:
        return {
            "connected": False,
            "hasTeams": False,
            "teamCount": 0,
            "configured": False,
            "missingEnv": status_payload.get("missingEnv", []),
            "redirectUri": status_payload.get("redirectUri"),
            "scope": status_payload.get("scope"),
            "service": "yahoo_fantasy",
        }

    token_manager = get_yahoo_token_manager()

    connected = await token_manager.is_connected(user_id)
    team_count = 0
    has_teams = False

    if connected:
        try:
            token_data = await token_manager.get_valid_token(user_id, proactive_refresh_seconds=120)
            yahoo_service = get_yahoo_service(token_data, user_id)
            teams = await yahoo_service.get_user_teams()
            team_count = len(teams)
            has_teams = team_count > 0

            # Persist any in-client token refresh updates.
            token_manager.save_external_token(
                user_id=user_id,
                token_payload=yahoo_service.get_token_data(),
                existing_token=token_data,
            )
        except HTTPException as exc:
            if exc.status_code == 401:
                connected = False
                team_count = 0
                has_teams = False
            else:
                raise
        except Exception as exc:
            # Token is valid but team listing failed (e.g. yfpy parsing error).
            # Report connected but with zero teams so the UI isn't blocked.
            logger.warning("Yahoo status team fetch failed (non-auth): %s", exc)
            team_count = 0
            has_teams = False

    return {
        "connected": connected,
        "hasTeams": has_teams,
        "teamCount": team_count,
        "configured": True,
        "missingEnv": [],
        "redirectUri": status_payload.get("redirectUri"),
        "scope": status_payload.get("scope"),
        "service": "yahoo_fantasy",
    }


@router.get("/yahoo/config")
async def yahoo_config_status(request: Request):
    """
    Get Yahoo OAuth setup status and non-secret defaults for in-app setup.
    """
    get_authenticated_user_id(request)
    cfg = get_yahoo_oauth_config()
    status_payload = get_yahoo_oauth_status()
    return {
        "configured": status_payload.get("configured", False),
        "missingEnv": status_payload.get("missingEnv", []),
        "clientIdHint": status_payload.get("clientIdHint"),
        "hasClientSecret": status_payload.get("hasClientSecret", False),
        "redirectUri": cfg.get("redirect_uri"),
        "scope": cfg.get("scope"),
    }


@router.put("/yahoo/config")
async def yahoo_config_update(request: Request, payload: YahooOAuthConfigUpdate):
    """
    Save Yahoo OAuth config from in-app setup form.
    """
    get_authenticated_user_id(request)
    redirect_uri = (payload.redirect_uri or "").strip() or None
    if redirect_uri:
        parsed = urlparse(redirect_uri)
        if parsed.scheme != "https" or not parsed.netloc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid redirect_uri. Yahoo requires a full HTTPS callback URL "
                    "(example: https://your-domain/api/auth/yahoo/callback)."
                ),
            )

    try:
        save_yahoo_oauth_config(
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            redirect_uri=redirect_uri,
            scope=payload.scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    status_payload = get_yahoo_oauth_status()
    return {
        "status": "saved",
        "configured": status_payload.get("configured", False),
        "missingEnv": status_payload.get("missingEnv", []),
        "redirectUri": status_payload.get("redirectUri"),
        "scope": status_payload.get("scope"),
    }


@router.post("/yahoo/disconnect")
async def yahoo_disconnect(request: Request):
    """
    Disconnect Yahoo account.
    Clears stored tokens.
    """
    user_id = get_authenticated_user_id(request)
    token_manager = get_yahoo_token_manager()
    token_manager.clear_token(user_id)

    return {"status": "disconnected", "service": "yahoo_fantasy"}


@router.get("/yahoo/test")
async def yahoo_test(request: Request):
    """
    Test Yahoo API connection by fetching user's leagues.
    Useful for verifying OAuth is working.
    """
    user_id = get_authenticated_user_id(request)
    token_manager = get_yahoo_token_manager()
    token_data = await token_manager.get_valid_token(user_id)

    yahoo_service = get_yahoo_service(token_data, user_id)

    try:
        leagues = await yahoo_service.get_user_leagues()
        token_manager.save_external_token(
            user_id=user_id,
            token_payload=yahoo_service.get_token_data(),
            existing_token=token_data,
        )
        return {
            "status": "success",
            "leagues_found": len(leagues),
            "leagues": leagues[:5],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Yahoo API test failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Yahoo API error: {str(exc)}")
