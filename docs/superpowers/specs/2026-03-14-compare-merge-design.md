# Compare & Merge — Deep Analysis + Intelligent Prompt Synthesis

## Context

The history sidebar has a "Compare" button that appears when exactly two optimizations are selected. Currently it's a non-functional stub — it creates a placeholder prompt tab with static text. Meanwhile, `BranchCompare.svelte` (for refinement branches within a single optimization) is fully built with score tables, DiffView, and winner selection.

This spec designs a cross-optimization comparison engine with an intelligent merge workflow that combines the best of two optimized prompts into a new entry, guided by deep analytical insights.

## Goals

1. Compare any two optimization records — same prompt re-forged, different strategies, evolved prompts, or entirely unrelated prompts
2. Surface data-science-grade insights that a prompt engineer would want (score patterns, structural analysis, strategy effectiveness, efficiency metrics, adaptation impact)
3. Merge the best qualities of both into a single new prompt using the full intelligence payload as LLM guidance
4. Enforce a clean commitment gate: accept the merge (parents archived) or discard it (parents untouched)

## Non-Goals

- Comparing 3+ items simultaneously (pairwise only)
- Auto-merging without user review
- Backend-side prompt execution (the merged prompt is saved as raw text, user forges it separately)

---

## Architecture

### Approach: Modal Dialog (matches BranchCompare pattern)

A full-screen modal overlay with three sequential phases. The modal naturally enforces the commitment gate — user must act before returning to the app. Reuses the established BranchCompare interaction pattern so users have a consistent mental model.

---

## Section 1: Situation Detection — Backend-Powered Deep Comparison Engine

### New Endpoint: `GET /api/compare?a={id}&b={id}`

The backend fetches both full `Optimization` records, computes classification and structured analysis, and returns a single payload. One round-trip, all intelligence server-side.

### Classification Algorithm

```
1. Semantic similarity via embedding_service.embed_single() on both raw_prompts
   cosine_similarity(embed(A.raw_prompt), embed(B.raw_prompt))
   >= 0.85 = HIGH, 0.45-0.84 = MODERATE, < 0.45 = LOW

2. Structural signals (existing DB fields, no extra computation):
   same_framework:   A.primary_framework == B.primary_framework
   same_task_type:    A.task_type == B.task_type
   same_repo:         A.linked_repo_full_name == B.linked_repo_full_name
   has_context_delta: one has repo context, other doesn't
   time_gap:          abs(A.created_at - B.created_at)

3. Classify:
   similarity HIGH + same_framework        → REFORGE
   similarity HIGH + different framework   → STRATEGY
   similarity MODERATE                     → EVOLVED
   similarity LOW                          → CROSS

4. Context modifiers (enrich, don't reclassify):
   "repo_added":     one has codebase context, other doesn't
   "repo_changed":   different repos linked
   "adapted":        time_gap > 1hr AND feedback exists between timestamps
   "complexity_shift": A.complexity != B.complexity
```

Fallback: if embedding model unavailable, use normalized Levenshtein ratio (`1 - (edit_distance / max_len)`). Threshold mapping for Levenshtein: >= 0.80 = HIGH, 0.35-0.79 = MODERATE, < 0.35 = LOW (shifted lower than cosine thresholds because Levenshtein penalizes word reordering that cosine similarity would tolerate).

### Situation Chromatic Encoding

| Situation | Badge Color | Neon Token |
|---|---|---|
| REFORGE | neon-green | `#22ff88` |
| STRATEGY | neon-purple | `#a855f7` |
| EVOLVED | neon-yellow | `#fbbf24` |
| CROSS | neon-blue | `#4d8eff` |

### Data Extraction Per Optimization (All From Existing DB Columns)

