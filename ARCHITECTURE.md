# PromptForge Architecture Document

## Section 0: Assumptions

| # | Assumption | Rationale |
|---|-----------|-----------|
| A1 | Single-instance deployment (no horizontal scaling) | SQLite database; self-hosted target audience |
| A2 | API keys are managed client-side or via env vars | Headers (`X-LLM-*`) pass keys per-request; server never persists them |
| A3 | Claude CLI (MAX subscription) is the primary provider | Zero-cost for subscribers; auto-detected first in provider order |
| A4 | All LLM calls are async, but not parallelized within a pipeline run | Each stage depends on the previous stage's output |
| A5 | SSE is sufficient for real-time updates (no WebSocket needed) | Unidirectional server-to-client; no client-to-server streaming |
| A6 | Authentication is optional (self-hosted) | Bearer token via env var; disabled when empty for local/dev use |
| A7 | No multi-tenancy or user isolation | Single-user or trusted-team deployment model |
| A8 | Provider SDKs handle their own TLS and certificate validation | We don't manage TLS for outbound LLM API calls |
| A9 | Docker deployment targets linux/amd64 and linux/arm64 | Standard CI/CD and self-hosted server architectures |
| A10 | Apache 2.0 license for maximum adoption and contribution | Permissive; patent grant; commercial-friendly |

---

## Section 1: Technology Stack

### Backend

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Language | Python | 3.14+ | Async-first, rich LLM SDK ecosystem |
| Framework | FastAPI | ≥0.115 | Native async, automatic OpenAPI docs, dependency injection |
| ORM | SQLAlchemy 2.0 | ≥2.0 | Async session support, mature migration tooling |
| Database | SQLite (aiosqlite) | ≥0.20 | Zero-config, single-file, sufficient for single-instance |
| Validation | Pydantic v2 | ≥2.0 | FastAPI integration, strict type coercion |
| Server | Uvicorn | ≥0.34 | ASGI reference server, HTTP/1.1 + HTTP/2 |

### Frontend

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Framework | SvelteKit 2 | ≥2.15 | SSR + SPA hybrid, file-based routing |
| UI Library | Svelte 5 | ≥5.0 | Runes reactivity (`$state`, `$derived`, `$effect`) |
| Styling | Tailwind CSS 4 | ≥4.0 | Utility-first, CSS custom properties for theming |
| Build | Vite 6 | ≥6.0 | Fast HMR, native ESM |
| Types | TypeScript | ≥5.7 | Strict mode, satisfies operator |

### LLM Provider SDKs

| Provider | SDK | Version |
|----------|-----|---------|
| Claude CLI | claude-agent-sdk | ≥0.1.37 |
| Anthropic API | anthropic | ≥0.40 |
| OpenAI | openai | ≥1.50 |
| Google Gemini | google-genai | ≥1.0 |

---

## Section 2: System Overview

Three services compose the runtime. The backend is the central hub; the frontend and MCP server both communicate with it.

```
┌──────────────────┐      HTTP (REST + SSE)      ┌──────────────────┐
│                  │◄────────────────────────────►│                  │
│  Frontend (5199) │                              │  Backend (8000)  │
│  SvelteKit / SSR │                              │  FastAPI / ASGI  │
│                  │                              │                  │
└──────────────────┘                              └────────┬─────────┘
                                                           │
                                                           │  Internal webhook
                                                           │  (POST /internal/mcp-event)
                                                           │
                                                  ┌────────┴─────────┐
                                                  │                  │
                                                  │  MCP Server (8001)│
                                                  │  FastMCP / SSE   │
                                                  │                  │
                                                  └──────────────────┘
                                                           ▲
                                                           │  MCP protocol (SSE transport)
                                                           │
                                                  ┌────────┴─────────┐
                                                  │  External Clients │
                                                  │  (Claude Code,   │
                                                  │   IDEs, etc.)    │
                                                  └──────────────────┘
```

**Data flow:**

- **Frontend → Backend**: REST API for CRUD, SSE streams for pipeline progress and MCP activity
- **MCP Server → Backend**: Fire-and-forget webhook (`POST /internal/mcp-event`) for tool call activity tracking; direct DB access (shared SQLite file) for all data operations
- **External clients → MCP Server**: MCP protocol over SSE HTTP transport for tool invocation and resource reads
- **Backend → LLM Providers**: Async HTTP via provider SDKs (or CLI subprocess for Claude CLI)

All three services share one SQLite database file. In Docker, this is a named volume; in development, it lives at `data/promptforge.db`.

---

## Section 3: Provider Abstraction Layer

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Pipeline Services                     │
│         (Analyzer, StrategySelector, Optimizer,          │
│                    Validator)                            │
├─────────────────────────────────────────────────────────┤
│              LLMProvider ABC (base.py)                   │
│  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │send_msg  │complete  │complete_ │send_msg_ │          │
│  │          │          │json      │json      │          │
│  └──────────┴──────────┴──────────┴──────────┘          │
├─────────────────────────────────────────────────────────┤
│              ProviderRegistry (registry.py)              │
│  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │claude-cli│anthropic │openai    │gemini    │          │
│  └──────────┴──────────┴──────────┴──────────┘          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 LLMProvider Interface

The abstract base class (`backend/app/providers/base.py`) defines:

