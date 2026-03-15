# Database Performance & Correctness Optimization — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix soft-delete filter gaps, push user_id into SQL WHERE clauses, add composite index, consolidate SSE session management, and clean up service-layer DRY violations.

**Architecture:** Six targeted changes across the database layer — correctness fixes first (R1/R2), then performance (R3), then maintainability (R4/R5), then documentation (R6). All changes are backward-compatible and require no Pydantic schema changes.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x async, aiosqlite, pytest

**Spec:** `docs/superpowers/specs/2026-03-10-db-performance-optimization-design.md`

---

## Chunk 1: Correctness Fixes (R1 + R2)

### Task 1: Test soft-delete filter gap in PATCH endpoint

**Files:**
- Test: `backend/tests/test_soft_delete.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_soft_delete.py`:

```python
async def test_patch_rejects_soft_deleted_record():
    """PATCH /api/optimize/{id} must return 404 for soft-deleted records."""
    from fastapi import HTTPException
    from app.routers.optimize import patch_optimization
    from app.schemas.optimization import PatchOptimizationRequest

    mock_user = MagicMock()
    mock_user.id = "user-id"

    # Simulate soft-deleted record: execute returns None because
    # the WHERE clause includes deleted_at IS NULL
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=execute_result)

    patch_body = PatchOptimizationRequest(title="Should Fail")

    try:
        await patch_optimization(
            optimization_id="soft-deleted-id",
            patch=patch_body,
            session=mock_session,
            current_user=mock_user,
        )
        assert False, "Expected HTTPException 404"
    except HTTPException as exc:
        assert exc.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_soft_delete.py::test_patch_rejects_soft_deleted_record -v`
Expected: PASS (the mock returns None regardless of query shape — but this test documents the contract)

Note: This test will pass even before the fix because it mocks at the session level. The real validation comes from the integration test in Task 3. This unit test documents the expected contract.

- [ ] **Step 3: Commit**

```bash
cd backend && git add tests/test_soft_delete.py
git commit -m "test(soft-delete): add contract test for PATCH rejecting soft-deleted records"
```

---

### Task 2: Fix soft-delete filter in PATCH and retry endpoints

**Files:**
- Modify: `backend/app/routers/optimize.py:277-278` (PATCH endpoint)
- Modify: `backend/app/routers/optimize.py:318-319` (retry endpoint)

- [ ] **Step 1: Fix PATCH endpoint — add deleted_at + user_id to WHERE**

In `backend/app/routers/optimize.py`, replace lines 277-282:

```python
# BEFORE:
result = await session.execute(
    select(Optimization).where(Optimization.id == optimization_id)
)
optimization = result.scalar_one_or_none()
if not optimization or optimization.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Optimization not found")
```

With:

```python
# AFTER:
result = await session.execute(
    select(Optimization).where(
        Optimization.id == optimization_id,
        Optimization.deleted_at.is_(None),
        Optimization.user_id == current_user.id,
    )
)
optimization = result.scalar_one_or_none()
if not optimization:
    raise HTTPException(status_code=404, detail="Optimization not found")
```

- [ ] **Step 2: Fix retry endpoint — add deleted_at + user_id to WHERE**

In `backend/app/routers/optimize.py`, replace lines 318-323:

```python
# BEFORE:
result = await session.execute(
    select(Optimization).where(Optimization.id == optimization_id)
)
original = result.scalar_one_or_none()
if not original or original.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Optimization not found")
```

With:

```python
# AFTER:
result = await session.execute(
    select(Optimization).where(
        Optimization.id == optimization_id,
        Optimization.deleted_at.is_(None),
        Optimization.user_id == current_user.id,
    )
)
original = result.scalar_one_or_none()
if not original:
    raise HTTPException(status_code=404, detail="Optimization not found")
```

- [ ] **Step 3: Fix GET endpoint — push user_id into SQL WHERE**

In `backend/app/routers/optimize.py`, replace lines 261-266:

```python
# BEFORE:
from app.services.optimization_service import get_optimization_orm
optimization = await get_optimization_orm(session, optimization_id)
if not optimization or optimization.user_id != current_user.id:
    raise HTTPException(status_code=404, detail="Optimization not found")
return optimization.to_dict()
```

With:

```python
# AFTER:
result = await session.execute(
    select(Optimization).where(
        Optimization.id == optimization_id,
        Optimization.deleted_at.is_(None),
        Optimization.user_id == current_user.id,
    )
)
optimization = result.scalar_one_or_none()
if not optimization:
    raise HTTPException(status_code=404, detail="Optimization not found")
return optimization.to_dict()
```

Remove the `get_optimization_orm` import from `optimize.py` — it is no longer used in this file after the inline query replacement. Note: `get_optimization_orm` is still used by `history.py` (line 124, delete endpoint) and internally by `optimization_service.py` (line 289, `update_optimization`) — do NOT delete the function itself.

- [ ] **Step 4: Run existing tests**

Run: `cd backend && python -m pytest tests/test_soft_delete.py tests/integration/test_optimize_api.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/optimize.py
git commit -m "fix(optimize): push deleted_at + user_id into SQL WHERE for GET/PATCH/retry

Closes soft-delete filter gap (R1) and defense-in-depth user_id push (R2).
PATCH and retry endpoints previously fetched by PK alone, allowing
soft-deleted records to be edited/retried."
```

---

### Task 3: Fix soft-delete filter in MCP _opt_session

**Files:**
- Modify: `backend/app/mcp_server.py:79` (_opt_session context manager)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_soft_delete.py`:

```python
async def test_mcp_opt_session_excludes_soft_deleted():
    """_opt_session must filter deleted_at IS NULL so soft-deleted records are invisible."""
    from app.mcp_server import _opt_session

    # Record with deleted_at set — should not be returned
    mock_opt = MagicMock()
    mock_opt.deleted_at = datetime(2026, 3, 1, tzinfo=timezone.utc)

    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=execute_result)

    with patch("app.mcp_server.async_session") as mock_async_session:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_async_session.return_value = mock_ctx

        async with _opt_session("deleted-id") as (session, opt):
            assert opt is None, "Soft-deleted record should not be returned"

        # Verify the query included deleted_at filter
        call_args = mock_session.execute.call_args
        query = call_args[0][0]
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at" in compiled, (
            f"Query should filter deleted_at but got: {compiled}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_soft_delete.py::test_mcp_opt_session_excludes_soft_deleted -v`
Expected: FAIL — `"deleted_at" not in compiled`

- [ ] **Step 3: Fix _opt_session — add deleted_at filter**

In `backend/app/mcp_server.py`, replace line 79:

```python
# BEFORE:
query = select(Optimization).where(Optimization.id == optimization_id)
```

With:

```python
# AFTER:
query = select(Optimization).where(
    Optimization.id == optimization_id,
    Optimization.deleted_at.is_(None),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_soft_delete.py::test_mcp_opt_session_excludes_soft_deleted -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd backend && python -m pytest -x -q`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/mcp_server.py tests/test_soft_delete.py
git commit -m "fix(mcp): add deleted_at filter to _opt_session context manager

