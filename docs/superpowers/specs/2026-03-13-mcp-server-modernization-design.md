# MCP Server Modernization

**Date**: 2026-03-13
**Status**: Approved
**Scope**: `backend/app/mcp_server.py`, new `backend/app/schemas/mcp_models.py`, docs

## Problem

The MCP server has 18 tools that return untyped `str` (JSON-serialized), use loose function parameters without Pydantic validation, lack service prefixes for multi-server environments, and underutilize SDK features (structured output, progress reporting, context logging). This limits agent operability, schema discoverability, and production readiness.

## Goals

1. **Structured output** on all tools via Pydantic return types (auto-generates `outputSchema` + `structuredContent`)
2. **Pydantic input models** with `Field()` constraints for tools with 3+ parameters
3. **Service prefix** (`synthesis_`) on all 18 tool names — breaking rename
4. **Progress reporting** on long-running `optimize`/`retry` tools via `ctx.report_progress()`
5. **Consistency**: `ToolAnnotations(title=...)` and full docstrings on all tools
6. **Shared httpx client** in lifespan context for GitHub API connection pooling
7. **Server rename** from `"project-synthesis"` to `"synthesis_mcp"`

## Non-Goals

- Response format option (markdown vs JSON) — deferred
- OAuth 2.1 auth — deferred to auth milestone
- MCP resources/prompts registration — deferred
- `stateless_http=True` migration — deferred to scaling milestone

## Design

### New file: `backend/app/schemas/mcp_models.py`

All MCP-specific Pydantic models. Reuses existing models from `pipeline_outputs.py` and `feedback.py` where applicable.

**Input models** (tools with 3+ params):

| Model | Tool |
|-------|------|
| `OptimizeInput` | `synthesis_optimize` |
| `RetryInput` | `synthesis_retry` |
| `ListOptimizationsInput` | `synthesis_list_optimizations` |
| `SearchInput` | `synthesis_search_optimizations` |
| `GetByProjectInput` | `synthesis_get_by_project` |
| `TagInput` | `synthesis_tag_optimization` |
| `BatchDeleteInput` | `synthesis_batch_delete` |
| `GitHubReadFileInput` | `synthesis_github_read_file` |
| `GitHubSearchCodeInput` | `synthesis_github_search_code` |
| `SubmitFeedbackInput` | `synthesis_submit_feedback` |

All input models use `model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")`.

Simple tools (1-2 params) keep function parameters: `get_optimization`, `delete_optimization`, `restore`, `list_trash`, `github_list_repos`, `get_stats`, `get_branches`, `get_adaptation_state`.

**Output models**:

| Model | Used by |
|-------|---------|
| `OptimizationRecord` | `get_optimization`, `tag_optimization` |
| `PaginationEnvelope[T]` | `list_optimizations`, `search`, `list_trash`, `get_by_project` |
| `PipelineResult` | `optimize`, `retry` |
| `StatsResult` | `get_stats` |
| `DeleteResult` | `delete_optimization` |
| `BatchDeleteResult` | `batch_delete` |
| `RestoreResult` | `restore` |
| `GitHubRepoItem` / `list[GitHubRepoItem]` | `github_list_repos` |
| `GitHubFileContent` | `github_read_file` |
| `GitHubSearchResult` | `github_search_code` |
| `FeedbackSubmitResult` | `submit_feedback` |
| `BranchesResult` | `get_branches` |
| `AdaptationStateResponse` | `get_adaptation_state` (reuse from `feedback.py`) |
| `MCPError` | All tools on error path |

`OptimizationRecord` mirrors `Optimization.to_dict()` with all 50+ fields as Optional where nullable. JSON-stored list/dict columns are typed as `list[str]`, `dict[str, Any]`, etc.

`PipelineResult` has optional stage dicts (`analysis`, `strategy`, `optimization`, `validation`) plus `optimization_id: str`.

### Shared httpx client

Add `http_client: httpx.AsyncClient` to `MCPAppContext`. Created in lifespan with `timeout=30.0`, closed on shutdown. All 3 GitHub tools use it instead of creating per-request clients.

### Progress reporting

In `_run_and_persist`, accept an optional `progress_callback` async callable. Map pipeline stage events to progress fractions:

| Stage | Progress |
|-------|----------|
| explore_result | 0.20 |
| analysis | 0.40 |
| strategy | 0.55 |
| optimization | 0.80 |
| validation | 1.00 |

The `optimize` and `retry` tools pass `ctx.report_progress` as the callback.

### Tool rename mapping

| Old name | New name |
|----------|----------|
| `optimize` | `synthesis_optimize` |
| `get_optimization` | `synthesis_get_optimization` |
| `list_optimizations` | `synthesis_list_optimizations` |
| `search_optimizations` | `synthesis_search_optimizations` |
| `get_by_project` | `synthesis_get_by_project` |
| `get_stats` | `synthesis_get_stats` |
| `tag_optimization` | `synthesis_tag_optimization` |
| `delete_optimization` | `synthesis_delete_optimization` |
| `batch_delete_optimizations` | `synthesis_batch_delete` |
| `list_trash` | `synthesis_list_trash` |
| `restore_optimization` | `synthesis_restore` |
| `retry_optimization` | `synthesis_retry` |
| `github_list_repos` | `synthesis_github_list_repos` |
| `github_read_file` | `synthesis_github_read_file` |
| `github_search_code` | `synthesis_github_search_code` |
| `submit_feedback` | `synthesis_submit_feedback` |
| `get_branches` | `synthesis_get_branches` |
| `get_adaptation_state` | `synthesis_get_adaptation_state` |

Server name: `"project-synthesis"` → `"synthesis_mcp"`

### Error handling

Tools that can fail return a union type. Since FastMCP structured output doesn't support `Union` return types cleanly, error cases set `isError=True` on the `CallToolResult`. The happy path returns the typed model.

Pattern for error returns: continue returning `json.dumps({"error": ...})` as a string — the SDK wraps this in a `TextContent` block with `isError=True` when the tool raises. For clean separation, tools raise a custom `ToolError` exception that the framework converts.

Actually, simpler: FastMCP already converts exceptions to `isError` responses. For expected errors (not found, validation), return the Pydantic model on success and raise `ValueError` with an actionable message on failure. The SDK handles the rest.

### Affected files

| File | Change |
|------|--------|
| `backend/app/schemas/mcp_models.py` | **NEW** — all input/output Pydantic models |
| `backend/app/mcp_server.py` | Full rewrite of tool signatures, returns, annotations, docstrings |
| `docs/MCP.md` | Updated tool names, parameter docs, output schemas |
| `CLAUDE.md` | Updated tool names in MCP section, TOOL_CATEGORIES note |
| `CHANGELOG.md` | Release notes under Unreleased |

### Testing

- Existing `backend/tests/` — verify no regressions
- Manual MCP Inspector test of renamed tools
- `python -m py_compile backend/app/schemas/mcp_models.py` — syntax check
- `python -m py_compile backend/app/mcp_server.py` — syntax check

## Implementation Order

1. Create `mcp_models.py` (inputs + outputs)
2. Add shared httpx client + progress callback to `MCPAppContext` / `_run_and_persist`
3. Rewrite all 18 tools in `mcp_server.py` (rename, Pydantic I/O, annotations, docstrings, progress)
4. Update `TOOL_CATEGORIES` registry
5. Update `docs/MCP.md`
6. Update `CLAUDE.md`
7. Update `CHANGELOG.md`
8. Compile check + test run
