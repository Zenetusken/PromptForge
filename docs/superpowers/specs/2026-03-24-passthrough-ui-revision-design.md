# Passthrough UI Revision — Design Spec

**Goal:** Revise the passthrough-mode UI to reflect unified context enrichment capabilities shipped in v0.3.1. The Navigator pipeline section morphs in-place (rather than hiding sections), the PassthroughGuide modal feature matrix is updated, and stale references are corrected throughout.

**Scope:** Frontend only — no backend changes. Touches Navigator, PassthroughGuide modal, and one API client cleanup.

---

## 1. Navigator Pipeline Section — Tier Morphing

### Problem

When passthrough mode is active, the Navigator hides the MODELS, EFFORT, and pipeline feature toggle sections entirely. After v0.3.1 shipped unified context enrichment, several features now apply to passthrough (heuristic analysis, codebase context from repo index, pattern auto-injection, adaptation state, heuristic scoring) but the UI gives no indication they exist.

### Design

The pipeline section uses the **same structural skeleton** in all tiers. When passthrough is active, sections morph in-place rather than disappearing. This reduces cognitive load — the user sees the same layout structure regardless of tier.

**Section mapping (internal/sampling → passthrough):**

| Internal/Sampling | Passthrough | Behavior |
|---|---|---|
| **PIPELINE** (2 toggles) | **PIPELINE** (2 toggles) | Identical — always interactive |
| **DEFAULTS** (strategy + badge) | **DEFAULTS** (strategy + badge) | Identical — always interactive |
| **MODELS** (3 model selectors) | **CONTEXT** (4 items) | Morphs — read-only indicators + 1 live toggle |
| Explore / Scoring / Adaptation toggles | _(absorbed into CONTEXT + SCORING)_ | Toggles replaced by their passthrough equivalents |
| **EFFORT** (3 effort selectors) | **SCORING** (1 read-only indicator) | Morphs — single item |

### CONTEXT section (replaces MODELS + feature toggles)

Four items, ordered by pipeline phase:

| Label | Value | Interactive? | Notes |
|---|---|---|---|
| Analysis | `heuristic` | Read-only | `HeuristicAnalyzer` runs zero-LLM classification |
| Codebase | `via index` or `no repo` | Read-only | `via index` when GitHub repo is linked, `no repo` (dimmed) when not |
| Patterns | `auto-injected` | Read-only | `auto_inject_patterns()` runs in passthrough prepare path |
| Adaptation | Toggle switch | **Live toggle** | `enable_adaptation` preference is respected by `ContextEnrichmentService.enrich()` in passthrough mode |

### SCORING section (replaces EFFORT)

Single item:

| Label | Value | Interactive? |
|---|---|---|
| Mode | `heuristic` | Read-only |

### Visual treatment

- Section headers (CONTEXT, SCORING) use `var(--color-neon-yellow)` — the established passthrough accent color — instead of the default dim color used for MODELS/EFFORT headers.
- Read-only value labels use `var(--color-neon-yellow)` with `font-size: 10px` for the value text.
- Read-only row labels use `var(--color-dim)` (the existing `#666680` dim style).
- The Adaptation toggle uses yellow accent (matching `Force passthrough` toggle style).
- LEAN MODE badge is hidden in passthrough (not applicable).

### Codebase indicator — repo-linked detection

The `Codebase` row needs to know if a GitHub repo is linked. The existing `githubStore.linkedRepo` reactive state provides this. When `linkedRepo` is non-null, show `via index`; otherwise show `no repo` in dimmed text.

### Implementation approach

In `Navigator.svelte`, the existing `{#if !routing.isPassthrough}` blocks that hide MODELS, toggles, and EFFORT are replaced with `{#if routing.isPassthrough} ... {:else} ... {/if}` blocks that render the passthrough variant in the same position.

---

## 2. PassthroughGuide Modal — Feature Matrix Fix

### Problem

Three rows in the feature matrix are stale after v0.3.1 unified context enrichment:

| Feature | Current (stale) | Actual capability |
|---|---|---|
| Score phase | `Heuristic` | Heuristic OR Hybrid (when external LLM provides scores) |
| Codebase explore | `Roots only` | Roots + curated context from pre-built repo index |
| Pattern injection | `✗` (cross, dimmed) | `✓` Auto-injected via `auto_inject_patterns()` |

### Design

Update the three rows in the `FEATURES` array in `PassthroughGuide.svelte`:

1. **Score phase** passthrough column: `Heuristic` → `Heuristic / Hybrid` — no footnote needed, the column header provides context.
2. **Codebase explore** passthrough column: `Roots only` → `Roots + index` — concise label indicating both workspace roots and repo index context.
3. **Pattern injection** passthrough column: cross icon (dimmed) → checkmark with yellow color — matching the Adaptation state row style. No label needed since the checkmark matches internal/sampling.

### Workflow step 1 description update

Current text in the step 1 detail:
> "Strategy template, scoring rubric, workspace context, and adaptation state are injected into a single optimized instruction."

Updated to:
> "Strategy template, scoring rubric, workspace context, codebase context, applied patterns, and adaptation state are assembled into a single optimized instruction."

The blockquote ("All context enrichment happens server-side. The assembled prompt appears in the editor.") remains unchanged.

### "Why Passthrough" intro — no change

The current text ("Scores, taxonomy, and adaptation all still work") is accurate and deliberately general enough to not require updates when enrichment features change.

---

## 3. PassthroughView Editor — No Changes

The PassthroughView component is well-structured and correct. The enrichment improvements are server-side and transparent to the user — they receive a richer assembled prompt without the view needing to describe its contents.

No changes to:
- Header ("MANUAL PASSTHROUGH" + strategy name + `?` button)
- Assembled prompt panel (read-only `<pre>` with COPY button)
- Optimized result panel (editable `<textarea>`)
- Save bar (changes summary input + SAVE button)

---

## 4. Inspector, StatusBar, EditorGroups — No Changes

All passthrough-specific behavior is already correct:

- **Inspector**: Shows "heuristic (passthrough)" scoring label, hides `web_passthrough` provider string, suppresses refinement timeline.
- **StatusBar**: Shows "passthrough..." in yellow accent during flow. System section scoring label dynamically shows "heuristic".
- **EditorGroups**: `forgeStore.status === 'passthrough'` correctly swaps PromptEdit for PassthroughView. Refinement suppression for passthrough results via `isPassthroughResult()` check.

---

## 5. Cleanup

### Remove deprecated `preparePassthrough()` API function

In `frontend/src/lib/api/client.ts`, the `preparePassthrough()` function is marked `@deprecated` with comment "Use unified POST /api/optimize — backend routes to passthrough via SSE". The function is unused by the current UI flow (which goes through `optimizeSSE()` → SSE `passthrough` event). Remove it.

### Keep PromptEdit "PREPARE" button label

The button text switches to "PREPARE" when `isPassthroughMode` is true. Although the user rarely sees it (EditorGroups swaps to PassthroughView at the same time), keep it as a defensive label for render timing edge cases.

---

## Files Changed

| File | Change |
|---|---|
| `frontend/src/lib/components/layout/Navigator.svelte` | Replace hide/show blocks with morphing CONTEXT + SCORING sections |
| `frontend/src/lib/components/shared/PassthroughGuide.svelte` | Fix 3 feature matrix rows, update step 1 description |
| `frontend/src/lib/api/client.ts` | Remove deprecated `preparePassthrough()` function |

## Files Unchanged

- `PassthroughView.svelte` — no changes needed
- `Inspector.svelte` — already correct
- `StatusBar.svelte` — already correct
- `EditorGroups.svelte` — already correct
- `routing.svelte.ts` — already exposes `isPassthrough` convenience
- `passthrough-guide.svelte.ts` — store logic unchanged

## Testing

- **Navigator morphing**: Toggle `Force passthrough` on/off and verify MODELS↔CONTEXT and EFFORT↔SCORING sections swap in-place. Verify Adaptation toggle is interactive. Verify Codebase shows `via index` when repo linked, `no repo` when not.
- **Feature matrix**: Open PassthroughGuide modal (`?` button or toggle enable), scroll to feature matrix, verify Score phase shows "Heuristic / Hybrid", Codebase explore shows "Roots + index", Pattern injection shows checkmark.
- **Workflow step 1**: Expand step 1 in the modal, verify updated description mentions codebase context and applied patterns.
- **API client**: Verify no imports reference `preparePassthrough` anywhere in the frontend.
- **Existing passthrough flow**: Full end-to-end passthrough optimization (prepare → copy → paste to external LLM → paste back → save) still works.
- **Existing tests**: `Navigator.test.ts`, `PassthroughGuide.test.ts`, `PassthroughView.test.ts` updated or extended for new behavior.
