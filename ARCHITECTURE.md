# PromptForge Architecture Document

## Section 0: Assumptions

| # | Assumption | Rationale |
|---|-----------|-----------|
| A1 | Single-instance deployment (no horizontal scaling) | SQLite database; self-hosted target audience |
| A2 | API keys are managed client-side or via env vars | Headers (`X-LLM-*`) pass keys per-request; server never persists them |
| A3 | Claude CLI (MAX subscription) is the primary provider | Zero-cost for subscribers; auto-detected first in provider order |
| A4 | All LLM calls are async, but not parallelized within a pipeline run | Each stage depends on the previous stage's output |
| A5 | SSE is sufficient for real-time updates (no WebSocket needed) | Unidirectional server-to-client; no client-to-server streaming |
| A6 | Authentication is optional (self-hosted) | Bearer token via env var; disabled when empty for local/dev use |
| A7 | No multi-tenancy or user isolation | Single-user or trusted-team deployment model |
| A8 | Provider SDKs handle their own TLS and certificate validation | We don't manage TLS for outbound LLM API calls |
| A9 | Docker deployment targets linux/amd64 and linux/arm64 | Standard CI/CD and self-hosted server architectures |
| A10 | MIT license for maximum adoption and contribution | No copyleft obligations; commercial-friendly |

---

## Section 1: Technology Stack

### Backend

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Language | Python | 3.14+ | Async-first, rich LLM SDK ecosystem |
| Framework | FastAPI | ≥0.115 | Native async, automatic OpenAPI docs, dependency injection |
| ORM | SQLAlchemy 2.0 | ≥2.0 | Async session support, mature migration tooling |
| Database | SQLite (aiosqlite) | ≥0.20 | Zero-config, single-file, sufficient for single-instance |
| Validation | Pydantic v2 | ≥2.0 | FastAPI integration, strict type coercion |
| Server | Uvicorn | ≥0.34 | ASGI reference server, HTTP/1.1 + HTTP/2 |

### Frontend

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Framework | SvelteKit 2 | ≥2.15 | SSR + SPA hybrid, file-based routing |
| UI Library | Svelte 5 | ≥5.0 | Runes reactivity (`$state`, `$derived`, `$effect`) |
| Styling | Tailwind CSS 4 | ≥4.0 | Utility-first, CSS custom properties for theming |
| Build | Vite 6 | ≥6.0 | Fast HMR, native ESM |
| Types | TypeScript | ≥5.7 | Strict mode, satisfies operator |

### LLM Provider SDKs

| Provider | SDK | Version |
|----------|-----|---------|
| Claude CLI | claude-agent-sdk | ≥0.1.37 |
| Anthropic API | anthropic | ≥0.40 |
| OpenAI | openai | ≥1.50 |
| Google Gemini | google-genai | ≥1.0 |

---

## Section 2: Provider Abstraction Layer

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Pipeline Services                     │
│         (Analyzer, StrategySelector, Optimizer,          │
│                    Validator)                            │
├─────────────────────────────────────────────────────────┤
│              LLMProvider ABC (base.py)                   │
│  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │send_msg  │complete  │complete_ │send_msg_ │          │
│  │          │          │json      │json      │          │
│  └──────────┴──────────┴──────────┴──────────┘          │
├─────────────────────────────────────────────────────────┤
│              ProviderRegistry (registry.py)              │
│  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │claude-cli│anthropic │openai    │gemini    │          │
│  └──────────┴──────────┴──────────┴──────────┘          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 LLMProvider Interface

The abstract base class (`backend/app/providers/base.py`) defines:

- **`send_message(system_prompt, user_message) -> str`** — Core text completion (abstract)
- **`complete(request: CompletionRequest) -> CompletionResponse`** — Unified request/response with token tracking (concrete, delegates to `send_message`)
- **`complete_json(request) -> (dict, CompletionResponse)`** — JSON extraction with 4-strategy fallback + retry (concrete)
- **`send_message_json(system_prompt, user_message) -> dict`** — Legacy JSON helper (concrete)
- **`test_connection(timeout) -> (bool, error)`** — Provider health check (concrete, overridable)
- **`supports(capability) -> bool`** — Model capability lookup via `MODEL_CATALOG`
- **`is_available() -> bool`** — Readiness check (abstract)
- **`model_name`** / **`provider_name`** — Identity properties (abstract)

### 2.3 Provider Adapters

