# Batch Delete Optimizations — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a batch soft-delete endpoint for optimization records, wired end-to-end across backend service layer, HTTP router, MCP server tool, and frontend multi-select UI.

**Architecture:** Service-layer function validates all IDs (existence + ownership) before mutating any rows, then sets `deleted_at` in a single flush. The router at `POST /api/history/batch-delete` handles auth, rate limiting, and Pydantic validation. The MCP server mirrors the operation as a `batch_delete_optimizations` tool. The frontend wires its existing `selectedIds` state to a new "Delete Selected" button with confirmation.

**Tech Stack:** Python 3.14+, FastAPI, SQLAlchemy async, Pydantic v2, SvelteKit 2 (Svelte 5 runes), FastMCP

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/services/optimization_service.py` | Add `batch_delete_optimizations()` service function |
| Modify | `backend/app/routers/history.py` | Add `POST /api/history/batch-delete` endpoint |
| Modify | `backend/app/config.py` | Add `RATE_LIMIT_HISTORY_BATCH_DELETE` setting |
| Modify | `backend/app/mcp_server.py` | Add `batch_delete_optimizations` MCP tool |
| Modify | `frontend/src/lib/api/client.ts` | Add `batchDeleteOptimizations()` API function |
| Modify | `frontend/src/lib/stores/history.svelte.ts` | Add `batchDelete()` store method |
| Modify | `frontend/src/lib/components/layout/NavigatorHistory.svelte` | Add "Delete Selected" button + confirmation |
| Create | `backend/tests/integration/test_batch_delete_api.py` | Integration tests for the batch delete endpoint |

---

## Chunk 1: Backend Service + Config

### Task 1: Add rate limit config

**Files:**
- Modify: `backend/app/config.py:70` (after `RATE_LIMIT_HISTORY_WRITE`)

- [ ] **Step 1: Add `RATE_LIMIT_HISTORY_BATCH_DELETE` to Settings**

In `backend/app/config.py`, add after line 70 (`RATE_LIMIT_HISTORY_WRITE`):

```python
RATE_LIMIT_HISTORY_BATCH_DELETE: str = "10/minute"
```

- [ ] **Step 2: Verify no import errors**

Run: `cd backend && source .venv/bin/activate && python -c "from app.config import settings; print(settings.RATE_LIMIT_HISTORY_BATCH_DELETE)"`
Expected: `10/minute`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add RATE_LIMIT_HISTORY_BATCH_DELETE config setting"
```

---

### Task 2: Add `batch_delete_optimizations` service function

**Files:**
- Modify: `backend/app/services/optimization_service.py` (append after `delete_optimization`)
- Test: `backend/tests/integration/test_batch_delete_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_batch_delete_api.py`:

```python
# backend/tests/integration/test_batch_delete_api.py
"""Integration tests for POST /api/history/batch-delete."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# ── Module-level patch: redirect async_session to the test engine ──────────

@pytest.fixture(scope="module", autouse=True)
def patch_async_session(engine):
    """Redirect app.database.async_session to the test engine's session factory."""
    import app.database as db_module
    import app.routers.optimize as opt_module

    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    with (
        patch.object(db_module, "async_session", TestSession),
        patch.object(opt_module, "async_session", TestSession),
    ):
        yield


# ── Helpers ───────────────────────────────────────────────────────────────

async def _create_optimization(client: AsyncClient, headers: dict, raw_prompt: str = "Test prompt") -> str:
    """Stream /api/optimize and return the created optimization id."""
    opt_id = None
    async with client.stream(
        "POST", "/api/optimize",
        json={"prompt": raw_prompt},
        headers=headers,
        timeout=30,
    ) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("data:") and '"optimization_id"' in line:
                data = json.loads(line[5:].strip())
                if "optimization_id" in data:
                    opt_id = data["optimization_id"]
    assert opt_id, "optimization_id not found in SSE stream"
    return opt_id


# ── POST /api/history/batch-delete ────────────────────────────────────────

async def test_batch_delete_requires_auth(client: AsyncClient):
    resp = await client.post("/api/history/batch-delete", json={"ids": ["fake-id"]})
    assert resp.status_code == 401


async def test_batch_delete_single_item(client: AsyncClient, auth_headers):
    opt_id = await _create_optimization(client, auth_headers, "Batch delete single")
    resp = await client.post(
        "/api/history/batch-delete",
        json={"ids": [opt_id]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_count"] == 1
    assert body["ids"] == [opt_id]

    # Verify not in listing
    list_resp = await client.get("/api/history", headers=auth_headers)
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert opt_id not in ids


async def test_batch_delete_multiple_items(client: AsyncClient, auth_headers):
    id1 = await _create_optimization(client, auth_headers, "Batch multi 1")
    id2 = await _create_optimization(client, auth_headers, "Batch multi 2")
    id3 = await _create_optimization(client, auth_headers, "Batch multi 3")

    resp = await client.post(
        "/api/history/batch-delete",
        json={"ids": [id1, id2, id3]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_count"] == 3
    assert set(body["ids"]) == {id1, id2, id3}


async def test_batch_delete_404_when_id_missing(client: AsyncClient, auth_headers):
    opt_id = await _create_optimization(client, auth_headers, "Batch 404 test")
    resp = await client.post(
        "/api/history/batch-delete",
        json={"ids": [opt_id, "nonexistent-id-12345"]},
        headers=auth_headers,
    )
    assert resp.status_code == 404

    # Original record must NOT have been deleted (all-or-nothing)
    list_resp = await client.get("/api/history", headers=auth_headers)
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert opt_id in ids


async def test_batch_delete_403_when_not_owner(client: AsyncClient, auth_headers, other_auth_headers):
    opt_id = await _create_optimization(client, auth_headers, "Batch 403 test")
    resp = await client.post(
        "/api/history/batch-delete",
        json={"ids": [opt_id]},
        headers=other_auth_headers,
    )
    assert resp.status_code == 403


async def test_batch_delete_400_when_over_50_ids(client: AsyncClient, auth_headers):
    fake_ids = [f"fake-id-{i}" for i in range(51)]
    resp = await client.post(
        "/api/history/batch-delete",
        json={"ids": fake_ids},
        headers=auth_headers,
    )
    assert resp.status_code == 422  # Pydantic validation error


async def test_batch_delete_400_when_empty_ids(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/history/batch-delete",
        json={"ids": []},
        headers=auth_headers,
    )
    assert resp.status_code == 422  # Pydantic validation error


async def test_batch_delete_items_appear_in_trash(client: AsyncClient, auth_headers):
    opt_id = await _create_optimization(client, auth_headers, "Batch trash check")
    await client.post(
        "/api/history/batch-delete",
        json={"ids": [opt_id]},
        headers=auth_headers,
    )
    trash_resp = await client.get("/api/history/trash", headers=auth_headers)
    trash_ids = [item["id"] for item in trash_resp.json()["items"]]
    assert opt_id in trash_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/integration/test_batch_delete_api.py::test_batch_delete_single_item -v --timeout=30 2>&1 | tail -5`
Expected: FAIL (endpoint does not exist yet → 404 or 405)

- [ ] **Step 3: Add `batch_delete_optimizations` to the service layer**

In `backend/app/services/optimization_service.py`, append after the `delete_optimization` function (after line 433):

