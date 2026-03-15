# Explore Stage Accuracy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the explore stage to produce accurate, verifiable observations by adding line numbers to file content, tightening the synthesis prompt, increasing coverage with dynamic budgeting, force-including prompt-referenced files, and validating LLM output post-synthesis.

**Architecture:** Seven changes across 4 files. Source fixes (line-numbered content, transparent truncation, tightened prompt, dynamic budget, prompt-referenced file extraction, 3-tier file merge) prevent fabrication at the source. One consumption fix (post-LLM validation) catches stragglers before they reach downstream stages.

**Tech Stack:** Python 3.14, pytest, regex, async generators

**Spec:** `docs/superpowers/specs/2026-03-10-explore-stage-accuracy-design.md`

---

## Chunk 1: Config + Line-Numbered Content + Transparent Truncation

### Task 1: Add config values

**Files:**
- Modify: `backend/app/config.py:78-86`

- [ ] **Step 1: Add three new config values**

In `backend/app/config.py`, after the existing `EXPLORE_MAX_FILES` line (84), add the new values and update the existing one:

```python
# Replace:
EXPLORE_MAX_FILES: int = 25              # max files to read for synthesis

# With:
EXPLORE_MAX_FILES: int = 40              # max files to read for synthesis (up from 25)
EXPLORE_TOTAL_LINE_BUDGET: int = 15_000  # total lines across all files for LLM context
EXPLORE_MAX_LINES_PER_FILE: int = 500    # hard ceiling per file (dynamic budget may lower this)
EXPLORE_MAX_AMBIGUOUS_MATCHES: int = 3   # skip prompt-referenced files with > N tree matches
```

- [ ] **Step 2: Verify config loads**

Run: `cd backend && source .venv/bin/activate && python -c "from app.config import settings; print(settings.EXPLORE_MAX_FILES, settings.EXPLORE_TOTAL_LINE_BUDGET)"`
Expected: `40 15000`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(explore): add dynamic budget and coverage config values"
```

### Task 2: Line-numbered file content and transparent truncation

**Files:**
- Modify: `backend/app/services/codebase_explorer.py:254-298`
- Test: `backend/tests/test_explore_phase.py`

- [ ] **Step 1: Write failing tests for line-numbered content**

Add to `backend/tests/test_explore_phase.py`, after the existing imports, add `_format_files_for_llm` to the import list. Then add a new test class:

```python
class TestFormatFilesForLlm:
    """Test line-numbered file formatting."""

    def test_adds_line_numbers(self):
        contents = {"main.py": "import os\nprint('hello')"}
        result = _format_files_for_llm(contents)
        assert "   1 | import os" in result
        assert "   2 | print('hello')" in result

    def test_file_header_preserved(self):
        contents = {"src/app.py": "x = 1"}
        result = _format_files_for_llm(contents)
        assert "=== src/app.py ===" in result

    def test_empty_lines_get_numbers(self):
        contents = {"f.py": "a\n\nb"}
        result = _format_files_for_llm(contents)
        assert "   1 | a" in result
        assert "   2 | " in result
        assert "   3 | b" in result

    def test_multiple_files(self):
        contents = {"a.py": "x = 1", "b.py": "y = 2"}
        result = _format_files_for_llm(contents)
        assert "=== a.py ===" in result
        assert "=== b.py ===" in result
        assert "   1 | x = 1" in result
        assert "   1 | y = 2" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_explore_phase.py::TestFormatFilesForLlm -v`
Expected: FAIL — `_format_files_for_llm` not in import or tests fail on content format

- [ ] **Step 3: Add `_format_files_for_llm` to test imports and implement line numbering**

Update the import in `test_explore_phase.py` line 9-16 to include `_format_files_for_llm`:

```python
from app.services.codebase_explorer import (
    CodebaseContext,
    _deduplicate_files,
    _format_files_for_llm,
    _get_anchor_paths,
    _keyword_fallback,
    _normalize_snippets,
    _normalize_string_list,
)
```

Then in `codebase_explorer.py`, replace `_format_files_for_llm` (lines 293-298):

```python
def _format_files_for_llm(file_contents: dict[str, str]) -> str:
    """Format file contents with line numbers for the LLM.

    Each line is prefixed with its 1-indexed number (right-aligned, 4 digits)
    so the LLM can reference accurate line numbers in its observations.
    """
    parts: list[str] = []
    for path, content in file_contents.items():
        numbered = "\n".join(
            f"{i:>4} | {line}"
            for i, line in enumerate(content.split("\n"), 1)
        )
        parts.append(f"=== {path} ===\n{numbered}\n")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_explore_phase.py::TestFormatFilesForLlm -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write failing test for transparent truncation**

