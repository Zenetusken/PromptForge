# Compare & Merge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-optimization comparison engine with intelligent merge that combines the best of two optimized prompts into a new entry, guided by deep analytical insights.

**Architecture:** Backend-powered comparison endpoint computes situation classification (REFORGE/STRATEGY/EVOLVED/CROSS), 8 insight categories, and LLM-generated merge directives. Frontend modal with 3 sequential phases: Analyze (read-only assessment) -> Merge (LLM streaming) -> Commit Gate (accept/discard). The merge LLM receives the full comparison intelligence as structured system prompt sections.

**Tech Stack:** Python/FastAPI (backend), Svelte 5 runes (frontend), sentence-transformers embeddings (similarity), SSE streaming (merge), Pydantic (schemas), SQLAlchemy async (DB)

**Spec:** `docs/superpowers/specs/2026-03-14-compare-merge-design.md`

---

## Chunk 1: Backend — Pydantic Models + Comparison Service

### Task 1: Pydantic Response Models

**Files:**
- Create: `backend/app/schemas/compare_models.py`

- [ ] **Step 1: Create Pydantic models for compare response**

```python
"""Pydantic models for the compare and merge endpoints."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ScoreComparison(BaseModel):
    dimensions: list[str]
    a_scores: dict[str, float | None]
    b_scores: dict[str, float | None]
    deltas: dict[str, float | None]
    overall_delta: float | None
    winner: str | None  # "a", "b", or None (tie)
    ceilings: list[str]  # dimensions where both >= 9
    floors: list[str]  # dimensions where both < 5


class StructuralComparison(BaseModel):
    a_input_words: int
    b_input_words: int
    a_output_words: int
    b_output_words: int
    a_expansion: float
    b_expansion: float
    a_complexity: str | None
    b_complexity: str | None


class EfficiencyComparison(BaseModel):
    a_duration_ms: int | None
    b_duration_ms: int | None
    a_tokens: int | None
    b_tokens: int | None
    a_cost: float | None
    b_cost: float | None
    a_score_per_token: float | None
    b_score_per_token: float | None


class StrategyComparison(BaseModel):
    a_framework: str | None
    a_source: str | None
    a_rationale: str | None
    a_guardrails: list[str]
    b_framework: str | None
    b_source: str | None
    b_rationale: str | None
    b_guardrails: list[str]


class ContextComparison(BaseModel):
    a_repo: str | None
    b_repo: str | None
    a_has_codebase: bool
    b_has_codebase: bool
    a_instruction_count: int
    b_instruction_count: int


class ValidationComparison(BaseModel):
    a_verdict: str | None
    b_verdict: str | None
    a_issues: list[str]
    b_issues: list[str]
    a_changes_made: list[str]
    b_changes_made: list[str]
    a_is_improvement: bool | None
    b_is_improvement: bool | None


class AdaptationComparison(BaseModel):
    feedbacks_between: int
    weight_shifts: dict[str, float]
    guardrails_added: list[str]


class CompareGuidance(BaseModel):
    headline: str
    merge_suggestion: str
    strengths_a: list[str]
    strengths_b: list[str]
    persistent_weaknesses: list[str]
    actionable: list[str]
    merge_directives: list[str]


class CompareResponse(BaseModel):
    situation: str  # REFORGE, STRATEGY, EVOLVED, CROSS
    situation_label: str
    insight_headline: str
    modifiers: list[str]
    a: dict  # full optimization record
    b: dict  # full optimization record
    scores: ScoreComparison
    structural: StructuralComparison
    efficiency: EfficiencyComparison
    strategy: StrategyComparison
    context: ContextComparison
    validation: ValidationComparison
    adaptation: AdaptationComparison
    top_insights: list[str]
    cross_patterns: list[str]  # CROSS-only insights; empty for other situations
    a_is_trashed: bool
    b_is_trashed: bool
    guidance: CompareGuidance | None  # None if LLM guidance failed


class MergeAcceptRequest(BaseModel):
    optimization_id_a: str
    optimization_id_b: str
    merged_prompt: str


class MergeAcceptResponse(BaseModel):
    optimization_id: str
    status: str
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/compare_models.py
git commit -m "feat(compare): add Pydantic response models for compare and merge endpoints"
```

---

### Task 2: Comparison Service — Classification + Data Extraction

**Files:**
- Create: `backend/app/services/compare_service.py`
- Reference: `backend/app/services/embedding_service.py` (for `embed_single`, `cosine_similarity`)
- Reference: `backend/app/models/optimization.py` (for field names)

- [ ] **Step 1: Write tests for situation classification**

Create `backend/tests/test_compare_service.py`:

