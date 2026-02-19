# Changelog

All notable changes to PromptForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
