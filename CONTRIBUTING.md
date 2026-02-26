# Contributing to PromptForge

Thank you for your interest in contributing to PromptForge! This guide covers setup, conventions, and extension points.

## Development Setup

### Prerequisites

- Python 3.14+
- Node.js 22+
- Git

### Quick Start

```bash
git clone <repo-url>
cd PromptForge
chmod +x init.sh
./init.sh
```

This installs all dependencies and starts backend (port 8000), frontend (port 5199), and MCP server (port 8001). See `./init.sh help` for subcommands: `stop`, `restart`, `status`, `test`, `seed`, `mcp`.

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -e ".[test,all-providers]"
python -m uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up     # builds and starts all services
docker compose down   # stops and removes containers
```

Configure via `.env` file (see `.env.example`). Services start in dependency order: backend -> MCP + frontend.

### Environment

Copy `.env.example` to `.env`. All settings have sensible defaults. Key variables:

- `LLM_PROVIDER` — leave empty for auto-detection (Claude CLI -> Anthropic -> OpenAI -> Gemini)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` — set to enable the corresponding provider
- `AUTH_TOKEN` — API authentication (empty = disabled)
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` — GitHub OAuth for Workspace Hub (optional)

See `backend/app/config.py` for the full list.

## Project Structure

```
backend/
  app/
    config.py          # Environment variables and defaults
    main.py            # FastAPI app, middleware stack, lifespan
    database.py        # SQLAlchemy engine, migrations, startup hooks
    mcp_server.py      # FastMCP server (20 tools, 4 resources)
    constants.py       # Strategy names, stage configs, aliases
    converters.py      # ORM -> Pydantic/dict transformation
    models/            # SQLAlchemy ORM models
    schemas/           # Pydantic v2 request/response schemas
    repositories/      # Data access layer (query logic)
    services/          # Business logic (pipeline, stats, workspace sync)
    routers/           # API endpoint definitions
    providers/         # LLM provider abstraction
    middleware/        # Auth, CSRF, rate limiting, security headers, audit
    utils/             # Score normalization, helpers
  tests/               # pytest (async), one file per module
frontend/
  src/
    lib/
      api/             # API client (fetch + SSE)
      stores/          # Svelte 5 runes state management
      services/        # System bus, notifications, clipboard, MCP feed
      components/      # 60+ Svelte components
      utils/           # Colors, strategies, formatting, templates
    routes/            # SvelteKit routes (/, /github/callback)
```

## Running Tests

```bash
# All tests
./init.sh test

# Backend only
cd backend && source venv/bin/activate && pytest -v

