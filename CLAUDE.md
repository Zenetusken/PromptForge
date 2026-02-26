# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is PromptForge

An AI-powered prompt optimization web app. Users submit a raw prompt, and a 4-stage pipeline (Analyze → Strategy → Optimize → Validate) rewrites it using Claude, scores the result, and persists everything to a history database. Results stream to the frontend in real time via SSE.

## Tech Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy 2.0 async ORM / SQLite (aiosqlite) / Pydantic v2
- **Frontend**: SvelteKit 2 / Svelte 5 (runes: `$state`, `$derived`, `$effect`) / Tailwind CSS 4 / TypeScript 5.7+ / Vite 6
- **LLM access**: Provider-agnostic via `backend/app/providers/` — supports Claude CLI (default), Anthropic API, OpenAI, and Google Gemini. Auto-detects available provider or set `LLM_PROVIDER` explicitly.
- **MCP server**: FastMCP-based (`promptforge_mcp`), exposes 19 tools for Claude Code integration (`optimize`, `retry`, `get`, `list`, `get_by_project`, `search`, `tag`, `stats`, `delete`, `bulk_delete`, `list_projects`, `get_project`, `strategies`, `create_project`, `add_prompt`, `update_prompt`, `set_project_context`, `batch`, `cancel`) and 3 MCP Resources (`promptforge://projects`, `promptforge://projects/{id}/context`, `promptforge://optimizations/{id}`). All tool calls emit activity events to the backend via webhook (`_mcp_tracked` decorator) for real-time visibility in the frontend Network Monitor. Runs as SSE HTTP transport on port 8001 with uvicorn `--reload` for hot-reload. Managed by `init.sh` alongside backend/frontend. Auto-discoverable via `.mcp.json` (`type: sse`).

## Commands

```bash
# Full dev setup (installs deps, starts all services)
./init.sh

# Backend only (from project root)
cd backend && source venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend && npm run dev

# Backend tests (requires test extras)
cd backend && source venv/bin/activate
pip install -e ".[test]"
pytest                              # all tests
pytest tests/test_strategy_selector.py  # single test file

# Frontend tests
cd frontend
npm run test          # vitest run
npm run check         # svelte-check type checking

# MCP server (standalone, for testing — normally managed by init.sh)
cd backend && source venv/bin/activate
python -m uvicorn app.mcp_server:app --reload --port 8001

# Docker
docker-compose up     # starts backend (8000) + frontend (5199) + MCP (8001)
```

## Architecture

### Optimization Pipeline (`backend/app/services/pipeline.py`)

Four LLM-calling stages, orchestrated as an async generator that yields SSE events:

1. **Analyze** (`PromptAnalyzer`) — classifies task type, complexity, weaknesses, strengths
2. **Strategy Selection** (`StrategySelector`) — LLM-based strategy selection with heuristic fallback. Sends analysis and prompt to the LLM to pick from 10 frameworks: co-star, risen, chain-of-thought, few-shot-scaffolding, role-task-format, structured-output, step-by-step, constraint-injection, context-enrichment, persona-assignment. Returns strategy name, reasoning, and confidence (0.0–1.0). Falls back to `HeuristicStrategySelector` (3-tier priority system with specificity exemptions and redundancy detection) on LLM errors. Users can override strategy via the UI or API (bypasses LLM call).
3. **Optimize** (`PromptOptimizer`) — rewrites the prompt using the selected strategy
4. **Validate** (`PromptValidator`) — scores clarity/specificity/structure/faithfulness (0.0–1.0), generates verdict

All 4 stages accept an optional `codebase_context` parameter (`CodebaseContext` dataclass from `backend/app/schemas/context.py`). When provided, each stage injects the rendered context into its LLM user message so the optimizer produces prompts grounded in actual codebase patterns, conventions, and architecture. Context is resolved via a merge pipeline: project context profile (stored on the `Project` record) serves as the base, explicit per-request `codebase_context` overrides individual fields, and the resolved result is snapshotted on the `Optimization` record for reproducibility. Accepted via the `codebase_context` dict parameter on both the MCP `optimize` tool and the `POST /api/optimize` HTTP endpoint. Fields: `language`, `framework`, `description`, `conventions`, `patterns`, `code_snippets`, `documentation`, `test_framework`, `test_patterns` — all optional, unknown keys silently ignored.

