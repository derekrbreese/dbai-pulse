"""
Encryption helpers for persisting OAuth token payloads.
"""

import base64
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from config import get_settings

logger = logging.getLogger(__name__)


def _derive_fernet_key(seed: str) -> bytes:
    """Derive a valid Fernet key from a seed string."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class TokenCrypto:
    """Encrypt/decrypt token dictionaries for database storage."""

    def __init__(self) -> None:
        settings = get_settings()
        raw_key = settings.token_encryption_key.strip()

        if raw_key:
            try:
                self._fernet = Fernet(raw_key.encode("utf-8"))
            except Exception as exc:
                raise ValueError("Invalid TOKEN_ENCRYPTION_KEY for Fernet") from exc
        else:
            logger.warning(
                "TOKEN_ENCRYPTION_KEY not set. Falling back to derived key from SESSION_SECRET_KEY."
            )
            derived_key = _derive_fernet_key(settings.session_secret_key)
            self._fernet = Fernet(derived_key)

    def encrypt_token(self, token_data: Dict[str, Any]) -> str:
        """Encrypt a token dictionary into a storable string."""
        payload = json.dumps(token_data).encode("utf-8")
        return self._fernet.encrypt(payload).decode("utf-8")

    def encrypt_text(self, value: str) -> str:
        """Encrypt a plain string value."""
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_token(self, encrypted_payload: str) -> Dict[str, Any]:
        """Decrypt a stored token payload back into a dictionary."""
        try:
            decrypted = self._fernet.decrypt(encrypted_payload.encode("utf-8"))
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt Yahoo token payload") from exc

        try:
            return json.loads(decrypted.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Decrypted token payload is not valid JSON") from exc

    def decrypt_text(self, encrypted_payload: str) -> str:
        """Decrypt a stored encrypted string."""
        try:
            decrypted = self._fernet.decrypt(encrypted_payload.encode("utf-8"))
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt text payload") from exc
        return decrypted.decode("utf-8")


_token_crypto: Optional[TokenCrypto] = None


def get_token_crypto() -> TokenCrypto:
    """Get or create the token encryption helper singleton."""
    global _token_crypto
    if _token_crypto is None:
        _token_crypto = TokenCrypto()
    return _token_crypto
