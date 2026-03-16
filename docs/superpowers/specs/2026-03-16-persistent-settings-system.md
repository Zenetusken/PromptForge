# Persistent Settings System

## Problem

Settings panel is sparse (3 read-only config values + API key). Model selection is hardcoded. Pipeline phases can't be toggled. GitHub lives in a separate panel. No preferences survive server restart. Users can't do lean token-conscious runs.

## Solution

File-based preferences (`data/preferences.json`) with full-stack integration: backend service + REST API + Svelte store + expanded settings UI. Pipeline reads preferences at execution time for model selection and phase toggling.

---

## 1. Preferences Schema

```json
{
  "schema_version": 1,
  "models": {
    "analyzer": "sonnet",
    "optimizer": "opus",
    "scorer": "sonnet"
  },
  "pipeline": {
    "enable_explore": true,
    "enable_scoring": true,
    "enable_adaptation": true
  },
  "defaults": {
    "strategy": "auto"
  }
}
```

### Model Options

All three models (sonnet, opus, haiku) are valid for any phase. The defaults reflect the quality/cost sweet spot:

| Phase | Default | Rationale |
|-------|---------|-----------|
| Analyzer | sonnet | Classification needs moderate intelligence |
| Optimizer | opus | Core value — highest quality by default |
| Scorer | sonnet | Evaluation needs nuance; haiku for speed |

Model names map to `settings.MODEL_SONNET`, `settings.MODEL_OPUS`, `settings.MODEL_HAIKU` in `config.py`. Validation is global (any of "sonnet", "opus", "haiku" accepted for any phase).

### Pipeline Toggles

| Toggle | Default | When OFF |
|--------|---------|----------|
| `enable_explore` | true | Skip codebase context fetch. Saves 1 Haiku call + embedding compute. |
| `enable_scoring` | true | Skip Phase 3 (scorer + heuristic blend). Returns optimized prompt with no scores. Saves 1 Sonnet call. |
| `enable_adaptation` | true | Skip strategy affinity state injection. Marginal token savings. |

**Lean mode**: `enable_explore=false` + `enable_scoring=false` = 2 LLM calls (analyze + optimize). Minimum viable pipeline.

### Default Strategy

Persists the user's preferred strategy across sessions. Applied when no explicit strategy override is passed in the optimize request.

---

## 2. Persistence Layer

**File**: `data/preferences.json`

- Atomic writes via temp file + rename (same pattern as `.app_secrets`)
- File mode: 0o644 (readable, owner-writable)
- Deep-merged with defaults on load — missing keys get default values
- Created automatically on first access with full defaults
- `schema_version` field for future-proofing (start at 1)
- No migration needed — additive schema (new keys get defaults, `schema_version` enables renames if ever needed)

### Corruption Recovery

- If JSON parsing fails on load: log warning, return full defaults (do not crash)
- If values are invalid (e.g., `"analyzer": "gpt-4"`): replace invalid values with their defaults, log each replacement
- `save()` validates the merged result against allowed enums before writing — prevents persisting garbage

### Why JSON file, not DB table

- Single-user self-hosted tool — no multi-tenancy
- Preferences are orthogonal to optimization data
- Survives DB resets (user clears `synthesis.db`, preferences survive)
- Easy to hand-edit for power users
- Consistent with existing `data/.app_secrets`, `data/.api_credentials`

---

## 3. Backend Service

**File**: `backend/app/services/preferences.py`

```python
class PreferencesService:
    DEFAULTS = {
        "schema_version": 1,
        "models": {"analyzer": "sonnet", "optimizer": "opus", "scorer": "sonnet"},
        "pipeline": {"enable_explore": True, "enable_scoring": True, "enable_adaptation": True},
        "defaults": {"strategy": "auto"},
    }

    def __init__(self, data_dir: Path): ...
    def load(self) -> dict: ...         # Read + deep-merge with defaults (single disk read)
    def save(self, prefs: dict): ...    # Validate + atomic write
    def get(self, path: str, snapshot: dict | None = None) -> Any: ...  # Dot-path accessor
    def patch(self, updates: dict): ... # Deep-merge updates into existing
    def resolve_model(self, phase: str, snapshot: dict | None = None) -> str: ...
```

`resolve_model()` maps short names ("sonnet", "opus", "haiku") to full model IDs from `config.py`.

**Snapshot pattern**: `load()` returns a frozen dict. Pipeline callers load ONCE at the start of a run and pass the snapshot to `get()` and `resolve_model()` to avoid mid-pipeline preference changes. The optional `snapshot` parameter operates on the provided dict instead of re-reading from disk.

