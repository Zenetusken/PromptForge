# Explore Stage Accuracy and Cross-Phase Coherence

## Problem

The explore stage (Stage 0) produces observations with fabricated specifics:
- Wrong line numbers (files shown without line markers, LLM invents them)
- False bug diagnoses (claims about code in truncated regions)
- Wrong technical details (e.g., MODEL_ROUTING values)

These inaccurate observations flow into the pipeline trace and, before the optimizer anti-fabrication fix, were embedded into optimized prompts.

## Root Causes

1. **No line numbers in file content** — `_format_files_for_llm()` shows raw code, but the synthesis prompt asks for "line numbers where possible"
2. **Soft anti-fabrication language** — "where possible" encourages guessing
3. **Limited coverage** — 25 files at 300 lines each; relevant code often beyond visibility
4. **No output validation** — hallucinated line numbers pass through unchanged

## Design

### Source Fixes

#### 1. Line-numbered file content (`codebase_explorer.py`)

`_format_files_for_llm()` prefixes each line with its 1-indexed number:

```python
def _format_files_for_llm(file_contents: dict[str, str]) -> str:
    parts: list[str] = []
    for path, content in file_contents.items():
        numbered = "\n".join(
            f"{i:>4} | {line}"
            for i, line in enumerate(content.split("\n"), 1)
        )
        parts.append(f"=== {path} ===\n{numbered}\n")
    return "\n".join(parts)
```

#### 2. Transparent truncation (`codebase_explorer.py`)

`_batch_read_files()` truncation footer replaced:

```python
# Old:
content += f"\n\n[TRUNCATED at {max_lines_per_file} of {len(lines)} lines]"

# New:
content += (
    f"\n\n[TRUNCATED — only lines 1–{max_lines_per_file} of {len(lines)} shown. "
    f"Do NOT reference or make claims about lines beyond {max_lines_per_file}.]"
)
```

#### 3. Tightened synthesis prompt (`explore_synthesis_prompt.py`)

Key changes:
- `relevant_code_snippets`: "Line numbers are shown in the provided file content. Use ONLY the line numbers visible in the numbered output. Never estimate or extrapolate."
- `prompt_grounding_notes`: Replace "where possible" with "from the numbered content only. If relevant code is in a truncated section, say 'code beyond visible range in {file}' — do NOT guess."
- New rule: "Do NOT fabricate line numbers, function behaviors, or bug diagnoses for code you cannot see. If a file is truncated, state that explicitly. Wrong specifics are worse than acknowledging limited visibility."

#### 4. Dynamic token budget (`config.py` + `codebase_explorer.py`)

New config values:

```python
EXPLORE_TOTAL_LINE_BUDGET: int = 15_000   # total lines across all files
EXPLORE_MAX_LINES_PER_FILE: int = 500     # hard ceiling per file
EXPLORE_MAX_FILES: int = 40               # up from 25
```

Per-file line limit computed dynamically in `run_explore()`, then passed to `_batch_read_files()` as the `max_lines_per_file` argument:

```python
# In run_explore(), after file_paths are determined:
max_lines = min(
    settings.EXPLORE_MAX_LINES_PER_FILE,
    settings.EXPLORE_TOTAL_LINE_BUDGET // max(1, len(file_paths)),
)
file_contents = await _batch_read_files(
    token, repo_full_name, tree, file_paths,
    max_lines_per_file=max_lines,
)
```

**Token budget assumption:** ~45 chars per line (including the `{i:>4} | ` prefix). At 15,000 total lines this is ~675K chars, which at ~4 chars/token = ~168K tokens. Haiku 4.5 has 200K context, leaving ~32K tokens for system prompt (~500 tokens) + output (~2K tokens). The assumption is conservative because code lines average 30-50 chars.

**Runtime guard:** If the total character count of the assembled file content exceeds 700K chars (~175K tokens), log a warning and truncate the lowest-priority files (semantic tier) until within budget. This prevents context overflow on repos with unusually long lines.

#### 5. Prompt-referenced file extraction (`codebase_explorer.py`)

New function `_extract_prompt_referenced_files(raw_prompt, tree, max_matches_per_ref)`:

```python
def _extract_prompt_referenced_files(
    raw_prompt: str,
    tree: list[dict],
    max_matches_per_ref: int = 3,
) -> list[str]:
```

Force-includes files the user mentions, validated against the actual repo tree.

Three-tier matching:
1. **Exact path match** — `backend/app/services/pipeline.py` found in tree → include
2. **Filename match** — `pipeline.py` matches tree entries ending with `/pipeline.py` → include all (up to `max_matches_per_ref`)
3. **Module stem match** — `optimizer` matches `optimizer.py`, `optimizer.ts` → include all (up to `max_matches_per_ref`)

Ambiguity guard: references with more than `max_matches_per_ref` (default 3, configurable via `EXPLORE_MAX_AMBIGUOUS_MATCHES` in config.py) tree matches are skipped entirely. This prevents common filenames like `index.ts` from flooding the file list.

Edge case handling:
- Windows-style backslashes normalized to forward slashes before matching
- URL-like strings (containing `://`) are excluded from path extraction
- Tree iteration is O(candidates × tree_size); for typical repos (≤5000 files) and prompts (≤20 candidate paths), this is sub-millisecond

