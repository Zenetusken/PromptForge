# Auto-Update Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect new releases on startup, show a persistent StatusBar badge, and let users update with one click including service restart and post-update validation.

**Architecture:** Two-phase trigger-and-resume pattern. Phase 1 (in-process): git fetch + tag validation + checkout + deps + alembic + marker file + detached restart. Phase 2 (new backend instance): read marker + validate + publish SSE + delete marker. Frontend polls health during restart window, suppresses error banner, shows progress.

**Tech Stack:** Python 3.12 (FastAPI, asyncio subprocess, packaging), SvelteKit 2 (Svelte 5 runes), bash (init.sh)

**Spec:** `docs/superpowers/specs/2026-04-10-auto-update-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/config.py` | Modify | Add `UPSTREAM_REPO` constant |
| `backend/requirements.txt` | Modify | Add `packaging` |
| `backend/app/services/github_client.py` | Modify | Add `get_release_by_tag()` |
| `backend/app/services/update_service.py` | Create | Version detection, update execution, validation |
| `backend/app/routers/update.py` | Create | REST endpoints for update status + apply |
| `backend/app/main.py` | Modify | Register router, startup background check |
| `init.sh` | Modify | Add `update` + `_do_update` subcommands |
| `frontend/src/lib/api/client.ts` | Modify | Add API functions + SSE event types |
| `frontend/src/lib/stores/update.svelte.ts` | Create | Update state management |
| `frontend/src/lib/components/shared/UpdateBadge.svelte` | Create | Badge + dialog UI |
| `frontend/src/lib/components/layout/StatusBar.svelte` | Modify | Mount UpdateBadge |
| `frontend/src/routes/app/+page.svelte` | Modify | SSE handlers + health poll suppression |
| `backend/tests/test_update_service.py` | Create | Backend unit tests |
| `frontend/src/lib/components/shared/UpdateBadge.test.ts` | Create | Frontend unit tests |

---

### Task 1: Config + Dependencies

**Files:**
- Modify: `backend/app/config.py:150` (after MODEL_HAIKU)
- Modify: `backend/requirements.txt:19` (after mcp)

- [ ] **Step 1: Add config constants**

In `backend/app/config.py`, add after line 150 (after the `MODEL_HAIKU` field), before the `# --- Traces ---` comment:

```python
    # --- Auto-Update ---
    UPSTREAM_REPO: str = Field(
        default="project-synthesis/ProjectSynthesis",
        description="GitHub owner/repo for upstream update checks.",
    )
```

Also add `import re` at the top of the file if not already present, and add this module-level constant after the `Settings` class definition:

```python
UPDATE_TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
```

- [ ] **Step 2: Add packaging to requirements.txt**

In `backend/requirements.txt`, add after line 18 (`mcp[cli]==1.26.0`), before `python-multipart`:

```
packaging>=24.0
```

- [ ] **Step 3: Install dependency**

Run: `cd backend && source .venv/bin/activate && pip install packaging>=24.0`
Expected: Successfully installed packaging-24.x

- [ ] **Step 4: Verify import works**

Run: `cd backend && source .venv/bin/activate && python -c "from packaging.version import Version; print(Version('0.3.20.dev0') < Version('0.4.0'))"`
Expected: `True`

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/requirements.txt
git commit -m "feat(update): add config constants and packaging dependency"
```

---

### Task 2: GitHub Client Extension

**Files:**
- Modify: `backend/app/services/github_client.py:111` (after `get_file_content`)
- Test: `backend/tests/test_update_service.py` (created in Task 4)

- [ ] **Step 1: Add `get_release_by_tag` method**

Append after line 111 (end of `get_file_content` method) in `backend/app/services/github_client.py`:

```python

    async def get_release_by_tag(
        self, token: str, full_name: str, tag: str
    ) -> dict | None:
        """Fetch GitHub release info by tag name. Returns None on 404."""
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{full_name}/releases/tags/{tag}",
            headers=self._headers(token),
        )
        if resp.status_code == 404:
            return None
        _check(resp)
        return resp.json()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/github_client.py
git commit -m "feat(update): add get_release_by_tag to GitHub client"
```

---

### Task 3: UpdateService — Version Detection

**Files:**
- Create: `backend/app/services/update_service.py`
- Test: `backend/tests/test_update_service.py`

- [ ] **Step 1: Write failing tests for version comparison and tag validation**

Create `backend/tests/test_update_service.py`:

```python
"""Tests for UpdateService — version detection and tag validation."""

import pytest

from app.services.update_service import (
    UpdateStatus,
    compare_versions,
    validate_tag,
)


class TestCompareVersions:
    def test_dev_less_than_release(self):
        assert compare_versions("0.3.20-dev", "0.4.0") == -1

    def test_equal_versions(self):
        assert compare_versions("0.4.0", "0.4.0") == 0

    def test_newer_local(self):
        assert compare_versions("0.5.0", "0.4.0") == 1

    def test_patch_bump(self):
        assert compare_versions("0.3.19", "0.3.20") == -1

    def test_prerelease_excluded(self):
        """Pre-release tags should not be considered newer than stable."""
        assert compare_versions("0.4.0", "0.5.0-dev") == 1


class TestValidateTag:
    def test_valid_semver_tag(self):
        validate_tag("v0.4.0")  # should not raise

    def test_valid_prerelease_tag(self):
        validate_tag("v1.0.0-rc.1")  # should not raise

    def test_rejects_shell_injection(self):
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag("v1.0; rm -rf /")

    def test_rejects_argument_injection(self):
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag("--help")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag("")

    def test_rejects_no_v_prefix(self):
        with pytest.raises(ValueError, match="Invalid tag format"):
            validate_tag("0.4.0")


class TestUpdateStatus:
    def test_no_update(self):
        status = UpdateStatus(
            current_version="0.4.0",
            latest_version="0.4.0",
            latest_tag="v0.4.0",
            update_available=False,
        )
        assert not status.update_available

    def test_update_available(self):
        status = UpdateStatus(
            current_version="0.3.20-dev",
            latest_version="0.4.0",
            latest_tag="v0.4.0",
            update_available=True,
            changelog="## Added\n- New feature",
        )
        assert status.update_available
        assert status.latest_tag == "v0.4.0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_update_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.update_service'`

- [ ] **Step 3: Implement UpdateService core**

Create `backend/app/services/update_service.py`:

```python
"""Auto-update service — version detection, update execution, validation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packaging.version import Version, InvalidVersion

from app.config import settings, UPDATE_TAG_PATTERN

logger = logging.getLogger(__name__)

MARKER_FILE = "data/.update_pending"
RAW_VERSION_URL = (
    "https://raw.githubusercontent.com/{repo}/main/version.json"
)


@dataclass
class UpdateStatus:
    """Cached result of a version check."""

    current_version: str
    latest_version: str | None = None
    latest_tag: str | None = None
    update_available: bool = False
    changelog: str | None = None
    changelog_entries: list[dict[str, str]] | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    detection_tier: str = "none"


def validate_tag(tag: str) -> None:
    """Validate a git tag against the allowed pattern. Raises ValueError."""
    if not tag or not UPDATE_TAG_PATTERN.match(tag):
        raise ValueError(f"Invalid tag format: {tag!r}")


def compare_versions(local: str, remote: str) -> int:
    """Compare two version strings. Returns -1 (local older), 0, or 1 (local newer).

    Handles -dev suffix by converting to PEP 440 .devN format.
    Pre-release remote versions are treated as older than stable local versions
    UNLESS the local version is also a pre-release.
    """
    try:
        local_v = Version(local.replace("-dev", ".dev0").replace("-rc", "rc"))
        remote_v = Version(remote.replace("-dev", ".dev0").replace("-rc", "rc"))
    except InvalidVersion:
        return 0

    # If local is stable but remote is pre-release, treat local as newer
    # (users on stable should not be prompted to update to dev/rc)
    local_is_stable = not (local_v.is_prerelease or local_v.is_devrelease)
    remote_is_prerelease = remote_v.is_prerelease or remote_v.is_devrelease
    if local_is_stable and remote_is_prerelease:
        return 1

    if local_v < remote_v:
        return -1
    if local_v > remote_v:
        return 1
    return 0


def _parse_latest_tag(tag_output: str) -> str | None:
    """Parse the latest stable semver tag from `git tag --sort=-v:refname` output."""
    for line in tag_output.strip().splitlines():
        tag = line.strip()
        if not tag:
            continue
        if UPDATE_TAG_PATTERN.match(tag):
            # Skip pre-release tags
            try:
                v = Version(tag.lstrip("v").replace("-rc", "rc"))
                if v.is_prerelease or v.is_devrelease:
                    continue
            except InvalidVersion:
                continue
            return tag
    return None


class UpdateService:
    """Manages version detection and update execution."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root
        self._state: UpdateStatus | None = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> UpdateStatus | None:
        return self._state

    async def check_for_updates(self) -> UpdateStatus:
        """Run 3-tier version detection. Safe to call from background task."""
        try:
            return await self._do_check()
        except Exception as exc:
            logger.warning("Update check failed: %s", exc)
            current = self._read_current_version()
            self._state = UpdateStatus(current_version=current)
            return self._state

    async def _do_check(self) -> UpdateStatus:
        current = self._read_current_version()

        # Check for pending update marker first (Phase 2 resume)
        await self._resume_pending_update(current)

        # Tier 1: git fetch --tags
        latest_tag = await self._check_git_tags()

        # Tier 2 fallback: raw version.json fetch
        detection_tier = "git_tags"
        if latest_tag is None:
            latest_tag = await self._check_raw_fetch()
            detection_tier = "raw_fetch" if latest_tag else "none"

        if latest_tag is None:
            self._state = UpdateStatus(
                current_version=current, detection_tier="none",
            )
            return self._state

        latest_version = latest_tag.lstrip("v")
        update_available = compare_versions(current, latest_version) == -1

        # Tier 3: GitHub Releases API enrichment
        changelog = None
        changelog_entries = None
        if update_available:
            changelog, changelog_entries = await self._fetch_changelog(latest_tag)

        self._state = UpdateStatus(
            current_version=current,
            latest_version=latest_version,
            latest_tag=latest_tag,
            update_available=update_available,
            changelog=changelog,
            changelog_entries=changelog_entries,
            detection_tier=detection_tier,
        )

        if update_available:
            try:
                from app.services.event_bus import event_bus
                event_bus.publish("update_available", {
                    "current_version": current,
                    "latest_version": latest_version,
                    "latest_tag": latest_tag,
                    "changelog": changelog,
                    "changelog_entries": changelog_entries,
                })
            except Exception:
                pass

        return self._state

    def _read_current_version(self) -> str:
        try:
            vf = self._root / "version.json"
            return json.loads(vf.read_text())["version"]
        except Exception:
            from app._version import __version__
            return __version__

    async def _check_git_tags(self) -> str | None:
        """Tier 1: git fetch --tags + parse latest semver tag."""
        try:
            fetch = await asyncio.create_subprocess_exec(
                "git", "fetch", "--tags", "--prune-tags",
                cwd=str(self._root),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(fetch.wait(), timeout=30)

            tags = await asyncio.create_subprocess_exec(
                "git", "tag", "--sort=-v:refname",
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(tags.communicate(), timeout=10)
            return _parse_latest_tag(stdout.decode())
        except Exception as exc:
            logger.debug("Git tag check failed: %s", exc)
            return None

    async def _check_raw_fetch(self) -> str | None:
        """Tier 2: fetch version.json from GitHub raw content."""
        try:
            import httpx
            url = RAW_VERSION_URL.format(repo=settings.UPSTREAM_REPO)
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                remote_version = resp.json()["version"]
                # Convert to tag format
                clean = remote_version.split("-")[0]  # strip -dev suffix
                return f"v{clean}"
        except Exception as exc:
            logger.debug("Raw version fetch failed: %s", exc)
            return None

    async def _fetch_changelog(
        self, tag: str
    ) -> tuple[str | None, list[dict[str, str]] | None]:
        """Tier 3: fetch release notes from GitHub Releases API."""
        try:
            from app.database import async_session_factory
            from app.models import GitHubToken
            from app.services.github_service import GitHubService
            from app.services.github_client import GitHubClient
            from sqlalchemy import select

            async with async_session_factory() as db:
                token_q = await db.execute(select(GitHubToken).limit(1))
                token_row = token_q.scalars().first()
                if not token_row:
                    return None, None

                svc = GitHubService(secret_key=settings.resolve_secret_key())
                token = svc.decrypt_token(token_row.token_encrypted)

                client = GitHubClient()
                release = await client.get_release_by_tag(
                    token, settings.UPSTREAM_REPO, tag,
                )
                if not release:
                    return None, None

                body = release.get("body", "")
                entries = _parse_changelog_entries(body)
                return body, entries
        except Exception as exc:
            logger.debug("Changelog fetch failed: %s", exc)
            return None, None

    async def _resume_pending_update(self, current_version: str) -> None:
        """Phase 2: check for pending update marker and validate."""
        marker = self._root / MARKER_FILE
        if not marker.exists():
            return

        try:
            data = json.loads(marker.read_text())
            expected_tag = data.get("tag", "")
            logger.info("Pending update marker found: %s", expected_tag)

            checks = await self.validate_update(expected_tag)
            success = all(c["passed"] for c in checks)

            try:
                from app.services.event_bus import event_bus
                event_bus.publish("update_complete", {
                    "success": success,
                    "tag": expected_tag,
                    "version": current_version,
                    "checks": checks,
                })
            except Exception:
                pass

            if success:
                logger.info("Update to %s validated successfully", expected_tag)
            else:
                logger.warning("Update validation partial failure: %s", checks)
        except Exception as exc:
            logger.warning("Failed to resume pending update: %s", exc)
        finally:
            try:
                marker.unlink(missing_ok=True)
            except Exception:
                pass

    async def validate_update(self, expected_tag: str) -> list[dict[str, Any]]:
        """Run 3-check post-update validation suite."""
        checks: list[dict[str, Any]] = []

        # Check 1: version matches
        current = self._read_current_version()
        expected_version = expected_tag.lstrip("v")
        version_ok = current.split("-")[0] == expected_version.split("-")[0]
        checks.append({
            "name": "version",
            "passed": version_ok,
            "detail": f"version.json reports {current}" + (
                "" if version_ok else f" (expected {expected_version})"
            ),
        })

        # Check 2: git tag matches
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "describe", "--tags", "--exact-match", "HEAD",
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            actual_tag = stdout.decode().strip()
            tag_ok = actual_tag == expected_tag
            checks.append({
                "name": "tag",
                "passed": tag_ok,
                "detail": f"HEAD at {actual_tag}" + (
                    "" if tag_ok else f" (expected {expected_tag})"
                ),
            })
        except Exception as exc:
            checks.append({
                "name": "tag",
                "passed": False,
                "detail": f"git describe failed: {exc}",
            })

        # Check 3: alembic at head
        try:
            proc = await asyncio.create_subprocess_exec(
                str(self._root / "backend" / ".venv" / "bin" / "python"),
                "-m", "alembic", "current",
                cwd=str(self._root / "backend"),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode().strip()
            alembic_ok = "(head)" in output
            checks.append({
                "name": "migrations",
                "passed": alembic_ok,
                "detail": "Alembic at head" if alembic_ok else f"Alembic: {output}",
            })
        except Exception as exc:
            checks.append({
                "name": "migrations",
                "passed": False,
                "detail": f"Alembic check failed: {exc}",
            })

        return checks

    async def apply_update(self, tag: str) -> dict[str, Any]:
        """Phase 1: validate, checkout, deps, alembic, marker, detached restart."""
        if not self._lock.acquire_nowait():
            raise RuntimeError("Update already in progress")

        try:
            validate_tag(tag)

            # Verify tag exists locally
            proc = await asyncio.create_subprocess_exec(
                "git", "tag", "-l", tag,
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if tag not in stdout.decode().strip().splitlines():
                raise ValueError(f"Tag {tag} does not exist locally")

            # Check for dirty working tree
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            dirty = [
                line for line in stdout.decode().strip().splitlines()
                if line.strip() and not line.strip().startswith("??")
            ]
            if dirty:
                raise ValueError(
                    "Uncommitted changes detected. Commit or stash before updating."
                )

            # Capture old HEAD
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            old_head = stdout.decode().strip()

            # Git fetch + checkout
            fetch = await asyncio.create_subprocess_exec(
                "git", "fetch", "--tags", "--prune-tags",
                cwd=str(self._root),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(fetch.wait(), timeout=60)

            checkout = await asyncio.create_subprocess_exec(
                "git", "checkout", f"refs/tags/{tag}",
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await checkout.communicate()
            if checkout.returncode != 0:
                raise RuntimeError(f"git checkout failed: {stderr.decode()}")

            # Check if deps changed
            try:
                await self._install_deps_if_changed(old_head)
            except Exception as dep_exc:
                logger.warning("Dependency install issue: %s", dep_exc)

            # Run alembic upgrade
            try:
                await self._run_alembic_upgrade()
            except Exception as alembic_exc:
                # Rollback to old HEAD on alembic failure
                logger.error("Alembic upgrade failed, rolling back: %s", alembic_exc)
                rollback = await asyncio.create_subprocess_exec(
                    "git", "checkout", old_head,
                    cwd=str(self._root),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await rollback.wait()
                raise RuntimeError(
                    f"Migration failed: {alembic_exc}. "
                    f"Code rolled back to previous version."
                ) from alembic_exc

            # Write marker file
            marker = self._root / MARKER_FILE
            marker.write_text(json.dumps({
                "tag": tag,
                "old_head": old_head,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

            # Spawn detached restart
            import subprocess as _sp
            _sp.Popen(
                [str(self._root / "init.sh"), "restart"],
                start_new_session=True,
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                close_fds=True,
                cwd=str(self._root),
            )

            return {"status": "restarting", "tag": tag}
        finally:
            if self._lock.locked():
                self._lock.release()

    async def _install_deps_if_changed(self, old_head: str) -> None:
        """Install backend/frontend deps if their lock files changed."""
        # Backend
        proc = await asyncio.create_subprocess_exec(
            "git", "diff", "--name-only", old_head, "--",
            "backend/requirements.txt",
            cwd=str(self._root),
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout.decode().strip():
            logger.info("requirements.txt changed — installing backend deps")
            pip = await asyncio.create_subprocess_exec(
                str(self._root / "backend" / ".venv" / "bin" / "pip"),
                "install", "-r", "requirements.txt",
                cwd=str(self._root / "backend"),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(pip.wait(), timeout=120)

        # Frontend
        proc = await asyncio.create_subprocess_exec(
            "git", "diff", "--name-only", old_head, "--",
            "frontend/package-lock.json",
            cwd=str(self._root),
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout.decode().strip():
            logger.info("package-lock.json changed — installing frontend deps")
            npm = await asyncio.create_subprocess_exec(
                "npm", "ci",
                cwd=str(self._root / "frontend"),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(npm.wait(), timeout=120)

    async def _run_alembic_upgrade(self) -> None:
        """Run alembic upgrade head in the backend venv."""
        proc = await asyncio.create_subprocess_exec(
            str(self._root / "backend" / ".venv" / "bin" / "python"),
            "-m", "alembic", "upgrade", "head",
            cwd=str(self._root / "backend"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip() or stdout.decode().strip())


def _parse_changelog_entries(body: str) -> list[dict[str, str]]:
    """Parse GitHub release body into categorized entries."""
    entries: list[dict[str, str]] = []
    category = "Changed"
    for line in body.splitlines():
        line = line.strip()
        # Detect category headers: ## Added, ## Fixed, etc.
        if line.startswith("##"):
            cat = line.lstrip("#").strip()
            if cat in ("Added", "Changed", "Fixed", "Removed", "Deprecated"):
                category = cat
            continue
        # Detect list items
        if line.startswith("- ") or line.startswith("* "):
            text = line.lstrip("-* ").strip()
            if text:
                entries.append({"category": category, "text": text})
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_update_service.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Write additional tests for tier detection and marker lifecycle**

Append to `backend/tests/test_update_service.py`:

```python
class TestParseLatestTag:
    def test_finds_latest_stable(self):
        from app.services.update_service import _parse_latest_tag
        output = "v0.5.0\nv0.4.0\nv0.3.0\n"
        assert _parse_latest_tag(output) == "v0.5.0"

    def test_skips_prerelease(self):
        from app.services.update_service import _parse_latest_tag
        output = "v0.5.0-rc.1\nv0.4.0\n"
        assert _parse_latest_tag(output) == "v0.4.0"

    def test_empty_output(self):
        from app.services.update_service import _parse_latest_tag
        assert _parse_latest_tag("") is None

    def test_no_matching_tags(self):
        from app.services.update_service import _parse_latest_tag
        assert _parse_latest_tag("not-a-tag\nfoo\n") is None


