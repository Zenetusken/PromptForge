# Context System

How project knowledge flows from storage through resolution, rendering, and into all 4 LLM pipeline stages. Covers the Kernel Knowledge Base, context resolution, budget allocation, snapshot storage, and frontend display.

## Architecture Overview

```
 ┌──────────────────────────────────────────────────────────┐
 │            Kernel Knowledge Base Resolution               │
 │                                                          │
 │  KnowledgeRepository.resolve("promptforge", project_id)  │
 │    → Profile: language, framework, description,          │
 │      test_framework (manual > auto_detected merge)       │
 │    → Metadata: conventions, patterns, test_patterns      │
 │      (app-specific, stored in metadata_json)             │
 │    → Sources: enabled Knowledge Sources (kernel table)   │
 │                                                          │
 │  codebase_context_from_kernel(resolved)                  │
 │    Maps kernel profile → CodebaseContext                  │
 └────────────────────────┬─────────────────────────────────┘
                          │
                          ▼ kernel CodebaseContext
 ┌──────────────────────────────────────────────────────────┐
 │           Per-Request Override (optional)                 │
 │                                                          │
 │  codebase_context_from_dict(request.codebase_context)    │
 │  (explicit dict in POST /optimize or /retry body)        │
 │                                                          │
 │  merge_contexts(kernel_ctx, explicit)                    │
 │  → scalars: override replaces if truthy                  │
 │  → lists: override replaces entirely if non-empty        │
 └────────────────────────┬─────────────────────────────────┘
                          │
                          ▼ resolved CodebaseContext
 ┌──────────────────────────────────────────────────────────┐
 │          Rendered Output (80K char budget)                │
 │                                                          │
 │  ## Project Identity                                     │
 │    description, language, framework, documentation       │
 │                                                          │
 │  ## Knowledge Sources              ← 50K char budget     │
 │    ### [1] Architecture Doc                              │
 │    ### [2] API Reference                                 │
 │    ### [3] Meeting Notes                                 │
 │    (proportional per-source truncation)                  │
 │                                                          │
 │  ## Technical Details                                    │
 │    conventions, patterns, code snippets, test patterns   │
 └────────────────────────┬─────────────────────────────────┘
                          │
                          ▼ injected into user message
               Analyze → Strategy → Optimize → Validate
```

## Kernel Knowledge Base

The Knowledge Base is a **kernel-level service** shared across all apps. It replaces the previous PromptForge-specific three-layer context merge with a unified storage model.

### Storage Model

Two kernel tables store all project knowledge:

- **`kernel_knowledge_profiles`** — Project identity (language, framework, description, test_framework) + app-specific metadata (`metadata_json`) + workspace auto-detected fields (`auto_detected_json`)
- **`kernel_knowledge_sources`** — Reference documents (title, content, source_type, enabled toggle, ordering) linked to profiles via FK

### Resolution Rule

`KnowledgeRepository.resolve(app_id, entity_id)` returns merged profile + enabled sources:
- Profile fields: explicit column wins if non-null/non-empty, else falls back to same key in `auto_detected_json`
- Sources: all enabled sources ordered by `order_index`
- Returns: `{"profile": {id, app_id, entity_id, name, language, framework, description, test_framework, created_at, updated_at}, "metadata": {...}, "auto_detected": {...}, "sources": [...]}`

### Migration from Legacy System

PromptForge's previous three-layer system (workspace → project context_profile → per-request) was consolidated:
- **Layer 1 (workspace auto-context)** → `auto_detected_json` on kernel profile
- **Layer 2 (project context_profile)** → kernel profile identity fields + `metadata_json` for app-specific hints
- **Layer 3 (per-request)** → unchanged, still works as explicit override via `merge_contexts()`
- **Knowledge Sources** → migrated from `project_sources` table to `kernel_knowledge_sources`
- **documentation** field → promoted to a Knowledge Source (type=document) during migration
- **code_snippets** field → promoted to individual Knowledge Sources (type=paste) during migration

## Constants

Defined in `apps/promptforge/schemas/context.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_CONTEXT_CHARS` | 80,000 | Total rendered output budget. Truncated with `... (truncated)` marker |
| `_SOURCE_BUDGET_CHARS` | 50,000 | Budget allocated to Knowledge Sources tier |
| `_SNAPSHOT_SOURCE_CONTENT_CHARS` | 5,000 | Per-source content limit in DB snapshots |
| `MAX_SOURCES_PER_PROJECT` | 50 | Max knowledge sources per project (enforced in repository) |
| `MAX_SOURCE_CONTENT_CHARS` | 100,000 | Max chars per individual source document |

## Data Structures

### CodebaseContext (Python dataclass)

```python
@dataclass
class CodebaseContext:
    language: str | None = None
    framework: str | None = None
    description: str | None = None
    conventions: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    code_snippets: list[str] = field(default_factory=list)  # deprecated — use Knowledge Sources
    documentation: str | None = None                         # deprecated — use Knowledge Sources
    test_framework: str | None = None
    test_patterns: list[str] = field(default_factory=list)
    sources: list[SourceDocument] = field(default_factory=list)
```

