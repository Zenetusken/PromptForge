# Force Sampling Toggle Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `pipeline.force_sampling` boolean preference that, when enabled, routes `synthesis_optimize` through MCP sampling (IDE's LLM) even when a local provider is detected.

**Architecture:** Single boolean added to the existing `pipeline.*` preference group. MCP server reads it per-call via a hoisted `PreferencesService` instance and short-circuits to `_run_sampling_pipeline()` before normal routing. Frontend adds one toggle and one conditional badge, both keyed off the same preference.

**Tech Stack:** Python 3.12 / FastAPI / FastMCP, Svelte 5 (runes), TypeScript, pytest

---

## File Map

| File | Change |
|---|---|
| `backend/app/services/preferences.py` | Add `force_sampling: False` to `DEFAULTS`; extend two hardcoded tuples in `_sanitize` and `_validate` |
| `backend/tests/test_preferences.py` | Add tests for `force_sampling` default, sanitize, validate, and patch |
| `backend/app/mcp_server.py` | Hoist `PreferencesService` + `_resolve_workspace_guidance`; add force-sampling short-circuit; update docstring |
| `frontend/src/lib/stores/preferences.svelte.ts` | Add `force_sampling: boolean` to `PipelinePrefs` interface and `DEFAULTS` |
| `frontend/src/lib/components/layout/Navigator.svelte` | Add `force_sampling` toggle (after existing loop) and `sampling` badge in Defaults section |
| `docs/CHANGELOG.md` | Add `Added` entry under `## Unreleased` |

---

## Task 1: Backend — preferences service

**Files:**
- Modify: `backend/app/services/preferences.py:36-51` (DEFAULTS), `~165` (_sanitize tuple), `~196` (_validate tuple)
- Test: `backend/tests/test_preferences.py`

- [ ] **Step 1.1: Write failing tests**

Add this class to `backend/tests/test_preferences.py` (after the existing `TestFileRecovery` class):

```python
# ── TestForceSampling ─────────────────────────────────────────────────


class TestForceSampling:
    def test_default_is_false(self, svc: PreferencesService) -> None:
        prefs = svc.load()
        assert prefs["pipeline"]["force_sampling"] is False

    def test_can_be_patched_true(self, svc: PreferencesService) -> None:
        result = svc.patch({"pipeline": {"force_sampling": True}})
        assert result["pipeline"]["force_sampling"] is True

    def test_can_be_patched_false(self, svc: PreferencesService) -> None:
        svc.patch({"pipeline": {"force_sampling": True}})
        result = svc.patch({"pipeline": {"force_sampling": False}})
        assert result["pipeline"]["force_sampling"] is False

    def test_non_boolean_rejected_by_validate(self, svc: PreferencesService) -> None:
        prefs = svc.load()
        prefs["pipeline"]["force_sampling"] = "yes"
        with pytest.raises(ValueError, match="force_sampling"):
            svc.save(prefs)

    def test_non_boolean_sanitized_to_default(
        self, svc: PreferencesService, prefs_file: Path
    ) -> None:
        import json as _json
        prefs_file.write_text(_json.dumps({
            "schema_version": 1,
            "pipeline": {"force_sampling": "yes"},
        }))
        prefs = svc.load()
        assert prefs["pipeline"]["force_sampling"] is False

    def test_missing_key_merges_to_false(
        self, svc: PreferencesService, prefs_file: Path
    ) -> None:
        """Older preferences.json without force_sampling silently gets False."""
        import json as _json
        prefs_file.write_text(_json.dumps({
            "schema_version": 1,
            "pipeline": {
                "enable_explore": True,
                "enable_scoring": True,
                "enable_adaptation": True,
            },
        }))
        prefs = svc.load()
        assert prefs["pipeline"]["force_sampling"] is False

    def test_get_dot_path(self, svc: PreferencesService) -> None:
        snap = svc.load()
        assert svc.get("pipeline.force_sampling", snapshot=snap) is False
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_preferences.py::TestForceSampling -v
```

Expected: all 7 tests FAIL — `force_sampling` key does not exist yet.

- [ ] **Step 1.3: Add `force_sampling` to DEFAULTS**

