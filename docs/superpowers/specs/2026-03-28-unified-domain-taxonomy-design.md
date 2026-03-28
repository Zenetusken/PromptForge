# Unified Domain Taxonomy — Design Specification

**Date:** 2026-03-28
**Status:** Approved
**ADR:** [ADR-004](../../adr/ADR-004-unified-domain-taxonomy.md)
**Supersedes:** Domain sections of [Evolutionary Taxonomy Engine Design](2026-03-20-evolutionary-taxonomy-engine-design.md)

---

## 1. Motivation

The domain system is the last hardcoded classification in Project Synthesis. Strategies are adaptive (filesystem-discovered), taxonomy clusters are organic (HDBSCAN-discovered), but domains remain a 7-item constant. This creates three problems:

1. **Non-coding prompts are invisible.** Marketing, legal, education, data science, creative writing — all collapse to `domain="general"` with identical gray coloring, no filtering, and no strategy affinity.
2. **The taxonomy engine's intelligence is wasted.** It already clusters prompts by semantic similarity and evolves through quality-gated lifecycle mutations. Domains don't participate.
3. **Scaling requires code changes.** Adding a domain requires editing 5 files across 2 codebases, rebuilding, and redeploying.

**Decision:** Domains become `PromptCluster` nodes with `state="domain"`. The taxonomy engine evolves them organically. All hardcoded domain constants are removed. See ADR-004 for full decision context and alternatives considered.

---

## 2. Data Model

### 2.1 PromptCluster state enum expansion

The `state` column (`String(20)`) gains one new value:

```
candidate → active → mature → template → archived
                                ↑
                             domain  (new)
```

`state="domain"` nodes are top-level navigational categories. They share the `PromptCluster` schema (centroid, metrics, lifecycle timestamps) but follow different lifecycle rules (see Section 4: Guardrails).

### 2.2 Domain node schema

Domain nodes use existing `PromptCluster` columns. No new columns are added:

| Column | Domain node usage |
|--------|-------------------|
| `id` | UUID, same as any cluster |
| `parent_id` | `NULL` for root domains. Non-null for sub-domains (future) |
| `label` | Domain name: `"backend"`, `"marketing"`, etc. Unique among domain nodes |
| `state` | `"domain"` |
| `domain` | Self-referencing: equals own `label` |
| `task_type` | `"general"` (domains span task types) |
| `centroid_embedding` | Mean embedding of member cluster centroids |
| `member_count` | Count of direct child clusters |
| `usage_count` | Aggregate of child cluster usage |
| `avg_score` | Weighted mean of child cluster scores |
| `coherence` | Intra-domain coherence (expected lower than cluster coherence) |
| `separation` | Inter-domain separation |
| `stability` | Change rate across warm path cycles |
| `persistence` | `1.0` for seed domains; computed for discovered domains |
| `color_hex` | Pinned color — not recomputed by cold path |
| `preferred_strategy` | Most effective strategy for this domain (from feedback data) |

### 2.3 Domain node metadata

Domain-specific configuration stored in a new `metadata` JSON column on `PromptCluster`:

```python
metadata = Column(JSON, nullable=True)
```

For domain nodes, this holds:

```json
{
  "source": "seed",
  "signal_keywords": [
    ["api", 0.8], ["endpoint", 0.9], ["server", 0.8],
    ["middleware", 0.9], ["fastapi", 1.0]
  ],
  "discovered_at": null,
  "proposed_by_snapshot": null
}
```

| Field | Purpose |
|-------|---------|
| `source` | `"seed"` (migration-created) or `"discovered"` (warm path-created) |
| `signal_keywords` | `[keyword, weight]` pairs for heuristic classifier. Seed domains carry current hardcoded values. Discovered domains get TF-IDF-extracted keywords. |
| `discovered_at` | ISO timestamp when warm path proposed this domain (null for seeds) |
| `proposed_by_snapshot` | `TaxonomySnapshot.id` that triggered discovery (audit trail) |

Non-domain nodes have `metadata=NULL` — no overhead.

