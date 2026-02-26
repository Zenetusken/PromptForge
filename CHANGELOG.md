# Changelog

All notable changes to PromptForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — GitHub OAuth Setup UI & Security Hardening

- **In-app OAuth configuration**: `GET/PUT/DELETE /api/github/config` endpoints for managing GitHub OAuth App credentials from within the Workspace Hub. Client secret stored Fernet-encrypted at rest; client ID returned as masked hint (`Iv1.****xxxx`) — secret never exposed in API responses.
- **Setup walkthrough UI**: When GitHub OAuth is not configured, the Workspace Hub GitHub tab shows a step-by-step setup form with direct links to GitHub Developer Settings and the "New OAuth App" creation page, input fields for Client ID / Secret, and a security note about Fernet encryption.
- **Three-state GitHub tab**: Not configured (setup form) → Configured but not connected ("Connect GitHub" button) → Connected (user card + repos list). Driven by `github_configured` flag in workspace health.
- **OAuth CSRF state validation** (security fix): `/api/github/callback` now validates the `state` parameter against a time-limited (10 min TTL), one-time-use in-memory store. Previously the state was generated but never verified.
- **Auth middleware callback exemption**: `/api/github/callback` added to `_EXEMPT_PREFIXES` — the OAuth redirect target cannot carry a Bearer token.
- **Sanitized exception logging**: Callback error logs now use `type(exc).__name__` instead of full exception details to prevent auth codes from appearing in logs.
- **Config resolution**: DB-stored OAuth config takes priority over env vars. All OAuth endpoints (authorize, callback, disconnect/revoke) resolve credentials via `resolve_github_config()`.
- **`github_configured` health flag**: Workspace health summary includes `github_configured: bool` so the frontend knows whether to show the setup form vs the connect button.
- **`GitHubOAuthConfig` model**: New single-row table for in-app credential management with encrypted secret storage.
- **`lock` icon**: Added lock icon to `Icon.svelte` for the security note in the setup form.
- **Backend tests**: 25 new tests — OAuth state validation (6), config repository CRUD (5), config endpoints (8), health `github_configured` (3), callback state validation (2), auth middleware exemption (1).

### Added — Workspace Hub: GitHub-Connected Dynamic Context Management

- **GitHub OAuth integration**: Connect GitHub account via OAuth flow, list repos, link repos to PromptForge projects for automatic codebase context extraction. Token stored encrypted at rest (Fernet). New env vars: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`, `ENCRYPTION_KEY`.
- **Three-layer context resolution**: Workspace auto-context (Layer 3, lowest priority) → manual `context_profile` (Layer 2) → per-request `codebase_context` (Layer 1, highest). Two chained `merge_contexts()` calls in `optimize.py`, `mcp_server.py` optimize/batch tools. Manual edits always preserved — workspace context only fills gaps.
- **Deterministic context extraction** (`workspace_sync.py`): No LLM calls. Parses `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile` for language/framework detection. Infers conventions from linter configs (`.eslintrc`, `ruff.toml`, `.prettierrc`), test frameworks from dev dependencies, and patterns from directory structure.
- **Data model**: `github_connections` table (encrypted tokens, user info, token validity), `workspace_links` table (project FK with UNIQUE constraint, repo metadata, sync status, workspace_context JSON, dependencies/file_tree snapshots, sync_source). `Project.workspace_synced_at` column.
- **Backend API** (`routers/github.py`): 9 new endpoints — `GET /api/github/authorize`, `GET /api/github/callback`, `GET /api/github/status`, `DELETE /api/github/disconnect`, `GET /api/github/repos`, `POST /api/workspace/link`, `DELETE /api/workspace/{id}`, `POST /api/workspace/{id}/sync`, `GET /api/workspace/status`.
- **Health endpoint**: `workspace` section with `github_connected`, `github_username`, `total_links`, `synced`, `stale`, `errors` counts. Staleness threshold: 24 hours.
- **MCP tool 20**: `sync_workspace` — allows Claude Code CLI to push workspace context (repo URL, file tree, dependencies, pre-analyzed context) for a project. Creates workspace link with `sync_source='claude-code'`.
- **MCP resource**: `promptforge://workspaces` — returns all workspace link statuses with staleness info.
- **Frontend Workspace Hub** (`WorkspaceWindow.svelte`): 3-tab persistent window (ID: `workspace-manager`). GitHub tab: connect/disconnect, searchable repo list, link to project. Workspaces tab: status table with sync/unlink, color-coded dots (green=synced, yellow=stale, red=error, gray=pending). Context Inspector tab: field-by-field source breakdown with completeness bar.
- **Workspace Manager store** (`workspaceManager.svelte.ts`): Reactive state for GitHub connection, repos, workspace links. Actions: `checkGitHubStatus()`, `connectGitHub()`, `disconnectGitHub()`, `loadRepos()`, `linkRepo()`, `unlinkWorkspace()`, `syncWorkspace()`.
- **OS integration**: Desktop icon (git-branch), Start Menu entry, `PERSISTENT_WINDOW_IDS` registration, bus events (`workspace:synced/error/connected/disconnected`), notification service subscriptions, MCP activity feed integration (`sync_workspace` in write tools).
- **OAuth callback route** (`/github/callback`): SvelteKit page handles `?status=connected` / `?error=...`, updates store, redirects to Workspace Hub.
- **ForgeContextSection**: Added `'workspace'` context source badge (green, "from workspace").
- **Icon additions**: `github` (octocat) and `link` icons added to `Icon.svelte` type system.
- **Backend tests**: 45 new tests — 15 for context extraction (React, Python/FastAPI, SvelteKit, empty, truncation), 30 for GitHub router (Fernet, repository CRUD, OAuth endpoints, workspace link CRUD, staleness detection, health).
- **Frontend tests**: `PERSISTENT_WINDOW_IDS` count 11→12, desktop icon count 15→16 (10 system + 2 folder + 4 file), 2 new notification tests (`workspace:synced`, `workspace:error`).

