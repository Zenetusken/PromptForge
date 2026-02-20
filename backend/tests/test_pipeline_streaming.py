"""Tests for pipeline streaming helpers: _run_with_progress_stream and _stream_stage."""

import asyncio
from dataclasses import dataclass

import pytest

from app.constants import StageConfig
from app.services.pipeline import StageResult, _run_with_progress_stream, _stream_stage


def _test_stage(interval: float = 0.05) -> StageConfig:
    """Create a minimal StageConfig for testing."""
    return StageConfig(
        name="test",
        stage_label="testing",
        stage_message="Running tests",
        event_name="test_result",
        progress_interval=interval,
        progress_messages=["Working on it...", "Still going..."],
        initial_messages=[("Starting...", 0.1)],
    )


class TestRunWithProgressStream:
    @pytest.mark.asyncio
    async def test_fast_coroutine_yields_only_stage_result(self):
        """A coroutine that completes before any timeout yields no progress events."""

        async def fast():
            return "done"

        events = []
        async for event in _run_with_progress_stream(fast(), _test_stage()):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], StageResult)
        assert events[0].value == "done"

    @pytest.mark.asyncio
    async def test_slow_coroutine_yields_progress_events(self):
        """A coroutine that takes longer than the interval yields progress SSE events."""

        async def slow():
            await asyncio.sleep(0.2)
            return "done"

        events = []
        async for event in _run_with_progress_stream(slow(), _test_stage(interval=0.05)):
            events.append(event)

        # Should have some string SSE events before the final StageResult
        sse_events = [e for e in events if isinstance(e, str)]
        assert len(sse_events) >= 1
        assert "step_progress" in sse_events[0]
        assert "Working on it..." in sse_events[0]

        # Last event should be the StageResult
        assert isinstance(events[-1], StageResult)
        assert events[-1].value == "done"

    @pytest.mark.asyncio
    async def test_progress_messages_cycle_through(self):
        """Multiple timeouts cycle through the progress messages list."""

        async def slow():
            await asyncio.sleep(0.25)
            return "done"

        events = []
        async for event in _run_with_progress_stream(slow(), _test_stage(interval=0.05)):
            events.append(event)

        sse_events = [e for e in events if isinstance(e, str)]
        # Should emit at least 2 progress messages
        assert len(sse_events) >= 2
        assert "Working on it..." in sse_events[0]
        assert "Still going..." in sse_events[1]

    @pytest.mark.asyncio
    async def test_coroutine_error_propagates(self):
        """If the coroutine raises, the error propagates through the generator."""

        async def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            async for _ in _run_with_progress_stream(failing(), _test_stage()):
                pass

    @pytest.mark.asyncio
    async def test_format_map_applied_to_messages(self):
        """Format placeholders in progress messages are interpolated."""
        stage = StageConfig(
            name="test",
            stage_label="testing",
            stage_message="Testing {strategy}",
            event_name="test_result",
            progress_interval=0.05,
            progress_messages=["Applying {strategy}..."],
            initial_messages=[],
        )

        async def slow():
            await asyncio.sleep(0.15)
            return "done"

        events = []
        async for event in _run_with_progress_stream(slow(), stage, {"strategy": "persona-assignment"}):
            events.append(event)

        sse_events = [e for e in events if isinstance(e, str)]
        assert len(sse_events) >= 1
        assert "persona-assignment" in sse_events[0]


    @pytest.mark.asyncio
    async def test_format_map_applied_to_stage_message(self):
        """Format placeholders in stage_message are interpolated in the start event."""
        stage = StageConfig(
            name="test",
            stage_label="testing",
            stage_message="Optimizing with {strategy}",
            event_name="test_result",
            progress_interval=0.05,
            progress_messages=[],
            initial_messages=[],
        )

        async def fast():
            return "done"

        events = []
        async for event in _run_with_progress_stream(fast(), stage, {"strategy": "co-star"}):
            events.append(event)

        # _run_with_progress_stream doesn't emit the stage_message directly,
        # but _stream_stage does. Verify via _stream_stage below.
        assert isinstance(events[-1], StageResult)


class TestStreamStageFormatMap:
    @pytest.mark.asyncio
    async def test_stage_start_event_has_format_placeholders_filled(self):
        """The stage start event should have {strategy} replaced in stage_message."""
        stage = StageConfig(
            name="optimize",
            stage_label="optimizing",
            stage_message="Applying {strategy} framework",
            event_name="optimization",
            progress_interval=0.5,
            progress_messages=["Rewriting with {strategy}..."],
            initial_messages=[("Starting {strategy}...", 0.1)],
        )

        @dataclass
        class FakeResult:
            optimized_prompt: str

        async def fast():
            return FakeResult(optimized_prompt="done")

        events = []
        async for event in _stream_stage(fast(), stage, {"strategy": "persona-assignment"}):
            events.append(event)

        sse_events = [e for e in events if isinstance(e, str)]
        # Stage start event should contain the interpolated strategy
        stage_start = sse_events[0]
        assert "event: stage" in stage_start
        assert "persona-assignment" in stage_start
        assert "{strategy}" not in stage_start  # No raw placeholder

        # Initial message should also be interpolated
        initial_msg = sse_events[1]
        assert "persona-assignment" in initial_msg
        assert "{strategy}" not in initial_msg


class TestStreamStage:
    @pytest.mark.asyncio
    async def test_emits_stage_start_and_complete(self):
        """_stream_stage emits stage start, initial progress, and complete events."""

        @dataclass
        class FakeResult:
            task_type: str
            complexity: str

        async def fast_dc():
            return FakeResult(task_type="coding", complexity="low")

        events = []
        async for event in _stream_stage(fast_dc(), _test_stage()):
            events.append(event)

        sse_events = [e for e in events if isinstance(e, str)]
        # First SSE: stage start
        assert "event: stage" in sse_events[0]
        assert "testing" in sse_events[0]

        # Should have initial message
        assert "Starting..." in sse_events[1]

        # Last SSE before StageResult: stage complete (event_name = "test_result")
        complete_events = [e for e in sse_events if "test_result" in e]
        assert len(complete_events) == 1
        assert "step_duration_ms" in complete_events[0]

        # Final item: StageResult
        assert isinstance(events[-1], StageResult)

    @pytest.mark.asyncio
    async def test_stage_error_propagates(self):
        """Errors in the coroutine propagate through _stream_stage."""

        async def failing():
            raise RuntimeError("stage failed")

        with pytest.raises(RuntimeError, match="stage failed"):
            async for _ in _stream_stage(failing(), _test_stage()):
                pass
