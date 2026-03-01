# Changelog

All notable changes to PromptForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

**Comprehensive Audit Logging**
- `kernel_audit_log()` helper (`kernel/bus/helpers.py`) — app-agnostic fire-and-forget audit logging shared across all apps
- PromptForge `audit_log()` simplified to thin wrapper delegating to kernel helper
- Audit logging on all 24 PromptForge REST mutation endpoints and all 12 MCP write tools (delete, bulk_delete, tag, create_project, add_prompt, update_prompt, set_project_context, batch, cancel, sync_workspace, move)
- TextForge `delete_transform` endpoint now audited; inline audit replaced with `kernel_audit_log()` call
- `AuditLogWindow` improvements: dynamic app filter via `fetchApps()`, expandable detail rows, resource ID tooltip, 20 action color mappings (added `batch_optimize`, `sync_workspace`), live connection indicator
- Backend test suite for `audit_log()` and `kernel_audit_log()` (`test_audit_logging_coverage.py`)
- Frontend test suite for `AuditLogWindow` component (`AuditLogWindow.test.ts`)

**Kernel Infrastructure Hardening**
- VFS move/rename: `POST /vfs/{app_id}/folders/{id}/move`, `PATCH .../rename`, `POST /vfs/{app_id}/files/{id}/move`, `PATCH .../rename` with circular-reference and depth-limit validation
- VFS version restore: `POST /vfs/{app_id}/files/{id}/versions/{version_id}/restore` — snapshots current content before overwriting
- Frontend VFS client: `moveFolder()`, `renameFolder()`, `moveFile()`, `renameFile()`, `restoreVersion()`
- App lifecycle API: `POST /api/kernel/apps/{id}/enable`, `POST .../disable`, `GET .../status` — invokes `on_enable`/`on_disable`/`on_shutdown`/`on_startup` hooks in correct order, persists state across restarts
- `on_disable` lifecycle hook added to `AppBase` (no-op default)
- Event payload schemas: `apps/promptforge/events.py` (4 contracts), `apps/textforge/events.py` (1 contract)
- `publish_event()` helper (`kernel/bus/helpers.py`) — resolves EventBus from kernel, graceful no-op on failure
- EventBus contract validation: `publish()` validates payloads against registered `ContractRegistry`, blocks invalid payloads
- PromptForge publishes `optimization.started` and `optimization.completed` events; TextForge publishes `transform.completed`
- TextForge subscribes to `promptforge:optimization.completed` (cross-app handler)
- Capabilities and resource quotas in all app manifests (`promptforge`, `textforge`, `hello_world`)
- Settings schema validation: PUT `/api/kernel/settings/{app_id}` rejects unknown keys (422) and type mismatches when manifest declares a schema
- Quota enforcement (`check_quota`) in all VFS, Storage, and Settings mutation endpoints
- Permissive fallback warning: unknown `app_id` in `get_app_context()` logs warning before granting permissive capabilities
- Disabled apps raise 503 on all kernel service endpoints (VFS, Storage, Settings)
- `AppRegistry.persist_app_states()` / `restore_app_states()` — disabled apps remembered and restored on boot

**Kernel VFS (Virtual Filesystem)**
- `vfs_folders`, `vfs_files`, `vfs_file_versions` kernel tables with per-app scoping and auto-versioning
- `VfsRepository` — folder CRUD with depth validation (max 8), file CRUD with auto-version snapshots, breadcrumb path, search
- REST API at `/api/kernel/vfs/{app_id}/*` — children, folders, files, versions, search
- Frontend `VfsClient` (`kernel/services/vfs.ts`) — full VFS operations for any app
- `vfs` service registered in kernel ServiceRegistry

**Access Control**
- `CapabilitiesDef` and `ResourceQuota` added to `AppManifest` — apps declare required/optional capabilities and resource quotas
- `AppContext` dataclass — request-scoped context built from manifest with capability list and quota limits
- `check_capability()` — raises 403 if app lacks a required capability
- `check_quota()` — raises 429 if app exceeds hourly usage limit, with `AuditRepository` usage tracking
- `audit_log` and `app_usage` kernel tables for audit logging and quota tracking
- `AuditRepository` — `log_action`, `list_logs`, `count_logs`, `increment_usage`, `get_usage`, `get_all_usage`
- REST API at `/api/kernel/audit/{app_id}` and `/api/kernel/audit/usage/{app_id}`

**App-to-App RPC (Event Bus)**
- `EventBus` — async pub/sub with `subscribe`, `unsubscribe`, `publish` (fire-and-forget), `request` (with timeout)
- `ContractRegistry` — typed event schemas via Pydantic models, `register`, `validate_publish`, `to_json`
- `EventContract` frozen dataclass — `event_type`, `source_app`, `payload_schema`, optional `response_schema`
- `AppBase` extended with `get_event_contracts()` and `get_event_handlers()` lifecycle hooks
- Kernel auto-wires contracts and handlers from all apps during startup
- REST API at `/api/kernel/bus/*` — `GET /contracts`, `GET /subscriptions`, `GET /events` (SSE stream)
- `bus` and `contracts` services registered in kernel ServiceRegistry

**Backend-to-Frontend Bus Bridge**
- `EventReplayBuffer` in `bus.py` — ring buffer (max 200) with sequential IDs for SSE replay on reconnect
- `POST /api/kernel/bus/publish` — validated event publishing (checks ContractRegistry), returns 202
- `GET /api/kernel/bus/events` SSE stream now includes `id:` field, supports `Last-Event-ID` header for replay after disconnect
- Frontend `kernelBusBridge.svelte.ts` — SSE client with exponential backoff + jitter (3s→30s), `Last-Event-ID` replay, 2-second snapshot phase suppression, `EVENT_TYPE_MAP` (backend dot-notation → frontend underscore)
- Bus bridge auto-connects on layout mount, disconnects on cleanup