### Fixed — Notification System Audit

- **Critical: `forge:completed` "Open in IDE" dead action** — notification handler read `event.payload.openInIDE` (always undefined) instead of constructing the callback from `optimizationId`; now self-contained via lazy `import()` just like MCP notifications
- **Critical: `MCP_WRITE_TOOLS` incomplete** — `delete`, `bulk_delete`, `tag`, `add_prompt`, `update_prompt`, `set_project_context` were missing; MCP deletions did not trigger history reload, leaving stale data in the UI
- **Moderate: `forge:cancelled` unhandled** — cancelling a forge produced no notification tray entry; now emits info notification with process title
- **Moderate: `tournament:completed` unhandled** — tournament results (long-running multi-strategy forges) were only shown via a 4s auto-dismiss toast; now persisted in notification tray with best score, top strategy, and "Open in IDE" action
- **Moderate: `mcp:session_disconnect` unhandled** — asymmetric with `session_connect`; now emits persistent error notification on MCP disconnect
- NotificationService `subscribeToBus()` now registers 10 event handlers (was 7): added `forge:cancelled`, `tournament:completed`, `mcp:session_disconnect`
- Added 7 new test cases to `notificationService.test.ts` covering all new handlers, MCP delete/bulk_delete notifications, and read-only tool filtering

### Fixed — MCP Server Toast Deduplication (E3)

- **Provider store MCP notifications routed through bus** — replaced direct `toastState.show()` calls for MCP server connect/disconnect with `systemBus.emit('mcp:session_connect'/'mcp:session_disconnect')`, unifying notification flow through the NotificationService (persistent tray entries, read/unread tracking, consistent UX)
- **`mcp:session_connect` handler** — upgraded from `info` to `success` type, title changed from "MCP client connected" to "MCP connected" (accurate for server health-poll detection)
- **`mcp:session_disconnect` handler** — upgraded from `info` to `error` type with `persistent: true`, title changed from "MCP client disconnected" to "MCP disconnected" (matches the severity of the old error toast)
- Reactivated previously dead-code NotificationService handlers for `mcp:session_connect`/`mcp:session_disconnect`
- Updated provider store tests to assert bus events instead of toast calls; added 2 new notification tests for connect/disconnect

### Added — Last-Event-ID SSE Reconnection (E4)

- Backend: `MCPActivityBroadcaster.get_history_after(event_id)` — returns events after a known ID for gap-fill on reconnect; falls back to `recent_history` if ID aged out of the 100-event buffer
- Backend: SSE `id:` field on all `mcp_activity` events — enables browser-native and custom SSE clients to track stream position
- Backend: `Last-Event-ID` header support on `GET /api/mcp/events` — on reconnect, replays only events since the last received ID instead of a full 20-event snapshot
- Frontend: `MCPActivityFeed._lastEventId` tracking — set from parsed event data, sent as `Last-Event-ID` header on reconnect, cleared on reset
- Backend: Added `tests/test_mcp_activity.py` with tests for broadcaster, `get_history_after()`, and SSE generator

### Added — MCP Live Bridge

