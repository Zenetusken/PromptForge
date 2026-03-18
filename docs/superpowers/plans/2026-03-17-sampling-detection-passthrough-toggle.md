# Sampling Detection + Force Passthrough Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add runtime MCP sampling capability detection (disabling the `force_sampling` toggle when unsupported) and a new `force_passthrough` toggle that forces the passthrough pipeline in both MCP and the frontend forge.

**Architecture:** The MCP server writes `data/mcp_session.json` on every `synthesis_optimize` call; the FastAPI health endpoint reads it and surfaces `sampling_capable: bool | null`; the frontend disables `force_sampling` when `false`. A new `force_passthrough` preference is mutually exclusive with `force_sampling` — enforced server-side in `_validate()` and client-side in `setPipelineToggle()`. The frontend forge enters passthrough mode when `force_passthrough=true`, mirroring the existing `noProvider` path.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic, pytest, SvelteKit 2 (Svelte 5 runes), TypeScript

---

## File Map

| File | What changes |
|------|-------------|
| `backend/app/services/preferences.py` | Add `force_passthrough` to DEFAULTS, `_sanitize` tuple, `_validate` tuple; add mutual exclusion check |
| `backend/tests/test_preferences.py` | Add `TestForcePassthrough` (7 tests) + `TestMutualExclusion` (5 tests) |
| `backend/app/routers/health.py` | Read `data/mcp_session.json`, append `sampling_capable` to response |
| `backend/app/mcp_server.py` | Add `_write_mcp_session_caps()` helper; insert capability write + `force_passthrough` routing block; update docstring |
| `frontend/src/lib/stores/preferences.svelte.ts` | Add `force_passthrough` to `PipelinePrefs` interface + DEFAULTS; update `setPipelineToggle` to clear the other flag |
| `frontend/src/lib/stores/forge.svelte.ts` | Add `samplingCapable` state field; update `forge()` passthrough condition |
| `frontend/src/routes/app/+page.svelte` | Set `forgeStore.samplingCapable` from health response |
| `frontend/src/lib/components/layout/Navigator.svelte` | Update `force_sampling` disabled logic + tooltips; add `force_passthrough` toggle + PASSTHROUGH badge |
| `docs/CHANGELOG.md` | Add entries under `## Unreleased` |

---

## Task 1: Backend — `force_passthrough` preference (RED)

**Files:**
- Test: `backend/tests/test_preferences.py`

- [ ] **Step 1: Write failing tests for `force_passthrough`**

Append after the `TestForceSampling` class (after line 242 in `test_preferences.py`):

