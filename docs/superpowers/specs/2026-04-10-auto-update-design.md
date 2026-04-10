# Auto-Update Feature — Design Spec

**Date**: 2026-04-10
**Status**: Reviewed (v2 — addresses all blocker/warning findings from independent review)
**Scope**: Backend service, REST endpoints, frontend UI, init.sh integration

## Problem

Users who cloned the repo and completed the install steps have no way to know a new version is available. They must manually check GitHub, pull changes, and restart. This friction means most users run stale versions indefinitely.

## Goal

A lightweight, frictionless auto-update system that detects new releases on startup, notifies the user with a persistent badge, and lets them update with one click — including service restart and post-update validation.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Detection strategy | 3-tier: git tags → raw version.json → GitHub Releases API | Git tags are fastest and always available for cloned repos. Raw fetch is the fallback. Releases API enriches with changelog when GitHub auth exists. |
| Check frequency | Startup only | No background polling. Lightweight, no timer management. |
| Update mechanism | `git fetch --tags && git checkout refs/tags/<tag>` | Pins to exact release. No merge conflicts. `refs/tags/` prefix prevents argument injection. |
| Update execution | Two-phase: trigger + resume-on-restart | Backend cannot survive `init.sh restart` (it kills its own PID). Phase 1 does git+deps in-process, writes marker file, spawns detached restart. Phase 2 runs validation on the new backend instance. |
| Post-update validation | Full suite: health version + git tag match + Alembic head | 3-check validation confirms update integrity. Runs on the NEW backend instance after restart. |
| Changelog display | Show when GitHub auth exists, version-only otherwise | Tier 3 enrichment — additive, never required. |
| Detached HEAD warning | Collapsible, dismissable ("don't show again" via localStorage) | Important for users with local commits, harmless noise for everyone else. |
| Tag validation | Strict regex + existence check | Prevents shell injection. Tag must match `^v\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$` AND exist in `git tag -l`. |
| Repo identity | `UPSTREAM_REPO` constant in config.py | Hardcoded `"project-synthesis/ProjectSynthesis"`. Avoids git dependency for Tier 2. |

## Architecture

### Detection Flow (startup)

```
init.sh start
  → backend lifespan startup
    → UpdateService.check_for_updates() [background task, try/except at top level]
      → Tier 1: git fetch --tags, parse latest semver tag
        → success? compare with version.json
        → fail? Tier 2: HTTP GET raw.githubusercontent.com/{UPSTREAM_REPO}/main/version.json
          → fail? give up, no update info
      → Tier 3 (enrichment): if GitHub token exists in DB
        → github_client.get_release_by_tag(token, UPSTREAM_REPO, tag)
        → extract release body as changelog
    → cache result in UpdateService._state
    → if pending update marker exists (data/.update_pending):
        → run validation suite, publish "update_complete" SSE
        → delete marker
    → if newer version found:
        → publish "update_available" SSE event
```

### Notification Flow

```
SSE: update_available {current, latest, tag, changelog}
  → updateStore receives event (via central /api/events EventSource)
  → StatusBar shows badge: "↑ v0.4.0" (green border, persistent)
  → Toast fires once: "Update available: v0.4.0"
```

### Update Flow (Two-Phase)

```
User clicks badge → dialog opens
  → Shows: version transition, changelog, detached HEAD warning
  → User clicks "Update & Restart"
    → POST /api/update/apply {tag: "v0.4.0"}
    → Backend Phase 1 (in-process, before restart):
      1. Validate tag: regex + git tag -l existence check
      2. Check git status --porcelain (reject if dirty)
      3. Capture OLD_HEAD=$(git rev-parse HEAD)
      4. git fetch --tags --prune-tags
      5. git checkout refs/tags/v0.4.0
      6. If backend/requirements.txt changed (git diff $OLD_HEAD): pip install
      7. If frontend/package-lock.json changed (git diff $OLD_HEAD): npm ci
      8. Run alembic upgrade head (in backend venv)
      9. Write marker: data/.update_pending {tag, old_head, timestamp}
      10. Return 202 Accepted {status: "restarting", tag: "v0.4.0"}
      11. Spawn detached: setsid ./init.sh restart &
    → Frontend enters "restarting" state:
      - Suppresses "Cannot connect to backend" error banner
      - Shows "Restarting services..." in badge area
      - Polls GET /api/health every 2s (tight loop, max 120s)
    → Backend Phase 2 (new instance, on startup):
      - Reads data/.update_pending marker
      - Runs validation: health version + git tag + alembic current
      - Publishes "update_complete" SSE {success, checks: [...]}
      - Deletes marker
    → Frontend receives update_complete via reconnected EventSource:
      - Green toast "Updated to v0.4.0" or amber warning with details
      - Badge disappears
```