- Backend: **MCP Activity Broadcaster** (`backend/app/services/mcp_activity.py`) — in-memory event fan-out for real-time MCP tool call tracking with bounded history (100 events), subscriber queue management (max 256 per client), and active call state
- Backend: **MCP Activity Router** (`backend/app/routers/mcp_activity.py`) — `POST /internal/mcp-event` webhook (auth-exempt), `GET /api/mcp/events` SSE stream (snapshot + live events), `GET /api/mcp/status` REST polling fallback
- Backend: **MCP Tracking Decorator** (`_mcp_tracked`) on all 19 MCP tools — emits `tool_start`/`tool_complete`/`tool_error` events via fire-and-forget webhook to backend; includes duration_ms and result_summary extraction
- Backend: **MCP Resources** — 3 read-only resources: `promptforge://projects`, `promptforge://projects/{id}/context`, `promptforge://optimizations/{id}` for bi-directional context flow with Claude Code
- Frontend: **MCPActivityFeed** (`$lib/services/mcpActivityFeed.svelte.ts`) — SSE client with auto-reconnect (exponential backoff), reactive state for events/activeCalls/sessionCount, SystemBus emission (`mcp:*` events)
- Frontend: **NetworkMonitorWindow** — 3-tab activity monitor (Live Activity with progress bars, Event Log table, Connections status) following OS metaphor
- Frontend: **SystemBus** — 6 new event types: `mcp:tool_start`, `mcp:tool_progress`, `mcp:tool_complete`, `mcp:tool_error`, `mcp:session_connect`, `mcp:session_disconnect`
- Frontend: **Taskbar** network activity indicator (animated when active, click opens Network Monitor)
- Frontend: **TaskManager** External (MCP) section showing active tool calls from external clients
- Frontend: **Terminal** 3 new commands: `mcp` (status), `mcp-log [n]` (recent events), `netmon` (open Network Monitor)
- Frontend: **Notifications** for MCP write-tool completions (optimize/retry/batch/create_project/cancel) with "Open in IDE" actions; error and session_connect notifications
- Frontend: **History auto-reload** on external MCP write-tool completion (debounced 1s)
- Frontend: **Desktop icon** for Network Monitor, command palette entry, persistent window ID

### Fixed — MCP Live Bridge Review Pass

- Backend: **Tool progress events** — `optimize` (3 checkpoints) and `batch` (per-prompt progress) tools now emit `tool_progress` events via `_emit_tool_progress()` helper using `contextvars.ContextVar` to propagate decorator-generated `call_id` into tool handlers
- Backend: **Config-based webhook port** — removed hardcoded `_BACKEND_PORT = 8000` in MCP server; `_emit_mcp_event()` now reads `config.PORT` dynamically
- Backend: **Rate limiter `/internal/` exemption** — internal webhook traffic (e.g., batch of 20 prompts = 60+ POSTs) now bypasses per-IP rate limiting to prevent self-throttling
- Frontend: **MCPStatus `startedAt` conversion** — backend sends ISO `timestamp` strings in active_calls; frontend now converts to epoch ms via `MCPStatusRaw` interface and `new Date().getTime()`
- Frontend: **Network Monitor elapsed time** — `formatElapsed()` now accepts reactive `_tick` parameter so Svelte re-renders on each `$effect` interval (previously displayed stale time)
- Frontend: **DRY `MCP_WRITE_TOOLS`** — extracted shared constant from `mcpActivityFeed.svelte.ts`, imported in `notificationService` and `+layout.svelte` (was duplicated inline)
- Backend: **Nested `_mcp_tracked` guard** — when a tracked tool calls another tracked tool (e.g. `retry` → `optimize`), the inner decorator is skipped so only the outer tool appears in the activity feed. Prevents duplicate events in Network Monitor.
- Backend: **`MCPEventType` enum enforcement** — `_emit_mcp_event()` and `_mcp_tracked` decorator now use `MCPEventType` enum values instead of raw strings, eliminating typo risk and ensuring consistency with the broadcaster
- Frontend: **DRY `MCP_TOOL_COLORS`** — extracted canonical tool→Tailwind-color mapping from `NetworkMonitorWindow` into `mcpActivityFeed.svelte.ts`; NetworkMonitorWindow now imports shared constant

### Added — Cognitive OS Architecture (Phases 1-3)

**Phase 1: System Libraries**
- Backend: **Token Budget Manager** (`backend/app/services/token_budget.py`) — per-provider token tracking with configurable daily limits, auto-reset, and health endpoint integration
- Frontend: **System Bus** (`$lib/services/systemBus.svelte.ts`) — decoupled IPC with typed events (`forge:*`, `window:*`, `clipboard:copied`, `provider:*`, `history/stats:reload`, `notification:show`), wildcard handlers, recent event log
- Frontend: **Notification Service** (`$lib/services/notificationService.svelte.ts`) — system notifications with info/success/warning/error types, auto-dismiss, read/unread tracking, action callbacks
- Frontend: **Clipboard Service** (`$lib/services/clipboardService.svelte.ts`) — copy with 10-entry history, bus integration, fallback textarea method for non-secure contexts
- Frontend: **Command Palette** (`$lib/services/commandPalette.svelte.ts`) — fuzzy-matched command registry with `Ctrl+K` activation, categories, recent commands

**Phase 2: Process Management**
- Frontend: **Process Scheduler** (`processScheduler.svelte.ts`) — bounded-concurrency queue for forge operations, configurable `maxConcurrent` (default 2), running/queued tracking
- Frontend: **Settings Store** (`settings.svelte.ts`) — persisted user preferences (accent color, default strategy, max concurrent forges, animations toggle, auto-retry), localStorage persistence with schema migration