| Category | Fields | Insight Value |
|---|---|---|
| **Prompt metrics** | `raw_prompt` length, word count, sentence count | Structural profile |
| **Output metrics** | `optimized_prompt` length, expansion ratio | Transformation magnitude |
| **Scores** | 5 dimensions + `overall_score` | Quality profile |
| **Validation** | `is_improvement`, `verdict`, `issues[]`, `validation_quality` | Validator flags |
| **Analysis** | `task_type`, `complexity`, `weaknesses[]`, `strengths[]`, `changes_made[]` | Analyzer classification |
| **Strategy** | `primary_framework`, `secondary_frameworks[]`, `strategy_rationale`, `strategy_source`, `approach_notes`, `active_guardrails[]` | Decision reasoning |
| **Context** | `linked_repo_full_name`, `codebase_context_snapshot`, `per_instruction_compliance[]` | External context |
| **Performance** | `duration_ms`, `stage_durations{}`, token counts, `estimated_cost_usd` | Efficiency |
| **Adaptation** | `adaptation_snapshot`, `retry_history[]`, `refinement_turns`, `branch_count` | Feedback loop influence |
| **Semantic** | Embedding cosine similarity | Conceptual relationship |

### Insight Categories (8 computed from A vs B deltas)

1. **Score Analysis** — Per-dimension deltas, winner dots, volatility, ceiling detection (both >= 9), floor detection (both < 5)
2. **Structural Analysis** — Input/output length delta, expansion ratio delta, complexity shift
3. **Strategy Analysis** — Framework effectiveness, switch impact, guardrail presence, selection source confidence
4. **Context Analysis** — Repo context delta, instruction compliance delta, codebase coverage
5. **Efficiency Analysis** — Duration delta, token efficiency (score/token ratio), cost delta, stage bottleneck
6. **Adaptation Analysis** — Feedback count between runs, weight shifts, guardrail evolution, framework preference drift
7. **Validation Analysis** — Verdict comparison, issues overlap, changes_made diff
8. **Pattern Insights** (CROSS only) — Structural choices correlated with scores, framework suitability by task type, optimal length ranges

### Response Payload

```json
{
  "situation": "STRATEGY",
  "situation_label": "Framework head-to-head",
  "insight_headline": "Same prompt: CO-STAR vs RISEN — +1.2 overall, clarity +2.0, faithfulness -0.5",
  "modifiers": ["adapted", "3 feedbacks"],

  "a": { /* full OptimizationRecord */ },
  "b": { /* full OptimizationRecord */ },

  "scores": {
    "dimensions": ["clarity", "faithfulness", "specificity", "structure", "conciseness"],
    "a_scores": { ... },
    "b_scores": { ... },
    "deltas": { ... },
    "overall_delta": 0.8,
    "winner": "a",
    "ceilings": [],
    "floors": ["conciseness"]
  },

  "structural": {
    "a_input_words": 45, "b_input_words": 120,
    "a_output_words": 144, "b_output_words": 252,
    "a_expansion": 3.2, "b_expansion": 2.1,
    "a_complexity": "basic", "b_complexity": "intermediate"
  },

  "efficiency": {
    "a_duration_ms": 4100, "b_duration_ms": 6500,
    "a_tokens": 2100, "b_tokens": 2600,
    "a_cost": 0.008, "b_cost": 0.011,
    "a_score_per_token": 3.8, "b_score_per_token": 2.8
  },

  "strategy": {
    "a_framework": "CO-STAR", "a_source": "llm", "a_rationale": "...",
    "a_guardrails": ["clarity-focus", "no-jargon"],
    "b_framework": "RISEN", "b_source": "heuristic", "b_rationale": "...",
    "b_guardrails": []
  },

  "adaptation": {
    "feedbacks_between": 3,
    "weight_shifts": { "clarity": 0.08 },
    "guardrails_added": ["clarity-focus"]
  },

  "top_insights": [
    "CO-STAR's Context section forces grounded responses — drives the clarity gap. Transferable.",
    "Both 7.0 conciseness — add word-limit instruction to break the ceiling.",
    "B's codebase context: +1.2s latency for +0.5 specificity — explore ROI marginal."
  ],

  "guidance": {
    "headline": "CO-STAR's context framing drove +2.0 clarity; RISEN preserved intent better",
    "merge_suggestion": "Combine CO-STAR's Context/Situation with RISEN's role anchoring",
    "strengths_a": ["clarity", "structure", "specificity"],
    "strengths_b": ["faithfulness"],
    "persistent_weaknesses": ["conciseness"],
    "actionable": [
      "The clarity gap is structural: CO-STAR's explicit Context section forces grounding.",
      "Both 7.0 conciseness — consider word-limit constraint instruction.",
      "B's repo context added 1.2s for +0.5 specificity — marginal ROI for this task type."
    ],
    "merge_directives": [
      "Preserve CO-STAR's Context and Situation sections — drive +2.0 clarity",
      "Inject RISEN's role definition as opening line — +0.5 faithfulness source",
      "Add output format constraint — break shared conciseness ceiling",
      "Retain A's numbered-section structure — +1.5 structure delta confirms",
      "Prefer A's token-efficient phrasing — 43% fewer words, higher scores",
      "Do not require repo context — marginal ROI for this task type"
    ]
  }
}
```

