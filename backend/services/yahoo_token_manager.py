"""
Yahoo OAuth token lifecycle manager.
"""

import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from services.crypto import get_token_crypto
from services.oauth_config import get_missing_yahoo_oauth_fields, get_yahoo_oauth_config
from services.storage import get_storage

logger = logging.getLogger(__name__)

YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


class YahooTokenManager:
    """Handles storage, refresh, and validation for Yahoo OAuth tokens."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.crypto = get_token_crypto()

    @staticmethod
    def _require_oauth_config() -> Dict[str, str]:
        """Load effective Yahoo OAuth config and ensure required fields are present."""
        config = get_yahoo_oauth_config()
        missing = get_missing_yahoo_oauth_fields(config)
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"Yahoo OAuth not configured. Missing: {', '.join(missing)}.",
            )
        parsed = urlparse(config["redirect_uri"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise HTTPException(
                status_code=500,
                detail="Yahoo callback must be HTTPS. Update redirect_uri before connecting.",
            )
        return config

    def _normalize_token_payload(
        self,
        token_payload: Dict[str, Any],
        existing_token: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Normalize Yahoo token fields into a consistent dictionary shape."""
        now = int(time.time())
        existing = existing_token or {}
        oauth_config = self._require_oauth_config()

        access_token = token_payload.get("access_token") or existing.get("access_token")
        refresh_token = token_payload.get("refresh_token") or existing.get("refresh_token")
        token_type = token_payload.get("token_type") or existing.get("token_type") or "bearer"
        guid = token_payload.get("xoauth_yahoo_guid") or token_payload.get("guid") or existing.get("guid")

        expires_in_value = (
            token_payload.get("expires_in")
            or token_payload.get("expires")
            or existing.get("expires_in")
            or 3600
        )
        try:
            expires_in = max(60, int(expires_in_value))
        except (TypeError, ValueError):
            expires_in = 3600

        obtained_at_value = (
            token_payload.get("obtained_at")
            or token_payload.get("token_time")
            or existing.get("obtained_at")
            or existing.get("token_time")
        )
        if obtained_at_value is None:
            obtained_at = now
        else:
            try:
                obtained_at = int(obtained_at_value)
            except (TypeError, ValueError):
                obtained_at = now

        # If access token was rotated, reset obtained_at to now.
        if token_payload.get("access_token") and token_payload.get("access_token") != existing.get("access_token"):
            obtained_at = now

        expires_at = obtained_at + expires_in

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "consumer_key": oauth_config["client_id"],
            "consumer_secret": oauth_config["client_secret"],
            "token_type": token_type,
            "guid": guid,
            "expires_in": expires_in,
            "obtained_at": obtained_at,
            "expires_at": expires_at,
            # Kept for YFPY compatibility.
            "token_time": obtained_at,
        }

    def _require_token_fields(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate required token fields."""
        required = ("access_token", "refresh_token", "consumer_key", "consumer_secret")
        missing = [field for field in required if not token_data.get(field)]
        if missing:
            raise HTTPException(
                status_code=401,
                detail=f"Yahoo token missing required fields: {', '.join(missing)}. Please reconnect.",
            )
        return token_data

    def get_stored_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return decrypted token payload from storage, if present."""
        record = self.storage.get_yahoo_token(user_id)
        if record is None:
            return None

        encrypted_payload = record.get("encrypted_token_json")
        if not encrypted_payload:
            return None

        try:
            token_data = self.crypto.decrypt_token(encrypted_payload)
        except ValueError:
            logger.warning("Unable to decrypt Yahoo token for user_id=%s; clearing token.", user_id)
            self.clear_token(user_id)
            return None

        if "expires_at" not in token_data and record.get("expires_at"):
            token_data["expires_at"] = int(record["expires_at"])

        return token_data

    def save_token(self, user_id: str, token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and persist token payload for a user."""
        normalized = self._normalize_token_payload(token_payload)
        validated = self._require_token_fields(normalized)

        encrypted_payload = self.crypto.encrypt_token(validated)
        self.storage.save_yahoo_token(
            user_id=user_id,
            encrypted_token_json=encrypted_payload,
            expires_at=int(validated["expires_at"]),
        )
        return validated

    def save_external_token(
        self,
        user_id: str,
        token_payload: Dict[str, Any],
        existing_token: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a token payload originating from Yahoo API client internals."""
        normalized = self._normalize_token_payload(token_payload, existing_token=existing_token)
        validated = self._require_token_fields(normalized)
        encrypted_payload = self.crypto.encrypt_token(validated)

        self.storage.save_yahoo_token(
            user_id=user_id,
            encrypted_token_json=encrypted_payload,
            expires_at=int(validated["expires_at"]),
        )
        return validated

    def clear_token(self, user_id: str) -> None:
        """Delete stored token and cached insights for a user."""
        self.storage.delete_yahoo_token(user_id)
        self.storage.clear_team_insights_cache(user_id)

    async def refresh_access_token(self, user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh Yahoo access token using the stored refresh token."""
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            self.clear_token(user_id)
            raise HTTPException(status_code=401, detail="Yahoo refresh token missing. Please reconnect.")

        oauth_config = self._require_oauth_config()

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(
                    YAHOO_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "redirect_uri": oauth_config["redirect_uri"],
                    },
                    auth=(oauth_config["client_id"], oauth_config["client_secret"]),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.RequestError as exc:
                logger.error("Yahoo token refresh request failed for user_id=%s: %s", user_id, exc)
                raise HTTPException(
                    status_code=502,
                    detail="Failed to communicate with Yahoo OAuth server while refreshing token.",
                )

        if response.status_code != 200:
            await self._handle_refresh_failure(user_id, response)

        refreshed_payload = response.json()
        refreshed_token = self._normalize_token_payload(refreshed_payload, existing_token=token_data)
        validated = self._require_token_fields(refreshed_token)

        encrypted_payload = self.crypto.encrypt_token(validated)
        self.storage.save_yahoo_token(
            user_id=user_id,
            encrypted_token_json=encrypted_payload,
            expires_at=int(validated["expires_at"]),
        )

        logger.info("Refreshed Yahoo token for user_id=%s", user_id)
        return validated

    async def _handle_refresh_failure(self, user_id: str, response: httpx.Response) -> None:
        """Map refresh failures to safe HTTP errors and clear invalid tokens."""
        error_code = ""
        error_description = ""

        try:
            error_payload = response.json()
            error_code = str(error_payload.get("error", "")).lower()
            error_description = str(error_payload.get("error_description", ""))
        except Exception:
            error_code = ""
            error_description = response.text

        if error_code in {"invalid_grant", "invalid_token", "token_expired"}:
            logger.warning("Yahoo token refresh rejected for user_id=%s (%s)", user_id, error_code)
            self.clear_token(user_id)
            raise HTTPException(status_code=401, detail="Yahoo session expired. Please reconnect.")

        if error_code == "invalid_scope":
            logger.error("Yahoo token refresh invalid scope for user_id=%s", user_id)
            raise HTTPException(
                status_code=400,
                detail="Yahoo OAuth scope rejected. Verify app scope includes Fantasy read access.",
            )

        if error_code == "invalid_redirect_uri":
            logger.error("Yahoo token refresh invalid redirect URI for user_id=%s", user_id)
            raise HTTPException(
                status_code=500,
                detail="Yahoo redirect URI mismatch. Verify YAHOO_REDIRECT_URI configuration.",
            )

        logger.error(
            "Yahoo token refresh failed for user_id=%s with status=%s error=%s description=%s",
            user_id,
            response.status_code,
            error_code,
            error_description,
        )
        raise HTTPException(status_code=502, detail="Yahoo token refresh failed.")

    async def get_valid_token(self, user_id: str, proactive_refresh_seconds: int = 300) -> Dict[str, Any]:
        """Load token for user and refresh when near expiry."""
        token_data = self.get_stored_token(user_id)
        if token_data is None:
            raise HTTPException(status_code=401, detail="Not connected to Yahoo. Please authenticate first.")

        validated = self._require_token_fields(token_data)
        now = int(time.time())
        expires_at = int(validated.get("expires_at") or 0)

        if expires_at <= now + proactive_refresh_seconds:
            validated = await self.refresh_access_token(user_id, validated)

        return validated

    async def is_connected(self, user_id: str) -> bool:
        """Return True when user has a valid, refreshable Yahoo token."""
        token_data = self.get_stored_token(user_id)
        if token_data is None:
            return False

        try:
            self._require_token_fields(token_data)
        except HTTPException:
            return False

        return True


_token_manager: Optional[YahooTokenManager] = None


def get_yahoo_token_manager() -> YahooTokenManager:
    """Get or create the Yahoo token manager singleton."""
    global _token_manager
    if _token_manager is None:
        _token_manager = YahooTokenManager()
    return _token_manager
