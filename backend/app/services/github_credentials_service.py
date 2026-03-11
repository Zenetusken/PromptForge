"""Runtime GitHub App credential management.

Persists credentials to data/github_credentials.json (Fernet-encrypted) and
hot-reloads the settings singleton so every subsequent request sees updated
values without a server restart.

Backward-compatible: on load, plaintext JSON files (legacy format) are
transparently migrated to the encrypted format on next save or immediately
when detected.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)
_CREDS_FILE = Path("data/github_credentials.json")


def load_credentials_from_file() -> None:
    """Load saved credentials and apply to settings singleton.

    Tries Fernet decryption first (new encrypted format).  Falls back to
    plaintext JSON (legacy format) and auto-migrates to encrypted on success.

    Called once at startup before first request.
    """
    if not _CREDS_FILE.exists():
        return
    try:
        raw = _CREDS_FILE.read_bytes()

        # Try decrypting first (new encrypted format)
        data = None
        try:
            from app.services.github_service import decrypt_token

            decrypted = decrypt_token(raw)
            data = json.loads(decrypted)
            logger.debug("GitHub credentials loaded from encrypted format")
        except Exception:
            # Fall back to plaintext (legacy format)
            try:
                data = json.loads(raw.decode())
                logger.info(
                    "GitHub credentials loaded from plaintext format — "
                    "will migrate to encrypted on next save"
                )
                # Auto-migrate: re-save as encrypted
                if data.get("client_id") and data.get("client_secret"):
                    try:
                        save_credentials(data["client_id"], data["client_secret"])
                        logger.info("GitHub credentials auto-migrated to encrypted format")
                    except Exception as me:
                        logger.warning("Auto-migration to encrypted format failed: %s", me)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning("GitHub credentials file is neither encrypted nor valid JSON")
                return

        if data:
            if cid := data.get("client_id"):
                settings.GITHUB_APP_CLIENT_ID = cid
            if sec := data.get("client_secret"):
                settings.GITHUB_APP_CLIENT_SECRET = sec
            logger.info("GitHub credentials loaded from %s", _CREDS_FILE)
    except Exception as e:
        logger.warning("Failed to load GitHub credentials file: %s", e)


def save_credentials(client_id: str, client_secret: str) -> None:
    """Persist Fernet-encrypted credentials to disk atomically, then hot-reload.

    Uses a temp-file + os.replace() pattern so that a crash or SIGKILL mid-write
    can never leave a partially-written (corrupted) credentials file.
    """
    from app.services.github_service import encrypt_token

    _CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    plaintext = json.dumps({"client_id": client_id, "client_secret": client_secret})
    encrypted = encrypt_token(plaintext)

    tmp_fd, tmp_path = tempfile.mkstemp(dir=_CREDS_FILE.parent, prefix=".tmp_creds_")
    try:
        os.write(tmp_fd, encrypted)
        os.close(tmp_fd)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, _CREDS_FILE)
    except Exception:
        try:
            os.close(tmp_fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    settings.GITHUB_APP_CLIENT_ID = client_id
    settings.GITHUB_APP_CLIENT_SECRET = client_secret
    logger.info("GitHub credentials updated (client_id=%s...)", client_id[:8])


def get_config_status() -> dict:
    """Return masked credential status for the API response."""
    cid = settings.GITHUB_APP_CLIENT_ID or ""
    has_secret = bool(settings.GITHUB_APP_CLIENT_SECRET)
    configured = bool(cid and has_secret)
    masked = (cid[:8] + "••••" + cid[-4:]) if len(cid) > 12 else ("••••" if cid else "")
    return {
        "configured": configured,
        "client_id_masked": masked,
        "has_secret": has_secret,
    }
