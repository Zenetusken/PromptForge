# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is PromptForge

An AI-powered prompt optimization platform with an OS kernel architecture. PromptForge runs as an installable app on a shared kernel, enabling a community developer ecosystem of LLM-powered applications.

Users submit a raw prompt, and a 4-stage pipeline (Analyze → Strategy → Optimize → Validate) rewrites it using Claude, scores the result, and persists everything to a history database. Results stream to the frontend in real time via SSE.

## Tech Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy 2.0 async ORM / SQLite (aiosqlite) / Pydantic v2
- **Frontend**: SvelteKit 2 / Svelte 5 (runes: `$state`, `$derived`, `$effect`) / Tailwind CSS 4 / TypeScript 5.7+ / Vite 6
- **LLM access**: Provider-agnostic via `backend/app/providers/` — Claude CLI (default), Anthropic API, OpenAI, Gemini. Auto-detects or set `LLM_PROVIDER`.
- **MCP server**: FastMCP (`backend/app/mcp_server.py`) — 22 tools, 4 resources, SSE transport on port 8001. Auto-discoverable via `.mcp.json`.
- **App Platform**: OS kernel architecture with app registry, manifest-driven discovery, lifecycle hooks.

## Commands

```bash
# Dev setup (installs deps, starts backend:8000 + frontend:5199 + MCP:8001)
./init.sh

# Built mode (pre-built assets, no hot-reload)
./init.sh build

# Other: stop | restart | restart-build | status | test | seed | mcp | help

# Backend tests
cd backend && source venv/bin/activate
pip install -e ".[test]"
pytest                                  # all
pytest tests/test_strategy_selector.py  # single file

# Frontend tests
cd frontend
npm run test    # vitest
npm run check   # svelte-check

# Docker
docker-compose up  # backend (8000) + frontend (5199) + MCP (8001)
```

## Architecture

For the full reference see [ARCHITECTURE.md](ARCHITECTURE.md). This section covers patterns and conventions needed for day-to-day development.

### OS Kernel Architecture

The codebase follows a kernel + apps architecture inspired by Django's app system:

```
backend/
  kernel/                          # OS kernel (app discovery + lifecycle)
    registry/                      # App discovery, manifest, lifecycle
      app_registry.py              # AppRegistry singleton — discover, mount_routers
      manifest.py                  # AppManifest Pydantic model
      hooks.py                     # AppBase ABC (lifecycle hooks)
    routers/                       # Kernel API (/api/kernel/*)

  apps/
    promptforge/                   # PromptForge as an installable app
      manifest.json                # App manifest (windows, routes, commands)
      app.py                       # PromptForgeApp(AppBase) — lifecycle + migrations
    hello_world/                   # Example app
      manifest.json
      app.py                       # HelloWorldApp(AppBase)
      router.py                    # /api/apps/hello-world/*

  app/                             # PromptForge host application
    main.py                        # Entry point — boots kernel, discovers apps, mounts routers
    database.py config.py          # DB engine, migrations, system config
    providers/ middleware/          # LLM providers, security middleware
    routers/ services/ models/     # Business logic (PromptForge-specific)

frontend/src/lib/
  kernel/                          # Shell (app registry, types)
    types.ts                       # AppFrontend, KernelAPI, WindowRegistration
    services/
      appRegistry.svelte.ts        # Frontend app registry — registry-driven windows
  apps/
    promptforge/                   # PromptForge frontend app
      index.ts                     # PromptForgeApp implements AppFrontend (14 windows)
    hello_world/                   # Example frontend app
      index.ts                     # HelloWorldApp implements AppFrontend
      HelloWorldWindow.svelte
```

**Key classes:**
- `AppBase` (ABC) — lifecycle hooks: `on_install`, `on_enable`, `on_startup`, `on_shutdown`, `run_migrations`
- `AppRegistry` — discovers `manifest.json` in `apps/`, loads entry points, mounts routers (with `exclude` for host app)
- `AppManifest` — Pydantic model for `manifest.json` (backend routers, frontend windows, commands, file types)
- `AppFrontend` (interface) — frontend apps implement `init`, `destroy`, `getComponent`

**API convention:** Kernel at `/api/kernel/*`, apps at `/api/apps/{app_id}/*`. PromptForge (host app) keeps its routes at `/api/*` directly.