```python
"""Tests for compare_service — classification and data extraction."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.compare_service import classify_situation, compute_comparison


def _mock_opt(
    raw_prompt="test prompt",
    optimized_prompt="optimized test",
    primary_framework="CO-STAR",
    overall_score=8.0,
    clarity_score=8,
    faithfulness_score=7,
    specificity_score=8,
    structure_score=9,
    conciseness_score=7,
    task_type="code_review",
    complexity="basic",
    duration_ms=4000,
    total_input_tokens=1000,
    total_output_tokens=1100,
    estimated_cost_usd=0.008,
    strategy_source="llm",
    strategy_rationale="Context grounding needed",
    active_guardrails=None,
    linked_repo_full_name=None,
    weaknesses=None,
    strengths=None,
    changes_made=None,
    verdict="Strong improvement",
    issues=None,
    stage_durations=None,
    **kwargs,
):
    opt = MagicMock()
    for k, v in locals().items():
        if k not in ("opt", "kwargs"):
            setattr(opt, k, v)
    for k, v in kwargs.items():
        setattr(opt, k, v)
    opt.to_dict = MagicMock(return_value={
        k: v for k, v in locals().items()
        if k not in ("opt", "kwargs") and not k.startswith("_")
    })
    return opt


class TestClassifySituation:
    def test_high_similarity_same_framework_is_reforge(self):
        result = classify_situation(similarity=0.92, fw_a="CO-STAR", fw_b="CO-STAR")
        assert result == "REFORGE"

    def test_high_similarity_different_framework_is_strategy(self):
        result = classify_situation(similarity=0.90, fw_a="CO-STAR", fw_b="RISEN")
        assert result == "STRATEGY"

    def test_moderate_similarity_is_evolved(self):
        result = classify_situation(similarity=0.60, fw_a="CO-STAR", fw_b="CO-STAR")
        assert result == "EVOLVED"

    def test_low_similarity_is_cross(self):
        result = classify_situation(similarity=0.30, fw_a="CO-STAR", fw_b="RISEN")
        assert result == "CROSS"

    def test_boundary_high(self):
        assert classify_situation(0.85, "X", "X") == "REFORGE"
        assert classify_situation(0.84, "X", "X") == "EVOLVED"

    def test_boundary_low(self):
        assert classify_situation(0.45, "X", "X") == "EVOLVED"
        assert classify_situation(0.44, "X", "X") == "CROSS"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd backend && python -m pytest tests/test_compare_service.py -v
```

Expected: ImportError or ModuleNotFoundError

- [ ] **Step 3: Implement classification + data extraction**

Create `backend/app/services/compare_service.py` with:

1. `classify_situation(similarity, fw_a, fw_b) -> str` — pure function, threshold-based
2. `compute_similarity(text_a, text_b) -> float` — uses `embedding_service.embed_single()` with Levenshtein fallback (`1 - edit_distance/max_len`, thresholds: 0.80/0.35)
3. `extract_scores(opt) -> dict` — pulls the 5 score dimensions + overall
4. `extract_structural(opt) -> dict` — word counts, expansion ratio, complexity
5. `extract_efficiency(opt) -> dict` — duration, tokens, cost, score/token
6. `extract_strategy(opt) -> dict` — framework, source, rationale, guardrails
7. `extract_context(opt) -> dict` — repo name, codebase context presence, instruction compliance
8. `extract_validation(opt) -> dict` — verdict, issues list, changes_made, is_improvement
9. `extract_adaptation(a, b) -> AdaptationComparison` — feedback count between timestamps, weight shifts from adaptation_snapshot, guardrail evolution
10. `compute_modifiers(a, b) -> list[str]` — repo_added, repo_changed, adapted, complexity_shift
11. `generate_top_insights(scores, structural, efficiency, strategy, context, validation, adaptation, situation) -> list[str]` — template-driven slot-filling from ALL 8 insight categories, ranked by delta magnitude, top 3 returned
12. `generate_merge_directives(scores, structural, efficiency, strategy, context, validation) -> list[str]` — ordered by impact, each cites specific data point
13. `generate_cross_patterns(a, b, scores) -> list[str]` — CROSS-only: structural choices correlated with scores, framework suitability by task type (empty list for non-CROSS situations)
14. `compute_comparison(a: Optimization, b: Optimization, provider) -> CompareResponse` — orchestrator that calls all of the above, plus an optional Haiku LLM call for `guidance.headline/merge_suggestion/actionable`

Each extraction function is a pure function taking an `Optimization` model instance. `compute_comparison` is the async orchestrator.

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd backend && python -m pytest tests/test_compare_service.py -v
```

Expected: All 6 classification tests PASS

- [ ] **Step 5: Add tests for score extraction and insight generation**

Add to `tests/test_compare_service.py`:

```python
class TestScoreExtraction:
    def test_extracts_all_dimensions(self):
        opt = _mock_opt(clarity_score=8, faithfulness_score=7, specificity_score=8,
                        structure_score=9, conciseness_score=7, overall_score=8.0)
        scores = extract_scores(opt)
        assert scores["clarity"] == 8
        assert scores["overall"] == 8.0
        assert len(scores) == 6

    def test_handles_none_scores(self):
        opt = _mock_opt(clarity_score=None, overall_score=None)
        scores = extract_scores(opt)
        assert scores["clarity"] is None