> **Order matters:** Steps 1.3 → 1.4 → 1.5 must be applied in this exact sequence. `_sanitize` reads `DEFAULTS["pipeline"][toggle]` directly (line ~168 of `preferences.py`) to get the fallback value. If the `_sanitize` or `_validate` tuple is extended before the key exists in `DEFAULTS`, a `KeyError` will occur at runtime.

In `backend/app/services/preferences.py`, find `DEFAULTS` (line ~36). Change:

```python
"pipeline": {
    "enable_explore": True,
    "enable_scoring": True,
    "enable_adaptation": True,
},
```

to:

```python
"pipeline": {
    "enable_explore": True,
    "enable_scoring": True,
    "enable_adaptation": True,
    "force_sampling": False,
},
```

- [ ] **Step 1.4: Extend `_sanitize` tuple**

In `_sanitize` (line ~165), change:

```python
for toggle in ("enable_explore", "enable_scoring", "enable_adaptation"):
```

to:

```python
for toggle in ("enable_explore", "enable_scoring", "enable_adaptation", "force_sampling"):
```

- [ ] **Step 1.5: Extend `_validate` tuple**

In `_validate` (line ~196), change:

```python
for toggle in ("enable_explore", "enable_scoring", "enable_adaptation"):
```

to:

```python
for toggle in ("enable_explore", "enable_scoring", "enable_adaptation", "force_sampling"):
```

- [ ] **Step 1.6: Run tests to verify they pass**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_preferences.py -v
```

Expected: all tests PASS (including the existing suite — backwards compatibility check).

- [ ] **Step 1.7: Commit**

```bash
git add backend/app/services/preferences.py backend/tests/test_preferences.py
git commit -m "feat: add pipeline.force_sampling preference with validation"
```

---

## Task 2: MCP server — routing refactor + force-sampling short-circuit

**Files:**
- Modify: `backend/app/mcp_server.py` — `synthesis_optimize` function (lines ~377–539)

No new test file — `synthesis_optimize` integration-tests against a real MCP session and is verified manually (see Step 2.5).

- [ ] **Step 2.1: Rewrite `synthesis_optimize` with hoisted prefs/guidance and force-sampling path**

Replace the entire `synthesis_optimize` function body (everything after the length validation, up to and including the final `return`) with:

```python
    if len(prompt) < 20:
        raise ValueError(
            "Prompt too short (%d chars). Minimum is 20 characters." % len(prompt)
        )
    if len(prompt) > 200000:
        raise ValueError(
            "Prompt too long (%d chars). Maximum is 200,000 characters." % len(prompt)
        )

    provider = _provider

    # ---- Hoist: single PreferencesService + workspace resolution for all paths ----
    prefs = PreferencesService(DATA_DIR)
    effective_strategy = strategy or prefs.get("defaults.strategy") or "auto"
    guidance = await _resolve_workspace_guidance(ctx, workspace_path)

    # ---- Force-sampling short-circuit (overrides local provider when enabled) ----
    if prefs.get("pipeline.force_sampling") and ctx and hasattr(ctx, "session") and ctx.session:
        logger.info("synthesis_optimize: force_sampling=True — attempting sampling pipeline")
        try:
            return await _run_sampling_pipeline(
                ctx, prompt,
                effective_strategy if effective_strategy != "auto" else None,
                guidance,
            )
        except Exception as exc:
            logger.info(
                "force_sampling requested but sampling failed, falling through: %s",
                type(exc).__name__,
            )

    # ---- No local provider: try sampling, then fall back to passthrough ----
    if not provider:
        # Try MCP sampling (3-phase pipeline via IDE's LLM)
        if ctx and hasattr(ctx, "session") and ctx.session:
            try:
                logger.info("synthesis_optimize: no provider — attempting sampling pipeline")
                return await _run_sampling_pipeline(
                    ctx, prompt, effective_strategy if effective_strategy != "auto" else None, guidance,
                )
            except Exception as exc:
                logger.info(
                    "Sampling not supported by client, falling back to passthrough: %s",
                    type(exc).__name__,
                )

        # Fallback: single-shot passthrough template
        logger.info("synthesis_optimize: no provider — using passthrough template")

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
            "instructions": (
                "No local LLM provider detected. Process the assembled_prompt "
                "with your LLM, then call synthesis_save_result with the trace_id "
                "and the optimized output. Include optimized_prompt, changes_summary, "
                "task_type, strategy_used, and optionally scores "
                "(clarity, specificity, structure, faithfulness, conciseness — each 1-10)."
            ),
        }

    start = time.monotonic()

    logger.info(
        "synthesis_optimize called: prompt_len=%d strategy=%s repo=%s",
        len(prompt), effective_strategy, repo_full_name,
    )

    async with async_session_factory() as db:
        orchestrator = PipelineOrchestrator(prompts_dir=PROMPTS_DIR)

        result = None
        async for event in orchestrator.run(
            raw_prompt=prompt,
            provider=provider,
            db=db,
            strategy_override=effective_strategy if effective_strategy != "auto" else None,
            codebase_guidance=guidance,
            repo_full_name=repo_full_name,
        ):
            if event.event == "optimization_complete":
                result = event.data
            elif event.event == "error":
                error_msg = event.data.get("error", "Pipeline failed")
                logger.error("synthesis_optimize pipeline error: %s", error_msg)
                raise ValueError(error_msg)

        if not result:
            raise ValueError(
                "Pipeline completed but produced no result. Check server logs for details."
            )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "synthesis_optimize completed in %dms: optimization_id=%s strategy=%s",
            elapsed_ms, result.get("id", ""), result.get("strategy_used", ""),
        )

        # Notify backend event bus via HTTP (MCP runs in a separate process)
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://127.0.0.1:8000/api/events/_publish",
                    json={
                        "event_type": "optimization_created",
                        "data": {
                            "id": result.get("id", ""),
                            "task_type": result.get("task_type", ""),
                            "strategy_used": result.get("strategy_used", ""),
                            "overall_score": result.get("overall_score"),
                            "provider": provider.name,
                            "status": "completed",
                        },
                    },
                    timeout=5.0,
                )
        except Exception:
            logger.debug("Failed to notify backend event bus", exc_info=True)

        return {
            "optimization_id": result.get("id", ""),
            "optimized_prompt": result.get("optimized_prompt", ""),
            "task_type": result.get("task_type", ""),
            "strategy_used": result.get("strategy_used", ""),
            "changes_summary": result.get("changes_summary", ""),
            "scores": result.get("optimized_scores", result.get("scores", {})),
            "original_scores": result.get("original_scores", {}),
            "score_deltas": result.get("score_deltas", {}),
            "scoring_mode": "independent",
        }
