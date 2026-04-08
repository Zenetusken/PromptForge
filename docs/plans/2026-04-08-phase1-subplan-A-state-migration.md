# Phase 1 Sub-plan A: State Constant + Project Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `EXCLUDED_STRUCTURAL_STATES` constant, add `state='project'` convention, create Legacy project node, re-parent domains under it, add `project_id` to Optimization, and backfill.

**Architecture:** Define a single source-of-truth constant for state exclusion patterns (currently scattered as inline lists across 37+ locations in 8 files). Create the project node hierarchy by migrating existing domain nodes under a "Legacy" project node. Add `project_id` to Optimization for fast per-project filtering.

**Tech Stack:** Python 3.12, SQLAlchemy async, aiosqlite, pytest

**Spec:** `docs/specs/2026-04-08-taxonomy-scaling-design.md` (sections: Data Model Changes, Migration)
**ADR:** `docs/adr/ADR-005-taxonomy-scaling-architecture.md`

---

### Task 1: Define EXCLUDED_STRUCTURAL_STATES constant

**Files:**
- Modify: `backend/app/services/taxonomy/_constants.py`
- Test: `backend/tests/taxonomy/test_constants.py` (create)

- [ ] **Step 1: Write the test**

```python
# backend/tests/taxonomy/test_constants.py
"""Tests for taxonomy constants."""

from app.services.taxonomy._constants import EXCLUDED_STRUCTURAL_STATES


def test_excluded_structural_states_contains_required():
    """The constant must contain domain, archived, and project."""
    assert "domain" in EXCLUDED_STRUCTURAL_STATES
    assert "archived" in EXCLUDED_STRUCTURAL_STATES
    assert "project" in EXCLUDED_STRUCTURAL_STATES


def test_excluded_structural_states_is_frozenset():
    """Must be frozenset (immutable) to prevent accidental mutation."""
    assert isinstance(EXCLUDED_STRUCTURAL_STATES, frozenset)


def test_excluded_structural_states_is_list_compatible():
    """Can be passed to SQLAlchemy .notin_() which expects a sequence."""
    as_list = list(EXCLUDED_STRUCTURAL_STATES)
    assert len(as_list) == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && source .venv/bin/activate
pytest tests/taxonomy/test_constants.py -v
```
Expected: FAIL — `EXCLUDED_STRUCTURAL_STATES` not defined

- [ ] **Step 3: Add the constant to _constants.py**

Add after the existing blend weight constants (after line 39):

```python
# ---------------------------------------------------------------------------
# Structural state exclusion
# ---------------------------------------------------------------------------
# States that represent structural/organizational nodes, not active clusters.
# Used in all taxonomy queries that operate on "active" clusters:
#   PromptCluster.state.notin_(EXCLUDED_STRUCTURAL_STATES)
# Centralized here so adding a new structural state is a one-line change.
EXCLUDED_STRUCTURAL_STATES: frozenset[str] = frozenset({
    "domain",    # domain grouping nodes
    "archived",  # tombstoned clusters
    "project",   # project hierarchy nodes (ADR-005)
})
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/taxonomy/test_constants.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy/_constants.py backend/tests/taxonomy/test_constants.py
git commit -m "feat(taxonomy): add EXCLUDED_STRUCTURAL_STATES constant for ADR-005"
```

---

### Task 2: Replace all inline state exclusion lists in taxonomy modules

**Files:**
- Modify: `backend/app/services/taxonomy/engine.py` (11 occurrences)
- Modify: `backend/app/services/taxonomy/warm_phases.py` (15 occurrences)
- Modify: `backend/app/services/taxonomy/cold_path.py` (7 occurrences)
- Modify: `backend/app/services/taxonomy/warm_path.py` (1 occurrence)
- Modify: `backend/app/services/taxonomy/family_ops.py` (1 occurrence)

- [ ] **Step 1: Add import to each file**

At the top of each file, add to the existing `_constants` import:

```python
from app.services.taxonomy._constants import EXCLUDED_STRUCTURAL_STATES
```

Files that already import from `_constants` (engine.py, warm_phases.py, cold_path.py, family_ops.py) — add to the existing import line.

For `warm_path.py` which may not import from `_constants` yet — add a new import.