- **`send_message(system_prompt, user_message) -> str`** — Core text completion (abstract)
- **`complete(request: CompletionRequest) -> CompletionResponse`** — Unified request/response with token tracking (concrete, delegates to `send_message`)
- **`complete_json(request) -> (dict, CompletionResponse)`** — JSON extraction with 4-strategy fallback + retry (concrete)
- **`send_message_json(system_prompt, user_message) -> dict`** — Legacy JSON helper (concrete)
- **`stream(request) -> AsyncIterator[StreamChunk]`** — Yields text chunks as they arrive; default falls back to `complete()`
- **`count_tokens(text) -> int | None`** — Optional token counting (default returns `None`)
- **`test_connection(timeout) -> (bool, error)`** — Provider health check (concrete, overridable)
- **`supports(capability) -> bool`** — Model capability lookup via `MODEL_CATALOG`
- **`supports_streaming() -> bool`** — Capability flag (default: False)
- **`is_available() -> bool`** — Readiness check (abstract)
- **`model_name`** / **`provider_name`** — Identity properties (abstract)

### 3.3 Provider Adapters

**Claude CLI** (`claude_cli.py`): Uses `claude-agent-sdk` subprocess. No API key — MAX subscription auth via OAuth. Runs in `_ISOLATED_CWD` (tempdir) to prevent project context detection. Heuristic token estimation (~4 chars/token). Handles `rate_limit_event` from SDK `MessageParseError`.

**Anthropic API** (`anthropic_api.py`): Direct `AsyncAnthropic` client. Enables prompt caching (`cache_control={"type": "ephemeral"}`). Tracks `cache_creation_input_tokens` and `cache_read_input_tokens` in `TokenUsage`. Typed exception hierarchy via `_classify_anthropic_error`. Async `count_tokens()` via SDK's `messages.count_tokens()` endpoint.

**OpenAI** (`openai_provider.py`): `AsyncOpenAI` client with Chat Completions API. Maps `prompt_tokens`/`completion_tokens` to `TokenUsage`. System prompt via messages array. Optional `tiktoken` for token counting.

**Gemini** (`gemini_provider.py`): `google.genai.Client` with async `generate_content`. System instruction via `GenerateContentConfig`. Maps `usage_metadata` fields to `TokenUsage`.

### 3.4 ProviderRegistry

Centralized registration, caching, and resolution (`backend/app/providers/registry.py`):

- **Lazy loading**: Providers imported only when first requested
- **Gate functions**: Fast availability checks skip unavailable providers during auto-detection
- **Instance caching**: Default-config instances cached; overridden instances (custom API key/model) created fresh
- **Auto-detect TTL**: 60-second cache with env-var snapshot fingerprinting
- **Resolution order**: Explicit name → `LLM_PROVIDER` env → auto-detect gates

### 3.5 Error Hierarchy

```
ProviderError
├── AuthenticationError        # Invalid/missing API key
├── ProviderPermissionError    # Key lacks permissions
├── RateLimitError             # Rate limit (+ retry_after)
├── ModelNotFoundError         # Invalid model name
├── ProviderUnavailableError   # Provider not ready (also RuntimeError)
└── ProviderConnectionError    # Network/timeout
```

`classify_error()` in `base.py` converts raw SDK exceptions into typed errors via pattern matching.

---

## Section 4: Optimization Pipeline

### 4.1 Four-Stage Flow

Each stage is registered in a `StageRegistry` and runs sequentially — each depends on the prior stage's output.

```
Raw Prompt ──► [1. Analyze] ──► [2. Strategy] ──► [3. Optimize] ──► [4. Validate] ──► Result
                  │                   │                  │                  │
                  ▼                   ▼                  ▼                  ▼
              task_type          strategy name      optimized_prompt    5 dimension
              complexity         reasoning          changes_made        scores + verdict
              weaknesses         confidence
              strengths
```

| # | Stage | Service Class | Output |
|---|-------|--------------|--------|
| 1 | **Analyze** | `AnalyzeStage` | Task type, complexity, weaknesses, strengths |
| 2 | **Strategy** | `StrategyStage` | Strategy name, reasoning, confidence (0.0–1.0) |
| 3 | **Optimize** | `OptimizeStage` | Rewritten prompt, changes made, optimization notes |
| 4 | **Validate** | `ValidateStage` | 5 dimension scores, verdict, detected patterns |

### 4.2 Strategy Selection

LLM-based selection from 10 frameworks, with heuristic fallback:

| Strategy | Description |
|----------|------------|
| `co-star` | Context, Objective, Style, Tone, Audience, Response |
| `risen` | Role, Instructions, Steps, End goal, Narrowing |
| `chain-of-thought` | Step-by-step reasoning chains |
| `few-shot-scaffolding` | Example-driven learning scaffolds |
| `role-task-format` | Role, Task, Format structure |
| `structured-output` | Output schema and format specification |
| `step-by-step` | Sequential instruction decomposition |
| `constraint-injection` | Boundary and constraint specification |
| `context-enrichment` | Context addition and grounding |
| `persona-assignment` | Persona and expertise assignment |

The LLM picks the best strategy given the analysis. On LLM errors, `HeuristicStrategySelector` (3-tier priority system with specificity exemptions and redundancy detection) takes over. Users can override strategy via UI or API, bypassing the LLM call entirely.

### 4.3 SSE Streaming

The pipeline runs as an async generator yielding named SSE events:

| Event | When | Key Fields |
|-------|------|------------|
| `stage` | Start of each stage | `stage`, `message` |
| `step_progress` | During LLM call (periodic) | `step`, `content`, `progress` (0.0–0.9) |
| `analysis` | Analyze completes | `task_type`, `complexity`, `weaknesses`, `strengths` |
| `strategy` | Strategy selected | `strategy`, `reasoning`, `confidence`, `task_type` |
| `optimization` | Optimize completes | `optimized_prompt`, `framework_applied`, `changes_made` |
| `validation` | Validate completes | All scores, `verdict`, `detected_patterns` |
| `iteration` | Iterative refinement loop | `iteration`, `score`, `threshold` |
| `complete` | Pipeline done | Full result with metadata and token counts |
| `error` | Failure | Error message |