```

- [ ] **Step 2.2: Update the docstring**

Change the docstring of `synthesis_optimize` from:

```python
    """Run the full optimization pipeline on a prompt.

    Three execution paths (automatic selection):
    1. Local provider exists → full 3-phase internal pipeline
    2. No provider + client supports MCP sampling → 3-phase pipeline via IDE's LLM
    3. No provider + no sampling → returns assembled template for manual processing
    """
```

to:

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

- [ ] **Step 2.3: Run the backend test suite to confirm no regressions**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2.4: Smoke-test via ruff**

```bash
cd backend && source .venv/bin/activate && ruff check app/mcp_server.py
```

Expected: no errors.

- [ ] **Step 2.5: Manual smoke test**

```bash
# Verify force_sampling=False (default) still uses internal pipeline
curl -s http://127.0.0.1:8000/api/preferences | python3 -c "import sys,json; p=json.load(sys.stdin); print('force_sampling:', p['pipeline'].get('force_sampling'))"
# Expected: force_sampling: False
```

Then call `synthesis_optimize` from Claude Code and check `data/mcp.log` — should NOT see `force_sampling=True` log line.

- [ ] **Step 2.6: Commit**

```bash
git add backend/app/mcp_server.py
git commit -m "refactor(mcp): hoist prefs/guidance in synthesis_optimize, add force_sampling short-circuit"
```

---

## Task 3: Frontend — preferences store

**Files:**
- Modify: `frontend/src/lib/stores/preferences.svelte.ts`

- [ ] **Step 3.1: Add `force_sampling` to `PipelinePrefs` interface**

In `frontend/src/lib/stores/preferences.svelte.ts`, change:

```ts
export interface PipelinePrefs {
  enable_explore: boolean;
  enable_scoring: boolean;
  enable_adaptation: boolean;
}
```

to:

```ts
export interface PipelinePrefs {
  enable_explore: boolean;
  enable_scoring: boolean;
  enable_adaptation: boolean;
  force_sampling: boolean;
}
```

- [ ] **Step 3.2: Add `force_sampling` to DEFAULTS**

Change:

```ts
  pipeline: { enable_explore: true, enable_scoring: true, enable_adaptation: true },
