# GitHub Connection State & Visibility Fixes

**Date:** 2026-04-10  
**Scope:** 2 critical bugs + 8 high + 7 medium severity gaps (connection state, project visibility, auth lifecycle)  
**Out of scope:** Project switcher/filtering (ADR-005 Phase 3 — separate implementation cycle)

## Problem

The frontend has no unified concept of "GitHub connection state." Every component independently checks combinations of `githubStore.user`, `githubStore.linkedRepo`, `githubStore.authExpired` to infer state. This causes:

1. **Reconnect button is dead code** — `_handleAuthError()` sets both `authExpired = true` AND `user = null`. The reconnect button renders inside `{:else if githubStore.user}` (Navigator.svelte:663), which is ALWAYS false when `authExpired` is true. Separately, when `linkedRepo` exists, the outermost `{#if githubStore.linkedRepo}` branch is taken, bypassing the reconnect block entirely. Two independent failures make the button permanently unreachable after token expiry.
2. **`authExpired` flag stuck** — `checkAuth()` null path and `logout()` don't reset `authExpired`, leaving it stale across sessions.
3. **No visible connection indicator** — users can't tell if GitHub is connected, expired, or indexing.
4. **Project affiliation invisible** — history, inspector, artifact don't show which project/repo owns an optimization despite backend already returning this data.

## Architecture: Unified Connection State

### State Model

```typescript
type GitHubConnectionState =
  | 'disconnected'    // no user, no linkedRepo, no authExpired
  | 'expired'         // authExpired=true (token revoked/expired, stale linkedRepo may persist)
  | 'authenticated'   // user set, no linkedRepo yet
  | 'linked'          // user + linkedRepo, index building or not yet loaded
  | 'ready'           // user + linkedRepo + index loaded and not building
```

Note: In the `'expired'` state, `user` is always null (set by `_handleAuthError`), but `linkedRepo` may persist so the Info tab can still show which repo was connected.

### Derivation (`github.svelte.ts`)

```typescript
get connectionState(): GitHubConnectionState {
  if (this.authExpired) return 'expired';
  if (!this.user) return 'disconnected';
  if (!this.linkedRepo) return 'authenticated';
  // indexStatus null = not yet loaded; treat as 'linked' until confirmed ready
  if (!this.indexStatus || this.indexStatus.status === 'building') return 'linked';
  return 'ready';
}
```

### Color Mapping (CSS custom properties)

| State | CSS Variable | StatusBar text |
|-------|-------------|----------------|
| `disconnected` | (hidden — no element rendered) | — |
| `expired` | `var(--color-neon-red)` | `session expired` |
| `authenticated` | `var(--color-neon-yellow)` | `no repo` |
| `linked` | `var(--color-neon-cyan)` | `indexing...` |
| `ready` | `var(--color-text-dim)` | repo short name |

## Changes by File

### 1. Store: `github.svelte.ts`

**Bug #2 fix — `authExpired` reset in all exit paths:**
- `checkAuth()` null branch (`else { this.user = null; }`): add `this.authExpired = false;`
- `checkAuth()` null branch: also clear `this.linkedRepo = null;` — if the server says "not authenticated" (not a 401 error, just null), there's no valid session. Keeping a stale `linkedRepo` creates the gap state `user=null, authExpired=false, linkedRepo={exists}` which the `connectionState` derivation maps to `'disconnected'` despite having stale data.
- `logout()`: add `this.authExpired = false;` (currently missing, reconnect flow would leave flag stale)
- `_reset()`: already resets — no change needed

**New method — `reconnect()`:**
```typescript
async reconnect() {
  this.authExpired = false;
  this.linkedRepo = null;  // allow device flow UI to render
  this.fileTree = [];
  this.branches = [];
  this.indexStatus = null;
  await this.login();  // await so callers can track loading if needed
}
```