Progress timing: `StageConfig` in `backend/app/constants.py` defines per-stage progress intervals (1.0–1.5s) and cycling progress messages. Progress values computed as `min(0.4 + 0.1 * msg_index, 0.9)`.

### 4.4 Iterative Refinement

Both `run_pipeline()` and `run_pipeline_streaming()` support:
- `max_iterations` (default 1 = single pass)
- `score_threshold` (default 1.0 = never iterate)

When the overall score falls below the threshold, the Optimize and Validate stages re-run on the previous output until the score meets the threshold or iterations are exhausted.

### 4.5 Scoring

Five weighted dimensions (stored as 0.0–1.0 floats, displayed as 1–10 integers):

| Dimension | Weight |
|-----------|--------|
| Clarity | 20% |
| Specificity | 20% |
| Structure | 15% |
| Faithfulness | 25% |
| Conciseness | 20% |

The overall score is always server-computed (never trusts LLM arithmetic). One supplementary dimension — `framework_adherence_score` — measures strategy fit but is excluded from the weighted average. Calibrated scoring rubric with anchoring examples makes 0.95+ genuinely rare.

### 4.6 Token Budget Manager

`TokenBudgetManager` (`backend/app/services/token_budget.py`) tracks per-provider token usage with optional daily limits:

- Records `input_tokens`, `output_tokens`, `request_count` per provider
- Auto-resets counters every 24 hours (preserves daily limits)
- `check_available(provider, estimated_tokens)` for pre-flight checks
- Exposed in the health endpoint via `to_dict()`
- Called at pipeline completion to record aggregate usage

---

## Section 5: Data Layer

### 5.1 Entity Relationships

```
Project (hierarchical via parent_id)
├── Prompt (ordered by order_index, project_id nullable = desktop)
│   ├── PromptVersion (immutable snapshots of prior content)
│   └── Optimization (via prompt_id FK)
│       └── Optimization (retry chain via retry_of)
└── WorkspaceLink (one per project, nullable github_connection_id)
        └── GitHubConnection (encrypted OAuth tokens)

GitHubOAuthConfig (single-row, encrypted client secret)
```

### 5.2 Key Models

**`Optimization`** — Core record of a forge run. Stores raw prompt, optimized prompt, all analysis/strategy/validation results, 5+1 scores, strategy metadata, token usage, duration, status, tags, title, version. `retry_of` links retries to parents (score deltas computed on-the-fly). `codebase_context_snapshot` (JSON) preserves the resolved context. `prompt_id` FK links to originating project prompt.

**`Project`** — Hierarchical folder via self-referential `parent_id` (max depth 8). Scoped unique name constraint: `UNIQUE(name, parent_id)`. `context_profile` (JSON) stores persistent `CodebaseContext`. `workspace_synced_at` tracks last GitHub/Claude Code sync.

**`Prompt`** — User-authored prompt content within a project (or desktop when `project_id` is NULL). Ordered by `order_index`. Version tracked: `PromptVersion` snapshots are auto-created on content update.

**`WorkspaceLink`** — Links a project to a GitHub repo or Claude Code workspace. Stores auto-detected `workspace_context` (JSON), `dependencies_snapshot`, `file_tree_snapshot`. `sync_source` distinguishes `'github'` from `'claude-code'`.

**`GitHubConnection`** — GitHub OAuth tokens encrypted at rest via Fernet. One row per GitHub user.

**`GitHubOAuthConfig`** — Single-row table for in-app OAuth App credentials. Client secret encrypted at rest. Resolved with priority over env vars.

### 5.3 Repository Pattern

Three repositories isolate all DB queries from business logic:

| Repository | File | Covers |
|-----------|------|--------|
| `OptimizationRepository` | `repositories/optimization.py` | CRUD, search, stats (10+ analytics), strategy distribution |
| `ProjectRepository` | `repositories/project.py` | Projects, prompts, versions, hierarchical ops, cascading deletes |
| `WorkspaceRepository` | `repositories/workspace.py` | GitHub connections, workspace links, OAuth config |

### 5.4 Score Normalization

DB stores 0.0–1.0 floats. API/MCP/UI displays 1–10 integers. Conversion logic in `backend/app/utils/scores.py`. The `converters.py` module transforms ORM models to Pydantic/dict with scores normalized for display.

### 5.5 SQLite Configuration

PRAGMAs set on every connection via engine event listener:

| PRAGMA | Value | Purpose |
|--------|-------|---------|
| `foreign_keys` | ON | FK enforcement |
| `journal_mode` | WAL | Non-blocking reads during SSE streaming |
| `synchronous` | NORMAL | Safe with WAL, reduced sync overhead |
| `cache_size` | -65536 (64 MB) | Larger page cache |
| `mmap_size` | 67108864 (64 MB) | Memory-mapped I/O |
| `temp_store` | MEMORY | Temp tables in RAM |
| `busy_timeout` | 5000 (5s) | Retry on lock contention |

### 5.6 Startup Sequence

`init_db()` runs on application startup:

1. **Create tables** — `Base.metadata.create_all` from ORM models
2. **Run migrations** — ~40+ ALTER TABLE / CREATE INDEX migrations (idempotent via `OperationalError` catch)
3. **Rebuild projects table** — Schema v1: adds `parent_id`, `depth`, scoped unique constraint
4. **Rebuild prompts table** — Schema v2: makes `project_id` nullable, changes cascade to `SET NULL`
5. **Migrate legacy strategies** — Normalizes old strategy names via `LEGACY_STRATEGY_ALIASES`
6. **Migrate legacy projects** — Seeds `projects` table from distinct `optimization.project` strings
7. **Backfill missing prompts** — Creates Prompt records for orphaned optimizations
8. **Backfill prompt IDs** — Links existing optimizations to project prompts by content match
9. **Cleanup stale running** — Marks orphaned RUNNING records (>30 min) as ERROR
10. **Harden data directory** — Sets `data/` to 0o700, DB file to 0o600

Schema versions tracked in a `_schema_version` table for idempotent table rebuilds.

---

## Section 6: MCP Server

### 6.1 Overview

FastMCP-based server (`backend/app/mcp_server.py`) exposing 22 tools and 4 resources over SSE HTTP transport on port 8001. Provides full programmatic access to PromptForge for external clients (Claude Code, IDEs). Auto-discoverable via `.mcp.json`.

### 6.2 Tools

| Tool | Description | Mutating |
|------|------------|----------|
| `optimize` | Run full 4-stage pipeline on a prompt | Yes |
| `retry` | Re-run optimization with optional strategy override | Yes |
| `get` | Retrieve optimization by UUID | No |
| `list` | List optimizations with filtering and pagination | No |
| `get_by_project` | Retrieve optimizations for a project by name | No |
| `search` | Full-text search across prompts, titles, tags | No |
| `tag` | Add/remove tags, set project/title on an optimization | Yes |
| `stats` | Usage statistics (strategy distribution, score analytics) | No |
| `delete` | Permanently delete an optimization | Yes |
| `bulk_delete` | Delete 1–100 optimizations by ID | Yes |
| `list_projects` | List projects with filtering and pagination | No |
| `get_project` | Retrieve project with associated prompts | No |
| `strategies` | List all 10 available optimization strategies | No |
| `create_project` | Create project (supports `parent_id` for subfolders) | Yes |
| `add_prompt` | Add prompt to a project | Yes |
| `update_prompt` | Update prompt content (auto-snapshots prior version) | Yes |
| `set_project_context` | Set/clear codebase context profile on a project | Yes |
| `batch` | Optimize 1–20 prompts in a single call | Yes |
| `cancel` | Cancel a running optimization | Yes |
| `sync_workspace` | Push workspace context from Claude Code to a project | Yes |
| `get_children` | List folder/prompt children at a hierarchy level | No |
| `move` | Move folder or prompt to new parent | Yes |

### 6.3 Resources

| URI | Description |
|-----|-------------|
| `promptforge://projects` | Active project list with context indicators |
| `promptforge://projects/{id}/context` | Project's codebase context profile |
| `promptforge://optimizations/{id}` | Full optimization result with display scores |
| `promptforge://workspaces` | Workspace link statuses with staleness info |

### 6.4 Activity Tracking

All tools are wrapped with `_mcp_tracked(tool_name)` which emits lifecycle events via fire-and-forget webhook to the backend:

```
External Client ──MCP──► MCP Server ──webhook──► Backend ──SSE──► Frontend
                         (tool_start)            (broadcasts)     (NetworkMonitor,
                         (tool_complete)                            TaskManager,
                         (tool_error)                              Notifications)
```

- `_extract_result_summary()` pulls `id`, `status`, `overall_score`, `total` from results
- Webhook uses `X-Webhook-Secret` header when `INTERNAL_WEBHOOK_SECRET` is configured
- Tool calls never fail if the webhook is unreachable
- Backend `MCPActivityBroadcaster` singleton provides in-memory pub/sub with bounded history
- SSE stream (`GET /api/mcp/events`) supports `Last-Event-ID` for gap-free reconnection

### 6.5 Authentication

