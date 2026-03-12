"""Fernet symmetric encryption for tokens and credentials.

Centralized encryption service used by GitHub token storage,
API key persistence, and GitHub credential management.

Supports key rotation: the primary key (GITHUB_TOKEN_ENCRYPTION_KEY) is
used for encryption; any comma-separated old keys in
GITHUB_TOKEN_ENCRYPTION_KEY_OLD are tried during decryption.
"""

import logging
import os
import threading
from typing import Optional

from cryptography.fernet import Fernet, MultiFernet

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Optional[MultiFernet] = None
_fernet_lock = threading.Lock()


def _get_fernet() -> MultiFernet:
    """Return a MultiFernet instance, creating/loading the key as needed.

    Thread-safe: uses a lock to prevent concurrent first-access from
    generating different keys (race condition).
    """
    global _fernet
    if _fernet is not None:
        return _fernet

    with _fernet_lock:
        # Double-check after acquiring the lock
        if _fernet is not None:
            return _fernet

        key = settings.GITHUB_TOKEN_ENCRYPTION_KEY
        if key:
            primary = Fernet(key.encode() if isinstance(key, str) else key)
            # Build rotation list: primary key first, then any old keys
            fernet_list = [primary]
            old_keys = settings.GITHUB_TOKEN_ENCRYPTION_KEY_OLD
            if old_keys:
                for old_key in old_keys.split(","):
                    old_key = old_key.strip()
                    if old_key:
                        fernet_list.append(Fernet(old_key.encode() if isinstance(old_key, str) else old_key))
            _fernet = MultiFernet(fernet_list)
            return _fernet

        # Auto-generate and persist a key if not configured
        key_path = os.path.join("data", ".github_encryption_key")
        os.makedirs("data", exist_ok=True)
        key_bytes: bytes
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                key_bytes = f.read().strip()
        else:
            key_bytes = Fernet.generate_key()
            # Atomic creation with restricted permissions (owner read/write only)
            fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(fd, key_bytes)
            finally:
                os.close(fd)
            logger.info("Generated new encryption key at %s", key_path)

        _fernet = MultiFernet([Fernet(key_bytes)])
        return _fernet


def encrypt_token(token: str) -> bytes:
    """Encrypt a token string using Fernet symmetric encryption.

    Args:
        token: The plaintext token string.

    Returns:
        The Fernet-encrypted token bytes.
    """
    return _get_fernet().encrypt(token.encode("utf-8"))


def decrypt_token(encrypted: bytes) -> str:
    """Decrypt a Fernet-encrypted token.

    Args:
        encrypted: The Fernet-encrypted token bytes.

    Returns:
        The plaintext token string.
    """
    return _get_fernet().decrypt(encrypted).decode("utf-8")
