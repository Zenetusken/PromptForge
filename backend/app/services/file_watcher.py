"""Background file watcher for strategy template hot-reload.

Uses watchfiles.awatch() for OS-native filesystem events (inotify/FSEvents).
Publishes strategy_changed events to the event bus on file add/modify/delete.
On deletion, proactively sanitizes preferences to prevent stale defaults.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from watchfiles import Change, awatch

logger = logging.getLogger(__name__)


def _sanitize_preferences_on_delete(deleted_name: str) -> None:
    """Reset default strategy in preferences if it matches the deleted strategy.

    Runs synchronously (file I/O only, no async needed). Non-fatal — logs
    and swallows all errors so the watcher loop is never interrupted.
    """
    try:
        from app.services.preferences import PreferencesService

        svc = PreferencesService()
        snapshot = svc.load()  # load() already calls _sanitize() internally
        current_default = svc.get("defaults.strategy", snapshot)
        if current_default == deleted_name:
            # The sanitize in load() won't catch this because the file is
            # already deleted by the time the watcher fires — _discover_strategies()
            # won't include it. But load() writes back the sanitized version,
            # so calling load() is sufficient: _sanitize() sees the strategy
            # is not in _discover_strategies() and resets to "auto".
            logger.info(
                "Default strategy '%s' was deleted — preferences reset to fallback",
                deleted_name,
            )
    except Exception as exc:
        logger.debug("Preferences sanitization on delete failed: %s", exc)


async def watch_strategy_files(strategies_dir: Path) -> None:
    """Watch strategies directory and publish changes to event bus.

    Runs as a long-lived background task. Cancellation-safe.
    Falls back to polling if native watching fails.
    On deletion, also sanitizes persisted preferences.
    """
    from app.services.event_bus import event_bus

    if not strategies_dir.is_dir():
        logger.info(
            "Strategies directory %s does not exist — file watcher not started",
            strategies_dir,
        )
        return

    logger.info("Strategy file watcher started: %s", strategies_dir)

    _action_map = {
        Change.added: "created",
        Change.modified: "modified",
        Change.deleted: "deleted",
    }

    # Use polling mode — native inotify can conflict with uvicorn's
    # own watchfiles reloader when both watch overlapping paths.
    # Polling at 1s is imperceptible for human-initiated file edits.
    while True:
        try:
            async for changes in awatch(
                strategies_dir,
                debounce=500,
                force_polling=True,
                poll_delay_ms=1000,
            ):
                for change_type, path_str in changes:
                    path = Path(path_str)
                    if path.suffix != ".md":
                        continue

                    action = _action_map.get(change_type)
                    if not action:
                        continue

                    name = path.stem
                    logger.info("Strategy file %s: %s", action, name)

                    # Sanitize preferences before publishing — ensures
                    # the default strategy is valid by the time the
                    # frontend re-fetches preferences.
                    if action == "deleted":
                        _sanitize_preferences_on_delete(name)

                    event_bus.publish("strategy_changed", {
                        "action": action,
                        "name": name,
                        "timestamp": time.time(),
                    })

        except asyncio.CancelledError:
            logger.info("Strategy file watcher stopped")
            return
        except Exception as exc:
            logger.error("Strategy file watcher error: %s", exc)
            await asyncio.sleep(5)


async def watch_seed_agent_files(agents_dir: Path) -> None:
    """Watch seed agent .md files for changes and publish events."""
    from app.services.event_bus import event_bus

    if not agents_dir.is_dir():
        logger.info(
            "Seed agents directory %s does not exist — file watcher not started",
            agents_dir,
        )
        return

    logger.info("Watching seed agent files in %s", agents_dir)
    while True:
        try:
            async for changes in awatch(
                agents_dir,
                debounce=500,
                force_polling=True,
                poll_delay_ms=1000,
            ):
                for change_type, path_str in changes:
                    if Path(path_str).suffix != ".md":
                        continue
                    stem = Path(path_str).stem
                    action = {1: "created", 2: "modified", 3: "deleted"}.get(
                        change_type, "unknown"
                    )
                    logger.info("Seed agent %s: %s", action, stem)
                    event_bus.publish("agent_changed", {
                        "action": action,
                        "name": stem,
                        "timestamp": time.time(),
                    })
        except asyncio.CancelledError:
            logger.info("Seed agent file watcher stopped")
            return
        except Exception as exc:
            logger.error("Seed agent file watcher error: %s", exc)
            await asyncio.sleep(5)
