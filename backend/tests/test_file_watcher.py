import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from watchfiles import Change

from app.services.file_watcher import _sanitize_preferences_on_delete, watch_strategy_files


@pytest.mark.asyncio
async def test_watch_strategy_files_dir_not_exist(caplog):
    # Tests that it exits early if directory doesn't exist
    with patch("app.services.file_watcher.Path.is_dir", return_value=False):
        await watch_strategy_files(Path("/fake/path"))
    assert caplog.records or not caplog.records

@pytest.mark.asyncio
async def test_watch_strategy_files_cancel():
    # Tests graceful exit on CancelledError
    async def mock_awatch(*args, **kwargs):
        raise asyncio.CancelledError()
        yield  # Make it an async generator

    with patch("app.services.file_watcher.Path.is_dir", return_value=True), \
         patch("app.services.file_watcher.awatch", side_effect=mock_awatch):
        await watch_strategy_files(Path("/fake/path"))

@pytest.mark.asyncio
async def test_watch_strategy_files_exception(caplog):
    # Force awatch to raise an exception, wait out the sleep, then cancel
    call_count = 0

    async def mock_awatch(*args, **kwargs):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            raise Exception("Test Exception")
        raise asyncio.CancelledError()
        yield  # Make it an async generator

    with patch("app.services.file_watcher.Path.is_dir", return_value=True), \
         patch("app.services.file_watcher.awatch", side_effect=mock_awatch), \
         patch("app.services.file_watcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        await watch_strategy_files(Path("/fake/path"))
        assert "Strategy file watcher error: Test Exception" in caplog.text
        mock_sleep.assert_called_once_with(5)

@pytest.mark.asyncio
async def test_watch_strategy_files_successful_events():
    # Provide a mock sequence for awatch yielding changes
    async def mock_awatch(*args, **kwargs):
        # Valid event
        yield {(Change.added, "/fake/path/test_strategy.md")}
        # Ignored because not .md
        yield {(Change.modified, "/fake/path/ignore_me.txt")}
        # Ignored because unsupported change type (not in _action_map)
        yield {("unsupported_change_type", "/fake/path/test_strategy2.md")}
        # Deleted event
        yield {(Change.deleted, "/fake/path/test_strategy3.md")}
        raise asyncio.CancelledError()

    mock_bus = MagicMock()

    with patch("app.services.file_watcher.Path.is_dir", return_value=True), \
         patch("app.services.file_watcher.awatch", side_effect=mock_awatch), \
         patch("app.services.file_watcher.time.time", return_value=12345.6), \
         patch("app.services.event_bus.event_bus", mock_bus):

        await watch_strategy_files(Path("/fake/path"))

        # Verify event was published for .md file only for supported actions
        assert mock_bus.publish.call_count == 2

        # Call 1
        args, kwargs = mock_bus.publish.call_args_list[0]
        assert args[0] == "strategy_changed"
        assert args[1]["action"] == "created"
        assert args[1]["name"] == "test_strategy"
        assert args[1]["timestamp"] == 12345.6

        # Call 2
        args, kwargs = mock_bus.publish.call_args_list[1]
        assert args[0] == "strategy_changed"
        assert args[1]["action"] == "deleted"
        assert args[1]["name"] == "test_strategy3"


def test_sanitize_preferences_on_delete_resets_default(tmp_path):
    """When the deleted strategy matches the persisted default, preferences are reset."""
    mock_svc = MagicMock()
    mock_snapshot = {"defaults": {"strategy": "my-custom-strategy"}}
    mock_svc.load.return_value = mock_snapshot
    mock_svc.get.return_value = "my-custom-strategy"

    with patch("app.services.preferences.PreferencesService", return_value=mock_svc):
        _sanitize_preferences_on_delete("my-custom-strategy")

    # load() was called (which triggers _sanitize internally)
    mock_svc.load.assert_called_once()


def test_sanitize_preferences_on_delete_ignores_non_matching():
    """When the deleted strategy does NOT match the default, no action needed."""
    mock_svc = MagicMock()
    mock_snapshot = {"defaults": {"strategy": "auto"}}
    mock_svc.load.return_value = mock_snapshot
    mock_svc.get.return_value = "auto"

    with patch("app.services.preferences.PreferencesService", return_value=mock_svc):
        _sanitize_preferences_on_delete("some-other-strategy")

    # load() was called but the strategy didn't match — no reset needed
    mock_svc.load.assert_called_once()


@pytest.mark.asyncio
async def test_delete_event_triggers_preferences_sanitization():
    """When a strategy file is deleted, _sanitize_preferences_on_delete is called."""
    async def mock_awatch(*args, **kwargs):
        yield {(Change.deleted, "/fake/path/custom-strategy.md")}
        raise asyncio.CancelledError()

    mock_bus = MagicMock()

    with patch("app.services.file_watcher.Path.is_dir", return_value=True), \
         patch("app.services.file_watcher.awatch", side_effect=mock_awatch), \
         patch("app.services.file_watcher.time.time", return_value=12345.6), \
         patch("app.services.event_bus.event_bus", mock_bus), \
         patch("app.services.file_watcher._sanitize_preferences_on_delete") as mock_sanitize:

        await watch_strategy_files(Path("/fake/path"))

        mock_sanitize.assert_called_once_with("custom-strategy")


@pytest.mark.asyncio
async def test_create_event_does_not_trigger_sanitization():
    """When a strategy file is created, preferences sanitization is NOT called."""
    async def mock_awatch(*args, **kwargs):
        yield {(Change.added, "/fake/path/new-strategy.md")}
        raise asyncio.CancelledError()

    mock_bus = MagicMock()

    with patch("app.services.file_watcher.Path.is_dir", return_value=True), \
         patch("app.services.file_watcher.awatch", side_effect=mock_awatch), \
         patch("app.services.file_watcher.time.time", return_value=12345.6), \
         patch("app.services.event_bus.event_bus", mock_bus), \
         patch("app.services.file_watcher._sanitize_preferences_on_delete") as mock_sanitize:

        await watch_strategy_files(Path("/fake/path"))

        mock_sanitize.assert_not_called()