## Backend

### Config Constants (`backend/app/config.py`)

```python
UPSTREAM_REPO = "project-synthesis/ProjectSynthesis"
UPDATE_TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
```

### UpdateService (`backend/app/services/update_service.py`)

New service. Responsibilities:
- `check_for_updates()` — 3-tier version detection, returns `UpdateStatus`
- `apply_update(tag: str)` — Phase 1: git checkout + deps + marker + detached restart
- `_resume_pending_update()` — Phase 2: called on startup, validates + publishes result
- `validate_update(expected_tag: str)` — runs 3-check validation suite

State model:
```python
@dataclass
class UpdateStatus:
    current_version: str          # from version.json
    latest_version: str | None    # from git tags or remote
    latest_tag: str | None        # e.g., "v0.4.0"
    update_available: bool
    changelog: str | None         # release body (Tier 3)
    changelog_entries: list[dict] | None  # parsed Added/Changed/Fixed
    checked_at: datetime
    detection_tier: str           # "git_tags" | "raw_fetch" | "none"
```

**Version comparison**: Add `packaging` to `backend/requirements.txt` as an explicit dependency. Use `packaging.version.Version` for proper semver ordering. Tags with `-dev`, `-rc` suffixes are excluded from "latest" unless the user is already on a pre-release.

**Tag validation** (security-critical):
```python
def _validate_tag(tag: str) -> None:
    if not UPDATE_TAG_PATTERN.match(tag):
        raise ValueError(f"Invalid tag format: {tag}")
    # Verify tag exists in local tag list
    result = subprocess.run(
        ["git", "tag", "-l", tag], capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    if tag not in result.stdout.strip().split("\n"):
        raise ValueError(f"Tag {tag} does not exist")
```

**Git operations** (all use `subprocess.run()` with list args, never `shell=True`):
- `["git", "fetch", "--tags", "--prune-tags"]` — sync remote tags
- `["git", "tag", "--sort=-v:refname"]` — list tags in descending semver order
- `["git", "checkout", f"refs/tags/{tag}"]` — switch to release tag (`refs/tags/` prefix prevents argument injection)
- `["git", "describe", "--tags", "--exact-match", "HEAD"]` — post-update verification
- `["git", "rev-parse", "HEAD"]` — capture old HEAD hash before checkout
- `["git", "diff", old_head, "--", "backend/requirements.txt"]` — deterministic dep check (not `HEAD@{1}`)

**Remote version.json fetch** (Tier 2 fallback):
- `GET https://raw.githubusercontent.com/{UPSTREAM_REPO}/main/version.json`
- No auth required for public repos. Timeout: 5s.
- Uses `httpx.AsyncClient` (already a project dependency).

**GitHub Releases API** (Tier 3 enrichment):
- New method: `github_client.get_release_by_tag(token, full_name, tag)` added to `github_client.py`
- Requires GitHub token from Device Flow OAuth (obtained via `github_service.decrypt_token()`)
- Graceful degradation: if no token or API fails, changelog is `None`

**Marker file** (`data/.update_pending`):
```json
{"tag": "v0.4.0", "old_head": "94bedc7...", "timestamp": "2026-04-10T02:00:00Z"}
```
Written after successful git checkout + deps, before spawning restart. Read by new backend instance on startup. Deleted after validation completes.

### Update Router (`backend/app/routers/update.py`)

Two endpoints, both with rate limiting:

**`GET /api/update/status`** — returns cached `UpdateStatus` as Pydantic `UpdateStatusResponse`. Rate limit: `10/minute` (matches project default via `settings.DEFAULT_RATE_LIMIT`).

