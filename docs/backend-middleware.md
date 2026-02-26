# Backend Middleware

Request/response middleware stack for the FastAPI app. Registered in `backend/app/main.py`. Starlette LIFO order — last added = outermost (first to process requests, last to process responses).

## Stack Order (outermost → innermost)

```
GZip → SecurityHeaders → CORS → CSRF → RateLimit → Auth → Audit → Router
```

| Layer | File | Purpose |
|-------|------|---------|
| GZip | `starlette.middleware.gzip` | Compresses responses ≥1 KB. `minimum_size=1000` ensures small SSE chunks pass through uncompressed. |
| SecurityHeaders | `middleware/security_headers.py` | Adds `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, strict CSP. Relaxes CSP for Swagger/ReDoc paths. |
| CORS | `fastapi.middleware.cors` | Origins from `FRONTEND_URL` (comma-separated). Exposes `X-LLM-*`, `X-Confirm-Delete`, `If-Unmodified-Since` headers. |
| CSRF | `middleware/csrf.py` | Origin-based validation for state-changing methods (POST/PUT/DELETE/PATCH). Allows requests without `Origin` header (curl). Also allows localhost origins for API docs. |
| RateLimit | `middleware/rate_limit.py` | Per-IP sliding window (60 s). Limits from config: `RATE_LIMIT_RPM` (general), `RATE_LIMIT_OPTIMIZE_RPM` (`POST /api/optimize`). Exempts `/internal/` paths (MCP webhook traffic). Returns 429 + `Retry-After: 60`. Uses `deque` for O(1) cleanup. Stale IPs pruned every 60 s. `reset()` for testing. |
| Auth | `middleware/auth.py` | Optional bearer token. Active when `AUTH_TOKEN` config is set. Exempts `/`, `/api/health`, `/internal/` prefix, docs paths. Uses `hmac.compare_digest()`. The `/internal/` exemption allows the MCP server process (port 8001) to POST webhook events to `/internal/mcp-event` without a bearer token. |
| Audit | `middleware/audit.py` | Logs state-changing requests (POST/PUT/DELETE/PATCH): method, path, status, client IP, provider name. Logger: `promptforge.audit`. Never logs API keys. |

## Shared Utilities

| File | Export | Purpose |
|------|--------|---------|
| `middleware/__init__.py` | `get_client_ip(request)` | Extracts IP from `X-Forwarded-For` or `request.client.host`. |
| `middleware/sanitize.py` | `sanitize_prompt(text)` | Prompt injection detection (warn-only, never blocks). Strips null bytes/control chars, pattern-matches 6 injection techniques. Returns `(cleaned_text, warnings)`. |

## MCP Server Middleware Stack

The MCP server (`backend/app/mcp_server.py`) has its own Starlette middleware stack, separate from the main FastAPI app. Registered at the bottom of `mcp_server.py` using `app.add_middleware()` (LIFO order).

### Stack Order (outermost → innermost)

```
MCPAuth → SecurityHeaders → FastMCP SSE handler
```

| Layer | File | Purpose |
|-------|------|---------|
| MCPAuth | `middleware/mcp_auth.py` | Optional bearer token auth. Active when `MCP_AUTH_TOKEN` is set. Exempts `/health`. Uses `hmac.compare_digest()`. Returns 401 JSON on failure. When token is empty, all requests pass through (development mode). |
| SecurityHeaders | `middleware/security_headers.py` | Same headers as the main backend — `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, strict CSP. |

The MCP server does not use CORS, CSRF, rate-limiting, or audit middleware — it is consumed by trusted MCP clients (Claude Code), not browsers.