### 2.4 Optimization.domain column

Remains `String`, stores the domain node's `label`. Resolution path:

```
Optimization.domain = "backend"
  → SELECT id FROM prompt_cluster WHERE state='domain' AND label='backend'
  → Returns the domain node for join/aggregation queries
```

This is a soft reference by label, not a FK. The taxonomy engine maintains label uniqueness among domain nodes.

### 2.5 Index additions

```python
Index("ix_prompt_cluster_state_label", "state", "label")  # domain lookup by label
Index("uq_prompt_cluster_domain_label", "label", unique=True,
      postgresql_where=text("state = 'domain'"),
      sqlite_where=text("state = 'domain'"))  # label uniqueness among domain nodes
```

---

## 3. Domain Lifecycle

### 3.1 Seed domains (migration)

Seven domain nodes created at migration time:

| Label | Color | Source keywords |
|-------|-------|----------------|
| `backend` | `#b44aff` | api, endpoint, server, middleware, fastapi, django, flask, authentication, route |
| `frontend` | `#ff4895` | react, svelte, component, css, ui, layout, responsive, tailwind, vue |
| `database` | `#36b5ff` | sql, migration, schema, query, postgresql, sqlite, orm, table |
| `devops` | `#6366f1` | docker, ci/cd, kubernetes, terraform, nginx, monitoring, deploy |
| `security` | `#ff2255` | auth, encryption, vulnerability, cors, jwt, oauth, sanitize, injection, xss, csrf |
| `fullstack` | `#d946ef` | (computed: backend + frontend signal co-occurrence) |
| `general` | `#7a7a9e` | (catch-all: no keywords, matched by fallback) |

Centroid embeddings computed by embedding the concatenated keyword list via `all-MiniLM-L6-v2`.

### 3.2 Domain discovery (warm path)

Added as a post-HDBSCAN step in the warm path:

```python
async def _propose_domains(self, db: AsyncSession) -> list[str]:
    """Discover new domains from coherent 'general' sub-populations."""

    # 1. Find coherent clusters under "general" domain
    general_node = await self._get_domain_node(db, "general")
    candidates = await db.execute(
        select(PromptCluster).where(
            PromptCluster.parent_id == general_node.id,
            PromptCluster.state.in_(["active", "mature"]),
            PromptCluster.member_count >= DOMAIN_DISCOVERY_MIN_MEMBERS,  # 5
            PromptCluster.coherence >= DOMAIN_DISCOVERY_MIN_COHERENCE,   # 0.6
        )
    )

    # 2. For each candidate, check domain_raw consistency
    for cluster in candidates:
        optimizations = await db.execute(
            select(Optimization.domain_raw).where(
                Optimization.cluster_id == cluster.id
            )
        )
        primaries = [parse_domain(o.domain_raw)[0] for o in optimizations]
        counter = Counter(primaries)
        top_primary, top_count = counter.most_common(1)[0]

        if (
            top_primary != "general"
            and top_count / len(primaries) >= DOMAIN_DISCOVERY_CONSISTENCY  # 0.60
            and not await self._domain_exists(db, top_primary)
        ):
            await self._create_domain_node(db, top_primary, cluster)

    # 3. Return list of newly created domain labels
```

### 3.3 Domain node creation

```python
async def _create_domain_node(
    self, db: AsyncSession, label: str, seed_cluster: PromptCluster
) -> PromptCluster:
    # Compute color via OKLab max-distance from existing domain colors
    existing_colors = await self._get_domain_colors(db)
    color_hex = compute_max_distance_color(existing_colors)

    # Extract TF-IDF keywords from member prompts
    keywords = await self._extract_domain_keywords(db, seed_cluster)

    domain_node = PromptCluster(
        label=label,
        state="domain",
        domain=label,
        task_type="general",
        color_hex=color_hex,
        persistence=1.0,
        centroid_embedding=seed_cluster.centroid_embedding,
        member_count=0,
        metadata={
            "source": "discovered",
            "signal_keywords": keywords,
            "discovered_at": utcnow().isoformat(),
            "proposed_by_snapshot": self._current_snapshot_id,
        },
    )
    db.add(domain_node)
    await db.flush()

    # Re-parent qualifying clusters
    await self._reparent_to_domain(db, domain_node, label)

    # Backfill Optimization.domain
    await self._backfill_optimization_domain(db, domain_node)

    # Emit event
    await event_bus.publish("domain_created", {
        "label": label,
        "color_hex": color_hex,
        "source": "discovered",
    })

    return domain_node
```