- [ ] **Step 2: Replace patterns in engine.py**

Replace every occurrence of:
```python
PromptCluster.state.notin_(["domain", "archived"])
```
with:
```python
PromptCluster.state.notin_(EXCLUDED_STRUCTURAL_STATES)
```

Also replace:
```python
PromptCluster.state.notin_(["archived"])
```
with:
```python
PromptCluster.state.notin_(["archived"])  # intentional: only archived, not structural
```
(Leave these as-is — they deliberately include domain nodes. Add a comment explaining why.)

Affected lines in engine.py: 582, 600, 647, 766, 1399, 1945, 2141, 2421 (replace with constant); lines 715, 734 (leave as `["archived"]` with comment).

- [ ] **Step 3: Replace patterns in warm_phases.py**

Same replacement for all `.notin_(["domain", "archived"])` occurrences.

Affected lines: 966, 1113, 1128, 1140, 1184, 1522, 1783, 1965, 2014, 2220, 2493, 2687, 3253.

Line 1440 uses `.notin_(["archived"])` — leave as-is with comment.

For Python-level `not in` checks — these use BOTH list and tuple syntax:
- `if node.state not in ["domain", "archived"]` (list)
- `if node.state not in ("domain", "archived")` (tuple, at lines ~2345, 2377, 2378)

Replace ALL with:
```python
if node.state not in EXCLUDED_STRUCTURAL_STATES:
```
`frozenset` supports membership test (`in`) for both list and tuple patterns.

- [ ] **Step 4: Replace patterns in cold_path.py**

Affected lines: 127, 139, 259, 495, 676, 939, 1112.

- [ ] **Step 5: Replace pattern in warm_path.py**

The `_load_active_nodes()` function at line 84-104 has:
```python
excluded = ["domain", "archived"]
```
Replace with:
```python
excluded = list(EXCLUDED_STRUCTURAL_STATES)
```

- [ ] **Step 6: Replace pattern in family_ops.py**

Line 567: replace `.notin_(["domain", "archived"])` with `.notin_(EXCLUDED_STRUCTURAL_STATES)`.

- [ ] **Step 6b: Replace patterns in quality.py**

Lines 109 and 183 use Python-level `state not in ("domain", "archived")`. Replace with:
```python
from app.services.taxonomy._constants import EXCLUDED_STRUCTURAL_STATES
# ...
if node.state not in EXCLUDED_STRUCTURAL_STATES:
```

Note: these use tuples `("domain", "archived")` not lists — `frozenset` membership test works with both.

- [ ] **Step 7: Run full backend test suite**

```bash
pytest --tb=short -q
```
Expected: All 1660+ tests pass (this is a pure refactor — no behavior change)

- [ ] **Step 8: Run ruff lint**

```bash
ruff check app/services/taxonomy/
```
Expected: All checks passed

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/taxonomy/
git commit -m "refactor(taxonomy): replace 37 inline state exclusion lists with EXCLUDED_STRUCTURAL_STATES

Pure refactor — no behavior change. Every .notin_(['domain', 'archived'])
replaced with .notin_(EXCLUDED_STRUCTURAL_STATES) from _constants.py.
Adding a new structural state (like 'project') is now a one-line change."
```

---

### Task 3: Replace state exclusion patterns in routers

**Files:**
- Modify: `backend/app/routers/clusters.py`
- Modify: `backend/app/routers/health.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Fix clusters.py**

Lines 180, 184 use `PromptCluster.state != "archived"`. Convert to:
```python
PromptCluster.state.notin_(EXCLUDED_STRUCTURAL_STATES)
```

Add import:
```python
from app.services.taxonomy._constants import EXCLUDED_STRUCTURAL_STATES
```

Line 375 uses `PromptCluster.state != "domain"` — this is a different pattern (filtering for non-domain). Leave as-is but add `!= "project"` alongside:
```python
PromptCluster.state != "domain",
PromptCluster.state != "project",
```

- [ ] **Step 2: Fix health.py**

The domain count query (line 112) uses `PromptCluster.state == "domain"` — this is correct (counting domain nodes). No change needed.

- [ ] **Step 3: Fix main.py**