Guidance `headline`, `merge_suggestion`, and `actionable` are generated by a lightweight LLM call (Haiku-class). The `top_insights` and `merge_directives` are template-driven with slot-filling from computed data (no LLM needed).

---

## Section 2: Modal Layout — Three-Phase Progressive Disclosure

### Phase 1: Analyze (Read-Only Assessment)

**Always visible (zero clicks):**
- Header (`h-8`): situation badge + framework labels (A purple, B blue)
- Insight strip (`p-1.5`): headline + modifier pills + top 3 actionable insights
- Score table: dimension rows (`h-5`), winner dots, colored deltas with inline sparkline bars
- Merge directives card: `border-accent`, arrow-prefixed directives, strength pills per side + shared weakness pills
- DiffView: existing component, side-by-side with word-level granularity
- Pinned action bar (`h-8`): Close | Merge Insights

**Expandable via accordion (`h-7` headers with one-line summaries):**
- **Structural** — 4-card grid: input length, output length, expansion ratio, complexity
- **Efficiency** — Dual horizontal bar charts: duration, tokens, cost, score/token
- **Strategy** — Side-by-side cards: framework, source badge, rationale, guardrail pills
- **Context & Adaptation** — Repo delta, feedback count, weight shifts

Accordion summaries provide the key takeaway on the header line — user only expands for detailed breakdowns.

### Phase 2: Merge (LLM Streaming)

- Accordions collapse, score table and guidance stay for reference
- Merge preview panel: `bg-input`, `border-teal/20`, streaming cursor animation
- Token count + model indicator below preview
- Action bar replaced with streaming status

### Phase 3: Commit Gate (Mandatory Decision)

- Merged prompt shown in full (scrollable, `border-teal/25`)
- Two buttons, equal width: "Accept — Archive Parents" (cyan) | "Discard — Cancel Merge" (red)
- Warning text explains consequences of each action
- Close button removed — must choose before exiting

### Brand Compliance

- Header: `h-8` (32px), Syne `text-[11px]` uppercase
- Accordion headers: `h-7` (28px), Syne `text-[9px]` uppercase
- Data rows: `h-5` (20px), Geist Mono `text-[10px]` tabular-nums
- Card interiors: `p-1.5` max, section padding `px-2`
- All borders: 1px solid, zero glow/shadow/drop-shadow
- Background tints: proper opacity tiers (`/5`, `/8`, `/15`)
- Chromatic encoding: situation badge color encodes classification type
- Action bar: `h-8`, pinned bottom

---

## Section 3: Merge Algorithm — Full Intelligence Injection

### New Endpoint: `POST /api/compare/merge` (SSE stream)

Request body: `{ optimization_id_a, optimization_id_b }`

The backend constructs a system prompt that injects the ENTIRE comparison intelligence as structured context sections:

**System prompt sections (all slot-filled from comparison payload):**