LLM calls go through the provider abstraction (`backend/app/providers/`). `LLMProvider` is the abstract base with `send_message` and `send_message_json` (4-strategy JSON extraction: direct parse → json fence → generic fence → brace match). Concrete providers: `ClaudeCLIProvider` (default, MAX subscription), `AnthropicAPIProvider`, `OpenAIProvider`, `GeminiProvider`. `get_provider()` auto-detects or uses explicit `LLM_PROVIDER` env var. Runtime API key and model overrides are passed via `X-LLM-API-Key` and `X-LLM-Model` HTTP headers (never in request bodies or logs). Model catalog (`backend/app/providers/models.py`) defines 2 models per provider (performance + cost-effective tier). `AnthropicAPIProvider` enables prompt caching (`cache_control={"type": "ephemeral"}`) on all API calls, tracks `cache_creation_input_tokens` and `cache_read_input_tokens` in `TokenUsage`, uses the SDK's typed exception hierarchy (`_classify_anthropic_error`) instead of string matching, and provides async `count_tokens()` via the SDK's `messages.count_tokens()` endpoint with heuristic fallback. `LLMProvider.count_tokens()` is an `async` method across all providers.

### SSE Streaming

Backend emits named SSE events: `stage`, `step_progress`, `strategy`, `analysis`, `optimization`, `validation`, `complete`, `error`. Stage lifecycle configs live in `backend/app/constants.py` (`StageConfig` dataclass with progress messages and intervals). The `strategy` event carries structured data: `{strategy, reasoning, task_type, confidence}`.

Frontend consumes SSE via `fetch` + `ReadableStream` reader (not native `EventSource`). The mapping from backend events to frontend `PipelineEvent` types is in `frontend/src/lib/api/client.ts:mapSSEEvent`. The `strategy` backend event maps to a dedicated `strategy_selected` frontend event type that preserves all structured fields (confidence, reasoning, task_type).

### MCP Activity Feed

Real-time bridge from MCP server tool calls to the PromptForge frontend. When external clients (Claude Code, IDEs) invoke MCP tools, the activity appears live in the Network Monitor window, taskbar indicator, Task Manager, Terminal log, and notifications.

**Backend** (`backend/app/services/mcp_activity.py`): `MCPActivityBroadcaster` singleton with in-memory pub/sub. `MCPEventType` enum: `tool_start`, `tool_progress`, `tool_complete`, `tool_error`, `session_connect`, `session_disconnect`. Bounded history (100 events), subscriber queues (max 256 per client, slow clients evicted). Router (`backend/app/routers/mcp_activity.py`): `POST /internal/mcp-event` webhook (auth-exempt), `GET /api/mcp/events` SSE stream (snapshot + live), `GET /api/mcp/status` REST fallback.

**MCP Server** (`backend/app/mcp_server.py`): `_mcp_tracked(tool_name)` decorator wraps all 19 tool handlers. Emits `tool_start`/`tool_complete`/`tool_error` events via fire-and-forget HTTP POST to `http://127.0.0.1:8000/internal/mcp-event`. Never fails the tool call if the webhook is down. `_extract_result_summary()` pulls `id`, `status`, `overall_score`, `total` from results.

**MCP Resources**: 3 read-only resources via `@mcp.resource()` — `promptforge://projects` (active project list), `promptforge://projects/{id}/context` (project codebase context profile), `promptforge://optimizations/{id}` (full optimization result). Claude Code can reference these as `@promptforge:projects/...` for context.

**Frontend** (`frontend/src/lib/services/mcpActivityFeed.svelte.ts`): SSE client with auto-reconnect (exponential backoff 3s→30s). Reactive state: `events`, `activeCalls`, `sessionCount`, `connected`. Emits `mcp:*` events on SystemBus. Bootstrapped in `+layout.svelte` `onMount`. `NetworkMonitorWindow` component provides 3-tab UI (Live Activity, Event Log, Connections). Taskbar shows activity indicator when feed is connected. TaskManager shows External (MCP) section. Terminal adds `mcp`, `mcp-log`, `netmon` commands. Notifications fire for write-tool completions (`optimize`, `retry`, `batch`, `create_project`, `cancel`) with "Open in IDE" actions. History/stats auto-reload on external MCP write-tool completion (debounced 1s).

### Data Layer

