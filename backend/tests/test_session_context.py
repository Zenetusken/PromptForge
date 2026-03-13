"""Tests for SessionContext serialization and compaction."""

import json
import pytest
from app.services.session_context import (
    SessionContext,
    MAX_REFINEMENT_TURNS,
    MAX_SESSION_CONTEXT_BYTES,
    needs_compaction,
)


class TestSessionContext:
    def test_default_values(self):
        ctx = SessionContext()
        assert ctx.session_id is None
        assert ctx.message_history is None
        assert ctx.turn_count == 0

    def test_serialization_roundtrip(self):
        ctx = SessionContext(
            session_id="test-123",
            provider_type="claude_cli",
            turn_count=3,
        )
        data = ctx.to_dict()
        restored = SessionContext.from_dict(data)
        assert restored.session_id == "test-123"
        assert restored.turn_count == 3

    def test_api_session_with_history(self):
        ctx = SessionContext(
            provider_type="anthropic_api",
            message_history=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
            turn_count=1,
        )
        data = ctx.to_dict()
        assert len(data["message_history"]) == 2


class TestNeedsCompaction:
    def test_no_compaction_below_thresholds(self):
        ctx = SessionContext(turn_count=3, message_history=[{"role": "user", "content": "short"}])
        assert needs_compaction(ctx) is False

    def test_compaction_on_turn_count(self):
        ctx = SessionContext(turn_count=MAX_REFINEMENT_TURNS + 1, message_history=[])
        assert needs_compaction(ctx) is True

    def test_compaction_on_byte_size(self):
        big_history = [{"role": "user", "content": "x" * 100_000}] * 5
        ctx = SessionContext(turn_count=2, message_history=big_history)
        assert needs_compaction(ctx) is True