The class name `CodebaseContext` is preserved for backward compatibility with existing API field names (`codebase_context`), DB columns (`codebase_context_snapshot`), and Python parameter names. Despite the name, it serves as a general-purpose project knowledge source.

**Deprecated fields:** `documentation` and `code_snippets` are superseded by Knowledge Sources. They are not populated from kernel data (see `codebase_context_from_kernel()`), but remain in the dataclass for backward compatibility with existing snapshots and per-request overrides from older API clients.

### SourceDocument (Python dataclass)

```python
@dataclass
class SourceDocument:
    title: str
    content: str
    source_type: str = "document"
```

### SourceType (Python StrEnum)

Defined in `apps/promptforge/models/source.py`:

| Value | Description |
|-------|-------------|
| `document` | General reference document (default) |
| `paste` | Pasted content snippet |
| `api_reference` | API documentation |
| `specification` | Product or technical specification |
| `notes` | Meeting notes, design notes, etc. |

### Frontend TypeScript

```typescript
interface ContextSourceDocument {
    title: string;
    content: string;
    source_type?: string;
}

interface CodebaseContext {
    language?: string;
    framework?: string;
    description?: string;
    conventions?: string[];
    patterns?: string[];
    code_snippets?: string[];    // deprecated — use Knowledge Sources
    documentation?: string;       // deprecated — use Knowledge Sources
    test_framework?: string;
    test_patterns?: string[];
    sources?: ContextSourceDocument[];
}
```

## Context Resolution

### resolve_project_context()

Implemented in `apps/promptforge/services/context_resolver.py`. The single entry point for resolving project context, shared by both REST endpoints and MCP tools.

```python
async def resolve_project_context(
    db: AsyncSession,
    project_name: str | None,
    explicit_dict: dict[str, Any] | None = None,
) -> CodebaseContext | None:
```

**Resolution steps:**

1. Parse `explicit_dict` via `codebase_context_from_dict()` → per-request `CodebaseContext | None`
2. If `project_name` is given:
   a. Look up project by name → get project ID
   b. Try kernel Knowledge Base: `KnowledgeRepository(db).resolve("promptforge", project.id)` → `codebase_context_from_kernel(resolved)`
   c. If no kernel profile, fall back to legacy three-layer: `workspace_context` → `context_profile` → legacy `project_sources`
3. Merge: `merge_contexts(kernel_ctx, explicit)` — per-request override wins

### REST Router Delegation

`_resolve_context()` in `routers/optimize.py` is a thin wrapper that delegates to `resolve_project_context()`. Called by `POST /optimize`, `POST /optimize/{id}/retry`, `POST /optimize/batch`, and all `/orchestrate/*` endpoints.

`_resolve_orchestration_context()` creates its own DB session when a project name is provided, delegates to `_resolve_context()`. Falls back to explicit-only (`codebase_context_from_dict`) when no project is given.

### Merge Logic

`merge_contexts(base, override)` applies field-level replacement:
- **Scalars** (`language`, `framework`, `description`, `documentation`, `test_framework`): override's value replaces base's if truthy (non-None, non-empty string)
- **Lists** (`conventions`, `patterns`, `code_snippets`, `test_patterns`, `sources`): override's list replaces base's entirely if non-empty (no concatenation — avoids duplicates)
- Returns a shallow copy (`dataclasses.replace`) to prevent aliasing
- Returns `None` if both inputs are `None`

### Knowledge Sources

Sources are resolved from the kernel `kernel_knowledge_sources` table during `KnowledgeRepository.resolve()`. They are included in the kernel context and mapped to `SourceDocument` objects by `codebase_context_from_kernel()`. Sources with empty title or content are filtered out during the mapping.

Sources can be overridden by per-request `codebase_context.sources` via `merge_contexts()` (the override list replaces entirely if non-empty).

### codebase_context_from_kernel()

Maps a kernel `resolve()` result dict → `CodebaseContext`:

| Kernel field | CodebaseContext field |
|---|---|
| `profile.language` | `language` |
| `profile.framework` | `framework` |
| `profile.description` | `description` |
| `profile.test_framework` | `test_framework` |
| `metadata.conventions` | `conventions` |
| `metadata.patterns` | `patterns` |
| `metadata.test_patterns` | `test_patterns` |
| `sources[*]` | `sources` (as `SourceDocument` objects) |

**Not populated from kernel:** `documentation`, `code_snippets` (deprecated — replaced by Knowledge Sources).

Returns `None` if every field ends up empty.

## Rendering

`CodebaseContext.render()` produces a formatted text block injected into LLM user messages. Returns `None` when all fields are empty.

### Render Tiers

**Tier 1 — Project Identity** (always relevant, even for non-coding prompts):
```
## Project Identity
Project description: {description}
Language: {language}
Framework: {framework}
Documentation:
{documentation}
```