**Background Job Queue**
- `JobQueue` service (`kernel/services/job_queue.py`) — async `PriorityQueue` with configurable `max_workers` (default 3), DB persistence via `JobQueueRepository`, retry logic with `max_retries`, progress tracking with 10% debounce
- `kernel_jobs` table with full lifecycle tracking (pending → running → completed/failed/cancelled)
- `JobQueueRepository` — `create_job`, `update_job`, `list_jobs`, `get_pending_jobs` for crash recovery
- REST API at `/api/kernel/jobs/*` — `POST /submit` (202), `GET /{job_id}`, `POST /{job_id}/cancel`, `GET` (list with filters)
- `AppBase.get_job_handlers()` lifecycle hook — apps register async job handlers, kernel auto-wires them on startup
- `recover_pending()` on startup restores in-flight jobs from DB
- Bus events: `kernel:job.submitted`, `kernel:job.started`, `kernel:job.progress`, `kernel:job.completed`, `kernel:job.failed`
- Frontend `jobClient.ts` — `submitJob`, `getJob`, `cancelJob`, `listJobs`

**Cross-App Integration (TextForge ↔ PromptForge)**
- TextForge auto-simplify: `promptforge:optimization.completed` with `overall_score < 7.0` triggers a `textforge:auto-simplify` background job
- Auto-simplify handler: fetches optimized prompt, runs LLM simplification, stores result in app storage, computes real `improvement_delta`
- TextForge window: "Suggested Simplifications" section shows auto-generated transforms linked to PF optimizations, with "Use as input" action
- Cross-app prefill: `SimplifyAction` extension emits `textforge:prefill` bus event → TextForge window auto-fills input

**Extension Points Framework**
- `ExtensionSlotDef` and `ExtensionDef` in backend manifests and frontend types — host apps declare slots, guest apps declare contributions
- `appRegistry` indexes extensions during `register()`, `getExtensions(slotId)` returns `ResolvedExtension[]` sorted by priority
- `ExtensionSlot.svelte` — lazy-loads guest components with error handling and context spreading
- PromptForge declares `review-actions` slot; TextForge contributes `SimplifyAction` with priority 10
- `max_extensions` enforcement and late binding support (guest can register before host)

**App Manager & Quota Dashboard**
- `AppManagerWindow.svelte` — grid of installed apps with status badges, enable/disable toggles, service satisfaction, resource usage vs. quota progress bars (green/yellow/red)
- `AuditLogWindow.svelte` — cross-app audit log table with app filter, action color coding, relative timestamps, pagination, live updates
- Frontend clients: `appManagerClient.ts`, `auditClient.ts` wrapping kernel REST endpoints
- Audit logging in PromptForge (optimize, batch, retry) and TextForge (transforms) via `_audit_log_optimization()` DRY helper
- `GET /api/kernel/audit/all`, `GET .../summary`, `GET .../usage` — cross-app audit and usage endpoints
- `GET /api/kernel/apps` now includes `resource_quotas` per app
- Quota enforcement on batch and retry endpoints (not just single optimize)

### Fixed

**Three-Tier Context Injection**
- `codebase_context_from_dict()` no longer crashes on non-dict input (e.g. JSON arrays); returns `None` instead of `AttributeError`
- `codebase_context_from_dict()` now coerces scalar fields to `str` and validates list field types, preventing garbage renders from `{"language": 42}` or `{"conventions": {"a": 1}}`
- `get_context_by_name()` resolves nested projects (removed `parent_id.is_(None)` filter); excludes deleted projects; handles name duplicates via `updated_at` ordering
- `/orchestrate/validate` now accepts `strategy` field and passes it to the validator for `framework_adherence_score` computation (previously always `None`)
- `/optimize/{id}/retry` now accepts optional JSON body with `strategy`, `secondary_frameworks`, and `codebase_context` overrides — REST parity with MCP `retry` tool
- `merge_contexts()` now returns shallow copies instead of identity references — prevents aliasing bugs where callers (e.g. description fallback injection) mutate the original workspace/project context objects
- `get_link_by_project_name()` no longer crashes with `MultipleResultsFound` when duplicate project names exist — uses `ORDER BY updated_at DESC LIMIT 1`
- All 4 `/orchestrate/*` endpoints now accept optional `project` field for full 3-layer context resolution (workspace → manual → explicit) — previously only used explicit layer
- REST and MCP `batch` endpoints now auto-link batch items to `Prompt` records via `ensure_prompt_in_project()` — previously skipped prompt linking unlike single optimize

**Kernel Bug Fixes & Polish**
- VFS `move_folder` now cascades depth updates to all descendant folders via `_cascade_depth()` — previously only the moved folder's depth was updated, leaving children with stale depth values
- `batch_optimize` event publishing now uses `pipeline_result.strategy` (actual strategy used) instead of `request.strategy` (user override), and includes `duration_ms` matching the streaming path
- VFS rename endpoints (`PATCH .../rename`) catch `IntegrityError` from UNIQUE constraint violations and return 409 instead of 500
- `bus.py` service retrieval (`_get_bus`, `_get_contracts`) now returns 503 with a clear message if EventBus or ContractRegistry services are not available, instead of crashing on `None`
- Audit router endpoints (`GET /api/kernel/audit/{app_id}`, `GET .../usage/{app_id}`) now require `audit:read` capability — previously had no access control
- `audit:read` added to `PERMISSIVE_CAPABILITIES` and all app manifests' optional capabilities
- Frontend `appRegistry.destroyAll()` uses `.length = 0` instead of array reassignment for correct Svelte 5 `$state` reactivity
- Frontend `appSettings.reset()` now consumes the response body for consistent cleanup
- Frontend `kernel/index.ts` exports all service singletons (`appSettings`, `appStorage`, `vfs`) alongside `appRegistry`

### Changed

