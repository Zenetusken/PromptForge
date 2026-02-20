# API Reference

PromptForge exposes a REST API on port 8000. Interactive documentation is available at [`/docs`](http://localhost:8000/docs) (Swagger UI) and [`/redoc`](http://localhost:8000/redoc) (ReDoc) when the backend is running.

## Authentication

When `AUTH_TOKEN` is set, all endpoints (except `/api/health`) require a `Bearer` token:

```
Authorization: Bearer <your-token>
```

## LLM Runtime Overrides

The optimize and retry endpoints accept optional headers to override the LLM provider at request time:

| Header | Description |
|--------|-------------|
| `X-LLM-API-Key` | API key override (never logged) |
| `X-LLM-Model` | Model override |
| `X-LLM-Provider` | Provider name (`anthropic`, `openai`, `gemini`) |

## Endpoints

### Optimize

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/optimize` | Start optimization pipeline (SSE stream) |
| GET | `/api/optimize/check-duplicate` | Check if a title already exists in a project |
| GET | `/api/optimize/{id}` | Get optimization by ID |
| POST | `/api/optimize/{id}/retry` | Re-run optimization with same prompt |

#### `POST /api/optimize`

Accepts a raw prompt and returns a Server-Sent Events stream with real-time progress through the pipeline stages.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | The raw prompt to optimize |
| `project` | string | No | Project name (auto-creates if needed) |
| `title` | string | No | Title for this optimization |
| `tags` | string[] | No | Tags for categorization |
| `strategy` | string | No | Override strategy selection |
| `provider` | string | No | Override LLM provider |
| `prompt_id` | string | No | Link to a project prompt by ID |

**SSE events emitted:**

| Event | Description |
|-------|-------------|
| `stage` | Pipeline stage started (analyze, strategy, optimize, validate) |
| `step_progress` | Progress message within a stage |
| `analysis` | Analysis results (task type, complexity, weaknesses, strengths) |
| `strategy` | Selected strategy with reasoning and confidence score |
| `optimization` | Optimized prompt text |
| `validation` | Scores (clarity, specificity, structure, faithfulness) and verdict |
| `complete` | Final result with all data and metadata |
| `error` | Error details (includes `error_type` and `retry_after` for rate limits) |

#### `GET /api/optimize/check-duplicate`

**Query parameters:** `title` (required), `project` (optional)

Returns `{"duplicate": true|false}`.

#### `GET /api/optimize/{id}`

Returns the full optimization record. Completed optimizations are served with `Cache-Control: max-age=3600, immutable`.

#### `POST /api/optimize/{id}/retry`

Creates a new optimization using the original prompt. Returns an SSE stream like `POST /api/optimize`.

---

### History

| Method | Path | Description |
|--------|------|-------------|
| GET/HEAD | `/api/history` | List optimizations (paginated, filterable) |
| DELETE | `/api/history/{id}` | Delete a single optimization |
| POST | `/api/history/bulk-delete` | Delete multiple optimizations by ID |
| DELETE | `/api/history/all` | Clear all history |
| GET/HEAD | `/api/history/stats` | Aggregated statistics |

#### `GET /api/history`

**Query parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | `1` | Page number |
| `per_page` | `20` | Items per page (max 100) |
| `search` | | Search in prompt text and title |
| `sort` | `created_at` | Sort field |
| `order` | `desc` | Sort order (`asc` or `desc`) |
| `project` | | Filter by project name |
| `project_id` | | Filter by project ID |
| `task_type` | | Filter by task type |
| `status` | | Filter by status |
| `include_archived` | `true` | Include items from archived projects |

#### `POST /api/history/bulk-delete`

Delete multiple optimization records in a single call.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ids` | string[] | Yes | UUIDs to delete (1–100) |

**Response:**

```json
{
  "deleted_count": 3,
  "deleted_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "not_found_ids": ["uuid-4"]
}
```

#### `DELETE /api/history/all`

Requires `X-Confirm-Delete: yes` header as a safety guard.

---

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List projects (paginated, filterable) |
| POST | `/api/projects` | Create project |
| GET | `/api/projects/{id}` | Get project with prompts |
| PUT | `/api/projects/{id}` | Update project |
| DELETE | `/api/projects/{id}` | Soft-delete project |
| POST | `/api/projects/{id}/archive` | Archive project |
| POST | `/api/projects/{id}/unarchive` | Restore archived project |

#### `GET /api/projects`

**Query parameters:** `page`, `per_page`, `search`, `status`, `sort`, `order`

#### `POST /api/projects`

**Request body:** `name` (required), `description` (optional). Returns 409 if name already exists.

#### `PUT /api/projects/{id}`

**Request body:** `name` (optional), `description` (optional). Supports optimistic concurrency via `If-Unmodified-Since` header. Returns 403 for archived projects.

---

### Prompts

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/{id}/prompts` | Add prompt to project |
| PUT | `/api/projects/{id}/prompts/reorder` | Reorder prompts |
| GET | `/api/projects/{id}/prompts/{pid}/versions` | Prompt version history |
| GET | `/api/projects/{id}/prompts/{pid}/forges` | Forge results for prompt |
| PUT | `/api/projects/{id}/prompts/{pid}` | Update prompt content |
| DELETE | `/api/projects/{id}/prompts/{pid}` | Delete prompt |

#### `POST /api/projects/{id}/prompts`

**Request body:** `content` (required)

#### `PUT /api/projects/{id}/prompts/reorder`

**Request body:** `prompt_ids` (ordered array of prompt IDs)

#### `PUT /api/projects/{id}/prompts/{pid}`

**Request body:** `content` (required). Automatically creates a version snapshot of the previous content.

---

### Providers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/providers` | List registered LLM providers with availability status |
| POST | `/api/providers/validate-key` | Test an API key against a provider |

#### `POST /api/providers/validate-key`

**Request body:** `provider` (required), `api_key` (required). Makes a minimal LLM request to verify connectivity.

---

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET/HEAD | `/api/health` | Service health check |
| GET/HEAD | `/health` | Alias for monitoring tools |

Returns database connection status, LLM provider availability, and app version.