class TestInsightGeneration:
    def test_generates_top_3_insights(self):
        # Mock comparison data with known deltas
        scores_data = {
            "deltas": {"clarity": 2.0, "faithfulness": -0.5, "specificity": 1.0,
                       "structure": 1.5, "conciseness": 0.0},
            "floors": ["conciseness"],
            "ceilings": [],
        }
        insights = generate_top_insights(
            scores=scores_data,
            structural={"a_input_words": 45, "b_input_words": 120},
            efficiency={"a_duration_ms": 4100, "b_duration_ms": 6500},
            strategy={"a_framework": "CO-STAR", "b_framework": "RISEN"},
            context={"a_repo": None, "b_repo": "owner/repo", "a_has_codebase": False, "b_has_codebase": True},
            validation={"a_verdict": "Strong improvement", "b_verdict": "Moderate improvement", "a_issues": [], "b_issues": ["verbose"]},
            adaptation={"feedbacks_between": 3, "weight_shifts": {"clarity": 0.08}},
            situation="STRATEGY",
        )
        assert len(insights) <= 3
        assert all(isinstance(i, str) for i in insights)
```

- [ ] **Step 6: Implement extraction functions to pass tests**

- [ ] **Step 7: Run full test suite**

```bash
cd backend && python -m pytest tests/test_compare_service.py -v
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/compare_service.py backend/tests/test_compare_service.py
git commit -m "feat(compare): comparison service — classification, data extraction, insight generation"
```

---

### Task 3: Merge Service — LLM Prompt Construction

**Files:**
- Create: `backend/app/services/merge_service.py`
- Reference: `backend/app/services/compare_service.py`
- Reference: `backend/app/providers/base.py` (LLMProvider interface)

- [ ] **Step 1: Write test for merge system prompt construction**

Add `backend/tests/test_merge_service.py`:

```python
"""Tests for merge_service — LLM prompt construction."""

import pytest
from app.services.merge_service import build_merge_system_prompt
from app.schemas.compare_models import (
    CompareResponse, CompareGuidance, ScoreComparison,
    StructuralComparison, EfficiencyComparison, StrategyComparison, AdaptationComparison,
)


def _build_mock_compare_response() -> CompareResponse:
    """Build a minimal but complete CompareResponse for testing."""
    return CompareResponse(
        situation="STRATEGY",
        situation_label="Framework head-to-head",
        insight_headline="CO-STAR vs RISEN — +0.8 overall",
        modifiers=["adapted"],
        a={"id": "a1", "optimized_prompt": "Prompt A text", "raw_prompt": "raw"},
        b={"id": "b1", "optimized_prompt": "Prompt B text", "raw_prompt": "raw"},
        scores=ScoreComparison(
            dimensions=["clarity", "faithfulness", "specificity", "structure", "conciseness"],
            a_scores={"clarity": 8.5, "faithfulness": 7.5, "specificity": 8.0, "structure": 9.0, "conciseness": 7.0},
            b_scores={"clarity": 6.5, "faithfulness": 8.0, "specificity": 7.0, "structure": 7.5, "conciseness": 7.0},
            deltas={"clarity": 2.0, "faithfulness": -0.5, "specificity": 1.0, "structure": 1.5, "conciseness": 0.0},
            overall_delta=0.8, winner="a", ceilings=[], floors=[],
        ),
        structural=StructuralComparison(
            a_input_words=45, b_input_words=120, a_output_words=144, b_output_words=252,
            a_expansion=3.2, b_expansion=2.1, a_complexity="basic", b_complexity="intermediate",
        ),
        efficiency=EfficiencyComparison(
            a_duration_ms=4100, b_duration_ms=6500, a_tokens=2100, b_tokens=2600,
            a_cost=0.008, b_cost=0.011, a_score_per_token=3.8, b_score_per_token=2.8,
        ),
        strategy=StrategyComparison(
            a_framework="CO-STAR", a_source="llm", a_rationale="Context grounding",
            a_guardrails=["clarity-focus"], b_framework="RISEN", b_source="heuristic",
            b_rationale="Role-based", b_guardrails=[],
        ),
        adaptation=AdaptationComparison(feedbacks_between=3, weight_shifts={"clarity": 0.08}, guardrails_added=["clarity-focus"]),
        top_insights=["Clarity gap is structural", "Both 7.0 conciseness", "Repo context ROI marginal"],
        guidance=CompareGuidance(
            headline="CO-STAR clarity +2.0; RISEN faithfulness +0.5",
            merge_suggestion="Combine CO-STAR context with RISEN role anchoring",
            strengths_a=["clarity", "structure", "specificity"],
            strengths_b=["faithfulness"],
            persistent_weaknesses=["conciseness"],
            actionable=["Clarity gap is structural", "Add word-limit"],
            merge_directives=["Preserve clarity sections", "Inject role definition", "Add format constraint"],
        ),
    )


class TestMergePromptConstruction:
    def test_includes_all_intelligence_sections(self):
        # Build a minimal CompareResponse
        compare = _build_mock_compare_response()
        prompt = build_merge_system_prompt(compare)

        assert "SITUATION" in prompt
        assert "SCORE INTELLIGENCE" in prompt
        assert "STRUCTURAL INTELLIGENCE" in prompt
        assert "STRATEGY INTELLIGENCE" in prompt
        assert "EFFICIENCY INTELLIGENCE" in prompt
        assert "MERGE DIRECTIVES" in prompt
        assert "DIMENSION TARGETS" in prompt
        assert "CONSTRAINTS" in prompt

    def test_directives_ordered_by_delta_magnitude(self):
        compare = _build_mock_compare_response()
        prompt = build_merge_system_prompt(compare)
        # The directive referencing clarity (+2.0, largest delta) should appear first
        clarity_pos = prompt.find("clarity")
        faithfulness_pos = prompt.find("faithfulness")
        assert clarity_pos < faithfulness_pos

    def test_dimension_targets_use_max_of_winners(self):
        compare = _build_mock_compare_response()
        prompt = build_merge_system_prompt(compare)
        # A scored 8.5 clarity (winner), so target should be >= 8.5
        assert "8.5" in prompt or "≥8.5" in prompt