**PromptForge Code Migration**
- All PF business logic moved from `backend/app/` to `backend/apps/promptforge/` — routers, services, models, schemas, repositories, utils, prompts, constants, converters, database migrations, MCP server
- PF routes migrated from `/api/*` to `/api/apps/promptforge/*` via manifest prefix
- Frontend `BASE_URL` updated to `/api/apps/promptforge`
- MCP server module moved to `apps.promptforge.mcp_server`
- `app/database.py` slimmed to kernel-only; PF migrations extracted to `apps/promptforge/database.py`
- Removed `exclude="promptforge"` hack from `registry.mount_routers()` — all apps auto-mounted via manifest

**OS Kernel Architecture**
- Backend app registry (`kernel/registry/`) — `AppRegistry` discovers `manifest.json` in `apps/`, loads `AppBase` subclasses, manages lifecycle (on_startup/on_shutdown), dynamically mounts routers via `mount_routers()`
- `AppManifest` Pydantic model — declares backend routers, models, frontend windows, commands, file types, start menu, desktop icons, settings
- `AppBase` ABC — lifecycle hooks (`on_install`, `on_enable`, `on_startup`, `on_shutdown`, `run_migrations`)
- Kernel API endpoints — `GET /api/kernel/apps` lists installed apps, `GET /api/kernel/apps/{id}` returns app details and manifest
- PromptForge app (`backend/apps/promptforge/`) — thin wrapper: `manifest.json`, `PromptForgeApp(AppBase)` with lifecycle hooks and migration delegation
- Hello World example app (`backend/apps/hello_world/`) — minimal app demonstrating the platform: `manifest.json`, `HelloWorldApp(AppBase)`, router at `/api/apps/hello-world/*`
- Frontend kernel shell (`frontend/src/lib/kernel/`) — `AppFrontend` interface, `KernelAPI` type, `appRegistry.svelte.ts` for frontend app discovery and registry-driven window rendering
- Frontend `+layout.svelte` — replaced ~180 lines of hardcoded window blocks with a single registry-driven `{#each appRegistry.allWindows}` loop; apps declare windows in manifests, kernel shell renders them dynamically
- `DesktopWindow` title resolution — uses `windowManager` state title (dynamically updated via `updateWindowTitle()`) with prop fallback
- Frontend PromptForge app (`frontend/src/lib/apps/promptforge/`) — `PromptForgeApp` implements `AppFrontend` with `COMPONENT_MAP` for 14 lazy-loaded window components
- Frontend Hello World app (`frontend/src/lib/apps/hello_world/`) — `HelloWorldApp` with `HelloWorldWindow.svelte`

**Backend Kernel Object & Service Registry**
- `Kernel` dataclass (`kernel/core.py`) — service locator passed to apps via `on_startup(kernel)` and `on_shutdown(kernel)`, providing `app_registry`, `db_session_factory`, `services`, and `get_provider()` for LLM access
- `ServiceRegistry` (`kernel/services/registry.py`) — DI container with `register`, `get`, `has`, `validate_requirements`. Core services registered at startup: `llm`, `db`, `storage`
- `GET /api/kernel/apps` now includes `services_satisfied` boolean per app, computed from `ServiceRegistry.validate_requirements()`

**Per-App Settings & Document Storage**
- `app_settings` kernel table — per-app key-value settings with `UNIQUE(app_id, key)`, JSON-serialized values
- `AppSettingsRepository` — `get_all`, `get`, `set` (upsert), `set_all`, `delete`, `reset`
- Settings REST API — `GET/PUT/DELETE /api/kernel/settings/{app_id}`
- `app_collections` + `app_documents` kernel tables — per-app scoped document store with collections and documents, `ON DELETE CASCADE` foreign keys
- `AppStorageRepository` — full CRUD for collections and documents
- Storage REST API — `CRUD /api/kernel/storage/{app_id}/collections`, `CRUD /api/kernel/storage/{app_id}/documents`
- Kernel-level database migrations (`kernel/database.py`) — `CREATE TABLE/INDEX IF NOT EXISTS`, runs before app migrations in `init_db()`
- Kernel router aggregation — 6 sub-routers (apps, audit, bus, settings, storage, vfs) aggregated into single `kernel_router` mounted once

**Process Types from Manifest**
- `ForgeProcess.processType` field (default `'forge'`) — manifest-declared process types flow through spawn/display
- `TaskManagerWindow` "Type" column — looks up process type metadata from `appRegistry.allProcessTypes` for icon/label display
- `appRegistry.allProcessTypes` getter — flat-maps process types from all registered apps with `appId` injection

**Dynamic App Settings UI**
- `appSettings` frontend service (`appSettings.svelte.ts`) — reactive `$state` cache wrapping `GET/PUT/DELETE /api/kernel/settings/{appId}`
- `ControlPanelWindow` dynamic tabs — appends one tab per app from `appRegistry.appsWithSettings`, lazy-loads settings component via `getSettingsComponent()`
- `KernelAPI` expanded — `KernelAppSettings` (load/save/reset/get/isLoading), `KernelStorage` (full CRUD), `KernelProcessScheduler` (spawn/complete/fail/updateProgress/cancel)
- `appStorage` frontend client (`appStorage.ts`) — wraps kernel document storage REST API

**TextForge App — Second Real App**
- Backend (`apps/textforge/`) — 7 transform types (summarize, expand, rewrite, simplify, translate, extract_keywords, fix_grammar) with system prompts and LLM prompt templates; uses `CompletionRequest`/`CompletionResponse` provider API; proper error classification (`RateLimitError`, `AuthenticationError`, `ProviderError`); stores transforms in kernel document storage
- `manifest.json` — 2 windows, 2 commands, 1 file type (`.txf`), 1 process type (`transform` with stages `analyze`/`transform`/`validate`), desktop icon, start menu, settings schema, `requires_services: ["llm", "storage"]`
- Frontend (`apps/textforge/`) — `TextForgeWindow` (split input/output with type selector, tone/language options, process scheduler integration), `TextForgeHistoryWindow` (list+detail with type-colored badges), `TextForgeSettings` (default transform, output format, preserve formatting)
- Brand-guideline styled — flat neon contour aesthetic with neon-orange accent