Response model (`UpdateStatusResponse`):
```json
{
  "current_version": "0.3.20-dev",
  "latest_version": "0.4.0",
  "latest_tag": "v0.4.0",
  "update_available": true,
  "changelog": "## What's New\n- Added batch seeding...",
  "changelog_entries": [
    {"category": "Added", "text": "Batch seeding with 5 agent types"},
    {"category": "Fixed", "text": "Duplicate RepoIndexMeta crash"}
  ],
  "checked_at": "2026-04-10T01:35:00Z",
  "detection_tier": "git_tags"
}
```

**`POST /api/update/apply`** — triggers Phase 1. Rate limit: `1/minute`. Returns 202 Accepted (NOT a streaming endpoint — the backend is about to die).

Request: `{"tag": "v0.4.0"}`

Response (202):
```json
{
  "status": "restarting",
  "tag": "v0.4.0",
  "message": "Update applied. Services restarting..."
}
```

Error responses:
- 400: invalid tag format, tag doesn't exist, dirty working tree, uncommitted changes
- 409: update already in progress (mutex)
- 500: git operation failed

**Mutex**: A simple `asyncio.Lock` prevents concurrent update execution.

### Startup Integration (`backend/app/main.py`)

Router registration (following existing `try/except ImportError` pattern):
```python
try:
    from app.routers.update import router as update_router
    app.include_router(update_router)
except ImportError:
    pass
```

In the lifespan function, after routing initialization:
```python
update_svc = UpdateService(project_root=PROJECT_ROOT)
app.state.update_service = update_svc
asyncio.create_task(update_svc.check_for_updates())
# check_for_updates() internally calls _resume_pending_update() first
```

The background task has top-level `try/except Exception` with `logger.warning()` — never silently swallowed.

## Frontend

### Update Store (`frontend/src/lib/stores/update.svelte.ts`)

New reactive store (Svelte 5 runes, class instance pattern):
```typescript
class UpdateStore {
  updateAvailable = $state(false);
  currentVersion = $state<string | null>(null);
  latestVersion = $state<string | null>(null);
  latestTag = $state<string | null>(null);
  changelog = $state<string | null>(null);
  changelogEntries = $state<ChangelogEntry[] | null>(null);
  detectionTier = $state<string | null>(null);

  // Dialog state
  dialogOpen = $state(false);

  // Update progress
  updating = $state(false);
  updateStep = $state<string | null>(null);
  updateComplete = $state(false);
  updateSuccess = $state<boolean | null>(null);
  validationChecks = $state<ValidationCheck[]>([]);

  // Dismissable warning
  hideDetachedWarning = $state(false); // loaded from localStorage
}
```

Initialized on page load via `GET /api/update/status`. Also listens for `update_available` and `update_complete` SSE events via the central `/api/events` EventSource.

### UpdateBadge Component (`frontend/src/lib/components/shared/UpdateBadge.svelte`)

Renders in StatusBar (right side, as a new element — StatusBar does NOT currently show version).

**Badge** (when `updateAvailable && !updating`):
- Green-bordered pill: `↑ v0.4.0`
- Tooltip: "Update available — click to see details"
- `onclick` → opens dialog

**Restarting** (when `updating`):
- Amber text: `↻ Restarting...`
- Suppresses the "Cannot connect to backend" error banner from `+page.svelte`

**Dialog** (popover, anchored to badge):
- Header: "Update Available" + version transition (`v0.3.20-dev → v0.4.0`)
- Changelog section (scrollable, max-height 160px) — only shown when `changelogEntries` is non-null
- Detached HEAD warning (collapsible, shown unless dismissed):
  - **Headline**: "This will detach from your current branch"
  - **Body**: "If you've made local commits or customizations, they won't be lost but will no longer be on an active branch. You can recover them later with `git checkout main && git merge <previous-hash>`."
  - **Who this affects**: "This matters if you've committed changes to strategies, prompts, or code. If you only use the app as-is (no git commits), you can safely dismiss this warning."
  - **Checkbox**: "Don't show this warning again" → `localStorage: synthesis:dismiss_detached_head_warning`