```python
# ── TestForcePassthrough ──────────────────────────────────────────────


class TestForcePassthrough:
    def test_default_is_false(self, svc: PreferencesService) -> None:
        prefs = svc.load()
        assert prefs["pipeline"]["force_passthrough"] is False

    def test_can_be_patched_true(self, svc: PreferencesService) -> None:
        result = svc.patch({"pipeline": {"force_passthrough": True}})
        assert result["pipeline"]["force_passthrough"] is True

    def test_can_be_patched_false(self, svc: PreferencesService) -> None:
        svc.patch({"pipeline": {"force_passthrough": True}})
        result = svc.patch({"pipeline": {"force_passthrough": False}})
        assert result["pipeline"]["force_passthrough"] is False

    def test_non_boolean_rejected_by_validate(self, svc: PreferencesService) -> None:
        prefs = svc.load()
        prefs["pipeline"]["force_passthrough"] = "yes"
        with pytest.raises(ValueError, match="force_passthrough"):
            svc.save(prefs)

    def test_non_boolean_sanitized_to_default(
        self, svc: PreferencesService, prefs_file: Path
    ) -> None:
        import json as _json
        prefs_file.write_text(_json.dumps({
            "schema_version": 1,
            "pipeline": {"force_passthrough": "yes"},
        }))
        prefs = svc.load()
        assert prefs["pipeline"]["force_passthrough"] is False

    def test_missing_key_merges_to_false(
        self, svc: PreferencesService, prefs_file: Path
    ) -> None:
        """Older preferences.json without force_passthrough silently gets False."""
        import json as _json
        prefs_file.write_text(_json.dumps({
            "schema_version": 1,
            "pipeline": {
                "enable_explore": True,
                "enable_scoring": True,
                "enable_adaptation": True,
                "force_sampling": False,
            },
        }))
        prefs = svc.load()
        assert prefs["pipeline"]["force_passthrough"] is False

    def test_get_dot_path(self, svc: PreferencesService) -> None:
        snap = svc.load()
        assert svc.get("pipeline.force_passthrough", snapshot=snap) is False


# ── TestMutualExclusion ───────────────────────────────────────────────


class TestMutualExclusion:
    def test_both_true_raises_value_error(self, svc: PreferencesService) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            svc.patch({"pipeline": {"force_sampling": True, "force_passthrough": True}})

    def test_force_sampling_true_when_passthrough_already_true_raises(
        self, svc: PreferencesService
    ) -> None:
        # Set passthrough first (no conflict yet)
        svc.patch({"pipeline": {"force_passthrough": True}})
        # Patch force_sampling=True — deep-merge produces both=True → raises
        with pytest.raises(ValueError, match="mutually exclusive"):
            svc.patch({"pipeline": {"force_sampling": True}})

    def test_both_false_is_valid(self, svc: PreferencesService) -> None:
        result = svc.patch({"pipeline": {"force_sampling": False, "force_passthrough": False}})
        assert result["pipeline"]["force_sampling"] is False
        assert result["pipeline"]["force_passthrough"] is False

    def test_only_force_sampling_true_valid(self, svc: PreferencesService) -> None:
        result = svc.patch({"pipeline": {"force_sampling": True, "force_passthrough": False}})
        assert result["pipeline"]["force_sampling"] is True
        assert result["pipeline"]["force_passthrough"] is False

    def test_only_force_passthrough_true_valid(self, svc: PreferencesService) -> None:
        result = svc.patch({"pipeline": {"force_passthrough": True, "force_sampling": False}})
        assert result["pipeline"]["force_passthrough"] is True
        assert result["pipeline"]["force_sampling"] is False
```

- [ ] **Step 2: Run to verify all 12 new tests fail**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_preferences.py::TestForcePassthrough tests/test_preferences.py::TestMutualExclusion -v 2>&1 | tail -20
```

Expected: 12 failures — `KeyError: 'force_passthrough'` and `AssertionError`

---

## Task 2: Backend — `force_passthrough` preference (GREEN)

**Files:**
- Modify: `backend/app/services/preferences.py`

- [ ] **Step 1: Add `force_passthrough` to DEFAULTS**

In `preferences.py`, find the `DEFAULTS` dict (around line 30). Change:

```python
    "pipeline": {
        "enable_explore": True,
        "enable_scoring": True,
        "enable_adaptation": True,
        "force_sampling": False,
    },
```

to:

```python
    "pipeline": {
        "enable_explore": True,
        "enable_scoring": True,
        "enable_adaptation": True,
        "force_sampling": False,
        "force_passthrough": False,
    },
```

- [ ] **Step 2: Add `force_passthrough` to the `_sanitize` tuple**

Find the `for toggle in (...)` loop inside `_sanitize` (around line 166). Change:

```python
        for toggle in ("enable_explore", "enable_scoring", "enable_adaptation", "force_sampling"):
```

to:

```python
        for toggle in ("enable_explore", "enable_scoring", "enable_adaptation", "force_sampling", "force_passthrough"):