**Phase 3: Window Components**
- Frontend: **ControlPanelWindow** — system settings with 4 tabs: Providers, Pipeline, Display (accent color grid), System (backend info + reset)
- Frontend: **TaskManagerWindow** — process monitor showing running/queued/completed forge processes
- Frontend: **BatchProcessorWindow** — multi-prompt batch optimization (up to 20), progress tracking, JSON export
- Frontend: **StrategyWorkshopWindow** — analytics with Score Heatmap (strategy × task type), Win Rates, Combo Analysis views
- Frontend: **TemplateLibraryWindow** — 10 built-in prompt templates across 6 categories with search/filter, double-click to forge
- Frontend: **TerminalWindow** — system bus event log for debugging
- Frontend: **RecycleBinWindow** — soft-deleted/cancelled optimization viewer
- Frontend: **CommandPaletteUI** — floating command palette overlay
- Frontend: **NotificationTray** — taskbar dropdown with unread count badge
- Backend: **Batch optimization endpoint** (`POST /api/optimize/batch`) — sequential pipeline runs for 1-20 prompts
- Backend: **Cancel optimization endpoint** (`POST /api/optimize/{id}/cancel`) — sets running optimization to CANCELLED status
- Backend: **MCP `batch` tool** — optimize multiple prompts via MCP (1-20, sequential)
- Backend: **MCP `cancel` tool** — cancel running optimization via MCP
- Frontend: 10 new icons added to `Icon.svelte`: `cpu`, `git-branch`, `monitor`, `settings`, `mail`, `users`, `x-circle`, `bar-chart`, `check-square`, `activity`

### Changed — Code Quality & Architecture
- Backend: **Stats cache extracted** to `backend/app/services/stats_cache.py` — eliminates circular cross-module dependency (MCP server → routers). All modules now import `invalidate_stats_cache` and `get_stats_cached` from the service layer.
- Backend: **MCP batch tool context snapshot** — `promptforge_batch` now resolves project codebase context and snapshots it on optimization records (consistency with the `optimize` tool)
- Backend: **Version schema validation** — empty/whitespace-only version strings now normalize to `None` instead of passing through as invalid empty strings
- Frontend: **Process lifecycle consolidated** — removed deprecated `forgeMachine.spawnProcess/completeProcess/failProcess/dismissProcess` bridge methods and `ProcessStatus`/`ForgeProcess` types. All callers now use `processScheduler` directly as the single source of truth.
- Frontend: **Component imports updated** — `ForgeIDEInspector` and `ForgeReview` now import and use `processScheduler.spawn()` directly instead of the removed `forgeMachine.spawnProcess()`

### Fixed — Audit Fixes
- Backend: **Batch endpoint `event.data` bug** — `event.result` → `event.data` (AttributeError), dict bracket access for `overall_score`, correct kwargs for `update_optimization_status()`
- Backend: **Token budget recording** — `token_budget.record_usage()` now called at pipeline completion in both `run_pipeline()` and `run_pipeline_streaming()`
- Backend: **`stages` parameter wired** — `request.stages` now passed through router to pipeline; analyze-only mode (`stages=["analyze"]`) returns early with partial result
- Frontend: **DRY strategy lists** — `ControlPanelWindow` and `BatchProcessorWindow` now import `ALL_STRATEGIES` from `$lib/utils/strategies` instead of hardcoding
- Frontend: **Clipboard service integration** — `TemplateLibraryWindow` now uses `clipboardService.copy()` instead of raw `navigator.clipboard.writeText()`
- Frontend: **StrategyWorkshopWindow types** — fixed `best_strategy` → `strategy` for win rates data, fixed combo entries to use `avg_score` field
- Frontend: **Window bus events** — `windowManager` now emits `window:opened` and `window:closed` events on the system bus
- Frontend: **StrategyWorkshopWindow heatmap** — fixed `entry.avg` → `entry.avg_score` to match backend `score_matrix` shape; heatmap cells now display actual scores instead of dashes
- Backend: **Batch endpoint robustness** — rewrote to use `run_pipeline()` (non-streaming) instead of `run_pipeline_streaming()`, added `model_fallback` computation, f-string logger fix
- Backend: **MCP batch error handling** — added try/except around `update_optimization_status` in error path to match HTTP endpoint pattern, truncate error to 500 chars

### Fixed
- Frontend: **Per-tab state coherence** — `WorkspaceTab` now carries `resultId` and `mode` fields, so closing a tab, switching tabs, or creating new tabs correctly saves/restores the inspector panel state. Previously, `forgeResult` and `forgeMachine.mode` were global singletons with no tab awareness, causing stale results to persist in the inspector after tab operations.
- Frontend: **Forging guards** — tab switching, active-tab close, and new-tab creation are blocked while a forge is in progress (both click and keyboard shortcuts `Ctrl+W`/`Ctrl+N`)
- Frontend: **Ctrl+W close stale result** — keyboard shortcut now clears `forgeResult` and resets `forgeMachine.mode` when closing the last tab
- Frontend: **Hydration recovery** — on page reload, `ForgeIDEWorkspace.onMount` restores results from the server or falls back to compose mode; hydration resets `'forging'` mode to `'compose'` and defaults missing `resultId`/`mode` fields