**Frontend window rendering:** `+layout.svelte` uses a single `{#each appRegistry.allWindows}` loop to render all manifest-declared windows dynamically. IDE window is a special case (static import, custom close handler). Folder windows are dynamically created at runtime (not manifest-declared).

### Pipeline (`backend/app/services/pipeline.py`)

Four LLM stages orchestrated as an async generator yielding SSE events:

1. **Analyze** — task type, complexity, weaknesses, strengths
2. **Strategy** — LLM selects from 10 frameworks (co-star, risen, chain-of-thought, few-shot-scaffolding, role-task-format, structured-output, step-by-step, constraint-injection, context-enrichment, persona-assignment). Heuristic fallback on LLM errors. Users can override via UI/API.
3. **Optimize** — rewrites the prompt using the selected strategy
4. **Validate** — scores 5 dimensions, generates verdict

Score weights (server-computed, never trusts LLM arithmetic): clarity 20% + specificity 20% + structure 15% + faithfulness 25% + conciseness 20%. `framework_adherence_score` is supplementary (not in weighted average). DB stores 0.0–1.0 floats; display/API uses 1–10 integers (`backend/app/utils/scores.py`).

All stages accept optional `codebase_context` (from `backend/app/schemas/context.py`). Context resolved via **three-layer merge**: (1) workspace auto-context → (2) project `context_profile` → (3) per-request `codebase_context`. Resolved context snapshotted as `Optimization.codebase_context_snapshot`.

### Provider Abstraction (`backend/app/providers/`)

`LLMProvider` ABC with `send_message`, `send_message_json` (4-strategy JSON extraction), `complete`, `stream`, `count_tokens`. Concrete: `ClaudeCLIProvider`, `AnthropicAPIProvider`, `OpenAIProvider`, `GeminiProvider`. Runtime overrides via `X-LLM-API-Key`, `X-LLM-Model`, and `X-LLM-Provider` headers (never in bodies or logs).

### SSE Events

Backend emits: `stage`, `step_progress`, `strategy`, `analysis`, `optimization`, `validation`, `iteration`, `complete`, `error`. Frontend consumes via `fetch` + `ReadableStream` (not `EventSource`). Event mapping in `frontend/src/lib/api/client.ts:mapSSEEvent`.

### MCP Activity Bridge

MCP tools wrapped with `_mcp_tracked()` → fire-and-forget webhook to `POST /internal/mcp-event` → `MCPActivityBroadcaster` → SSE stream at `GET /api/mcp/events` (supports `Last-Event-ID`) → frontend `MCPActivityFeed` service. Write-tool completions trigger notifications and history/stats reload.

### Data Layer

- **Repository pattern**: `OptimizationRepository`, `ProjectRepository`, `WorkspaceRepository` — all DB queries isolated from business logic
- **Hierarchical folders**: `Project.parent_id` (self-FK, max depth 8 via `MAX_FOLDER_DEPTH`). `Prompt.project_id` nullable (NULL = desktop). Backend: `get_children()`, `get_subtree()` (recursive CTE), `get_path()`, `move_project()` (validates circular refs + depth + uniqueness). Frontend: `FilesystemOrchestratorState` provides caching, mutations, and drop validation.
- **Deletion cascade**: `delete_project_data()` recursively deletes child folders (depth-first), then prompts (which removes linked optimizations), then sweeps legacy optimizations by project name.
- **Auto-create projects**: Optimizations with a `project` name auto-create matching `Project` records. Reactivates soft-deleted projects.
- **Prompt versioning**: `PromptVersion` snapshots auto-created by `update_prompt()` before overwriting content.
- **Forge linking**: `Optimization.prompt_id` FK → `Prompt`. `ON DELETE SET NULL` in DB, but app-level `delete_prompt()` removes linked optimizations first.
- **Comparative evaluation**: `Optimization.retry_of` links retries; score deltas computed on-the-fly. `detected_patterns` records observed strategies.

### Frontend

One route: `/` (content dashboard). All interactions through the persistent window system — no detail page routes.

**OS Metaphor**: Dashboard = Desktop, Sidebar = Start Menu, IDE = VS Code program.