#### 6. Priority-ordered file merge (`codebase_explorer.py`)

Replace the current 2-tier `_deduplicate_files(ranked, anchors, cap)` with a new 3-tier function:

```python
def _merge_file_lists(
    prompt_referenced: list[str],
    anchors: list[str],
    semantic_ranked: list[str],
    cap: int,
) -> list[str]:
    """Merge three file tiers with deduplication, respecting priority order.

    Priority: prompt_referenced > anchors > semantic_ranked.
    Files appearing in multiple tiers count once at their highest priority.
    Semantic results are trimmed first when the cap is hit.
    """
```

This replaces `_deduplicate_files()` with the same dedup logic but an additional tier. Callers of the old function are updated to use the new signature.

### Consumption Validation

New function `_validate_explore_output(parsed, file_contents, max_lines_shown)` runs post-LLM, between normalization and `CodebaseContext` construction.

**Integration point:** Currently, normalization happens inline inside the `CodebaseContext()` constructor call (lines 583-596 of `codebase_explorer.py`). This is refactored to:

```python
# Step 1: Normalize LLM output into intermediate variables
tech_stack = _normalize_string_list(parsed.get("tech_stack", []))
snippets = _normalize_snippets(parsed.get("relevant_code_snippets", []))
observations = _normalize_string_list(parsed.get("codebase_observations", []))
grounding_notes = _normalize_string_list(parsed.get("prompt_grounding_notes", []))

# Step 2: Validate against what was actually shown
snippets, observations, grounding_notes = _validate_explore_output(
    snippets, observations, grounding_notes,
    file_contents=file_contents,
    max_lines_shown=max_lines,  # the dynamic value computed earlier
)

# Step 3: Construct CodebaseContext with validated data
context = CodebaseContext(
    tech_stack=tech_stack,
    snippets=snippets,
    observations=observations,
    grounding_notes=grounding_notes,
    # ... remaining fields unchanged
)
```

**Validation logic in `_validate_explore_output()`:**

1. **Snippet line validation** — For each snippet, parse the `lines` field (e.g., "45-62"). If the file exists in `file_contents`, check that both endpoints are ≤ `max_lines_shown`. If not, append `[unverified — beyond visible range]` to the snippet's `context` field.

2. **Observation/grounding note line references** — Regex patterns matched:
   - `lines? \d+[-–]\d+` (range: "lines 233-240")
   - `line \d+` (single: "line 42")
   - `L\d+` (shorthand: "L42")
   - `:\d+` preceded by a file path (colon notation: "pipeline.py:233")

   For each match, extract the file path context and line number. If the line exceeds `max_lines_shown` for that file, append `[unverified — beyond visible range]` to the observation/note string.

3. **Grounding notes claiming bugs** — Notes containing claim indicators ("does NOT", "is NOT set", "missing", "but doesn't") about code in truncated files get `[unverified — file truncated at line {N}]` suffix.

**Note:** Validation suffixes like `[unverified — beyond visible range]` will be visible in downstream stage prompts via `build_codebase_summary()`. This is intentional — it signals to the optimizer that specific claims are unverified, aligning with the optimizer's existing anti-fabrication constraints.

## Files Modified

| File | Change |
|------|--------|
| `backend/app/services/codebase_explorer.py` | Line-numbered content, transparent truncation, prompt-referenced file extraction, post-LLM validation, priority-ordered merge via new `_merge_file_lists()`, dynamic line budget, runtime char guard |
| `backend/app/prompts/explore_synthesis_prompt.py` | Hard anti-fabrication constraints, line number accuracy requirements |
| `backend/app/config.py` | `EXPLORE_MAX_FILES` 25→40, new `EXPLORE_TOTAL_LINE_BUDGET`, `EXPLORE_MAX_LINES_PER_FILE`, `EXPLORE_MAX_AMBIGUOUS_MATCHES` |
| `backend/tests/test_explore_phase.py` | Update existing tests for line-numbered content format, add tests for `_validate_explore_output()`, `_extract_prompt_referenced_files()`, `_merge_file_lists()`, dynamic budget calculation, runtime char guard |

## What Does NOT Change

- `context_builders.py` — already consumes quality flags correctly; validation suffixes flow through as part of observation/snippet strings (intentional)
- `optimizer_prompts.py` / `optimizer.py` — already fixed with anti-fabrication constraints
- `EXPLORE_OUTPUT_SCHEMA` — same JSON structure, more accurate data
- `pipeline.py` — no changes to stage orchestration
- `EXPLORE_RESULT_CACHE_TTL` — stays at 1 hour; existing cached results produced with old config will expire naturally within 1 hour of deployment (acceptable since the old results are simply less accurate, not structurally incompatible)

## Verification

1. `cd backend && pytest` — no regressions
2. Same base prompt against linked repo — confirm observations have accurate line numbers from numbered content
3. Verify truncated files get flagged observations, not fabricated line numbers
4. Confirm prompt-referenced files always included in file list
5. Monitor Haiku synthesis call token usage — must stay within 200K context; runtime char guard logs warning if budget exceeded
6. Test with a repo >1000 files to verify dynamic budget scaling and runtime guard
