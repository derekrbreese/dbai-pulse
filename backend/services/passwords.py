"""
Password hashing helpers for local account authentication.
"""

import base64
import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 16
HASH_BYTES = 32
HASH_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=HASH_BYTES,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("utf-8")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("utf-8")
    return f"{HASH_PREFIX}${PBKDF2_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify plaintext password against stored PBKDF2 hash string."""
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = encoded_hash.split("$", 3)
        if algorithm != HASH_PREFIX:
            return False

        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("utf-8"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("utf-8"))
    except (ValueError, TypeError):
        return False

    computed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected),
    )
    return hmac.compare_digest(computed, expected)
