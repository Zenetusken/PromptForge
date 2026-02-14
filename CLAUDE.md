# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is PromptForge

An AI-powered prompt optimization web app. Users submit a raw prompt, and a 3-stage pipeline (Analyze → Optimize → Validate) rewrites it using Claude, scores the result, and persists everything to a history database. Results stream to the frontend in real time via SSE.

## Tech Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy 2.0 async ORM / SQLite (aiosqlite) / Pydantic v2
- **Frontend**: SvelteKit 2 / Svelte 5 (runes: `$state`, `$derived`, `$effect`) / Tailwind CSS 4 / TypeScript 5.7+ / Vite 6
- **LLM access**: `claude-code-sdk` — calls Claude via CLI subprocess, no API key needed with MAX subscription
- **MCP server**: FastMCP-based, exposes 8 tools for Claude Code integration (`promptforge_optimize`, `promptforge_get`, `promptforge_list`, `promptforge_get_by_project`, `promptforge_search`, `promptforge_tag`, `promptforge_stats`, `promptforge_delete`)

## Commands

```bash
# Full dev setup (installs deps, starts both servers)
./init.sh

# Backend only (from project root)
cd backend && source venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend && npm run dev

# Backend tests (requires test extras)
cd backend && source venv/bin/activate
pip install -e ".[test]"
pytest                              # all tests
pytest tests/test_strategy_selector.py  # single test file

# Frontend tests
cd frontend
npm run test          # vitest run
npm run check         # svelte-check type checking

# MCP server
cd backend && python -m app.mcp_server

# Docker
docker-compose up     # starts backend (8000) + frontend (5173)
```

## Architecture

### Optimization Pipeline (`backend/app/services/pipeline.py`)

Three LLM-calling stages plus one sync step, orchestrated as an async generator that yields SSE events:

1. **Analyze** (`PromptAnalyzer`) — classifies task type, complexity, weaknesses, strengths
2. **Strategy Selection** (`StrategySelector`) — sync logic, picks from: chain-of-thought, few-shot, role-based, constraint-focused, structured-enhancement
3. **Optimize** (`PromptOptimizer`) — rewrites the prompt using the selected strategy
4. **Validate** (`PromptValidator`) — scores clarity/specificity/structure/faithfulness (0.0–1.0), generates verdict

`ClaudeClient` (`backend/app/services/claude_client.py`) wraps the SDK with `max_turns=1`, `allowed_tools=[]`, runs in `/tmp` to isolate from project context. JSON extraction uses 4 fallback strategies (direct parse → json fence → generic fence → brace match).

### SSE Streaming

Backend emits named SSE events: `stage`, `step_progress`, `analysis`, `optimization`, `validation`, `complete`, `error`. Stage lifecycle configs live in `backend/app/constants.py` (`StageConfig` dataclass with progress messages and intervals).

Frontend consumes SSE via `fetch` + `ReadableStream` reader (not native `EventSource`). The mapping from backend events to frontend `PipelineEvent` types is in `frontend/src/lib/api/client.ts:mapSSEEvent`.

### Data Layer

- **Repository pattern**: `OptimizationRepository` (`backend/app/repositories/optimization.py`) handles all DB queries
- **Converters**: `backend/app/converters.py` transforms ORM → Pydantic/dict, handles score normalization
- **Score normalization**: DB stores 0.0–1.0 floats; display/API uses 1–10 integers (`backend/app/utils/scores.py`)

### Frontend State

Svelte 5 runes-based stores (`.svelte.ts` files in `frontend/src/lib/stores/`):
- `optimization.svelte.ts` — current pipeline run state (isRunning, result, steps, error)
- `history.svelte.ts` — history list with pagination/filtering
- `prompt.svelte.ts` — last prompt text
- `toast.svelte.ts` — toast notifications

Routes: `/` (home with PromptInput + ResultPanel) and `/optimize/[id]` (detail page with SSR data loading).

## API Endpoints

| Method | Path | SSE |
|--------|------|-----|
| POST | `/api/optimize` | Yes |
| GET | `/api/optimize/{id}` | No |
| POST | `/api/optimize/{id}/retry` | Yes |
| GET/HEAD | `/api/history` | No |
| DELETE | `/api/history/{id}` | No |
| DELETE | `/api/history/all` | No |
| GET/HEAD | `/api/history/stats` | No |
| GET/HEAD | `/api/health` | No |

## Configuration

Environment defaults (set in `backend/app/config.py`, overridable via `.env`):
- `FRONTEND_URL` — default `http://localhost:5173`
- `BACKEND_PORT` — default `8000`
- `CLAUDE_MODEL` — default `claude-opus-4-6`
- `DATABASE_URL` — default `sqlite+aiosqlite:///<project>/data/promptforge.db`
- `ANTHROPIC_API_KEY` — leave empty to use MAX subscription

## Linting

- **Ruff**: target py314, line-length 100, rules: E/F/I/W (configured in `pyproject.toml`)
- **Pyright**: basic type checking mode, py314 (configured in `pyproject.toml`)
- **svelte-check**: `npm run check` in frontend

## Frontend Theme

Cyberpunk palette defined in `frontend/src/app.css` with CSS custom properties: `bg-primary` (#0a0a0f), `neon-cyan` (#00f0ff), `neon-purple` (#b000ff), `neon-green` (#00ff88), `neon-red` (#ff0055). Custom animations: `neon-pulse`, `copy-flash`, `fade-in`, `shimmer`.
