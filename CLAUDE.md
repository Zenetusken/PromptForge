# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is PromptForge

An AI-powered prompt optimization web app. Users submit a raw prompt, and a 4-stage pipeline (Analyze → Strategy → Optimize → Validate) rewrites it using Claude, scores the result, and persists everything to a history database. Results stream to the frontend in real time via SSE.

## Tech Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy 2.0 async ORM / SQLite (aiosqlite) / Pydantic v2
- **Frontend**: SvelteKit 2 / Svelte 5 (runes: `$state`, `$derived`, `$effect`) / Tailwind CSS 4 / TypeScript 5.7+ / Vite 6
- **LLM access**: Provider-agnostic via `backend/app/providers/` — supports Claude CLI (default), Anthropic API, OpenAI, and Google Gemini. Auto-detects available provider or set `LLM_PROVIDER` explicitly.
- **MCP server**: FastMCP-based (`promptforge_mcp`), exposes 16 tools for Claude Code integration (`optimize`, `retry`, `get`, `list`, `get_by_project`, `search`, `tag`, `stats`, `delete`, `bulk_delete`, `list_projects`, `get_project`, `strategies`, `create_project`, `add_prompt`, `update_prompt`). Runs as SSE HTTP transport on port 8001 with uvicorn `--reload` for hot-reload. Managed by `init.sh` alongside backend/frontend. Auto-discoverable via `.mcp.json` (`type: sse`).

## Commands

```bash
# Full dev setup (installs deps, starts all services)
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

# MCP server (standalone, for testing — normally managed by init.sh)
cd backend && source venv/bin/activate
python -m uvicorn app.mcp_server:app --reload --port 8001

# Docker
docker-compose up     # starts backend (8000) + frontend (5199) + MCP (8001)
```

## Architecture

### Optimization Pipeline (`backend/app/services/pipeline.py`)

Four LLM-calling stages, orchestrated as an async generator that yields SSE events:

1. **Analyze** (`PromptAnalyzer`) — classifies task type, complexity, weaknesses, strengths
2. **Strategy Selection** (`StrategySelector`) — LLM-based strategy selection with heuristic fallback. Sends analysis and prompt to the LLM to pick from 10 frameworks: co-star, risen, chain-of-thought, few-shot-scaffolding, role-task-format, structured-output, step-by-step, constraint-injection, context-enrichment, persona-assignment. Returns strategy name, reasoning, and confidence (0.0–1.0). Falls back to `HeuristicStrategySelector` (3-tier priority system with specificity exemptions and redundancy detection) on LLM errors. Users can override strategy via the UI or API (bypasses LLM call).
3. **Optimize** (`PromptOptimizer`) — rewrites the prompt using the selected strategy
4. **Validate** (`PromptValidator`) — scores clarity/specificity/structure/faithfulness (0.0–1.0), generates verdict