**Tier 2 — Knowledge Sources** (inserted between Identity and Technical Details):
```
## Knowledge Sources

### [1] Architecture Doc
{content, truncated to per_source budget}

### [2] API Reference
{content, truncated to per_source budget}
```

Budget allocation: `per_source = _SOURCE_BUDGET_CHARS (50K) // len(enabled_sources)`. Sources with empty content are filtered out before budget division. Content exceeding the per-source share is truncated with a `\n... (truncated)` marker.

**Tier 3 — Technical Details** (relevant for coding/technical tasks):
```
## Technical Details
Conventions:
  - {convention_1}
  - {convention_2}

Architectural patterns:
  - {pattern_1}

Code snippets:
{snippet_1}
---
{snippet_2}

Test framework: {test_framework}

Test patterns:
  - {test_pattern_1}
```

### Final Truncation

After all tiers are joined with `\n\n`, the total output is truncated to `MAX_CONTEXT_CHARS` (80K):

```python
if len(rendered) > MAX_CONTEXT_CHARS:
    rendered = rendered[:MAX_CONTEXT_CHARS] + "\n... (truncated)"
```

## Pipeline Injection

The resolved `CodebaseContext` is passed as `codebase_context` to all 4 pipeline stages.

### Stage 1: Analyzer

```python
result = await PromptAnalyzer(provider).analyze(raw_prompt, codebase_context=context)
```

Context is rendered and appended to the user message:
```
Analyze the following prompt...
---
{raw_prompt}
---

The user has attached the following project context as a knowledge source
for this optimization:

{context.render()}
```

**LLM directive** (`analyzer_prompt.py`): Notes whether the prompt is ABOUT the source material or merely adjacent to it. Flags missing project context as a weakness; notes correct project terminology as a strength.

### Stage 2: Strategy Selector

```python
result = await StrategySelector(provider).select(
    analysis, raw_prompt=prompt, prompt_length=len(prompt), codebase_context=context,
)
```

Context influences strategy selection through heuristic confidence boosts:
- Rich description (>50 chars) → `context-enrichment` +0.05
- Strict type system keywords → `structured-output` +0.05
- Domain-specific keywords → `persona-assignment` +0.05
- Multi-layer architectural patterns → `step-by-step` +0.05

For LLM-based selection, rendered context is included in the JSON payload as `project_context`.

**LLM directive** (`strategy_prompt.py`): When Knowledge Sources are present, ALWAYS strengthens case for `context-enrichment` as a secondary framework. Knowledge sources are treated as "highest-signal context available."

### Stage 3: Optimizer

```python
result = await PromptOptimizer(provider).optimize(
    raw_prompt, analysis, strategy,
    secondary_frameworks=secondary_frameworks, codebase_context=context,
)
```

Rendered context is injected as `project_context` in the JSON user message payload.

**LLM directive** (`optimizer_prompts.py`, Section E): When `## Knowledge Sources` appears:
- Cross-reference between sources — synthesize across multiple documents
- Cite by source title when referencing specific information
- Prioritize sources over general knowledge — the user uploaded them for a reason
- Handle source conflicts — note discrepancies, prefer the more specific source
- Don't summarize sources back — weave insights into the optimized prompt naturally

### Stage 4: Validator

```python
result = await PromptValidator(provider).validate(
    raw_prompt, optimized_prompt, strategy=strategy, codebase_context=context,
)
```

Context calibrates scoring:
- **Faithfulness**: Higher when optimized prompt correctly references project identity; lower when context describes a specific product but prompt uses generic examples
- **Knowledge Sources scoring**: Higher when optimized prompt grounds in source material (source-specific terminology, examples, details); lower when sources provide specific information but the prompt uses generic alternatives

**LLM directive** (`validator_prompt.py`): General scoring calibration targets 0.70–0.85 for well-optimized prompts across all dimensions; scores above 0.90 are exceptional and require explicit justification in the verdict.

## Snapshot Storage

When an optimization is created, the resolved context (including sources) is snapshotted:

```python
if resolved_context:
    ctx_dict = context_to_dict(resolved_context)
    if ctx_dict:
        optimization.codebase_context_snapshot = json.dumps(ctx_dict)
```

### Serialization (`context_to_dict`)

- Converts `CodebaseContext` to a dict, filtering out empty/None fields
- Source content is truncated to `_SNAPSHOT_SOURCE_CONTENT_CHARS` (5K) per source to prevent DB bloat
- The LLM already saw the full budget-truncated version during pipeline execution
- Returns `None` if all fields are empty after filtering

```python
# Snapshot source format:
{"title": "Architecture Doc", "content": "{first 5K chars}", "source_type": "document"}
```

### Deserialization (`codebase_context_from_dict`)

- Unknown keys silently ignored (forward compatibility)
- Scalar fields coerced to `str` (guards against `{"language": 42}`)
- List fields: `str` → `[str]`, list items → `str`, invalid types dropped
- Sources: requires both `title` and `content` to be truthy; `source_type` defaults to `"document"`
- Non-dict input returns `None`