**Kernel Wiring — Manifest-to-Consumer Integration**
- Desktop icons from registry — `desktopStore.createDefaultIcons()` now sources app icons from `appRegistry.allDesktopIcons` via `manifestIconToStore()` mapping; `syncAppIcons()` merges icons after registry population; generic `_executeIconAction()` dispatches `openWindow:*` action strings replacing 12 hardcoded if/else branches
- Start menu from registry — `StartMenu.svelte` pinned section now reads from `appRegistry.allStartMenuEntries` mapped to window registrations for labels/icons; API Docs kept as system link
- Command palette from registry — 14 PromptForge-specific commands moved from `+layout.svelte` `registerAll()` into `PromptForgeApp.init(kernel)` via `kernel.commandPalette.registerAll()`; HelloWorld registers its "Say Hello" command in `init()`; 8 kernel commands remain in layout
- Typed `KernelAPI` — replaced all `unknown` fields with 8 proper interfaces (`KernelBus`, `KernelWindowManager`, `KernelCommandPalette`, `KernelProcessScheduler`, `KernelSettings`, `KernelClipboard`); apps can now call kernel methods without casting
- `CommandCategory` widened from closed union to open union with `(string & {})` for app-defined categories
- App migrations wired into `init_db()` — optional `app_registry` parameter; after kernel migrations, iterates `registry.list_enabled()` and calls `run_migrations(conn)` per app
- File type registry integration — `FILE_EXTENSIONS` backed by a `Proxy` that falls back to `appRegistry.allFileTypes`; `documentOpener.ts` routes unknown file types to `appRegistry` via `openViaRegistry()` fallback
- MCP tool aggregation — `AppRegistry.collect_mcp_tools()` calls `get_mcp_tools()` on all enabled apps; MCP server lifespan registers collected tools at startup
- `FileExtension` type widened with `(string & {})` for app-defined extensions
- Backend `DesktopIconDef` model — added optional `color` and `type` fields to match frontend types
- Backend `manifest.json` synced — PromptForge backend manifest now mirrors frontend manifest for desktop_icons (11), commands (14), and start_menu pinned items

**PromptForge FileSystem (PFFS)**
- Hierarchical folder system for projects — `parent_id` self-FK with precomputed `depth` (max 8 via `MAX_FOLDER_DEPTH`), scoped `UNIQUE(name, parent_id)` constraint, nullable `Prompt.project_id` (NULL = desktop/unorganized)
- 6 filesystem API endpoints — `GET /api/fs/children`, `GET /api/fs/tree`, `GET /api/fs/path/{project_id}`, `GET /api/fs/prompt/{prompt_id}`, `DELETE /api/fs/prompt/{prompt_id}`, `POST /api/fs/move`
- File type system — `FileExtension` registry (`.md`, `.forge`, `.scan`, `.val`, `.strat`, `.tmpl`, `.app`, `.lnk`), `ArtifactKind` enum (`forge-result`, `forge-analysis`, `forge-scores`, `forge-strategy`), `TYPE_SORT_ORDER` (system < folder < shortcut < file)
- `FileDescriptor` discriminated union — `PromptDescriptor`, `ArtifactDescriptor`, `SubArtifactDescriptor`, `TemplateDescriptor`, `FolderDescriptor` with factory helpers and type guards
- Unified document opener (`documentOpener.ts`) — single `openDocument(descriptor)` entry point replacing separate `openPromptInIDE()` and `openInIDEFromHistory()` paths; all contexts (history, projects, start menu, notifications, drag-and-drop, desktop icons) funnel through it
- Filesystem orchestrator store (`filesystemOrchestrator.svelte.ts`) — caching, mutation methods (`createFolder`, `move`, `renameFolder`, `deleteFolder`, `deletePrompt`), `validateDrop()` for drag targets, `fs:created/moved/deleted/renamed` bus events
- `FolderWindow` component — breadcrumb navigation, inline folder creation, forge expansion with score badges, drag-and-drop between folders, live refresh via bus events
- `DesktopSurface` component — grid-based icon layout with selection, double-click open, context menu, drag-to-reposition, folder/prompt sync from DB, external drag-and-drop (move into folder or to root), wallpaper layer
- Drag-and-drop system (`dragPayload.ts`) — `DragPayload` with `NodeDescriptor` and `DragSource`, custom MIME `application/x-promptforge`, `encodeDragPayload()`/`decodeDragPayload()` serialization
- MCP tools `get_children` and `move` for filesystem operations

**Snap Layout System**
- Windows 11-style snap zones — 7 zone IDs (`left`, `right`, `top`, `top-left`, `top-right`, `bottom-left`, `bottom-right`) with 20px edge threshold, corners prioritized over edges
- 7 preset layouts — Full Screen, Left/Right 50/50, 60/40, Top/Bottom, Left + Right Stack (3-pane), Left Stack + Right (3-pane), Quad Grid (4-pane)
- `SnapPreview` component — live overlay showing target zone geometry during drag (fade 120ms)
- `SnapAssist` component — after snapping a window, shows remaining unfilled slots with candidate window buttons (up to 4 per slot, "+N more" overflow)
- `SnapLayoutPicker` component — layout thumbnails on maximize button hover, click assigns window and triggers snap assist
- Magnetic edge snapping — window-to-window magnetic attraction (12px `EDGE_SNAP_THRESHOLD`), viewport snap zones take priority, checks 4 edge relationships per axis with overlap guards
- Snap groups — locked windows move/resize together, lock icon in title bar, group indicators in taskbar with sibling highlight on hover, auto-dissolve when < 2 members
- Keyboard shortcuts — `Alt+Arrow` (snap/maximize/minimize), `Ctrl+Alt+Arrow` (top quadrants), `Ctrl+Alt+Shift+Arrow` (bottom quadrants), `Escape` dismisses snap assist/picker
- System bus events — `snap:created`, `snap:dissolved`, `snap:window_added`, `snap:window_removed`