```python
async def batch_delete_optimizations(
    session: AsyncSession,
    user_id: str,
    ids: list[str],
) -> list[str]:
    """Batch soft-delete optimizations by setting deleted_at.

    All-or-nothing semantics: validates existence and ownership of every ID
    before mutating any rows. Raises HTTPException on validation failure.

    Args:
        session: Async database session (transaction-scoped).
        user_id: Authenticated user's ID — all records must belong to this user.
        ids: List of optimization UUIDs to soft-delete (1–50 items).

    Returns:
        List of deleted optimization IDs.

    Raises:
        HTTPException 404: If any ID does not exist (or is already deleted).
        HTTPException 403: If any record belongs to a different user.
    """
    from fastapi import HTTPException

    from app.schemas.auth import ERR_INSUFFICIENT_PERMISSIONS

    # Fetch all records matching the provided IDs (including other users' records
    # so we can distinguish 404 vs 403).
    result = await session.execute(
        select(Optimization).where(
            Optimization.id.in_(ids),
            Optimization.deleted_at.is_(None),
        )
    )
    records = {opt.id: opt for opt in result.scalars().all()}

    # Validate: every requested ID must exist
    missing = [oid for oid in ids if oid not in records]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Optimization(s) not found: {', '.join(missing)}",
        )

    # Validate: every record must belong to the authenticated user
    unauthorized = [oid for oid, opt in records.items() if opt.user_id != user_id]
    if unauthorized:
        raise HTTPException(
            status_code=403,
            detail={
                "code": ERR_INSUFFICIENT_PERMISSIONS,
                "message": "Not authorized to delete one or more optimizations",
            },
        )

    # All checks passed — mutate
    now = datetime.now(timezone.utc)
    for opt in records.values():
        opt.deleted_at = now
    await session.flush()

    deleted_ids = list(records.keys())
    logger.info("Batch soft-deleted %d optimizations for user %s", len(deleted_ids), user_id)
    return deleted_ids
```

- [ ] **Step 4: Run test to verify service function exists (still fails at router level)**

Run: `cd backend && source .venv/bin/activate && python -c "from app.services.optimization_service import batch_delete_optimizations; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/optimization_service.py backend/tests/integration/test_batch_delete_api.py
git commit -m "feat: add batch_delete_optimizations service function and integration tests"
```

---

### Task 3: Add `POST /api/history/batch-delete` router endpoint

**Files:**
- Modify: `backend/app/routers/history.py` (add endpoint + Pydantic models)

- [ ] **Step 1: Add Pydantic request/response models and endpoint**

In `backend/app/routers/history.py`, add the imports and models near the top (after the existing imports, before the router definition):

Add to imports at line 2:
```python
from pydantic import BaseModel, field_validator
```

Add after the `VALID_STATUSES` definition (line 21), before the first route:

```python
class BatchDeleteRequest(BaseModel):
    ids: list[str]

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, v: list[str]) -> list[str]:
        if len(v) < 1:
            raise ValueError("At least one ID is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 IDs per batch delete request")
        return v


class BatchDeleteResponse(BaseModel):
    deleted_count: int
    ids: list[str]
```

Add the endpoint **before** the single-item `DELETE /api/history/{optimization_id}` (before line 115), to avoid route shadowing:

```python
@router.post("/api/history/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_optimizations(
    request: Request,
    body: BatchDeleteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rl: None = Depends(RateLimit(lambda: settings.RATE_LIMIT_HISTORY_BATCH_DELETE)),
):
    """Batch soft-delete optimization records (user-scoped, all-or-nothing)."""
    from app.services.optimization_service import batch_delete_optimizations as svc_batch_delete

    deleted_ids = await svc_batch_delete(session, current_user.id, body.ids)
    # TODO: Fire notification event when notification service is available
    # e.g. notify(event="optimizations_batch_deleted", user_id=current_user.id,
    #             deleted_ids=deleted_ids, deleted_count=len(deleted_ids))
    logger.info(
        "Batch-deleted %d optimizations by user %s",
        len(deleted_ids), current_user.id,
    )
    return BatchDeleteResponse(deleted_count=len(deleted_ids), ids=deleted_ids)
```

- [ ] **Step 2: Run the integration tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/integration/test_batch_delete_api.py -v --timeout=60 2>&1 | tail -20`
Expected: All 8 tests PASS

- [ ] **Step 3: Run the full history test suite to check for regressions**

Run: `cd backend && source .venv/bin/activate && pytest tests/integration/test_history_api.py -v --timeout=60 2>&1 | tail -20`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/history.py
git commit -m "feat: add POST /api/history/batch-delete endpoint with Pydantic validation"
```

---

## Chunk 2: MCP Server Tool

### Task 4: Add `batch_delete_optimizations` MCP tool

**Files:**
- Modify: `backend/app/mcp_server.py` (add tool inside `create_mcp_server()`)

- [ ] **Step 1: Add the MCP tool**

In `backend/app/mcp_server.py`, add after the `restore_optimization` tool (after line 601), before the `search_optimizations` tool:

```python
    @mcp.tool(
        name="batch_delete_optimizations",
        annotations=ToolAnnotations(
            title="Batch Delete Optimizations",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def batch_delete_optimizations(
        ids: list[str], user_id: Optional[str] = None
    ) -> str:
        """Batch soft-delete multiple optimization records (sets deleted_at; purged after 7 days).

        All-or-nothing: if any ID is not found, none are deleted.
        Maximum 50 IDs per request.

        Args:
            ids: List of optimization UUIDs to delete (1–50 items).
                 Use list_optimizations to discover valid IDs.
            user_id: Optional owner filter. When set, all records must belong to
                     this user. Omit for unscoped access (single-user/localhost mode).

        Returns:
            JSON {"deleted_count": N, "ids": [...]} on success.
            Returns {"error": ...} on validation failure.
        """
        if len(ids) < 1 or len(ids) > 50:
            return json.dumps({
                "error": "ids must contain 1–50 items",
                "count": len(ids),
            })

        from app.services.optimization_service import (
            batch_delete_optimizations as svc_batch_delete,
        )

        try:
            async with async_session() as session:
                deleted_ids = await svc_batch_delete(session, user_id or "", ids)
                await session.commit()
        except Exception as e:
            # Service raises HTTPException for 404/403 — extract detail
            detail = getattr(e, "detail", str(e))
            status = getattr(e, "status_code", 500)
            return json.dumps({"error": detail, "status": status})

        return json.dumps({"deleted_count": len(deleted_ids), "ids": deleted_ids})
```

- [ ] **Step 2: Verify MCP server imports and tool compiles**

Run: `cd backend && source .venv/bin/activate && python -c "from app.mcp_server import create_mcp_server; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/mcp_server.py
git commit -m "feat: add batch_delete_optimizations MCP tool"
```

---

## Chunk 3: Frontend Wiring

### Task 5: Add `batchDeleteOptimizations` API client function

**Files:**
- Modify: `frontend/src/lib/api/client.ts`

- [ ] **Step 1: Add the batch delete API function**

In `frontend/src/lib/api/client.ts`, add after `deleteOptimization` (after line 378):

```typescript
export interface BatchDeleteResponse {
  deleted_count: number;
  ids: string[];
}

export async function batchDeleteOptimizations(ids: string[]): Promise<BatchDeleteResponse> {
  const res = await apiFetch(`${BASE}/api/history/batch-delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Batch delete failed: ${res.status}` }));
    const msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
    throw new Error(msg);
  }
  return res.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api/client.ts
git commit -m "feat: add batchDeleteOptimizations API client function"
```

---

### Task 6: Add batch delete to history store

**Files:**
- Modify: `frontend/src/lib/stores/history.svelte.ts`

- [ ] **Step 1: Add the import and store method**

In `frontend/src/lib/stores/history.svelte.ts`, update the import at line 1:

```typescript
import { fetchHistory, fetchHistoryTrash, restoreOptimization, batchDeleteOptimizations } from '$lib/api/client';
```

Add the `batchDelete` method to `HistoryStore` class (after `restoreItem`, before the closing `}`):

```typescript
  async batchDelete(ids: string[]): Promise<boolean> {
    try {
      const result = await batchDeleteOptimizations(ids);
      // Remove deleted entries from local state
      const deletedSet = new Set(result.ids);
      this.entries = this.entries.filter(e => !deletedSet.has(e.id));
      this.totalCount = Math.max(0, this.totalCount - result.deleted_count);
      if (this.selectedId && deletedSet.has(this.selectedId)) {
        this.selectedId = null;
      }
      toast.success(`Deleted ${result.deleted_count} optimization${result.deleted_count > 1 ? 's' : ''}`);
      return true;
    } catch (err) {
      toast.error(`Batch delete failed: ${(err as Error).message}`);
      return false;
    }
  }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/stores/history.svelte.ts
git commit -m "feat: add batchDelete method to history store"
```

---

### Task 7: Add "Delete Selected" button to NavigatorHistory

**Files:**
- Modify: `frontend/src/lib/components/layout/NavigatorHistory.svelte`