- **Repository pattern**: `OptimizationRepository` (`backend/app/repositories/optimization.py`) handles all DB queries; `ProjectRepository` (`backend/app/repositories/project.py`) for projects/prompts
- **Converters**: `backend/app/converters.py` transforms ORM → Pydantic/dict, handles score normalization
- **Score normalization**: DB stores 0.0–1.0 floats; display/API uses 1–10 integers (`backend/app/utils/scores.py`)
- **Legacy migration**: On startup, `_migrate_legacy_projects()` in `database.py` seeds the `projects` table from distinct `optimization.project` string values and imports unique `raw_prompt` values as `Prompt` entries. Idempotent (safe on every restart).
- **Auto-create projects**: When an optimization is created/retried with a `project` name (via API or MCP), a matching `Project` record is auto-created if it doesn't exist (`ensure_project_by_name` in `repositories/project.py`). Reactivates soft-deleted projects.
- **Prompt version history**: `PromptVersion` table (`models/project.py`) stores immutable snapshots of prior prompt content. Created automatically by `update_prompt()` when content changes. Current version lives in `prompts.content`; only superseded versions are snapshotted.
- **Forge result linking**: `Optimization.prompt_id` FK links an optimization to the project prompt that triggered it. Set when forging from a project prompt card. Nullable for legacy/home-page optimizations. DB constraint is `ON DELETE SET NULL`, but application-level `delete_prompt()` explicitly removes linked optimizations before deleting the prompt.
- **Project deletion cascade**: `delete_project_data()` in `ProjectRepository` deletes all prompts (reusing `delete_prompt()` per prompt) then sweeps remaining legacy optimizations by project name. The router calls this before soft-deleting the project record.
- **Project context profiles**: `Project.context_profile` (JSON text column) stores a persistent `CodebaseContext` for each project. When an optimization references a project (by name), the pipeline resolves context via `merge_contexts(project_context, explicit_context)` — explicit per-request fields override the project profile. The resolved context is snapshotted as `Optimization.codebase_context_snapshot` (JSON text column) so every optimization is self-documenting. Managed via `PUT /api/projects/{id}` (set/clear `context_profile`), MCP `set_project_context` tool, or the `ContextProfileEditor` component on the project detail page. `ProjectSummaryResponse.has_context` boolean drives green-dot indicators in the sidebar. Stack templates (`frontend/src/lib/utils/stackTemplates.ts`) provide 8 pre-built profiles for common stacks.
- **Extended analytics** (`get_stats()` in `OptimizationRepository`): Beyond basic strategy distribution and score averages, the stats endpoint computes 10 additional DB-driven analytics: score matrix (strategy × task-type avg scores), score variance (min/max/stddev per strategy), confidence averages, combo effectiveness (primary+secondary pair scores), complexity performance, improvement rates per strategy, error rates (includes non-completed records), time trends (7d/30d), token economics (avg input/output tokens and duration), and win rates (best strategy per task type). All respect project-scope filters and legacy alias normalization. Nullable fields default to `None` on empty DB for backward compatibility. The stats endpoint (`GET /api/history/stats`) accepts an optional `project` query parameter to scope all stats to a single project. `total_projects` counts active projects from the `projects` table (not from optimizations) to exclude archived projects.

### Frontend

Svelte 5 runes-based stores in `frontend/src/lib/stores/`, shared color/strategy/recommendation utilities in `frontend/src/lib/utils/`, and key components in `frontend/src/lib/components/`. One route: `/` (content dashboard). All project and forge interactions happen through the persistent window system (ProjectsWindow, HistoryWindow, IDE) — there are no detail page routes.

**OS Metaphor Architecture**: The frontend follows an operating system metaphor — Dashboard = Desktop, Sidebar = Start Menu, IDE = VS Code program.