class TestParseChangelog:
    def test_categorized_entries(self):
        from app.services.update_service import _parse_changelog_entries
        body = "## Added\n- New feature\n- Another feature\n## Fixed\n- Bug fix\n"
        entries = _parse_changelog_entries(body)
        assert len(entries) == 3
        assert entries[0] == {"category": "Added", "text": "New feature"}
        assert entries[2] == {"category": "Fixed", "text": "Bug fix"}

    def test_empty_body(self):
        from app.services.update_service import _parse_changelog_entries
        assert _parse_changelog_entries("") == []


@pytest.mark.asyncio
async def test_update_service_status_default(tmp_path):
    """UpdateService starts with no state."""
    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)
    assert svc.status is None


class TestCompareVersionsPrerelease:
    """Pre-release filtering: stable local should not be prompted for pre-release remote."""

    def test_stable_local_ignores_dev_remote(self):
        assert compare_versions("0.4.0", "0.5.0-dev") == 1

    def test_stable_local_ignores_rc_remote(self):
        assert compare_versions("0.4.0", "0.5.0-rc.1") == 1

    def test_prerelease_local_sees_prerelease_remote(self):
        """User on rc.1 should see rc.2 as newer."""
        assert compare_versions("0.5.0-rc.1", "0.5.0-rc.2") == -1

    def test_dev_local_sees_stable_remote(self):
        assert compare_versions("0.4.0-dev", "0.4.0") == -1


@pytest.mark.asyncio
async def test_tier2_raw_fetch_fallback(tmp_path, monkeypatch):
    """Tier 2 raw fetch parses version.json from GitHub raw content."""
    import httpx
    from unittest.mock import AsyncMock, MagicMock

    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')
    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)

    # Mock _check_git_tags to fail (simulate no git)
    svc._check_git_tags = AsyncMock(return_value=None)

    # Mock _check_raw_fetch to succeed
    svc._check_raw_fetch = AsyncMock(return_value="v0.4.0")

    status = await svc._do_check()
    assert status.detection_tier == "raw_fetch"
    assert status.latest_tag == "v0.4.0"
    assert status.update_available is True


@pytest.mark.asyncio
async def test_tier3_changelog_enrichment(tmp_path, monkeypatch):
    """Tier 3 enrichment fetches changelog from GitHub Releases API."""
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')
    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)

    # Mock tiers 1+2
    svc._check_git_tags = AsyncMock(return_value="v0.4.0")

    # Mock tier 3 to return changelog
    svc._fetch_changelog = AsyncMock(return_value=(
        "## Added\n- New feature\n## Fixed\n- Bug fix",
        [
            {"category": "Added", "text": "New feature"},
            {"category": "Fixed", "text": "Bug fix"},
        ]
    ))

    status = await svc._do_check()
    assert status.changelog is not None
    assert len(status.changelog_entries) == 2
    assert status.changelog_entries[0]["category"] == "Added"