---

## 4. REST API

**File**: `backend/app/routers/preferences.py`

### `GET /api/preferences`
Returns the full preferences object (merged with defaults).

### `PATCH /api/preferences`
Deep-merges the request body into existing preferences. Validates:
- Model names must be one of: "sonnet", "opus", "haiku"
- Pipeline toggles must be boolean
- Strategy must match an available strategy file

Returns the updated full preferences.

---

## 5. Pipeline Integration

Preferences apply to **all pipeline contexts**: main pipeline, refinement service, and MCP tools.

### 5a. Main Pipeline (`pipeline.py`)

**Snapshot semantics** — load preferences ONCE at the start of `run()`, freeze for the entire pipeline execution:
```python
prefs = PreferencesService(DATA_DIR)
prefs_snapshot = prefs.load()  # single read, frozen for this run
# All subsequent calls use the snapshot:
model=prefs.resolve_model("analyzer", prefs_snapshot)
model=prefs.resolve_model("optimizer", prefs_snapshot)
model=prefs.resolve_model("scorer", prefs_snapshot)
```

**`model_used` tracking** — DB record and PipelineResult must store the actual resolved model:
```python
optimizer_model = prefs.resolve_model("optimizer", prefs_snapshot)
model_used=optimizer_model  # NOT settings.MODEL_OPUS
```

**Phase skipping:**

- **Explore** (`enable_explore`): `if prefs.get("pipeline.enable_explore", prefs_snapshot) and repo_full_name: ...`
- **Scoring** (`enable_scoring`): when OFF, skip Phase 3 entirely. Do NOT emit `status: {stage: 'score'}` or `score_card` SSE events. Pipeline jumps from optimize-complete directly to `optimization_complete`. Set `scoring_mode="skipped"`, scores to None.
- **Adaptation** (`enable_adaptation`): when OFF, pass `adaptation_state=None` to optimizer template.

**Schema change required** — `PipelineResult` in `pipeline_contracts.py` must make score fields optional:
```python
optimized_scores: DimensionScores | None = None
original_scores: DimensionScores | None = None
score_deltas: dict[str, float] | None = None
overall_score: float | None = None
```

**Scoring-disabled interactions:**
- History panel: null `overall_score` renders as "—" (existing `scoreColor` handles null)
- Inspector: when `forgeStore.scores` is null in `complete` state, show "Scoring disabled" indicator instead of empty space
- Refinement from a scoring-skipped optimization: first refinement turn re-runs scoring to establish a baseline (automatic — refinement always scores)
- `score_card` SSE event is NOT emitted — frontend status goes directly from 'optimizing' to 'complete'

### 5b. Refinement Service (`refinement_service.py`)

Same snapshot pattern — load prefs once at the start of `create_refinement_turn()`:
```python
prefs_snapshot = prefs.load()
```

Model substitution at 4 callsites:
- Analyze phase (line ~188): `prefs.resolve_model("analyzer", prefs_snapshot)`
- Refine phase (line ~215): `prefs.resolve_model("optimizer", prefs_snapshot)`
- Score phase (line ~247): `prefs.resolve_model("scorer", prefs_snapshot)`
- Suggest phase (line ~457): always `settings.MODEL_HAIKU` (intentionally not configurable — suggestions are lightweight)

### 5c. MCP Server (`mcp_server.py`)

`synthesis_analyze` has 3 model references — all must use preferences:
```python
prefs_snapshot = prefs.load()
model=prefs.resolve_model("analyzer", prefs_snapshot)   # line ~250 (analyze call)
model=prefs.resolve_model("scorer", prefs_snapshot)      # line ~274 (score call)
model_used=prefs.resolve_model("analyzer", prefs_snapshot)  # line ~314 (DB persist)
```

`synthesis_optimize` delegates to `PipelineOrchestrator` which inherits pipeline.py changes automatically.

### 5d. Codebase Explorer (`codebase_explorer.py`)

Uses `settings.MODEL_HAIKU` at line ~198 for synthesis. **Intentionally not configurable** — same rationale as suggestions (lightweight, always Haiku). Document this decision in CLAUDE.md.

### 5e. Default Strategy

Applied in `optimize.py` router when request has no explicit strategy. Requires importing PreferencesService:
```python
from app.services.preferences import PreferencesService
from app.config import DATA_DIR

prefs = PreferencesService(DATA_DIR)
strategy = request.strategy or prefs.get("defaults.strategy") or "auto"
```