Lines 184, 205 use `state != "archived"`. Convert to `.notin_(EXCLUDED_STRUCTURAL_STATES)`.

Add import:
```python
from app.services.taxonomy._constants import EXCLUDED_STRUCTURAL_STATES
```

- [ ] **Step 4: Run full test suite**

```bash
pytest --tb=short -q
```
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/clusters.py backend/app/routers/health.py backend/app/main.py
git commit -m "refactor(routers): use EXCLUDED_STRUCTURAL_STATES in cluster and health queries"
```

---

### Task 4: Add GlobalPattern model and project_id to Optimization

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_models_migration.py` (create)

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_models_migration.py
"""Tests for ADR-005 model additions."""

import pytest

from app.models import GlobalPattern, Optimization


def test_optimization_has_project_id_field():
    """Optimization model has project_id column."""
    assert hasattr(Optimization, "project_id")


def test_global_pattern_model_exists():
    """GlobalPattern model is defined with required fields."""
    gp = GlobalPattern.__table__
    assert "id" in gp.columns
    assert "pattern_text" in gp.columns
    assert "embedding" in gp.columns
    assert "source_cluster_ids" in gp.columns
    assert "source_project_ids" in gp.columns
    assert "cross_project_count" in gp.columns
    assert "global_source_count" in gp.columns
    assert "avg_cluster_score" in gp.columns
    assert "promoted_at" in gp.columns
    assert "last_validated_at" in gp.columns
    assert "state" in gp.columns
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models_migration.py -v
```
Expected: FAIL — `GlobalPattern` not defined, `project_id` not on Optimization

- [ ] **Step 3: Add project_id to Optimization model**

In `backend/app/models.py`, add to the Optimization class (after `cluster_id`):

```python
project_id = Column(String(36), nullable=True, index=True)  # ADR-005: denormalized project FK
```

- [ ] **Step 4: Add GlobalPattern model**

In `backend/app/models.py`, add after the existing models:

```python
class GlobalPattern(Base):
    """Durable cross-project pattern (ADR-005).

    Promoted from MetaPattern when a technique proves universal across
    2+ projects. Survives source cluster archival. Injected into all
    projects with a 1.3x relevance boost.
    """

    __tablename__ = "global_patterns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    pattern_text = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=True)  # 384-dim float32
    source_cluster_ids = Column(JSON, nullable=False, default=list)
    source_project_ids = Column(JSON, nullable=False, default=list)
    cross_project_count = Column(Integer, nullable=False, default=0)
    global_source_count = Column(Integer, nullable=False, default=0)
    avg_cluster_score = Column(Float, nullable=True)
    promoted_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_validated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    state = Column(String(20), nullable=False, default="active")  # active|demoted|retired
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_models_migration.py -v
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/tests/test_models_migration.py
git commit -m "feat(models): add GlobalPattern model and project_id to Optimization (ADR-005)"
```

---

### Task 5: Create migration — Legacy project node + domain re-parenting

**Files:**
- Modify: `backend/app/main.py` (lifespan startup migration)
- Test: `backend/tests/test_project_migration.py` (create)

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_project_migration.py
"""Tests for ADR-005 Legacy project node migration."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Optimization, PromptCluster


@pytest.mark.asyncio
async def test_legacy_project_node_created(db_session: AsyncSession):
    """Migration creates a Legacy project node if none exists."""
    from app.main import _run_adr005_migration

    await _run_adr005_migration(db_session)
    await db_session.commit()

    result = await db_session.execute(
        select(PromptCluster).where(PromptCluster.state == "project")
    )
    project = result.scalar_one_or_none()
    assert project is not None
    assert project.label == "Legacy"
    assert project.state == "project"


@pytest.mark.asyncio
async def test_domain_nodes_reparented(db_session: AsyncSession):
    """All domain nodes get parent_id pointing to Legacy project."""
    # Create a domain node
    domain = PromptCluster(
        label="test-domain",
        state="domain",
        domain="test",
        task_type="general",
        member_count=0,
    )
    db_session.add(domain)
    await db_session.flush()
    assert domain.parent_id is None

    from app.main import _run_adr005_migration

    await _run_adr005_migration(db_session)
    await db_session.commit()

    await db_session.refresh(domain)
    assert domain.parent_id is not None

    # parent should be the project node
    parent = await db_session.get(PromptCluster, domain.parent_id)
    assert parent.state == "project"


@pytest.mark.asyncio
async def test_migration_is_idempotent(db_session: AsyncSession):
    """Running migration twice doesn't create duplicate project nodes."""
    from app.main import _run_adr005_migration

    await _run_adr005_migration(db_session)
    await db_session.commit()
    await _run_adr005_migration(db_session)
    await db_session.commit()

    result = await db_session.execute(
        select(PromptCluster).where(PromptCluster.state == "project")
    )
    projects = result.scalars().all()
    assert len(projects) == 1


@pytest.mark.asyncio
async def test_optimization_project_id_backfilled(db_session: AsyncSession):
    """Optimizations get project_id from their cluster's project ancestry."""
    from app.main import _run_adr005_migration

    # Create project -> domain -> cluster -> optimization chain
    project = PromptCluster(label="TestProject", state="project", domain="general", task_type="general", member_count=0)
    db_session.add(project)
    await db_session.flush()

    domain = PromptCluster(label="backend", state="domain", domain="backend", task_type="general", member_count=0, parent_id=project.id)
    db_session.add(domain)
    await db_session.flush()

    cluster = PromptCluster(label="API patterns", state="active", domain="backend", task_type="coding", member_count=1, parent_id=domain.id)
    db_session.add(cluster)
    await db_session.flush()

    opt = Optimization(raw_prompt="test", status="completed", cluster_id=cluster.id)
    db_session.add(opt)
    await db_session.flush()
    assert opt.project_id is None

    await _run_adr005_migration(db_session)
    await db_session.commit()

    await db_session.refresh(opt)
    assert opt.project_id == project.id
```

