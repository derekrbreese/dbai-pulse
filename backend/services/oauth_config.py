"""
App-managed Yahoo OAuth configuration service.
"""

import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

from config import get_settings
from services.crypto import get_token_crypto
from services.storage import get_storage

logger = logging.getLogger(__name__)

_KEY_CLIENT_ID = "yahoo_client_id"
_KEY_CLIENT_SECRET_ENCRYPTED = "yahoo_client_secret_encrypted"
_KEY_REDIRECT_URI = "yahoo_redirect_uri"
_KEY_SCOPE = "yahoo_scope"


def _mask_value(value: Optional[str], visible: int = 4) -> Optional[str]:
    """Mask secrets for status responses."""
    if not value:
        return None
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"


def _load_stored_value(key: str) -> Optional[str]:
    """Read one app setting value by key."""
    row = get_storage().get_app_setting(key)
    if not row:
        return None
    value = str(row.get("value", "")).strip()
    return value or None


def _load_stored_secret() -> Optional[str]:
    """Read and decrypt stored Yahoo client secret."""
    encrypted = _load_stored_value(_KEY_CLIENT_SECRET_ENCRYPTED)
    if not encrypted:
        return None

    try:
        return get_token_crypto().decrypt_text(encrypted)
    except ValueError:
        logger.warning("Failed to decrypt stored Yahoo client secret; ignoring stored value.")
        return None


def _is_valid_https_redirect_uri(value: str) -> bool:
    """Return True when redirect URI is a valid absolute HTTPS URL."""
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def get_yahoo_oauth_config() -> Dict[str, str]:
    """
    Return effective Yahoo OAuth config.

    Environment variables take precedence over app-saved values.
    """
    settings = get_settings()

    client_id = settings.yahoo_client_id or _load_stored_value(_KEY_CLIENT_ID) or ""
    client_secret = settings.yahoo_client_secret or _load_stored_secret() or ""
    redirect_uri = (
        settings.yahoo_redirect_uri
        or _load_stored_value(_KEY_REDIRECT_URI)
        or ""
    )
    scope = settings.yahoo_scope or _load_stored_value(_KEY_SCOPE) or "fspt-r"

    return {
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip(),
        "redirect_uri": redirect_uri.strip(),
        "scope": scope.strip(),
    }


def get_missing_yahoo_oauth_fields(config: Optional[Dict[str, str]] = None) -> List[str]:
    """Return missing required Yahoo OAuth fields."""
    cfg = config or get_yahoo_oauth_config()
    missing: List[str] = []
    if not cfg.get("client_id"):
        missing.append("YAHOO_CLIENT_ID")
    if not cfg.get("client_secret"):
        missing.append("YAHOO_CLIENT_SECRET")
    if not cfg.get("redirect_uri"):
        missing.append("YAHOO_REDIRECT_URI")
    return missing


def is_yahoo_oauth_configured() -> bool:
    """Return True when required Yahoo OAuth fields are available."""
    config = get_yahoo_oauth_config()
    return (
        len(get_missing_yahoo_oauth_fields(config)) == 0
        and _is_valid_https_redirect_uri(config.get("redirect_uri", ""))
    )


def save_yahoo_oauth_config(
    client_id: str,
    client_secret: str,
    redirect_uri: Optional[str] = None,
    scope: Optional[str] = None,
) -> Dict[str, str]:
    """Persist Yahoo OAuth config to app settings."""
    clean_client_id = client_id.strip()
    clean_client_secret = client_secret.strip()
    clean_redirect_uri = (redirect_uri or "").strip()
    clean_scope = (scope or "fspt-r").strip()

    if not clean_client_id:
        raise ValueError("client_id is required")
    if not clean_client_secret:
        raise ValueError("client_secret is required")
    if not clean_redirect_uri:
        raise ValueError("redirect_uri is required")
    if not _is_valid_https_redirect_uri(clean_redirect_uri):
        raise ValueError("redirect_uri must be a full HTTPS URL for Yahoo OAuth.")

    storage = get_storage()
    crypto = get_token_crypto()

    storage.save_app_setting(_KEY_CLIENT_ID, clean_client_id)
    storage.save_app_setting(_KEY_CLIENT_SECRET_ENCRYPTED, crypto.encrypt_text(clean_client_secret))
    storage.save_app_setting(_KEY_REDIRECT_URI, clean_redirect_uri)
    storage.save_app_setting(_KEY_SCOPE, clean_scope)

    return get_yahoo_oauth_config()


def get_yahoo_oauth_status() -> Dict[str, object]:
    """Return client-safe Yahoo OAuth setup status for UI."""
    cfg = get_yahoo_oauth_config()
    missing = get_missing_yahoo_oauth_fields(cfg)
    issues: List[str] = []
    redirect_uri = cfg.get("redirect_uri", "")
    if redirect_uri and not _is_valid_https_redirect_uri(redirect_uri):
        issues.append("YAHOO_REDIRECT_URI_HTTPS")

    configured = len(missing) == 0 and len(issues) == 0

    return {
        "configured": configured,
        "missingEnv": [*missing, *issues],
        "clientIdHint": _mask_value(cfg.get("client_id")),
        "hasClientSecret": bool(cfg.get("client_secret")),
        "redirectUri": cfg.get("redirect_uri"),
        "scope": cfg.get("scope"),
    }