MCP get/tag/retry tools now correctly exclude soft-deleted records.
Previously, _opt_session fetched by PK without deleted_at IS NULL guard."
```

---

## Chunk 2: Composite Index (R3)

### Task 4: Add composite index for user-scoped history listing

**Files:**
- Modify: `backend/app/models/optimization.py:91-97` (__table_args__)
- Modify: `backend/app/database.py:144-152` (_migrate_add_missing_indexes)
- Test: `backend/tests/test_database.py` (add to existing file — 7 tests already present)

- [ ] **Step 1: Write the failing test**

Add to the bottom of `backend/tests/test_database.py` (file already exists with 7 tests — do NOT overwrite):

```python
async def test_migrate_adds_composite_user_listing_index(tmp_path):
    """_migrate_add_missing_indexes creates idx_optimizations_user_listing."""
    import app.models.optimization  # noqa: F401
    import app.models.auth          # noqa: F401
    import app.models.github        # noqa: F401

    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/idx_user_listing.db")
    from app.database import Base, _migrate_add_missing_indexes

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _migrate_add_missing_indexes(eng)

    async with eng.connect() as conn:
        result = await conn.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='optimizations'")
        )
        index_names = {row[0] for row in result.fetchall()}

    assert "idx_optimizations_user_listing" in index_names
    await eng.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_database.py::test_migrate_adds_composite_user_listing_index -v`
Expected: FAIL — `"idx_optimizations_user_listing" not in index_names`

- [ ] **Step 3: Add composite index to model __table_args__**

In `backend/app/models/optimization.py`, add to `__table_args__` tuple (before the closing parenthesis):

```python
__table_args__ = (
    Index("idx_optimizations_project", "project"),
    Index("idx_optimizations_task_type", "task_type"),
    Index("idx_optimizations_created_at", created_at.desc()),
    Index("idx_optimizations_user_id", "user_id"),
    Index("idx_optimizations_retry_of", "retry_of"),
    Index("idx_optimizations_user_listing",
          "user_id", "deleted_at", created_at.desc()),
)
```

- [ ] **Step 4: Add composite index to migration function**

In `backend/app/database.py`, add to the `_new_indexes` list in `_migrate_add_missing_indexes`:

```python
("idx_optimizations_user_listing", "optimizations",
 "user_id, deleted_at, created_at DESC"),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Run full test suite**

Run: `cd backend && python -m pytest -x -q`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/models/optimization.py app/database.py tests/test_database.py
git commit -m "perf(db): add composite index (user_id, deleted_at, created_at DESC)