### 3.4 OKLab max-distance color assignment

```python
def compute_max_distance_color(existing_hex: list[str]) -> str:
    """Find the OKLab color maximally distant from all existing domain colors.

    Also avoids tier accent colors:
      internal=#00e5ff, sampling=#22ff88, passthrough=#fbbf24
    """
    existing_lab = [hex_to_oklab(h) for h in existing_hex + TIER_ACCENTS]

    best_color = None
    best_min_dist = 0.0

    # Sample candidates in OKLab space (L=0.7 for neon brightness, sweep a/b)
    for a in np.linspace(-0.15, 0.15, 60):
        for b in np.linspace(-0.15, 0.15, 60):
            candidate = OKLab(L=0.7, a=a, b=b)
            min_dist = min(oklab_distance(candidate, e) for e in existing_lab)
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_color = candidate

    return oklab_to_hex(best_color)
```

### 3.5 Keyword extraction for discovered domains

```python
async def _extract_domain_keywords(
    self, db: AsyncSession, cluster: PromptCluster, top_k: int = 15
) -> list[list[str | float]]:
    """Extract top TF-IDF keywords from cluster member prompts."""
    optimizations = await db.execute(
        select(Optimization.raw_prompt).where(
            Optimization.cluster_id == cluster.id
        )
    )
    texts = [o.raw_prompt for o in optimizations if o.raw_prompt]

    if not texts:
        return []

    vectorizer = TfidfVectorizer(
        max_features=top_k,
        stop_words="english",
        ngram_range=(1, 2),
    )
    tfidf = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()
    scores = tfidf.mean(axis=0).A1

    ranked = sorted(zip(feature_names, scores), key=lambda x: x[1], reverse=True)
    return [[kw, round(float(score), 2)] for kw, score in ranked[:top_k]]
```

### 3.6 Re-parenting and backfill

When a new domain is created, two operations execute:

**Re-parent clusters:**
```sql
UPDATE prompt_cluster
SET parent_id = :new_domain_id, domain = :new_label
WHERE parent_id = :general_domain_id
  AND domain = 'general'
  AND id IN (
    SELECT cluster_id FROM optimizations
    WHERE domain_raw LIKE :label || '%'
    GROUP BY cluster_id
    HAVING COUNT(*) * 1.0 / (SELECT COUNT(*) FROM optimizations WHERE cluster_id = prompt_cluster.id) >= 0.6
  )
```

**Backfill optimizations:**
```sql
UPDATE optimizations
SET domain = :new_label
WHERE cluster_id IN (SELECT id FROM prompt_cluster WHERE parent_id = :new_domain_id)
  AND domain = 'general'
```

---

## 4. Stability Guardrails

### 4.1 Color pinning

**Location:** `taxonomy/coloring.py`

The cold path's `assign_colors()` function skips domain nodes:

```python
async def assign_colors(nodes: list[PromptCluster]) -> None:
    for node in nodes:
        if node.state == "domain":
            continue  # Domain colors are pinned at creation time
        node.color_hex = oklab_from_umap(node.umap_x, node.umap_y, node.umap_z)
```

### 4.2 Retire exemption

**Location:** `taxonomy/lifecycle.py`

```python
async def retire(db: AsyncSession, node: PromptCluster, ...) -> bool:
    if node.state == "domain":
        logger.info("Skipping retire for domain node: %s", node.label)
        return False
    # ... existing retire logic
```

### 4.3 Separate coherence floor