```

- [ ] **Step 2: Implement `build_merge_system_prompt(compare: CompareResponse) -> str`**

Pure function that slot-fills the 11 intelligence sections from the CompareResponse payload. Returns the complete system prompt string.

- [ ] **Step 3: Implement `stream_merge(provider, compare: CompareResponse, model: str) -> AsyncGenerator`**

Async generator that:
1. Calls `build_merge_system_prompt(compare)`
2. Builds user message: `"PROMPT A (CO-STAR):\n{a.optimized_prompt}\n\nPROMPT B (RISEN):\n{b.optimized_prompt}"`
3. Resolves model: if `model == "auto"`, use provider's default; otherwise pass model ID to provider
4. Streams via `provider.stream(system=system_prompt, user=user_msg, model=model)`
5. Yields text chunks as they arrive

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_merge_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/merge_service.py backend/tests/test_merge_service.py
git commit -m "feat(compare): merge service — full intelligence injection LLM prompt construction"
```

---

### Task 4: Compare Router — Endpoints

**Files:**
- Create: `backend/app/routers/compare.py`
- Modify: `backend/app/main.py` (register router)
- Modify: `backend/app/models/optimization.py` (add `merge_parents` column)
- Modify: `backend/app/routers/history.py` (add `"merged"` to `VALID_STATUSES`)

- [ ] **Step 1: Add `merge_parents` column to Optimization model**

In `backend/app/models/optimization.py`, add after `active_branch_id`:
```python
merge_parents = Column(Text, nullable=True)  # JSON: [parent_id_a, parent_id_b]
```

Add `"merge_parents"` to the JSON list-column parsing block in `to_dict()` (alongside `weaknesses`, `strengths`, etc.).

- [ ] **Step 2: Add `"merged"` to VALID_STATUSES and sort column whitelist**

In `backend/app/routers/history.py`, update the `VALID_STATUSES` frozenset:
```python
VALID_STATUSES = frozenset({"running", "completed", "failed", "pending", "merged"})
```

In `backend/app/services/optimization_service.py`, verify `"status"` is already in `_VALID_SORT_COLUMNS` (it is — `"merged"` is a status value, not a column name, so no column whitelist change needed).

- [ ] **Step 3: Create compare router with all three endpoints**

Create `backend/app/routers/compare.py`:

```python
"""Compare and merge endpoints for cross-optimization analysis."""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.database import async_session
from app.dependencies.auth import get_current_user
from app.dependencies.rate_limit import RateLimit
from app.errors import not_found, bad_request
from app.models.optimization import Optimization
from app.schemas.auth import AuthenticatedUser
from app.schemas.compare_models import CompareResponse, MergeAcceptRequest, MergeAcceptResponse
from app.services.cache_service import get_cache
from app.services.compare_service import compute_comparison
from app.services.merge_service import stream_merge
from app.services.settings_service import load_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["compare"])


async def _fetch_user_optimization(opt_id: str, user_id: str) -> Optimization:
    """Fetch optimization scoped to user. Does NOT filter deleted_at so trashed items are allowed.
    Returns 404 for missing or wrong-user (information hiding — no 403)."""
    async with async_session() as session:
        query = select(Optimization).where(
            Optimization.id == opt_id,
            Optimization.user_id == user_id,
        )
        result = await session.execute(query)
        opt = result.scalar_one_or_none()
        if not opt:
            raise not_found("Optimization not found")
        return opt


def _cache_key(id_a: str, id_b: str) -> str:
    return f"compare:{':'.join(sorted([id_a, id_b]))}"


@router.get("/api/compare")
async def compare_optimizations(
    request: Request,
    a: str = Query(..., description="First optimization ID"),
    b: str = Query(..., description="Second optimization ID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: "10/minute")),
) -> CompareResponse:
    if a == b:
        raise HTTPException(status_code=422, detail="Cannot compare an optimization with itself")
    opt_a = await _fetch_user_optimization(a, current_user.id)
    opt_b = await _fetch_user_optimization(b, current_user.id)
    if not opt_a.optimized_prompt or not opt_b.optimized_prompt:
        raise HTTPException(status_code=422, detail="Cannot compare incomplete optimizations")

    cache = get_cache()
    key = _cache_key(a, b)
    cached = await cache.get(key)
    if cached:
        return CompareResponse(**cached)

    provider = request.app.state.provider
    result = await compute_comparison(opt_a, opt_b, provider)
    await cache.set(key, result.model_dump(), ttl_seconds=300)
    return result


@router.post("/api/compare/merge")
async def merge_optimizations(
    request: Request,
    body: dict,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: "5/minute")),
):
    """Stream merged prompt via SSE. Same pattern as optimize.py SSE endpoint."""
    id_a = body.get("optimization_id_a")
    id_b = body.get("optimization_id_b")
    if not id_a or not id_b:
        raise bad_request("optimization_id_a and optimization_id_b required")

    # Fetch or recompute comparison (from cache if available)
    cache = get_cache()
    key = _cache_key(id_a, id_b)
    cached = await cache.get(key)
    if cached:
        compare = CompareResponse(**cached)
    else:
        opt_a = await _fetch_user_optimization(id_a, current_user.id)
        opt_b = await _fetch_user_optimization(id_b, current_user.id)
        provider = request.app.state.provider
        compare = await compute_comparison(opt_a, opt_b, provider)

    settings = load_settings()
    model = settings.get("default_model", "auto")
    provider = request.app.state.provider

    async def event_stream():
        try:
            async for chunk in stream_merge(provider, compare, model):
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
        except Exception as e:
            logger.error("Merge stream error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/compare/merge/accept")
async def accept_merge(
    request: Request,
    body: MergeAcceptRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: "10/minute")),
) -> MergeAcceptResponse:
    # Validate both parents exist and belong to user
    opt_a = await _fetch_user_optimization(body.optimization_id_a, current_user.id)
    opt_b = await _fetch_user_optimization(body.optimization_id_b, current_user.id)

    new_id = str(uuid.uuid4())
    async with async_session() as session:
        async with session.begin():
            # Create merged optimization
            merged = Optimization(
                id=new_id,
                raw_prompt=body.merged_prompt,
                status="merged",
                user_id=current_user.id,
                merge_parents=json.dumps([body.optimization_id_a, body.optimization_id_b]),
                created_at=datetime.now(timezone.utc),
            )
            session.add(merged)

            # Soft-delete parents (separate try so merge record survives if this fails)
            try:
                now = datetime.now(timezone.utc)
                for opt in (opt_a, opt_b):
                    parent = await session.get(Optimization, opt.id)
                    if parent:
                        parent.deleted_at = now
            except Exception as e:
                logger.error("Failed to soft-delete merge parents: %s", e)
                # Continue — merged record is saved, orphaned parents are cosmetic

    # Invalidate compare cache
    cache = get_cache()
    await cache.delete(_cache_key(body.optimization_id_a, body.optimization_id_b))

    return MergeAcceptResponse(optimization_id=new_id, status="merged")
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py` import section and router registration:
```python
from app.routers import compare as compare_router
# ...
app.include_router(compare_router.router)
```

- [ ] **Step 5: Write integration test for compare endpoint**

- [ ] **Step 6: Run all backend tests**

```bash
cd backend && python -m pytest -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/compare.py backend/app/main.py \
  backend/app/models/optimization.py backend/app/routers/history.py \
  backend/tests/test_compare_router.py
git commit -m "feat(compare): router with compare, merge SSE, and accept endpoints"
```

---

## Chunk 2: Frontend — API Client + CompareModal + Wiring

### Task 5: API Client Functions

**Files:**
- Modify: `frontend/src/lib/api/client.ts`

- [ ] **Step 1: Add TypeScript interfaces and API functions**

```typescript
// ---- Compare ----

export interface CompareResponse {
  situation: string;
  situation_label: string;
  insight_headline: string;
  modifiers: string[];
  a: Record<string, unknown>;
  b: Record<string, unknown>;
  scores: {
    dimensions: string[];
    a_scores: Record<string, number | null>;
    b_scores: Record<string, number | null>;
    deltas: Record<string, number | null>;
    overall_delta: number | null;
    winner: string | null;
    ceilings: string[];
    floors: string[];
  };
  structural: Record<string, unknown>;
  efficiency: Record<string, unknown>;
  strategy: Record<string, unknown>;
  context: Record<string, unknown>;
  validation: Record<string, unknown>;
  adaptation: Record<string, unknown>;
  top_insights: string[];
  cross_patterns: string[];
  a_is_trashed: boolean;
  b_is_trashed: boolean;
  guidance: {
    headline: string;
    merge_suggestion: string;
    strengths_a: string[];
    strengths_b: string[];
    persistent_weaknesses: string[];
    actionable: string[];
    merge_directives: string[];
  } | null;
}

export async function compareOptimizations(idA: string, idB: string): Promise<CompareResponse> {
  const res = await apiFetch(
    `${BASE}/api/compare?a=${encodeURIComponent(idA)}&b=${encodeURIComponent(idB)}`
  );
  if (!res.ok) throw new Error(`Compare failed: ${res.status}`);
  return res.json();
}

export async function mergeOptimizations(
  idA: string,
  idB: string,
  onChunk: (text: string) => void,
  onError: (err: Error) => void,
  onComplete: () => void,
): Promise<AbortController> {
  const controller = new AbortController();
  const res = await apiFetch(`${BASE}/api/compare/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ optimization_id_a: idA, optimization_id_b: idB }),
    signal: controller.signal,
  });
  if (!res.ok) {
    onError(new Error(`Merge failed: ${res.status}`));
    return controller;
  }

  // Parse SSE stream — same pattern as startOptimization
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  (async () => {
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') onChunk(data.text);
            else if (data.type === 'complete') onComplete();
            else if (data.type === 'error') onError(new Error(data.message));
          } catch { /* skip malformed lines */ }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') onError(err as Error);
    }
  })();

  return controller;
}

