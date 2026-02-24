# Changelog

All notable changes to PromptForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Prompt caching on `AnthropicAPIProvider` — `cache_control={"type": "ephemeral"}` on all API calls for up to 90% cost savings on repeated system prompts
- Cache token tracking — `cache_creation_input_tokens` and `cache_read_input_tokens` fields in `TokenUsage`, `PipelineResult`, DB `Optimization` model, API schemas, and frontend display (cache savings indicator in result metadata tooltip)
- SDK-typed error classification — `_classify_anthropic_error()` uses the Anthropic SDK's exception hierarchy (`AuthenticationError`, `RateLimitError`, etc.) with `retry-after` header extraction, replacing string-based pattern matching for the Anthropic provider
- Async `count_tokens()` — `LLMProvider.count_tokens()` is now an `async` method; `AnthropicAPIProvider` calls the SDK's `messages.count_tokens()` endpoint with heuristic fallback
- `prompt_caching` capability flag in Claude model catalog
- MCP health monitoring — backend probes MCP server via `/health` endpoint, surfaces `mcp_connected` in health response, frontend shows MCP status in footer tooltip and fires toast notifications on status transitions
- MCP server `/health` endpoint — zero-state liveness probe on the MCP ASGI app (Starlette wrapper around SSE)
- `MCP_PORT` config variable (`backend/app/config.py`) — mirrors `init.sh` default of 8001
- `httpx` promoted to runtime dependency for async MCP connectivity probe
- Project-scoped stats via `GET /api/history/stats?project=...` query parameter
- Stateful header stats — shows project-scoped stats on `/projects/[id]` and `/optimize/[id]` routes, global stats elsewhere
- `statsState.setContext()` / `clearProjectContext()` / `activeStats` getter for route-aware stat switching
- `RecentForges` dashboard section — last 6 optimizations as compact navigational cards (score, task type, strategy, relative time) with "View all →" sidebar bridge
- `RecentProjects` dashboard section — up to 4 recent projects as compact navigational cards (prompt count, context indicator, description) with "View all →" sidebar bridge
- Sidebar open state in `sidebar.svelte.ts` — `isOpen`/`open()`/`close()`/`toggle()`/`openTo(tab)` with localStorage persistence
- Global stats store (`stats.svelte.ts`) — persistent stats across all routes, initialized in layout
- `HeaderStats` component — compact stats bar in the header replacing the logo (FORGED, AVG, IMP, PROJ, TODAY + dimension bars + top task)
- `OnboardingHero` component — interactive 3-step workflow guide (Write → Forge → Iterate) replacing ForgeHero, dismissible, shown for < 5 forges
- ForgePanel brand upgrade — gradient bolt logo, gradient "FORGE" text, shimmer placeholder, "/" kbd hint, entrance animation on expand
- Per-task-type color system (`taskTypes.ts`) — 14 unique neon colors for task type badges across all components
- Per-complexity color system (`complexity.ts`) — green/yellow/red with alias normalization (simple/moderate/complex)
- Premium filter bar with glass treatment, accent-tinted `.filter-row` rows, and `.filter-label` typography
- `.collapsible-toggle-section` CSS modifier for standalone collapsible sections
- `identityColor` prop on `MetadataSummaryLine` for per-type identity coloring via CSS variable
- Project context profiles — persistent codebase context on projects, auto-resolved during optimization, snapshotted on each optimization record for reproducibility
- `set_project_context` MCP tool — set or clear codebase context profile on a project
- Stack templates — 8 pre-built context profiles for common stacks (SvelteKit, FastAPI, Next.js, Django, Express, Rails, Spring Boot, Go)
- `ContextProfileEditor` component on project detail page with template picker, dirty detection, and save/clear
- Context auto-population in PromptInput when a project with a context profile is selected
- "Context Used" collapsible section on optimization detail page showing resolved context snapshot
- Bulk-delete endpoint (`POST /api/history/bulk-delete`) — delete 1–100 records in a single call
- `bulk_delete` MCP tool

### Removed
- `ForgeHero.svelte` — replaced by `OnboardingHero` (workflow guide) and `HeaderStats` (persistent stats bar)
- Header bolt icon — removed home link icon; HeaderStats fills full header width; breadcrumbs handle "get home" on detail pages
- "Back to Home" button + `navigation.svelte.ts` store — redundant with breadcrumbs; breadcrumbs are the single navigation mechanism on detail pages

### Changed
- `HeaderStats` — redesigned as wing formation layout with center-stage task type chip and animated glow (`header-contour-pulse` keyframes), context-aware project label
- `total_projects` stat — now counts only active projects from the projects table instead of distinct project names from optimizations
- Homepage — transformed from forge-only into content dashboard (RecentForges + RecentProjects above StrategyInsights for returning users)
- Sidebar open state — lifted from local `$state` in layout to `sidebarState` store with localStorage persistence
- Breadcrumbs — redesigned with cyberpunk brand treatment: glass pill container, monospace typography, `/` separators, neon-cyan hover glow with drop-shadow, truncated current segment
- CLAUDE.md — extracted frontend stores/components/utilities/routes catalog to `docs/frontend-internals.md`; CLAUDE.md now links to it instead of inlining ~30 lines of detail

### Fixed
- `most_common_task_type` ignored project filter — subquery used `.correlate(None)` without project/completed filters, always returning the global most common task type even when stats were scoped to a project
- `total_projects` included archived projects in count — now queries `projects` table with `status = 'active'`
- CLAUDE.md palette documentation — corrected 5 hex values to match `app.css` and brand guidelines (`bg-primary` #0a0a0f→#06060c, `neon-cyan` #00f0ff→#00e5ff, `neon-purple` #b000ff→#a855f7, `neon-green` #00ff88→#22ff88, `neon-red` #ff0055→#ff3366) and expanded from 5 to 19 palette tokens

## [0.2.0] - 2026-02-18

### Added
- ARCHITECTURE.md — comprehensive architecture document
- MIT LICENSE, CONTRIBUTING.md, CHANGELOG.md
- Authentication middleware (Bearer token via `AUTH_TOKEN` env var)
- Security headers middleware (CSP, X-Frame-Options, etc.)
- Rate limiting middleware (per-IP sliding window, configurable RPM)
- CSRF protection middleware (Origin-based validation)
- Audit logging middleware (state-changing request logging)
- Prompt injection detection (warn-only sanitization)
- Streaming interface on LLMProvider (`stream()` method)
- Token counting abstraction (`count_tokens()` method)
- Backend Dockerfile (multi-stage, non-root)
- Frontend Dockerfile (multi-stage, adapter-node)
- `.dockerignore` for clean build contexts
- GitHub Actions CI pipeline (backend + frontend + docker)
- Confirmation header required for bulk history delete

### Changed
- CORS tightened: explicit methods and headers lists (was `["*"]`)
- docker-compose.yml rewritten with healthchecks, restart policies, named volumes
- Frontend switched to `@sveltejs/adapter-node` for Docker deployment
- Frontend API client injects `Authorization` header when `AUTH_TOKEN` configured

## [0.1.0] - 2025-12-01

### Added
- Initial release
- 4-stage prompt optimization pipeline (Analyze, Strategy, Optimize, Validate)
- Provider abstraction with Claude CLI, Anthropic API, OpenAI, Gemini
- SSE streaming for real-time pipeline updates
- SQLite database with async SQLAlchemy
- SvelteKit 2 frontend with Svelte 5 runes
- Project and prompt management
- History with search, filter, and pagination
- MCP server for Claude Code integration