**Location:** `taxonomy/quality.py`

```python
DOMAIN_COHERENCE_FLOOR = 0.3
CLUSTER_COHERENCE_FLOOR = 0.6

def coherence_threshold(node: PromptCluster) -> float:
    return DOMAIN_COHERENCE_FLOOR if node.state == "domain" else CLUSTER_COHERENCE_FLOOR
```

### 4.4 Merge approval gate

**Location:** `taxonomy/lifecycle.py`

```python
async def merge(db: AsyncSession, survivor: PromptCluster, loser: PromptCluster, ...) -> bool:
    if survivor.state == "domain" or loser.state == "domain":
        await event_bus.publish("domain_merge_proposed", {
            "survivor": survivor.label,
            "loser": loser.label,
            "similarity": cosine_similarity,
        })
        logger.info("Domain merge proposed (requires approval): %s ← %s", survivor.label, loser.label)
        return False
    # ... existing merge logic
```

### 4.5 Split creates clusters

**Location:** `taxonomy/lifecycle.py`

```python
async def split(db: AsyncSession, parent: PromptCluster, ...) -> list[PromptCluster]:
    # Children always start as candidates, even when parent is a domain
    children = []
    for centroid, member_ids in sub_clusters:
        child = PromptCluster(
            parent_id=parent.id,
            state="candidate",  # Never "domain"
            domain=parent.label if parent.state == "domain" else parent.domain,
            # ...
        )
        children.append(child)
    return children
```

---

## 5. Removals — Code Deleted

No fallback maps, no legacy constants. Clean removal.

### 5.1 Backend removals

| File | What | Replacement |
|------|------|-------------|
| `pipeline_constants.py` | `VALID_DOMAINS` set | Domain nodes: `SELECT label FROM prompt_cluster WHERE state='domain'` |
| `pipeline_constants.py` | `apply_domain_gate()` | Taxonomy engine embedding-based assignment with "general" domain fallback |
| `heuristic_analyzer.py` | `_DOMAIN_SIGNALS` dict (hardcoded) | `DomainSignalLoader` reads from domain node metadata |
| `heuristic_analyzer.py` | `_classify_domain()` fullstack promotion hack | Fullstack is a seed domain node; classification via signal matching like any other domain |
| `optimize.py:586-591` | `VALID_DOMAINS` validation | Domain label validation against `state="domain"` nodes |
| `save_result.py:195-208` | `VALID_DOMAINS` validation | Same domain label validation |

### 5.2 Frontend removals

| File | What | Replacement |
|------|------|-------------|
| `colors.ts:22-30` | `DOMAIN_COLORS` map | `domainStore.colors` (API-fetched, cached) |
| `Inspector.svelte:9` | `KNOWN_DOMAINS` array | `domainStore.labels` (API-fetched) |

### 5.3 Prompt removals

| File | What | Replacement |
|------|------|-------------|
| `analyze.md:17` | Hardcoded domain list | `{{known_domains}}` template variable |

---

## 6. New Services

### 6.1 DomainSignalLoader (`backend/app/services/domain_signal_loader.py`)

Replaces `_DOMAIN_SIGNALS` in `heuristic_analyzer.py`.

```python
class DomainSignalLoader:
    """Loads domain classification signals from domain node metadata."""

    _signals: dict[str, list[tuple[str, float]]] = {}
    _patterns: dict[str, re.Pattern] = {}

    async def load(self, db: AsyncSession) -> None:
        """Load signals from all active domain nodes."""
        domains = await db.execute(
            select(PromptCluster).where(PromptCluster.state == "domain")
        )
        self._signals = {}
        for domain in domains.scalars():
            if domain.metadata and domain.metadata.get("signal_keywords"):
                self._signals[domain.label] = [
                    (kw, weight) for kw, weight in domain.metadata["signal_keywords"]
                ]
        self._precompile_patterns()

    def classify(self, scored: dict[str, float]) -> str:
        """Classify domain from keyword scores. Same algorithm as current _classify_domain()."""
        # ... identical logic, but uses self._signals instead of module-level dict
```