- **Window Manager** (`windowManager.svelte.ts`): Multi-window with z-index stacking. Dual-layer persistence: sessionStorage for session state, localStorage for geometry prefs. 13 persistent window IDs survive route changes. Snap layouts (`snapLayout.ts`): 7 preset layouts, magnetic edge snapping, snap groups with lock/dissolve.
- **Forge Machine** (`forgeMachine.svelte.ts`): State machine `compose` → `forging` → `review` / `compare`. Mode + isMinimized persisted to sessionStorage; panel width to localStorage.
- **PFFS Type System**: `FileDescriptor` discriminated union (`prompt | artifact | sub-artifact | template`) in `fileDescriptor.ts`. `FileExtension` registry (`.md`, `.forge`, `.scan`, `.val`, `.strat`, `.tmpl`, `.app`, `.lnk`). `ArtifactKind` enum in `fileTypes.ts`. Unified document opener (`documentOpener.ts`): single `openDocument(descriptor)` entry point for all contexts.
- **Tab System**: `MAX_TABS = 5` with LRU eviction. Each `WorkspaceTab` carries `resultId`, `mode`, `document`. `tabCoherence.ts` handles save/restore. Forging guards block tab operations during active forges.
- **Scoped Results** (`optimization.svelte.ts`): `forgeResult` (from SSE) and `viewResult` (from history) as separate slots. `result` returns `forgeResult ?? viewResult`.
- **Process Scheduler** (`processScheduler.svelte.ts`): Bounded-concurrency queue (`maxConcurrent` from settings, default 2). Tracks running/queued/completed processes. Persisted to sessionStorage.
- **System Bus** (`systemBus.svelte.ts`): Decoupled IPC — `forge:*` (started/completed/failed/cancelled/progress), `window:*`, `provider:*` (rate_limited/unavailable/available), `mcp:*` (tool_start/tool_progress/tool_complete/tool_error/session_connect/session_disconnect), `workspace:*`, `fs:*`, `snap:*`, `clipboard:copied`, `history:reload`, `stats:reload`, `notification:show`, `tournament:completed`.
- **Services**: `notificationService` (subscribes to 13 bus events, max 50, auto-dismiss), `clipboardService`, `commandPalette` (Ctrl+K), `mcpActivityFeed` (SSE with auto-reconnect and `Last-Event-ID`).
- **Settings** (`settings.svelte.ts`): `accentColor`, `defaultStrategy`, `maxConcurrentForges`, `enableAnimations`, `wallpaperMode`, `wallpaperOpacity`, `performanceProfile`. Drives CSS custom properties on `:root`.
- **Windows**: ControlPanel, TaskManager, BatchProcessor, StrategyWorkshop, TemplateLibrary, Terminal, NetworkMonitor, RecycleBin, Workspace, DisplaySettings, FolderWindow.

## Developer Documentation

The following docs contain implementation details that **must be kept in sync** when changes are made to the corresponding code, just as CLAUDE.md itself is updated:

| Doc | Covers | Update when changing... |
|-----|--------|------------------------|
| [`docs/frontend-internals.md`](docs/frontend-internals.md) | Stores, utilities, components, routes | Any frontend store, shared utility, key component, or route |
| [`docs/frontend-components.md`](docs/frontend-components.md) | All Svelte components: shared vs individual, props, store deps, patterns | Adding/removing/renaming components, changing props or store dependencies |
| [`docs/backend-middleware.md`](docs/backend-middleware.md) | Middleware stack order, per-layer config | Middleware add/remove/reorder, config values, security headers |
| [`docs/backend-database.md`](docs/backend-database.md) | PRAGMAs, migrations, startup sequence, models, repositories | Schema changes, new migrations, startup hooks, repository methods |
| [`docs/backend-caching.md`](docs/backend-caching.md) | Stats cache, invalidation points, provider staleness, LLM caching | Cache TTLs, new invalidation points, polling behavior |
| [`docs/pffs-filesystem.md`](docs/pffs-filesystem.md) | PFFS type system, descriptors, document routing, desktop hierarchy, orchestrator, backend API, drag & drop | File extensions, artifact kinds, descriptor types, filesystem endpoints, folder/prompt operations, desktop sync |

### CHANGELOG.md Guidelines

Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Update when shipping user-visible changes.