- "Update & Restart" button (green border)
- "Later" button (gray border, closes dialog)
- Footer: "Your data (database, preferences, embeddings) is preserved."

### Frontend Reconnection Protocol

After clicking "Update & Restart":
1. `POST /api/update/apply` returns 202 → `updateStore.updating = true`
2. Frontend enters "restarting" state:
   - Badge shows `↻ Restarting...`
   - `+page.svelte` checks `updateStore.updating` and suppresses the `backendError` banner
3. Health poll tightens to 2-second interval (overrides normal 60s)
4. When `GET /api/health` succeeds AND returns the new version → stop tight polling
5. EventSource reconnects → receives `update_complete` event with validation results
6. On success: green toast "Updated to v0.4.0", badge disappears
7. On partial failure: amber toast with details, link to run `./init.sh restart` manually
8. If health polling fails for >120s: red toast "Update may have failed. Try `./init.sh restart` in the terminal."

### SSE Event Registration

Add `update_available` and `update_complete` to the `eventTypes` array in `connectEventStream()` at `frontend/src/lib/api/client.ts`.

In `+page.svelte` event handler:
```typescript
case 'update_available':
  updateStore.receive(event.data);
  addToast('created', `Update available: v${event.data.latest_version}`);
  break;
case 'update_complete':
  updateStore.receiveComplete(event.data);
  break;
```

## init.sh Integration

### New `update` Subcommand

```bash
./init.sh update [tag]
```

**Self-modification safety**: The `update` subcommand copies itself to a temp file and re-execs from there, so `git checkout` can overwrite `init.sh` without breaking the running script:
```bash
update)
  _tmp="$(mktemp /tmp/synthesis-update-XXXXXX.sh)"
  cp "$0" "$_tmp"
  chmod +x "$_tmp"
  exec "$_tmp" _do_update "$@"
  ;;
_do_update)
  # actual update logic here
  ;;
```

Steps (in `_do_update`):
1. If no tag provided, auto-detect latest: `git fetch --tags && git tag --sort=-v:refname | head -1`
2. Validate tag format (regex match)
3. Show current version vs target version
4. `OLD_HEAD=$(git rev-parse HEAD)`
5. `git fetch --tags --prune-tags`
6. `git checkout refs/tags/<tag>`
7. Check if `backend/requirements.txt` changed: `git diff $OLD_HEAD -- backend/requirements.txt`
   - If changed: `cd backend && source .venv/bin/activate && pip install -r requirements.txt`
8. Check if `frontend/package-lock.json` changed: `git diff $OLD_HEAD -- frontend/package-lock.json`
   - If changed: `cd frontend && npm ci`
9. Run Alembic migrations: `cd backend && source .venv/bin/activate && alembic upgrade head`
10. `./init.sh restart` (calls the NEW init.sh from the checked-out tag)
11. Validate:
    - Health endpoint returns new version
    - `git describe --tags --exact-match HEAD` matches tag
12. Print summary: pass/fail for each check
13. Clean up temp file

### Backend Spawns Detached Restart

The `POST /api/update/apply` endpoint does Phase 1 (git + deps + alembic + marker) in-process, then spawns the restart as a fully detached process:

```python
import os, subprocess
subprocess.Popen(
    [str(PROJECT_ROOT / "init.sh"), "restart"],
    start_new_session=True,  # Python-level process group detach (no setsid binary needed)
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    close_fds=True,
    cwd=str(PROJECT_ROOT),
)
```

The backend returns 202 Accepted immediately. The detached `init.sh restart` survives the backend process being killed.

## Edge Cases

**No git repo** (downloaded as zip): Tier 1 fails. Tier 2 provides version info using `UPSTREAM_REPO` constant. Update button disabled with tooltip: "Auto-update requires a git clone. Download the latest release from GitHub."

**Uncommitted changes**: `git checkout` fails on tracked file conflicts. The endpoint checks `git status --porcelain` first and returns 400: "Uncommitted changes detected. Please commit or stash your changes before updating."