Loaded at startup. Hot-reloaded on `domain_created` and `taxonomy_changed` events via event bus subscription.

### 6.2 Domain color service (extension of `taxonomy/coloring.py`)

`compute_max_distance_color()` added to `coloring.py`. Reuses existing OKLab conversion utilities.

---

## 7. API Changes

### 7.1 New endpoint: `GET /api/domains`

```python
@router.get("/api/domains")
async def list_domains(db: AsyncSession = Depends(get_db)) -> list[DomainInfo]:
    """List all active domain nodes with colors and metadata."""
    domains = await db.execute(
        select(PromptCluster)
        .where(PromptCluster.state == "domain")
        .order_by(PromptCluster.label)
    )
    return [
        DomainInfo(
            id=d.id,
            label=d.label,
            color_hex=d.color_hex,
            member_count=d.member_count,
            avg_score=d.avg_score,
            source=d.metadata.get("source", "seed") if d.metadata else "seed",
        )
        for d in domains.scalars()
    ]
```

### 7.2 New schema: `DomainInfo`

```python
class DomainInfo(BaseModel):
    id: str
    label: str
    color_hex: str
    member_count: int = 0
    avg_score: float | None = None
    source: str = "seed"  # seed | discovered
```

### 7.3 New endpoint: `POST /api/domains/{id}/promote`

Promotes a mature cluster to domain status. Validates:
- Source cluster must be `state="mature"` or `state="active"` with `member_count >= 5`
- No existing domain node with the same label
- Assigns OKLab max-distance color

### 7.4 Modified: `PATCH /api/clusters/{id}`

Accepts `state="domain"` only with explicit validation:
- Caller must confirm intent (e.g., `"confirm_domain_promotion": true` in body)
- Target cluster must meet minimum thresholds (member_count, coherence)

### 7.5 Modified: `GET /api/health`

Adds `domain_count: int` to health response.

### 7.6 Modified: `GET /api/clusters/tree`

Domain nodes appear as root-level entries with their child clusters nested. No schema change — `ClusterNode` already has `parent_id` and `state`.

---

## 8. Frontend Architecture

### 8.1 Domain store (`frontend/src/lib/stores/domains.svelte.ts`)

New reactive store that is the single source of truth for domain data:

```typescript
interface DomainEntry {
  id: string;
  label: string;
  color_hex: string;
  member_count: number;
  avg_score: number | null;
  source: 'seed' | 'discovered';
}

// State
let domains = $state<DomainEntry[]>([]);
let loaded = $state(false);

// Derived
let colors = $derived(
  Object.fromEntries(domains.map(d => [d.label, d.color_hex]))
);
let labels = $derived(domains.map(d => d.label));

// Actions
async function fetchDomains(): Promise<void> { ... }
function colorFor(domain: string): string { ... }
```

Initialized in app startup. Refreshed on `domain_created` and `taxonomy_changed` SSE events.

### 8.2 Color resolution (`colors.ts`)

`taxonomyColor()` rewritten to resolve from domain store:

```typescript
import { domainStore } from '$lib/stores/domains.svelte';

const FALLBACK_COLOR = '#7a7a9e';

export function taxonomyColor(color: string | null | undefined): string {
  if (!color) return FALLBACK_COLOR;
  if (color.startsWith('#')) return color;

  const primary = color.includes(':') ? color.split(':')[0].trim() : color;
  return domainStore.colorFor(primary);
}
```

No hardcoded `DOMAIN_COLORS` map.

### 8.3 Inspector domain picker

```svelte
{#each domainStore.labels as d (d)}
  <button
    class="domain-option"
    class:domain-option--active={d === parsePrimaryDomain(family.domain)}
    style="background: {domainStore.colorFor(d)};"
    onclick={() => selectDomain(d)}
    disabled={domainSaving}
  >{d}</button>
{/each}
```

No hardcoded `KNOWN_DOMAINS` array.

### 8.4 Topology rendering