Add test class to `test_explore_phase.py`:

```python
class TestBatchReadFilesTruncation:
    """Test that truncation message warns the LLM not to reference beyond cutoff."""

    @pytest.mark.asyncio
    async def test_truncation_message_warns_against_claims(self):
        """Truncated files warn LLM not to reference lines beyond the cutoff."""
        long_content = "\n".join(f"line {i}" for i in range(1, 101))  # 100 lines

        with patch(
            "app.services.codebase_explorer.read_file_content",
            new_callable=AsyncMock,
            return_value=long_content,
        ):
            from app.services.codebase_explorer import _batch_read_files

            tree = [{"path": "big.py", "sha": "abc"}]
            result = await _batch_read_files("tok", "o/r", tree, ["big.py"], max_lines_per_file=10)

        content = result["big.py"]
        assert "Do NOT reference or make claims about lines beyond 10" in content
        assert "TRUNCATED" in content

    @pytest.mark.asyncio
    async def test_no_truncation_for_short_files(self):
        """Short files are not truncated."""
        short_content = "line 1\nline 2\nline 3"

        with patch(
            "app.services.codebase_explorer.read_file_content",
            new_callable=AsyncMock,
            return_value=short_content,
        ):
            from app.services.codebase_explorer import _batch_read_files

            tree = [{"path": "small.py", "sha": "abc"}]
            result = await _batch_read_files("tok", "o/r", tree, ["small.py"], max_lines_per_file=10)

        content = result["small.py"]
        assert "TRUNCATED" not in content
```

- [ ] **Step 6: Run truncation test to verify it fails**

Run: `cd backend && pytest tests/test_explore_phase.py::TestBatchReadFilesTruncation -v`
Expected: FAIL — old truncation message doesn't match

- [ ] **Step 7: Update truncation message in `_batch_read_files`**

In `codebase_explorer.py`, replace line 283:

```python
# Old (line 283):
content += f"\n\n[TRUNCATED at {max_lines_per_file} of {len(lines)} lines]"

# New:
content += (
    f"\n\n[TRUNCATED — only lines 1\u2013{max_lines_per_file} of {len(lines)} shown. "
    f"Do NOT reference or make claims about lines beyond {max_lines_per_file}.]"
)
```

- [ ] **Step 8: Run truncation tests to verify they pass**

Run: `cd backend && pytest tests/test_explore_phase.py::TestBatchReadFilesTruncation -v`
Expected: PASS (2 tests)

- [ ] **Step 9: Run full test suite**

Run: `cd backend && pytest`
Expected: All pass. If `test_sse_event_sequence` fails due to changed content format, update its mock return value — the test checks event types, not content format.

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/codebase_explorer.py backend/tests/test_explore_phase.py
git commit -m "feat(explore): add line numbers to file content and transparent truncation"
```

---

## Chunk 2: Tightened Synthesis Prompt

### Task 3: Update explore synthesis prompt

**Files:**
- Modify: `backend/app/prompts/explore_synthesis_prompt.py`

- [ ] **Step 1: Read current prompt**

Read `backend/app/prompts/explore_synthesis_prompt.py` to see the current content (already read — lines 1-74).

- [ ] **Step 2: Update `relevant_code_snippets` section**

Replace lines 36-39 of `explore_synthesis_prompt.py`:

```python
# Old:
### relevant_code_snippets (optional but valuable)
Extract 3\u20138 code snippets that are directly relevant to the user's prompt:
  - Each snippet: {"file": "path/to/file.py", "lines": "45-62", "context": "brief description of what this code does and why it's relevant"}
  - Prioritize: entry points, API definitions, config schemas, the exact code the prompt references

# New:
### relevant_code_snippets (optional but valuable)
Extract 3\u20138 code snippets that are directly relevant to the user's prompt:
  - Each snippet: {"file": "path/to/file.py", "lines": "45-62", "context": "brief description of what this code does and why it's relevant"}
  - Line numbers are shown in the provided file content (format: "   N | code"). Use ONLY the line numbers visible in the numbered output. Never estimate or extrapolate line numbers beyond what is shown.
  - Prioritize: entry points, API definitions, config schemas, the exact code the prompt references
```

- [ ] **Step 3: Update `prompt_grounding_notes` section**

Replace line 54:

```python
# Old:
  - Confirm correct references with file paths and line numbers where possible

# New:
  - Confirm correct references with file paths and line numbers from the numbered content only. If the relevant code is in a truncated section (beyond visible lines), say "code beyond visible range in {file}" \u2014 do NOT guess line numbers.