**Conciseness Dimension, Calibrated Rubric & Comparative Evaluation**
- Conciseness as 5th weighted scoring dimension (20%) — weights: clarity 20%, specificity 20%, structure 15%, faithfulness 25%, conciseness 20%
- Calibrated scoring rubric with anchoring examples — makes 0.95+ genuinely rare, 1.0 requires near-perfection
- `framework_adherence_score` supplementary dimension — measures strategy fit but excluded from the weighted average
- `detected_patterns` JSON list — records which optimization strategies the validator observed in the output, regardless of what was formally selected
- Comparative evaluation via `retry_of` — nullable FK-like text linking retries to parent optimizations; `compute_score_deltas()` computes per-dimension score differences on-the-fly in both GET endpoint and MCP `get` tool

**Display Settings Window**
- `DisplaySettingsWindow` component — performance presets (Low/Balanced/High with auto-detect Custom), wallpaper animation mode (Static/Subtle/Dynamic), opacity slider (5%–35%), accent color grid (10 neon colors), UI animations toggle
- `WallpaperMode` and `PerformanceProfile` types on settings store; `applyPreset(profile)` patches governed fields in one call

**Shared UI Primitives**
- 4 reusable components in `components/ui/` — `EmptyState` (centered icon + message), `InlineProgress` (1px animated progress bar), `StatusDot` (6px color indicator), `WindowTabStrip` (horizontal tab strip with accent active indicator)
- Window components refactored to adopt shared primitives

**Workspace Hub: GitHub-Connected Dynamic Context Management**
- GitHub OAuth integration — connect GitHub account, list/search repos, link repos to projects for automatic codebase context extraction; tokens encrypted at rest via Fernet
- Three-layer context resolution — workspace auto-context (lowest) → manual `context_profile` → per-request `codebase_context` (highest); two chained `merge_contexts()` calls; resolved context snapshotted as `Optimization.codebase_context_snapshot`
- Deterministic context extraction (`workspace_sync.py`) — no LLM calls; parses `package.json`, `pyproject.toml`, `go.mod`, etc. for language/framework; infers conventions from linter configs, test frameworks from dev deps, patterns from directory structure
- Data model — `GitHubConnection` (encrypted tokens), `WorkspaceLink` (project FK with UNIQUE, sync status, workspace_context JSON, sync_source: `'github'`/`'claude-code'`), `Project.workspace_synced_at`
- 9 backend API endpoints — `GET /api/github/authorize`, `GET /api/github/callback`, `GET /api/github/status`, `DELETE /api/github/disconnect`, `GET /api/github/repos`, `POST /api/workspace/link`, `DELETE /api/workspace/{id}`, `POST /api/workspace/{id}/sync`, `GET /api/workspace/status`
- Health endpoint `workspace` section — `github_connected`, `github_username`, `total_links`, `synced`, `stale`, `errors`
- MCP tool `sync_workspace` — push workspace context from Claude Code CLI; creates workspace link with `sync_source='claude-code'`
- MCP resource `promptforge://workspaces` — workspace link statuses with staleness info
- Frontend `WorkspaceWindow` — 3-tab persistent window: GitHub (connect/disconnect, searchable repo list), Workspaces (status table with sync/unlink), Context Inspector (field-by-field source breakdown with completeness bar)
- `workspaceManager` store — reactive state for GitHub connection, repos, workspace links, sync operations
- Bus events `workspace:synced/error/connected/disconnected`, notification service subscriptions

**GitHub OAuth Setup UI**
- In-app OAuth configuration — `GET/PUT/DELETE /api/github/config` endpoints; client secret encrypted at rest, never exposed in API responses
- Setup walkthrough UI — step-by-step form with direct links to GitHub Developer Settings, input fields, security note about encryption
- Three-state GitHub tab — not configured (setup form) → configured but not connected → connected (user card + repos)
- `GitHubOAuthConfig` single-row model with encrypted secret storage
- Config resolution — DB-stored OAuth config takes priority over env vars

**MCP Live Bridge**
- `MCPActivityBroadcaster` (`services/mcp_activity.py`) — in-memory event fan-out with bounded history (100 events), subscriber queue management (max 256 per client), active call state tracking
- MCP Activity Router (`routers/mcp_activity.py`) — `POST /internal/mcp-event` authenticated webhook, `GET /api/mcp/events` SSE stream with `id:` fields and `Last-Event-ID` reconnection support, `GET /api/mcp/status` REST fallback
- `_mcp_tracked` decorator on all MCP tools — emits `tool_start`/`tool_complete`/`tool_error` events via fire-and-forget webhook; includes duration_ms and result_summary; nested call guard via `contextvars.ContextVar`
- MCP Resources — `promptforge://projects`, `promptforge://projects/{id}/context`, `promptforge://optimizations/{id}` for bi-directional context flow
- `MCPActivityFeed` frontend service — SSE client with auto-reconnect (exponential backoff 3s–30s), `Last-Event-ID` tracking for gap-free reconnection, reactive state (events, activeCalls, sessionCount, connected)
- `NetworkMonitorWindow` — 3-tab activity monitor (Live Activity, Event Log, Connections)
- Taskbar network activity indicator, TaskManager External (MCP) section, Terminal `mcp`/`mcp-log`/`netmon` commands
- Notifications for MCP write-tool completions with "Open in IDE" actions
- History/stats auto-reload on external MCP write-tool completion (debounced 1s)
- `optimize` and `batch` tools emit `tool_progress` events via `_emit_tool_progress()` helper