Optional bearer token auth via `MCP_AUTH_TOKEN` env var. When set, `MCPAuthMiddleware` (separate from the main app's auth) validates tokens on all MCP endpoints except `/health`. Disabled when empty.

---

## Section 7: Codebase Context System

### 7.1 Three-Layer Merge

When an optimization references a project, the pipeline resolves codebase context through three layers, each overriding the previous:

```
Layer 1: Workspace auto-context     (from GitHub sync or sync_workspace MCP tool)
    ▼  merge_contexts()
Layer 2: Manual project context      (from context_profile on Project record)
    ▼  merge_contexts()
Layer 3: Per-request context         (from codebase_context parameter on API/MCP call)
    ▼
Resolved context ──► snapshotted as Optimization.codebase_context_snapshot
```

### 7.2 Context Fields

All fields are optional; unknown keys are silently ignored:

| Field | Description |
|-------|-------------|
| `language` | Primary programming language |
| `framework` | Primary framework |
| `description` | Project description |
| `conventions` | Coding conventions and style rules |
| `patterns` | Architectural patterns in use |
| `code_snippets` | Representative code examples |
| `documentation` | Relevant documentation excerpts |
| `test_framework` | Testing framework |
| `test_patterns` | Testing patterns and conventions |

### 7.3 Context Sources

**GitHub OAuth** (`sync_source='github'`): `workspace_sync.py` performs deterministic extraction (no LLM calls) — detects language/framework from marker files, conventions from linter configs, test frameworks from dev dependencies, infrastructure patterns (Docker, CI/CD, monorepo), and README documentation.

**Claude Code** (`sync_source='claude-code'`): The `sync_workspace` MCP tool accepts workspace metadata (repo URL, git branch, file tree, dependencies) and creates/updates a workspace link.

**Manual**: `context_profile` on the Project record, managed via `PUT /api/projects/{id}`, MCP `set_project_context`, or the `ContextProfileEditor` component. Stack templates provide 8 pre-built profiles for common technology stacks.

### 7.4 Pipeline Integration

All four pipeline stages (`Analyze`, `Strategy`, `Optimize`, `Validate`) accept an optional `codebase_context` parameter. When provided, each stage injects the rendered context into its LLM user message so the optimizer produces prompts grounded in actual codebase patterns.

---

## Section 8: Frontend Architecture

### 8.1 OS Metaphor

The frontend follows an operating system metaphor: the dashboard is a desktop surface, the sidebar is a start menu, and the IDE is a VS Code-like program running in a managed window. All interactions — viewing projects, browsing history, forging prompts — happen through a persistent window system.

### 8.2 Window Manager

`windowManager.svelte.ts` implements a multi-window system:

- **Z-index stacking** with focus tracking
- **Dual-layer persistence**: sessionStorage (`pf_wm`) for session state; localStorage (`pf_window_prefs`) for per-window geometry preferences
- **Snap layouts** (`snapLayout.ts`): Windows 11-style snap zones with 20px edge threshold, 7 preset layouts, and locked snap groups
- **Magnetic edge snapping**: Window-to-window magnetic attraction (12px threshold) with viewport snap priority
- **Keyboard shortcuts**: `Alt+Arrow` (snap/maximize/minimize), `Ctrl+Alt+Arrow` (top quadrants), `Ctrl+Alt+Shift+Arrow` (bottom quadrants)
- **Persistent windows**: IDE, Recycle Bin, Projects, History survive route changes and minimize on active taskbar click

### 8.3 Window Catalog

| Window | Purpose |
|--------|---------|
| `ForgeIDEEditor` | Primary prompt editing and forge result review (tabbed workspace) |
| `ProjectsWindow` | Project browser with folder hierarchy |
| `HistoryWindow` | Optimization history with search and filters |
| `ControlPanelWindow` | Provider, pipeline, display, and system settings |
| `TaskManagerWindow` | Process monitor (running/completed/queued forges) |
| `BatchProcessorWindow` | Multi-prompt batch optimization |
| `StrategyWorkshopWindow` | Score heatmap, win rates, combo analysis |
| `TemplateLibraryWindow` | Prompt templates with search and categories |
| `TerminalWindow` | System bus event log + MCP commands |
| `NetworkMonitorWindow` | Real-time MCP tool call activity (live, event log, connections) |
| `RecycleBinWindow` | Soft-deleted items |
| `WorkspaceWindow` | GitHub OAuth, workspace links, context inspector |
| `DisplaySettingsWindow` | Wallpaper, accent color, performance presets |
| `FolderWindow` | Folder contents with breadcrumbs |

### 8.4 PFFS Type System

OS-like file type architecture for IDE documents and desktop entities:

- **`FileDescriptor`** discriminated union: `'prompt'` (user-authored), `'artifact'` (forge results), `'sub-artifact'` (analysis/scores/strategy), `'template'` (future)
- **`FileExtension`** registry: `.md`, `.forge`, `.scan`, `.val`, `.strat`, `.tmpl`, `.app`, `.lnk`
- **`ArtifactKind`** enum: `'forge-result'`, `'forge-analysis'`, `'forge-scores'`, `'forge-strategy'`
- **Unified document opener** (`documentOpener.ts`): Single `openDocument(descriptor)` entry point for all contexts (history, projects, start menu, notifications, drag-and-drop, desktop icons)
- **Desktop icons**: System apps use `.app` extension (hidden in label), shortcuts use `.lnk` (visible), DB prompts use `.md`
- **Drag-and-drop**: `DragPayload` with custom MIME `application/x-promptforge`

### 8.5 Forge Machine & Process Scheduler

**Forge Machine** (`forgeMachine.svelte.ts`): State machine governing IDE modes — `compose` → `forging` → `review` / `compare`. Manages panel width (auto-widen on forge/compare), minimize/restore state, and comparison slots.

**Process Scheduler** (`processScheduler.svelte.ts`): Single source of truth for all forge process lifecycle. Bounded-concurrency queue (`maxConcurrent` default 2). Methods: `spawn`, `complete`, `fail`, `cancel`, `dismiss`, `updateProgress`. Rate-limit aware via `provider:rate_limited` bus events. Persisted to sessionStorage; running processes become `'error'` on hydrate.

**Tab System**: `MAX_TABS = 5` with LRU eviction. Each `WorkspaceTab` carries `resultId`, `mode` (`ForgeMode`), and `document` (`FileDescriptor | null`). Tab coordination (`tabCoherence.ts`) saves/restores inspector panel state on tab switches. Forging guards block tab switching during active forges.

### 8.6 Scoped Results

Two separate result slots prevent clobbering — `forgeResult` (set by SSE pipeline) and `viewResult` (set by loading from history). The `result` getter returns `forgeResult ?? viewResult`. `resetForge()` clears forge-side state while preserving `viewResult`.

### 8.7 System Bus

`systemBus.svelte.ts` provides decoupled IPC for inter-store communication:

| Event Category | Events |
|---------------|--------|
| `forge:*` | `started`, `completed`, `failed`, `cancelled` |
| `window:*` | `opened`, `closed`, `focused` |
| `provider:*` | `rate_limited`, `unavailable` |
| `mcp:*` | `tool_complete`, `tool_error`, `session_connect`, `session_disconnect` |
| `workspace:*` | `synced`, `error`, `connected`, `disconnected` |
| `fs:*` | `created`, `moved`, `deleted`, `renamed` |
| `snap:*` | `created`, `dissolved`, `window_added`, `window_removed` |
| Others | `clipboard:copied`, `history:reload`, `stats:reload`, `notification:show`, `tournament:completed` |

### 8.8 Services

| Service | Purpose |
|---------|---------|
| `notificationService` | System notifications with read/unread/actions, auto-dismiss, max 50; subscribes to 12+ bus events |
| `clipboardService` | Copy with history and bus integration |
| `commandPalette` | Fuzzy-matched command palette (Ctrl+K) |
| `mcpActivityFeed` | MCP SSE client with auto-reconnect (exponential backoff 3s–30s), `Last-Event-ID` tracking |

### 8.9 Stores

| Store | Purpose |
|-------|---------|
| `optimization` | Scoped forge/view results |
| `forgeSession` | IDE workspace (tabs, active tab, load requests) |
| `forgeMachine` | IDE mode state machine |
| `processScheduler` | Forge process lifecycle queue |
| `windowManager` | Window state, z-order, snap groups |
| `snapLayout` | Snap zone computation and layout presets |
| `filesystemOrchestrator` | PFFS hierarchy caching, mutations, drag validation |
| `desktopStore` | Desktop surface state |
| `projects` | Project list and navigation |
| `history` | Optimization history list |
| `stats` | Statistics data |
| `provider` | LLM provider/model/key state |
| `settings` | User preferences (accent color, wallpaper, performance profile) |
| `workspaceManager` | GitHub OAuth, workspace links, sync operations |
| `sessionContext` | Session context |
| `toast` | Toast notifications |
| `promptAnalysis` | Prompt analysis state |
| `tabCoherence` | Tab state save/restore coordination |

### 8.10 Theme

Cyberpunk flat-neon-contour design. **Zero glow effects, drop shadows, or text blooms.** Interactions rely on sharp 1px borders, vector color shifts, and micro-interactions.

- 10 neon colors: cyan, purple, green, red, yellow, orange, blue, pink, teal, indigo
- Dark backgrounds: `bg-primary` (#06060c) through `bg-glass` (rgba)
- 3-tier text hierarchy: primary, secondary, dim
- Configurable accent color, wallpaper animation mode (static/subtle/dynamic), and performance presets (Low/Balanced/High)

---

## Section 9: Security Architecture

### 9.1 Threat Model

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Unauthorized API access | High | Bearer token auth middleware |
| Prompt injection via user input | Medium | Warn-only sanitization (log + SSE warning) |
| CSRF on state-changing endpoints | Medium | Origin-based validation |
| API abuse / DoS | Medium | Per-IP sliding window rate limiting |
| XSS via API responses | Medium | Security headers (CSP, X-XSS-Protection) |
| Clickjacking | Low | X-Frame-Options: DENY |
| Accidental data destruction | Medium | Confirmation header for bulk delete |
| API key exposure in logs | High | Keys passed via headers, never logged |
| OAuth token theft | High | Fernet encryption at rest for GitHub tokens |
| Supply chain attacks | Medium | Pinned dependency versions, CI checks |

### 9.2 Middleware Stack

Ordered outermost to innermost (request flows top-down):

```
Request → GZip → SecurityHeaders → CORS → CSRF → RateLimit → Auth → Audit → Router
```

| # | Middleware | Purpose |
|---|-----------|---------|
| 1 | **GZip** | Compresses responses ≥ 4096 bytes |
| 2 | **SecurityHeaders** | 6 protective response headers (CSP, X-Frame-Options, etc.) |
| 3 | **CORS** | Explicit methods/headers with credential support |
| 4 | **CSRF** | Origin validation on POST/PUT/DELETE/PATCH; internal paths exempt |
| 5 | **RateLimit** | In-memory sliding window, per-IP (60 RPM general, 10 RPM optimize) |
| 6 | **Auth** | Optional bearer token (disabled when `AUTH_TOKEN` empty) |
| 7 | **Audit** | Logs state-changing requests (never logs keys or tokens) |

### 9.3 Authentication

- **Backend API**: Bearer token via `Authorization` header. Exempt: `/api/health`, `/api/github/callback`, `/docs`, `/internal/`
- **MCP Server**: Separate `MCPAuthMiddleware` with `MCP_AUTH_TOKEN`. Exempt: `/health`
- **MCP Webhook**: `X-Webhook-Secret` header with `INTERNAL_WEBHOOK_SECRET`

### 9.4 Secrets at Rest

- GitHub OAuth tokens: Fernet-encrypted in `GitHubConnection.access_token_encrypted`
- GitHub OAuth client secrets: Fernet-encrypted in `GitHubOAuthConfig.client_secret_encrypted`
- `ENCRYPTION_KEY` env var (auto-generated on first use if empty)
- `INTERNAL_WEBHOOK_SECRET` auto-resolved: env var → persisted file → auto-generated

### 9.5 Prompt Injection Defense

PromptForge intentionally processes arbitrary prompt text. Defense is **warn-only**:

- Strip null bytes and control characters
- Pattern-match known injection techniques (system prompt override, role hijacking)
- Log warnings server-side; emit via SSE for user visibility
- **Never block** — the user's prompt is their intent

---

## Section 10: Deployment & Configuration

### 10.1 Repository Structure

```
PromptForge/
├── backend/
│   ├── app/
│   │   ├── main.py              # App entry + middleware stack
│   │   ├── config.py            # Environment configuration
│   │   ├── constants.py         # Strategies, stage configs, enums
│   │   ├── converters.py        # ORM → Pydantic/dict transforms
│   │   ├── database.py          # SQLAlchemy async setup + migrations
│   │   ├── mcp_server.py        # FastMCP server (22 tools, 4 resources)
│   │   ├── middleware/          # Security middleware package
│   │   │   ├── auth.py          # Bearer token authentication
│   │   │   ├── rate_limit.py    # Sliding window rate limiter
│   │   │   ├── security_headers.py
│   │   │   ├── sanitize.py      # Prompt injection detection (warn-only)
│   │   │   ├── csrf.py          # Origin-based CSRF protection
│   │   │   ├── audit.py         # Request audit logging
│   │   │   └── mcp_auth.py      # MCP server bearer token auth
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── optimization.py  # Optimization (core forge record)
│   │   │   ├── project.py       # Project, Prompt, PromptVersion
│   │   │   └── workspace.py     # GitHubConnection, WorkspaceLink, GitHubOAuthConfig
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API endpoint handlers
│   │   │   ├── health.py        # Health check + provider detection
│   │   │   ├── optimize.py      # Pipeline execution + orchestration
│   │   │   ├── history.py       # History CRUD + stats
│   │   │   ├── projects.py      # Projects + prompts CRUD
│   │   │   ├── filesystem.py    # PFFS hierarchy endpoints
│   │   │   ├── providers.py     # Provider listing + key validation
│   │   │   ├── mcp_activity.py  # MCP webhook + SSE activity stream
│   │   │   └── github.py        # GitHub OAuth + workspace links
│   │   ├── repositories/        # Data access layer
│   │   │   ├── optimization.py  # Optimization queries + 10 analytics
│   │   │   ├── project.py       # Project/prompt/version queries
│   │   │   └── workspace.py     # GitHub + workspace link queries
│   │   ├── services/            # Business logic
│   │   │   ├── pipeline.py      # Pipeline orchestration (SSE generator)
│   │   │   ├── analyzer.py      # Stage 1: Analyze
│   │   │   ├── strategy_selector.py  # Stage 2: Strategy (LLM + heuristic)
│   │   │   ├── optimizer.py     # Stage 3: Optimize
│   │   │   ├── validator.py     # Stage 4: Validate
│   │   │   ├── token_budget.py  # Per-provider token tracking
│   │   │   ├── mcp_activity.py  # MCPActivityBroadcaster
│   │   │   ├── stats_cache.py   # Stats caching
│   │   │   ├── github.py        # GitHub API integration
│   │   │   └── workspace_sync.py # Workspace context extraction
│   │   ├── providers/           # LLM provider abstraction
│   │   │   ├── base.py          # LLMProvider ABC + JSON extraction
│   │   │   ├── registry.py      # ProviderRegistry with auto-detection
│   │   │   ├── errors.py        # Typed error hierarchy
│   │   │   ├── types.py         # CompletionRequest/Response/TokenUsage
│   │   │   ├── models.py        # Static model catalog
│   │   │   ├── claude_cli.py    # Claude CLI adapter
│   │   │   ├── anthropic_api.py # Anthropic API adapter
│   │   │   ├── openai_provider.py # OpenAI adapter
│   │   │   └── gemini_provider.py # Gemini adapter
│   │   ├── prompts/             # LLM system prompt templates
│   │   └── utils/               # Score normalization, helpers
│   ├── tests/                   # pytest test suite
│   ├── Dockerfile               # Production image (multi-stage)
│   └── pyproject.toml           # Dependencies + tool config
├── frontend/
│   ├── src/
│   │   ├── routes/              # SvelteKit file-based routing
│   │   └── lib/
│   │       ├── components/      # 50+ Svelte 5 components
│   │       ├── stores/          # 17 runes-based state stores
│   │       ├── services/        # 5 system services
│   │       ├── api/             # API client + SSE handling
│   │       └── utils/           # 20+ utility modules
│   ├── Dockerfile               # Production image (two-stage)
│   └── package.json             # Dependencies
├── docs/                        # Developer documentation (6 docs)
├── data/                        # SQLite database (gitignored)
├── docker-compose.yml           # Production orchestration (3 services)
├── .mcp.json                    # MCP server auto-discovery config
├── .github/workflows/ci.yml     # CI pipeline (3 jobs)
├── init.sh                      # Dev setup + service management
├── ARCHITECTURE.md              # This document
├── CLAUDE.md                    # Claude Code project instructions
├── CHANGELOG.md                 # Release history
└── README.md                    # User-facing documentation
```

### 10.2 Configuration

All configuration via environment variables with sensible defaults:

| Variable | Default | Purpose |
|----------|---------|---------|
| `FRONTEND_URL` | `http://localhost:5199` | CORS allowed origins |
| `BACKEND_PORT` | `8000` | Backend listen port |
| `HOST` | `0.0.0.0` | Backend bind address |
| `MCP_PORT` | `8001` | MCP server listen port |
| `MCP_HOST` | `127.0.0.1` | MCP server bind address |
| `BACKEND_HOST` | `127.0.0.1` | Backend address for MCP webhook (set to `backend` in Docker) |
| `DATABASE_URL` | `sqlite+aiosqlite:///.../promptforge.db` | Database connection |
| `LLM_PROVIDER` | (auto-detect) | Explicit provider selection |
| `AUTH_TOKEN` | (empty = disabled) | Backend bearer token |
| `MCP_AUTH_TOKEN` | (empty = disabled) | MCP server bearer token |
| `INTERNAL_WEBHOOK_SECRET` | (auto-resolved) | MCP → backend webhook secret |
| `RATE_LIMIT_RPM` | `60` | General rate limit (requests/min) |
| `RATE_LIMIT_OPTIMIZE_RPM` | `10` | Optimize endpoint rate limit |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API access |
| `OPENAI_API_KEY` | (empty) | OpenAI API access |
| `GEMINI_API_KEY` | (empty) | Gemini API access |
| `CLAUDE_MODEL` | `claude-opus-4-6` | Claude model selection |
| `OPENAI_MODEL` | `gpt-4.1` | OpenAI model selection |
| `GEMINI_MODEL` | `gemini-2.5-pro` | Gemini model selection |
| `GITHUB_CLIENT_ID` | (empty) | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | (empty) | GitHub OAuth App client secret |
| `GITHUB_REDIRECT_URI` | `http://localhost:8000/api/github/callback` | OAuth callback URL |
| `GITHUB_SCOPE` | `repo` | GitHub OAuth scope |
| `ENCRYPTION_KEY` | (auto-generated) | Fernet key for token encryption at rest |

### 10.3 Docker Deployment

Three-service `docker-compose.yml`:

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `backend` | `./backend/Dockerfile` | 8000 | Read-only filesystem, 4G memory limit, health check |
| `frontend` | `./frontend/Dockerfile` | 5199 | Read-only filesystem, 512M memory limit, depends on backend |
| `mcp` | `./backend/Dockerfile` | 8001 (internal) | Shares DB volume with backend, 2G memory limit |

All containers run with `no-new-privileges`, `cap_drop: ALL`, `read_only: true` (with `/tmp` tmpfs). Named volume `promptforge-data` shared between backend and MCP service.

### 10.4 CI/CD Pipeline

Three-job GitHub Actions workflow (`.github/workflows/ci.yml`):

1. **Backend**: Python 3.14 + Ruff lint + pytest
2. **Frontend**: Node 22 + svelte-check + vitest
3. **Docker**: Build both images + smoke test (health endpoint)

Triggered on push to `main` and pull requests.

---

## Appendix

### A.1 Glossary

| Term | Definition |
|------|-----------|
| **Provider** | An LLM service adapter implementing the `LLMProvider` interface |
| **Pipeline** | The 4-stage optimization flow: Analyze → Strategy → Optimize → Validate |
| **Forge** | A single prompt optimization run (verb: "to forge a prompt") |
| **SSE** | Server-Sent Events — unidirectional server-to-client streaming protocol |
| **MCP** | Model Context Protocol — standardized tool interface for Claude Code |
| **PFFS** | PromptForge FileSystem — the OS-like type system for documents and desktop entities |
| **Runes** | Svelte 5's reactivity primitives (`$state`, `$derived`, `$effect`) |
| **Gate function** | Fast boolean check used by ProviderRegistry to skip unavailable providers |
| **Context profile** | Persistent `CodebaseContext` stored on a project for grounding optimizations |
| **Workspace link** | Connection between a project and a GitHub repo (or Claude Code workspace) for auto-context |
| **Snap group** | Set of windows locked into a snap layout, moved/resized as a unit |
| **Score normalization** | Conversion between 0.0–1.0 (storage) and 1–10 (display) scales |

### A.2 Key File References

| File | Purpose |
|------|---------|
| `backend/app/providers/base.py` | LLMProvider ABC + JSON extraction + retry logic |
| `backend/app/providers/registry.py` | ProviderRegistry with auto-detection and caching |
| `backend/app/providers/errors.py` | Typed error hierarchy |
| `backend/app/providers/types.py` | CompletionRequest/Response/TokenUsage |
| `backend/app/providers/models.py` | Static model catalog |
| `backend/app/services/pipeline.py` | Pipeline orchestration (SSE generator) |
| `backend/app/services/token_budget.py` | Per-provider token tracking with daily limits |
| `backend/app/services/mcp_activity.py` | MCPActivityBroadcaster for real-time MCP event feed |
| `backend/app/services/workspace_sync.py` | Deterministic codebase context extraction |
| `backend/app/mcp_server.py` | FastMCP server (22 tools, 4 resources) |
| `backend/app/database.py` | SQLAlchemy setup, PRAGMAs, migration sequence |
| `backend/app/constants.py` | Strategies enum, stage configs, score weights |
| `backend/app/converters.py` | ORM → Pydantic/dict with score normalization |
| `frontend/src/lib/stores/windowManager.svelte.ts` | Multi-window manager with snap layouts |
| `frontend/src/lib/stores/forgeMachine.svelte.ts` | IDE mode state machine |
| `frontend/src/lib/stores/processScheduler.svelte.ts` | Forge process lifecycle queue |
| `frontend/src/lib/stores/filesystemOrchestrator.svelte.ts` | PFFS hierarchy state |
| `frontend/src/lib/services/systemBus.svelte.ts` | Decoupled inter-store event bus |
| `frontend/src/lib/services/mcpActivityFeed.svelte.ts` | MCP SSE client with auto-reconnect |
| `frontend/src/lib/utils/documentOpener.ts` | Unified document opener |
| `frontend/src/lib/utils/fileDescriptor.ts` | PFFS file type descriptors |
| `frontend/src/lib/api/client.ts` | API client + SSE consumer + header builder |