- **Window Manager** (`windowManager.svelte.ts`): Multi-window system with z-index stacking and sessionStorage persistence. `PERSISTENT_WINDOW_IDS` (`ide`, `recycle-bin`, `projects`, `history`) survive route changes and minimize on active taskbar click. Breadcrumb address bar: `setBreadcrumbs(id, segments)` / `getBreadcrumbs(id)` — Projects/History windows manage their own breadcrumbs via `onMount`; `DesktopWindow.svelte` renders them between title bar and content. `WindowNavigation` interface: `set/get/clearNavigation(id, nav)` — per-window back/forward state (not persisted; callbacks rebuilt by components on mount). `DesktopWindow` renders back/forward chevron buttons in the address bar when navigation state exists. ProjectsWindow uses drill-down navigation (list → project prompts) with back/forward history stacks; `pendingNavigateProjectId` + `navigateToProject()` on `ProjectsState` lets external code (StartMenu, ResultActions) request the ProjectsWindow to drill into a project. Convenience openers: `openIDE()`, `openProjectsWindow()`, `openHistoryWindow()`, `focusDashboard()`. Derived: `ideVisible` (true when IDE exists + not minimized), `ideSpawned`. Desktop icons for Projects/History open dedicated `DesktopWindow`s (not the Start Menu).
- **Scoped Results** (`optimization.svelte.ts`): Two separate result slots prevent clobbering — `forgeResult` (set by SSE pipeline) and `viewResult` (set by `loadFromHistory()`). The `result` getter returns `forgeResult ?? viewResult`. `resetForge()` clears forge-side state while preserving `viewResult`.
- **Forge Machine** (`forgeMachine.svelte.ts`): IDE mode state machine (`compose` → `forging` → `review` / `compare`). Manages panel width (auto-widen on forge/compare), minimize/restore state, and `ComparisonSlots`. Derived: `runningCount` (from `processScheduler`), `widthTier`, `isCompact`. Persisted to sessionStorage.
- **Taskbar** (`ForgeTaskbar.svelte`): Horizontal strip of process buttons shown when IDE is hidden and processes exist. Click running → open IDE, click completed → load result into `forgeResult` and open IDE in review mode.
- **IDE-Native Interactions**: All entry points open results in the IDE — no detail page routes exist. HistoryWindow double-click/context "Open in IDE" calls `optimizationState.openInIDEFromHistory(id)`. StartMenu recent forges do the same. StartMenu project clicks call `projectsState.navigateToProject(id)` + `openProjectsWindow()`. ProjectsWindow prompt double-click uses `openPromptInIDE()` (from `$lib/utils/promptOpener.ts`): if the prompt has forges, opens latest forge in IDE review mode with reiterate context; if no forges, opens in compose mode. Running forges section appears above history list when active.
- **Prompt Opener** (`$lib/utils/promptOpener.ts`): `openPromptInIDE({ promptId, projectId, projectData?, prompt? })` — resolves project/prompt data, then branches: forge_count > 0 → `openInIDEFromHistory` + `loadRequest(reiterate)` + `enterReview()`; forge_count === 0 → `restore()` + `loadRequest(optimize)` (which internally opens IDE).
- **Tab Bounds & Per-Tab State**: `MAX_TABS = 5` with LRU eviction of non-active tabs in `forgeSession.loadRequest()`. Each `WorkspaceTab` carries `resultId` (bound optimization ID) and `mode` (`ForgeMode`) so switching/closing tabs correctly saves and restores the inspector panel state. Tab coordination (`tabCoherence.ts`) provides `saveActiveTabState()` and `restoreTabState(tab)` — used by `ForgeIDEEditor` tab operations, keyboard shortcuts (`Ctrl+W`/`Ctrl+N`), and layout `$effect`s. Forging guards block tab switching, closing the active tab, and new tab creation during an active forge. Hydration resets `'forging'` to `'compose'` and defaults missing fields; `ForgeIDEWorkspace.onMount` restores results from the server on page reload.
- **Compare Robustness**: `ForgeCompare.svelte` has async server fallback with staleness guards — when `resultHistory` misses a slot ID, it fetches from the server via `fetchOptimization()` with loading/error/empty UI states and race-condition protection.
- **Keyboard Shortcuts**: `Ctrl/Cmd+M` toggles minimize, `Escape` restores/closes IDE, `/` focuses textarea, `Ctrl/Cmd+N` new tab, `Ctrl/Cmd+W` close tab.
- **Transitions**: IDE open/close uses `fly` transition (window feel) vs `fade` for dashboard content.
- **System Bus** (`$lib/services/systemBus.svelte.ts`): Decoupled IPC for inter-store events — `forge:started/completed/failed/cancelled`, `window:opened/closed/focused`, `clipboard:copied`, `provider:*`, `history:reload`, `stats:reload`, `notification:show`. Handlers: `on(type, handler)`, `once()`, wildcard `'*'`. Tracks recent events for debugging.
- **Services Layer** (`$lib/services/`): `notificationService` (system notifications with read/unread/actions, auto-dismiss, max 50), `clipboardService` (copy with history + bus integration), `commandPalette` (fuzzy-matched commands with Ctrl+K activation).
- **Process Scheduler** (`processScheduler.svelte.ts`): Single source of truth for all forge process lifecycle. Methods: `spawn(config)`, `complete(id, data)`, `fail(id)`, `cancel(id)`, `dismiss(pid)`, `updateProgress(id, stage, progress)`. Bounded-concurrency queue — `maxConcurrent` (default 2) limits parallel forges. Tracks `queue`, `running`, `completed` process lists, `runningCount`, `canSpawn`, `activeProcess`. Persisted to sessionStorage; running processes become `'error'` on hydrate (can't resume callbacks). Wired into `startOptimization()`, SSE event handlers, and tournament forges. Rate-limit aware via `provider:rate_limited` bus events.
- **Settings Store** (`settings.svelte.ts`): Persisted user preferences — `accentColor`, `defaultStrategy`, `maxConcurrentForges`, `enableAnimations`, `autoRetryOnRateLimit`. Persisted to localStorage with schema migration.
- **Additional Windows**: `ControlPanelWindow` (provider/pipeline/display/system settings), `TaskManagerWindow` (process monitor), `BatchProcessorWindow` (multi-prompt batch optimization), `StrategyWorkshopWindow` (score heatmap, win rates, combo analysis), `TemplateLibraryWindow` (prompt templates with search/categories), `TerminalWindow` (system bus event log), `NetworkMonitorWindow` (real-time MCP tool call activity: live calls, event log, connections), `RecycleBinWindow` (soft-deleted items).
- **Token Budget Manager** (backend: `backend/app/services/token_budget.py`): Per-provider token tracking with optional daily limits. Records usage at pipeline completion. Exposes `to_dict()` for health endpoint integration.

For detailed store APIs, component catalog, utility reference, and route descriptions, see [`docs/frontend-internals.md`](docs/frontend-internals.md).

## Developer Documentation

The following docs contain implementation details that **must be kept in sync** when changes are made to the corresponding code, just as CLAUDE.md itself is updated:

| Doc | Covers | Update when changing... |
|-----|--------|------------------------|
| [`docs/frontend-internals.md`](docs/frontend-internals.md) | Stores, utilities, components, routes | Any frontend store, shared utility, key component, or route |
| [`docs/frontend-components.md`](docs/frontend-components.md) | All 62 Svelte components: shared vs individual, props, store deps, patterns | Adding/removing/renaming components, changing props or store dependencies |
| [`docs/backend-middleware.md`](docs/backend-middleware.md) | Middleware stack order, per-layer config | Middleware add/remove/reorder, config values, security headers |
| [`docs/backend-database.md`](docs/backend-database.md) | PRAGMAs, migrations, startup sequence, models, repositories | Schema changes, new migrations, startup hooks, repository methods |
| [`docs/backend-caching.md`](docs/backend-caching.md) | Stats cache, invalidation points, provider staleness, LLM caching | Cache TTLs, new invalidation points, polling behavior |

## API Endpoints

| Method | Path | SSE |
|--------|------|-----|
| POST | `/api/optimize` | Yes |
| GET | `/api/optimize/{id}` | No |
| POST | `/api/optimize/batch` | No |
| POST | `/api/optimize/{id}/retry` | Yes |
| POST | `/api/optimize/{id}/cancel` | No |
| GET/HEAD | `/api/history` | No |
| DELETE | `/api/history/{id}` | No |
| POST | `/api/history/bulk-delete` | No |
| DELETE | `/api/history/all` | No |
| GET/HEAD | `/api/history/stats` | No |
| GET/HEAD | `/api/health` | No |
| GET | `/api/providers` | No |
| POST | `/api/providers/validate-key` | No |
| GET | `/api/projects` | No |
| POST | `/api/projects` | No |
| GET | `/api/projects/{id}` | No |
| PUT | `/api/projects/{id}` | No |
| DELETE | `/api/projects/{id}` | No |
| POST | `/api/projects/{id}/archive` | No |
| POST | `/api/projects/{id}/unarchive` | No |
| POST | `/api/projects/{id}/prompts` | No |
| PUT | `/api/projects/{id}/prompts/reorder` | No |
| GET | `/api/projects/{id}/prompts/{pid}/versions` | No |
| GET | `/api/projects/{id}/prompts/{pid}/forges` | No |
| PUT | `/api/projects/{id}/prompts/{pid}` | No |
| DELETE | `/api/projects/{id}/prompts/{pid}` | No |
| POST | `/internal/mcp-event` | No |
| GET | `/api/mcp/events` | Yes |
| GET | `/api/mcp/status` | No |
| POST | `/api/orchestrate/analyze` | No |
| POST | `/api/orchestrate/strategy` | No |
| POST | `/api/orchestrate/optimize` | No |
| POST | `/api/orchestrate/validate` | No |

## Configuration

Environment defaults (set in `backend/app/config.py`, overridable via `.env`):
- `FRONTEND_URL` — default `http://localhost:5199`
- `BACKEND_PORT` — default `8000`
- `HOST` — default `0.0.0.0`
- `MCP_PORT` — default `8001` (managed by `init.sh`, not config.py)
- `DATABASE_URL` — default `sqlite+aiosqlite:///<project>/data/promptforge.db`
- `LLM_PROVIDER` — auto-detect when empty; explicit: `claude-cli`, `anthropic`, `openai`, `gemini`
- `CLAUDE_MODEL` — default `claude-opus-4-6` (used by Claude CLI and Anthropic API providers)
- `ANTHROPIC_API_KEY` — leave empty to use MAX subscription via Claude CLI
- `OPENAI_API_KEY` — set to enable OpenAI provider
- `OPENAI_MODEL` — default `gpt-4.1`
- `GEMINI_API_KEY` — set to enable Gemini provider
- `GEMINI_MODEL` — default `gemini-2.5-pro`

## Testing

Run all tests: `./init.sh test`

### Backend (pytest, async)

- **Config**: `pyproject.toml` — `asyncio_mode = "auto"`, extras in `[test]`
- **Fixtures** (`tests/conftest.py`): `db_engine` (in-memory SQLite), `db_session`, `client` (httpx AsyncClient with FastAPI dependency override)
- **File naming**: `tests/test_{module}.py` — one file per module/concern
- **Structure**: Group related tests in classes (`class TestGetById`, `class TestCreate`). Use `@pytest.mark.asyncio` on each async test method. Top-level functions for standalone tests.
- **Mocking LLM calls**: Create a `FakeProvider(LLMProvider)` that returns canned responses. Patch `get_provider` where needed.
- **DB tests**: Use `db_session` fixture, write `_seed()` helpers for test data factories.
- **Router tests**: Use `client` fixture, assert status codes + response JSON.
- **No external calls**: All tests run offline — LLM providers are mocked, DB is in-memory.

### Frontend (vitest, Svelte 5)

- **Config**: `vite.config.ts` — `test.include: ['src/**/*.test.ts']`, `environment: 'jsdom'`, `svelteTesting()` plugin
- **File naming**: Co-located `{module}.test.ts` next to source file
- **Structure**: `describe`/`it` blocks. Use `vi.mock()` for module mocking, `vi.fn()` for stubs.
- **Store tests**: Import the store, set state in `beforeEach`, assert reactive properties.
- **Component tests**: Use `@testing-library/svelte` (`render`, `screen`, `fireEvent`). Clear `document.body` in `beforeEach`. Add `data-testid` attributes for querying.
- **Browser APIs**: Stub `sessionStorage`/`localStorage` with in-memory objects when testing in Node.

## Linting

- **Ruff**: target py314, line-length 100, rules: E/F/I/W (configured in `pyproject.toml`)
- **Pyright**: basic type checking mode, py314 (configured in `pyproject.toml`)
- **svelte-check**: `npm run check` in frontend

## Frontend Theme

**Design Philosophy (Absolute Edge):** Strict "flat neon contour" directive. **ZERO glow effects, drop shadows, or text blooms.** Interactions rely purely on sharp 1px borders, vector color shifts, and precise micro-interactions (like an Iguana Bar neon sign). Emulate hardware precision.

Cyberpunk palette defined in `frontend/src/app.css` with CSS custom properties and canonical values in `.claude/skills/brand-guidelines.md`:

**Neon palette (10 colors):** `neon-cyan` (#00e5ff), `neon-purple` (#a855f7), `neon-green` (#22ff88), `neon-red` (#ff3366), `neon-yellow` (#fbbf24), `neon-orange` (#ff8c00), `neon-blue` (#4d8eff), `neon-pink` (#ff6eb4), `neon-teal` (#00d4aa), `neon-indigo` (#7b61ff).

**Backgrounds:** `bg-primary` (#06060c), `bg-secondary` (#0c0c16), `bg-card` (#11111e), `bg-input` (#0a0a14), `bg-hover` (#16162a), `bg-glass` (rgba(12, 12, 22, 0.7)).

**Text hierarchy:** `text-primary` (#e4e4f0), `text-secondary` (#8b8ba8), `text-dim` (#7a7a9e).

Custom animations: `copy-flash`, `fade-in`, `shimmer`, `shimmer-text` (no glowing pulse effects allowed).