### Added
- Frontend: **`tabCoherence.ts`** coordination module — `saveActiveTabState()` and `restoreTabState(tab)` centralize save/restore logic across `forgeSession`, `optimizationState`, and `forgeMachine` stores
- Frontend: **`restoreResult(id)`** method on `OptimizationState` — loads a result by ID from `resultHistory` cache or server without side effects (no `enterReview`, no `openIDE`)
- Frontend: **Tab sync `$effect`** in layout — binds `forgeResult` to the active tab on forge completion and on non-pipeline result loads (e.g. `openInIDEFromHistory`)

### Removed
- Frontend: **Route-based detail pages** — removed `/projects/[id]` and `/optimize/[id]` SvelteKit routes. All project and forge interactions now happen through the persistent window system (ProjectsWindow, HistoryWindow, IDE). No backend changes.

### Added
- Frontend: **`openPromptInIDE()` utility** (`$lib/utils/promptOpener.ts`) — opens a project prompt in the IDE; branches on forge_count: latest forge → IDE review mode with reiterate context; no forges → compose mode with prompt text
- Frontend: **`navigateToProject(id)`** on `ProjectsState` — lets external code (StartMenu, ResultActions) request the ProjectsWindow to drill into a specific project via `pendingNavigateProjectId`
- Frontend: **Nautilus-style file manager navigation** — Projects and History windows now use shared `FileManagerView`/`FileManagerRow` components with sortable column headers. ProjectsWindow supports drill-down navigation (list → project prompts) with back/forward history stacks. `WindowNavigation` interface in `windowManager.svelte.ts` enables per-window back/forward buttons in `DesktopWindow` address bar. Windows manage their own breadcrumbs.
- Frontend: **Window Manager** store (`windowManager.svelte.ts`) — IDE renders as route-independent overlay on any page, controlled by `openIDE()`, `closeIDE()`, `focusDashboard()`
- Frontend: **Scoped optimization results** — `forgeResult` (from SSE pipeline) and `viewResult` (from history) are separate slots; navigating to detail pages no longer clobbers an active forge
- Frontend: **Forge process tracking** — `ForgeProcess[]` in `forgeMachine` tracks running/completed/error forges (max 5, LRU eviction), persisted to sessionStorage
- Frontend: **Taskbar** component (`ForgeTaskbar.svelte`) — horizontal process strip shown on dashboard when IDE is hidden, click to resume/view processes
- Frontend: **IDE-aware cards** — sidebar history entries, dashboard recent forges, and project detail forge cards detect IDE visibility; when IDE is open, primary click loads result directly into the IDE (no page navigation), and the redundant "Open in IDE" overlay button is hidden. When IDE is closed, cards navigate to `/optimize/[id]` as before with the "Open in IDE" button available.
- Frontend: **"Open in IDE" on detail page** — `ResultActions.svelte` now includes an "Open in IDE" button (shown only when IDE is not visible) providing a pathway from the forge detail page into the IDE
- Frontend: **Running Forges** section in sidebar — live pulse indicators for active forge processes, clickable to restore IDE
- Frontend: **Tab bounds** — `MAX_TABS = 5` with LRU eviction of non-active tabs when at capacity
- Frontend: **Compare robustness** — async server fallback in `ForgeCompare` fetches missing slot data from API when `resultHistory` is empty (e.g., after page reload)
- Frontend: **Session desync guard** — `$effect` in layout resets forge machine when both `forgeSession.isActive` and `windowManager.ideSpawned` are false while machine is in non-compose mode
- Frontend: `openInIDE(result)` and `openInIDEFromHistory(id)` methods on `OptimizationState` — DRY entry points for loading results into IDE review mode
- Frontend: `enterReview()` and `enterForging()` methods on `forgeMachine` — teleport transitions with proper sessionStorage persistence (replaces direct `mode =` mutations)
- Frontend: `resetForge()` method on `OptimizationState` — clears forge-side state while preserving `viewResult`
- Frontend: `Ctrl/Cmd+N` keyboard shortcut — creates new forge tab and opens IDE
- Frontend: `Ctrl/Cmd+W` keyboard shortcut — closes current tab or exits IDE when on last tab
- Frontend: `fly` transition for IDE open/close (window feel) replacing `fade`
- Frontend: `forgeMachine` state persistence — mode, isMinimized, activeProcessId, processes persisted to sessionStorage