- [ ] **Step 2: Implement the migration function**

In `backend/app/main.py`, add a standalone migration function (before the lifespan):

```python
async def _run_adr005_migration(db: AsyncSession) -> None:
    """ADR-005: Create Legacy project node, re-parent domains, backfill project_id.

    Idempotent — safe to run on every startup. Skips if project node already exists.
    """
    from sqlalchemy import select as _sel, update as _upd

    from app.models import Optimization, PromptCluster

    # Step 1: Check if migration already ran
    existing = await db.execute(
        _sel(PromptCluster).where(PromptCluster.state == "project").limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        # Already migrated — just backfill any new optimizations missing project_id
        await _backfill_project_ids(db)
        return

    # Step 2: Create Legacy project node
    legacy = PromptCluster(
        label="Legacy",
        state="project",
        domain="general",
        task_type="general",
        member_count=0,
    )
    db.add(legacy)
    await db.flush()
    logger.info("ADR-005 migration: created Legacy project node %s", legacy.id)

    # Step 3: Backup + re-parent all domain nodes under Legacy
    # Preserve original parent_id for rollback support (spec requirement)
    domain_q = await db.execute(
        _sel(PromptCluster).where(
            PromptCluster.state == "domain",
            PromptCluster.parent_id.is_(None),
        )
    )
    domains = domain_q.scalars().all()
    for d in domains:
        # Store original parent_id for rollback (most are None for top-level domains)
        if not hasattr(d, '_migration_prev_parent_id'):
            # Use cluster_metadata to store rollback info (avoids schema change)
            from app.services.taxonomy.cluster_meta import read_meta, write_meta
            d.cluster_metadata = write_meta(
                d.cluster_metadata,
                _migration_prev_parent_id=d.parent_id,
            )
        d.parent_id = legacy.id
    if domains:
        logger.info("ADR-005 migration: re-parented %d domain nodes under Legacy", len(domains))

    # Step 4: Backfill project_id on Optimizations
    await _backfill_project_ids(db)


async def _backfill_project_ids(db: AsyncSession) -> None:
    """Backfill Optimization.project_id from cluster ancestry (2 hops)."""
    from sqlalchemy import select as _sel

    from app.models import Optimization, PromptCluster

    # Find and backfill ALL optimizations missing project_id (loop until done)
    total_filled = 0
    while True:
        missing_q = await db.execute(
            _sel(Optimization).where(
                Optimization.project_id.is_(None),
                Optimization.cluster_id.isnot(None),
            ).limit(500)  # batch to keep SQLite writer lock short
        )
        missing = missing_q.scalars().all()
        if not missing:
            break

    # Build cluster_id -> project_id lookup (2-hop: cluster -> domain -> project)
    cluster_ids = {opt.cluster_id for opt in missing if opt.cluster_id}
    if not cluster_ids:
        return

    clusters = (await db.execute(
        _sel(PromptCluster).where(PromptCluster.id.in_(cluster_ids))
    )).scalars().all()

    cluster_to_domain = {c.id: c.parent_id for c in clusters}

    domain_ids = {pid for pid in cluster_to_domain.values() if pid}
    domains = (await db.execute(
        _sel(PromptCluster).where(PromptCluster.id.in_(domain_ids))
    )).scalars().all() if domain_ids else []

    domain_to_project = {d.id: d.parent_id for d in domains}

        # Backfill this batch
        filled = 0
        for opt in missing:
            domain_id = cluster_to_domain.get(opt.cluster_id)
            project_id = domain_to_project.get(domain_id) if domain_id else None
            if project_id:
                opt.project_id = project_id
                filled += 1
        total_filled += filled
        await db.flush()  # persist batch before next iteration

    if total_filled:
        logger.info("ADR-005 migration: backfilled project_id on %d optimizations", total_filled)
```