1. `SITUATION` — Classification, semantic similarity score, time gap, adaptation trajectory
2. `SCORE INTELLIGENCE` — Full dimension table with winner, delta, signal strength per dimension. Key patterns narrative (which side dominates, where the ceiling is, what the adaptation state implies)
3. `STRUCTURAL INTELLIGENCE` — Input/output lengths, expansion ratios, complexity classification, efficiency conclusion ("A achieved higher scores with shorter output")
4. `STRATEGY INTELLIGENCE` — Framework names, selection sources and confidence, rationale text, guardrail lists, cross-framework analysis ("A's framework was LLM-selected with higher confidence AND performed better")
5. `CONTEXT INTELLIGENCE` — Repo context presence, ROI assessment, instruction compliance delta
6. `ADAPTATION INTELLIGENCE` — Feedback count, weight shifts with percentage, guardrail evolution, trajectory interpretation ("user's feedback loop is ALREADY steering toward A's strengths")
7. `EFFICIENCY INTELLIGENCE` — Duration, tokens, cost, score/token ratio, conclusion ("A is 37% more token-efficient")
8. `VALIDATION INTELLIGENCE` — Both verdicts, both issue lists, both changes_made arrays, cross-validation insight ("A's validator praised structure; B's validator flagged the exact weaknesses A solved")
9. `MERGE DIRECTIVES` — Ordered by delta magnitude (highest impact first), each directive cites the specific data point that justifies it
10. `DIMENSION TARGETS` — Per-dimension target scores derived from max(A, B) for winner dimensions and current+0.5 for shared weaknesses
11. `CONSTRAINTS` — Output only merged text, no commentary, no hallucinated requirements, target A's length range

User message provides both full `optimized_prompt` texts labeled A and B.

**Model:** User's configured default model (from Settings). Streamed via SSE, same pattern as pipeline optimize stage.

### Post-Merge Actions

**Accept:**
1. `POST /api/compare/merge/accept` with `{ optimization_id_a, optimization_id_b, merged_prompt }`
2. Create new `Optimization` record: `raw_prompt = merged_prompt`, `status = 'merged'`. Note: add `"merged"` to `VALID_STATUSES` in `history.py` and to `_VALID_SORT_COLUMNS` in `optimization_service.py`
3. Store `merge_parents = [id_a, id_b]` as JSON column (lineage tracking). Add `merge_parents` to the JSON list-column parsing block in `Optimization.to_dict()` alongside `weaknesses`, `strengths`, etc.
4. Soft-delete both parents (`deleted_at = now()`)
5. Return new optimization ID
6. Frontend: close modal, open merged prompt in editor tab, refresh history, toast

**Discard:**
1. Frontend only — close modal, no API call, no state change

---

## Section 4: Data Flow and Error Handling

### Complete Flow

```
Select 2 items → Compare button
  → GET /api/compare?a={id}&b={id}
  → Modal Phase 1 (Analyze)
  → Click "Merge Insights"
  → POST /api/compare/merge (SSE)
  → Modal Phase 2 (streaming)
  → Stream completes
  → Modal Phase 3 (Commit Gate)
  → Accept: POST /api/compare/merge/accept → new record + soft-delete parents
  → Discard: close modal, no changes
```

### Error Handling

| Failure | Response | UX |
|---|---|---|
| ID not found | 404 | Toast "Optimization not found", no modal |
| No `optimized_prompt` (running/failed) | 422 | Toast "Cannot compare incomplete optimizations" |
| Embedding model unavailable | Fallback to Levenshtein | No degradation visible to user |
| LLM guidance generation fails | Omit `guidance` from payload | Scores + diff render, guidance card hidden, merge button disabled with tooltip |
| Merge stream fails mid-generation | SSE error event | Partial text shown with red border, "Retry" button replaces action bar |
| Accept DB write fails | 500 | Toast "Failed to save merge", modal stays on Phase 3 for retry |
| Parent soft-delete fails after new record created | Log error, return success | Merged prompt saved, orphaned parents cleaned up on next trash sweep |
| Same ID for both A and B | 422 | "Cannot compare an optimization with itself" |
| One optimization is soft-deleted | Allowed | "Trashed" indicator badge shown on that side |

### Caching

Compare endpoint result cached via `cache_service` (Redis with in-memory LRU fallback). Key: `compare:{sorted_id_pair}`, TTL 5 minutes. Merge endpoint reads from same cache key. Invalidation: explicit `cache_service.delete(key)` called from `optimization_service.update_optimization()` and `optimization_service.delete_optimization()` when either ID matches a cached pair.

### Authentication & Authorization