## Database Models

### kernel_knowledge_profiles table (kernel)

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID |
| `app_id` | TEXT NOT NULL | "promptforge", "textforge", etc. |
| `entity_id` | TEXT NOT NULL | App-specific ref (e.g., project ID) |
| `name` | TEXT NOT NULL | Human-readable label |
| `language` | TEXT | Manual or auto-detected |
| `framework` | TEXT | Manual or auto-detected |
| `description` | TEXT | Manual or auto-detected |
| `test_framework` | TEXT | Manual or auto-detected |
| `metadata_json` | TEXT | App-specific extensions as JSON (conventions, patterns, test_patterns) |
| `auto_detected_json` | TEXT | Workspace auto-fill (shadow fields, lower priority) |
| `created_at` | TIMESTAMP NOT NULL | |
| `updated_at` | TIMESTAMP NOT NULL | |

UNIQUE constraint on `(app_id, entity_id)`. Indexes: `ix_knowledge_profiles_app_id`, `ix_knowledge_profiles_entity`.

Resolution rule: explicit column wins if non-null/non-empty, else fall back to same key in `auto_detected_json`.

### kernel_knowledge_sources table (kernel)

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID |
| `profile_id` | TEXT FK | → `kernel_knowledge_profiles(id)` ON DELETE CASCADE |
| `title` | TEXT NOT NULL | 1–200 chars |
| `content` | TEXT NOT NULL | Up to 100K chars |
| `source_type` | TEXT NOT NULL | Default `'document'` |
| `char_count` | INTEGER NOT NULL | Pre-computed `len(content)` |
| `enabled` | BOOLEAN NOT NULL | Default `True`. Toggle without deleting |
| `order_index` | INTEGER NOT NULL | Ordering within profile |
| `created_at` | TIMESTAMP NOT NULL | |
| `updated_at` | TIMESTAMP NOT NULL | |

Indexes: `ix_knowledge_sources_profile_id`, `ix_knowledge_sources_enabled (profile_id, enabled)`.

### Legacy tables (kept for Phase 4 cleanup)

| Table | Column | Type | Purpose |
|-------|--------|------|---------|
| `project_sources` | *(all)* | *(all)* | Legacy source table — kernel tables are authoritative |
| `projects` | `context_profile` | TEXT (JSON) | Legacy manual context profile |
| `workspace_links` | `workspace_context` | TEXT (JSON) | Legacy auto-extracted context |
| `optimizations` | `codebase_context_snapshot` | TEXT (JSON) | Frozen snapshot at optimization time (still active) |

## REST API

### Kernel Knowledge Base Endpoints

Shared kernel endpoints at `/api/kernel/knowledge/`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{app_id}/{entity_id}` | Resolve profile + sources (merged identity + metadata + enabled sources) |
| `PUT` | `/{app_id}/{entity_id}` | Create/update profile fields. Uses `exclude_unset=True` — explicit `null` clears a field, omitted fields are unchanged |
| `DELETE` | `/{app_id}/{entity_id}` | Delete profile + cascade sources |
| `POST` | `/{app_id}/{entity_id}/sync` | Update `auto_detected_json` (workspace auto-fill) |
| `GET` | `/{app_id}/{entity_id}/sources` | List sources. Query: `?enabled_only=true` |
| `POST` | `/{app_id}/{entity_id}/sources` | Add source. Enforces `MAX_SOURCES` (50) |
| `PATCH` | `/sources/{source_id}` | Update source title/content/enabled |
| `DELETE` | `/sources/{source_id}` | Delete source |
| `POST` | `/sources/{source_id}/toggle` | Toggle enabled/disabled |
| `PUT` | `/{app_id}/{entity_id}/sources/reorder` | Reorder by ID list |

**Response shapes:**

- `GET /{app_id}/{entity_id}` → `{"profile": {...identity fields...}, "metadata": {...}, "auto_detected": {...}, "sources": [...]}`
- `GET /.../sources` → `{"items": [...], "total": int, "total_chars": int}`
- `PUT /{app_id}/{entity_id}` → flat profile dict with `metadata` and `auto_detected` parsed from JSON. Body uses `exclude_unset=True` semantics: send `{"language": null}` to clear a field, omit fields to leave them unchanged. (Frontend sends `null` for empty strings.)
- `POST /.../sources` → source dict with `id`, `title`, `content`, `source_type`, `char_count`, `enabled`, `order_index`
- `POST /sources/{source_id}/toggle` → updated source dict
- `DELETE /sources/{source_id}` → `{"deleted": true, "id": "..."}`

### Context Preview Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/apps/promptforge/context/preview` | Preview resolved context before forging |

**Request:** `ContextPreviewRequest` — `{ project: str | null, codebase_context: dict | null }`

**Response:** `{ context: dict | null, field_count: int, rendered_chars: int }`