### Performance
- Frontend: IDE spawn/minimize transitions — fade in/out (150ms/100ms) via absolute-positioned overlay, minimized bar slides with `transition:slide`
- Frontend: View Transitions API for page navigation crossfade between routes (graceful fallback on unsupported browsers)
- Frontend: `section-expand` animation replaced `max-height` keyframe with CSS `grid-template-rows: 0fr→1fr` (no layout thrashing, no arbitrary height cap)
- Frontend: `shimmer-placeholder` promoted to own compositor layer (`will-change: background-position`, `contain: paint`)
- Frontend: `status-degraded-pulse` converted from `background-color` animation to GPU-composited `opacity` on `::after` pseudo-element
- Frontend: Removed dead `gradient-flow` keyframe (defined but never referenced)
- Frontend: Replaced all 32 `transition-all` instances across 15 components with specific property transitions (`transition-colors`, `transition-[width]`, `transition-transform`)
- Frontend: CSS class definitions (`card-hover-bleed`, `prompt-card`, `iteration-timeline-item`, `ctx-template-chip`, `forge-action-btn`, `btn-primary`) replaced `transition: all` with explicit properties
- Frontend: `content-visibility: auto` containment on `HistoryEntry` and `ProjectItem` sidebar cards for off-screen rendering skip
- Frontend: BrandLogo `IntersectionObserver` pauses/resumes 17+ infinite SVG animations when scrolled off-screen
- Frontend: Vite `manualChunks` splits `bits-ui` into dedicated vendor chunk for better cache efficiency
- Backend: `ensure_project_by_name()` returns `ProjectInfo(id, status)` dataclass, eliminating redundant `_is_project_archived()` DB round-trip on every optimize/retry
- Backend: Summary serialization now only deserializes 2 JSON fields instead of 6, saving ~120 `json.loads()` calls per 20-item list view
- Backend: Archive filter query uses `NOT EXISTS` correlated subqueries instead of `NOT IN` with materialized UNION
- Backend: SQLite `busy_timeout = 5000` prevents `SQLITE_BUSY` errors under concurrent SSE writes; `mmap_size` raised to 256 MB
- Backend: Read-only `get_db_readonly()` session dependency for GET/HEAD endpoints — skips unnecessary `commit()` flush
- Backend: Rate limiter stale IP prune interval reduced from 300s to 60s
- Backend: Stats cache TTL increased from 30s to 120s (cache is already invalidated on mutations)
- Backend: MCP stats score conversion uses recursive `_convert_scores_recursive()` utility instead of nested manual loops
- Backend: Legacy migration batches prompt inserts per project instead of one-at-a-time
- Frontend: Skeleton shimmer animation uses GPU-composited `transform: translateX()` via pseudo-element instead of `background-position` (120 FPS safe)
- Frontend: `RecentForges` list keyed by `item.id` to prevent DOM reuse glitches on reorder
- Frontend: Stats and history load in parallel on mount instead of sequentially gated
- Frontend: `promptAnalysis.destroy()` method cleans up debounce timer on workspace teardown
- Frontend: Visibility restore polling adds 0-2s random jitter to prevent thundering herd across tabs

