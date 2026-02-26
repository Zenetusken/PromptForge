# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in PromptForge, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email the maintainers with a description of the vulnerability, steps to reproduce, and any relevant details
3. Allow reasonable time for a fix before public disclosure

We aim to acknowledge reports within 48 hours and provide a fix or mitigation plan within 7 days for confirmed vulnerabilities.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest on `main` | Yes |
| Older releases | Best effort |

## Security Model Overview

PromptForge provides multiple layers of security for local and deployed environments:

- **Authentication** — Optional bearer-token auth for both the API and MCP server. Disabled by default for local development; enable via `AUTH_TOKEN` and `MCP_AUTH_TOKEN` environment variables.
- **Internal service authentication** — Service-to-service communication between the MCP server and backend is authenticated with a shared secret (`INTERNAL_WEBHOOK_SECRET`, auto-generated if not set).
- **Rate limiting** — Per-IP sliding window rate limiting on API endpoints. Configurable via `RATE_LIMIT_RPM` and `RATE_LIMIT_OPTIMIZE_RPM`.
- **CSRF protection** — Origin-based validation for state-changing requests.
- **Security headers** — Standard security headers (CSP, X-Frame-Options, X-Content-Type-Options, etc.) on all responses.
- **Input sanitization** — Prompt injection detection (warn-only mode) with pattern matching.
- **Encryption at rest** — OAuth tokens and sensitive credentials are encrypted at rest using symmetric encryption. Auto-generates a key if `ENCRYPTION_KEY` is not set.
- **Filesystem hardening** — Data directory and database file permissions are restricted to owner-only access on startup.
- **Network isolation** — MCP server binds to localhost by default (`MCP_HOST=127.0.0.1`).
- **Audit logging** — State-changing requests are logged with method, path, status, and client IP. Sensitive values (API keys, tokens) are never logged.

## Configuration

See [`.env.example`](.env.example) for all security-related environment variables and their defaults. Key variables:

- `AUTH_TOKEN` — API bearer token (empty = auth disabled)
- `MCP_AUTH_TOKEN` — MCP server bearer token (empty = auth disabled)
- `INTERNAL_WEBHOOK_SECRET` — MCP-to-backend shared secret (auto-generated if empty)
- `ENCRYPTION_KEY` — Symmetric key for token encryption (auto-generated if empty)
- `RATE_LIMIT_RPM` — General rate limit (default: 60 requests/minute)
- `RATE_LIMIT_OPTIMIZE_RPM` — Optimize endpoint rate limit (default: 10 requests/minute)

## Dependencies

We monitor dependencies for known vulnerabilities. If you identify a vulnerable dependency, please report it through the process above.