**Claude CLI** (`claude_cli.py`): Uses `claude-agent-sdk` subprocess. No API key — MAX subscription auth via OAuth. Runs in `_ISOLATED_CWD` (tempdir) to prevent project context detection. Handles `rate_limit_event` from SDK `MessageParseError`.

**Anthropic API** (`anthropic_api.py`): Direct `AsyncAnthropic` client. Tracks `TokenUsage` from response. Lazy client initialization. Minimal 1-token ping for `test_connection`.

**OpenAI** (`openai_provider.py`): `AsyncOpenAI` client with Chat Completions API. Maps `prompt_tokens`/`completion_tokens` to `TokenUsage`. System prompt via messages array.

**Gemini** (`gemini_provider.py`): `google.genai.Client` with async `generate_content`. System instruction via `GenerateContentConfig`. Maps `usage_metadata` fields to `TokenUsage`.

### 2.4 ProviderRegistry

Centralized registration, caching, and resolution (`backend/app/providers/registry.py`):

- **Lazy loading**: Providers are imported only when first requested (avoids hard deps)
- **Gate functions**: Fast availability checks (e.g., `which_claude_cached()`, env var presence) skip unavailable providers during auto-detection
- **Instance caching**: Default-config instances cached; overridden instances (custom API key/model) created fresh
- **Auto-detect TTL**: 60-second cache with env-var snapshot fingerprinting
- **Resolution order**: Explicit name → `LLM_PROVIDER` env → auto-detect gates

### 2.5 Error Hierarchy

```
ProviderError
├── AuthenticationError        # Invalid/missing API key
├── ProviderPermissionError    # Key lacks permissions
├── RateLimitError             # Rate limit (+ retry_after)
├── ModelNotFoundError         # Invalid model name
├── ProviderUnavailableError   # Provider not ready (also RuntimeError)
└── ProviderConnectionError    # Network/timeout
```

`classify_error()` in `base.py` converts raw SDK exceptions into typed errors via pattern matching on error message content.

### 2.6 Streaming Interface (Phase 2)

Extension to `LLMProvider`:

- **`stream(request: CompletionRequest) -> AsyncIterator[StreamChunk]`** — Yields text chunks as they arrive
- **`supports_streaming() -> bool`** — Capability flag (default: False)
- Default `stream()` implementation: calls `complete()`, yields single `StreamChunk`
- Implemented for: Anthropic API (`messages.stream()`), OpenAI (`stream=True`), Gemini (`generate_content_stream()`)
- Claude CLI: Falls back to non-streaming (SDK streams internally)

### 2.7 Token Counting (Phase 2)

- **`count_tokens(text: str) -> int | None`** — Optional token counting on `LLMProvider` (default returns `None`)
- Anthropic: `client.count_tokens()`
- OpenAI: `tiktoken` library (optional dependency)
- Others: Return `None` (not supported)

---

## Section 3: FOSS & Self-Hosting

### 3.1 Repository Structure

```
PromptForge/
├── backend/                   # FastAPI application
│   ├── app/
│   │   ├── main.py           # App entry + middleware stack
│   │   ├── config.py         # Environment configuration
│   │   ├── database.py       # SQLAlchemy async setup
│   │   ├── middleware/       # Security middleware package
│   │   │   ├── __init__.py
│   │   │   ├── auth.py       # Bearer token authentication
│   │   │   ├── rate_limit.py # In-memory sliding window
│   │   │   ├── security_headers.py
│   │   │   ├── sanitize.py   # Prompt injection detection (warn-only)
│   │   │   ├── csrf.py       # Origin-based CSRF protection
│   │   │   └── audit.py      # Request audit logging
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── routers/          # API endpoint handlers
│   │   ├── repositories/     # Data access layer
│   │   ├── services/         # Business logic (pipeline stages)
│   │   ├── providers/        # LLM provider abstraction
│   │   ├── prompts/          # LLM system prompt templates
│   │   └── mcp_server.py     # FastMCP server
│   ├── tests/                # pytest test suite
│   ├── Dockerfile            # Production backend image
│   └── pyproject.toml        # Dependencies + tool config
├── frontend/                  # SvelteKit application
│   ├── src/
│   │   ├── routes/           # File-based routing
│   │   └── lib/
│   │       ├── components/   # Svelte 5 components
│   │       ├── stores/       # Runes-based state (.svelte.ts)
│   │       ├── api/          # API client + SSE handling
│   │       └── utils/        # Utilities
│   ├── Dockerfile            # Production frontend image
│   └── package.json          # Dependencies
├── data/                      # SQLite database (gitignored)
├── docker-compose.yml         # Production orchestration
├── .dockerignore              # Build context exclusions
├── .env.example               # Environment template
├── .github/workflows/ci.yml   # CI pipeline
├── LICENSE                    # MIT
├── CONTRIBUTING.md            # Contribution guide
├── CHANGELOG.md               # Release history
├── ARCHITECTURE.md            # This document
├── CLAUDE.md                  # Claude Code project instructions
└── README.md                  # User-facing documentation
```