- [ ] **Step 1: Add the import for batchDeleteOptimizations**

In `NavigatorHistory.svelte`, update the import at line 6 to include `batchDeleteOptimizations`:

```typescript
import { fetchHistory, fetchHistoryStats, fetchOptimization, deleteOptimization, fetchHistoryTrash, restoreOptimization, patchOptimization, batchDeleteOptimizations, type HistoryStats, type HistoryResponse } from '$lib/api/client';
```

- [ ] **Step 2: Add a confirmation state variable and handler**

Add after line 14 (`let selectedIds = ...`):

```typescript
let confirmBatchDelete = $state(false);
```

Add the batch delete handler after the `clearSelection` function (after line 62):

```typescript
  async function handleBatchDelete() {
    if (!confirmBatchDelete) {
      confirmBatchDelete = true;
      return;
    }
    confirmBatchDelete = false;
    const ids = Array.from(selectedIds);
    const success = await history.batchDelete(ids);
    if (success) {
      selectedIds = new Set();
      await loadStats();
    }
  }

  function cancelBatchDelete() {
    confirmBatchDelete = false;
  }
```

- [ ] **Step 3: Update the selection toolbar UI**

Replace the existing selection toolbar (lines 398–416, the `{#if selectedIds.size >= 2}` block) with a version that shows at `selectedIds.size >= 1` and includes both Compare and Delete Selected:

```svelte
    {#if selectedIds.size >= 1}
      <div class="px-2 py-1.5 border-b border-neon-cyan/20 bg-neon-cyan/5 flex items-center justify-between">
        <span class="text-[10px] text-neon-cyan">{selectedIds.size} selected</span>
        <div class="flex items-center gap-1">
          {#if selectedIds.size === 2}
            <button
              class="text-[10px] px-2 py-0.5 bg-neon-cyan/20 border border-neon-cyan/30 text-neon-cyan hover:bg-neon-cyan/30 transition-colors"
              onclick={handleCompare}
            >
              Compare
            </button>
          {/if}
          {#if confirmBatchDelete}
            <span class="text-[10px] text-neon-red">Confirm?</span>
            <button
              class="text-[10px] px-2 py-0.5 bg-neon-red/20 border border-neon-red/40 text-neon-red hover:bg-neon-red/30 transition-colors"
              onclick={handleBatchDelete}
            >
              Yes, delete
            </button>
            <button
              class="text-[10px] px-1.5 py-0.5 text-text-dim hover:text-text-secondary transition-colors"
              onclick={cancelBatchDelete}
            >
              No
            </button>
          {:else}
            <button
              class="text-[10px] px-2 py-0.5 bg-neon-red/10 border border-neon-red/20 text-neon-red/70 hover:text-neon-red hover:border-neon-red/40 hover:bg-neon-red/20 transition-colors"
              onclick={handleBatchDelete}
            >
              Delete Selected
            </button>
          {/if}
          <button
            class="text-[10px] px-1.5 py-0.5 text-text-dim hover:text-text-secondary transition-colors"
            onclick={() => { clearSelection(); cancelBatchDelete(); }}
          >
            Cancel
          </button>
        </div>
      </div>
    {/if}
```

- [ ] **Step 4: Verify frontend compiles**

Run: `cd frontend && npm run check 2>&1 | tail -10`
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/layout/NavigatorHistory.svelte
git commit -m "feat: add Delete Selected button to history sidebar with confirmation"
```

---

## Chunk 4: Verification

### Task 8: Run full test suite and verify end-to-end

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/ -v --timeout=60 2>&1 | tail -30`
Expected: All tests PASS, no regressions

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npm run check 2>&1 | tail -10`
Expected: No type errors

- [ ] **Step 3: Verify backend starts without errors**

Run: `cd backend && source .venv/bin/activate && timeout 5 python -c "from app.main import app; print('Routes:', [r.path for r in app.routes if hasattr(r, 'path') and 'batch' in r.path])" 2>&1`
Expected: Shows the batch-delete route

- [ ] **Step 4: Final commit (if any lint/type fixes needed)**

```bash
git add -A
git commit -m "fix: address lint/type issues from batch delete implementation"
```