```

- [ ] **Step 4: Update Rules section**

Replace lines 66-69:

```python
# Old:
## Rules
- Do NOT hallucinate file paths or function names. Only reference what you can see in the provided files.
- If the provided files don't cover something the prompt mentions, say so explicitly in grounding_notes.
- Be concise but precise. Every observation must be grounded in actual file content.

# New:
## Rules
- Do NOT hallucinate file paths or function names. Only reference what you can see in the provided files.
- Do NOT fabricate line numbers, function behaviors, or bug diagnoses for code you cannot see. If a file is truncated, state that explicitly. Wrong specifics are worse than acknowledging limited visibility.
- If the provided files don't cover something the prompt mentions, say so explicitly in grounding_notes. Do NOT guess what the missing code does.
- Be concise but precise. Every observation must be grounded in actual file content.
```

- [ ] **Step 5: Run full test suite**

Run: `cd backend && pytest`
Expected: All pass (prompt changes don't affect unit tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/prompts/explore_synthesis_prompt.py
git commit -m "feat(explore): tighten synthesis prompt against line number fabrication"
```

---

## Chunk 3: Dynamic Budget + Prompt-Referenced Files + 3-Tier Merge

### Task 4: Dynamic line budget

**Files:**
- Modify: `backend/app/services/codebase_explorer.py:509-511`

- [ ] **Step 1: Write failing test for dynamic budget**

Add to `test_explore_phase.py`:

```python
class TestDynamicBudget:
    """Test dynamic line budget calculation."""

    def test_few_files_get_max_lines(self):
        """With few files, each gets the max lines per file."""
        from app.config import settings
        file_count = 10
        max_lines = min(
            settings.EXPLORE_MAX_LINES_PER_FILE,
            settings.EXPLORE_TOTAL_LINE_BUDGET // max(1, file_count),
        )
        assert max_lines == settings.EXPLORE_MAX_LINES_PER_FILE  # 500 < 15000/10=1500

    def test_many_files_get_budget_share(self):
        """With many files, lines per file is budget/count."""
        from app.config import settings
        file_count = 40
        max_lines = min(
            settings.EXPLORE_MAX_LINES_PER_FILE,
            settings.EXPLORE_TOTAL_LINE_BUDGET // max(1, file_count),
        )
        assert max_lines == 375  # 15000/40 = 375 < 500

    def test_zero_files_no_crash(self):
        """Zero files doesn't divide by zero."""
        from app.config import settings
        max_lines = min(
            settings.EXPLORE_MAX_LINES_PER_FILE,
            settings.EXPLORE_TOTAL_LINE_BUDGET // max(1, 0),
        )
        assert max_lines == settings.EXPLORE_MAX_LINES_PER_FILE
```

- [ ] **Step 2: Run test (should pass immediately — pure math)**

Run: `cd backend && pytest tests/test_explore_phase.py::TestDynamicBudget -v`
Expected: PASS (these test the formula, not the integration)

- [ ] **Step 3: Wire dynamic budget into `run_explore()`**

In `codebase_explorer.py`, replace lines 509-511 to add dynamic budget:

```python
# Old:
    file_contents = await _batch_read_files(
        token, repo_full_name, tree, all_file_paths,
    )

# New:
    # Dynamic line budget: divide total budget across files, capped per file
    max_lines = min(
        settings.EXPLORE_MAX_LINES_PER_FILE,
        settings.EXPLORE_TOTAL_LINE_BUDGET // max(1, len(all_file_paths)),
    )
    file_contents = await _batch_read_files(
        token, repo_full_name, tree, all_file_paths,
        max_lines_per_file=max_lines,
    )
```

Then, AFTER the `if not file_contents:` early return block (after line 527), add the runtime char guard. Also replace the existing `context_payload = _format_files_for_llm(file_contents)` at line 538 with this guard block:

```python
# Replace line 538:
#   context_payload = _format_files_for_llm(file_contents)
# With:
    # Runtime char guard — prevent context overflow on repos with long lines
    context_payload = _format_files_for_llm(file_contents)
    _MAX_CONTEXT_CHARS = 700_000  # ~175K tokens
    if len(context_payload) > _MAX_CONTEXT_CHARS:
        logger.warning(
            "Explore context exceeds %d chars (%d chars); trimming semantic files",
            _MAX_CONTEXT_CHARS, len(context_payload),
        )
        # Remove semantic-tier files (last in priority) until within budget
        # Note: this also affects key_files_read downstream (intentional —
        # trimmed files were not shown to the LLM)
        paths_by_priority = list(file_contents.keys())
        while len(context_payload) > _MAX_CONTEXT_CHARS and paths_by_priority:
            removed = paths_by_priority.pop()
            del file_contents[removed]
            context_payload = _format_files_for_llm(file_contents)
```