Domain nodes render as larger spheres (2x cluster radius) with `persistence=1.0` ensuring they're always visible regardless of LOD tier. Their pinned `color_hex` is used directly.

---

## 9. Migration Plan

### 9.1 Alembic migration: `add_domain_nodes`

**Step 1:** Add `metadata` column to `prompt_cluster`:
```python
op.add_column('prompt_cluster', sa.Column('metadata', sa.JSON, nullable=True))
```

**Step 2:** Add index:
```python
op.create_index('ix_prompt_cluster_state_label', 'prompt_cluster', ['state', 'label'])
```

**Step 3:** Insert 7 seed domain nodes with pre-computed centroid embeddings, colors, and keyword metadata.

**Step 4:** Re-parent existing clusters under matching domain nodes:
```sql
UPDATE prompt_cluster
SET parent_id = (SELECT id FROM prompt_cluster AS d WHERE d.state = 'domain' AND d.label = prompt_cluster.domain)
WHERE state != 'domain' AND parent_id IS NULL
```

**Step 5:** Backfill `Optimization.domain` for `domain_raw` values resolvable to new domains:
```python
# For each domain node, find optimizations with matching domain_raw primary
for domain in seed_domains:
    await db.execute(
        update(Optimization)
        .where(
            Optimization.domain == "general",
            func.substr(Optimization.domain_raw, 1, func.instr(Optimization.domain_raw, ':') - 1) == domain.label
        )
        .values(domain=domain.label)
    )
```

### 9.2 Migration safety

- **Idempotent:** Checks for existing domain nodes before inserting. Safe to re-run.
- **Reversible:** Downgrade drops domain nodes, nullifies re-parented `parent_id`, restores `domain="general"` on backfilled rows.
- **Tested:** Integration test creates sample data, runs migration, validates tree structure and domain assignments.

---

## 10. Configuration Constants

All in `pipeline_constants.py` (replacing `VALID_DOMAINS`):

```python
# Domain discovery thresholds
DOMAIN_DISCOVERY_MIN_MEMBERS = 5
DOMAIN_DISCOVERY_MIN_COHERENCE = 0.6
DOMAIN_DISCOVERY_CONSISTENCY = 0.60  # 60% of members share the same domain_raw primary

# Domain quality
DOMAIN_COHERENCE_FLOOR = 0.3

# Color constraints
TIER_ACCENTS = ["#00e5ff", "#22ff88", "#fbbf24"]  # internal, sampling, passthrough — avoid proximity
```

---

## 11. Event Bus Integration

New SSE event types:

| Event | Payload | Trigger |
|-------|---------|---------|
| `domain_created` | `{label, color_hex, source}` | Warm path creates a new domain node |
| `domain_merge_proposed` | `{survivor, loser, similarity}` | Warm path detects two domains should merge |

Frontend handlers:
- `domain_created` → refresh domain store, show toast, invalidate topology
- `domain_merge_proposed` → show actionable toast with approve/reject buttons

---

## 12. Testing Strategy

### Unit tests
- `DomainSignalLoader`: load from domain metadata, classify with dynamic signals, hot-reload on event
- `compute_max_distance_color()`: produces valid hex, avoids tier accents, maximizes distance
- `_propose_domains()`: discovers domains when thresholds met, skips when not, handles edge cases (empty clusters, conflicting primaries)
- Guardrails: retire skips domains, merge blocks domain-domain, split creates candidates, cold path skips domain colors

### Integration tests
- Full warm path cycle with domain discovery: seed data → HDBSCAN → domain proposal → re-parent → backfill → event emission
- Migration: create sample clusters + optimizations, run migration, validate tree structure
- API: `GET /api/domains` returns seed domains, `POST /api/domains/{id}/promote` validates preconditions

### Frontend tests
- Domain store: fetches from API, caches, refreshes on SSE
- `taxonomyColor()`: resolves from store, handles unknown domains, handles hex passthrough
- Inspector picker: renders dynamic domain list, handles empty state during load