**Cognitive OS Architecture**
- Token Budget Manager (`services/token_budget.py`) — per-provider token tracking with configurable daily limits, auto-reset (24h), health endpoint integration
- System Bus (`systemBus.svelte.ts`) — decoupled IPC with typed events (`forge:*`, `window:*`, `clipboard:copied`, `provider:*`, `history/stats:reload`, `notification:show`, `mcp:*`, `workspace:*`, `fs:*`, `snap:*`), wildcard handlers, recent event log
- Notification Service — system notifications with info/success/warning/error types, auto-dismiss, read/unread tracking, action callbacks, max 50; subscribes to 12+ bus events
- Clipboard Service — copy with 10-entry history, bus integration, fallback textarea method
- Command Palette — fuzzy-matched command registry with `Ctrl+K` activation, categories, recent commands
- Process Scheduler (`processScheduler.svelte.ts`) — bounded-concurrency queue (default `maxConcurrent` 2), spawn/complete/fail/cancel/dismiss lifecycle, rate-limit aware via `provider:rate_limited` bus events, sessionStorage persistence
- Settings Store (`settings.svelte.ts`) — persisted preferences (accent color, default strategy, max concurrent forges, animations, wallpaper mode/opacity, performance profile), localStorage with schema migration
- `ControlPanelWindow` — 4 static tabs (Providers, Pipeline, Display, System) + dynamic app settings tabs from `appRegistry.appsWithSettings`
- `TaskManagerWindow` — process monitor for running/queued/completed forges
- `BatchProcessorWindow` — multi-prompt batch optimization (up to 20) with progress tracking and JSON export
- `StrategyWorkshopWindow` — score heatmap (strategy x task type), win rates, combo analysis
- `TemplateLibraryWindow` — 10 built-in prompt templates across 6 categories with search/filter
- `TerminalWindow` — system bus event log for debugging
- `RecycleBinWindow` — soft-deleted/cancelled optimization viewer
- `CommandPaletteUI` — floating overlay, `NotificationTray` — taskbar dropdown with unread badge
- Batch optimization endpoint (`POST /api/optimize/batch`) and cancel endpoint (`POST /api/optimize/{id}/cancel`)
- MCP `batch` and `cancel` tools

**IDE & Window System**
- Window Manager (`windowManager.svelte.ts`) — multi-window system with z-index stacking, dual-layer persistence (sessionStorage for session state, localStorage for geometry preferences), 3-tier restore fallback, geometry validation, `PERSISTENT_WINDOW_IDS` survive route changes
- Forge Machine (`forgeMachine.svelte.ts`) — state machine (`compose` → `forging` → `review` / `compare`), panel width management, minimize/restore with `isMinimized` state, comparison slots
- Scoped results (`optimization.svelte.ts`) — `forgeResult` (from SSE) and `viewResult` (from history) as separate slots; `result` getter returns `forgeResult ?? viewResult`
- Tab system — `MAX_TABS = 5` with LRU eviction, `WorkspaceTab` carries `resultId`, `mode`, `document`; centralized `createTab()` with sequential "Untitled N" naming; `tabCoherence.ts` for save/restore; forging guards block tab operations during active forges
- Taskbar (`ForgeTaskbar.svelte`) — horizontal process strip when IDE hidden, click to resume/view
- IDE minimize — `ForgeMinimizedBar` with three mode renders (forging: step dots + timer, review: score + strategy, compare: label); `Ctrl/Cmd+M` toggle, `Escape` restores
- IDE-native interactions — all entry points open results in IDE via `openDocument()`; no detail page routes exist
- `openPromptInIDE()` utility — branches on forge_count: latest forge → review mode, no forges → compose mode
- Nautilus-style file manager — `FileManagerView`/`FileManagerRow` with sortable columns, drill-down navigation with back/forward stacks, `WindowNavigation` interface for per-window nav
- Compare robustness — async server fallback in `ForgeCompare` with staleness guards and race-condition protection
- Keyboard shortcuts — `Ctrl/Cmd+N` new tab, `Ctrl/Cmd+W` close tab, `Ctrl/Cmd+M` toggle minimize, `Escape` restore/close, `/` focus textarea
- `fly` transition for IDE open/close (window feel) vs `fade` for dashboard

**Pipeline & Provider Enhancements**
- Prompt caching on `AnthropicAPIProvider` — `cache_control={"type": "ephemeral"}` on all API calls; tracks `cache_creation_input_tokens` and `cache_read_input_tokens` in `TokenUsage`, DB model, API schemas, and frontend display
- SDK-typed error classification — `_classify_anthropic_error()` uses Anthropic SDK exception hierarchy with `retry-after` header extraction
- Async `count_tokens()` — `LLMProvider.count_tokens()` is now async; `AnthropicAPIProvider` calls SDK's `messages.count_tokens()` with heuristic fallback
- MCP health monitoring — backend probes MCP server `/health`, surfaces `mcp_connected` in health response, frontend fires toast on status transitions
- Project-scoped stats — `GET /api/history/stats?project=...` query parameter
- Extended analytics engine — score matrix (strategy x task-type), score variance, confidence averages, combo effectiveness, complexity performance, improvement/error rates, time trends, token economics, win rates
- Context profiles — persistent `CodebaseContext` on projects, auto-resolved during optimization, 8 stack templates (SvelteKit, FastAPI, Next.js, Django, Express, Rails, Spring Boot, Go), `ContextProfileEditor` component, `set_project_context` MCP tool
- Codebase context pipeline support — all 4 stages inject rendered context into LLM messages when `codebase_context` provided
- Bulk-delete endpoint (`POST /api/history/bulk-delete`) and `bulk_delete` MCP tool
- Iterative refinement — `max_iterations` and `score_threshold` parameters on pipeline, loops Optimize + Validate until score threshold met
- Individual stage endpoints — `POST /api/orchestrate/analyze|strategy|optimize|validate`

