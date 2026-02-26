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
2. **`_run_migrations`** — applies column-add and index migrations (skips already-applied via `IF NOT EXISTS` / `OperationalError` catch)
3. **`_migrate_legacy_strategies`** — normalizes strategy names via `LEGACY_STRATEGY_ALIASES`
4. **`_migrate_legacy_projects`** — seeds `projects` table from legacy `optimization.project` strings, imports unique `raw_prompt` values as `Prompt` entries
5. **`_backfill_missing_prompts`** — creates `Prompt` records for orphaned optimizations (prompt_id IS NULL)
6. **`_backfill_prompt_ids`** — links optimizations to prompts by matching content within same project
7. **`_cleanup_stale_running`** — marks RUNNING records >30 min old as ERROR

8. **`_harden_data_dir`** — sets `0o700` on the `data/` directory and `0o600` on the database file (owner-only access). Logs a warning on `OSError` (e.g., non-owner process).

All steps are idempotent — safe to run on every restart.

## Migration List

24 migrations in `_MIGRATIONS` covering:

- Column additions: `strategy_reasoning`, `input_tokens`, `output_tokens`, `strategy_confidence`, `prompt_id`, `strategy`, `secondary_frameworks`, `version`, `context_profile`, `codebase_context_snapshot`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- Table creation: `projects`, `prompts`, `prompt_versions`
- Indexes: 13 single/composite indexes on `optimizations`, `projects`, `prompts`, `prompt_versions`

New databases get indexes at CREATE TABLE time; migrations apply them for pre-existing databases.

## Models

| Table | File | Key Fields |
|-------|------|------------|
| `optimizations` | `models/optimization.py` | `raw_prompt`, `optimized_prompt`, `status`, `overall_score`, `strategy`, `project`, `prompt_id` FK, `codebase_context_snapshot` |
| `projects` | `models/project.py` | `name` (unique), `status` (active/archived/deleted), `context_profile` (JSON text) |
| `prompts` | `models/project.py` | `content`, `version`, `project_id` FK, `order_index` |
| `prompt_versions` | `models/project.py` | `prompt_id` FK, `version`, `content`, `optimization_id` FK (immutable snapshots) |

## Repositories

| Repository | File | Scope |
|------------|------|-------|
| `OptimizationRepository` | `repositories/optimization.py` | All optimization queries: CRUD, list with filters/pagination/sorting, stats (10+ analytics), tag management |
| `ProjectRepository` | `repositories/project.py` | Project/prompt CRUD, prompt versioning, cascade deletion, context profiles |

Standalone helpers: `ensure_project_by_name()` (returns `ProjectInfo(id, status)` — avoids redundant follow-up query for archive checks), `ensure_prompt_in_project()` (3-tier matching: exact → SQL fuzzy → Python fallback with LIMIT 100).

## Session Management

Two FastAPI dependencies:

- **`get_db()`** — yields `AsyncSession`, auto-commits on success, rolls back on exception. Used by mutation endpoints (POST/PUT/DELETE).
- **`get_db_readonly()`** — yields `AsyncSession`, skips commit/rollback (read-only). Used by GET/HEAD endpoints to avoid unnecessary identity-map flush.

MCP server uses its own `_repo_session()` context manager with `async_session_factory`.