- [ ] **Step 4: Run full test suite**

Run: `cd backend && pytest`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/codebase_explorer.py backend/tests/test_explore_phase.py
git commit -m "feat(explore): wire dynamic line budget and runtime char guard"
```

### Task 5: Prompt-referenced file extraction

**Files:**
- Modify: `backend/app/services/codebase_explorer.py` (new function)
- Test: `backend/tests/test_explore_phase.py`

- [ ] **Step 1: Write failing tests**

Add to `test_explore_phase.py`. First add `_extract_prompt_referenced_files` to the import list from `codebase_explorer`. Then:

```python
class TestExtractPromptReferencedFiles:
    """Test tree-validated prompt file extraction."""

    def _tree(self, paths):
        return [{"path": p, "sha": "abc", "size_bytes": 100} for p in paths]

    def test_exact_path_match(self):
        tree = self._tree(["backend/app/services/pipeline.py", "README.md"])
        prompt = "Audit backend/app/services/pipeline.py for handoff issues"
        result = _extract_prompt_referenced_files(prompt, tree)
        assert "backend/app/services/pipeline.py" in result

    def test_filename_match(self):
        tree = self._tree(["src/pipeline.py", "tests/test_pipeline.py"])
        prompt = "Check pipeline.py for bugs"
        result = _extract_prompt_referenced_files(prompt, tree)
        assert "src/pipeline.py" in result

    def test_ambiguous_filename_skipped(self):
        tree = self._tree([f"pkg{i}/index.ts" for i in range(5)])
        prompt = "Fix index.ts"
        result = _extract_prompt_referenced_files(prompt, tree)
        assert result == []  # >3 matches, skipped

    def test_url_excluded(self):
        tree = self._tree(["src/config.py"])
        prompt = "See https://example.com/config.py for details"
        result = _extract_prompt_referenced_files(prompt, tree)
        # config.py should NOT match from a URL context
        assert result == []

    def test_backslash_normalized(self):
        tree = self._tree(["src/app/main.py"])
        prompt = r"Check src\app\main.py"
        result = _extract_prompt_referenced_files(prompt, tree)
        assert "src/app/main.py" in result

    def test_module_stem_match(self):
        tree = self._tree(["backend/app/services/optimizer.py", "README.md"])
        prompt = "How does the optimizer handle secondary frameworks?"
        result = _extract_prompt_referenced_files(prompt, tree)
        assert "backend/app/services/optimizer.py" in result

    def test_no_matches_returns_empty(self):
        tree = self._tree(["src/main.py"])
        prompt = "What is the meaning of life?"
        result = _extract_prompt_referenced_files(prompt, tree)
        assert result == []

    def test_deduplication(self):
        tree = self._tree(["backend/pipeline.py"])
        prompt = "Audit backend/pipeline.py — check pipeline.py for bugs"
        result = _extract_prompt_referenced_files(prompt, tree)
        assert result.count("backend/pipeline.py") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_explore_phase.py::TestExtractPromptReferencedFiles -v`
Expected: FAIL — `_extract_prompt_referenced_files` not importable

- [ ] **Step 3: Implement `_extract_prompt_referenced_files`**

First, add `import re` to the module-level imports at the top of `codebase_explorer.py` (around line 14, with the other imports):

```python
import re
```

Then add the following before `_get_anchor_paths()` (around line 167):

```python
# Code extension set for module stem matching
_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".js", ".jsx", ".tsx", ".svelte", ".vue",
    ".go", ".rs", ".java", ".rb", ".php", ".cs", ".swift",
    ".yaml", ".yml", ".toml", ".json", ".md", ".txt",
})