### Added
- IDE minimize/restore — `forgeMachine.minimize()`/`restore()` with `isMinimized` transient state and `showMinimizedBar` derived
- `ForgeMinimizedBar` component — slim real-time status bar with three mode renders (forging: step dots + timer + cancel, review: score + strategy, compare: label), persists across routes, expand navigates to home when on other pages
- Minimize buttons in `ForgeIDEInspector` (forging), `ForgeReview` (review), `ForgeCompare` (compare) headers
- Keyboard shortcuts: `Ctrl/Cmd+M` toggle minimize, `Escape` restores when minimized, `/` restores and focuses textarea
- `formatElapsed()` shared utility in `$lib/utils/format` (extracted from duplicated implementations)
- Dashboard state guard — `+page.svelte` skips clearing optimization state when forge is minimized or in active mode
- Detail page guard — `/optimize/[id]` uses local result mapping when forge is minimized to avoid clobbering shared store
- Prompt caching on `AnthropicAPIProvider` — `cache_control={"type": "ephemeral"}` on all API calls for up to 90% cost savings on repeated system prompts
- Cache token tracking — `cache_creation_input_tokens` and `cache_read_input_tokens` fields in `TokenUsage`, `PipelineResult`, DB `Optimization` model, API schemas, and frontend display (cache savings indicator in result metadata tooltip)
- SDK-typed error classification — `_classify_anthropic_error()` uses the Anthropic SDK's exception hierarchy (`AuthenticationError`, `RateLimitError`, etc.) with `retry-after` header extraction, replacing string-based pattern matching for the Anthropic provider
- Async `count_tokens()` — `LLMProvider.count_tokens()` is now an `async` method; `AnthropicAPIProvider` calls the SDK's `messages.count_tokens()` endpoint with heuristic fallback
- `prompt_caching` capability flag in Claude model catalog
- MCP health monitoring — backend probes MCP server via `/health` endpoint, surfaces `mcp_connected` in health response, frontend shows MCP status in footer tooltip and fires toast notifications on status transitions
- MCP server `/health` endpoint — zero-state liveness probe on the MCP ASGI app (Starlette wrapper around SSE)
- `MCP_PORT` config variable (`backend/app/config.py`) — mirrors `init.sh` default of 8001
- `httpx` promoted to runtime dependency for async MCP connectivity probe
- Project-scoped stats via `GET /api/history/stats?project=...` query parameter
- Stateful header stats — shows project-scoped stats on `/projects/[id]` and `/optimize/[id]` routes, global stats elsewhere
- `statsState.setContext()` / `clearProjectContext()` / `activeStats` getter for route-aware stat switching
- `RecentForges` dashboard section — last 6 optimizations as compact navigational cards (score, task type, strategy, relative time) with "View all →" sidebar bridge
- `RecentProjects` dashboard section — up to 4 recent projects as compact navigational cards (prompt count, context indicator, description) with "View all →" sidebar bridge
- Sidebar open state in `sidebar.svelte.ts` — `isOpen`/`open()`/`close()`/`toggle()`/`openTo(tab)` with localStorage persistence
- Global stats store (`stats.svelte.ts`) — persistent stats across all routes, initialized in layout
- `HeaderStats` component — compact stats bar in the header replacing the logo (FORGED, AVG, IMP, PROJ, TODAY + dimension bars + top task)
- `OnboardingHero` component — interactive 3-step workflow guide (Write → Forge → Iterate) replacing ForgeHero, dismissible, shown for < 5 forges
- ForgePanel brand upgrade — gradient bolt logo, gradient "FORGE" text, shimmer placeholder, "/" kbd hint, entrance animation on expand
- Per-task-type color system (`taskTypes.ts`) — 14 unique neon colors for task type badges across all components
- Per-complexity color system (`complexity.ts`) — green/yellow/red with alias normalization (simple/moderate/complex)
- Premium filter bar with glass treatment, accent-tinted `.filter-row` rows, and `.filter-label` typography
- `.collapsible-toggle-section` CSS modifier for standalone collapsible sections
- `identityColor` prop on `MetadataSummaryLine` for per-type identity coloring via CSS variable
- Project context profiles — persistent codebase context on projects, auto-resolved during optimization, snapshotted on each optimization record for reproducibility
- `set_project_context` MCP tool — set or clear codebase context profile on a project
- Stack templates — 8 pre-built context profiles for common stacks (SvelteKit, FastAPI, Next.js, Django, Express, Rails, Spring Boot, Go)
- `ContextProfileEditor` component on project detail page with template picker, dirty detection, and save/clear
- Context auto-population in PromptInput when a project with a context profile is selected
- "Context Used" collapsible section on optimization detail page showing resolved context snapshot
- Bulk-delete endpoint (`POST /api/history/bulk-delete`) — delete 1–100 records in a single call
- `bulk_delete` MCP tool

### Removed
- `ForgeHero.svelte` — replaced by `OnboardingHero` (workflow guide) and `HeaderStats` (persistent stats bar)
- Header bolt icon — removed home link icon; HeaderStats fills full header width; breadcrumbs handle "get home" on detail pages
- "Back to Home" button + `navigation.svelte.ts` store — redundant with breadcrumbs; breadcrumbs are the single navigation mechanism on detail pages

### Changed
- IDE compaction — VS Code + Excel density overhaul across all 3 panes (Explorer `w-56`, Editor tab bar `h-7`, Inspector `w-72`), global CSS utilities, pipeline/analysis/review/editor components; strict 2–8px spacing scale (`p-0.5`–`p-2` max), removed `shadow-inner`/`shadow-xl` for flat neon contour compliance, `leading-relaxed` → `leading-snug` on all display text, extracted `.section-toggle-btn` CSS utility for DRY collapsible buttons
- `HeaderStats` — redesigned as wing formation layout with center-stage task type chip and animated glow (`header-contour-pulse` keyframes), context-aware project label
- `total_projects` stat — now counts only active projects from the projects table instead of distinct project names from optimizations
- Homepage — transformed from forge-only into content dashboard (RecentForges + RecentProjects above StrategyInsights for returning users)
- Sidebar open state — lifted from local `$state` in layout to `sidebarState` store with localStorage persistence
- Breadcrumbs — redesigned with cyberpunk brand treatment: glass pill container, monospace typography, `/` separators, neon-cyan hover glow with drop-shadow, truncated current segment
- CLAUDE.md — extracted frontend stores/components/utilities/routes catalog to `docs/frontend-internals.md`; CLAUDE.md now links to it instead of inlining ~30 lines of detail