# Frontend only
cd frontend && npm run test && npm run check
```

### Backend Testing Patterns

- **Fixtures** (`tests/conftest.py`): `db_engine` (in-memory SQLite), `db_session`, `client` (httpx AsyncClient with FastAPI dep override)
- **Mocking LLM calls**: Create a `FakeProvider(LLMProvider)` returning canned responses; patch `get_provider` where needed
- **DB tests**: Use `db_session` fixture; write `_seed()` helpers for test data factories
- **Cache clearing**: Use `@pytest.fixture(autouse=True)` calling `invalidate_detect_cache()` in provider tests
- **No external calls**: All tests run offline — LLM providers are mocked, DB is in-memory

### Frontend Testing Patterns

- **Co-located tests**: `{module}.test.ts` next to the source file
- **Component tests**: `@testing-library/svelte` (`render`, `screen`, `fireEvent`)
- **Store tests**: Import the store, set state in `beforeEach`, assert reactive properties
- **Browser APIs**: Stub `sessionStorage`/`localStorage` with in-memory objects

## Code Style

- **Python**: Ruff (E/F/I/W rules), line length 100, target Python 3.14. Run `ruff check .` from `backend/`.
- **TypeScript**: Strict mode, checked via `npm run check` (svelte-check)
- **Svelte**: Svelte 5 runes (`$state`, `$derived`, `$effect`). No legacy `$:` reactive statements.
- **Frontend theme**: Flat neon contour — no glow effects, no drop shadows, no text blooms. Sharp 1px borders, vector color shifts. See `CLAUDE.md` for the full palette.

## Making Changes

1. **Fork** the repository and create a feature branch from `main`
2. **Write tests** for new functionality
3. **Follow existing patterns** — check nearby code for conventions
4. **Keep commits focused** — one logical change per commit
5. **Run the full test suite** before submitting
6. **Update documentation** when changing code covered by the docs listed below

### Documentation Sync Requirements

These docs **must be kept in sync** when you change the corresponding code:

| Doc | Update when changing... |
|-----|------------------------|
| `CLAUDE.md` | Config vars, API endpoints, architecture, MCP tools |
| `docs/frontend-internals.md` | Stores, shared utilities, key components, routes |
| `docs/frontend-components.md` | Adding/removing/renaming components, changing props or store deps |
| `docs/backend-middleware.md` | Middleware add/remove/reorder, config values |
| `docs/backend-database.md` | Schema changes, new migrations, startup hooks |
| `docs/backend-caching.md` | Cache TTLs, new invalidation points |

## Extension Points

### Adding an LLM Provider

1. **Create** `backend/app/providers/your_provider.py` implementing the `LLMProvider` abstract base class (see `base.py` for the interface: `send_message`, `send_message_json`, `is_available`, `count_tokens`, `stream`)
2. **Register** in `backend/app/providers/__init__.py`:
   ```python
   _registry.register(
       "your-provider",                       # name (used in LLM_PROVIDER env var)
       "app.providers.your_provider",          # module path (lazy import)
       "YourProvider",                         # class name
       gate=lambda: bool(os.getenv("YOUR_API_KEY")),  # fast availability check
   )
   ```
3. **Add models** to `backend/app/providers/models.py` — define `ModelInfo` entries and add them to `MODEL_CATALOG["your-provider"]` and `REQUIRES_API_KEY`
4. **Add optional dependency** to `backend/pyproject.toml` under `[project.optional-dependencies]` and include it in `all-providers`
5. **Add config** to `backend/app/config.py` — env var for API key and default model
6. **Write tests** in `backend/tests/test_providers_your_provider.py` — see `test_providers_openai.py` for the pattern (mock SDK client via `patch.dict(sys.modules, ...)`)

### Adding an MCP Tool

MCP tools live in `backend/app/mcp_server.py`. Each tool is a decorated async function:

```python
@mcp.tool()
@_mcp_tracked("your_tool")     # emits activity events to the frontend
async def promptforge_your_tool(param: str) -> dict:
    """Tool description shown to Claude Code."""
    async with get_db_context() as session:
        # ... business logic using repositories ...
        return {"result": "..."}
```

Checklist:
- Prefix the function name with `promptforge_`
- Wrap with `@_mcp_tracked("your_tool")` for activity feed visibility
- Use `get_db_context()` for database access
- Add to `MCP_WRITE_TOOLS` in `frontend/src/lib/services/mcpActivityFeed.svelte.ts` if the tool mutates data (triggers history/stats reload + notifications)
- Update the tool count in `CLAUDE.md`

### Adding a Database Column

PromptForge uses a migration-on-startup pattern (no Alembic):

1. **Add the column** to the SQLAlchemy model in `backend/app/models/`
2. **Add a migration** to the `_MIGRATIONS` list in `backend/app/database.py`:
   ```python
   "ALTER TABLE your_table ADD COLUMN your_column TYPE",
   ```
   Migrations are idempotent — `_run_migrations()` catches `OperationalError` for already-applied statements.
3. **Update** `docs/backend-database.md` with the new column

### Adding a Frontend Window

The frontend follows an OS metaphor (windows, taskbar, start menu):

1. **Create** `frontend/src/lib/components/YourWindow.svelte`
2. **Register** a window ID in `windowManager.svelte.ts` — add to `PERSISTENT_WINDOW_IDS` if it should survive route changes
3. **Add** a desktop icon, start menu entry, and/or command palette command
4. **Update** `docs/frontend-components.md`

## Pull Requests

- Describe what changed and why
- Reference any related issues
- Ensure all tests pass (`./init.sh test`)
- Keep PRs focused — large changes should be split into smaller PRs

## Reporting Issues

- Use GitHub Issues
- Include steps to reproduce
- Include error messages and logs
- Specify your Python/Node versions and OS

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
