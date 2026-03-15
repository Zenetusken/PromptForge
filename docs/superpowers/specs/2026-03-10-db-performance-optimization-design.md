# Database Performance & Correctness Optimization

**Date**: 2026-03-10
**Status**: Approved
**Scale profile**: Small/moderate (< 10K rows, < 10 concurrent users)
**Approach**: C (full optimization suite)

## Context

Production audit of the SQLAlchemy 2.x async database layer (SQLite + aiosqlite) surfaced six concerns: soft-delete filter gaps, unused user_id index, missing composite index, fragile session management in the SSE streaming endpoint, service-layer DRY violations, and JSON TEXT columns blocking DB-level filtering.

## Recommendations

### R1: Soft-Delete Filter Gaps

**Category**: Data integrity / correctness
**Severity**: HIGH
**Affected files**: `backend/app/routers/optimize.py`, `backend/app/mcp_server.py`

#### Problem

Three router endpoints and one MCP helper fetch by PK without `deleted_at.is_(None)`:

1. `optimize.py:277` — PATCH endpoint
2. `optimize.py:318` — retry endpoint
3. `mcp_server.py:79` — `_opt_session()` (shared by get, tag, retry MCP tools)

Note: `optimize.py:263` (GET) calls `get_optimization_orm()` which does filter correctly.

#### Solution

Add `Optimization.deleted_at.is_(None)` to all three WHERE clauses.

#### Rationale

Soft-deleted records in the 7-day limbo can be mutated or retried, violating the soft-delete contract.

---

### R2: Push user_id Into SQL WHERE

**Category**: Security / query efficiency
**Severity**: MEDIUM
**Affected files**: `backend/app/routers/optimize.py`

#### Problem

GET, PATCH, and retry endpoints fetch by PK, then check `user_id` in Python post-fetch. The `idx_optimizations_user_id` index is never exercised, and the pattern is vulnerable to future code paths forgetting the Python guard.

#### Solution

Push `Optimization.user_id == current_user.id` into the SQL WHERE clause for all three endpoints. The Python ownership check becomes redundant once the SQL WHERE enforces it — remove the post-fetch guard.

For GET: this means replacing the `get_optimization_orm()` call (which filters `deleted_at` but not `user_id`) with an inline query that includes both `deleted_at.is_(None)` and `user_id == current_user.id`. Do NOT remove the Python guard until the SQL-layer equivalent is in place.

For PATCH and retry: add both `deleted_at.is_(None)` (R1) and `user_id` to the existing inline WHERE clause, then remove the Python guard.

#### Rationale

Defense-in-depth. SQL-layer enforcement is atomic — no TOCTOU gap.

---

### R3: Composite Index for History Listing

**Category**: Query performance
**Severity**: MEDIUM
**Affected files**: `backend/app/models/optimization.py`, `backend/app/database.py`

#### Problem

`GET /api/history` filters `WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC`. The single-column `idx_optimizations_user_id` doesn't cover the full access pattern.

#### Solution

Add composite index `(user_id, deleted_at, created_at DESC)` to model `__table_args__` and `_migrate_add_missing_indexes`. Keep the standalone `idx_optimizations_user_id` for now (leftmost-prefix overlap is harmless).

#### Rationale

One index covers ~90% of DB reads. SQLite can satisfy WHERE + ORDER BY from the index alone.

---

### R4: Session Consolidation in SSE Endpoint

**Category**: Maintainability / efficiency
**Severity**: MEDIUM
**Affected files**: `backend/app/routers/optimize.py`

#### Problem

`event_stream()` mutates a detached ORM object, then calls `merge()` (which performs SELECT + UPDATE) in one of three mutually exclusive session blocks. Fragile: any lazy-load access raises `DetachedInstanceError`.

#### Solution

Replace detached ORM mutation with a plain dict accumulator. Replace `merge()` with explicit `update(Optimization).where(...).values(**updates)` — eliminates the extra SELECT.

#### Rationale

Removes detached-ORM antipattern. Dict accumulation is immune to `DetachedInstanceError`. One fewer round-trip per pipeline run.

---

### R5: Service-Layer list_optimizations Cleanup

**Category**: DRY / consistency
**Severity**: LOW
**Affected files**: `backend/app/services/optimization_service.py`

#### Problem

1. No `user_id` parameter (unlike `compute_stats()`). MCP `list_optimizations` tool calls this function without user scoping.
2. Count query manually duplicates all WHERE filters instead of using `select_from(query.subquery())`.

Note: The `history.py` router builds its own query (8 filters) instead of calling this service function (3 filters). This divergence is justified by the filter complexity gap — adding `user_id` here does NOT aim to unify the two query paths.

#### Solution

Add `user_id: str | None = None` parameter. Use subquery count pattern to eliminate internal filter duplication within `list_optimizations()` itself.

---

### R6: JSON Column Strategy

**Category**: Schema design / future-proofing
**Severity**: LOW
**Affected files**: `backend/app/models/optimization.py` (documentation only)

#### Problem

Six columns store JSON arrays as TEXT. No DB-level filtering possible.

#### Solution — Phased

- **Phase 1 (now)**: Document the trade-off and upgrade path in a code comment.
- **Phase 2 (when needed)**: Extract `tags` to a junction table for heavy filtering.
- **Phase 3 (PostgreSQL migration)**: Convert all six to JSONB.

#### Rationale

At < 10K rows, premature normalization adds complexity with no measurable benefit.

---

## Summary

| # | Title | Severity | Migration? |
|---|-------|----------|-----------|
| R1 | Soft-delete filter gaps | HIGH | No |
| R2 | Push user_id into SQL WHERE | MEDIUM | No |
| R3 | Composite index for history | MEDIUM | Yes (idempotent) |
| R4 | Session consolidation (SSE) | MEDIUM | No |
| R5 | Service list_optimizations cleanup | LOW | No |
| R6 | JSON column strategy | LOW | No (phased) |

## Constraints

- Must maintain SQLite + PostgreSQL dual compatibility
- Async-first (AsyncSession throughout)
- Idempotent migrations (safe to re-run on every startup)
- Do not alter Pydantic response schemas
- Do not change the SSE `(event_type, event_data)` streaming tuple contract