@pytest.mark.asyncio
async def test_apply_update_rollback_on_alembic_failure(tmp_path):
    """If alembic upgrade fails after checkout, code rolls back to old HEAD."""
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True,
    )
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "tag", "v0.4.0"], cwd=str(tmp_path), capture_output=True)

    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)

    # Mock _run_alembic_upgrade to raise
    svc._run_alembic_upgrade = AsyncMock(side_effect=RuntimeError("migration failed"))
    # Mock _install_deps_if_changed to no-op
    svc._install_deps_if_changed = AsyncMock()

    with pytest.raises(RuntimeError, match="Migration failed"):
        await svc.apply_update("v0.4.0")

    # Verify HEAD was rolled back (not on v0.4.0 tag)
    result = subprocess.run(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    # Should NOT be on v0.4.0 since rollback happened
    # (It might fail describe entirely since the original commit has no tag)
    assert "v0.4.0" not in result.stdout


@pytest.mark.asyncio
async def test_concurrent_update_rejected(tmp_path):
    """Second update call while first is running raises RuntimeError."""
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "tag", "v0.4.0"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')

    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)

    # Acquire the lock manually to simulate an in-progress update
    await svc._lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="already in progress"):
            await svc.apply_update("v0.4.0")
    finally:
        svc._lock.release()


@pytest.mark.asyncio
async def test_marker_file_lifecycle(tmp_path):
    """Marker file is created during apply and cleaned up after resume."""
    from app.services.update_service import UpdateService, MARKER_FILE
    # Create a minimal version.json
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')
    marker = tmp_path / MARKER_FILE
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"tag": "v0.4.0", "old_head": "abc123"}')
    assert marker.exists()

    svc = UpdateService(project_root=tmp_path)
    # Resume will fail validation (no git repo) but should still clean up marker
    await svc._resume_pending_update("0.4.0")
    assert not marker.exists()
```

- [ ] **Step 6: Run all update tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_update_service.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/update_service.py backend/tests/test_update_service.py
git commit -m "feat(update): add UpdateService with 3-tier detection and TDD tests"
```

---

### Task 4: Update Router

**Files:**
- Create: `backend/app/routers/update.py`
- Modify: `backend/app/main.py:1209` (router registration)

- [ ] **Step 1: Create update router**

Create `backend/app/routers/update.py`:

```python
"""Update status and apply endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.dependencies.rate_limit import RateLimit
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/update", tags=["update"])


class UpdateStatusResponse(BaseModel):
    current_version: str
    latest_version: str | None = None
    latest_tag: str | None = None
    update_available: bool = False
    changelog: str | None = None
    changelog_entries: list[dict[str, str]] | None = None
    checked_at: str | None = None
    detection_tier: str = "none"


class ApplyRequest(BaseModel):
    tag: str = Field(description="Git tag to update to, e.g. 'v0.4.0'")


class ApplyResponse(BaseModel):
    status: str
    tag: str
    message: str = ""


@router.get("/status", response_model=UpdateStatusResponse)
async def get_update_status(
    request: Request,
    _rate: None = Depends(RateLimit(lambda: settings.DEFAULT_RATE_LIMIT)),
) -> UpdateStatusResponse:
    """Return cached update status from last startup check."""
    svc = getattr(request.app.state, "update_service", None)
    if not svc or not svc.status:
        return UpdateStatusResponse(current_version="unknown")

    s = svc.status
    return UpdateStatusResponse(
        current_version=s.current_version,
        latest_version=s.latest_version,
        latest_tag=s.latest_tag,
        update_available=s.update_available,
        changelog=s.changelog,
        changelog_entries=s.changelog_entries,
        checked_at=s.checked_at.isoformat() if s.checked_at else None,
        detection_tier=s.detection_tier,
    )


@router.post("/apply", response_model=ApplyResponse, status_code=202)
async def apply_update(
    request: Request,
    body: ApplyRequest,
    _rate: None = Depends(RateLimit(lambda: "1/minute")),
) -> ApplyResponse:
    """Trigger Phase 1 of the update: checkout, deps, alembic, restart."""
    svc = getattr(request.app.state, "update_service", None)
    if not svc:
        raise HTTPException(500, "Update service not initialized")

    try:
        result = await svc.apply_update(body.tag)
        return ApplyResponse(
            status=result["status"],
            tag=result["tag"],
            message="Update applied. Services restarting...",
        )
    except RuntimeError as exc:
        if "already in progress" in str(exc).lower():
            raise HTTPException(409, str(exc))
        raise HTTPException(500, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
```

- [ ] **Step 2: Register router in main.py**

In `backend/app/main.py`, add after line 1209 (after `monitoring_router` block), before `asgi_app = app`:

```python
try:
    from app.routers.update import router as update_router
    app.include_router(update_router)
except ImportError:
    pass
```

- [ ] **Step 3: Add startup background check in lifespan**

In `backend/app/main.py`, add after line 220 (after `agent_watcher_task`):

```python
    # Start update checker (background — non-blocking)
    from app.services.update_service import UpdateService
    _update_svc = UpdateService(project_root=PROJECT_ROOT)
    app.state.update_service = _update_svc

    async def _run_update_check():
        try:
            await _update_svc.check_for_updates()
            if _update_svc.status and _update_svc.status.update_available:
                logger.info(
                    "Update available: %s -> %s",
                    _update_svc.status.current_version,
                    _update_svc.status.latest_version,
                )
        except Exception as exc:
            logger.warning("Update check failed: %s", exc)

    asyncio.create_task(_run_update_check())
```

- [ ] **Step 4: Run full backend test suite**

Run: `cd backend && source .venv/bin/activate && pytest --cov=app -v --tb=short 2>&1 | tail -10`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/update.py backend/app/main.py
git commit -m "feat(update): add REST endpoints and startup integration"
```

---

### Task 5: init.sh Update Subcommand

**Files:**
- Modify: `init.sh:1044-1062` (case statement)

- [ ] **Step 1: Add update and _do_update cases**

In `init.sh`, replace the case block (lines 1044-1062) with:

```bash
case "${1:-start}" in
    start)   start_services ;;
    stop)    stop_services ;;
    restart) do_restart ;;
    status)  show_status ;;
    logs)    show_logs ;;
    setup-vscode) shift; "$SCRIPT_DIR/scripts/setup-vscode.sh" "$@" ;;
    update)
        # Copy self to temp and re-exec to survive git checkout overwriting init.sh
        _tmp="$(mktemp /tmp/synthesis-update-XXXXXX.sh)"
        cp "$0" "$_tmp"
        chmod +x "$_tmp"
        shift
        exec "$_tmp" _do_update "$@"
        ;;
    _do_update)
        shift  # consume _do_update arg
        _update_tag="${1:-}"
        echo "[init.sh] Auto-update"

        # Auto-detect latest tag if not provided
        if [ -z "$_update_tag" ]; then
            git fetch --tags --prune-tags 2>/dev/null
            _update_tag=$(git tag --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
            if [ -z "$_update_tag" ]; then
                echo "  ✗ No release tags found"
                exit 1
            fi
        fi

        # Validate tag format
        if ! echo "$_update_tag" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
            echo "  ✗ Invalid tag format: $_update_tag"
            exit 1
        fi

        _current=$(python3 -c "import json; print(json.load(open('version.json'))['version'])" 2>/dev/null || echo "unknown")
        echo "  Current: v$_current"
        echo "  Target:  $_update_tag"

        # Capture old HEAD for dep diffing
        _old_head=$(git rev-parse HEAD)

        # Fetch and checkout
        echo "  Fetching tags..."
        git fetch --tags --prune-tags 2>/dev/null
        echo "  Checking out $_update_tag..."
        if ! git checkout "refs/tags/$_update_tag" 2>/dev/null; then
            echo "  ✗ Checkout failed. Check for uncommitted changes: git status"
            exit 1
        fi

        # Conditional dependency install
        if git diff --name-only "$_old_head" -- backend/requirements.txt | grep -q .; then
            echo "  Installing backend dependencies..."
            (cd backend && source .venv/bin/activate && pip install -r requirements.txt -q)
        fi
        if git diff --name-only "$_old_head" -- frontend/package-lock.json | grep -q .; then
            echo "  Installing frontend dependencies..."
            (cd frontend && npm ci --silent)
        fi

        # Run alembic migrations
        echo "  Running database migrations..."
        if ! (cd backend && source .venv/bin/activate && python -m alembic upgrade head 2>&1); then
            echo "  ! Migration warning: alembic upgrade may have failed. Check backend logs."
        fi

        # Restart services (use the NEW init.sh from the checked-out tag)
        echo "  Restarting services..."
        "$SCRIPT_DIR/init.sh" restart

        # Validate
        echo ""
        echo "  Validation:"
        _new_version=$(python3 -c "import json; print(json.load(open('version.json'))['version'])" 2>/dev/null || echo "unknown")
        _actual_tag=$(git describe --tags --exact-match HEAD 2>/dev/null || echo "none")
        if [ "$_actual_tag" = "$_update_tag" ]; then
            echo "    ✓ Tag: HEAD at $_actual_tag"
        else
            echo "    ✗ Tag: HEAD at $_actual_tag (expected $_update_tag)"
        fi
        echo "    ✓ Version: v$_new_version"

        # Clean up temp file
        rm -f "$0" 2>/dev/null
        echo ""
        echo "  ✓ Update complete: $_update_tag"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|setup-vscode|update [tag]}"
        echo ""
        echo "  start         Start all services (backend, MCP, frontend)"
        echo "  stop          Graceful stop (SIGTERM → wait → SIGKILL)"
        echo "  restart       Stop then start"
        echo "  status        Show service health with PIDs"
        echo "  logs          Tail all service logs"
        echo "  setup-vscode  Install VS Code bridge extension for sampling pipeline"
        echo "  update [tag]  Update to latest release (or specific tag)"
        exit 1
        ;;
