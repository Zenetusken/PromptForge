"""Tests for TraceLogger — TDD: write tests first, then implement."""

import json
from pathlib import Path

import pytest

from app.services.trace_logger import TraceLogger


def test_write_and_read(tmp_path: Path) -> None:
    """Write one phase entry, read it back, verify all fields are present."""
    logger = TraceLogger(traces_dir=tmp_path)

    logger.log_phase(
        trace_id="trace-001",
        phase="analyze",
        duration_ms=123,
        tokens_in=50,
        tokens_out=200,
        model="claude-haiku-4-5",
        provider="anthropic",
        result={"task_type": "generation"},
    )

    entries = logger.read_trace("trace-001")

    assert len(entries) == 1
    entry = entries[0]
    assert entry["trace_id"] == "trace-001"
    assert entry["phase"] == "analyze"
    assert entry["duration_ms"] == 123
    assert entry["tokens_in"] == 50
    assert entry["tokens_out"] == 200
    assert entry["model"] == "claude-haiku-4-5"
    assert entry["provider"] == "anthropic"
    assert entry["result"] == {"task_type": "generation"}
    assert "timestamp" in entry


def test_multiple_phases(tmp_path: Path) -> None:
    """Write 3 phases for the same trace_id, read all back, verify order."""
    logger = TraceLogger(traces_dir=tmp_path)
    trace_id = "trace-multi"

    phases = ["analyze", "strategy", "optimize"]
    for i, phase in enumerate(phases):
        logger.log_phase(
            trace_id=trace_id,
            phase=phase,
            duration_ms=(i + 1) * 100,
            tokens_in=10 * (i + 1),
            tokens_out=20 * (i + 1),
            model="claude-haiku-4-5",
            provider="anthropic",
        )

    entries = logger.read_trace(trace_id)

    assert len(entries) == 3
    assert [e["phase"] for e in entries] == ["analyze", "strategy", "optimize"]
    assert entries[0]["duration_ms"] == 100
    assert entries[1]["duration_ms"] == 200
    assert entries[2]["duration_ms"] == 300


def test_read_nonexistent_trace(tmp_path: Path) -> None:
    """read_trace returns [] for a trace_id that was never written."""
    logger = TraceLogger(traces_dir=tmp_path)

    # Write an unrelated trace so the directory and a file exist
    logger.log_phase(
        trace_id="other-trace",
        phase="analyze",
        duration_ms=50,
        tokens_in=5,
        tokens_out=10,
        model="claude-haiku-4-5",
        provider="anthropic",
    )

    result = logger.read_trace("nonexistent-trace-id")
    assert result == []


def test_jsonl_format(tmp_path: Path) -> None:
    """Verify the raw file contains valid JSONL — one JSON object per line."""
    logger = TraceLogger(traces_dir=tmp_path)

    for i in range(3):
        logger.log_phase(
            trace_id=f"trace-{i}",
            phase="validate",
            duration_ms=i * 10,
            tokens_in=i,
            tokens_out=i * 2,
            model="claude-haiku-4-5",
            provider="cli",
        )

    # Find the written file(s)
    jsonl_files = list(tmp_path.glob("traces-*.jsonl"))
    assert len(jsonl_files) >= 1, "Expected at least one .jsonl file to be created"

    all_lines: list[str] = []
    for f in jsonl_files:
        all_lines.extend(f.read_text().splitlines())

    # Every non-empty line must be valid JSON
    parsed = [json.loads(line) for line in all_lines if line.strip()]
    assert len(parsed) == 3

    # Each object must have the required fields
    required_fields = {"trace_id", "phase", "duration_ms", "tokens_in", "tokens_out", "model", "provider", "timestamp"}
    for obj in parsed:
        assert required_fields.issubset(obj.keys()), f"Missing fields in: {obj}"