**Untracked files in data/**: `data/` is in `.gitignore`. `git checkout` preserves untracked files. No conflict.

**Network offline**: All tiers fail gracefully. No badge shown. No error.

**Already on latest**: `update_available: false`. No badge, no notification.

**Pre-release versions**: User on `0.3.20-dev` sees `0.4.0` as update. User on `0.4.0` does NOT see `0.5.0-dev`.

**Mid-update crash** (between checkout and restart): Repo is on new tag, services are down. Marker file exists. User runs `./init.sh restart` manually. New backend reads marker, runs validation, publishes result.

**Alembic migration fails**: Caught during Phase 1 (before restart). The endpoint automatically rolls back: `git checkout $OLD_HEAD` to restore the previous code, then returns 500 with details: "Migration failed: {error}. Code rolled back to previous version. Database may need manual repair — run `cd backend && alembic upgrade head` after resolving the issue."

**Concurrent update requests**: `asyncio.Lock` mutex rejects with 409 Conflict.

**init.sh self-modification**: Handled by copy-to-temp-and-exec pattern.

**Pipeline running during update**: The endpoint does NOT check for running pipelines. `git checkout` only changes files on disk — loaded Python modules continue running until restart. The restart phase (Phase 1 step 11) will gracefully drain SSE connections via Uvicorn's shutdown sequence. This is acceptable — a mid-pipeline optimization may fail, but the next one after restart will succeed.

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/services/update_service.py` | Create | Version check + update execution + validation |
| `backend/app/routers/update.py` | Create | `/api/update/status`, `/api/update/apply` |
| `backend/app/main.py` | Modify | Register router (try/except pattern), startup check + resume |
| `backend/app/services/github_client.py` | Modify | Add `get_release_by_tag()` method |
| `backend/app/config.py` | Modify | Add `UPSTREAM_REPO`, `UPDATE_TAG_PATTERN` |
| `backend/requirements.txt` | Modify | Add `packaging` |
| `frontend/src/lib/stores/update.svelte.ts` | Create | Update state + SSE listener |
| `frontend/src/lib/components/shared/UpdateBadge.svelte` | Create | Badge + dialog + progress |
| `frontend/src/lib/components/layout/StatusBar.svelte` | Modify | Add UpdateBadge |
| `frontend/src/routes/app/+page.svelte` | Modify | SSE handler for update_available/update_complete, suppress error during restart |
| `frontend/src/lib/api/client.ts` | Modify | Add `getUpdateStatus()`, `applyUpdate()`, add event types to `connectEventStream()` |
| `init.sh` | Modify | Add `update` + `_do_update` subcommands |
| `CLAUDE.md` | Modify | Add `update_available`, `update_complete` to event bus types |
| `backend/CLAUDE.md` | Modify | Document new router and endpoints |
| `docs/CHANGELOG.md` | Modify | Add entry under Unreleased |

## Testing

**Backend unit tests** (`tests/test_update_service.py`):
- Version comparison: `0.3.20-dev` < `0.4.0`, `0.4.0` == `0.4.0`, pre-release filtering
- Tag validation: rejects `v1.0; rm -rf /`, `--help`, empty string, accepts `v0.4.0`, `v1.0.0-rc.1`
- Tier fallback: mock git failure → Tier 2 fetch → success
- Tier 3 enrichment: mock GitHub release → changelog parsed
- Changelog parsing: release body → categorized entries
- Dirty working tree detection: mock `git status` returns porcelain output
- Concurrent update rejection: second call while first is in progress → 409
- Marker file lifecycle: write, read, delete
- Subprocess timeout handling: mock slow git → timeout error

**Frontend unit tests** (`UpdateBadge.test.ts`):
- Badge renders when update available
- Badge hidden when no update
- Dialog opens on click
- "Don't show again" checkbox persists to localStorage and hides warning
- Restarting state suppresses error banner
- Progress states render correctly

**init.sh tests** (manual verification):
- `./init.sh update v0.3.0` — checkout older tag, verify services restart
- `./init.sh update` (no arg) — auto-detect latest tag
- `./init.sh update invalid-tag` — rejected with error message

**E2E verification**:
1. Start services → `GET /api/update/status` returns current state
2. Create a tag ahead of current version → restart → verify badge appears
3. Click update → verify checkout + restart + validation → badge disappears
4. Verify `data/synthesis.db` preserved across update
5. Verify EventSource reconnects and receives `update_complete`