```

- [ ] **Step 3: Add `force_passthrough` to the `_validate` tuple + mutual exclusion check**

Find the `for toggle in (...)` loop inside `_validate` (around line 197). Change:

```python
        for toggle in ("enable_explore", "enable_scoring", "enable_adaptation", "force_sampling"):
            val = pipeline.get(toggle)
            if val is not None and not isinstance(val, bool):
                raise ValueError(
                    f"Pipeline toggle '{toggle}' must be boolean, got {type(val).__name__}"
                )
```

to:

```python
        for toggle in ("enable_explore", "enable_scoring", "enable_adaptation", "force_sampling", "force_passthrough"):
            val = pipeline.get(toggle)
            if val is not None and not isinstance(val, bool):
                raise ValueError(
                    f"Pipeline toggle '{toggle}' must be boolean, got {type(val).__name__}"
                )

        if pipeline.get("force_sampling") and pipeline.get("force_passthrough"):
            raise ValueError("force_sampling and force_passthrough are mutually exclusive")
```

- [ ] **Step 4: Run tests — all 12 must pass, no regressions**

```bash
pytest tests/test_preferences.py -v 2>&1 | tail -30
```

Expected: all pass (previously 337, now 349 total)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/preferences.py backend/tests/test_preferences.py
git commit -m "feat: add force_passthrough preference with mutual exclusion against force_sampling"
```

---

## Task 3: Health endpoint — `sampling_capable` field

**Files:**
- Modify: `backend/app/routers/health.py`

- [ ] **Step 1: Add all required imports and `sampling_capable` to the health response**

In `health.py`, add these three imports at the top (after existing imports). All three are required — none are currently present:

```python
import json as _json
from datetime import datetime, timedelta, timezone

from app.config import DATA_DIR
```

Then in the `health_check` function, before the `return` statement, add:

```python
    # MCP session sampling capability (written by mcp_server.py on tool calls)
    sampling_capable: bool | None = None
    mcp_session_path = DATA_DIR / "mcp_session.json"
    try:
        if mcp_session_path.exists():
            raw = _json.loads(mcp_session_path.read_text(encoding="utf-8"))
            written_at = datetime.fromisoformat(raw["written_at"])
            if datetime.now(timezone.utc) - written_at <= timedelta(minutes=30):
                sampling_capable = bool(raw["sampling_capable"])
    except Exception:
        logger.debug("Could not read mcp_session.json", exc_info=True)
```

Then add `"sampling_capable": sampling_capable` to the `return` dict:

```python
    return {
        "status": "healthy" if provider else "degraded",
        "version": __version__,
        "provider": provider.name if provider else None,
        "score_health": score_health,
        "avg_duration_ms": phase_durations if phase_durations else avg_duration_ms,
        "recent_errors": recent_errors,
        "sampling_capable": sampling_capable,
    }
```

- [ ] **Step 2: Verify health response manually**

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool | grep sampling
```

Expected: `"sampling_capable": null` (no mcp_session.json yet)

- [ ] **Step 3: Run full backend tests to confirm no regressions**

```bash
pytest --tb=short -q 2>&1 | tail -5
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/health.py
git commit -m "feat(health): add sampling_capable field from mcp_session.json"
```

---

## Task 4: MCP server — session capability write + `force_passthrough` routing

**Files:**
- Modify: `backend/app/mcp_server.py`

- [ ] **Step 1: Add module-level imports + `_write_mcp_session_caps()` helper**

First, add two imports to the existing import block at the top of `mcp_server.py`. Find the `import` section and add:

```python
import json as _json
from datetime import datetime, timezone
```

(`json` and `datetime`/`timezone` are not currently imported at module level.)

Then, after the `_resolve_workspace_guidance` function (around line 87), insert:

```python

