# Backend Database

SQLAlchemy 2.0 async ORM with SQLite (aiosqlite). Engine, session factory, migrations, and startup hooks live in `backend/app/database.py`.

## SQLite PRAGMAs

Set per connection via `@event.listens_for(engine.sync_engine, "connect")`:

| PRAGMA | Value | Why |
|--------|-------|-----|
| `foreign_keys` | `ON` | Enforce referential integrity |
| `journal_mode` | `WAL` | Write-ahead logging — eliminates reader/writer blocking during SSE streaming |
| `synchronous` | `NORMAL` | Safe with WAL, reduces fsync calls |
| `cache_size` | `-65536` | 64 MB in-memory page cache |
| `mmap_size` | `268435456` | 256 MB memory-mapped I/O |
| `temp_store` | `MEMORY` | Temporary tables in memory |
| `busy_timeout` | `5000` | 5 s retry on lock contention (prevents `SQLITE_BUSY` during concurrent SSE writes) |

Tests use `:memory:` SQLite — PRAGMAs are applied but most are no-ops there.

## Startup Sequence

`init_db()` runs on app startup (via lifespan handler in `main.py`):

1. **`create_all`** — creates tables from ORM models
2. **`run_kernel_migrations`** — applies kernel table migrations (settings, storage, VFS, audit)
3. **Per-app migrations** — each app's `run_migrations()` runs (e.g. PromptForge's column-add, index, and data migrations in `apps/promptforge/database.py`)
4. **`_harden_data_dir`** — restricts filesystem permissions on the data directory and database file (owner-only access). Logs a warning on `OSError` (e.g., non-owner process).

All steps are idempotent — safe to run on every restart.

PromptForge-specific migrations (in `apps/promptforge/database.py`): `run_migrations` (27 column/index migrations), `migrate_legacy_strategies`, `migrate_legacy_projects`, `backfill_missing_prompts`, `backfill_prompt_ids`, `cleanup_stale_running`.

## Migration List

27 migrations in `_MIGRATIONS` covering:

- Column additions: `strategy_reasoning`, `input_tokens`, `output_tokens`, `strategy_confidence`, `prompt_id`, `strategy`, `secondary_frameworks`, `version`, `context_profile`, `codebase_context_snapshot`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `conciseness_score`, `detected_patterns`, `retry_of`, `framework_adherence_score`
- Table creation: `projects`, `prompts`, `prompt_versions`
- Indexes: 13 single/composite indexes on `optimizations`, `projects`, `prompts`, `prompt_versions`

New databases get indexes at CREATE TABLE time; migrations apply them for pre-existing databases.

## Models

| Table | File | Key Fields |
|-------|------|------------|
| `optimizations` | `apps/promptforge/models/optimization.py` | `raw_prompt`, `optimized_prompt`, `status`, `overall_score`, `conciseness_score`, `framework_adherence_score`, `detected_patterns` (JSON list), `strategy`, `project`, `prompt_id` FK, `retry_of`, `codebase_context_snapshot` |
| `projects` | `apps/promptforge/models/project.py` | `name` (unique), `status` (active/archived/deleted), `context_profile` (JSON text) |
| `prompts` | `apps/promptforge/models/project.py` | `content`, `version`, `project_id` FK, `order_index` |
| `prompt_versions` | `apps/promptforge/models/project.py` | `prompt_id` FK, `version`, `content`, `optimization_id` FK (immutable snapshots) |
| `github_connections` | `apps/promptforge/models/workspace.py` | `github_user_id`, `github_username`, `access_token_encrypted`, `avatar_url`, `scopes`, `token_valid` |
| `github_oauth_config` | `apps/promptforge/models/workspace.py` | `client_id`, `client_secret_encrypted`, `redirect_uri`, `scope` (single-row table) |
| `workspace_links` | `apps/promptforge/models/workspace.py` | `project_id` FK, `github_connection_id` FK, `repo_full_name`, `repo_url`, `default_branch`, `sync_status`, `workspace_context` (JSON), `file_tree_snapshot` (JSON) |

## Repositories

| Repository | File | Scope |
|------------|------|-------|
| `OptimizationRepository` | `apps/promptforge/repositories/optimization.py` | All optimization queries: CRUD, list with filters/pagination/sorting, stats (10+ analytics), tag management |
| `ProjectRepository` | `apps/promptforge/repositories/project.py` | Project/prompt CRUD, prompt versioning, cascade deletion, context profiles |
| `WorkspaceRepository` | `apps/promptforge/repositories/workspace.py` | GitHub connections CRUD, OAuth config, workspace links, sync status, context resolution (3-layer merge: workspace → project → request), health summary |

Standalone helpers: `ensure_project_by_name()` (returns `ProjectInfo(id, status)` — avoids redundant follow-up query for archive checks), `ensure_prompt_in_project()` (3-tier matching: exact → SQL fuzzy → Python fallback with LIMIT 100).

## Kernel Tables