**Frontend Dashboard & UI**
- `HeaderStats` component — wing formation layout with center-stage task type chip, context-aware project label
- `OnboardingHero` — interactive 3-step workflow guide (Write → Forge → Iterate), dismissible, shown for < 5 forges
- `RecentForges` dashboard section — last 6 optimizations as compact cards with score, task type, strategy
- `RecentProjects` dashboard section — up to 4 recent projects with prompt count and context indicator
- Per-task-type color system (`taskTypes.ts`) — 14 unique neon colors; per-complexity colors (`complexity.ts`) — green/yellow/red with alias normalization
- Stateful header stats — project-scoped on project views, global elsewhere
- Sidebar state store (`sidebar.svelte.ts`) with localStorage persistence
- Desktop context menu, desktop icons for all windows

**init.sh Enhancements**
- 9 subcommands — `build` (pre-built assets, no hot-reload), `stop`, `restart`, `restart-build`, `status` (per-service health + auth/rate-limit config), `test` (pytest + vitest + svelte-check), `seed` (example data), `mcp` (print config snippet), `help`
- Robust process management — `kill_pid_tree()` recursive kill, `find_port_pid()` with 3-tier fallback (lsof → fuser → ss), `wait_for_port_free()`/`wait_for_url()` polling
- `.env` config reading for ports, auth, rate limits; health check polling with provider info in startup banner; log file security (chmod 600/700)

### Changed

- App command registration DRYed — `PromptForgeApp.init()` and `HelloWorldApp.init()` now build commands from `manifest.commands` metadata merged with an execute function map, eliminating duplicated id/label/category/icon/shortcut across 14+ command definitions
- `closeActiveTab()` extracted from `+layout.svelte` into `PromptForgeApp` module as a shared export; layout keyboard handler and command palette both use the same function
- Window-open commands auto-generated — `window-*` command IDs automatically derive their execute function from the corresponding manifest window, replacing 10 near-identical manual entries
- License changed from MIT to Apache 2.0
- Homepage transformed from forge-only into content dashboard (RecentForges + RecentProjects + StrategyInsights)
- Route-based detail pages removed — `/projects/[id]` and `/optimize/[id]` routes deleted; all interactions through the persistent window system
- `total_projects` stat counts only active projects from the `projects` table (not from optimizations)
- IDE compaction — VS Code + Excel density overhaul, strict 2–8px spacing scale, `leading-relaxed` → `leading-snug`, extracted `.section-toggle-btn` CSS utility
- Process lifecycle consolidated — removed deprecated `forgeMachine` bridge methods; all callers use `processScheduler` directly
- Stats cache extracted to `services/stats_cache.py` to eliminate circular dependency
- Version schema validation — empty/whitespace version strings normalize to `None`
- MCP batch tool now resolves project codebase context and snapshots it on records
- Breadcrumbs redesigned — glass pill container, monospace typography, `/` separators, neon-cyan hover
- Sidebar open state lifted to `sidebarState` store with localStorage persistence
- Frontend stores documentation extracted to `docs/frontend-internals.md`
- `ForgeHero` replaced by `OnboardingHero` (workflow guide) and `HeaderStats` (persistent stats bar)
- Header bolt icon removed; HeaderStats fills full header width

### Fixed

**Kernel Robustness**
- AppRegistry double-init guard — `setKernel()` now tracks per-record `initialized` flag; prevents `init()` being called twice when an app registers after kernel is already set; `destroyAll()` resets flags and kernel reference
- StartMenu accent color derivation — replaced hardcoded 5-color map with dynamic `text-${accent}` class derivation from `manifest.accent_color`, supporting all 10 neon palette colors
- `FILE_EXTENSIONS` Proxy — added `Symbol` type guards to `get`/`has` traps preventing runtime errors from framework introspection (Svelte/Vite calling `Symbol.toPrimitive` etc.)
- `documentOpener` type safety — `openViaRegistry()` uses `as unknown as Record<string, unknown>` with runtime `typeof` check instead of unsafe direct cast
- `closeActiveTab()` async safety — keyboard handler in `+layout.svelte` now catches rejected promise instead of firing and forgetting

**Notification System**
- `forge:completed` "Open in IDE" dead action — handler read `event.payload.openInIDE` (always undefined); now self-contained via lazy `import()` callback
- `MCP_WRITE_TOOLS` incomplete — `delete`, `bulk_delete`, `tag`, `add_prompt`, `update_prompt`, `set_project_context` were missing; MCP deletions didn't trigger history reload
- `forge:cancelled` and `tournament:completed` unhandled — added notification tray entries with process title / best score
- `mcp:session_disconnect` unhandled — now emits persistent error notification
- Provider store MCP notifications routed through bus — replaced direct `toastState.show()` with `systemBus.emit()` for unified notification flow
- Notification tray crash from duplicate key IDs

**Tab & IDE State**
- Per-tab state coherence — `WorkspaceTab` now carries `resultId` and `mode`, so tab operations correctly save/restore inspector panel state
- Forging guards — tab switching, active-tab close, and new-tab creation blocked during active forge (click and keyboard shortcuts)
- `Ctrl+W` close now clears `forgeResult` and resets mode when closing last tab
- Hydration recovery — on page reload, restores results from server or falls back to compose; resets stale `'forging'` mode
- Centralized tab creation prevents duplicates and enforces `MAX_TABS = 5`; meaningful titles passed to all creation entry points
- Orphaned `processScheduler.spawn()` calls causing zombie processes removed

