"""
Authentication router for dbAI Pulse API.
Handles Yahoo Fantasy OAuth 2.0 flow.
"""

import logging
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from config import get_settings
from services.yahoo import get_yahoo_service

logger = logging.getLogger(__name__)

router = APIRouter()

# OAuth state storage (in-memory for now, use Redis/DB in production)
_oauth_states: dict = {}

# Yahoo OAuth endpoints
YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


@router.get("/yahoo/login")
async def yahoo_login(redirect_url: Optional[str] = Query(None)):
    """
    Initiate Yahoo OAuth flow.
    Redirects user to Yahoo consent screen.
    """
    settings = get_settings()
    
    if not settings.yahoo_client_id:
        raise HTTPException(
            status_code=500,
            detail="Yahoo OAuth not configured. Set YAHOO_CLIENT_ID in environment."
        )
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "redirect_url": redirect_url or "http://localhost:5173"
    }
    
    params = {
        "client_id": settings.yahoo_client_id,
        "redirect_uri": settings.yahoo_redirect_uri,
        "response_type": "code",
        "scope": "fspt-r",  # Fantasy Sports read access
        "state": state,
    }
    
    auth_url = f"{YAHOO_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/yahoo/callback")
async def yahoo_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    Handle Yahoo OAuth callback.
    Exchanges auth code for access token.
    """
    # Check for errors from Yahoo
    if error:
        logger.error(f"Yahoo OAuth error: {error} - {error_description}")
        raise HTTPException(
            status_code=400,
            detail=f"Yahoo authorization failed: {error_description or error}"
        )
    
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code or state"
        )
    
    # Validate state
    if state not in _oauth_states:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter. Possible CSRF attack."
        )
    
    state_data = _oauth_states.pop(state)
    redirect_url = state_data.get("redirect_url", "http://localhost:5173")
    
    settings = get_settings()
    
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                YAHOO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.yahoo_redirect_uri,
                },
                auth=(settings.yahoo_client_id, settings.yahoo_client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code != 200:
                logger.error(f"Yahoo token exchange failed: {response.text}")
                raise HTTPException(
                    status_code=400,
                    detail="Failed to exchange authorization code for tokens"
                )
            
            token_data = response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Yahoo token request failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to communicate with Yahoo OAuth server"
            )
    
    # Store token data in service
    yahoo_service = get_yahoo_service()
    yahoo_service.set_token_data({
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "consumer_key": settings.yahoo_client_id,
        "consumer_secret": settings.yahoo_client_secret,
        "token_time": token_data.get("expires_in", 3600),
        "token_type": token_data.get("token_type", "bearer"),
        "guid": token_data.get("xoauth_yahoo_guid"),
    })
    
    logger.info("Yahoo OAuth completed successfully")
    
    # Redirect back to frontend with success
    return RedirectResponse(url=f"{redirect_url}?yahoo_connected=true")


@router.get("/yahoo/status")
async def yahoo_status():
    """
    Check Yahoo connection status.
    """
    yahoo_service = get_yahoo_service()
    is_connected = yahoo_service.is_authenticated()
    
    return {
        "connected": is_connected,
        "service": "yahoo_fantasy",
    }


@router.post("/yahoo/disconnect")
async def yahoo_disconnect():
    """
    Disconnect Yahoo account.
    Clears stored tokens.
    """
    yahoo_service = get_yahoo_service()
    yahoo_service.set_token_data(None)
    yahoo_service.clear_cache()
    
    return {"status": "disconnected", "service": "yahoo_fantasy"}


@router.get("/yahoo/test")
async def yahoo_test():
    """
    Test Yahoo API connection by fetching user's leagues.
    Useful for verifying OAuth is working.
    """
    yahoo_service = get_yahoo_service()
    
    if not yahoo_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not connected to Yahoo. Please authenticate first."
        )
    
    try:
        leagues = await yahoo_service.get_user_leagues()
        return {
            "status": "success",
            "leagues_found": len(leagues),
            "leagues": leagues[:5],  # Return first 5 for preview
        }
    except Exception as e:
        logger.error(f"Yahoo API test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Yahoo API error: {str(e)}"
        )