**Format rules:**
- One `### Added/Changed/Fixed/Removed/Security/Performance` heading per version — never duplicate a heading
- Group related items under a **bold label** on one line, then bullet details below (e.g., `**Snap Layout System**` followed by feature bullets)
- Each bullet: one sentence, start with the component or scope, include the key technical detail. No paragraph-length entries.
- Omit internal refactors, lint fixes, and doc-only changes unless they affect developer workflow
- New API endpoints: list method + path. New MCP tools: list tool name. New components: list component name. Don't repeat what CLAUDE.md already documents in detail.
- Keep `[Unreleased]` lean — when it grows past ~200 lines, cut a version release

**Token budget awareness:** CHANGELOG is a historical record, not a design doc. If an entry needs more than 2 lines to explain, the detail belongs in CLAUDE.md or a `docs/` file instead. Link rather than inline.

## Configuration

Essential defaults (full list in [ARCHITECTURE.md](ARCHITECTURE.md#section-10-deployment--configuration) and `.env.example`):

| Variable | Default | Notes |
|----------|---------|-------|
| `FRONTEND_URL` | `http://localhost:5199` | CORS origins |
| `BACKEND_PORT` | `8000` | |
| `MCP_PORT` | `8001` | Bound to `127.0.0.1` by default |
| `DATABASE_URL` | `sqlite+aiosqlite:///...data/promptforge.db` | |
| `LLM_PROVIDER` | *(auto-detect)* | `claude-cli`, `anthropic`, `openai`, `gemini` |
| `AUTH_TOKEN` | *(disabled)* | API bearer token |
| `MCP_AUTH_TOKEN` | *(disabled)* | MCP bearer token |
| `ENCRYPTION_KEY` | *(auto-generated)* | Fernet key for GitHub token encryption |

## Testing

Run all: `./init.sh test`

### Backend (pytest, async)

- **Fixtures** (`tests/conftest.py`): `db_engine` (in-memory SQLite), `db_session`, `client` (httpx AsyncClient with dep override)
- **File naming**: `tests/test_{module}.py`
- **Structure**: Group in classes (`class TestGetById`). `@pytest.mark.asyncio` on async methods.
- **Mocking LLM**: `FakeProvider(LLMProvider)` with canned responses. Patch `get_provider`.
- **DB tests**: `db_session` fixture + `_seed()` helpers for test data.
- **No external calls**: All offline — providers mocked, DB in-memory.

### Frontend (vitest, Svelte 5)

- **File naming**: Co-located `{module}.test.ts` next to source
- **Structure**: `describe`/`it` with `vi.mock()` and `vi.fn()`.
- **Store tests**: Import store, set state in `beforeEach`, assert reactive properties.
- **Component tests**: `@testing-library/svelte` (`render`, `screen`, `fireEvent`). `data-testid` for querying.
- **Browser APIs**: Stub `sessionStorage`/`localStorage` with in-memory objects.

## Linting

- **Ruff**: target py314, line-length 100, rules: E/F/I/W (`pyproject.toml`)
- **Pyright**: basic type checking, py314 (`pyproject.toml`)
- **svelte-check**: `npm run check` in frontend

## Frontend Theme

**Design Philosophy:** Strict "flat neon contour" directive. **ZERO glow effects, drop shadows, or text blooms.** Sharp 1px borders, vector color shifts, precise micro-interactions. Canonical values in `.claude/skills/brand-guidelines.md`.

**Neon palette (10 colors):** `neon-cyan` (#00e5ff), `neon-purple` (#a855f7), `neon-green` (#22ff88), `neon-red` (#ff3366), `neon-yellow` (#fbbf24), `neon-orange` (#ff8c00), `neon-blue` (#4d8eff), `neon-pink` (#ff6eb4), `neon-teal` (#00d4aa), `neon-indigo` (#7b61ff).

**Backgrounds:** `bg-primary` (#06060c), `bg-secondary` (#0c0c16), `bg-card` (#11111e), `bg-input` (#0a0a14), `bg-hover` (#16162a), `bg-glass` (rgba(12, 12, 22, 0.7)).

**Text hierarchy:** `text-primary` (#e4e4f0), `text-secondary` (#8b8ba8), `text-dim` (#7a7a9e).