def _write_mcp_session_caps(ctx: Context | None) -> None:
    """Detect sampling capability from MCP client and persist to mcp_session.json.

    Called at the start of every synthesis_optimize invocation, before routing.
    Silently skips if ctx is None or attribute lookup fails.
    """
    try:
        sampling_capable = (
            ctx is not None
            and hasattr(ctx, "session")
            and ctx.session is not None
            and ctx.session.client_params is not None
            and getattr(ctx.session.client_params.capabilities, "sampling", None) is not None
        )
        path = DATA_DIR / "mcp_session.json"
        path.write_text(
            _json.dumps({
                "sampling_capable": sampling_capable,
                "written_at": datetime.now(timezone.utc).isoformat(),
            }),
            encoding="utf-8",
        )
        logger.debug("mcp_session.json written: sampling_capable=%s", sampling_capable)
    except Exception:
        logger.debug("Could not write mcp_session.json", exc_info=True)
```

- [ ] **Step 2: Insert capability write and `force_passthrough` block in `synthesis_optimize`**

In `synthesis_optimize`, find the hoisted block (around line 407–410):

```python
    # ---- Hoist: single PreferencesService + workspace resolution for all paths ----
    prefs = PreferencesService(DATA_DIR)
    effective_strategy = strategy or prefs.get("defaults.strategy") or "auto"
    guidance = await _resolve_workspace_guidance(ctx, workspace_path)

    # ---- Force-sampling short-circuit (overrides local provider when enabled) ----
```

Replace with:

```python
    # ---- Hoist: single PreferencesService + workspace resolution for all paths ----
    prefs = PreferencesService(DATA_DIR)
    effective_strategy = strategy or prefs.get("defaults.strategy") or "auto"
    guidance = await _resolve_workspace_guidance(ctx, workspace_path)

    # ---- Detect and persist MCP client sampling capability (before routing) ----
    _write_mcp_session_caps(ctx)

    # ---- Force-passthrough short-circuit (explicit manual override, checked first) ----
    if prefs.get("pipeline.force_passthrough"):
        logger.info("synthesis_optimize: force_passthrough=True — returning passthrough template directly")
        assembled, strategy_name = assemble_passthrough_prompt(
            prompts_dir=PROMPTS_DIR,
            raw_prompt=prompt,
            strategy_name=effective_strategy,
            codebase_guidance=guidance,
        )
        trace_id = str(uuid.uuid4())
        async with async_session_factory() as db:
            pending = Optimization(
                id=str(uuid.uuid4()),
                raw_prompt=prompt,
                status="pending",
                trace_id=trace_id,
                provider="mcp_passthrough",
                strategy_used=strategy_name,
                task_type="general",
            )
            db.add(pending)
            await db.commit()
        return {
            "status": "pending_external",
            "trace_id": trace_id,
            "assembled_prompt": assembled,
            "strategy_used": strategy_name,
            "pipeline_mode": "passthrough",
            "instructions": (
                "force_passthrough=True. Process the assembled_prompt with your LLM, "
                "then call synthesis_save_result with the trace_id and the optimized output. "
                "Include optimized_prompt, changes_summary, task_type, strategy_used, and "
                "optionally scores (clarity, specificity, structure, faithfulness, conciseness — each 1-10)."
            ),
        }

    # ---- Force-sampling short-circuit (overrides local provider when enabled) ----
```

- [ ] **Step 3: Update the docstring to 5 execution paths**

Find the docstring of `synthesis_optimize` (around line 385). Replace:

```python
    """Run the full optimization pipeline on a prompt.

    Four execution paths (automatic selection):
    1. force_sampling=True + client supports sampling → 3-phase pipeline via IDE's LLM
    2. Local provider exists → full 3-phase internal pipeline
    3. No provider + client supports MCP sampling → 3-phase pipeline via IDE's LLM
    4. No provider + no sampling → returns assembled template for manual processing

    Set pipeline.force_sampling=True in preferences to always use path 1 regardless
    of whether a local provider is detected.
    """
