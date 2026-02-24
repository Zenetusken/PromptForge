# PromptForge — Intelligent Prompt Optimization Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Node.js 22](https://img.shields.io/badge/Node.js-22-green?logo=node.js&logoColor=white)](https://nodejs.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker&logoColor=white)](https://www.docker.com/)

A self-adaptive prompt optimization web app that transforms raw, unstructured prompts into properly structured, improved, and optimized versions using a 4-stage AI pipeline. Provider-agnostic — works with Claude (MAX subscription or API), OpenAI, and Google Gemini.

<!-- ![PromptForge screenshot](docs/screenshot.png) -->

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Pipeline](#pipeline)
- [Development](#development)
- [API Reference](#api-reference)
- [MCP Integration](#mcp-integration)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

## Features

- **4-stage optimization pipeline** — Analyze, Strategy, Optimize, Validate — streamed to the browser in real time via SSE
- **Provider-agnostic** — Claude CLI, Anthropic API, OpenAI, and Google Gemini with auto-detection
- **Project management** — organize prompts into projects with full version history and forge-result linking
- **MCP server** — 17 tools for Claude Code integration (`optimize`, `retry`, `search`, `set_project_context`, etc.)
- **Security stack** — optional bearer-token auth, per-endpoint rate limiting, CSRF protection, security headers, input sanitization, and audit logging
- **Docker-ready** — multi-stage builds, healthchecks, non-root containers, and compose orchestration

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

### Docker

```bash
# Basic
docker compose up -d

# With authentication
AUTH_TOKEN=your-secret-token docker compose up -d

# With a specific LLM provider
ANTHROPIC_API_KEY=sk-... docker compose up -d
OPENAI_API_KEY=sk-... LLM_PROVIDER=openai docker compose up -d
```

## Pipeline

Each optimization runs through four LLM-powered stages:

1. **Analyze** — Classify the prompt's task type, complexity, weaknesses, and strengths
2. **Strategy** — Select an optimization strategy: chain-of-thought, few-shot, role-based, constraint-focused, or structured-enhancement. LLM-based selection with heuristic fallback; users can override via the UI
3. **Optimize** — Rewrite the prompt using the selected strategy
4. **Validate** — Score the result on four dimensions (clarity, specificity, structure, faithfulness) on a 1–10 scale and generate a verdict

Results stream to the frontend as named SSE events (`stage`, `analysis`, `strategy`, `optimization`, `validation`, `complete`).

## Development

### `init.sh` Commands

| Command | Description |
|---------|-------------|
| `./init.sh` | Install dependencies and start all services (default) |
| `./init.sh stop` | Stop all running services |
| `./init.sh restart` | Stop then start (no reinstall) |
| `./init.sh status` | Show running/stopped state and health details |
| `./init.sh test` | Install test extras, run backend + frontend tests |
| `./init.sh seed` | Populate example optimization data |
| `./init.sh mcp` | Print MCP server config snippet for Claude Code |
| `./init.sh help` | Show usage message |

### Running Servers Individually

```bash
# Backend (port 8000)
cd backend && source venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000

# Frontend (port 5199)
cd frontend && npm run dev
```

### Running Tests

```bash
# All tests
./init.sh test

# Backend only
cd backend && source venv/bin/activate && pytest

# Frontend only
cd frontend && npm run test && npm run check
```

### Tech Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy 2.0 async / SQLite (aiosqlite) / Pydantic v2
- **Frontend**: SvelteKit 2 (Svelte 5 runes) / Tailwind CSS 4 / TypeScript / Vite 6
- **LLM Providers**: Claude CLI (MAX subscription), Anthropic API, OpenAI, Google Gemini
- **Streaming**: Server-Sent Events (SSE)
- **MCP Server**: FastMCP for Claude Code integration

## API Reference

Interactive API documentation is available when the backend is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

For the full endpoint reference (25 endpoints across optimize, history, projects, prompts, providers, and health), see [API.md](API.md).

## MCP Integration

PromptForge exposes its engine as an MCP server for Claude Code integration:

```bash
# Print the config snippet to paste into your Claude Code MCP settings
./init.sh mcp

# Or run the server directly
cd backend && python -m app.mcp_server
```

**Available tools:** `optimize`, `retry`, `get`, `list`, `get_by_project`, `search`, `tag`, `stats`, `delete`, `bulk_delete`, `list_projects`, `get_project`, `strategies`, `create_project`, `add_prompt`, `update_prompt`, `set_project_context`

## Configuration

Key environment variables (set in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `FRONTEND_URL` | `http://localhost:5199` | Frontend origin for CORS |
| `BACKEND_PORT` | `8000` | Backend server port |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/promptforge.db` | Database connection string |
| `AUTH_TOKEN` | *(disabled)* | Bearer token for API authentication |
| `LLM_PROVIDER` | *(auto-detect)* | `claude-cli`, `anthropic`, `openai`, or `gemini` |
| `ANTHROPIC_API_KEY` | | Anthropic API key |
| `OPENAI_API_KEY` | | OpenAI API key |
| `GEMINI_API_KEY` | | Google Gemini API key |
| `RATE_LIMIT_RPM` | `60` | General rate limit (requests/minute) |
| `RATE_LIMIT_OPTIMIZE_RPM` | `10` | Optimize endpoint rate limit |

See [`.env.example`](.env.example) for the full list.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── middleware/      # Auth, rate limiting, CSRF, security headers
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── prompts/         # LLM prompt templates
│   │   ├── providers/       # LLM provider abstraction (Claude, OpenAI, Gemini)
│   │   ├── repositories/    # Data access layer
│   │   ├── routers/         # FastAPI route handlers
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # Pipeline orchestration
│   │   ├── utils/           # Score normalization, helpers
│   │   ├── config.py        # Environment configuration
│   │   ├── database.py      # Async SQLAlchemy setup
│   │   ├── main.py          # FastAPI application entry point
│   │   └── mcp_server.py    # FastMCP server (16 tools)
│   └── tests/
├── frontend/
│   └── src/
│       ├── lib/
│       │   ├── api/         # SSE client, API helpers
│       │   ├── components/  # Svelte 5 UI components
│       │   ├── stores/      # Runes-based reactive stores
│       │   └── utils/       # Formatting, export
│       └── routes/          # SvelteKit pages (/, /optimize/[id], /projects/[id])
├── docker-compose.yml
├── init.sh                  # Dev environment manager
├── .env.example             # Environment template
└── ARCHITECTURE.md          # Full architecture document
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture document covering provider abstraction, security middleware, Docker deployment, and more.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding guidelines, and how to add new LLM providers.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