Read-only, no LLM calls, uses `get_db_readonly`. Calls `resolve_project_context()` from `services/context_resolver.py`.

### PromptForge Source CRUD (Proxy)

PromptForge-specific endpoints at `/api/apps/promptforge/projects/{project_id}/sources` proxy to the kernel Knowledge Base:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/projects/{project_id}/sources` | Create source → kernel `create_source` |
| `GET` | `/projects/{project_id}/sources` | List sources → kernel `list_sources` |
| `GET` | `/projects/{project_id}/sources/{source_id}` | Get single source → kernel `get_source` |
| `PATCH` | `/projects/{project_id}/sources/{source_id}` | Update → kernel `update_source` |
| `DELETE` | `/projects/{project_id}/sources/{source_id}` | Delete → kernel `delete_source` |
| `POST` | `/projects/{project_id}/sources/{source_id}/toggle` | Toggle → kernel toggle logic |
| `PUT` | `/projects/{project_id}/sources/reorder` | Reorder → kernel `reorder_sources` |

All mutation endpoints validate: project exists, not deleted, not archived.

### Project List `has_context` Computation

The `GET /api/apps/promptforge/projects` endpoint enriches each project with a `has_context` flag and `source_count`. These drive frontend auto-resolve triggers and green-dot visual indicators.

`_kernel_knowledge_batch(db, project_ids)` in `routers/projects.py` performs a batch lookup returning:
- `dict[str, int]` — source counts per project ID (via `KnowledgeRepository.get_source_counts()`)
- `set[str]` — project IDs that have a kernel knowledge profile (even if empty)

The `has_context` flag is computed as:
```python
has_context = bool(p.context_profile) or p.id in has_kernel_profile
```

This dual check ensures projects with kernel-only knowledge (set via ProjectsWindow identity fields or kernel API) appear correctly in the UI. Without the kernel profile check, only legacy `context_profile` projects would trigger auto-resolve and visual indicators.

### Context in Optimize Endpoints

| Endpoint | Context Resolution |
|----------|-------------------|
| `POST /optimize` | `resolve_project_context(db, project, body.codebase_context)` via `_resolve_context()` |
| `POST /optimize/{id}/retry` | Same (re-resolves fresh from current state) |
| `POST /optimize/batch` | Same (resolved once, shared across batch) |
| `POST /orchestrate/analyze` | `_resolve_orchestration_context()` — own session when project given |
| `POST /orchestrate/strategy` | Same |
| `POST /orchestrate/optimize` | Same |
| `POST /orchestrate/validate` | Same |

## MCP Tools

### Source management (tools 23–26)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `add_source` | `project_id` (UUID, required), `title` (1–200 chars, required), `content` (1–100K chars, required), `source_type?` (default `"document"`) | Create a knowledge source. Enforces `MAX_SOURCES` (50). Returns source dict. |
| `update_source` | `source_id` (UUID, required), `title?` (1–200 chars), `content?` (1–100K chars), `enabled?` (bool) | Update source fields. Returns updated source dict. |
| `delete_source` | `source_id` (UUID, required) | Permanently delete. Returns `{"deleted": true, "id": "..."}`. |
| `list_sources` | `project_id` (UUID, required), `enabled_only?` (bool) | List sources. Returns `{"items": [...], "total": int, "total_chars": int}`. Items include `id`, `title`, `source_type`, `char_count`, `enabled`, `order_index` (no full content). |

All validate project existence and archived status. Delegate to `KnowledgeRepository` via kernel tables.

### Context-related tools

| Tool | Context behavior |
|------|-----------------|
| `optimize` | Accepts `codebase_context` dict + `project` name → `resolve_project_context()` (kernel resolve + per-request override) |
| `retry` | Accepts `codebase_context` override → `resolve_project_context()` for original project |
| `batch` | Accepts `codebase_context` + `project` → `resolve_project_context()` once for batch |
| `set_project_context` | Writes identity fields to kernel profile + `metadata_json` for app-specific hints (conventions, patterns, test_patterns). Uses shared `_sync_context_to_kernel()` helper. |
| `sync_workspace` | Writes `auto_detected_json` to kernel profile (workspace auto-fill) |
| `create_project` | When `context_profile` is provided, dual-writes to both legacy `context_profile` column and kernel profile via `_sync_context_to_kernel()` |

## Event System

### Backend Event Contracts

Defined in `kernel/events/knowledge.py`. Published by kernel knowledge router endpoints on mutations.

| Backend event name | Payload schema | Trigger |
|---|---|---|
| `kernel:knowledge.profile_updated` | `ProfileUpdatedPayload` (profile_id, app_id, entity_id, changed_fields) | PUT profile, POST sync |
| `kernel:knowledge.source_added` | `SourceAddedPayload` (source_id, profile_id, title, source_type) | POST source |
| `kernel:knowledge.source_updated` | `SourceUpdatedPayload` (source_id, profile_id, changed_fields) | PATCH source, POST toggle, PUT reorder |
| `kernel:knowledge.source_removed` | `SourceRemovedPayload` (source_id, profile_id) | DELETE source |

### Frontend Bus Bridge

Backend sends events with **dots** (e.g., `kernel:knowledge.profile_updated`). The `KernelBusBridge` SSE client maps them to **underscores** for the frontend `SystemBus`:

| Backend (dots) | Frontend SystemBus (underscores) |
|---|---|
| `kernel:knowledge.profile_updated` | `kernel:knowledge_profile_updated` |
| `kernel:knowledge.source_added` | `kernel:knowledge_source_added` |
| `kernel:knowledge.source_updated` | `kernel:knowledge_source_updated` |
| `kernel:knowledge.source_removed` | `kernel:knowledge_source_removed` |

Mapping is in `EVENT_TYPE_MAP` in `frontend/src/lib/kernel/services/kernelBusBridge.svelte.ts`.

## Frontend Integration

### Kernel Knowledge Service

`frontend/src/lib/kernel/services/knowledge.svelte.ts` — reactive kernel client following `appSettings.svelte.ts` pattern. Exported as a singleton: `export const knowledge = new KnowledgeService()`.

**Caches:** Three `$state` caches keyed by `"appId:entityId"`:
- `_profiles`: `Record<string, KnowledgeProfile | null>` — profile data
- `_sources`: `Record<string, KnowledgeSource[]>` — source lists
- `_loading`: `Record<string, boolean>` — loading states

**Public methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `getCachedProfile` | `(appId, entityId) → KnowledgeProfile \| null` | Synchronous cache read |
| `getCachedSources` | `(appId, entityId) → KnowledgeSource[]` | Synchronous cache read (empty if not loaded) |
| `isLoading` | `(appId, entityId) → boolean` | Check if fetch is in progress |
| `getProfile` | `(appId, entityId) → Promise<KnowledgeProfile \| null>` | Fetch from backend resolve endpoint; populates profile + source caches |
| `updateProfile` | `(appId, entityId, fields) → Promise<KnowledgeProfile>` | PUT identity fields (name, language, framework, description, test_framework) + `metadata_json` for metadata writes |
| `getSources` | `(appId, entityId, opts?) → Promise<KnowledgeSource[]>` | List sources; supports `{enabledOnly: true}` |
| `addSource` | `(appId, entityId, data) → Promise<KnowledgeSource>` | Create source; appends to cache |
| `updateSource` | `(sourceId, data) → Promise<KnowledgeSource>` | PATCH source; updates cache in-place |
| `deleteSource` | `(sourceId) → Promise<void>` | DELETE source; removes from cache |
| `toggleSource` | `(sourceId) → Promise<KnowledgeSource>` | Toggle enabled; updates cache |
| `invalidate` | `(appId, entityId) → void` | Clear cache entries for an entity |

Calls `/api/kernel/knowledge/*` REST endpoints. URL path segments are encoded via `encodeURIComponent()`.

### ForgeContextSection.svelte

Displays in the Forge IDE compose panel. Flat single-level layout with four sections:

**1. Identity line** — Compact inline badges loaded from kernel knowledge profile when a project is matched:
- Language badge (neon-purple), Framework badge (neon-purple)
- Test framework badge (neon-green) from `ctxTestFramework`
- Source count with file-text icon (derives from `knowledge.getCachedSources()` with fallback to `projectsState.allItems[...].source_count`)

**2. Four editable fields** — Always visible, synced to `forgeSession.draft.contextProfile`:
- Conventions (textarea, one per line)
- Patterns (textarea, one per line)
- Test Framework (text input)
- Test Patterns (textarea, one per line)

**3. Action row** — `<select>` dropdown for stack templates + Clear button:
- Template select populates the 4 hint fields; deselecting clears template association but keeps fields
- Clear button resets all fields, identity state, and preview data

**4. Auto-fetching resolved summary** — Debounced (600ms) preview that loads automatically when the section is open:
- Calls `fetchContextPreview(project, contextProfile, signal)` → `POST /context/preview`
- Shows resolved field count, character estimate, and compact text digest (identity + counts)
- Uses `AbortController` to cancel stale requests on rapid changes
- No manual button or nested collapsible

**Trigger badge:** Shows `N fields · XK` in neon-green when preview data is populated (uses shared `formatChars()` from `utils/safe.ts`); falls back to green dot when hint fields have manual data.

**Auto-resolve:** When `forgeSession.draft.project` changes, `loadAndApplyProjectContext()` is called. It:
1. Fetches the kernel profile via `knowledge.getProfile()` → populates identity badges (language, framework + source count)
2. Fetches legacy `context_profile` via `fetchProject()` → populates hint fields if present
3. **Kernel metadata fallback:** When no legacy `context_profile` exists but a kernel profile does, builds hint context from `kernelProfile.metadata` (`conventions`, `patterns`, `test_patterns`) and `kernelProfile.test_framework`.

**Key functions:**
- `syncContextToDraft()` — exports 4 hint fields to `forgeSession.draft.contextProfile`
- `applyContext(ctx, source, templateId?)` — applies template or project hint data
- `clearContext()` — resets all fields, identity state, and preview data
- `loadAndApplyProjectContext(projectId)` — fetches kernel + legacy data, applies identity badges and hint fields

### ProjectsWindow.svelte Knowledge Panel

Displayed at project root level (`isProjectRoot && activeFolderId`). Three collapsible sections:

**1. Project Knowledge** (identity fields):
- Language input with "auto" badge when value came from `auto_detected_json`
- Framework input with "auto" badge
- Description textarea
- Test Framework input
- All save on blur via `knowledge.updateProfile('promptforge', entityId, {field: value.trim() || null})` — sends `null` for empty strings to clear the field on the backend
- Disabled when project status is not "active"
- Loads kernel profile via `knowledge.getProfile()` when navigating to project root

**2. Technical Hints** (metadata fields):
- Conventions textarea (one per line)
- Patterns textarea (one per line)
- Test Patterns textarea (one per line)
- Save on blur via `saveHintField(field, value)` — read-modify-write to `metadata_json` to avoid clobbering other metadata keys
- Collapsible header shows item count when any hints are set
- Disabled when project status is not "active"

**Context coverage bar** (list view only):
- Shows above the FileManagerView: "Context: X/Y projects · Z sources"
- Derived from `projectsState.items` — counts `has_context || source_count > 0` for active projects
- Color: green (>50%), yellow (>0%), dim (0)

**3. Knowledge Sources** (SourceManager embed):
```svelte
<SourceManager appId="promptforge" entityId={activeFolderId}
    projectStatus={activeProjectStatus} />
```

### SourceManager.svelte

Embedded in ProjectsWindow for source CRUD. **Backed by kernel Knowledge Service** (not PromptForge-specific endpoints).

**Props:**
```typescript
interface Props {
    appId: string;       // "promptforge"
    entityId: string;    // project ID
    projectStatus?: string;  // "active" | "archived" | "deleted"
}
```

**Features:**
- Source list with title, type badge (Doc/Paste/API/Spec/Notes), char count, enabled/disabled toggle (eye icon), edit and delete buttons, clickable title expands inline content preview
- Expand-in-place: click source title to toggle `previewId`, shows `<pre>` with content truncated to 2K chars, max-h-48 scroll; clicking edit clears preview
- Add form: title input (maxlength 200) + type selector (5 options) + content textarea (monospace) + char count display
- Edit: in-place editor with title input + content textarea + save/cancel buttons
- Budget bar: visual `totalChars / 100K` indicator with neon-orange warning at 80%+
- Read-only when `projectStatus !== "active"` (disables add/toggle/edit/delete)
- Disabled source appearance: 50% opacity
- Empty state: "No sources yet. Add reference documents to ground your prompts."

**API calls** (all via `knowledge` singleton):
- `loadSources()` → `knowledge.getSources(appId, entityId)`
- `handleAdd()` → `knowledge.addSource(appId, entityId, {...})`
- `handleDelete(id)` → `knowledge.deleteSource(id)`
- `handleToggle(id)` → `knowledge.toggleSource(id)`
- `saveEdit()` → `knowledge.updateSource(editingId, {...})`
- Reloads on `entityId` change via `$effect`

### WorkspaceWindow.svelte Context Inspector

The "Context Inspector" tab is a fully editable knowledge profile editor for the selected workspace's linked project. Mirrors the ProjectsWindow knowledge panel pattern.

**Profile loading:** When `selectedWorkspace` changes, loads the kernel profile via `knowledge.getProfile('promptforge', ws.project_id)` and unpacks into editable `$state` variables (`inspLanguage`, `inspFramework`, `inspDescription`, `inspTestFramework`, `inspConventions`, `inspPatterns`, `inspTestPatterns`).

**Editable fields:**
- **Identity fields** (language, framework, description, test_framework): `<input>`/`<textarea>` with `onblur` → `saveInspectorIdentity(field, value)` → `knowledge.updateProfile()`. Focus border accent: neon-purple.
- **Hint fields** (conventions, patterns, test_patterns): `<textarea>` (one item per line) with `onblur` → `saveInspectorHint(field, value)` → splits by newline, reads current metadata via `getCachedProfile`, merges, writes via `knowledge.updateProfile({ metadata_json })`. Focus border accent: neon-green.

**Auto-detect badges:** When an identity field is empty and `inspAutoDetected[field]` exists, a small "auto" label appears inside the input (neon-green/50). Manual values always override.

**Completeness bar:** `inspectorCompleteness` derived from the 7 local editable state variables (counts non-empty trimmed values). Updates reactively as the user types — no stale profile dependency.

**Knowledge Sources:** `SourceManager` component embedded with `appId="promptforge"` and `entityId={selectedWorkspace.project_id}`, providing full source CRUD inline.

### ContextSnapshotPanel.svelte

Displays in the review panel for completed optimizations. Renders the `codebase_context_snapshot` from the optimization record. Shows historical data as frozen at optimization time.

- Shows `{fieldCount}/9 fields` badge (counts non-empty fields including deprecated ones)
- Scalar badges for language, framework, test framework
- Description as text paragraph
- Lists for conventions, patterns, test patterns (as inline tags)
- Code snippets as monospace `<pre>` blocks (from legacy snapshots)
- Documentation as monospace `<pre>` truncated to 500 chars (from legacy snapshots)
- **Knowledge Sources section**: Source titles as neon-cyan tags, with expandable `<details>` for content preview (truncated to 500 chars in UI, already truncated to 5K in snapshot)

## KnowledgeRepository API

Full public API in `kernel/repositories/knowledge.py`:

### Profile Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_profile` | `(app_id, entity_id) → dict \| None` | Raw fields, no auto-merge |
| `get_profile_by_id` | `(profile_id) → dict \| None` | Lookup by primary key |
| `get_or_create_profile` | `(app_id, entity_id, name) → dict` | Auto-create if missing |
| `update_profile` | `(profile_id, **fields) → dict` | Update identity + metadata_json |
| `update_auto_detected` | `(profile_id, auto_fields) → dict` | Workspace sync (shadow fields) |
| `delete_profile` | `(profile_id) → bool` | Cascade deletes all sources |
| `list_profiles` | `(app_id) → list[dict]` | All profiles for an app |
| `resolve_profile` | `(app_id, entity_id) → dict \| None` | Manual > auto merge on identity fields |
| `resolve` | `(app_id, entity_id) → dict \| None` | resolve_profile + enabled sources |

### Source Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `list_sources` | `(profile_id, enabled_only=False) → list[dict]` | Ordered by order_index |
| `get_source` | `(source_id) → dict \| None` | Single source by ID |
| `create_source` | `(profile_id, title, content, source_type="document") → dict` | Auto-sets order_index, char_count |
| `update_source` | `(source_id, **fields) → dict` | Mutable: title, content, source_type, enabled |
| `delete_source` | `(source_id) → bool` | Permanent delete |
| `reorder_sources` | `(profile_id, source_ids) → None` | All source IDs must be provided |
| `get_source_count` | `(profile_id) → int` | Single profile count |
| `get_source_counts` | `(profile_ids) → dict[str, int]` | Batch counts via GROUP BY |
| `get_total_char_count` | `(profile_id) → int` | Sum of all char_counts |

## Key Invariants

1. **Sources always flow through all 4 stages**: Enabled sources are resolved from kernel tables and passed as `codebase_context` to every pipeline stage.
2. **Project Identity is always relevant**: Description, language, framework, and documentation are included regardless of prompt type (coding, writing, creative, analysis).
3. **Kernel profile resolution merges manual > auto**: Explicit profile columns win if non-null/non-empty; `auto_detected_json` fields are fallback-only.
4. **Per-source budget is proportional**: `50K / N` chars per source. No single source can starve others.
5. **Per-request override is last**: Kernel resolve (lowest) < Explicit Request (highest). Override's non-empty fields replace kernel-resolved values.
6. **Lists replace, never concatenate**: Override lists entirely replace base lists to avoid duplicates.
7. **Snapshots preserve history**: The resolved context at optimization time is frozen in `codebase_context_snapshot`, enabling historical comparison and audit.
8. **Snapshot truncation prevents bloat**: Source content limited to 5K per source in snapshots. The LLM saw the full budget-truncated version.
9. **Knowledge is kernel-level**: All project knowledge lives in `kernel_knowledge_profiles` and `kernel_knowledge_sources` tables, accessible to any app via `KnowledgeRepository`.
10. **Data migration is non-destructive**: Legacy tables (`project_sources`, `projects.context_profile`, `workspace_links.workspace_context`) are kept intact until Phase 4 cleanup.
11. **Single resolution entry point**: Both REST and MCP paths use `resolve_project_context()` from `services/context_resolver.py` — no duplication.
12. **Deprecated fields preserved for compatibility**: `documentation` and `code_snippets` remain in `CodebaseContext` for old snapshots and API clients, but are not populated from kernel data.
13. **`has_context` checks both legacy and kernel**: Project list uses `bool(context_profile) or id in kernel_profiles` to detect knowledge. Frontend auto-resolve and green-dot indicators use `has_context || source_count > 0`.
14. **Kernel metadata fallback for hints**: When a project has a kernel profile but no legacy `context_profile`, ForgeContextSection builds hint fields from `kernelProfile.metadata` (conventions, patterns, test_patterns) and `kernelProfile.test_framework`.
15. **PUT profile uses `exclude_unset`**: Backend uses `model_dump(exclude_unset=True)` to distinguish "field omitted" (unchanged) from "field set to null" (clear). Frontend sends `null` for empty strings, not `undefined`.