```

with:

```python
    """Run the full optimization pipeline on a prompt.

    Five execution paths (checked in order):
    1. force_passthrough=True → assembled template returned immediately (manual processing)
    2. force_sampling=True + client supports sampling → 3-phase pipeline via IDE's LLM
    3. Local provider exists → full 3-phase internal pipeline
    4. No provider + client supports MCP sampling → 3-phase pipeline via IDE's LLM
    5. No provider + no sampling → assembled template for manual processing

    pipeline.force_passthrough and pipeline.force_sampling are mutually exclusive.
    """
```

- [ ] **Step 4: Restart services and smoke-test**

```bash
./init.sh restart 2>&1 | tail -3
```

After reconnecting MCP (`/mcp` in Claude Code), run a test call. With `force_passthrough=true`:
```bash
curl -s -X PATCH http://127.0.0.1:8000/api/preferences \
  -H "Content-Type: application/json" \
  -d '{"pipeline": {"force_passthrough": true, "force_sampling": false}}' | python3 -m json.tool
```

- [ ] **Step 5: Verify `mcp_session.json` is written**

```bash
cat data/mcp_session.json
```

Expected after any MCP tool call: `{"sampling_capable": false, "written_at": "..."}` (false for Claude Code CLI)

- [ ] **Step 6: Restore preferences to defaults**

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/preferences \
  -H "Content-Type: application/json" \
  -d '{"pipeline": {"force_passthrough": false, "force_sampling": false}}' | python3 -m json.tool
```

- [ ] **Step 7: Run full backend tests**

```bash
cd backend && source .venv/bin/activate && pytest --tb=short -q 2>&1 | tail -5
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/mcp_server.py
git commit -m "feat(mcp): write mcp_session.json caps, add force_passthrough routing (5-path docstring)"
```

---

## Task 5: Frontend — preferences store `force_passthrough` + mutual exclusion

**Files:**
- Modify: `frontend/src/lib/stores/preferences.svelte.ts`

- [ ] **Step 1: Add `force_passthrough` to `PipelinePrefs` interface**

Change:

```ts
export interface PipelinePrefs {
  enable_explore: boolean;
  enable_scoring: boolean;
  enable_adaptation: boolean;
  force_sampling: boolean;
}
```

to:

```ts
export interface PipelinePrefs {
  enable_explore: boolean;
  enable_scoring: boolean;
  enable_adaptation: boolean;
  force_sampling: boolean;
  force_passthrough: boolean;
}
```

- [ ] **Step 2: Add `force_passthrough` to DEFAULTS**

Change:

```ts
  pipeline: { enable_explore: true, enable_scoring: true, enable_adaptation: true, force_sampling: false },
```

to:

```ts
  pipeline: { enable_explore: true, enable_scoring: true, enable_adaptation: true, force_sampling: false, force_passthrough: false },
```

- [ ] **Step 3: Update `setPipelineToggle` to enforce mutual exclusion**

Change:

```ts
  async setPipelineToggle(key: string, value: boolean): Promise<void> {
    await this.update({ pipeline: { [key]: value } });
  }
```

to:

```ts
  async setPipelineToggle(key: string, value: boolean): Promise<void> {
    const patch: Record<string, boolean> = { [key]: value };
    // Enforce mutual exclusion: enabling one clears the other
    if (value) {
      if (key === 'force_sampling') patch['force_passthrough'] = false;
      if (key === 'force_passthrough') patch['force_sampling'] = false;
    }
    await this.update({ pipeline: patch });
  }
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx svelte-check --output machine 2>&1 | tail -5
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/stores/preferences.svelte.ts
git commit -m "feat(frontend): add force_passthrough to PipelinePrefs, mutual exclusion in setPipelineToggle"
```

---

## Task 6: Frontend — forge store `samplingCapable` + passthrough condition

**Files:**
- Modify: `frontend/src/lib/stores/forge.svelte.ts`

- [ ] **Step 1: Add `samplingCapable` state field**

In `forge.svelte.ts`, find the `noProvider` field (around line 36):

```ts
  /** Set by +page.svelte after health check — true when health.provider is null. */
  noProvider = $state(false);
```

