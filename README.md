# PromptForge — AI-Powered Prompt Optimization Workbench

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Node.js 22](https://img.shields.io/badge/Node.js-22-green?logo=node.js&logoColor=white)](https://nodejs.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker&logoColor=white)](https://www.docker.com/)

Submit a raw prompt, get it rewritten and scored through a 4-stage AI pipeline (Analyze, Strategy, Optimize, Validate). Provider-agnostic — works with Claude (MAX subscription or API), OpenAI, and Google Gemini. Includes an MCP server for Claude Code integration and a GitHub-connected Workspace Hub for automatic codebase context extraction.

<!-- ![PromptForge screenshot](docs/screenshot.png) -->

## Features

- **4-stage optimization pipeline** — Analyze, Strategy, Optimize, Validate — streamed in real time via SSE
- **10 optimization strategies** — chain-of-thought, co-star, risen, few-shot-scaffolding, and more; LLM-selected with heuristic fallback or manual override
- **5-dimension scoring** — clarity, specificity, structure, faithfulness, conciseness (weighted, 1–10 scale) with calibrated rubric
- **Provider-agnostic** — Claude CLI, Anthropic API, OpenAI, Google Gemini with auto-detection
- **Project management** — hierarchical folders (PFFS), prompt version history, forge-result linking, codebase context profiles
- **Workspace Hub** — GitHub OAuth repo linking for automatic context extraction; three-layer context merge; also supports Claude Code push via MCP
- **MCP server** — 22 tools and 4 resources for Claude Code integration, with real-time activity tracking in the frontend
- **OS-metaphor UI** — multi-window desktop with snap layouts, IDE workspace, file manager, process scheduler, network monitor, strategy workshop, batch processor, terminal, and more
- **Security** — bearer-token auth, authenticated webhooks, rate limiting, CSRF protection, security headers, encrypted token storage, hardened Docker containers
- **Docker-ready** — multi-stage builds, healthchecks, non-root containers, read-only filesystems, compose orchestration

## Quick Start

### Prerequisites

- Python 3.14+
- Node.js 22+
- An LLM provider: Claude MAX subscription (zero-config default), or an API key for Anthropic / OpenAI / Gemini

### Local Development

```bash
chmod +x init.sh
./init.sh
```

This installs all dependencies, creates the SQLite database, and starts:
- Backend on http://localhost:8000
- Frontend on http://localhost:5199
- MCP server on http://localhost:8001

### Docker

```bash
docker compose up -d

# With authentication
AUTH_TOKEN=your-secret-token docker compose up -d

# With a specific LLM provider
ANTHROPIC_API_KEY=sk-... docker compose up -d
```

## Pipeline

Each optimization runs through four LLM-powered stages:

1. **Analyze** — Classify task type, complexity, weaknesses, and strengths
2. **Strategy** — Select from 10 optimization frameworks; LLM-based with heuristic fallback
3. **Optimize** — Rewrite the prompt using the selected strategy, optionally grounded in codebase context
4. **Validate** — Score on 5 dimensions (clarity, specificity, structure, faithfulness, conciseness) and generate a verdict

Results stream as named SSE events. Supports iterative refinement (re-runs Optimize + Validate until a score threshold is met) and comparative evaluation (retry chains with score deltas).

### Codebase Context

Optimizations can be grounded in real project context via a three-layer merge:

1. **Workspace auto-context** (lowest priority) — extracted from linked GitHub repos or pushed via Claude Code
2. **Project context profile** (manual) — set via UI or `set_project_context` MCP tool
3. **Per-request context** (highest priority) — passed in API/MCP calls

The resolved context is snapshotted on every optimization for reproducibility.

## Development

### `init.sh` Commands

| Command | Description |
|---------|-------------|
| `./init.sh` | Install dependencies and start all services (dev mode) |
| `./init.sh build` | Build frontend and start with pre-built assets (no hot-reload) |
| `./init.sh stop` | Stop all running services |
| `./init.sh restart` | Stop then start dev mode (no reinstall) |
| `./init.sh restart-build` | Stop then start built mode (requires prior `build`) |
| `./init.sh status` | Show running/stopped state and health details |
| `./init.sh test` | Run backend (pytest) + frontend (vitest + svelte-check) tests |
| `./init.sh seed` | Populate example optimization data |
| `./init.sh mcp` | Print MCP server config snippet for Claude Code |

### Running Tests

```bash
./init.sh test              # All tests
cd backend && pytest        # Backend only
cd frontend && npm run test # Frontend only
```

## API & MCP

### API

Interactive docs available when the backend is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### MCP Server

22 tools and 4 resources for Claude Code integration over SSE transport (port 8001):

```bash
./init.sh mcp  # Print config snippet for Claude Code
```

**Tools:** `optimize`, `retry`, `get`, `list`, `get_by_project`, `search`, `tag`, `stats`, `delete`, `bulk_delete`, `list_projects`, `get_project`, `strategies`, `create_project`, `add_prompt`, `update_prompt`, `set_project_context`, `batch`, `cancel`, `sync_workspace`, `get_children`, `move`

**Resources:** `promptforge://projects`, `promptforge://projects/{id}/context`, `promptforge://optimizations/{id}`, `promptforge://workspaces`

All tool calls emit activity events for real-time visibility in the frontend Network Monitor. Set `MCP_AUTH_TOKEN` to require bearer token authentication.

## Configuration

Key environment variables (see [`.env.example`](.env.example) for the full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | *(auto-detect)* | `claude-cli`, `anthropic`, `openai`, or `gemini` |
| `ANTHROPIC_API_KEY` | | Anthropic API key |
| `OPENAI_API_KEY` | | OpenAI API key |
| `GEMINI_API_KEY` | | Google Gemini API key |
| `AUTH_TOKEN` | *(disabled)* | Bearer token for API authentication |
| `MCP_AUTH_TOKEN` | *(disabled)* | Bearer token for MCP server authentication |
| `GITHUB_CLIENT_ID` | | GitHub OAuth App client ID (for Workspace Hub) |
| `GITHUB_CLIENT_SECRET` | | GitHub OAuth App client secret |
| `ENCRYPTION_KEY` | *(auto-generated)* | Symmetric key for token encryption at rest |

Ports: backend `8000` (`BACKEND_PORT`), frontend `5199` (`FRONTEND_URL`), MCP `8001` (`MCP_PORT`). Full configuration reference in [ARCHITECTURE.md](ARCHITECTURE.md#section-10-deployment--configuration).

## Further Reading

| Document | Contents |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System overview, pipeline, data layer, MCP server, codebase context, frontend architecture, security, deployment |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, coding guidelines, how to add new LLM providers |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [API.md](API.md) | Standalone API reference |

## License

Apache 2.0 — see [LICENSE](LICENSE).