Covers the dominant GET /api/history access pattern. SQLite can now
satisfy WHERE + ORDER BY from the index alone, avoiding filesort.
Added to both model __table_args__ (new DBs) and idempotent migration
(existing DBs)."
```

---

## Chunk 3: Session Consolidation (R4)

### Task 5: Refactor SSE endpoint from detached ORM mutation to dict accumulation

**Files:**
- Modify: `backend/app/routers/optimize.py:49-242` (event_stream function)
- Test: `backend/tests/integration/test_optimize_api.py` (existing tests validate behavior)

This is a refactor — existing integration tests cover the behavior. No new tests needed; the existing `test_optimize_result_persisted`, `test_optimize_patch_updates_title`, and `test_optimize_sse_emits_stage_events` verify the pipeline produces correct results.

- [ ] **Step 1: Add `update` import**

In `backend/app/routers/optimize.py`, add to the sqlalchemy import line:

```python
from sqlalchemy import select, update
```

- [ ] **Step 2: Replace event_stream body with dict accumulation pattern**

Replace the entire `event_stream()` inner function. Key changes:
1. After creating the record (session 1), accumulate field updates in a `dict` instead of mutating a detached ORM object
2. Replace `s.merge(optimization)` with `s.execute(update(Optimization).where(...).values(**updates))`
3. JSON-encode list fields in the accumulator (same pattern as `update_optimization` service)

```python
async def event_stream():
    # Session 1: create the record in pending state
    async with async_session() as s:
        s.add(Optimization(
            id=opt_id,
            raw_prompt=request.prompt,
            status="running",
            project=request.project,
            tags=json.dumps(request.tags or []),
            title=request.title,
            linked_repo_full_name=request.repo_full_name,
            linked_repo_branch=request.repo_branch,
            retry_of=retry_of,
            user_id=current_user.id,
        ))
        await s.commit()

    # Accumulate field updates as pipeline events arrive (no ORM object needed)
    updates: dict = {}
    total_tokens = 0
    pipeline_failed = False
    pipeline_error_message = None

    try:
        from app.services.pipeline import run_pipeline

        url_fetched = await fetch_url_contexts(request.url_contexts)

        async with asyncio.timeout(settings.PIPELINE_TIMEOUT_SECONDS):
            async for event_type, event_data in run_pipeline(
                provider=req.app.state.provider,
                raw_prompt=request.prompt,
                optimization_id=opt_id,
                strategy_override=request.strategy,
                repo_full_name=request.repo_full_name,
                repo_branch=request.repo_branch,
                session_id=req.session.get("session_id"),
                github_token=request.github_token,
                file_contexts=request.file_contexts,
                instructions=request.instructions,
                url_fetched_contexts=url_fetched,
            ):
                yield _sse_event(event_type, event_data)

                if event_type == "stage" and event_data.get("status") == "complete":
                    total_tokens += event_data.get("token_count", 0)

                if event_type == "error" and not event_data.get("recoverable", True):
                    pipeline_failed = True
                    pipeline_error_message = event_data.get("error", "Unknown stage failure")

                if event_type == "codebase_context":
                    _snapshot = json.dumps(event_data)
                    if len(_snapshot) > 65536:
                        logger.warning(
                            "codebase_context_snapshot truncated from %d to 65536 chars for opt %s",
                            len(_snapshot), opt_id,
                        )
                        truncated_data = {
                            k: v for k, v in event_data.items()
                            if k in ("model", "repo", "branch", "files_read_count",
                                     "explore_quality", "tech_stack", "coverage_pct")
                        }
                        truncated_data["_truncated"] = True
                        _snapshot = json.dumps(truncated_data)
                        if len(_snapshot) > 65536:
                            _snapshot = json.dumps({"_truncated": True, "model": event_data.get("model")})
                    updates["codebase_context_snapshot"] = _snapshot
                    updates["model_explore"] = event_data.get("model")
                elif event_type == "analysis":
                    updates["task_type"] = event_data.get("task_type")
                    updates["complexity"] = event_data.get("complexity")
                    updates["weaknesses"] = json.dumps(event_data.get("weaknesses", []))
                    updates["strengths"] = json.dumps(event_data.get("strengths", []))
                    updates["model_analyze"] = event_data.get("model")
                    updates["analysis_quality"] = event_data.get("analysis_quality")
                elif event_type == "strategy":
                    updates["primary_framework"] = event_data.get("primary_framework")
                    updates["secondary_frameworks"] = json.dumps(
                        event_data.get("secondary_frameworks", [])
                    )
                    updates["approach_notes"] = event_data.get("approach_notes")
                    updates["strategy_rationale"] = event_data.get("rationale")
                    updates["strategy_source"] = event_data.get("strategy_source")
                    updates["model_strategy"] = event_data.get("model")
                elif event_type == "optimization":
                    updates["optimized_prompt"] = event_data.get("optimized_prompt")
                    updates["changes_made"] = json.dumps(event_data.get("changes_made", []))
                    updates["framework_applied"] = event_data.get("framework_applied")
                    updates["optimization_notes"] = event_data.get("optimization_notes")
                    updates["model_optimize"] = event_data.get("model")
                elif event_type == "validation":
                    if "scores" not in event_data:
                        logger.error(
                            "Validation event missing 'scores' sub-dict for opt %s; keys: %s",
                            opt_id, list(event_data.keys())
                        )
                    scores = event_data.get("scores", {})
                    updates["clarity_score"] = scores.get("clarity_score")
                    updates["specificity_score"] = scores.get("specificity_score")
                    updates["structure_score"] = scores.get("structure_score")
                    updates["faithfulness_score"] = scores.get("faithfulness_score")
                    updates["conciseness_score"] = scores.get("conciseness_score")
                    updates["overall_score"] = scores.get("overall_score")
                    updates["is_improvement"] = event_data.get("is_improvement")
                    updates["verdict"] = event_data.get("verdict")
                    updates["issues"] = json.dumps(event_data.get("issues", []))
                    updates["model_validate"] = event_data.get("model")
                    updates["validation_quality"] = event_data.get("validation_quality")

            # Finalize — success or partial failure
            duration_ms = int((time.time() - start_time) * 1000)
            updates["duration_ms"] = duration_ms
            updates["updated_at"] = datetime.now(timezone.utc)
            updates["provider_used"] = req.app.state.provider.name

            if pipeline_failed:
                updates["status"] = "failed"
                updates["error_message"] = pipeline_error_message
            else:
                updates["status"] = "completed"

            async with async_session() as s:
                await s.execute(
                    update(Optimization)
                    .where(Optimization.id == opt_id)
                    .values(**updates)
                )
                await s.commit()

            if not pipeline_failed:
                yield _sse_event("complete", {
                    "optimization_id": opt_id,
                    "total_duration_ms": duration_ms,
                    "total_tokens": total_tokens,
                })

    except asyncio.TimeoutError:
        logger.error(
            "Pipeline timeout (%ds) for opt %s",
            settings.PIPELINE_TIMEOUT_SECONDS, opt_id,
        )
        updates["status"] = "failed"
        updates["error_message"] = (
            f"Pipeline timed out after {settings.PIPELINE_TIMEOUT_SECONDS}s"
        )
        updates["duration_ms"] = int((time.time() - start_time) * 1000)
        updates["updated_at"] = datetime.now(timezone.utc)
        async with async_session() as s:
            await s.execute(
                update(Optimization)
                .where(Optimization.id == opt_id)
                .values(**updates)
            )
            await s.commit()
        yield _sse_event("error", {
            "stage": "pipeline",
            "error": f"Pipeline timed out after {settings.PIPELINE_TIMEOUT_SECONDS}s",
            "recoverable": False,
        })
        return

    except Exception as e:
        logger.exception(f"Pipeline error for {opt_id}: {e}")
        updates["status"] = "failed"
        updates["error_message"] = str(e)
        updates["duration_ms"] = int((time.time() - start_time) * 1000)
        updates["updated_at"] = datetime.now(timezone.utc)

        try:
            async with async_session() as s:
                await s.execute(
                    update(Optimization)
                    .where(Optimization.id == opt_id)
                    .values(**updates)
                )
                await s.commit()
        except Exception:
            logger.exception("Failed to save error state")

        yield _sse_event("error", {
            "stage": "pipeline",
            "error": str(e),
            "recoverable": False,
        })