Add below it:

```ts
  /** Set by +page.svelte after health check — null until health is fetched. */
  samplingCapable = $state<boolean | null>(null);
```

- [ ] **Step 2: Update `forge()` passthrough condition**

Find in `forge()` (around line 68):

```ts
    // Passthrough mode — no provider configured
    if (this.noProvider) {
```

Change to:

```ts
    // Passthrough mode — no provider, or force_passthrough preference enabled
    if (this.noProvider || preferencesStore.pipeline.force_passthrough) {
```

`preferencesStore` is not currently imported in `forge.svelte.ts`. Add this import at the top of the file:

```ts
import { preferencesStore } from '$lib/stores/preferences.svelte';
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx svelte-check --output machine 2>&1 | tail -5
```

Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/stores/forge.svelte.ts
git commit -m "feat(frontend): add samplingCapable field, forge() enters passthrough when force_passthrough=true"
```

---

## Task 7: Frontend — set `samplingCapable` from health

**Files:**
- Modify: `frontend/src/routes/app/+page.svelte`

- [ ] **Step 1: Set `samplingCapable` in health callback**

Find the health callback (around line 46–50):

```ts
    getHealth()
      .then((h) => {
        health = h;
        backendError = null;
        forgeStore.noProvider = !h.provider;
      })
```

Change to:

```ts
    getHealth()
      .then((h) => {
        health = h;
        backendError = null;
        forgeStore.noProvider = !h.provider;
        forgeStore.samplingCapable = h.sampling_capable ?? null;
      })
