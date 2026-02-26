# Backend Caching

Server-side caching strategies used across the backend. All caches are in-process (no external cache service).

## Stats Cache

**Location:** `backend/app/services/stats_cache.py`

Caches the expensive `repo.get_stats()` query (10+ DB analytics across strategy distribution, score variance, combo effectiveness, time trends, etc).

| Property | Value |
|----------|-------|
| TTL | 120 seconds (`_STATS_CACHE_TTL`) |
| Key | `project_name: str \| None` — `None` for global stats |
| Storage | Module-level dict: `{key: (monotonic_timestamp, data)}` |
| Clock | `time.monotonic()` (immune to wall-clock adjustments) |

### Public API

```python
from app.services.stats_cache import get_stats_cached, invalidate_stats_cache

# Read (creates OptimizationRepository from session internally)
stats = await get_stats_cached(project_name_or_none, db_session)

# Invalidate after mutations
invalidate_stats_cache()              # clear all entries
invalidate_stats_cache("MyProject")   # clear project + global
```

### Invalidation Points

Every mutation that affects stats data calls `invalidate_stats_cache()`:

| Router/Module | Endpoints |
|---------------|-----------|
| `routers/optimize.py` | `POST /api/optimize`, `POST /api/optimize/{id}/retry` |
| `routers/history.py` | `DELETE /api/history/{id}`, `POST /api/history/bulk-delete`, `DELETE /api/history/all` |
| `routers/projects.py` | `POST /api/projects`, `DELETE /api/projects/{id}`, `POST .../archive`, `POST .../unarchive`, `DELETE .../prompts/{pid}` |
| `mcp_server.py` | `optimize`, `tag` (when project changes), `delete`, `bulk_delete`, `create_project` |

### HTTP Cache Headers

`GET /api/history/stats` returns `Cache-Control: max-age=30` — browser caches for 30 s. The server-side TTL (120 s) is longer; between 30–120 s the client re-fetches but the server serves from cache.

## Provider Staleness (Frontend)

The frontend `providerState` store has its own staleness tracking to avoid redundant fetches:

| Data | Stale After | Dedup |
|------|-------------|-------|
| Providers list | 10 s (`_PROVIDERS_STALE_MS`) | In-flight promise dedup |
| Health check | 15 s (`_HEALTH_STALE_MS`) | In-flight promise dedup |

Polling interval: 60 s. Providers list refreshes every 3rd poll tick (~180 s). Polling pauses when the browser tab is hidden (`visibilitychange` listener), resumes with a 0–2 s random jitter delay on tab restore to avoid thundering herd across tabs.

## LLM Prompt Caching

`AnthropicAPIProvider` sets `cache_control={"type": "ephemeral"}` on all API calls. Anthropic caches identical system prompts server-side for up to 5 minutes — saves up to 90% on repeated calls. Cache token metrics tracked in `TokenUsage` (`cache_creation_input_tokens`, `cache_read_input_tokens`) and persisted on the `Optimization` record.
