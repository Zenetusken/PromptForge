# Remove Sampling Model Hints — Show Actual Models Used

**Date:** 2026-03-24
**Status:** Approved

## Problem

MCP `ModelPreferences` and `ModelHint` are purely advisory — the IDE makes the final model selection. Our sampling pipeline sends per-phase hints (Sonnet for analyze/score, Opus for optimize, Haiku for suggest) and effort priorities, but VS Code's free tier resolves everything to GPT-5 Mini or Haiku 4.5 regardless. The UI labels these as "Model Hints" and "Effort Hints" with `// via IDE` annotations, creating a false sense of control.

The per-phase model information is already captured via `result.model` but only the optimizer model is persisted to `model_used`. The actual models used are not surfaced in the UI.

## Solution

Strip all `ModelPreferences`/`ModelHint` machinery from the sampling pipeline. Persist per-phase model IDs to a new DB column. Surface actual models in the Navigator sidebar and Inspector in real time.

## Design

### Backend

#### 1. Remove hint machinery from `sampling_pipeline.py`

Delete (~95 lines):
- `_PHASE_PRESETS` dict (phase → hint + default_effort)
- `_PREF_TO_MODEL` dict (preference name → model ID)
- `_EFFORT_PRIORITIES` dict (effort → priority triad)
- `_resolve_model_preferences()` function
- `ModelHint`, `ModelPreferences` imports from `mcp.types`

Remove `model_preferences` parameter from:
- `_sampling_request_plain()` — remove from signature, remove from `kwargs` dict
- `_sampling_request_structured()` — remove from signature, remove from `kwargs` dict

Remove all call sites that pass `model_preferences=_resolve_model_preferences(...)` throughout `run_sampling_pipeline()` and `run_sampling_analyze()`.

**Note:** `prefs_snapshot` must remain — it is loaded internally by both pipeline entry points and used for pipeline toggle reads (`enable_explore`, `enable_scoring`, `enable_adaptation`). Only the six call sites passing it to `_resolve_model_preferences()` are removed.

#### 2. New `models_by_phase` column

Add `models_by_phase = Column(JSON, nullable=True)` to the `Optimization` model in `models.py`.

Alembic migration adds the column. Stores:
```json
{"analyze": "gpt-5-mini", "optimize": "claude-sonnet-4-6", "score": "gpt-5-mini", "suggest": "gpt-5-mini"}
```

Populated from the existing `model_ids` dict in `run_sampling_pipeline()`. The internal pipeline also populates it by capturing `analyzer_model`, `optimizer_model`, and `scorer_model` from `prefs.resolve_model()` calls into a local `model_ids` dict.

`model_used` (single string) remains for backward compatibility.

#### 3. SSE phase events include model ID

When `pipeline.py` emits `PipelineEvent(event="status", data={"stage": "<phase>", "state": "complete"})`, add `"model": model_id` to the data dict for each phase that has completed.

For the **internal pipeline**, this requires capturing the model ID from `prefs.resolve_model()` for each phase (analyzer, optimizer, scorer) and storing them in a local `model_ids` dict (mirroring the sampling pipeline pattern). Currently only `optimizer_model` is tracked — extend to capture `analyzer_model` and `scorer_model` from their respective `_call_provider()` sites.

For the **sampling pipeline via MCP tools**, there is no SSE stream — the tool returns a synchronous `OptimizeOutput`. Real-time model reveal does not apply to this path. The `models_by_phase` field in the final result is the only delivery mechanism. The sampling result dict (returned by `run_sampling_pipeline()`) must include `"models_by_phase": model_ids` alongside the existing `"model_used"` field.

#### 4. API response changes

Add `models_by_phase: dict[str, str] | None` to:
- `OptimizeResponse` schema in `routers/optimize.py`
- `OptimizationDetail` schema and `_serialize_optimization()` helper in `routers/optimize.py`
- The `GET /api/optimize/{trace_id}` response
- History list items (optional, only when non-null)

The `_sampling_result_to_output()` helper in `tools/optimize.py` must forward `models_by_phase` from the sampling result dict to the `OptimizeOutput` model.

### Frontend

#### 5. Navigator sidebar — sampling tier overhaul

**Remove** (when `routing.isSampling`):
- "Model Hints" sub-section with 3 model dropdowns
- "Effort Hints" sub-section with 3 effort dropdowns
- Both `// via IDE` annotations