```

- [ ] **Step 2: Update `HealthResponse` type in API client if needed**

Check `frontend/src/lib/api/client.ts` for the `HealthResponse` type. Add `sampling_capable?: boolean | null` if not present:

```ts
export interface HealthResponse {
  status: string;
  version?: string;
  provider?: string | null;
  score_health?: any;
  avg_duration_ms?: any;
  recent_errors?: any;
  sampling_capable?: boolean | null;  // add this line
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx svelte-check --output machine 2>&1 | tail -5
```

Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/app/+page.svelte frontend/src/lib/api/client.ts
git commit -m "feat(frontend): propagate sampling_capable from health to forgeStore"
```

---

## Task 8: Navigator.svelte — update `force_sampling`, add `force_passthrough` + badge

**Files:**
- Modify: `frontend/src/lib/components/layout/Navigator.svelte`

- [ ] **Step 1: Update `force_sampling` toggle — disabled condition and tooltip**

Find the `force_sampling` toggle (around line 439–454). The current toggle is:

```svelte
<button
  class="toggle-track"
  class:toggle-track--on={preferencesStore.pipeline.force_sampling}
  onclick={() => preferencesStore.setPipelineToggle('force_sampling', !preferencesStore.pipeline.force_sampling)}
  role="switch"
  aria-checked={preferencesStore.pipeline.force_sampling}
  aria-label="Toggle Force IDE sampling"
  disabled={forgeStore.noProvider}
  title={forgeStore.noProvider ? 'No local provider to bypass — sampling is already the active path' : undefined}
  style={forgeStore.noProvider ? 'opacity: 0.4; cursor: not-allowed;' : undefined}
>
```

Replace with:

```svelte
<button
  class="toggle-track"
  class:toggle-track--on={preferencesStore.pipeline.force_sampling}
  onclick={() => preferencesStore.setPipelineToggle('force_sampling', !preferencesStore.pipeline.force_sampling)}
  role="switch"
  aria-checked={preferencesStore.pipeline.force_sampling}
  aria-label="Toggle Force IDE sampling"
  disabled={forgeStore.noProvider || forgeStore.samplingCapable === false || preferencesStore.pipeline.force_passthrough}
  title={
    forgeStore.noProvider
      ? 'No local provider to bypass — sampling is already the active path'
      : forgeStore.samplingCapable === false
        ? 'Your MCP client does not support sampling'
        : preferencesStore.pipeline.force_passthrough
          ? 'Disable Force passthrough first'
          : undefined
  }
  style={
    (forgeStore.noProvider || forgeStore.samplingCapable === false || preferencesStore.pipeline.force_passthrough)
      ? 'opacity: 0.4; cursor: not-allowed;'
      : undefined
  }
>
```

- [ ] **Step 2: Add `force_passthrough` toggle after the `force_sampling` toggle**

After the closing `</div>` of the `force_sampling` info-row (around line 454), add:

```svelte
            <!-- Force passthrough — manual override, always available except when sampling works -->
            <div class="info-row">
              <span class="info-key" title="Bypass all pipelines — returns assembled template for manual processing">Force passthrough</span>
              <button
                class="toggle-track"
                class:toggle-track--on={preferencesStore.pipeline.force_passthrough}
                onclick={() => preferencesStore.setPipelineToggle('force_passthrough', !preferencesStore.pipeline.force_passthrough)}
                role="switch"
                aria-checked={preferencesStore.pipeline.force_passthrough}
                aria-label="Toggle Force passthrough"
                disabled={forgeStore.samplingCapable === true || preferencesStore.pipeline.force_sampling}
                title={
                  forgeStore.samplingCapable === true
                    ? 'Sampling is available — use Force IDE sampling instead'
                    : preferencesStore.pipeline.force_sampling
                      ? 'Disable Force IDE sampling first'
                      : undefined
                }
                style={
                  (forgeStore.samplingCapable === true || preferencesStore.pipeline.force_sampling)
                    ? 'opacity: 0.4; cursor: not-allowed;'
                    : undefined
                }
              >
                <span class="toggle-thumb"></span>
              </button>
            </div>
```

- [ ] **Step 3: Add PASSTHROUGH badge in the Defaults section**

Find the existing SAMPLING badge block (around line 474–478):

```svelte
            {#if preferencesStore.pipeline.force_sampling && !forgeStore.noProvider}
              <div class="info-row">
                <span class="lean-badge" style="color: var(--color-accent, #00e5ff); border-color: var(--color-accent, #00e5ff);">SAMPLING</span>
              </div>
            {/if}
```

Add immediately after:

```svelte
            {#if preferencesStore.pipeline.force_passthrough}
              <div class="info-row">
                <span class="lean-badge" style="color: var(--color-warn, #f59e0b); border-color: var(--color-warn, #f59e0b);">PASSTHROUGH</span>
              </div>
            {/if}
```

- [ ] **Step 4: Verify TypeScript / Svelte compiles**

```bash
cd frontend && npx svelte-check --output machine 2>&1 | tail -5
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/layout/Navigator.svelte
git commit -m "feat(frontend): update force_sampling disabled logic, add force_passthrough toggle + PASSTHROUGH badge"
```

---

## Task 9: Changelog + push

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Add changelog entries**

Under `## Unreleased → Added`, append:

```markdown
- Added runtime MCP sampling capability detection — `force_sampling` toggle disabled when connected MCP client does not advertise `sampling/createMessage` (detected via `data/mcp_session.json`, surfaced on `/api/health` as `sampling_capable`)
- Added `pipeline.force_passthrough` preference toggle — forces `synthesis_optimize` to return the assembled passthrough template immediately, and makes the frontend forge enter passthrough mode; mutually exclusive with `force_sampling`
```

- [ ] **Step 2: Run full backend test suite one final time**

```bash
cd backend && source .venv/bin/activate && pytest --tb=short -q 2>&1 | tail -5
```

Expected: all pass (349 total)

- [ ] **Step 3: Run final frontend type check**

```bash
cd frontend && npx svelte-check --output machine 2>&1 | tail -5
```

Expected: 0 errors

- [ ] **Step 4: Final commit + push**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: add sampling detection + force_passthrough toggle changelog entries"
git push origin main
```
