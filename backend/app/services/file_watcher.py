"""Background file watcher for strategy template hot-reload.

Uses watchfiles.awatch() for OS-native filesystem events (inotify/FSEvents).
Publishes strategy_changed events to the event bus on file add/modify/delete.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from watchfiles import Change, awatch

logger = logging.getLogger(__name__)


async def watch_strategy_files(strategies_dir: Path) -> None:
    """Watch strategies directory and publish changes to event bus.

    Runs as a long-lived background task. Cancellation-safe.
    Falls back to polling if native watching fails.
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

    force_polling = False

    while True:
        try:
            async for changes in awatch(
                strategies_dir,
                debounce=500,
                force_polling=force_polling,
                poll_delay_ms=2000 if force_polling else 1600,
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

                    event_bus.publish("strategy_changed", {
                        "action": action,
                        "name": name,
                        "timestamp": time.time(),
                    })

        except asyncio.CancelledError:
            logger.info("Strategy file watcher stopped")
            return
        except Exception as exc:
            if not force_polling:
                logger.warning(
                    "Native file watching failed (%s), falling back to polling", exc,
                )
                force_polling = True
            else:
                logger.error("Strategy file watcher error: %s", exc)
                await asyncio.sleep(5)