All three endpoints require `Depends(get_current_user)`. Compare and merge operations are scoped to the authenticated user's optimizations via `user_id` filter — a user cannot compare or merge another user's records. Returns 404 (not 403) if either ID belongs to a different user (information hiding).

### Rate Limiting

| Endpoint | Rate Limit | Rationale |
|---|---|---|
| `GET /api/compare` | `Depends(RateLimit(lambda: "10/minute"))` | Embedding computation per call |
| `POST /api/compare/merge` | `Depends(RateLimit(lambda: "5/minute"))` | Full LLM call (Opus-class) |
| `POST /api/compare/merge/accept` | `Depends(RateLimit(lambda: "10/minute"))` | DB write only, lightweight |

### Migration Strategy

The project uses SQLAlchemy `create_all()` at startup (no Alembic). New `merge_parents` column is nullable Text with default `None`. SQLite `ALTER TABLE ADD COLUMN` is supported for nullable columns. Add the column via a startup migration check in `main.py` lifespan (same pattern as existing nullable column additions) — if column doesn't exist, `ALTER TABLE optimizations ADD COLUMN merge_parents TEXT`.

### Phase 3 Escape Handling

When the commit gate is active (Phase 3):
- **Escape key**: blocked (`e.preventDefault()` in keydown handler)
- **Backdrop click**: blocked (no-op, unlike Phase 1 which closes on backdrop)
- **Browser back**: `beforeunload` event listener warns "Merge in progress — changes will be lost"
- **Close button**: removed from header in Phase 3 (header renders without X)
- The ONLY exits are the two buttons: Accept or Discard

---

## Files to Create/Modify

### New Files
| File | Purpose |
|---|---|
| `frontend/src/lib/components/shared/CompareModal.svelte` | The 3-phase modal component |
| `backend/app/routers/compare.py` | Compare + merge + accept endpoints under `/api/compare/*` namespace |
| `backend/app/services/compare_service.py` | Comparison engine: classification, data extraction, insight generation |
| `backend/app/services/merge_service.py` | Merge prompt construction + LLM streaming |
| `backend/app/schemas/compare_models.py` | Pydantic response models for compare/merge |

### Modified Files
| File | Changes |
|---|---|
| `frontend/src/lib/components/layout/NavigatorHistory.svelte` | Wire `handleCompare()` to open CompareModal instead of stub tab |
| `frontend/src/lib/api/client.ts` | Add `compareOptimizations()`, `mergeOptimizations()`, `acceptMerge()` |
| `backend/app/main.py` | Register compare router |
| `backend/app/models/optimization.py` | Add `merge_parents` column (nullable Text, JSON) |

### Reused Components
| Component | Path | Usage |
|---|---|---|
| `DiffView.svelte` | `shared/` | Prompt diff in Phase 1 |
| `BranchCompare.svelte` | `pipeline/` | Reference implementation for score table + DiffView + action pattern |
| `ScoreCircle.svelte` | `shared/` | Score display (already used in NavigatorHistory, Inspector) |
| `StrategyBadge.svelte` | `shared/` | Framework labels |
| `embedding_service.py` | `services/` | Semantic similarity via `embed_single()` + `cosine_search()` |

---

## Verification

1. `npx svelte-check --tsconfig ./tsconfig.json --threshold error` — 0 errors
2. `cd backend && pytest` — all tests pass
3. Select 2 history items → Compare button appears → click opens modal
4. Modal shows situation badge, scores, insights, accordions, diff, merge directives
5. Click "Merge Insights" → LLM streams merged prompt into preview
6. Click "Accept" → new optimization created, parents soft-deleted, editor tab opens
7. Click "Discard" → modal closes, no changes, parents intact
8. Compare two items with same prompt different strategies → situation = STRATEGY
9. Compare two unrelated prompts → situation = CROSS, pattern insights shown
10. Compare item with no optimized_prompt → 422 error, toast shown
11. Close modal during merge stream → no orphaned state
12. Accordion expand/collapse works, progressive disclosure intact

---

## Visual Reference

Mockups saved to `.superpowers/brainstorm/402566-1773477068/`:
- `compare-modal-v3.html` — Brand-compliant Phase 1 + Phase 2 + Phase 3