```

to:

```ts
  pipeline: { enable_explore: true, enable_scoring: true, enable_adaptation: true, force_sampling: false },
```

- [ ] **Step 3.3: Verify TypeScript compiles**

```bash
cd frontend && npm run check 2>&1 | tail -20
```

Expected: no errors mentioning `force_sampling` or `PipelinePrefs`.

- [ ] **Step 3.4: Commit**

```bash
git add frontend/src/lib/stores/preferences.svelte.ts
git commit -m "feat(frontend): add force_sampling to PipelinePrefs interface and store defaults"
```

---

## Task 4: Frontend — Navigator toggle + sampling badge

**Files:**
- Modify: `frontend/src/lib/components/layout/Navigator.svelte` (lines ~410–458)

- [ ] **Step 4.1: Add the `force_sampling` toggle after the existing pipeline toggles**

In `Navigator.svelte`, find the pipeline section (after the `{#if preferencesStore.isLeanMode}` block, before `</div></div>` closing the pipeline sub-section). The current structure ends at:

```svelte
            {#if preferencesStore.isLeanMode}
              <div class="info-row">
                <span class="lean-badge">LEAN MODE</span>
              </div>
            {/if}
          </div>
        </div>
```

Add the `force_sampling` toggle **before** the closing `</div></div>` of the pipeline sub-section, after the `{/if}` for lean mode:

```svelte
            <!-- Force sampling — rendered separately for disabled-state support -->
            <div class="info-row">
              <span class="info-key" title="Use IDE's LLM for the 3-phase pipeline via MCP sampling">Force IDE sampling</span>
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
                <span class="toggle-thumb"></span>
              </button>
            </div>
```

- [ ] **Step 4.2: Add the `sampling` badge in the Defaults section**

Find the closing of the Defaults `info-block` div (lines ~456–458). It currently looks like:

```svelte
          </div>
        </div>
```

**Insert** the badge block immediately before that `</div></div>` sequence, so the result becomes:

```svelte
            {#if preferencesStore.pipeline.force_sampling && !forgeStore.noProvider}
              <div class="info-row">
                <span class="lean-badge" style="color: var(--color-accent, #00e5ff); border-color: var(--color-accent, #00e5ff);">SAMPLING</span>
              </div>
            {/if}
          </div>
        </div>
```

Do **not** remove or replace the existing strategy `<select>` row. This is a pure insertion after the last existing `info-row` inside the Defaults `info-block`.

- [ ] **Step 4.3: Verify TypeScript / Svelte compiles**

```bash
cd frontend && npm run check 2>&1 | tail -20
```

Expected: no errors.

- [ ] **Step 4.4: Verify UI visually**

Open `http://localhost:5199`, navigate to Settings. Confirm:
- "Force IDE sampling" toggle appears in the Pipeline section below Adaptation
- Toggle is disabled (greyed out, cursor: not-allowed) when no provider is detected
- Toggling it on shows the `SAMPLING` badge in the Defaults section next to Strategy
- Toggling it off hides the badge
- Toggle state persists on page refresh (reloaded from `GET /api/preferences`)

- [ ] **Step 4.5: Commit**

```bash
git add frontend/src/lib/components/layout/Navigator.svelte
git commit -m "feat(frontend): add Force IDE sampling toggle and SAMPLING badge to Navigator"
```

---

## Task 5: CHANGELOG

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 5.1: Add entry under `## Unreleased → Added`**

Add this line to `docs/CHANGELOG.md` under `## Unreleased` → `### Added`:

```
- Added `pipeline.force_sampling` preference toggle — forces `synthesis_optimize` through the MCP sampling pipeline (IDE's LLM) even when a local provider is detected; gracefully falls through to the local provider if sampling fails
```

- [ ] **Step 5.2: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: add force_sampling toggle changelog entry"
```

---

## Final verification

- [ ] Run full backend test suite: `cd backend && source .venv/bin/activate && pytest tests/ -v` — all pass
- [ ] Run frontend type check: `cd frontend && npm run check` — no errors
- [ ] End-to-end smoke test: enable `force_sampling` in the UI, call `synthesis_optimize` from Claude Code, confirm `data/mcp.log` shows `force_sampling=True — attempting sampling pipeline`