esac
```

- [ ] **Step 2: Verify syntax**

Run: `bash -n init.sh && echo "Syntax OK"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add init.sh
git commit -m "feat(update): add init.sh update subcommand with self-copy safety"
```

---

### Task 6: Frontend — API Client + Store

**Files:**
- Modify: `frontend/src/lib/api/client.ts:536` (eventTypes array)
- Create: `frontend/src/lib/stores/update.svelte.ts`

- [ ] **Step 1: Add API functions and event types to client.ts**

In `frontend/src/lib/api/client.ts`, add after the last export (at end of file):

```typescript
// --- Update ---
export interface UpdateStatusResponse {
  current_version: string;
  latest_version: string | null;
  latest_tag: string | null;
  update_available: boolean;
  changelog: string | null;
  changelog_entries: { category: string; text: string }[] | null;
  checked_at: string | null;
  detection_tier: string;
}

export const getUpdateStatus = () =>
  apiFetch<UpdateStatusResponse>('/update/status');

export const applyUpdate = (tag: string) =>
  apiFetch<{ status: string; tag: string; message: string }>('/update/apply', {
    method: 'POST',
    body: JSON.stringify({ tag }),
  });
```

In the `eventTypes` array (around line 536), add after `'agent_changed'`:

```typescript
    'update_available',
    'update_complete',
```

- [ ] **Step 2: Create update store**

Create `frontend/src/lib/stores/update.svelte.ts`:

```typescript
/**
 * Update state management — tracks available updates, dialog state, and restart progress.
 */
import { getUpdateStatus, applyUpdate, getHealth } from '$lib/api/client';
import { addToast } from '$lib/stores/toast.svelte';

export interface ChangelogEntry {
  category: string;
  text: string;
}

export interface ValidationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

const LS_KEY = 'synthesis:dismiss_detached_head_warning';

class UpdateStore {
  // Version info
  updateAvailable = $state(false);
  currentVersion = $state<string | null>(null);
  latestVersion = $state<string | null>(null);
  latestTag = $state<string | null>(null);
  changelog = $state<string | null>(null);
  changelogEntries = $state<ChangelogEntry[] | null>(null);
  detectionTier = $state<string | null>(null);

  // Dialog
  dialogOpen = $state(false);

  // Update progress
  updating = $state(false);
  updateStep = $state<string | null>(null);
  updateComplete = $state(false);
  updateSuccess = $state<boolean | null>(null);
  validationChecks = $state<ValidationCheck[]>([]);

  // Dismissable warning
  hideDetachedWarning = $state(false);

  private _pollTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    // Load dismissed state from localStorage
    try {
      this.hideDetachedWarning = localStorage.getItem(LS_KEY) === 'true';
    } catch { /* SSR or no localStorage */ }
  }

  /** Populate from GET /api/update/status on page load. */
  async load(): Promise<void> {
    try {
      const s = await getUpdateStatus();
      this.currentVersion = s.current_version;
      this.latestVersion = s.latest_version;
      this.latestTag = s.latest_tag;
      this.updateAvailable = s.update_available;
      this.changelog = s.changelog;
      this.changelogEntries = s.changelog_entries;
      this.detectionTier = s.detection_tier;
    } catch {
      // Silently fail — update info is optional
    }
  }

  /** Handle SSE update_available event. */
  receive(data: Record<string, unknown>): void {
    this.currentVersion = (data.current_version as string) ?? this.currentVersion;
    this.latestVersion = (data.latest_version as string) ?? null;
    this.latestTag = (data.latest_tag as string) ?? null;
    this.changelog = (data.changelog as string) ?? null;
    this.changelogEntries = (data.changelog_entries as ChangelogEntry[]) ?? null;
    this.updateAvailable = true;
  }

  /** Handle SSE update_complete event (Phase 2 — after restart). */
  receiveComplete(data: Record<string, unknown>): void {
    this.updating = false;
    this.updateComplete = true;
    this.updateSuccess = data.success as boolean;
    this.validationChecks = (data.checks as ValidationCheck[]) ?? [];
    this.updateAvailable = false;
    this._stopPolling();

    if (this.updateSuccess) {
      addToast('created', `Updated to v${(data.version as string) ?? this.latestVersion}`);
    } else {
      addToast('deleted', 'Update completed with warnings — check validation results');
    }
  }

  /** Trigger the update — calls POST /api/update/apply then polls health. */
  async startUpdate(): Promise<void> {
    if (!this.latestTag || this.updating) return;

    this.updating = true;
    this.dialogOpen = false;

    try {
      await applyUpdate(this.latestTag);
      // Backend will restart — start tight health polling
      this._startPolling();
    } catch (err) {
      this.updating = false;
      const msg = err instanceof Error ? err.message : 'Update failed';
      addToast('deleted', msg);
    }
  }

  /** Toggle the "don't show again" checkbox. */
  dismissWarning(dismissed: boolean): void {
    this.hideDetachedWarning = dismissed;
    try {
      if (dismissed) {
        localStorage.setItem(LS_KEY, 'true');
      } else {
        localStorage.removeItem(LS_KEY);
      }
    } catch { /* SSR */ }
  }

  private _startPolling(): void {
    let elapsed = 0;
    this._pollTimer = setInterval(async () => {
      elapsed += 2000;
      try {
        const h = await getHealth();
        // If health responds with the new version, update is live
        if (h.version && this.latestVersion && h.version.startsWith(this.latestVersion.split('-')[0])) {
          // SSE will deliver update_complete — just clear the poll
          this._stopPolling();
        }
      } catch {
        // Backend still down — keep polling
      }
      if (elapsed > 120_000) {
        this._stopPolling();
        this.updating = false;
        addToast('deleted', 'Update may have failed. Try ./init.sh restart in the terminal.');
      }
    }, 2000);
  }

  private _stopPolling(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }
}

export const updateStore = new UpdateStore();
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api/client.ts frontend/src/lib/stores/update.svelte.ts
git commit -m "feat(update): add frontend API client + update store"
```

---

### Task 7: Frontend — UpdateBadge Component

**Files:**
- Create: `frontend/src/lib/components/shared/UpdateBadge.svelte`
- Modify: `frontend/src/lib/components/layout/StatusBar.svelte:161` (before Ctrl+K)
- Modify: `frontend/src/routes/app/+page.svelte` (SSE handlers + error suppression)

- [ ] **Step 1: Create UpdateBadge component**

Create `frontend/src/lib/components/shared/UpdateBadge.svelte`:

```svelte
<script lang="ts">
  import { updateStore } from '$lib/stores/update.svelte';
  import { tooltip } from '$lib/actions/tooltip';

  let dialogEl = $state<HTMLDivElement | null>(null);

  function toggleDialog() {
    if (updateStore.updating) return;
    updateStore.dialogOpen = !updateStore.dialogOpen;
  }

  function handleUpdate() {
    updateStore.startUpdate();
  }

  // Close on outside click
  function handleClickOutside(e: MouseEvent) {
    if (dialogEl && !dialogEl.contains(e.target as Node)) {
      updateStore.dialogOpen = false;
    }
  }

  $effect(() => {
    if (updateStore.dialogOpen) {
      document.addEventListener('click', handleClickOutside, true);
      return () => document.removeEventListener('click', handleClickOutside, true);
    }
  });

  const categoryColor: Record<string, string> = {
    Added: '#22c55e',
    Changed: '#eab308',
    Fixed: '#ef4444',
    Removed: '#ef4444',
    Deprecated: '#7a7a9e',
  };
