"""Tests for MCP tool DB persistence (Tasks 14-15)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch


def _make_session_mock():
    """Return an AsyncMock that works as an async context manager session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.merge = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


# ── Task 14 tests ─────────────────────────────────────────────────────────────

def test_accumulate_event_analysis():
    """_accumulate_event maps analysis event fields onto the ORM object."""
    from app.mcp_server import _accumulate_event

    opt = MagicMock()
    _accumulate_event(opt, "analysis", {
        "task_type": "coding",
        "complexity": "medium",
        "weaknesses": ["unclear scope"],
        "strengths": ["concise"],
        "model": "claude-opus-4-6",
    })

    assert opt.task_type == "coding"
    assert opt.model_analyze == "claude-opus-4-6"
    assert opt.weaknesses == json.dumps(["unclear scope"])
    assert opt.strengths == json.dumps(["concise"])
    assert opt.complexity == "medium"


def test_accumulate_event_codebase_context():
    """_accumulate_event maps codebase_context event fields onto the ORM object."""
    from app.mcp_server import _accumulate_event

    opt = MagicMock()
    _accumulate_event(opt, "codebase_context", {"model": "claude-opus-4-6"})
    assert opt.model_explore == "claude-opus-4-6"


def test_accumulate_event_strategy():
    """_accumulate_event maps strategy event fields onto the ORM object."""
    from app.mcp_server import _accumulate_event

    opt = MagicMock()
    _accumulate_event(opt, "strategy", {
        "primary_framework": "CO-STAR",
        "secondary_frameworks": ["RISEN"],
        "approach_notes": "use context",
        "rationale": "best fit",
        "strategy_source": "selector",
        "model": "claude-opus-4-6",
    })
    assert opt.primary_framework == "CO-STAR"
    assert opt.secondary_frameworks == json.dumps(["RISEN"])
    assert opt.model_strategy == "claude-opus-4-6"


def test_accumulate_event_optimization():
    """_accumulate_event maps optimization event fields onto the ORM object."""
    from app.mcp_server import _accumulate_event

    opt = MagicMock()
    _accumulate_event(opt, "optimization", {
        "optimized_prompt": "better prompt",
        "changes_made": ["added context"],
        "framework_applied": "CO-STAR",
        "optimization_notes": "improved clarity",
        "model": "claude-opus-4-6",
    })
    assert opt.optimized_prompt == "better prompt"
    assert opt.changes_made == json.dumps(["added context"])
    assert opt.model_optimize == "claude-opus-4-6"


def test_accumulate_event_validation():
    """_accumulate_event maps validation event fields onto the ORM object."""
    from app.mcp_server import _accumulate_event

    opt = MagicMock()
    _accumulate_event(opt, "validation", {
        "scores": {
            "clarity_score": 8,
            "specificity_score": 7,
            "structure_score": 9,
            "faithfulness_score": 8,
            "conciseness_score": 7,
            "overall_score": 8,
        },
        "is_improvement": True,
        "verdict": "improved",
        "issues": ["minor verbosity"],
        "model": "claude-opus-4-6",
    })
    assert opt.overall_score == 8
    assert opt.is_improvement is True
    assert opt.issues == json.dumps(["minor verbosity"])
    assert opt.model_validate == "claude-opus-4-6"


async def test_run_and_persist_commits_twice():
    """_run_and_persist creates and finalises the Optimization — commits exactly twice."""
    from app.mcp_server import _run_and_persist

    cm, session = _make_session_mock()

    async def _fake_pipeline(**kwargs):
        yield "analysis", {"task_type": "coding", "model": "test-model"}

    mock_provider = MagicMock()
    mock_provider.name = "test-provider"

    with (
        patch("app.mcp_server.async_session", return_value=cm),
        patch("app.services.pipeline.run_pipeline", side_effect=_fake_pipeline),
    ):
        results, opt = await _run_and_persist(
            mock_provider,
            "test prompt",
            opt_id="test-id-001",
        )

    assert session.commit.call_count == 2
    session.merge.assert_called_once()


# ── Task 15 tests ─────────────────────────────────────────────────────────────

async def test_run_and_persist_sets_retry_of():
    """_run_and_persist passes retry_of through to the Optimization constructor."""
    from app.mcp_server import _run_and_persist

    cm, session = _make_session_mock()

    async def _fake_pipeline(**kwargs):
        yield "analysis", {"task_type": "coding", "model": "test-model"}
        return

    mock_provider = MagicMock()
    mock_provider.name = "test-provider"

    with (
        patch("app.mcp_server.async_session", return_value=cm),
        patch("app.services.pipeline.run_pipeline", side_effect=_fake_pipeline),
        patch("app.mcp_server.Optimization") as MockOpt,
    ):
        MockOpt.return_value = MagicMock()
        await _run_and_persist(
            mock_provider,
            "test prompt",
            opt_id="new-id-002",
            retry_of="orig-id",
        )

    MockOpt.assert_called_once()
    _, kwargs = MockOpt.call_args
    assert kwargs.get("retry_of") == "orig-id"