### 3.2 Configuration Management

All configuration via environment variables with sensible defaults:

| Variable | Default | Purpose |
|----------|---------|---------|
| `FRONTEND_URL` | `http://localhost:5199` | CORS allowed origins |
| `BACKEND_PORT` | `8000` | Server listen port |
| `HOST` | `0.0.0.0` | Server bind address |
| `DATABASE_URL` | `sqlite+aiosqlite:///.../promptforge.db` | Database connection |
| `LLM_PROVIDER` | (auto-detect) | Explicit provider selection |
| `AUTH_TOKEN` | (empty = disabled) | Bearer token for API auth |
| `RATE_LIMIT_RPM` | `60` | General rate limit (requests/min) |
| `RATE_LIMIT_OPTIMIZE_RPM` | `10` | Optimize endpoint rate limit |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API access |
| `OPENAI_API_KEY` | (empty) | OpenAI API access |
| `GEMINI_API_KEY` | (empty) | Gemini API access |
| `CLAUDE_MODEL` | `claude-opus-4-6` | Claude model selection |
| `OPENAI_MODEL` | `gpt-4.1` | OpenAI model selection |
| `GEMINI_MODEL` | `gemini-2.5-pro` | Gemini model selection |

### 3.3 Docker Deployment

**Backend Dockerfile**: Multi-stage build with Python 3.14-slim base. Installs only production dependencies. Runs as non-root user. Health check via `/api/health`.

**Frontend Dockerfile**: Two-stage build — Node 22-alpine for build, Node 22-alpine for runtime. Uses `@sveltejs/adapter-node` for production SSR. Runs as non-root user.

**docker-compose.yml**: Named volumes for data persistence. Healthchecks with retries. Restart policies (`unless-stopped`). Environment passthrough for API keys. Frontend depends on backend health.

### 3.4 CI/CD Pipeline

Three-job GitHub Actions workflow (`.github/workflows/ci.yml`):

1. **Backend**: Python 3.14 + ruff lint + pytest
2. **Frontend**: Node 22 + svelte-check + vitest
3. **Docker**: Build both images + smoke test (health endpoint)

Triggered on push to `main` and pull requests.

---

## Section 4: Security Architecture

### 4.1 Threat Model

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Unauthorized API access | High | Bearer token auth middleware |
| Prompt injection via user input | Medium | Warn-only sanitization (log + SSE warning) |
| CSRF on state-changing endpoints | Medium | Origin-based validation |
| API abuse / DoS | Medium | Per-IP sliding window rate limiting |
| XSS via API responses | Medium | Security headers (CSP, X-XSS-Protection) |
| Clickjacking | Low | X-Frame-Options: DENY |
| Accidental data destruction | Medium | Confirmation header for bulk delete |
| API key exposure in logs | High | Keys passed via headers, never logged |
| Supply chain attacks | Medium | Pinned dependency versions, CI checks |

### 4.2 Middleware Stack

Ordered outermost to innermost (request flows top-down, response flows bottom-up):

```
Request → SecurityHeaders → CORS → CSRF → RateLimit → Auth → Audit → Router
```

1. **SecurityHeaders**: Sets protective response headers on every response
2. **CORS**: FastAPI CORSMiddleware with explicit methods/headers
3. **CSRF**: Validates `Origin` header on POST/PUT/DELETE requests
4. **RateLimit**: In-memory sliding window, per-IP, configurable RPM
5. **Auth**: Bearer token validation (skips health/docs endpoints)
6. **Audit**: Logs state-changing requests (method, path, status, IP)

### 4.3 Authentication

- **Mechanism**: Bearer token via `Authorization: Bearer <token>` header
- **Configuration**: `AUTH_TOKEN` environment variable
- **Disabled when**: `AUTH_TOKEN` is empty or unset (backward compatible)
- **Exempt endpoints**: `GET /api/health`, `GET /docs`, `GET /openapi.json`, `GET /`
- **Frontend**: Injects `Authorization` header via extended `buildLLMHeaders()`

### 4.4 Prompt Injection Defense