def _extract_prompt_referenced_files(
    raw_prompt: str,
    tree: list[dict],
    max_matches_per_ref: int | None = None,
) -> list[str]:
    """Extract file paths mentioned in the prompt, validated against the repo tree.

    Three-tier matching (exact path > filename > module stem).
    Ambiguous references (>max_matches_per_ref matches) are skipped.
    """
    if max_matches_per_ref is None:
        max_matches_per_ref = settings.EXPLORE_MAX_AMBIGUOUS_MATCHES

    # Normalize prompt: backslashes to forward slashes
    normalized = raw_prompt.replace("\\", "/")

    # Strip URL-like strings to prevent false matches
    normalized = re.sub(r"https?://\S+", "", normalized)

    tree_paths = [e["path"] for e in tree]
    tree_path_set = set(tree_paths)
    result: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        if path not in seen:
            seen.add(path)
            result.append(path)

    # Tier 1: Exact path match — check each tree path against the prompt
    for tp in tree_paths:
        if tp in normalized:
            _add(tp)

    # Tier 2: Filename match — extract filename-like tokens from prompt
    filename_pattern = re.compile(r"[\w./-]*\w+\.\w{1,10}")
    candidates = filename_pattern.findall(normalized)

    for candidate in candidates:
        filename = candidate.split("/")[-1]
        if not any(filename.endswith(ext) for ext in _CODE_EXTENSIONS):
            continue
        matches = [tp for tp in tree_paths if tp.endswith("/" + filename) or tp == filename]
        if 0 < len(matches) <= max_matches_per_ref:
            for m in matches:
                _add(m)

    # Tier 3: Module stem match — words that match a code file's stem
    words = set(normalized.lower().split())
    words = {w.strip(".,;:!?()[]{}\"'") for w in words}
    words = {w for w in words if len(w) >= 3 and "/" not in w and "." not in w}

    for word in words:
        matches = [
            tp for tp in tree_paths
            if tp.split("/")[-1].rsplit(".", 1)[0].lower() == word
            and any(tp.endswith(ext) for ext in _CODE_EXTENSIONS)
        ]
        if 0 < len(matches) <= max_matches_per_ref:
            for m in matches:
                _add(m)

    return result