### Fixed
- Frontend: `ResultActions.handleReforge()` missing `forgeMachine.spawnProcess()` and `forgeMachine.forge()` — re-forging from detail page had no process tracking and no mode transition to forging state
- Frontend: `ResultActions.handleEditReforge()` dropped title, tags, version, and sourceAction metadata — iterating from detail page lost all metadata context
- Frontend: `ForgeTaskbar` completed process click silently failed when `resultHistory` cache missed — added `openInIDEFromHistory()` async server fallback
- Frontend: "Open in IDE" wrote to `viewResult` but `ForgeReview` read `forgeResult` — result never displayed; now uses `openInIDE()` which sets `forgeResult` directly
- Frontend: Desync guard immediately reset `forgeMachine` when "Open in IDE" set mode to review (because `forgeSession.isActive` was false) — guard now also checks `windowManager.ideSpawned`
- Frontend: Direct `forgeMachine.mode =` mutations (in re-forge, Open in IDE, taskbar) skipped `_persistMachine()` — replaced with `enterReview()`/`enterForging()` methods that persist correctly
- Frontend: `ForgeCompare` showed stale slot data briefly when comparison changed — now clears `fetchedSlotA/B` on comparison change and adds `.catch()` for error handling
- `most_common_task_type` ignored project filter — subquery used `.correlate(None)` without project/completed filters, always returning the global most common task type even when stats were scoped to a project
- `total_projects` included archived projects in count — now queries `projects` table with `status = 'active'`
- CLAUDE.md palette documentation — corrected 5 hex values to match `app.css` and brand guidelines (`bg-primary` #0a0a0f→#06060c, `neon-cyan` #00f0ff→#00e5ff, `neon-purple` #b000ff→#a855f7, `neon-green` #00ff88→#22ff88, `neon-red` #ff0055→#ff3366) and expanded from 5 to 19 palette tokens
- Rate limiter memory leak — replaced `defaultdict(list)` with `defaultdict(deque)` for O(1) cleanup, added periodic stale IP pruning every 5 minutes

### Performance
- SQLite WAL mode + PRAGMAs — `journal_mode=WAL` eliminates reader/writer blocking during SSE streaming, `synchronous=NORMAL`, 64MB cache, 30MB mmap, temp_store=MEMORY
- GZip compression — `GZipMiddleware(minimum_size=1000)` for 60-80% size reduction on JSON responses; small SSE chunks pass through uncompressed
- Shared stats cache — MCP `stats` tool reuses the HTTP router's TTL cache; all mutation paths (optimize, delete, bulk_delete, tag, create/archive/unarchive/delete project, delete prompt) invalidate the cache consistently across both HTTP routers and MCP tools
- Fuzzy prompt match optimization — SQL-side whitespace normalization before Python fallback loop, LIMIT(100) safety cap on fallback query
- Debounced post-forge reloads — `loadHistory()` + `loadProjects()` delayed 500ms to coalesce with server commit
- Tab visibility polling — provider health/providers polling pauses when tab is hidden, immediate poll on tab restore
- PipelineNarrative consolidation — 8 separate `$derived` values collapsed into single `$derived.by()` returning one object
- ScoreDecomposition animation — `$effect` replaced with `onMount` (animation is lifecycle, not reactive)
- Vite build target `es2022` for modern output

## [0.2.0] - 2026-02-18

### Added
- ARCHITECTURE.md — comprehensive architecture document
- MIT LICENSE, CONTRIBUTING.md, CHANGELOG.md
- Authentication middleware (Bearer token via `AUTH_TOKEN` env var)
- Security headers middleware (CSP, X-Frame-Options, etc.)
- Rate limiting middleware (per-IP sliding window, configurable RPM)
- CSRF protection middleware (Origin-based validation)
- Audit logging middleware (state-changing request logging)
- Prompt injection detection (warn-only sanitization)
- Streaming interface on LLMProvider (`stream()` method)
- Token counting abstraction (`count_tokens()` method)
- Backend Dockerfile (multi-stage, non-root)
- Frontend Dockerfile (multi-stage, adapter-node)
- `.dockerignore` for clean build contexts
- GitHub Actions CI pipeline (backend + frontend + docker)
- Confirmation header required for bulk history delete

### Changed
- CORS tightened: explicit methods and headers lists (was `["*"]`)
- docker-compose.yml rewritten with healthchecks, restart policies, named volumes
- Frontend switched to `@sveltejs/adapter-node` for Docker deployment
- Frontend API client injects `Authorization` header when `AUTH_TOKEN` configured

## [0.1.0] - 2025-12-01

### Added
- Initial release
- 4-stage prompt optimization pipeline (Analyze, Strategy, Optimize, Validate)
- Provider abstraction with Claude CLI, Anthropic API, OpenAI, Gemini
- SSE streaming for real-time pipeline updates
- SQLite database with async SQLAlchemy
- SvelteKit 2 frontend with Svelte 5 runes
- Project and prompt management
- History with search, filter, and pagination
- MCP server for Claude Code integration