- [ ] **Step 3: Wire migration into lifespan**

In the lifespan function, after the existing ALTER TABLE migrations (after the `global_source_count` column migration around line 284), add:

```python
# ADR-005: Legacy project node + domain re-parenting + project_id backfill
try:
    async with async_session_factory() as _adr005_db:
        await _run_adr005_migration(_adr005_db)
        await _adr005_db.commit()
except Exception as adr005_exc:
    logger.warning("ADR-005 migration failed (non-fatal): %s", adr005_exc)
```

- [ ] **Step 4: Add GlobalPattern table creation**

In the lifespan, after the SQLite WAL setup (around line 44), ensure `create_all()` is called or add explicit table creation:

```python
# Ensure GlobalPattern table exists (ADR-005)
try:
    from app.models import GlobalPattern
    async with engine.begin() as conn:
        await conn.run_sync(GlobalPattern.__table__.create, checkfirst=True)
except Exception:
    pass  # Table already exists
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_project_migration.py -v
pytest --tb=short -q  # full suite
```
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_project_migration.py
git commit -m "feat(taxonomy): ADR-005 migration — Legacy project node + domain re-parenting + project_id backfill"
```

---

### Task 6: E2E validation — restart server and verify migration

- [ ] **Step 1: Restart server**

```bash
./init.sh restart
```

- [ ] **Step 2: Check migration in logs**

```bash
grep "ADR-005" data/backend.log
```
Expected: "ADR-005 migration: created Legacy project node" and "re-parented N domain nodes"

- [ ] **Step 3: Verify database state**

```bash
cd backend && source .venv/bin/activate
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.database import async_session_factory
from sqlalchemy import select, func
from app.models import PromptCluster, Optimization

async def verify():
    async with async_session_factory() as db:
        # Project node exists
        p = (await db.execute(select(PromptCluster).where(PromptCluster.state == 'project'))).scalar_one()
        print(f'Project node: {p.label} ({p.id[:8]})')

        # All domains are children of project
        orphan_domains = (await db.scalar(
            select(func.count()).where(
                PromptCluster.state == 'domain',
                PromptCluster.parent_id.is_(None),
            )
        )) or 0
        print(f'Orphan domains (should be 0): {orphan_domains}')

        # Optimizations have project_id
        total = (await db.scalar(select(func.count()).select_from(Optimization).where(Optimization.status == 'completed'))) or 0
        filled = (await db.scalar(select(func.count()).select_from(Optimization).where(Optimization.project_id.isnot(None)))) or 0
        print(f'Optimizations: {filled}/{total} have project_id')
asyncio.run(verify())
" 2>/dev/null
```

- [ ] **Step 4: Run full backend tests**

```bash
pytest --tb=short -q
```
Expected: All 1660+ tests pass

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A && git commit -m "fix: ADR-005 migration adjustments from E2E validation"
```