**Pipeline & Backend**
- Batch endpoint `event.data` bug — `event.result` → `event.data` (AttributeError), dict bracket access for `overall_score`
- Token budget recording now called at pipeline completion in both `run_pipeline()` and `run_pipeline_streaming()`
- `stages` parameter wired — `request.stages` passed through router to pipeline; analyze-only mode returns early
- `most_common_task_type` ignored project filter — subquery used `.correlate(None)` without project filters
- Batch endpoint rewritten to use `run_pipeline()` (non-streaming), added `model_fallback` computation
- Guard array method calls to prevent `TypeError` on string values
- Ruff lint errors fixed (imports, line length, unused vars)

**Frontend**
- `ResultActions.handleReforge()` missing `spawnProcess()` and `forge()` — re-forge had no process tracking or mode transition
- `ResultActions.handleEditReforge()` dropped title, tags, version, sourceAction metadata
- `ForgeTaskbar` completed process click silently failed when `resultHistory` missed — added async server fallback
- "Open in IDE" wrote to `viewResult` but `ForgeReview` read `forgeResult` — now uses `openInIDE()` which sets `forgeResult` directly
- Desync guard immediately reset `forgeMachine` on IDE open — now also checks `windowManager.ideSpawned`
- `ForgeCompare` stale slot data on comparison change — now clears fetched data and adds error handling
- `StrategyWorkshopWindow` heatmap `entry.avg` → `entry.avg_score` to match backend; win rates `best_strategy` → `strategy`
- DRY strategy lists — `ControlPanelWindow` and `BatchProcessorWindow` import `ALL_STRATEGIES` instead of hardcoding
- Clipboard service integration in `TemplateLibraryWindow`
- Window bus events — `windowManager` now emits `window:opened/closed` on system bus
- Dropdown filter reset — allow resetting to "All" in history sidebar
- `score_threshold_to_db` returns correct lower bound for `min_score` filter
- Self-hosted fonts — removed external font CDN dependency
- Added `aria-label` attributes and `{#each}` keys to suppress browser warnings
- Added `id` attributes to 31 form fields missing id/name

**Security**
- OAuth CSRF state validation — callback now validates `state` parameter against time-limited, one-time-use in-memory store (previously generated but never verified)
- Auth middleware exempts OAuth callback endpoint (redirect target cannot carry a token)
- Sanitized exception logging — callback error logs no longer leak sensitive values
- CSRF origin caching fix and `init.sh` built-mode support
- Rate limiter memory leak — fixed unbounded per-IP memory growth with bounded structures and periodic cleanup

**Strategy & Scoring**
- Legacy strategy aliases normalized in stats and historical records (`few-shot` → `few-shot-scaffolding`, etc.)
- Strategy utilization gap resolved across all 10 frameworks
- CLAUDE.md palette documentation corrected — 5 hex values fixed to match `app.css`

### Security

- **MCP server authentication** — `MCP_AUTH_TOKEN` env var enables bearer token auth on MCP server; disabled when empty
- **Internal webhook authentication** — `INTERNAL_WEBHOOK_SECRET` (auto-generated if empty) secures MCP → backend communication
- **MCP localhost binding** — `init.sh` binds MCP to `127.0.0.1`; Docker removes host port mapping (inter-container only)
- **Security headers on MCP server** — same security headers as backend applied to MCP ASGI app
- **Database file permissions** — `init_db()` restricts `data/` to 0o700, `promptforge.db` to 0o600
- **Encryption key validation** — round-trip test on first use; CRITICAL log on mismatch/corruption
- **Docker Compose hardening** — `read_only: true` with `/tmp` tmpfs, `no-new-privileges:true`, `cap_drop: ALL`, memory limits (backend 4G, frontend 512M, MCP 2G), json-file logging with rotation (10m x 3), MCP exposed only to inter-container network
- **init.sh hardening** — log file security (chmod 600/700), process management hardening, doc disclosure scrubbing

### Performance

- SQLite WAL mode + PRAGMAs — `journal_mode=WAL` eliminates reader/writer blocking, `synchronous=NORMAL`, 64MB cache, 64MB mmap, `temp_store=MEMORY`, `busy_timeout=5000`
- GZip compression — `GZipMiddleware(minimum_size=4096)` for response compression
- Read-only DB sessions — `get_db_readonly()` for GET/HEAD endpoints skips unnecessary `commit()` flush
- Shared stats cache — MCP `stats` reuses HTTP router's TTL cache; all mutation paths invalidate consistently
- `ensure_project_by_name()` returns `ProjectInfo` dataclass, eliminating redundant DB round-trip
- Summary serialization reduced from 6 to 2 JSON field deserializations per item
- Archive filter uses `NOT EXISTS` correlated subqueries instead of `NOT IN` with materialized UNION
- Legacy migration batches prompt inserts per project
- Frontend: replaced all 32 `transition-all` instances with specific property transitions
- Frontend: `content-visibility: auto` on sidebar cards for off-screen rendering skip
- Frontend: BrandLogo `IntersectionObserver` pauses/resumes SVG animations when off-screen
- Frontend: skeleton shimmer uses GPU-composited `transform: translateX()` (120 FPS safe)
- Frontend: stats and history load in parallel on mount instead of sequentially
- Frontend: `section-expand` animation uses CSS `grid-template-rows: 0fr→1fr` (no layout thrashing)
- Frontend: `status-degraded-pulse` converted to GPU-composited `opacity` on pseudo-element
- Frontend: Vite `manualChunks` splits `bits-ui` into dedicated vendor chunk; build target `es2022`
- Frontend: tab visibility polling pauses provider health checks when hidden
- Frontend: `PipelineNarrative` consolidation — 8 `$derived` collapsed into one
- Frontend: debounced post-forge reloads (500ms coalesce)
- Frontend: `promptAnalysis.destroy()` cleans up debounce timer on teardown
- Frontend: visibility restore polling adds 0–2s random jitter to prevent thundering herd

## [0.2.0] - 2026-02-18

### Added
- ARCHITECTURE.md — architecture document
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