**Replace with** "IDE Model" sub-section (green-themed):
- Before first optimization: shows `pending` in dim text for each phase
- During optimization: per-phase model labels appear in real time as each phase completes
- After optimization: shows actual model IDs per phase (Analyzer / Optimizer / Scorer)
- Model values styled as `neon-green` data values

**Internal tier unchanged** — "Models" and "Effort" dropdowns remain (they control real model selection).

**Passthrough tier unchanged** — "Context" section remains as-is.

#### 6. Forge store — `phaseModels` state

New reactive property `phaseModels: Record<string, string>` on the forge store. Populated from:
- SSE `status` events with `state: "complete"` and `model` field (real-time reveal)
- SSE `optimization_complete` event's `models_by_phase` field (catch-up on reconnect)
- Reset to `{}` on new optimization start

#### 7. `OptimizationResult` interface

Add `models_by_phase: Record<string, string> | null` to `client.ts` `OptimizationResult` interface.

#### 8. Inspector metadata

The Inspector meta-section gains a "Models" row when `models_by_phase` is present:
- Compact format: `gpt-5-mini / claude-sonnet-4-6 / gpt-5-mini`
- Title attribute shows full phase labels
- Only rendered for `mcp_sampling` provider results

#### 9. SamplingGuide modal updates

Step 2: Change description from "Model Hints and Effort Hints steer the IDE's model selection" to "The IDE selects which model to use for each phase. The actual model is captured and shown in real time."

Step 2 detail: Change from "Hints are advisory — the IDE has final say on which model to use" to "Model used per phase is displayed as each phase completes"

`whyText`: Remove "Model and effort preferences are transmitted as hints; the IDE has final say on model selection." Replace with "The IDE selects the model — the actual model used is captured per phase and displayed in real time."

### Files Changed

| File | Change |
|------|--------|
| `backend/app/services/sampling_pipeline.py` | Delete hint machinery, remove `model_preferences` from request functions, persist `models_by_phase` |
| `backend/app/models.py` | Add `models_by_phase` JSON column |
| `backend/alembic/versions/<new>.py` | Migration for new column |
| `backend/app/routers/optimize.py` | Include `models_by_phase` in response schema |
| `backend/app/routers/history.py` | Include `models_by_phase` in list response |
| `backend/app/services/pipeline.py` | Add `model` field to phase-complete SSE events, populate `models_by_phase` |
| `backend/app/schemas/pipeline_contracts.py` | Add `models_by_phase` to contract |
| `backend/app/tools/optimize.py` | Pass `models_by_phase` through from sampling result |
| `backend/app/schemas/mcp_models.py` | Add `models_by_phase` to `OptimizeOutput` |
| `frontend/src/lib/api/client.ts` | Add `models_by_phase` to `OptimizationResult` |
| `frontend/src/lib/stores/forge.svelte.ts` | Add `phaseModels` state, capture from SSE |
| `frontend/src/lib/components/layout/Navigator.svelte` | Replace hint dropdowns with IDE Model display |
| `frontend/src/lib/components/layout/Inspector.svelte` | Add Models row to meta-section |
| `frontend/src/lib/components/shared/SamplingGuide.svelte` | Remove hint references |
| `frontend/src/lib/components/layout/Navigator.test.ts` | Rewrite 12 tests asserting on "Model Hints", "Effort Hints", `// via IDE` |
| `backend/tests/test_sampling_pipeline.py` | Remove `_resolve_model_preferences` tests (~8 functions), update pipeline tests |
| `backend/tests/test_mcp_tools.py` | Verify mocked sampling calls no longer pass `model_preferences` |
| `backend/tests/test_mcp_synthesis_optimize.py` | Verify patched `run_sampling_pipeline` expectations |
| `CLAUDE.md` | Update sampling pipeline description (remove `ModelPreferences` per phase references) |
| `docs/CHANGELOG.md` | Add entry under `## Unreleased` → `Changed` |

### What stays the same

- Internal tier model/effort preferences — still work, still control actual model selection
- Passthrough tier UI — unchanged
- `model_used` DB column — backward compatible, still populated
- Preferences store schema — `models` and effort fields remain (used by internal tier). Effort preferences persist in `preferences.json` and continue to be used by the internal pipeline even when the sampling UI no longer shows them
- Force sampling / force passthrough toggles — unchanged
- Routing logic — unchanged
- Capability detection — unchanged