PromptForge is a prompt optimizer, not a chatbot — it intentionally processes and transforms arbitrary prompt text. The defense strategy is **warn-only**:

- Strip null bytes and control characters from input
- Pattern-match known injection techniques (system prompt override, role hijacking)
- Log warnings server-side
- Emit warnings via SSE events for user visibility
- **Never block** — the user's prompt is their intent

### 4.5 Secrets Management

- API keys are passed via HTTP headers (`X-LLM-API-Key`), never in request bodies
- Keys are never logged (middleware audit excludes sensitive headers)
- Frontend stores keys in `sessionStorage` (cleared on tab close) or `localStorage` (user choice)
- Server-side env vars for default keys (`ANTHROPIC_API_KEY`, etc.)
- Docker: Environment passthrough, no baked-in secrets

### 4.6 Destructive Endpoint Protection

`DELETE /api/history/all` requires `X-Confirm-Delete: yes` header. Frontend sends this header after user confirmation dialog.

---

## Section 5: Implementation Roadmap

### Phase 1: MVP Security + Deployment (P0)

| Item | Description | Acceptance Criteria |
|------|-------------|-------------------|
| Auth middleware | Bearer token authentication | 401 without valid token; health/docs exempt |
| Security headers | 6 protective response headers | All headers present on `curl -I /api/health` |
| CORS tightening | Explicit methods/headers lists | Only GET/POST/PUT/DELETE/HEAD; only needed headers |
| Rate limiting | Per-IP sliding window | 429 after exceeding configured RPM |
| Docker infrastructure | Working Dockerfiles + compose | `docker compose build` succeeds; images run |
| FOSS licensing | MIT LICENSE + CONTRIBUTING + CHANGELOG | Files present; license in pyproject.toml/package.json |
| Destructive guards | Confirmation header for bulk delete | 400 without `X-Confirm-Delete: yes` |

### Phase 2: Full Provider + Security Hardening (P1-P2)

| Item | Description | Acceptance Criteria |
|------|-------------|-------------------|
| Streaming interface | `stream()` on LLMProvider | Anthropic/OpenAI/Gemini yield StreamChunks |
| Token counting | `count_tokens()` on LLMProvider | Anthropic returns counts; others return None |
| Prompt sanitization | Warn-only injection detection | Null bytes stripped; patterns logged |
| CSRF protection | Origin-based validation | POST/PUT/DELETE blocked without valid Origin |
| Audit logging | Request logging middleware | State-changing requests logged with metadata |
| CI/CD pipeline | GitHub Actions workflow | 3 jobs pass on push to main |

### Phase 3: Extensibility (Future)

| Item | Description |
|------|-------------|
| Plugin system | Config-based community provider registration (YAML + entry points) |
| Key encryption | API keys encrypted at rest via Fernet/AES |
| Kubernetes | Helm chart for k8s deployment |
| Signed releases | SBOM generation + release signing |

---

## Section 6: Appendix

### 6.1 Glossary

| Term | Definition |
|------|-----------|
| **Provider** | An LLM service adapter implementing the `LLMProvider` interface |
| **Pipeline** | The 4-stage optimization flow: Analyze → Strategy → Optimize → Validate |
| **SSE** | Server-Sent Events — unidirectional server-to-client streaming protocol |
| **Forge** | A single prompt optimization run (verb: "to forge a prompt") |
| **Gate function** | Fast boolean check used by ProviderRegistry to skip unavailable providers |
| **Runes** | Svelte 5's reactivity primitives (`$state`, `$derived`, `$effect`) |
| **MCP** | Model Context Protocol — standardized tool interface for Claude Code |

### 6.2 Key File References

| File | Purpose |
|------|---------|
| `backend/app/providers/base.py` | LLMProvider ABC + JSON extraction + retry logic |
| `backend/app/providers/registry.py` | ProviderRegistry with auto-detection and caching |
| `backend/app/providers/errors.py` | Typed error hierarchy |
| `backend/app/providers/types.py` | CompletionRequest/Response/TokenUsage |
| `backend/app/providers/models.py` | Static model catalog |
| `backend/app/services/pipeline.py` | Pipeline orchestration (SSE generator) |
| `backend/app/middleware/auth.py` | Bearer token authentication |
| `backend/app/middleware/rate_limit.py` | Sliding window rate limiter |
| `frontend/src/lib/api/client.ts` | API client + SSE consumer + header builder |
| `frontend/src/lib/stores/provider.svelte.ts` | Provider/model/key state management |