Tables owned by the OS kernel (`backend/kernel/`), created via `run_kernel_migrations()` in `kernel/database.py`. All use `CREATE TABLE IF NOT EXISTS` for idempotency. Migrations run before app-specific migrations in `init_db()`.

| Table | File | Key Fields |
|-------|------|------------|
| `app_settings` | `kernel/models/app_settings.py` | `id`, `app_id`, `key`, `value` (JSON text), `created_at`, `updated_at`. `UNIQUE(app_id, key)` |
| `app_collections` | `kernel/models/app_document.py` | `id`, `app_id`, `name`, `parent_id` (self-FK, `CASCADE`). `UNIQUE(app_id, name, parent_id)` |
| `app_documents` | `kernel/models/app_document.py` | `id`, `app_id`, `collection_id` FK (`CASCADE`), `name`, `content_type`, `content`, `metadata_json`, `created_at`, `updated_at`. Index on `(app_id, collection_id)` |
| `vfs_folders` | `kernel/models/vfs.py` | `id`, `app_id`, `name`, `parent_id` (self-FK, `CASCADE`), `depth`, `metadata_json`, `created_at`, `updated_at`. `UNIQUE(app_id, name, parent_id)` |
| `vfs_files` | `kernel/models/vfs.py` | `id`, `app_id`, `folder_id` FK (`SET NULL`), `name`, `content`, `content_type`, `version`, `metadata_json`, `created_at`, `updated_at`. Index on `(app_id, folder_id)` |
| `vfs_file_versions` | `kernel/models/vfs.py` | `id`, `file_id` FK (`CASCADE`), `version`, `content`, `change_source`, `created_at`. Auto-created on content changes. |
| `audit_log` | `kernel/models/audit.py` | `id`, `app_id`, `action`, `resource_type`, `resource_id`, `details_json`, `timestamp`. Index on `(app_id, timestamp)` |
| `app_usage` | `kernel/models/audit.py` | `id`, `app_id`, `resource`, `period` (hourly), `count`, `updated_at`. `UNIQUE(app_id, resource, period)` |

### Kernel Repositories

| Repository | File | Scope |
|------------|------|-------|
| `AppSettingsRepository` | `kernel/repositories/app_settings.py` | Per-app key-value settings: `get_all`, `get`, `set` (upsert), `set_all`, `delete`, `reset`. JSON serialization for values. |
| `AppStorageRepository` | `kernel/repositories/app_storage.py` | Per-app document store: collections CRUD (`list_collections`, `create_collection`, `delete_collection`), documents CRUD (`list_documents`, `get_document`, `create_document`, `update_document`, `delete_document`). Scoped by `app_id`. |
| `VfsRepository` | `kernel/repositories/vfs.py` | Virtual filesystem: folder CRUD with depth validation (max 8), file CRUD with auto-versioning, breadcrumb path traversal, file search by name. Scoped by `app_id`. |
| `AuditRepository` | `kernel/repositories/audit.py` | Audit log: `log_action`, `list_logs`, `count_logs`. Usage tracking: `get_usage`, `increment_usage`, `get_all_usage`. Hourly period-based quota tracking. |

### Kernel REST Endpoints

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| `kernel/routers/settings.py` | `/api/kernel/settings/{app_id}` | `GET` (all settings), `PUT` (merge settings), `DELETE` (reset all) |
| `kernel/routers/storage.py` | `/api/kernel/storage/{app_id}` | Collections: `GET/POST .../collections`, `DELETE .../collections/{id}`. Documents: `GET/POST .../documents`, `GET/PUT/DELETE .../documents/{id}` |
| `kernel/routers/apps.py` | `/api/kernel/apps` | `GET` (list apps with `services_satisfied`), `GET .../{id}` (app details + manifest) |
| `kernel/routers/vfs.py` | `/api/kernel/vfs/{app_id}` | Children: `GET .../children`. Folders: `POST/GET/DELETE .../folders/{id}`, `GET .../folders/{id}/path`. Files: `POST/GET/PUT/DELETE .../files/{id}`, `GET .../files/{id}/versions`. Search: `GET .../search?q=` |
| `kernel/routers/audit.py` | `/api/kernel/audit` | `GET /{app_id}` (audit logs with pagination), `GET /usage/{app_id}` (current quota usage) |
| `kernel/routers/bus.py` | `/api/kernel/bus` | `GET /contracts` (registered event contracts), `GET /subscriptions` (active subscriptions), `GET /events` (SSE stream) |

All kernel routers are aggregated into `kernel_router` in `kernel/routers/__init__.py` and mounted once in `main.py`.

## Session Management

Two FastAPI dependencies:

- **`get_db()`** — yields `AsyncSession`, auto-commits on success, rolls back on exception. Used by mutation endpoints (POST/PUT/DELETE).
- **`get_db_readonly()`** — yields `AsyncSession`, skips commit/rollback (read-only). Used by GET/HEAD endpoints to avoid unnecessary identity-map flush.

MCP server uses its own `_repo_session()` context manager with `async_session_factory`.