**Cleanup: `checkAuth()` catch branch.** The catch block currently calls `_handleAuthError(err)`, but `githubMe()` uses `tryFetch` (returns null on 401, doesn't throw). The catch only fires on network-level errors where `_handleAuthError` is a no-op. Clean up: remove the `_handleAuthError` call in the catch, keep only `this.user = null`.

**New derived:** Add `get connectionState(): GitHubConnectionState` as specified above.

**Index auto-load:** `loadLinked()` already calls `loadIndexStatus()` when `linkedRepo` exists (line 179). No change needed — verify only.

### 2. Types: `client.ts`

**`OptimizationResult`** — add field to match backend `OptimizationDetail` response:
```typescript
repo_full_name?: string | null;  // already returned by backend (optimize.py:70), missing from frontend type
```
This is a **type-only change** — the backend SSE pipeline and REST endpoints already serialize `repo_full_name`. The data already flows to the frontend; the TypeScript interface just doesn't expose it. No backend changes needed.

Note: `project_id` is NOT in the backend `OptimizationDetail` serializer today. Adding it requires a backend change — deferred to project switcher scope (ADR-005 Phase 3).

**`LinkedRepo`** — add field already returned by backend but missing from frontend type:
```typescript
linked_at?: string | null;  // backend already returns this (github_repos.py:62)
```

### 3. Backend: `optimize.py` (minor — type alignment)

**Verify** that `OptimizationDetail` (line 30-73) already includes `repo_full_name`. If yes, the frontend type addition is sufficient. If not, add it to the serializer `_serialize_optimization()`.

No other backend changes needed for this scope. Server-side project filtering on history (`?project_id=`) is ADR-005 Phase 3.

### 4. Navigator: `Navigator.svelte`

**Bug #1 fix — auth-expired banner with reconnect button:**

The reconnect UI must render inside the `{#if githubStore.linkedRepo}` branch (the Info tab), not inside the `{:else if githubStore.user}` branch where it currently lives as dead code.

**Critical: reconnect flow mechanics.** The device flow UI (user code display, "Copy code & open GitHub" button) renders at Navigator.svelte:745 inside the `{:else}` branch, which requires BOTH `linkedRepo` AND `user` to be falsy. Since `linkedRepo` persists through auth expiry, clicking Reconnect must clear it first so the template falls through to the device flow branch. After re-authentication completes, the user re-links via the repo picker (which re-creates the linked repo with a fresh session).

Reconnect handler: `githubStore.reconnect()` — a new store method that:
1. Clears `authExpired = false`
2. Clears `linkedRepo = null` (allows device flow UI to render)
3. Calls `this.login()` to start device flow

This matches the existing dead-code reconnect button's intent (`Navigator.svelte:675`: `githubStore.authExpired = false; githubStore.logout(); githubStore.login()`), but avoids calling `logout()` which hits the backend (and fails if the token is already deleted).

```svelte
<!-- This block is INSIDE the {#if githubStore.linkedRepo} branch,
     so linkedRepo is always truthy when this renders. -->
{#if githubStore.connectionState === 'expired'}
  <div class="auth-expired-banner">
    <span>GitHub session expired</span>
    <button class="action-btn action-btn--primary"
      onclick={() => githubStore.reconnect()}
    >Reconnect</button>
  </div>
{/if}
```

After clicking Reconnect:
1. `linkedRepo` → null, `authExpired` → false → state = `'disconnected'`
2. Template falls to `{:else}` branch → device flow UI renders with user code
3. User completes device flow → `checkAuth()` → state = `'authenticated'`
4. User re-links repo via picker → state = `'linked'` → `'ready'`

Brand: `border-radius: 0`, `border: 1px solid var(--color-neon-red)`, no shadows, no gradients.

**Info tab — connection status badge:**

Add a status indicator at the top of the GitHub panel section header, reading from `connectionState`:
```svelte
{#if githubStore.connectionState !== 'disconnected'}
  <span class="connection-badge" style="color: {connectionColor}">{connectionLabel}</span>
{/if}
```
Where `connectionColor` and `connectionLabel` are derived from the color mapping table above using CSS custom properties.

**Info tab — project_label null state:**

When `linkedRepo.project_label` is null, show `(pending)` instead of hiding the row entirely. The backend auto-creates project nodes on repo link, but there's a brief window before the taxonomy event fires.

**History rows — project visibility (read-only, no filtering):**

`HistoryItem` already includes `project_id` from the backend. When rendering history rows, if `item.project_id` exists, show the project label as a subtle badge.

**Project label cache:** Use the existing `listProjects()` function (already in `client.ts:358`, already imported by `Navigator.svelte:17`). Call it in a `$effect` on Navigator mount (not only when repo picker opens). Store the result in a local `projectLabelMap: Record<string, string>` derived from the response. Refresh mechanism: Navigator already listens for `optimization-event` CustomEvent (line 236) to refresh history — add `listProjects()` re-fetch to the same handler since `taxonomy_changed` SSE already triggers `clustersStore.invalidateClusters()` in `+page.svelte:117` which fires the CustomEvent indirectly. Alternatively, watch `clustersStore.taxonomyTree` length changes via `$effect` as a trigger. Stale cache gracefully degrades — unknown IDs show nothing (not "Unknown").

No project dropdown/filter. No client-side filtering. This is display-only, using data already returned by the API.

### 5. StatusBar: `StatusBar.svelte`

Replace the current simple project badge with a connection-state-aware indicator:

```svelte
{#if githubStore.connectionState === 'ready'}
  <span class="status-github" style="color: var(--color-text-dim)"
    use:tooltip={`Project: ${githubStore.linkedRepo.full_name}`}
  >{githubStore.linkedRepo.full_name.split('/')[1]}</span>
{:else if githubStore.connectionState === 'linked'}
  <span class="status-github" style="color: var(--color-neon-cyan)">indexing...</span>
{:else if githubStore.connectionState === 'expired'}
  <span class="status-github" style="color: var(--color-neon-red)">session expired</span>
{:else if githubStore.connectionState === 'authenticated'}
  <span class="status-github" style="color: var(--color-neon-yellow)">no repo</span>
{/if}
```

CSS: `font-family: var(--font-mono); font-size: 10px; white-space: nowrap; border-radius: 0;`

### 6. Inspector: `Inspector.svelte`

**Cluster detail — project info (behavior change):**

`ClusterDetail` already returns `project_ids` and `member_counts_by_project` from the backend. The existing Inspector code at line 215 only shows project info for multi-project clusters (`length > 1`). This change lowers the threshold to `length > 0` so single-project clusters also show their project affiliation — making the ADR-005 project hierarchy visible at all times:
```svelte
{#if clusterDetail.project_ids?.length > 0}
  <div class="data-row">
    <span class="data-label">Project</span>
    <span class="data-value font-mono">
      {#if clusterDetail.project_ids.length === 1}
        {projectLabelMap[clusterDetail.project_ids[0]] ?? 'Unknown'}
      {:else}
        {clusterDetail.project_ids.length} projects
      {/if}
    </span>
  </div>
{/if}
```

**Optimization detail — repo context:**

When `activeResult?.repo_full_name` exists:
```svelte
{#if activeResult?.repo_full_name}
  <div class="data-row">
    <span class="data-label">Repo</span>
    <span class="data-value font-mono">{activeResult.repo_full_name}</span>
  </div>
{/if}
```

### 7. ForgeArtifact: `ForgeArtifact.svelte`

When `result?.repo_full_name` exists, show a subtle context line:
```svelte
{#if result?.repo_full_name}
  <span class="artifact-repo-context font-mono">{result.repo_full_name}</span>
{/if}
```

CSS: `font-size: 10px; color: var(--color-text-dim); border-radius: 0;`

### 8. Reactivity: `+page.svelte` / `+layout.svelte`

No changes needed for this scope. The `connectionState` derived is reactive — components that read it via `githubStore.connectionState` will re-render automatically. No CustomEvents or manual event dispatch required.

Project-scoped topology filtering (`loadTree(projectId)`) is deferred to ADR-005 Phase 3.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Token expires with linkedRepo | `connectionState = 'expired'`, Info tab shows repo data + reconnect banner, StatusBar shows "session expired" in red |
| Token expires without linkedRepo | `connectionState = 'expired'`, GitHub panel shows "Connect GitHub" + "session expired" text |
| Reconnect clicked (with linkedRepo) | `reconnect()` clears `linkedRepo` + `authExpired` → state = `'disconnected'` → template falls to `{:else}` → device flow UI renders. User completes flow → `checkAuth()` → state = `'authenticated'` → user re-links repo via picker → `'linked'` → `'ready'` |
| Reconnect clicked (without linkedRepo) | Same flow, template already in `{:else}` branch |
| `checkAuth()` returns null (not error) | `user = null`, `linkedRepo = null`, `authExpired = false` → state = `'disconnected'` (clean slate) |
| Fresh page load, no GitHub | `connectionState = 'disconnected'`, no StatusBar indicator, GitHub panel shows "Connect GitHub" |
| Repo linked, index building | `connectionState = 'linked'`, StatusBar shows "indexing..." in cyan |
| `indexStatus` not yet loaded | `connectionState = 'linked'` (null treated as not-ready, conservative) |
| `logout()` called | `authExpired` reset to false, `user` and `linkedRepo` cleared, state → `'disconnected'` |

## Testing

**Store tests (`github.svelte.test.ts`):**
- `connectionState` returns `'disconnected'` when user=null, linkedRepo=null, authExpired=false
- `connectionState` returns `'expired'` when authExpired=true (regardless of linkedRepo)
- `connectionState` returns `'authenticated'` when user set, linkedRepo=null
- `connectionState` returns `'linked'` when user + linkedRepo, indexStatus=null
- `connectionState` returns `'linked'` when user + linkedRepo, indexStatus.status='building'
- `connectionState` returns `'ready'` when user + linkedRepo, indexStatus.status='ready'
- `checkAuth` resets `authExpired` on null return (not error)
- `logout` resets `authExpired`

**Component tests:**
- Navigator renders reconnect button when `connectionState === 'expired'` AND `linkedRepo` exists
- Navigator: clicking Reconnect clears `linkedRepo` and starts device flow (verifies template falls to device flow branch)
- StatusBar renders all 4 visible connection states with correct colors
- Inspector shows repo context row when `activeResult.repo_full_name` exists
- History rows show project label when `item.project_id` exists

## Files Modified

| File | Changes |
|------|---------|
| `frontend/src/lib/stores/github.svelte.ts` | `connectionState` getter, `reconnect()` method, `authExpired` reset in `checkAuth`+`logout`, `linkedRepo` clear in `checkAuth` null path, type export |
| `frontend/src/lib/api/client.ts` | `OptimizationResult.repo_full_name`, `LinkedRepo.linked_at` |
| `frontend/src/lib/components/layout/Navigator.svelte` | Auth-expired banner + reconnect, connection badge, project_label null state, history project badges |
| `frontend/src/lib/components/layout/StatusBar.svelte` | Connection-state-aware GitHub indicator (replaces simple project badge) |
| `frontend/src/lib/components/layout/Inspector.svelte` | Project breadcrumb in cluster detail, repo context in optimization detail |
| `frontend/src/lib/components/editor/ForgeArtifact.svelte` | Repo context line |
| `backend/app/routers/optimize.py` | Verify `repo_full_name` in `OptimizationDetail` (likely already present) |
| Tests: `github.svelte.test.ts` + component tests | ~12 new test cases |

## Out of Scope (ADR-005 Phase 3 / Future Roadmap)

- **Project switcher dropdown** — requires server-side `?project_id` filtering on history, tree param plumbing through `getClusterTree()`/`loadTree()`, localStorage persistence, stale-ID validation. Separate implementation cycle.
- **Cross-project pattern sharing UI** — GlobalPattern table is backend-only, no UI designed yet
- **Branch refresh/live sync** — requires GitHub webhooks, separate feature
- **Project deletion/rename** — admin action, not in current ADR scope
- **`project_id` on `OptimizationDetail`** — requires backend serializer change, deferred to project switcher
- **Server-side history filtering by `project_id`** — backend endpoint change, deferred to project switcher