export async function acceptMerge(
  idA: string,
  idB: string,
  mergedPrompt: string,
): Promise<{ optimization_id: string }> {
  const res = await apiFetch(`${BASE}/api/compare/merge/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      optimization_id_a: idA,
      optimization_id_b: idB,
      merged_prompt: mergedPrompt,
    }),
  });
  if (!res.ok) throw new Error(`Accept merge failed: ${res.status}`);
  return res.json();
}

export async function discardMerge(): Promise<void> {
  // No-op — frontend only, included for API surface completeness
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api/client.ts
git commit -m "feat(compare): API client functions for compare, merge SSE, and accept"
```

---

### Task 6: CompareModal Component

**Files:**
- Create: `frontend/src/lib/components/shared/CompareModal.svelte`
- Reference: `frontend/src/lib/components/pipeline/BranchCompare.svelte` (pattern reference for score table + DiffView + action buttons)
- Reference: `frontend/src/lib/components/shared/DiffView.svelte`
- Reuse: `frontend/src/lib/components/shared/ScoreCircle.svelte` (for optional score display)
- Reuse: `frontend/src/lib/components/shared/StrategyBadge.svelte` (for framework labels)
- Note: No `Modal.svelte` exists in shared — CompareModal implements its own overlay (same pattern as BranchCompare: fixed inset-0 div with glass backdrop)

This is the largest single task. The component has 3 phases and multiple sub-sections. Build it incrementally.

**Brand compliance reference (exact Tailwind classes for every element):**

| Element | Classes |
|---|---|
| Modal overlay | `fixed inset-0 z-50 flex items-center justify-center p-4` + `style="background:rgba(12,12,22,0.7);backdrop-filter:blur(8px)"` |
| Modal panel | `border border-border-subtle bg-bg-card w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col` (no border-radius — flat edges for data-dense context) |
| Header | `h-8 flex items-center justify-between px-2 border-b border-border-subtle shrink-0` |
| Header title | `font-display text-[11px] font-bold uppercase tracking-wider text-text-dim` |
| Situation badge REFORGE | `font-mono text-[9px] font-medium px-1.5 py-0.5 border border-neon-green/35 text-neon-green bg-neon-green/5` |
| Situation badge STRATEGY | `font-mono text-[9px] font-medium px-1.5 py-0.5 border border-neon-purple/35 text-neon-purple bg-neon-purple/5` |
| Situation badge EVOLVED | `font-mono text-[9px] font-medium px-1.5 py-0.5 border border-neon-yellow/35 text-neon-yellow bg-neon-yellow/5` |
| Situation badge CROSS | `font-mono text-[9px] font-medium px-1.5 py-0.5 border border-neon-blue/35 text-neon-blue bg-neon-blue/5` |
| Framework label A | `font-mono text-[9px] px-1 py-0.5 border border-neon-purple/20 text-neon-purple/80` |
| Framework label B | `font-mono text-[9px] px-1 py-0.5 border border-neon-blue/20 text-neon-blue/80` |
| Close button | `w-6 h-6 flex items-center justify-center text-text-dim hover:text-text-primary transition-colors duration-150` |
| Insight strip | `px-2 py-1.5 border-b border-border-subtle bg-bg-secondary/40` |
| Insight headline | `font-mono text-[10px] text-text-secondary leading-snug` |
| Modifier pills | `font-mono text-[7px] px-1 border border-neon-teal/25 text-neon-teal uppercase tracking-wider` |
| Top insight rows | `font-mono text-[9px] text-text-secondary` with `▸` icon in `text-[7px] text-neon-cyan` |
| Section label | `font-display text-[10px] font-bold uppercase tracking-wider text-text-dim` |
| Score table | `font-mono text-[10px]` with `style="font-variant-numeric:tabular-nums"` |
| Score table header | `text-[8px] uppercase tracking-wider text-text-dim font-medium` |
| Score table row | `h-5` with `border-b border-border-subtle/50 hover:bg-bg-hover/15 transition-colors duration-150` |
| Winner dot | `w-1 h-1 bg-neon-cyan inline-block mr-0.5` |
| Delta positive | `text-neon-green font-semibold` |
| Delta negative | `text-neon-red font-semibold` |
| Delta zero | `text-text-dim` |
| Delta sparkline bar | `inline-block h-1 ml-1` with `bg-neon-green/25 border-r border-neon-green` (pos) or `bg-neon-red/25 border-l border-neon-red` (neg) |
| Accordion header | `h-7 flex items-center justify-between px-2 cursor-pointer hover:bg-bg-hover/15 transition-colors duration-200` |
| Accordion title | `font-display text-[9px] font-bold uppercase tracking-wider text-text-dim` |
| Accordion summary | `font-mono text-[8px] text-text-dim` |
| Accordion body | `px-2 pb-2` with `transition:slide={{ duration: 200 }}` (Svelte directive) |
| Structural mini-cards | `border border-border-subtle/50 p-1` in `grid grid-cols-4 gap-1` |
| Efficiency bar tracks | `h-1.5 bg-bg-primary` with A fill `bg-neon-purple/30 border-r border-neon-purple` and B fill `bg-neon-blue/30 border-r border-neon-blue` |
| Guidance card | `border border-border-accent bg-neon-cyan/[0.015] p-1.5 mx-2` |
| Guidance label | `font-display text-[9px] font-bold uppercase tracking-wider text-neon-cyan` |
| Merge directives | `font-mono text-[9px] text-text-secondary` with `→` prefix in `text-neon-teal` |
| Strength pills A | `font-mono text-[8px] px-1 border border-neon-purple/20 text-neon-purple capitalize` |
| Strength pills B | `font-mono text-[8px] px-1 border border-neon-blue/20 text-neon-blue capitalize` |
| Weakness pills | `font-mono text-[8px] px-1 border border-neon-yellow/20 text-neon-yellow capitalize` |
| Trashed badge | `font-mono text-[8px] px-1 border border-neon-red/20 text-neon-red uppercase` |
| Action bar | `h-8 flex items-center justify-between px-2 border-t border-border-subtle bg-bg-secondary/40 shrink-0` |
| Merge button | `font-mono text-[10px] px-3 py-1 border border-neon-teal/40 text-neon-teal bg-neon-teal/5 hover:bg-neon-teal/10 hover:border-neon-teal/60 transition-colors duration-200 uppercase tracking-wider` |
| Close button (action) | `font-mono text-[10px] px-3 py-1 border border-border-subtle text-text-dim hover:text-text-secondary hover:border-border-accent transition-colors duration-200 uppercase tracking-wider` |
| Accept button | `font-mono text-[10px] px-3 py-1.5 border border-neon-cyan/40 text-neon-cyan bg-neon-cyan/5 hover:bg-neon-cyan/15 hover:border-neon-cyan transition-colors duration-200 flex-1 text-center uppercase` |
| Discard button | `font-mono text-[10px] px-3 py-1.5 border border-neon-red/25 text-neon-red bg-neon-red/5 hover:bg-neon-red/10 hover:border-neon-red transition-colors duration-200 flex-1 text-center uppercase` |
| Merge preview panel | `bg-bg-input border border-neon-teal/20 p-1.5 font-mono text-[10px] text-text-secondary leading-relaxed max-h-40 overflow-y-auto` |
| Warning text | `font-mono text-[8px] text-neon-yellow leading-snug` |

**Typography assignment:**
- **Syne** (`font-display`): header title, section labels, accordion titles, guidance label, gate question
- **Geist Mono** (`font-mono`): all data values, scores, badges, pills, framework labels, insight text, directive text, preview panel, buttons
- **Space Grotesk** (`font-sans`): NOT used in this modal — it's 100% data-dense, all mono + display

**Transitions:**
- Micro (icon/text hover): `duration-150`
- Standard hover (borders, backgrounds): `duration-200`
- Accordion expand/collapse: Svelte `transition:slide={{ duration: 200 }}` (NOT CSS @keyframes)
- Modal entrance: `animation: dialog-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) both` (spring entrance)

**Zero-effects:** No `shadow-*`, no `ring`, no `glow`, no `radial-gradient`. Borders 1px solid only.

---

- [ ] **Step 1: Create CompareModal with Phase 1 — header + insight strip + score table**

Props: `{ idA: string, idB: string, onclose: () => void }`

On mount: call `compareOptimizations(idA, idB)`, store result in `$state`. While loading, show skeleton. On error, show toast and call `onclose`.

Header (`h-8`): situation badge (use badge class map above keyed by `result.situation`), framework labels (A purple, B blue), close button. If `result.a_is_trashed` or `result.b_is_trashed`, show "TRASHED" badge next to the affected framework label.

Insight strip (`px-2 py-1.5`): `insight_headline` in `font-mono text-[10px]`, modifier pills, `top_insights` as `▸`-prefixed rows in `font-mono text-[9px]`.

Score table: iterate `scores.dimensions`, show a_scores/b_scores/deltas per row (`h-5`), winner dot (`w-1 h-1 bg-neon-cyan`), inline delta sparkline bar, overall row at bottom with `border-t`.

- [ ] **Step 2: Add accordion sections — Structural, Efficiency, Strategy, Context & Adaptation**

Each accordion: `h-7` header with one-line summary derived from the comparison data, collapsible body with the detailed cards/charts per spec.

Structural: 4-card grid (input words, output words, expansion ratio, complexity).
Efficiency: dual bar chart rows (duration, tokens, cost, score/token).
Strategy: 2-column grid with framework card per side (name, source badge, rationale, guardrail pills).
Context & Adaptation: repo delta, feedbacks_between, weight_shifts.

All start collapsed by default.

- [ ] **Step 3: Add guidance card + DiffView + action bar (Phase 1 complete)**

Guidance card: `border-accent`, arrow-prefixed `merge_directives`, strength pills per side, persistent weakness pills.

DiffView: `<DiffView original={a.optimized_prompt} modified={b.optimized_prompt} />`

Action bar (`h-8`, pinned): Close button + Merge Insights button. Merge Insights disabled if `guidance` is null (tooltip: "Analysis unavailable").

- [ ] **Step 4: Add Phase 2 — Merge streaming**

On "Merge Insights" click:
1. Set `phase = 'merge'`
2. Collapse accordions
3. Call `mergeOptimizations(idA, idB, onChunk, onError, onComplete)`
4. `onChunk`: append text to `mergedText` state, show in preview panel with streaming cursor
5. `onComplete`: set `phase = 'commit'`
6. `onError`: show partial text with red border, "Retry" button

Preview panel: `bg-bg-input`, `border-teal/20`, `font-mono text-[10px]`, max-height scrollable.
Below: model indicator + token count.

- [ ] **Step 5: Add Phase 3 — Commit Gate**

When `phase === 'commit'`:
- Remove close button from header (conditional render: `{#if phase !== 'commit'}`)
- Show merged prompt in full (scrollable, `border-neon-teal/25`)
- Two equal-width buttons: "Accept — Archive Parents" (cyan) | "Discard — Cancel Merge" (red)
- Warning text in `font-mono text-[8px] text-neon-yellow` below buttons
- Block Escape key: `onkeydown` handler calls `e.preventDefault()` when `phase === 'commit' && e.key === 'Escape'`
- Block backdrop click: backdrop `onclick` is no-op when `phase === 'commit'`
- Browser back protection via `$effect` lifecycle:
  ```typescript
  $effect(() => {
    if (phase !== 'commit') return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  });
  ```

Accept handler: wrap `acceptMerge(idA, idB, mergedText)` in try/catch. On success: open new tab via `editor.openTab(...)`, call `history.loadHistory()`, show toast "Merge complete — prompt ready to forge", call `onclose`. On error: show toast "Failed to save merge", keep `phase = 'commit'` (don't call `onclose` — user can retry or copy text manually).

Discard handler: call `onclose` directly (no API call).

- [ ] **Step 6: Run svelte-check**

```bash
cd frontend && npx svelte-check --tsconfig ./tsconfig.json --threshold error
```

Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/components/shared/CompareModal.svelte
git commit -m "feat(compare): CompareModal — 3-phase modal with analysis, merge streaming, commit gate"
```

---

### Task 7: Wire NavigatorHistory to CompareModal

**Files:**
- Modify: `frontend/src/lib/components/layout/NavigatorHistory.svelte`

- [ ] **Step 1: Replace stub `handleCompare()` with modal trigger**

Import CompareModal. Add state:
```typescript
let showCompare = $state(false);
let compareIdA = $state('');
let compareIdB = $state('');
```

Replace `handleCompare()`:
```typescript
function handleCompare() {
  const ids = Array.from(selectedIds);
  if (ids.length === 2) {
    compareIdA = ids[0];
    compareIdB = ids[1];
    showCompare = true;
    clearSelection();
  }
}
```

Add modal render at end of component template:
```svelte
{#if showCompare}
  <CompareModal
    idA={compareIdA}
    idB={compareIdB}
    onclose={() => { showCompare = false; }}
  />
{/if}
```

- [ ] **Step 2: Remove old stub tab-creation code** (the `editor.openTab` call with placeholder text)

- [ ] **Step 3: Run svelte-check**

```bash
cd frontend && npx svelte-check --tsconfig ./tsconfig.json --threshold error
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/components/layout/NavigatorHistory.svelte
git commit -m "feat(compare): wire NavigatorHistory Compare button to CompareModal"
```

---

## Chunk 3: Integration + Polish

### Task 8: Migration for merge_parents Column

**Files:**
- Modify: `backend/app/main.py` (startup migration check)

- [ ] **Step 1: Add startup migration for merge_parents column**

In `main.py` lifespan, after `create_all()`, add:

```python
# Migration: add merge_parents column if not present (nullable, safe for SQLite)
async with engine.begin() as conn:
    result = await conn.execute(text("PRAGMA table_info(optimizations)"))
    columns = {row[1] for row in result.fetchall()}
    if "merge_parents" not in columns:
        await conn.execute(text("ALTER TABLE optimizations ADD COLUMN merge_parents TEXT"))
        logger.info("Migration: added merge_parents column to optimizations")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(compare): startup migration for merge_parents column"
```

---

### Task 9: End-to-End Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest -v
```

Expected: All tests pass including new compare/merge tests

- [ ] **Step 2: Run frontend type check**

```bash
cd frontend && npx svelte-check --tsconfig ./tsconfig.json --threshold error
```

Expected: 0 errors

- [ ] **Step 3: Manual test — full compare flow**

1. Start services: `./init.sh restart`
2. Select 2 history items in sidebar
3. Click Compare → modal opens with situation badge, scores, insights
4. Expand accordion sections — verify data populated
5. Click "Merge Insights" → LLM streams merged prompt
6. Click "Accept" → new entry appears in history, parents moved to trash
7. Open new entry → verify it's the merged prompt text

- [ ] **Step 4: Manual test — discard flow**

1. Select 2 items, Compare, Merge Insights
2. Click "Discard" → modal closes, parents untouched in history

- [ ] **Step 5: Manual test — error handling**

1. Compare item with no optimized_prompt → 422 toast
2. Close browser tab during merge stream → no orphaned state

- [ ] **Step 6: Final commit (if any remaining unstaged changes)**

```bash
git status
# Stage only specific files that were modified during verification
git commit -m "feat(compare): end-to-end compare and merge — complete implementation"
```
