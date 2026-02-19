# PromptForge — Intelligent Prompt Optimization Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/your-org/promptforge/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/promptforge/actions)

A self-adaptive prompt optimization web app that transforms raw, unstructured prompts into properly structured, improved, and optimized versions using a 4-stage AI pipeline. Provider-agnostic — works with Claude (MAX subscription or API), OpenAI, and Google Gemini.

## Quick Start

```bash
# Local development
chmod +x init.sh
./init.sh

# Docker deployment
docker compose up
```

This will:
1. Install Python and Node.js dependencies
2. Create the SQLite database
3. Start the backend on http://localhost:8000
4. Start the frontend on http://localhost:5199
5. Wait for both services to be healthy

## Docker Deployment

```bash
# Basic
docker compose up -d

# With authentication
AUTH_TOKEN=your-secret-token docker compose up -d

# With a specific LLM provider
ANTHROPIC_API_KEY=sk-... docker compose up -d
OPENAI_API_KEY=sk-... LLM_PROVIDER=openai docker compose up -d
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_TOKEN` | (disabled) | Bearer token for API authentication |
| `LLM_PROVIDER` | (auto-detect) | `claude-cli`, `anthropic`, `openai`, or `gemini` |
| `ANTHROPIC_API_KEY` | | Anthropic API key |
| `OPENAI_API_KEY` | | OpenAI API key |
| `GEMINI_API_KEY` | | Google Gemini API key |
| `RATE_LIMIT_RPM` | `60` | General rate limit (requests/minute) |
| `RATE_LIMIT_OPTIMIZE_RPM` | `10` | Optimize endpoint rate limit |

See `.env.example` for the full list.

## Tech Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy 2.0 async / SQLite
- **Frontend**: SvelteKit 2 (Svelte 5) / Tailwind CSS 4 / TypeScript / Vite
- **LLM Providers**: Claude CLI (MAX subscription), Anthropic API, OpenAI, Google Gemini
- **Streaming**: Server-Sent Events (SSE) for real-time pipeline updates
- **MCP Server**: FastMCP for Claude Code integration

## Development

### Backend (port 8000)
```bash
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend (port 5199)
```bash
cd frontend
npm run dev
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

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/optimize` | Start optimization pipeline (SSE stream) |
| GET | `/api/optimize/{id}` | Get optimization by ID |
| POST | `/api/optimize/{id}/retry` | Re-run optimization |
| GET | `/api/history` | List optimizations (paginated) |
| DELETE | `/api/history/{id}` | Delete optimization |
| DELETE | `/api/history/all` | Clear all history (requires `X-Confirm-Delete: yes`) |
| GET | `/api/history/stats` | Dashboard statistics |
| GET | `/api/providers` | List available LLM providers |
| GET/POST | `/api/projects` | Project management |
| GET | `/api/health` | Health check |

### MCP Server

PromptForge exposes its engine as an MCP server for Claude Code integration:

```bash
cd backend
python -m app.mcp_server
```

## Pipeline

1. **Analyze** — Classify the prompt type and identify weaknesses/strengths
2. **Strategy** — Select optimization strategy (chain-of-thought, few-shot, role-based, etc.)
3. **Optimize** — Transform the prompt using the selected strategy
4. **Validate** — Score the optimization on clarity, specificity, structure, faithfulness

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture document covering:
- Provider abstraction layer design
- Security middleware stack
- Docker deployment architecture
- Implementation roadmap

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding guidelines, and how to add new LLM providers.

## License

MIT — see [LICENSE](LICENSE).
