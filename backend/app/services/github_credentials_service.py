"""Runtime GitHub App credential management.

Persists credentials to data/github_credentials.json and hot-reloads the
settings singleton so every subsequent request sees updated values without
a server restart.
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

    Called once at startup before first request.
    """
    if not _CREDS_FILE.exists():
        return
    try:
        data = json.loads(_CREDS_FILE.read_text())
        if cid := data.get("client_id"):
            settings.GITHUB_APP_CLIENT_ID = cid
        if sec := data.get("client_secret"):
            settings.GITHUB_APP_CLIENT_SECRET = sec
        logger.info("GitHub credentials loaded from %s", _CREDS_FILE)
    except Exception as e:
        logger.warning("Failed to load GitHub credentials file: %s", e)


def save_credentials(client_id: str, client_secret: str) -> None:
    """Persist credentials to disk atomically and hot-reload settings singleton.

    Uses a temp-file + os.replace() pattern so that a crash or SIGKILL mid-write
    can never leave a partially-written (corrupted) credentials file.
    """
    _CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"client_id": client_id, "client_secret": client_secret})
    tmp_fd, tmp_path = tempfile.mkstemp(dir=_CREDS_FILE.parent, prefix=".tmp_creds_")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.write(data)
        os.replace(tmp_path, _CREDS_FILE)
    except Exception:
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