```

- [ ] **Step 4: Add to import list in test file and run tests**

Run: `cd backend && pytest tests/test_explore_phase.py::TestExtractPromptReferencedFiles -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/codebase_explorer.py backend/tests/test_explore_phase.py
git commit -m "feat(explore): add prompt-referenced file extraction with tree validation"
```

### Task 6: 3-tier priority merge

**Files:**
- Modify: `backend/app/services/codebase_explorer.py:176-202` (replace `_deduplicate_files`)
- Test: `backend/tests/test_explore_phase.py`

- [ ] **Step 1: Write failing tests for `_merge_file_lists`**

Add to `test_explore_phase.py`. Will need to add `_merge_file_lists` to imports (and later remove `_deduplicate_files`):

```python
class TestMergeFileLists:
    """Test 3-tier priority file merge."""

    def test_priority_order(self):
        result = _merge_file_lists(
            prompt_referenced=["pipeline.py"],
            anchors=["README.md"],
            semantic_ranked=["utils.py"],
            cap=10,
        )
        assert result[0] == "pipeline.py"
        assert result[1] == "README.md"
        assert result[2] == "utils.py"

    def test_dedup_across_tiers(self):
        result = _merge_file_lists(
            prompt_referenced=["README.md"],  # also an anchor
            anchors=["README.md", "Dockerfile"],
            semantic_ranked=["README.md", "utils.py"],
            cap=10,
        )
        assert result.count("README.md") == 1
        assert len(result) == 3  # README.md, Dockerfile, utils.py

    def test_cap_trims_semantic_first(self):
        result = _merge_file_lists(
            prompt_referenced=["a.py", "b.py"],
            anchors=["README.md"],
            semantic_ranked=["c.py", "d.py", "e.py"],
            cap=4,
        )
        assert len(result) == 4
        assert "a.py" in result
        assert "b.py" in result
        assert "README.md" in result
        # Only 1 semantic file fits

    def test_prompt_referenced_never_trimmed(self):
        result = _merge_file_lists(
            prompt_referenced=["a.py", "b.py", "c.py"],
            anchors=["README.md"],
            semantic_ranked=["d.py"],
            cap=3,
        )
        # Cap is 3, but prompt_referenced has 3 — they all survive
        assert len(result) == 3
        assert all(f in result for f in ["a.py", "b.py", "c.py"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_explore_phase.py::TestMergeFileLists -v`
Expected: FAIL — `_merge_file_lists` not importable

- [ ] **Step 3: Replace `_deduplicate_files` with `_merge_file_lists`**

In `codebase_explorer.py`, replace the `_deduplicate_files` function (lines 176-202):

```python
def _merge_file_lists(
    prompt_referenced: list[str],
    anchors: list[str],
    semantic_ranked: list[str] | list["RankedFile"],
    cap: int,
) -> list[str]:
    """Merge three file tiers with deduplication, respecting priority order.

    Priority: prompt_referenced > anchors > semantic_ranked.
    Files appearing in multiple tiers count once at their highest priority.
    Semantic results are trimmed first when the cap is hit.
    """
    seen: set[str] = set()
    result: list[str] = []

    # Tier 1: Prompt-referenced (highest priority)
    for path in prompt_referenced:
        if path not in seen:
            seen.add(path)
            result.append(path)

    # Tier 2: Anchors
    for path in anchors:
        if path not in seen:
            seen.add(path)
            result.append(path)

    # Tier 3: Semantic ranked (fill remaining)
    for item in semantic_ranked:
        path = item.path if hasattr(item, "path") else str(item)
        if path not in seen:
            seen.add(path)
            result.append(path)
        if len(result) >= cap:
            break

    return result[:cap]
```

- [ ] **Step 4: Update call site in `run_explore()`**

Replace line 487:

```python
# Old:
    all_file_paths = _deduplicate_files(ranked_files, anchor_paths, cap=max_files)

# New:
    prompt_file_paths = _extract_prompt_referenced_files(raw_prompt, tree)
    all_file_paths = _merge_file_lists(
        prompt_referenced=prompt_file_paths,
        anchors=anchor_paths,
        semantic_ranked=ranked_files,
        cap=max_files,
    )
```

- [ ] **Step 5: Update test imports**

In `test_explore_phase.py`, replace `_deduplicate_files` with `_merge_file_lists` in the import block. The full import should be:

```python
from app.services.codebase_explorer import (
    CodebaseContext,
    _extract_prompt_referenced_files,
    _format_files_for_llm,
    _get_anchor_paths,
    _keyword_fallback,
    _merge_file_lists,
    _normalize_snippets,
    _normalize_string_list,
)
```

Then update `TestDeduplicateFiles` class to use `_merge_file_lists`:

```python
class TestDeduplicateFiles:
    """Test file deduplication and capping (now via _merge_file_lists)."""

    def test_basic_dedup(self):
        ranked = [
            RankedFile(path="src/auth.py", score=0.9),
            RankedFile(path="src/main.py", score=0.8),
        ]
        anchors = ["README.md", "package.json"]
        result = _merge_file_lists([], anchors, ranked, cap=10)

        # Anchors first, then ranked
        assert result[0] == "README.md"
        assert result[1] == "package.json"
        assert "src/auth.py" in result
        assert "src/main.py" in result

    def test_dedup_overlap(self):
        ranked = [
            RankedFile(path="README.md", score=0.9),
            RankedFile(path="src/auth.py", score=0.8),
        ]
        anchors = ["README.md"]
        result = _merge_file_lists([], anchors, ranked, cap=10)

        assert result.count("README.md") == 1
        assert len(result) == 2

    def test_cap_enforced(self):
        ranked = [RankedFile(path=f"file_{i}.py", score=0.5) for i in range(50)]
        anchors = ["README.md"]
        result = _merge_file_lists([], anchors, ranked, cap=5)
        assert len(result) == 5
```

- [ ] **Step 6: Run all tests**

Run: `cd backend && pytest tests/test_explore_phase.py -v`
Expected: All pass

- [ ] **Step 7: Run full test suite**

Run: `cd backend && pytest`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/codebase_explorer.py backend/tests/test_explore_phase.py
git commit -m "feat(explore): replace _deduplicate_files with 3-tier _merge_file_lists"
```

---

## Chunk 4: Consumption Validation

### Task 7: Post-LLM output validation

**Files:**
- Modify: `backend/app/services/codebase_explorer.py:580-596`
- Test: `backend/tests/test_explore_phase.py`

- [ ] **Step 1: Write failing tests for `_validate_explore_output`**

Add to `test_explore_phase.py`:

```python
class TestValidateExploreOutput:
    """Test post-LLM output validation."""

    def test_valid_snippet_passes_through(self):
        snippets = [{"file": "main.py", "lines": "1-10", "context": "entry point"}]
        file_contents = {"main.py": "\n".join(f"line {i}" for i in range(1, 51))}
        s, o, g = _validate_explore_output(snippets, [], [], file_contents, max_lines_shown=50)
        assert s[0]["context"] == "entry point"  # no flag added

    def test_snippet_beyond_visible_range_flagged(self):
        snippets = [{"file": "big.py", "lines": "400-420", "context": "some logic"}]
        file_contents = {"big.py": "\n".join(f"line {i}" for i in range(1, 301))}
        s, o, g = _validate_explore_output(snippets, [], [], file_contents, max_lines_shown=300)
        assert "[unverified" in s[0]["context"]

    def test_observation_with_valid_line_ref_unchanged(self):
        obs = ["Pipeline stage at line 50 handles retries"]
        file_contents = {"pipeline.py": "x" * 100}
        s, o, g = _validate_explore_output([], obs, [], file_contents, max_lines_shown=300)
        assert o[0] == obs[0]  # within range, no flag

    def test_observation_with_invalid_line_ref_flagged(self):
        obs = ["Bug at lines 600-610 in pipeline.py"]
        file_contents = {"pipeline.py": "x"}
        s, o, g = _validate_explore_output([], obs, [], file_contents, max_lines_shown=300)
        assert "[unverified" in o[0]

    def test_grounding_note_bug_claim_in_truncated_file_flagged(self):
        # File content includes truncation marker — indicates the file was cut off
        truncated_content = "\n".join(f"line {i}" for i in range(1, 301))
        truncated_content += "\n\n[TRUNCATED — only lines 1–300 of 800 shown.]"
        notes = ["analysis_quality is NOT set when defaults are applied in analyzer.py"]
        file_contents = {"analyzer.py": truncated_content}
        s, o, g = _validate_explore_output([], [], notes, file_contents, max_lines_shown=300)
        assert "[unverified" in g[0]

    def test_snippet_for_unknown_file_flagged(self):
        snippets = [{"file": "nonexistent.py", "lines": "1-5", "context": "ghost"}]
        s, o, g = _validate_explore_output(snippets, [], [], {}, max_lines_shown=300)
        assert "[unverified" in s[0]["context"]

    def test_empty_inputs_no_crash(self):
        s, o, g = _validate_explore_output([], [], [], {}, max_lines_shown=300)
        assert s == [] and o == [] and g == []

    def test_unparseable_line_range_left_alone(self):
        snippets = [{"file": "a.py", "lines": "various", "context": "ok"}]
        file_contents = {"a.py": "x"}
        s, o, g = _validate_explore_output(snippets, [], [], file_contents, max_lines_shown=300)
        assert s[0]["context"] == "ok"  # can't parse "various", so left alone
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_explore_phase.py::TestValidateExploreOutput -v`
Expected: FAIL — `_validate_explore_output` not importable

- [ ] **Step 3: Implement `_validate_explore_output`**

Add after `_normalize_snippets` in `codebase_explorer.py` (around line 96):

```python
_LINE_REF_PATTERNS = [
    re.compile(r"lines?\s+(\d+)\s*[-\u2013]\s*(\d+)"),          # "lines 233-240" or "line 45-62"
    re.compile(r"line\s+(\d+)(?!\s*[-\u2013])"),                 # "line 42" (single)
    re.compile(r"\bL(\d+)\b"),                                    # "L42"
    re.compile(r"\.(?:py|ts|js|svelte|go|rs|java):(\d+)"),       # "pipeline.py:233"
]

_BUG_CLAIM_INDICATORS = re.compile(
    r"does NOT|is NOT set|is NOT|but doesn't|but does not|missing|"
    r"never set|not implemented|not called|not used|not defined",
    re.IGNORECASE,
)


def _validate_explore_output(
    snippets: list[dict],
    observations: list[str],
    grounding_notes: list[str],
    file_contents: dict[str, str],
    max_lines_shown: int,
) -> tuple[list[dict], list[str], list[str]]:
    """Validate LLM explore output against what was actually shown.

    Flags unverifiable claims with [unverified] suffixes.
    Returns (snippets, observations, grounding_notes) with flags applied.
    """
    _UNVERIFIED = " [unverified \u2014 beyond visible range]"
    _UNVERIFIED_TRUNC = " [unverified \u2014 file truncated at line {}]"

    # Build a set of file stems for fuzzy matching in observations
    file_stems = {}
    for path in file_contents:
        filename = path.split("/")[-1]
        file_stems[filename] = path
        stem = filename.rsplit(".", 1)[0]
        file_stems[stem] = path

    def _parse_line_range(lines_str: str) -> tuple[int, int] | None:
        """Parse '45-62' or '45' into (start, end). Returns None if unparseable."""
        lines_str = lines_str.strip()
        m = re.match(r"(\d+)\s*[-\u2013]\s*(\d+)", lines_str)
        if m:
            return int(m.group(1)), int(m.group(2))
        m = re.match(r"(\d+)$", lines_str)
        if m:
            n = int(m.group(1))
            return n, n
        return None

    def _max_line_for_file(file_path: str) -> int:
        """Return the max visible line for a file, or 0 if unknown."""
        content = file_contents.get(file_path)
        if content is None:
            return 0
        return min(max_lines_shown, content.count("\n") + 1)

    # Validate snippets
    validated_snippets = []
    for snip in snippets:
        snip = dict(snip)  # copy
        file_path = snip.get("file", "")
        lines_str = snip.get("lines", "")
        rng = _parse_line_range(lines_str) if lines_str else None

        if file_path not in file_contents:
            snip["context"] = snip.get("context", "") + _UNVERIFIED
        elif rng:
            max_line = _max_line_for_file(file_path)
            if rng[1] > max_line:
                snip["context"] = snip.get("context", "") + _UNVERIFIED
        validated_snippets.append(snip)

    # Validate observations and grounding notes
    def _flag_text(text: str) -> str:
        for pattern in _LINE_REF_PATTERNS:
            for m in pattern.finditer(text):
                groups = m.groups()
                line_num = int(groups[-1])  # last group is always a line number
                if line_num > max_lines_shown:
                    return text + _UNVERIFIED
        return text

    def _is_truncated(file_path: str) -> bool:
        """Check if a file was truncated by looking for the truncation marker."""
        content = file_contents.get(file_path, "")
        return "[TRUNCATED" in content

    def _flag_bug_claim(text: str) -> str:
        if _BUG_CLAIM_INDICATORS.search(text):
            # Check if the claim references a truncated file
            for filename, path in file_stems.items():
                if filename in text and _is_truncated(path):
                    return text + _UNVERIFIED_TRUNC.format(max_lines_shown)
        return text

    validated_obs = [_flag_text(o) for o in observations]
    validated_notes = [_flag_bug_claim(_flag_text(n)) for n in grounding_notes]

    return validated_snippets, validated_obs, validated_notes
```

- [ ] **Step 4: Add to test imports and run tests**

Add `_validate_explore_output` to the import list in `test_explore_phase.py`.

Run: `cd backend && pytest tests/test_explore_phase.py::TestValidateExploreOutput -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Wire validation into `run_explore()` CodebaseContext construction**

Replace lines 583-596 of `codebase_explorer.py`:

```python
# Old:
    context = CodebaseContext(
        repo=repo_full_name,
        branch=used_branch,
        tech_stack=_normalize_string_list(parsed.get("tech_stack", [])),
        key_files_read=list(file_contents.keys()),
        relevant_snippets=_normalize_snippets(parsed.get("relevant_code_snippets", [])),
        observations=_normalize_string_list(parsed.get("codebase_observations", [])),
        grounding_notes=_normalize_string_list(parsed.get("prompt_grounding_notes", [])),
        files_read_count=len(file_contents),
        coverage_pct=min(100, round(len(file_contents) / max(1, total_in_tree) * 100)),
        duration_ms=duration_ms,
        explore_quality="complete" if parsed else "partial",
        retrieval_method=retrieval_method,
    )

# New:
    # Step 1: Normalize LLM output
    tech_stack = _normalize_string_list(parsed.get("tech_stack", []))
    snippets = _normalize_snippets(parsed.get("relevant_code_snippets", []))
    observations = _normalize_string_list(parsed.get("codebase_observations", []))
    grounding_notes = _normalize_string_list(parsed.get("prompt_grounding_notes", []))

    # Step 2: Validate against what was actually shown to the LLM
    try:
        snippets, observations, grounding_notes = _validate_explore_output(
            snippets, observations, grounding_notes,
            file_contents=file_contents,
            max_lines_shown=max_lines,
        )
    except Exception as val_err:
        logger.warning("Explore output validation failed, using unvalidated data: %s", val_err)

    # Step 3: Construct CodebaseContext with validated data
    context = CodebaseContext(
        repo=repo_full_name,
        branch=used_branch,
        tech_stack=tech_stack,
        key_files_read=list(file_contents.keys()),
        relevant_snippets=snippets,
        observations=observations,
        grounding_notes=grounding_notes,
        files_read_count=len(file_contents),
        coverage_pct=min(100, round(len(file_contents) / max(1, total_in_tree) * 100)),
        duration_ms=duration_ms,
        explore_quality="complete" if parsed else "partial",
        retrieval_method=retrieval_method,
    )
```

- [ ] **Step 6: Run full test suite**

Run: `cd backend && pytest`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/codebase_explorer.py backend/tests/test_explore_phase.py
git commit -m "feat(explore): add post-LLM output validation for line number accuracy"
```

---

## Final Verification

- [ ] **Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: All pass, no regressions

- [ ] **Verify no import errors**

Run: `cd backend && python -c "from app.services.codebase_explorer import run_explore, _merge_file_lists, _extract_prompt_referenced_files, _validate_explore_output; print('OK')"`
Expected: `OK`

- [ ] **Final commit with all changes if any unstaged**

```bash
git status
# If any unstaged changes remain, add and commit
```