---

## 6. Frontend Store

**File**: `frontend/src/lib/stores/preferences.svelte.ts`

```typescript
class PreferencesStore {
  prefs = $state<Preferences>(DEFAULTS);
  loading = $state(false);

  async init(): Promise<void>;              // GET /api/preferences
  async update(patch: Partial<Preferences>): Promise<void>;  // PATCH
  get models(): ModelPrefs;
  get pipeline(): PipelinePrefs;
  get defaultStrategy(): string;
}
```

**Init timing**: `preferencesStore.init()` is called in the app's root layout (`+layout.svelte`) alongside existing settings/providers pre-fetch. This ensures `forgeStore` can read the default strategy on first render, before the user opens the settings panel. Each settings change triggers a PATCH.

---

## 7. Settings Panel UI

**File**: `frontend/src/lib/components/layout/Navigator.svelte` (modifications)

Consolidate all settings into one panel with these sections:

### MODELS section
Three `<select>` dropdowns — one per phase. Options sourced from a static list. Compact info-row layout matching existing patterns.

### PIPELINE section
Three toggle switches (CSS-only, no library). Each with a label and description. When scoring is OFF, show a "lean mode" indicator.

### DEFAULTS section
Strategy dropdown — same options as the toolbar strategy selector.

### PROVIDER section (existing, no changes)
Active provider + available list (read-only).

### API KEY section (existing, no changes)
Input + set/remove buttons.

### GITHUB section (moved from separate panel)
- Auth status + avatar + username
- Linked repo display
- Connect/Disconnect buttons
- Repo list + link/unlink

The GitHub activity bar icon still works but now navigates to the settings panel's GitHub section.

### SYSTEM section (existing, expanded)
Read-only config values + scoring mode display.

---

## 8. Activity Bar Changes

The GitHub icon in the activity bar switches to the settings panel and scrolls to the GitHub section, rather than having its own separate panel. This consolidates the two panels into one.

---

## 9. Files to Create/Modify

| File | Action |
|------|--------|
| `backend/app/services/preferences.py` | **Create** — PreferencesService with snapshot pattern |
| `backend/app/routers/preferences.py` | **Create** — GET/PATCH endpoints with validation |
| `backend/app/schemas/pipeline_contracts.py` | **Modify** — make score fields Optional on PipelineResult |
| `backend/app/main.py` | **Modify** — register preferences router |
| `backend/app/services/pipeline.py` | **Modify** — snapshot load, model selection, phase skipping, model_used tracking |
| `backend/app/services/refinement_service.py` | **Modify** — snapshot load, model selection at 4 callsites |
| `backend/app/mcp_server.py` | **Modify** — model selection + model_used in synthesis_analyze (3 refs) |
| `backend/app/routers/optimize.py` | **Modify** — default strategy from prefs (import PreferencesService) |
| `frontend/src/lib/stores/preferences.svelte.ts` | **Create** — reactive store |
| `frontend/src/lib/api/client.ts` | **Modify** — add getPreferences/patchPreferences |
| `frontend/src/routes/+layout.svelte` | **Modify** — init preferences store on app load |
| `frontend/src/lib/components/layout/Navigator.svelte` | **Modify** — expanded settings panel + GitHub consolidation |
| `frontend/src/lib/components/layout/EditorGroups.svelte` | **Modify** — Inspector "scoring disabled" indicator |
| `CLAUDE.md` | **Modify** — document preferences system + non-configurable model decisions |

---

## 10. Verification

### Happy path
1. `pytest backend/tests/` — all existing tests pass
2. New test: `test_preferences.py` — load/save/patch/defaults/resolve_model
3. Start server → change model → restart → verify preference persisted
4. Toggle scoring OFF → run optimize → verify no scores in result, `scoring_mode="skipped"`
5. Toggle explore OFF → run optimize with linked repo → verify no explore phase
6. Change default strategy → open new tab → verify strategy dropdown matches
7. Check `data/preferences.json` file on disk after changes

### Edge cases
8. Corrupt `preferences.json` (invalid JSON) → server starts with defaults, logs warning
9. `PATCH /api/preferences` with `{"models": {"analyzer": "gpt-4"}}` → returns 422
10. `PATCH /api/preferences` with `{"defaults": {"strategy": "nonexistent"}}` → returns 422
11. Delete `preferences.json` while server running → next GET regenerates defaults
12. Refinement from scoring-skipped optimization → first turn re-scores automatically