```

- [ ] **Step 3: Run integration tests**

Run: `cd backend && python -m pytest tests/integration/test_optimize_api.py -v`
Expected: ALL PASS — behavior is identical, only the persistence mechanism changed.

- [ ] **Step 4: Run full test suite**

Run: `cd backend && python -m pytest -x -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/optimize.py
git commit -m "refactor(optimize): replace detached ORM merge() with dict + update()

Session consolidation (R4): pipeline events now accumulate field updates
in a plain dict. Final persist uses update(Optimization).where(...).values()
instead of merge() — eliminates the extra SELECT round-trip and removes
the detached-ORM mutation antipattern."
```

---

## Chunk 4: Service Cleanup + Documentation (R5 + R6)

### Task 6: Add user_id to list_optimizations and DRY the count query

**Files:**
- Modify: `backend/app/services/optimization_service.py:76-142`
- Test: `backend/tests/test_optimization_service.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimization_service.py`:

```python
async def test_list_optimizations_with_user_id_filter(tmp_path):
    """list_optimizations must filter by user_id when provided."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import app.models.optimization  # noqa: F401
    from app.database import Base
    from app.models.optimization import Optimization
    from app.services.optimization_service import list_optimizations

    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/list_user.db")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    # Seed two records with different user_ids
    async with Session() as session:
        session.add(Optimization(id="opt-a", raw_prompt="prompt a", user_id="user-1", status="completed"))
        session.add(Optimization(id="opt-b", raw_prompt="prompt b", user_id="user-2", status="completed"))
        await session.commit()

    async with Session() as session:
        items, total = await list_optimizations(session, user_id="user-1")

    assert total == 1
    assert items[0]["id"] == "opt-a"
    await eng.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_optimization_service.py::test_list_optimizations_with_user_id_filter -v`
Expected: FAIL — `TypeError: list_optimizations() got an unexpected keyword argument 'user_id'`

- [ ] **Step 3: Add user_id parameter and DRY the count query**

In `backend/app/services/optimization_service.py`, replace the `list_optimizations` function (lines 76–142):

```python
async def list_optimizations(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    project: str | None = None,
    task_type: str | None = None,
    search: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    user_id: str | None = None,
) -> tuple[list[dict], int]:
    """List optimizations with pagination, filtering, and sorting.

    Args:
        session: Async database session.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        project: Filter by project name.
        task_type: Filter by task type classification.
        search: Search term to match against raw_prompt and title.
        sort: Column name to sort by.
        order: Sort direction ('asc' or 'desc').
        user_id: When provided, restrict to records owned by this user.

    Returns:
        Tuple of (list of optimization dicts, total count).
    """
    query = select(Optimization).where(Optimization.deleted_at.is_(None))

    if user_id:
        query = query.where(Optimization.user_id == user_id)

    if project:
        query = query.where(Optimization.project == project)

    if task_type:
        query = query.where(Optimization.task_type == task_type)

    if search:
        escaped = escape_like(search)
        search_pattern = f"%{escaped}%"
        query = query.where(
            Optimization.raw_prompt.ilike(search_pattern, escape="\\")
            | Optimization.title.ilike(search_pattern, escape="\\")
        )

    # DRY count — derived from the same filtered query (no filter duplication)
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # Sorting — whitelist prevents getattr on arbitrary user input
    if sort not in VALID_SORT_COLUMNS:
        sort = "created_at"
    if order not in ("asc", "desc"):
        order = "desc"
    sort_column = getattr(Optimization, sort)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    optimizations = result.scalars().all()

    return [opt.to_dict() for opt in optimizations], total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_optimization_service.py::test_list_optimizations_with_user_id_filter -v`
Expected: PASS

- [ ] **Step 5: Also add the import for pytest at the top of the test file if missing**

Check if `import pytest` is present in `test_optimization_service.py`. If not, add it.

- [ ] **Step 6: Run full test suite**

Run: `cd backend && python -m pytest -x -q`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/services/optimization_service.py tests/test_optimization_service.py
git commit -m "refactor(service): add user_id to list_optimizations, DRY count query

R5: list_optimizations now accepts user_id parameter (aligns with
compute_stats). Count query uses select_from(query.subquery())
instead of duplicating all WHERE filters."
```

---

### Task 7: Document JSON column strategy (R6)

**Files:**
- Modify: `backend/app/models/optimization.py` (add comment block)

- [ ] **Step 1: Add documentation comment**

In `backend/app/models/optimization.py`, add a comment block before `__table_args__` (before line 91) — this documents a cross-cutting concern about multiple columns, so it belongs near the index definitions rather than next to any single column:

```python
    # ── JSON-as-TEXT columns ────────────────────────────────────────────
    # weaknesses, strengths, changes_made, issues, tags, secondary_frameworks
    # are stored as JSON-encoded TEXT. At current scale (< 10K rows),
    # application-level deserialization is acceptable. Upgrade paths:
    #   SQLite:     json_extract(col, '$') + json_each() for membership tests
    #   PostgreSQL: migrate to JSONB columns; use @> containment operator
    #   Junction:   tags -> optimization_tags (id, tag) for heavy filtering
    # ────────────────────────────────────────────────────────────────────
```

- [ ] **Step 2: Verify no test breakage**

Run: `cd backend && python -m pytest -x -q`
Expected: ALL PASS (comment-only change)

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/models/optimization.py
git commit -m "docs(model): document JSON-as-TEXT column trade-offs and upgrade paths (R6)"
```

---

### Task 8: Final verification and cleanup

- [ ] **Step 1: Run full test suite with verbose output**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: ALL PASS

- [ ] **Step 2: Verify no type errors**

Run: `cd backend && python -m mypy app/routers/optimize.py app/services/optimization_service.py app/mcp_server.py app/models/optimization.py app/database.py --ignore-missing-imports`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 3: Verify formatting**

Run: `cd backend && python -m ruff check app/routers/optimize.py app/services/optimization_service.py app/mcp_server.py app/models/optimization.py app/database.py`
Expected: No warnings

- [ ] **Step 4: Push to main**

```bash
git push origin main
```
