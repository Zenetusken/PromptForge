# Contributing to Project Synthesis

Thank you for considering contributing to Project Synthesis. This document covers everything you need to get a local development environment running, understand the codebase, and submit high-quality contributions.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## Ways to Contribute

- **Bug reports** — open an issue using the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Feature requests** — open an issue using the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- **Documentation improvements** — fix typos, clarify sections, add examples
- **Code contributions** — fix bugs, implement features, improve performance

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.14+ | Backend runtime |
| Node.js | 24+ | Frontend runtime |
| Redis | 7+ | Caching and rate limiting (optional — in-memory fallback available) |
| `claude` CLI | latest | LLM provider via Max subscription (alternative: `ANTHROPIC_API_KEY`) |

## Development Setup

### Quick start (recommended)

```bash
git clone https://github.com/project-synthesis/ProjectSynthesis.git
cd ProjectSynthesis
./init.sh
```

`init.sh` handles everything automatically:
- Creates a Python 3.14 venv at `backend/.venv` and installs dependencies
- Installs frontend npm packages
- Copies `.env.example` to `.env` if not present
- Starts backend (port 8000), frontend (port 5199), and MCP server (port 8001)
- Backend runs with `--reload` — edit Python files and changes take effect immediately

### Managing services

```bash
./init.sh              # start all services (runs setup on first use)
./init.sh restart      # stop + start (required after changing site-packages)
./init.sh stop         # stop all services
./init.sh status       # check what's running
./init.sh seed         # populate example optimizations
./init.sh mcp          # restart only the MCP server
```

Logs are written to `data/backend.log`, `data/frontend.log`, and `data/mcp.log`.

### Manual setup (if you prefer)

```bash
# Backend
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# MCP server (separate terminal)
cd backend
source .venv/bin/activate
python -m app.mcp_server
```

### Environment configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**LLM provider** (at least one required):
- **Claude Max** (preferred) — install the `claude` CLI and run `claude login`. The app auto-detects it at startup. Zero API cost.
- **Anthropic API** — set `ANTHROPIC_API_KEY=sk-ant-...` in `.env`

**GitHub App** (required for authentication):
- Create a GitHub App at `https://github.com/settings/apps/new`
- Callback URL: `http://localhost:8000/auth/github/callback`
- Set `GITHUB_APP_CLIENT_ID` and `GITHUB_APP_CLIENT_SECRET` in `.env`

**Redis** (optional):
- If Redis is running locally on port 6379, the app connects automatically
- Without Redis, rate limiting and caching use in-memory fallbacks — fully functional for development

**Auto-generated secrets**: `SECRET_KEY`, `JWT_SECRET`, and `JWT_REFRESH_SECRET` are auto-generated on first startup and persisted to `data/.app_secrets`. No manual configuration needed for local dev.

## Architecture Overview

See [CLAUDE.md](CLAUDE.md) for the full architecture reference. Key points for contributors:

### Service layout

| Service | Port | Entry point | Hot reload |
|---------|------|-------------|------------|
| FastAPI backend | 8000 | `backend/app/main.py` | Yes (`--reload`) |
| SvelteKit frontend | 5199 | `frontend/src/` | Yes (Vite HMR) |
| MCP server | 8001 | `backend/app/mcp_server.py` | No (restart via `./init.sh mcp`) |

### Backend structure

```
backend/app/
├── routers/        # HTTP endpoints (thin — delegate to services)
├── services/       # Business logic
├── providers/      # LLM provider abstraction (Claude CLI, Anthropic API)
├── models/         # SQLAlchemy models
├── schemas/        # Pydantic request/response schemas
├── dependencies/   # FastAPI dependencies (auth, rate limiting)
└── utils/          # Shared utilities (JWT, etc.)
```

**Layer rule**: `routers/` → `services/` → `models/` only. Services must never import from routers.

### Frontend structure

```
frontend/src/lib/
├── components/
│   ├── layout/     # Navigator, Inspector, StatusBar, EditorGroups
│   ├── editor/     # PromptEdit, ForgeArtifact, PromptPipeline
│   ├── pipeline/   # StageCard, StageAnalyze, StageExplore, StageOptimize
│   ├── github/     # RepoBadge, RepoPickerModal
│   └── shared/     # CommandPalette, DiffView, ToastContainer
├── stores/         # Svelte 5 rune stores (forge, editor, github, workbench)
└── api/            # Backend API client
```

**Design system**: Industrial cyberpunk, flat neon contour — no rounded corners, no drop shadows.

## Running Tests

```bash
# All backend tests
cd backend && source .venv/bin/activate && pytest

# Single test file
pytest tests/test_auth_wiring.py

# With verbose output
pytest -v --tb=short

# Frontend type-check
cd frontend && npx tsc --noEmit

# Frontend Svelte check
cd frontend && npx svelte-check --tsconfig ./tsconfig.json --threshold error
```

## Linting

```bash
# Python — ruff (lint + format check)
cd backend && source .venv/bin/activate
ruff check app/ tests/

# Auto-fix
ruff check --fix app/ tests/
```

All checks must pass before submitting a PR. CI runs `pytest`, `ruff check`, `tsc --noEmit`, and `svelte-check` automatically.

## Branch Naming

| Prefix | Use for |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring without behaviour change |
| `test/` | Tests only |
| `chore/` | Dependency bumps, CI config, tooling |

## Pull Request Process

1. **Open an issue first** for significant changes so we can discuss approach before you invest time coding.
2. **Keep PRs focused** — one logical change per PR. If you find a separate bug while working, open a separate PR.
3. **Write tests** — backend contributions should include pytest coverage; aim to keep coverage above 90%.
4. **Update documentation** — if your change affects the API, MCP tools, or configuration, update `docs/` and `CLAUDE.md`.
5. **Pass all checks** — `pytest`, `ruff`, and `tsc --noEmit` must all pass before requesting review.
6. **Sign-off** — all commits must be signed off as per the [Developer Certificate of Origin (DCO)](https://developercertificate.org/). Add `Signed-off-by: Your Name <email>` to each commit or use `git commit -s`.

## Code Style

- **Python**: [Ruff](https://docs.astral.sh/ruff/) for linting and formatting (line length 100)
- **TypeScript/Svelte**: Prettier defaults + strict TypeScript
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) format (`feat:`, `fix:`, `docs:`, etc.)

## Reporting Security Vulnerabilities

Do **not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