All 4 stages accept an optional `codebase_context` parameter (`CodebaseContext` dataclass from `backend/app/schemas/context.py`). When provided, each stage injects the rendered context into its LLM user message so the optimizer produces prompts grounded in actual codebase patterns, conventions, and architecture. Context is caller-provided (e.g. from Claude Code's Plan agent), transient (not persisted to DB), and adds zero extra LLM calls. Accepted via the `codebase_context` dict parameter on both the MCP `optimize` tool and the `POST /api/optimize` HTTP endpoint. Fields: `language`, `framework`, `description`, `conventions`, `patterns`, `code_snippets`, `documentation`, `test_framework`, `test_patterns` — all optional, unknown keys silently ignored.

LLM calls go through the provider abstraction (`backend/app/providers/`). `LLMProvider` is the abstract base with `send_message` and `send_message_json` (4-strategy JSON extraction: direct parse → json fence → generic fence → brace match). Concrete providers: `ClaudeCLIProvider` (default, MAX subscription), `AnthropicAPIProvider`, `OpenAIProvider`, `GeminiProvider`. `get_provider()` auto-detects or uses explicit `LLM_PROVIDER` env var. Runtime API key and model overrides are passed via `X-LLM-API-Key` and `X-LLM-Model` HTTP headers (never in request bodies or logs). Model catalog (`backend/app/providers/models.py`) defines 2 models per provider (performance + cost-effective tier).

### SSE Streaming

Backend emits named SSE events: `stage`, `step_progress`, `strategy`, `analysis`, `optimization`, `validation`, `complete`, `error`. Stage lifecycle configs live in `backend/app/constants.py` (`StageConfig` dataclass with progress messages and intervals). The `strategy` event carries structured data: `{strategy, reasoning, task_type, confidence}`.

Frontend consumes SSE via `fetch` + `ReadableStream` reader (not native `EventSource`). The mapping from backend events to frontend `PipelineEvent` types is in `frontend/src/lib/api/client.ts:mapSSEEvent`. The `strategy` backend event maps to a dedicated `strategy_selected` frontend event type that preserves all structured fields (confidence, reasoning, task_type).

### Data Layer

- **Repository pattern**: `OptimizationRepository` (`backend/app/repositories/optimization.py`) handles all DB queries; `ProjectRepository` (`backend/app/repositories/project.py`) for projects/prompts
- **Converters**: `backend/app/converters.py` transforms ORM → Pydantic/dict, handles score normalization
- **Score normalization**: DB stores 0.0–1.0 floats; display/API uses 1–10 integers (`backend/app/utils/scores.py`)
- **Legacy migration**: On startup, `_migrate_legacy_projects()` in `database.py` seeds the `projects` table from distinct `optimization.project` string values and imports unique `raw_prompt` values as `Prompt` entries. Idempotent (safe on every restart).
- **Auto-create projects**: When an optimization is created/retried with a `project` name (via API or MCP), a matching `Project` record is auto-created if it doesn't exist (`ensure_project_by_name` in `repositories/project.py`). Reactivates soft-deleted projects.
- **Prompt version history**: `PromptVersion` table (`models/project.py`) stores immutable snapshots of prior prompt content. Created automatically by `update_prompt()` when content changes. Current version lives in `prompts.content`; only superseded versions are snapshotted.
- **Forge result linking**: `Optimization.prompt_id` FK links an optimization to the project prompt that triggered it. Set when forging from a project prompt card. Nullable for legacy/home-page optimizations. DB constraint is `ON DELETE SET NULL`, but application-level `delete_prompt()` explicitly removes linked optimizations before deleting the prompt.
- **Project deletion cascade**: `delete_project_data()` in `ProjectRepository` deletes all prompts (reusing `delete_prompt()` per prompt) then sweeps remaining legacy optimizations by project name. The router calls this before soft-deleting the project record.
- **Extended analytics** (`get_stats()` in `OptimizationRepository`): Beyond basic strategy distribution and score averages, the stats endpoint computes 10 additional DB-driven analytics: score matrix (strategy × task-type avg scores), score variance (min/max/stddev per strategy), confidence averages, combo effectiveness (primary+secondary pair scores), complexity performance, improvement rates per strategy, error rates (includes non-completed records), time trends (7d/30d), token economics (avg input/output tokens and duration), and win rates (best strategy per task type). All respect project-scope filters and legacy alias normalization. Nullable fields default to `None` on empty DB for backward compatibility.

### Frontend State

Svelte 5 runes-based stores (`.svelte.ts` files in `frontend/src/lib/stores/`):
- `optimization.svelte.ts` — current pipeline run state (isRunning, result, steps, strategyData, error). Pipeline has 4 steps: analyze, strategy, optimize, validate.
- `history.svelte.ts` — history list with pagination/filtering
- `prompt.svelte.ts` — last prompt text, project name, prompt ID, and strategy override (for cross-route pre-fill from project detail and Strategy Explorer)
- `provider.svelte.ts` — provider selection, API key management (sessionStorage/localStorage), model selection, LLM header building
- `projects.svelte.ts` — project CRUD, prompt management, sidebar list with active-only filter
- `sidebar.svelte.ts` — sidebar tab state (history/projects), persisted to localStorage
- `toast.svelte.ts` — toast notifications

Shared utilities (`frontend/src/lib/utils/`):
- `strategies.ts` — canonical list of all 10 strategy names, display labels, descriptions, extended details (`STRATEGY_DETAILS`: bestFor task types + motivation blurbs), and 10 unique per-strategy colors (`STRATEGY_COLOR_META`). `getStrategyColor(name)` is the single lookup function all consumers import — returns `StrategyColorMeta` with `bar`, `text`, `border`, `btnBg`, `rawRgba` fields, cyan fallback for unknown/null. Single source of truth imported by `PromptInput` (strategy picker), `StrategyInsights` (Strategy Explorer), `HistoryEntry`, `PipelineStep`, and project detail pages.
- `recommendation.ts` — multi-signal composite recommendation engine for the Strategy Explorer. Scores untried strategies using 4 weighted signals plus a multiplicative dampener. Base signals: task-type affinity (0.50), performance gap analysis (0.25), diversity bonus (0.25). Secondary composite (0.20): a blended score from 5 sub-signals (frequency, reach, synergy, familiarity, tag affinity) processed by `computeSecondaryComposite` with configurable internal weights (`SecondaryProcessorWeights`), plus a combo effectiveness bonus (~10% weight from `computeComboScore`). Data confidence is a multiplicative dampener. Formula: `(affinity×0.50 + gap×0.25 + diversity×0.25 + secondaryComposite×0.20) × confidence`. When backend analytics are available (score matrix, score variance, combo effectiveness), the engine upgrades scoring precision: `computeAffinityScore` uses need-weighted factors from per-task-type performance gaps, `computeGapScore` uses per-task-type scores instead of strategy-wide averages, and `selectTopPerformer` breaks score ties by lower variance (more consistent). All enhancements are optional — the engine falls back to pure-frequency scoring when analytics are unavailable. Shared analytics types (`ScoreMatrixEntry`, `ScoreVarianceEntry`, `ComboEntry`, `ImprovementEntry`) are defined in `client.ts` and re-exported from `recommendation.ts`. Exports pure functions (`computeRecommendations`, `selectTopPerformer`, `computeComboScore`, `computeSecondaryComposite`, `computeFrequencyScore`, `computeReachScore`, `computeSynergyScore`, `computeSecondaryFamiliarityScore`, `computeTagAffinityBoost`, `buildTaskFrequency`, `buildGlobalTags`, `generateSecondaryInsights`, and other individual signal scorers) and types (`RecommendationResult`, `ScoredStrategy`, `RecommendationConfidence`, `SecondaryInsight`, `SecondaryProcessorWeights`). Weights configurable via `RecommendationWeights` interface. Includes confidence tier classification (high/moderate/exploratory) with secondary-aware text, insight generation (0–3 insights per recommendation), and improved top performer selection (min 3 uses, significance flag at 5+, variance-aware tie-breaking).

Key components:
- `PromptInput.svelte` — prompt textarea with three collapsible sections: Metadata (title/project/tags/version), Context (codebase context fields for grounded optimization), and Strategy (override selection with secondary frameworks). Context section sends `codebase_context` in the optimize request body.
- `StrategyInsights.svelte` — interactive Strategy Explorer with section heading (`section-heading-dim` + "X/10 used" counter), badge column (fixed `w-4` between label and bar — ✳ for recommended strategy, ♛ crown for top performer; mutually exclusive since recommended = untried, top performer = tried), column headers (#, 2nd, Avg), clickable distribution bars with relative-to-leader normalization (leader fills ~100%, others proportional; tooltips still show share-of-total percentages), stagger entrance animation (primary bars have premium glass-depth effect, secondary bars use flat opacity fills), expandable detail panels (`animate-section-expand`, `.chip` task type badges, `.tag-chip` tag badges, `font-display` micro-headings, primary/secondary micro-bars, single contextual action button). Enhanced recommendation card: headline summary (derived from top scoring signal), signal breakdown (top 3 signals with mini `neon-yellow` progress bars and mono scores via `SIGNAL_META` lookup), confidence badge + conversational rationale (uses total optimizations and tried strategy count instead of internal scores), rich multi-category insights (8 categories: task_match, coverage_gap, new_territory, familiar_pick, tag_alignment, usage_pattern, signal_synergy, data_profile — 3–6 per recommendation sorted by signal priority, with conversational messages referencing concrete user data), collapsible runner-ups (up to 3 cards with rank badge, composite %, confidence tier mini-badge, motivation, and "Try it" button). Primary/secondary legend with toggle. Accepts `onStrategySelect` callback to pre-fill strategy in PromptInput.

Routes: `/` (home with PromptInput + ResultPanel + StrategyInsights), `/optimize/[id]` (detail page with SSR data loading), and `/projects/[id]` (project detail with prompts).

## API Endpoints

| Method | Path | SSE |
|--------|------|-----|
| POST | `/api/optimize` | Yes |
| GET | `/api/optimize/{id}` | No |
| POST | `/api/optimize/{id}/retry` | Yes |
| GET/HEAD | `/api/history` | No |
| DELETE | `/api/history/{id}` | No |
| POST | `/api/history/bulk-delete` | No |
| DELETE | `/api/history/all` | No |
| GET/HEAD | `/api/history/stats` | No |
| GET/HEAD | `/api/health` | No |
| GET | `/api/providers` | No |
| POST | `/api/providers/validate-key` | No |
| GET | `/api/projects` | No |
| POST | `/api/projects` | No |
| GET | `/api/projects/{id}` | No |
| PUT | `/api/projects/{id}` | No |
| DELETE | `/api/projects/{id}` | No |
| POST | `/api/projects/{id}/archive` | No |
| POST | `/api/projects/{id}/unarchive` | No |
| POST | `/api/projects/{id}/prompts` | No |
| PUT | `/api/projects/{id}/prompts/reorder` | No |
| GET | `/api/projects/{id}/prompts/{pid}/versions` | No |
| GET | `/api/projects/{id}/prompts/{pid}/forges` | No |
| PUT | `/api/projects/{id}/prompts/{pid}` | No |
| DELETE | `/api/projects/{id}/prompts/{pid}` | No |

## Configuration

Environment defaults (set in `backend/app/config.py`, overridable via `.env`):
- `FRONTEND_URL` — default `http://localhost:5199`
- `BACKEND_PORT` — default `8000`
- `HOST` — default `0.0.0.0`
- `MCP_PORT` — default `8001` (managed by `init.sh`, not config.py)
- `DATABASE_URL` — default `sqlite+aiosqlite:///<project>/data/promptforge.db`
- `LLM_PROVIDER` — auto-detect when empty; explicit: `claude-cli`, `anthropic`, `openai`, `gemini`
- `CLAUDE_MODEL` — default `claude-opus-4-6` (used by Claude CLI and Anthropic API providers)
- `ANTHROPIC_API_KEY` — leave empty to use MAX subscription via Claude CLI
- `OPENAI_API_KEY` — set to enable OpenAI provider
- `OPENAI_MODEL` — default `gpt-4.1`
- `GEMINI_API_KEY` — set to enable Gemini provider
- `GEMINI_MODEL` — default `gemini-2.5-pro`

## Testing

Run all tests: `./init.sh test`

### Backend (pytest, async)

- **Config**: `pyproject.toml` — `asyncio_mode = "auto"`, extras in `[test]`
- **Fixtures** (`tests/conftest.py`): `db_engine` (in-memory SQLite), `db_session`, `client` (httpx AsyncClient with FastAPI dependency override)
- **File naming**: `tests/test_{module}.py` — one file per module/concern
- **Structure**: Group related tests in classes (`class TestGetById`, `class TestCreate`). Use `@pytest.mark.asyncio` on each async test method. Top-level functions for standalone tests.
- **Mocking LLM calls**: Create a `FakeProvider(LLMProvider)` that returns canned responses. Patch `get_provider` where needed.
- **DB tests**: Use `db_session` fixture, write `_seed()` helpers for test data factories.
- **Router tests**: Use `client` fixture, assert status codes + response JSON.
- **No external calls**: All tests run offline — LLM providers are mocked, DB is in-memory.

### Frontend (vitest, Svelte 5)

- **Config**: `vite.config.ts` — `test.include: ['src/**/*.test.ts']`, `environment: 'jsdom'`, `svelteTesting()` plugin
- **File naming**: Co-located `{module}.test.ts` next to source file
- **Structure**: `describe`/`it` blocks. Use `vi.mock()` for module mocking, `vi.fn()` for stubs.
- **Store tests**: Import the store, set state in `beforeEach`, assert reactive properties.
- **Component tests**: Use `@testing-library/svelte` (`render`, `screen`, `fireEvent`). Clear `document.body` in `beforeEach`. Add `data-testid` attributes for querying.
- **Browser APIs**: Stub `sessionStorage`/`localStorage` with in-memory objects when testing in Node.

## Linting

- **Ruff**: target py314, line-length 100, rules: E/F/I/W (configured in `pyproject.toml`)
- **Pyright**: basic type checking mode, py314 (configured in `pyproject.toml`)
- **svelte-check**: `npm run check` in frontend

## Frontend Theme

Cyberpunk palette defined in `frontend/src/app.css` with CSS custom properties: `bg-primary` (#0a0a0f), `neon-cyan` (#00f0ff), `neon-purple` (#b000ff), `neon-green` (#00ff88), `neon-red` (#ff0055). Custom animations: `neon-pulse`, `copy-flash`, `fade-in`, `shimmer`.
