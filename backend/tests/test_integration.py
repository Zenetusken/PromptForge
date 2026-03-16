"""End-to-end integration test: optimize -> refine -> feedback -> history."""

import json

from app.schemas.pipeline_contracts import (
    AnalysisResult,
    DimensionScores,
    OptimizationResult,
    ScoreResult,
)
from app.services.refinement_service import SuggestionsOutput


def _parse_sse_events(response_text: str) -> list[dict]:
    """Extract parsed JSON events from an SSE response body."""
    events = []
    for line in response_text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


class TestEndToEndFlow:
    """Full pipeline flow using mocked provider but real router -> service -> DB path."""

    async def test_optimize_refine_feedback_history(
        self, app_client, mock_provider, db_session,
    ):
        # --- Step 1: Optimize ---
        mock_provider.complete_parsed.side_effect = [
            AnalysisResult(
                task_type="coding",
                weaknesses=["vague"],
                strengths=["concise"],
                selected_strategy="chain-of-thought",
                strategy_rationale="reasoning helps",
                confidence=0.9,
            ),
            OptimizationResult(
                optimized_prompt=(
                    "Write a Python function sort_list(items: list) -> list "
                    "that returns a new sorted list."
                ),
                changes_summary="Added language, function signature, return type.",
                strategy_used="chain-of-thought",
            ),
            ScoreResult(
                prompt_a_scores=DimensionScores(
                    clarity=4.0, specificity=3.0, structure=3.0,
                    faithfulness=5.0, conciseness=7.0,
                ),
                prompt_b_scores=DimensionScores(
                    clarity=8.0, specificity=8.0, structure=7.0,
                    faithfulness=9.0, conciseness=6.0,
                ),
            ),
        ]

        resp = await app_client.post(
            "/api/optimize",
            json={"prompt": "Write a function that sorts a list"},
        )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)

        # Verify the optimization_complete event exists and extract the ID
        complete_event = next(
            (e for e in events if e.get("event") == "optimization_complete"),
            None,
        )
        assert complete_event is not None, (
            f"No optimization_complete event. Events: {[e.get('event') for e in events]}"
        )

        optimization_id = complete_event["id"]
        assert optimization_id

        # Verify start event was emitted with a trace_id
        start_event = next(
            (e for e in events if e.get("event") == "optimization_start"),
            None,
        )
        assert start_event is not None
        assert start_event.get("trace_id")

        # --- Step 2: Verify history shows the optimization ---
        resp = await app_client.get("/api/history")
        assert resp.status_code == 200
        history = resp.json()
        assert history["total"] >= 1
        assert any(item["id"] == optimization_id for item in history["items"])

        # --- Step 3: Submit feedback ---
        resp = await app_client.post("/api/feedback", json={
            "optimization_id": optimization_id,
            "rating": "thumbs_up",
            "comment": "Great optimization!",
        })
        assert resp.status_code == 200
        fb = resp.json()
        assert fb["rating"] == "thumbs_up"
        assert fb["optimization_id"] == optimization_id

        # --- Step 4: Verify feedback shows up ---
        resp = await app_client.get(
            f"/api/feedback?optimization_id={optimization_id}",
        )
        assert resp.status_code == 200
        fb_data = resp.json()
        assert fb_data["aggregation"]["thumbs_up"] == 1
        assert fb_data["aggregation"]["total"] == 1
        assert len(fb_data["items"]) == 1

        # --- Step 5: Refine ---
        mock_provider.complete_parsed.side_effect = [
            # analyze
            AnalysisResult(
                task_type="coding",
                weaknesses=["no error handling"],
                strengths=["clear signature"],
                selected_strategy="chain-of-thought",
                strategy_rationale="reasoning",
                confidence=0.85,
            ),
            # refine (uses OptimizationResult contract)
            OptimizationResult(
                optimized_prompt=(
                    "Write a Python function sort_list(items: list) -> list "
                    "that returns a new sorted list. Raise TypeError if items "
                    "is not a list."
                ),
                changes_summary="Added error handling.",
                strategy_used="chain-of-thought",
            ),
            # score
            ScoreResult(
                prompt_a_scores=DimensionScores(
                    clarity=4.0, specificity=3.0, structure=3.0,
                    faithfulness=5.0, conciseness=7.0,
                ),
                prompt_b_scores=DimensionScores(
                    clarity=8.5, specificity=9.0, structure=7.5,
                    faithfulness=9.0, conciseness=6.0,
                ),
            ),
            # suggest
            SuggestionsOutput(suggestions=[
                {"text": "Add return type examples", "source": "score-driven"},
                {"text": "Specify sorting algorithm", "source": "analysis-driven"},
                {"text": "Add docstring requirement", "source": "strategic"},
            ]),
        ]

        resp = await app_client.post("/api/refine", json={
            "optimization_id": optimization_id,
            "refinement_request": "Add error handling for invalid input types",
        })
        assert resp.status_code == 200
        # Verify SSE events were streamed
        assert "data:" in resp.text

        refine_events = _parse_sse_events(resp.text)
        refine_event_types = [e.get("event") for e in refine_events]
        # Refinement pipeline should emit analyze, refine, score, and suggest phases
        assert "status" in refine_event_types
        assert "prompt_preview" in refine_event_types
        assert "score_card" in refine_event_types
        assert "suggestions" in refine_event_types

        # --- Step 6: Get refinement versions ---
        resp = await app_client.get(
            f"/api/refine/{optimization_id}/versions",
        )
        assert resp.status_code == 200
        versions = resp.json()
        assert versions["optimization_id"] == optimization_id
        # Should have initial turn (v1) + refinement turn (v2)
        assert len(versions["versions"]) >= 2

        # --- Step 7: Health check includes metrics ---
        resp = await app_client.get("/api/health")
        assert resp.status_code == 200
        health = resp.json()
        assert "score_health" in health
        assert "provider" in health
        assert health["provider"] == "mock"