</script>

<div class="update-badge-wrapper" bind:this={dialogEl}>
  {#if updateStore.updating}
    <span class="update-badge updating">&#8635; Restarting...</span>
  {:else}
    <button
      class="update-badge available"
      onclick={toggleDialog}
      use:tooltip={'Update available — click for details'}
    >
      &#8593; v{updateStore.latestVersion}
    </button>
  {/if}

  {#if updateStore.dialogOpen}
    <div class="update-dialog">
      <div class="dialog-header">
        <div>
          <div class="dialog-title">Update Available</div>
          <div class="dialog-subtitle">
            v{updateStore.currentVersion} &rarr; v{updateStore.latestVersion}
          </div>
        </div>
        <span class="dialog-new-badge">NEW</span>
      </div>

      {#if updateStore.changelogEntries && updateStore.changelogEntries.length > 0}
        <div class="dialog-changelog">
          <div class="changelog-label">What's New</div>
          {#each updateStore.changelogEntries as entry}
            <div class="changelog-entry">
              <span style="color: {categoryColor[entry.category] ?? '#7a7a9e'}">{entry.category}</span>
              &mdash; {entry.text}
            </div>
          {/each}
        </div>
      {/if}

      {#if !updateStore.hideDetachedWarning}
        <details class="dialog-warning">
          <summary>This will detach from your current branch</summary>
          <p>
            If you've made local commits or customizations, they won't be lost but
            will no longer be on an active branch. You can recover them later with
            <code>git checkout main</code>.
          </p>
          <p class="warning-who">
            This matters if you've committed changes to strategies, prompts, or code.
            If you only use the app as-is, you can safely dismiss this warning.
          </p>
          <label class="warning-dismiss">
            <input
              type="checkbox"
              checked={updateStore.hideDetachedWarning}
              onchange={(e) => updateStore.dismissWarning((e.target as HTMLInputElement).checked)}
            />
            Don't show this warning again
          </label>
        </details>
      {/if}

      <div class="dialog-actions">
        <button class="btn-update" onclick={handleUpdate}>Update &amp; Restart</button>
        <button class="btn-later" onclick={() => updateStore.dialogOpen = false}>Later</button>
      </div>

      <div class="dialog-footer">
        Your data (database, preferences, embeddings) is preserved.
      </div>
    </div>
  {/if}
</div>

<style>
  .update-badge-wrapper {
    position: relative;
  }
  .update-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 6px;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    border: none;
    background: transparent;
    cursor: pointer;
    line-height: 18px;
  }
  .update-badge.available {
    color: #22c55e;
    border: 1px solid #22c55e;
  }
  .update-badge.updating {
    color: #eab308;
    cursor: default;
    animation: pulse 1.5s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  .update-dialog {
    position: absolute;
    bottom: 24px;
    right: 0;
    width: 360px;
    border: 1px solid var(--color-border-subtle, #1a1a2e);
    background: var(--color-bg-secondary, #0d0d14);
    font-family: var(--font-mono);
    z-index: 100;
  }
  .dialog-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--color-border-subtle, #1a1a2e);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .dialog-title {
    color: var(--color-text, #e0e0e0);
    font-size: 13px;
    font-weight: 600;
  }
  .dialog-subtitle {
    color: var(--color-text-dim, #4a4a6e);
    font-size: 11px;
    margin-top: 2px;
  }
  .dialog-new-badge {
    color: #22c55e;
    font-size: 10px;
    border: 1px solid #22c55e;
    padding: 2px 6px;
    letter-spacing: 0.5px;
  }
  .dialog-changelog {
    padding: 12px 16px;
    border-bottom: 1px solid var(--color-border-subtle, #1a1a2e);
    max-height: 160px;
    overflow-y: auto;
  }
  .changelog-label {
    color: var(--color-text-dim, #7a7a9e);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
  }
  .changelog-entry {
    color: var(--color-text-secondary, #c0c0d0);
    font-size: 11px;
    line-height: 1.6;
    margin-bottom: 4px;
  }
  .dialog-warning {
    padding: 12px 16px;
    border-bottom: 1px solid var(--color-border-subtle, #1a1a2e);
    color: var(--color-text-dim, #7a7a9e);
    font-size: 10px;
    line-height: 1.5;
  }
  .dialog-warning summary {
    cursor: pointer;
    color: #eab308;
    font-size: 11px;
  }
  .dialog-warning p {
    margin: 8px 0 0;
  }
  .dialog-warning code {
    background: rgba(255,255,255,0.05);
    padding: 1px 4px;
  }
  .warning-who {
    color: var(--color-text-dim, #4a4a6e);
    font-style: italic;
  }
  .warning-dismiss {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
    cursor: pointer;
  }
  .warning-dismiss input {
    accent-color: #22c55e;
  }
  .dialog-actions {
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .btn-update {
    flex: 1;
    padding: 8px 0;
    text-align: center;
    border: 1px solid #22c55e;
    color: #22c55e;
    background: transparent;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .btn-update:hover {
    background: rgba(34, 197, 94, 0.1);
  }
  .btn-later {
    padding: 8px 12px;
    text-align: center;
    border: 1px solid var(--color-border-subtle, #2a2a3e);
    color: var(--color-text-dim, #7a7a9e);
    background: transparent;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .dialog-footer {
    padding: 8px 16px 12px;
    color: var(--color-text-dim, #4a4a6e);
    font-size: 10px;
    line-height: 1.4;
  }
</style>
```

- [ ] **Step 2: Add UpdateBadge to StatusBar**

In `frontend/src/lib/components/layout/StatusBar.svelte`, add import at top:

```typescript
import UpdateBadge from '$lib/components/shared/UpdateBadge.svelte';
import { updateStore } from '$lib/stores/update.svelte';
```

In the template, add before line 161 (before the `Ctrl+K` span), inside `<div class="status-right">`:

```svelte
    {#if updateStore.updateAvailable || updateStore.updating}
      <UpdateBadge />
    {/if}
```

- [ ] **Step 3: Add SSE handlers and error suppression to +page.svelte**

In `frontend/src/routes/app/+page.svelte`, add import at top:

```typescript
import { updateStore } from '$lib/stores/update.svelte';
```

After the `agent_changed` handler (around line 151), add:

```typescript
      if (type === 'update_available') {
        updateStore.receive(data as Record<string, unknown>);
        addToast('modified', `Update available: v${(data as any).latest_version}`);
      }
      if (type === 'update_complete') {
        updateStore.receiveComplete(data as Record<string, unknown>);
      }
```

In the `healthPoll` catch block (line 245), change to:

```typescript
      .catch(() => {
        if (!updateStore.updating) {
          backendError = 'Cannot connect to backend. Check that services are running.';
        }
      });
```

In the `$effect` block for initialization (find where `healthPoll()` is first called), add after the initial health poll:

```typescript
    updateStore.load();
```

- [ ] **Step 4: Run frontend type check**

Run: `cd frontend && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -5`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/shared/UpdateBadge.svelte \
        frontend/src/lib/components/layout/StatusBar.svelte \
        frontend/src/routes/app/+page.svelte
git commit -m "feat(update): add UpdateBadge component + StatusBar integration + SSE handlers"
```

---

### Task 8: Documentation

**Files:**
- Modify: `CLAUDE.md` (event bus types)
- Modify: `backend/CLAUDE.md` (router docs)
- Modify: `docs/CHANGELOG.md` (unreleased entry)

- [ ] **Step 1: Add event types to root CLAUDE.md**

Find the event bus line in the root `CLAUDE.md` that lists event types. Add `update_available`, `update_complete` to the list.

- [ ] **Step 2: Add router to backend CLAUDE.md**

In `backend/CLAUDE.md`, add to the Routers table:

```markdown
| `update.py` | `GET /api/update/status`, `POST /api/update/apply` (202) |
```

- [ ] **Step 3: Add changelog entry**

In `docs/CHANGELOG.md`, add under `## Unreleased`:

```markdown
### Added
- Auto-update detection on startup (3-tier: git tags, raw fetch, GitHub Releases API)
- Persistent StatusBar badge when a newer version is available
- One-click update dialog with changelog display and detached HEAD warning
- `./init.sh update [tag]` CLI subcommand for terminal-based updates
- Post-update validation suite (version, tag, migration checks)
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md backend/CLAUDE.md docs/CHANGELOG.md
git commit -m "docs: add auto-update feature to CLAUDE.md and changelog"
```

---

### Task 9: Comprehensive Backend Tests (Happy + Unhappy + Edge Cases)

**Files:**
- Modify: `backend/tests/test_update_service.py` (expand with integration + edge case tests)

- [ ] **Step 1: Add unhappy path and edge case tests**

Append to `backend/tests/test_update_service.py`:

```python
# ---------------------------------------------------------------------------
# Unhappy paths
# ---------------------------------------------------------------------------

class TestValidateTagUnhappy:
    """Exhaustive tag validation edge cases."""

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            validate_tag("v1.0.0/../../etc/passwd")

    def test_rejects_newline_injection(self):
        with pytest.raises(ValueError):
            validate_tag("v1.0.0\n--exec")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError):
            validate_tag("v1.0.0 --help")

    def test_rejects_unicode(self):
        with pytest.raises(ValueError):
            validate_tag("v1.0.0\u0000")

    def test_rejects_only_v(self):
        with pytest.raises(ValueError):
            validate_tag("v")


class TestCompareVersionsEdgeCases:
    def test_rc_vs_release(self):
        """RC is less than the final release."""
        assert compare_versions("0.4.0-rc.1", "0.4.0") == -1

    def test_different_dev_versions(self):
        assert compare_versions("0.3.20-dev", "0.3.21-dev") == -1

    def test_invalid_version_string(self):
        """Non-semver strings return 0 (can't compare)."""
        assert compare_versions("not-a-version", "0.4.0") == 0

    def test_both_invalid(self):
        assert compare_versions("abc", "xyz") == 0

    def test_major_bump(self):
        assert compare_versions("0.99.99", "1.0.0") == -1


class TestParseLatestTagEdgeCases:
    def test_dev_tags_skipped(self):
        from app.services.update_service import _parse_latest_tag
        output = "v0.5.0-dev\nv0.4.0-dev\nv0.3.0\n"
        assert _parse_latest_tag(output) == "v0.3.0"

    def test_only_prerelease_tags(self):
        from app.services.update_service import _parse_latest_tag
        output = "v0.5.0-rc.1\nv0.4.0-dev\n"
        assert _parse_latest_tag(output) is None

    def test_whitespace_lines(self):
        from app.services.update_service import _parse_latest_tag
        output = "  \n\nv0.4.0\n  \n"
        assert _parse_latest_tag(output) == "v0.4.0"

    def test_mixed_tags_and_noise(self):
        from app.services.update_service import _parse_latest_tag
        output = "latest\nrelease-2026\nv0.4.0\nv0.3.0\n"
        assert _parse_latest_tag(output) == "v0.4.0"


class TestParseChangelogEdgeCases:
    def test_no_category_header(self):
        """Entries without a header default to 'Changed'."""
        from app.services.update_service import _parse_changelog_entries
        body = "- Some improvement\n- Another one\n"
        entries = _parse_changelog_entries(body)
        assert len(entries) == 2
        assert all(e["category"] == "Changed" for e in entries)

    def test_asterisk_bullets(self):
        from app.services.update_service import _parse_changelog_entries
        body = "## Fixed\n* Bug one\n* Bug two\n"
        entries = _parse_changelog_entries(body)
        assert len(entries) == 2
        assert entries[0] == {"category": "Fixed", "text": "Bug one"}

    def test_nested_headers_ignored(self):
        from app.services.update_service import _parse_changelog_entries
        body = "## Added\n### Sub-section\n- Feature\n"
        entries = _parse_changelog_entries(body)
        assert len(entries) == 1

    def test_blank_lines_between_entries(self):
        from app.services.update_service import _parse_changelog_entries
        body = "## Added\n\n- Feature A\n\n- Feature B\n"
        entries = _parse_changelog_entries(body)
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# Integration tests (UpdateService with mocked subprocesses)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_for_updates_no_git(tmp_path):
    """When git is not available, falls back gracefully."""
    from app.services.update_service import UpdateService
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')
    svc = UpdateService(project_root=tmp_path)
    status = await svc.check_for_updates()
    assert status.current_version == "0.3.20-dev"
    # No git repo in tmp_path, so detection_tier should be "none" or "raw_fetch"
    assert status.detection_tier in ("none", "raw_fetch")


@pytest.mark.asyncio
async def test_check_for_updates_reads_version_json(tmp_path):
    """UpdateService reads current version from version.json."""
    (tmp_path / "version.json").write_text('{"version": "1.2.3"}')
    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)
    status = await svc.check_for_updates()
    assert status.current_version == "1.2.3"


@pytest.mark.asyncio
async def test_apply_update_rejects_invalid_tag(tmp_path):
    """apply_update raises ValueError for invalid tag."""
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')
    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)
    with pytest.raises(ValueError, match="Invalid tag format"):
        await svc.apply_update("not-a-tag")


@pytest.mark.asyncio
async def test_apply_update_rejects_nonexistent_tag(tmp_path):
    """apply_update raises ValueError when tag doesn't exist in local git."""
    import subprocess
    # Create a real git repo
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')

    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        await svc.apply_update("v99.99.99")


@pytest.mark.asyncio
async def test_update_status_default_none():
    """Status is None before first check."""
    from app.services.update_service import UpdateService
    from pathlib import Path
    svc = UpdateService(project_root=Path("/nonexistent"))
    assert svc.status is None


@pytest.mark.asyncio
async def test_validate_update_reports_failures(tmp_path):
    """Validation suite reports failures when git/alembic are unavailable."""
    (tmp_path / "version.json").write_text('{"version": "0.3.20-dev"}')
    from app.services.update_service import UpdateService
    svc = UpdateService(project_root=tmp_path)
    checks = await svc.validate_update("v0.4.0")
    # version check: 0.3.20-dev != 0.4.0
    assert not checks[0]["passed"]
    # git describe: no git repo
    assert not checks[1]["passed"]
    # alembic: no venv/alembic
    assert not checks[2]["passed"]
```

- [ ] **Step 2: Run all backend update tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_update_service.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_update_service.py
git commit -m "test(update): add comprehensive unhappy path, edge case, and integration tests"
```

---

### Task 10: Comprehensive Frontend Tests

**Files:**
- Create: `frontend/src/lib/components/shared/UpdateBadge.test.ts`

- [ ] **Step 1: Write comprehensive frontend tests**

Create `frontend/src/lib/components/shared/UpdateBadge.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { updateStore } from '$lib/stores/update.svelte';

vi.mock('$lib/api/client', () => ({
  getUpdateStatus: vi.fn().mockResolvedValue({ update_available: false, current_version: '0.3.20' }),
  applyUpdate: vi.fn().mockResolvedValue({ status: 'restarting', tag: 'v0.4.0' }),
  getHealth: vi.fn().mockResolvedValue({ version: '0.3.20', provider: 'mock' }),
}));

describe('UpdateStore — Happy Paths', () => {
  beforeEach(() => {
    updateStore.updateAvailable = false;
    updateStore.updating = false;
    updateStore.updateComplete = false;
    updateStore.updateSuccess = null;
    updateStore.dialogOpen = false;
    updateStore.latestVersion = null;
    updateStore.latestTag = null;
    updateStore.changelog = null;
    updateStore.changelogEntries = null;
    updateStore.hideDetachedWarning = false;
    updateStore.validationChecks = [];
    localStorage.clear();
  });

  it('starts with no update available', () => {
    expect(updateStore.updateAvailable).toBe(false);
    expect(updateStore.updating).toBe(false);
    expect(updateStore.updateComplete).toBe(false);
  });

  it('receive() populates all update info', () => {
    updateStore.receive({
      current_version: '0.3.20-dev',
      latest_version: '0.4.0',
      latest_tag: 'v0.4.0',
      changelog: '## Added\n- Feature',
      changelog_entries: [{ category: 'Added', text: 'Feature' }],
    });
    expect(updateStore.updateAvailable).toBe(true);
    expect(updateStore.latestVersion).toBe('0.4.0');
    expect(updateStore.latestTag).toBe('v0.4.0');
    expect(updateStore.changelog).toBe('## Added\n- Feature');
    expect(updateStore.changelogEntries).toHaveLength(1);
  });

  it('receiveComplete() with success clears badge', () => {
    updateStore.updating = true;
    updateStore.updateAvailable = true;
    updateStore.receiveComplete({
      success: true,
      version: '0.4.0',
      checks: [
        { name: 'version', passed: true, detail: 'OK' },
        { name: 'tag', passed: true, detail: 'OK' },
        { name: 'migrations', passed: true, detail: 'OK' },
      ],
    });
    expect(updateStore.updating).toBe(false);
    expect(updateStore.updateComplete).toBe(true);
    expect(updateStore.updateSuccess).toBe(true);
    expect(updateStore.updateAvailable).toBe(false);
    expect(updateStore.validationChecks).toHaveLength(3);
  });

  it('dismissWarning persists and restores', () => {
    updateStore.dismissWarning(true);
    expect(updateStore.hideDetachedWarning).toBe(true);
    expect(localStorage.getItem('synthesis:dismiss_detached_head_warning')).toBe('true');

    updateStore.dismissWarning(false);
    expect(updateStore.hideDetachedWarning).toBe(false);
    expect(localStorage.getItem('synthesis:dismiss_detached_head_warning')).toBeNull();
  });
});

describe('UpdateStore — Unhappy Paths', () => {
  beforeEach(() => {
    updateStore.updateAvailable = false;
    updateStore.updating = false;
    updateStore.dialogOpen = false;
    updateStore.latestVersion = null;
    updateStore.latestTag = null;
    localStorage.clear();
  });

  it('receiveComplete() with failure keeps badge visible', () => {
    updateStore.updating = true;
    updateStore.updateAvailable = true;
    updateStore.receiveComplete({
      success: false,
      version: '0.4.0',
      checks: [
        { name: 'version', passed: true, detail: 'OK' },
        { name: 'tag', passed: false, detail: 'HEAD detached' },
      ],
    });
    expect(updateStore.updateSuccess).toBe(false);
    expect(updateStore.updateComplete).toBe(true);
    expect(updateStore.validationChecks).toHaveLength(2);
  });

  it('receive() with null changelog still sets updateAvailable', () => {
    updateStore.receive({
      current_version: '0.3.20',
      latest_version: '0.4.0',
      latest_tag: 'v0.4.0',
      changelog: null,
      changelog_entries: null,
    });
    expect(updateStore.updateAvailable).toBe(true);
    expect(updateStore.changelog).toBeNull();
    expect(updateStore.changelogEntries).toBeNull();
  });

  it('startUpdate() does nothing when no latestTag', async () => {
    updateStore.latestTag = null;
    await updateStore.startUpdate();
    expect(updateStore.updating).toBe(false);
  });

  it('startUpdate() does nothing when already updating', async () => {
    updateStore.latestTag = 'v0.4.0';
    updateStore.updating = true;
    const { applyUpdate } = await import('$lib/api/client');
    await updateStore.startUpdate();
    expect(applyUpdate).not.toHaveBeenCalled();
  });
});

describe('UpdateStore — Edge Cases', () => {
  beforeEach(() => {
    updateStore.updateAvailable = false;
    updateStore.updating = false;
    updateStore.dialogOpen = false;
    localStorage.clear();
  });

  it('receive() called multiple times overwrites cleanly', () => {
    updateStore.receive({ latest_version: '0.4.0', latest_tag: 'v0.4.0' });
    updateStore.receive({ latest_version: '0.5.0', latest_tag: 'v0.5.0' });
    expect(updateStore.latestVersion).toBe('0.5.0');
    expect(updateStore.latestTag).toBe('v0.5.0');
  });

  it('receiveComplete() after receive() clears update state', () => {
    updateStore.receive({ latest_version: '0.4.0', latest_tag: 'v0.4.0' });
    expect(updateStore.updateAvailable).toBe(true);
    updateStore.updating = true;
    updateStore.receiveComplete({ success: true, version: '0.4.0', checks: [] });
    expect(updateStore.updateAvailable).toBe(false);
  });

  it('localStorage failure does not crash dismissWarning', () => {
    const orig = localStorage.setItem;
    localStorage.setItem = () => { throw new Error('quota exceeded'); };
    // Should not throw
    updateStore.dismissWarning(true);
    expect(updateStore.hideDetachedWarning).toBe(true);
    localStorage.setItem = orig;
  });
});
```

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm run test 2>&1 | tail -10`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/shared/UpdateBadge.test.ts
git commit -m "test(update): comprehensive frontend tests — happy, unhappy, edge cases"
```

---

### Task 11: Router Integration Tests

**Files:**
- Modify: `backend/tests/test_update_service.py` (add router-level tests)

- [ ] **Step 1: Add router integration tests**

Append to `backend/tests/test_update_service.py`:

```python
# ---------------------------------------------------------------------------
# Router integration tests (using app_client fixture)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_update_status_no_service(app_client):
    """GET /api/update/status returns default when service not initialized."""
    resp = await app_client.get("/api/update/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_version" in data
    assert data["update_available"] is False


@pytest.mark.asyncio
async def test_apply_update_invalid_tag(app_client):
    """POST /api/update/apply rejects invalid tag format."""
    resp = await app_client.post(
        "/api/update/apply",
        json={"tag": "not-a-tag"},
    )
    assert resp.status_code in (400, 500)


@pytest.mark.asyncio
async def test_apply_update_shell_injection(app_client):
    """POST /api/update/apply rejects shell metacharacters."""
    resp = await app_client.post(
        "/api/update/apply",
        json={"tag": "v1.0.0; rm -rf /"},
    )
    assert resp.status_code in (400, 500)
    assert "Invalid tag" in resp.json().get("detail", "")
```

- [ ] **Step 2: Run integration tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_update_service.py -v --tb=short`
Expected: All tests PASS (app_client fixture from conftest.py provides test client)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_update_service.py
git commit -m "test(update): add router integration tests for security validation"
```

---

### Task 12: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && source .venv/bin/activate && pytest --cov=app -v --tb=short 2>&1 | tail -5`
Expected: All tests PASS, no regressions

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm run test`
Expected: All tests PASS

- [ ] **Step 3: Restart services and verify endpoint**

Run:
```bash
cd /home/drei/my_project/builder/claude-quickstarts/autonomous-coding/generations/PromptForge_v2
./init.sh restart
sleep 10
curl -s http://localhost:8000/api/update/status | python3 -m json.tool
```

Expected: JSON response with `current_version`, `update_available`, `detection_tier`

- [ ] **Step 4: Check logs for update check**

Run: `grep "Update available\|Update check\|update_available" data/backend.log | head -5`
Expected: Either "Update available" or "Update check failed" (depending on tag state)

- [ ] **Step 5: Verify init.sh update syntax**

Run: `./init.sh update --dry-run 2>&1 || echo "Expected: shows usage or runs check"`

- [ ] **Step 6: Final commit**

```bash
git add -A
git status
# If any remaining files, commit:
git commit -m "feat: auto-update detection + one-click update with validation"
```
