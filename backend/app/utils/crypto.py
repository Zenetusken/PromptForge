"""Shared cryptographic utilities for Fernet key derivation.

Uses PBKDF2-SHA256 (600K iterations, OWASP 2024) with context-specific
static salts. Includes legacy SHA256 fallback for migration.

See ADR-002 for design rationale.
"""

import base64
import hashlib
import logging
from collections.abc import Callable
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_PBKDF2_ITERATIONS = 600_000


@lru_cache(maxsize=8)
def derive_fernet(secret: str, context: str) -> Fernet:
    """Derive a Fernet instance using PBKDF2-SHA256 with a context-specific salt.

    Args:
        secret: The application SECRET_KEY (high-entropy random).
        context: A unique salt string per credential type (e.g., 'synthesis-github-token-v1').

    Returns:
        A cached Fernet instance. Cached per (secret, context) pair.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=context.encode(),
        iterations=_PBKDF2_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return Fernet(key)


def _derive_legacy_fernet(secret: str) -> Fernet:
    """Legacy SHA256-based Fernet derivation (pre-hardening)."""
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def decrypt_with_migration(
    ciphertext: bytes,
    secret: str,
    context: str,
    persist_fn: Callable[[bytes], None] | None = None,
) -> bytes:
    """Decrypt ciphertext, falling back to legacy KDF and re-encrypting if needed.

    Args:
        ciphertext: The encrypted bytes.
        secret: The application SECRET_KEY.
        context: Fernet context salt for the new KDF.
        persist_fn: Callback to persist re-encrypted ciphertext (called only on migration).

    Returns:
        Decrypted plaintext bytes.

    Raises:
        InvalidToken: If both new and legacy decryption fail.
    """
    new_fernet = derive_fernet(secret, context)
    try:
        return new_fernet.decrypt(ciphertext)
    except InvalidToken:
        pass

    # Fall back to legacy SHA256 key
    legacy_fernet = _derive_legacy_fernet(secret)
    plaintext = legacy_fernet.decrypt(ciphertext)  # raises InvalidToken if both fail

    # Re-encrypt with new KDF and persist
    logger.info("Migrating encrypted credential from legacy SHA256 to PBKDF2 (context=%s)", context)
    new_ciphertext = new_fernet.encrypt(plaintext)
    if persist_fn:
        persist_fn(new_ciphertext)

    return plaintext
