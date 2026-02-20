"""Tests for OptimizationRepository — CRUD, filters, pagination, tags, stats."""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import OptimizationStatus
from app.models.optimization import Optimization
from app.models.project import Project, Prompt
from app.repositories.optimization import (
    ListFilters,
    OptimizationRepository,
    Pagination,
)
from app.repositories.project import ProjectRepository, ensure_prompt_in_project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed(session: AsyncSession, **overrides) -> Optimization:
    """Insert an Optimization record and return it."""
    defaults = {
        "id": "test-001",
        "raw_prompt": "test prompt",
        "status": OptimizationStatus.COMPLETED,
        "task_type": "coding",
        "overall_score": 0.8,
    }
    defaults.update(overrides)
    opt = Optimization(**defaults)
    session.add(opt)
    await session.flush()
    return opt


# ---------------------------------------------------------------------------
# TestGetById
# ---------------------------------------------------------------------------

class TestGetById:
    @pytest.mark.asyncio
    async def test_found(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="abc-123")
        result = await repo.get_by_id("abc-123")
        assert result is not None
        assert result.id == "abc-123"

    @pytest.mark.asyncio
    async def test_not_found(self, db_session):
        repo = OptimizationRepository(db_session)
        result = await repo.get_by_id("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# TestCreate
# ---------------------------------------------------------------------------

class TestCreate:
    @pytest.mark.asyncio
    async def test_basic_create(self, db_session):
        repo = OptimizationRepository(db_session)
        opt = await repo.create(
            id="new-001",
            raw_prompt="hello world",
            status=OptimizationStatus.RUNNING,
        )
        assert opt.id == "new-001"
        assert opt.raw_prompt == "hello world"
        assert opt.status == OptimizationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, db_session):
        repo = OptimizationRepository(db_session)
        opt = await repo.create(
            id="new-002",
            raw_prompt="test",
            status=OptimizationStatus.COMPLETED,
            project="my-project",
            tags=json.dumps(["tag1"]),
            title="My Title",
        )
        assert opt.project == "my-project"
        assert opt.title == "My Title"


# ---------------------------------------------------------------------------
# TestDeleteById
# ---------------------------------------------------------------------------

class TestDeleteById:
    @pytest.mark.asyncio
    async def test_delete_existing(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="del-001")
        result = await repo.delete_by_id("del-001")
        assert result is True
        assert await repo.get_by_id("del-001") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db_session):
        repo = OptimizationRepository(db_session)
        result = await repo.delete_by_id("nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# TestList
# ---------------------------------------------------------------------------

class TestList:
    @pytest.mark.asyncio
    async def test_no_filters(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a")
        await _seed(db_session, id="b")
        items, total = await repo.list()
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_filter_by_project(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", project="proj-a")
        await _seed(db_session, id="b", project="proj-b")
        items, total = await repo.list(filters=ListFilters(project="proj-a"))
        assert total == 1
        assert items[0].id == "a"

    @pytest.mark.asyncio
    async def test_filter_by_task_type(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", task_type="coding")
        await _seed(db_session, id="b", task_type="creative")
        items, total = await repo.list(filters=ListFilters(task_type="coding"))
        assert total == 1
        assert items[0].task_type == "coding"

    @pytest.mark.asyncio
    async def test_filter_by_status(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", status=OptimizationStatus.COMPLETED)
        await _seed(db_session, id="b", status=OptimizationStatus.ERROR)
        items, total = await repo.list(
            filters=ListFilters(status=OptimizationStatus.COMPLETED)
        )
        assert total == 1
        assert items[0].status == OptimizationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_filter_by_min_score(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", overall_score=0.9)
        await _seed(db_session, id="b", overall_score=0.3)
        # min_score=7 on 1-10 scale → score_threshold_to_db converts to 0.65
        items, total = await repo.list(filters=ListFilters(min_score=7))
        assert total == 1
        assert items[0].id == "a"

    @pytest.mark.asyncio
    async def test_filter_by_search(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", raw_prompt="optimize my SQL query")
        await _seed(db_session, id="b", raw_prompt="write a poem")
        items, total = await repo.list(filters=ListFilters(search="SQL"))
        assert total == 1
        assert items[0].id == "a"

    @pytest.mark.asyncio
    async def test_completed_only(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", status=OptimizationStatus.COMPLETED)
        await _seed(db_session, id="b", status=OptimizationStatus.RUNNING)
        items, total = await repo.list(filters=ListFilters(completed_only=True))
        assert total == 1
        assert items[0].id == "a"

    @pytest.mark.asyncio
    async def test_search_with_special_characters_no_crash(self, db_session):
        """Searching with SQL wildcards (%, _) should not crash."""
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", raw_prompt="100% complete")
        await _seed(db_session, id="b", raw_prompt="nothing here")
        # Should not raise even with wildcard characters in search text
        items, total = await repo.list(filters=ListFilters(search="100%"))
        assert total >= 0


# ---------------------------------------------------------------------------
# TestPagination
# ---------------------------------------------------------------------------

class TestPagination:
    @pytest.mark.asyncio
    async def test_offset_and_limit(self, db_session):
        repo = OptimizationRepository(db_session)
        for i in range(5):
            await _seed(db_session, id=f"item-{i}")
        items, total = await repo.list(pagination=Pagination(offset=2, limit=2))
        assert total == 5
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_sort_asc(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(
            db_session, id="old",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        await _seed(
            db_session, id="new",
            created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        items, _ = await repo.list(
            pagination=Pagination(sort="created_at", order="asc")
        )
        assert items[0].id == "old"
        assert items[1].id == "new"

    @pytest.mark.asyncio
    async def test_sort_desc(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(
            db_session, id="old",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        await _seed(
            db_session, id="new",
            created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        items, _ = await repo.list(
            pagination=Pagination(sort="created_at", order="desc")
        )
        assert items[0].id == "new"
        assert items[1].id == "old"

    @pytest.mark.asyncio
    async def test_invalid_sort_falls_back(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a")
        # Should not crash; defaults to created_at
        items, total = await repo.list(
            pagination=Pagination(sort="nonexistent_field")
        )
        assert total == 1


# ---------------------------------------------------------------------------
# TestClearAll
# ---------------------------------------------------------------------------

class TestClearAll:
    @pytest.mark.asyncio
    async def test_clears_records(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a")
        await _seed(db_session, id="b")
        count = await repo.clear_all()
        assert count == 2
        items, total = await repo.list()
        assert total == 0

    @pytest.mark.asyncio
    async def test_empty_table_returns_zero(self, db_session):
        repo = OptimizationRepository(db_session)
        count = await repo.clear_all()
        assert count == 0


# ---------------------------------------------------------------------------
# TestUpdateTags
# ---------------------------------------------------------------------------

class TestUpdateTags:
    @pytest.mark.asyncio
    async def test_add_tags(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="t1", tags=json.dumps(["existing"]))
        result = await repo.update_tags("t1", add_tags=["new"])
        assert "new" in result["tags"]
        assert "existing" in result["tags"]

    @pytest.mark.asyncio
    async def test_remove_tags(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="t1", tags=json.dumps(["a", "b"]))
        result = await repo.update_tags("t1", remove_tags=["a"])
        assert result["tags"] == ["b"]

    @pytest.mark.asyncio
    async def test_add_duplicate_tag_ignored(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="t1", tags=json.dumps(["a"]))
        result = await repo.update_tags("t1", add_tags=["a"])
        assert result["tags"] == ["a"]

    @pytest.mark.asyncio
    async def test_set_project(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="t1")
        result = await repo.update_tags("t1", project="new-proj")
        assert result["project"] == "new-proj"

    @pytest.mark.asyncio
    async def test_set_title(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="t1")
        result = await repo.update_tags("t1", title="New Title")
        assert result["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self, db_session):
        repo = OptimizationRepository(db_session)
        result = await repo.update_tags("nonexistent", add_tags=["x"])
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_project_with_none(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="t1", project="old-proj")
        result = await repo.update_tags("t1", project=None)
        assert result["project"] is None


# ---------------------------------------------------------------------------
# TestGetStats
# ---------------------------------------------------------------------------

class TestGetStats:
    @pytest.mark.asyncio
    async def test_empty_db(self, db_session):
        repo = OptimizationRepository(db_session)
        stats = await repo.get_stats()
        assert stats["total_optimizations"] == 0
        assert stats["average_overall_score"] is None

    @pytest.mark.asyncio
    async def test_with_records(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(
            db_session, id="a", overall_score=0.8, is_improvement=True,
            framework_applied="persona-assignment",
        )
        await _seed(
            db_session, id="b", overall_score=0.6, is_improvement=False,
            framework_applied="chain-of-thought",
        )
        stats = await repo.get_stats()
        assert stats["total_optimizations"] == 2
        assert stats["average_overall_score"] is not None
        assert stats["improvement_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_project_filter(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", project="alpha", overall_score=0.9)
        await _seed(db_session, id="b", project="beta", overall_score=0.5)
        stats = await repo.get_stats(project="alpha")
        assert stats["total_optimizations"] == 1

    @pytest.mark.asyncio
    async def test_strategy_distribution(self, db_session):
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", framework_applied="persona-assignment")
        await _seed(db_session, id="b", framework_applied="persona-assignment")
        await _seed(db_session, id="c", framework_applied="few-shot-scaffolding")
        stats = await repo.get_stats()
        assert stats["strategy_distribution"]["persona-assignment"] == 2
        assert stats["strategy_distribution"]["few-shot-scaffolding"] == 1

    @pytest.mark.asyncio
    async def test_legacy_alias_normalization(self, db_session):
        """Legacy strategy names are merged under their canonical name."""
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", framework_applied="constraint-focused", overall_score=0.8)
        await _seed(db_session, id="b", framework_applied="constraint-injection", overall_score=0.6)
        stats = await repo.get_stats()
        dist = stats["strategy_distribution"]
        assert "constraint-injection" in dist
        assert dist["constraint-injection"] == 2
        assert "constraint-focused" not in dist

    @pytest.mark.asyncio
    async def test_legacy_alias_score_averaging(self, db_session):
        """Scores are correctly weighted when merging legacy + canonical buckets."""
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", framework_applied="role-based", overall_score=0.8)
        await _seed(db_session, id="b", framework_applied="persona-assignment", overall_score=0.6)
        stats = await repo.get_stats()
        scores = stats["score_by_strategy"]
        assert "persona-assignment" in scores
        assert "role-based" not in scores
        # Weighted average: (0.8 + 0.6) / 2 = 0.7
        assert scores["persona-assignment"] == 0.7

    @pytest.mark.asyncio
    async def test_legacy_alias_all_four_aliases(self, db_session):
        """All four legacy aliases normalize to canonical names."""
        repo = OptimizationRepository(db_session)
        await _seed(db_session, id="a", framework_applied="few-shot")
        await _seed(db_session, id="b", framework_applied="role-based")
        await _seed(db_session, id="c", framework_applied="constraint-focused")
        await _seed(db_session, id="d", framework_applied="structured-enhancement")
        stats = await repo.get_stats()
        dist = stats["strategy_distribution"]
        assert "few-shot-scaffolding" in dist
        assert "persona-assignment" in dist
        assert "constraint-injection" in dist
        assert "role-task-format" in dist
        # No legacy names should appear
        for legacy in ("few-shot", "role-based", "constraint-focused", "structured-enhancement"):
            assert legacy not in dist


# ---------------------------------------------------------------------------
# Forge linking helpers
# ---------------------------------------------------------------------------

async def _seed_project(session: AsyncSession, name: str = "testproj") -> Project:
    """Insert a Project and return it."""
    proj = Project(name=name)
    session.add(proj)
    await session.flush()
    return proj


async def _seed_prompt(
    session: AsyncSession, project: Project, content: str = "test prompt",
) -> Prompt:
    """Insert a Prompt linked to a project and return it."""
    prompt = Prompt(content=content, project_id=project.id)
    session.add(prompt)
    await session.flush()
    return prompt


# ---------------------------------------------------------------------------
# TestGetByPromptId
# ---------------------------------------------------------------------------


class TestGetByPromptId:
    @pytest.mark.asyncio
    async def test_fk_match(self, db_session):
        """Optimizations linked by FK are returned."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session)
        prompt = await _seed_prompt(db_session, proj, "my prompt")
        await _seed(db_session, id="opt-1", prompt_id=prompt.id, raw_prompt="my prompt")
        items, total = await repo.get_by_prompt_id(prompt.id)
        assert total == 1
        assert items[0].id == "opt-1"

    @pytest.mark.asyncio
    async def test_content_fallback(self, db_session):
        """Un-linked optimizations matching by content+project are found."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session, "myproj")
        prompt = await _seed_prompt(db_session, proj, "some unique prompt")
        await _seed(
            db_session, id="opt-2", raw_prompt="some unique prompt",
            project="myproj", prompt_id=None,
        )
        items, total = await repo.get_by_prompt_id(
            prompt.id, prompt_content="some unique prompt", project_name="myproj",
        )
        assert total == 1
        assert items[0].id == "opt-2"

    @pytest.mark.asyncio
    async def test_no_content_fallback_without_args(self, db_session):
        """Without content/project args, only FK matches are returned."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session, "proj")
        prompt = await _seed_prompt(db_session, proj, "some prompt")
        await _seed(
            db_session, id="opt-3", raw_prompt="some prompt",
            project="proj", prompt_id=None,
        )
        items, total = await repo.get_by_prompt_id(prompt.id)
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_no_double_counting(self, db_session):
        """FK-linked + content fallback are deduplicated (mutually exclusive)."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session, "dedup")
        prompt = await _seed_prompt(db_session, proj, "test prompt")
        # FK-linked
        await _seed(
            db_session, id="opt-fk", raw_prompt="test prompt",
            project="dedup", prompt_id=prompt.id,
        )
        # Un-linked but matching content
        await _seed(
            db_session, id="opt-content", raw_prompt="test prompt",
            project="dedup", prompt_id=None,
        )
        items, total = await repo.get_by_prompt_id(
            prompt.id, prompt_content="test prompt", project_name="dedup",
        )
        assert total == 2
        ids = {i.id for i in items}
        assert ids == {"opt-fk", "opt-content"}


# ---------------------------------------------------------------------------
# TestGetForgeCounts
# ---------------------------------------------------------------------------


class TestGetForgeCounts:
    @pytest.mark.asyncio
    async def test_empty(self, db_session):
        repo = OptimizationRepository(db_session)
        assert await repo.get_forge_counts([]) == {}

    @pytest.mark.asyncio
    async def test_fk_counts(self, db_session):
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session)
        p1 = await _seed_prompt(db_session, proj, "prompt A")
        p2 = await _seed_prompt(db_session, proj, "prompt B")
        await _seed(db_session, id="a1", prompt_id=p1.id)
        await _seed(db_session, id="a2", prompt_id=p1.id)
        await _seed(db_session, id="b1", prompt_id=p2.id)
        counts = await repo.get_forge_counts([p1.id, p2.id])
        assert counts[p1.id] == 2
        assert counts[p2.id] == 1

    @pytest.mark.asyncio
    async def test_content_fallback_counts(self, db_session):
        """Content-map fallback adds counts for un-linked optimizations."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session, "proj")
        p1 = await _seed_prompt(db_session, proj, "prompt X")
        # FK-linked
        await _seed(db_session, id="fk1", prompt_id=p1.id)
        # Un-linked content match
        await _seed(
            db_session, id="cm1", raw_prompt="prompt X",
            project="proj", prompt_id=None,
        )
        content_map = {p1.id: ("prompt X", "proj")}
        counts = await repo.get_forge_counts([p1.id], content_map=content_map)
        assert counts[p1.id] == 2  # 1 FK + 1 content

    @pytest.mark.asyncio
    async def test_content_fallback_ignores_linked(self, db_session):
        """Content fallback only counts where prompt_id IS NULL."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session, "proj2")
        p1 = await _seed_prompt(db_session, proj, "prompt Y")
        p2 = await _seed_prompt(db_session, proj, "prompt Y")  # same content
        # Linked to p2, same content as p1
        await _seed(
            db_session, id="linked", raw_prompt="prompt Y",
            project="proj2", prompt_id=p2.id,
        )
        content_map = {p1.id: ("prompt Y", "proj2")}
        counts = await repo.get_forge_counts([p1.id], content_map=content_map)
        # The linked optimization maps to p2, not p1, and prompt_id is set
        # so content fallback shouldn't count it
        assert counts.get(p1.id, 0) == 0


# ---------------------------------------------------------------------------
# TestEnsurePromptInProject
# ---------------------------------------------------------------------------


class TestEnsurePromptInProject:
    @pytest.mark.asyncio
    async def test_creates_prompt_on_first_call(self, db_session):
        proj = await _seed_project(db_session, "proj")
        prompt_id = await ensure_prompt_in_project(db_session, proj.id, "hello world")
        assert prompt_id is not None
        # Verify it was actually written
        prompt = await db_session.get(Prompt, prompt_id)
        assert prompt is not None
        assert prompt.content == "hello world"
        assert prompt.project_id == proj.id

    @pytest.mark.asyncio
    async def test_idempotent_same_content(self, db_session):
        proj = await _seed_project(db_session, "proj")
        id1 = await ensure_prompt_in_project(db_session, proj.id, "same content")
        id2 = await ensure_prompt_in_project(db_session, proj.id, "same content")
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_different_content_different_id(self, db_session):
        proj = await _seed_project(db_session, "proj")
        id1 = await ensure_prompt_in_project(db_session, proj.id, "content A")
        id2 = await ensure_prompt_in_project(db_session, proj.id, "content B")
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_project_id(self, db_session):
        result = await ensure_prompt_in_project(db_session, "", "content")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_content(self, db_session):
        proj = await _seed_project(db_session, "proj")
        result = await ensure_prompt_in_project(db_session, proj.id, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_fuzzy_whitespace_match(self, db_session):
        """Trailing/leading whitespace and extra internal spaces should match."""
        proj = await _seed_project(db_session, "proj")
        id1 = await ensure_prompt_in_project(db_session, proj.id, "hello   world")
        id2 = await ensure_prompt_in_project(db_session, proj.id, "hello world")
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_fuzzy_whitespace_newlines(self, db_session):
        """Content with newlines should match collapsed version."""
        proj = await _seed_project(db_session, "proj")
        id1 = await ensure_prompt_in_project(db_session, proj.id, "line one\nline two")
        id2 = await ensure_prompt_in_project(db_session, proj.id, "line one line two")
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_fuzzy_whitespace_trailing(self, db_session):
        """Trailing whitespace should match stripped version."""
        proj = await _seed_project(db_session, "proj")
        id1 = await ensure_prompt_in_project(db_session, proj.id, "hello world  ")
        id2 = await ensure_prompt_in_project(db_session, proj.id, "hello world")
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_order_index_increments(self, db_session):
        proj = await _seed_project(db_session, "proj")
        id1 = await ensure_prompt_in_project(db_session, proj.id, "first")
        id2 = await ensure_prompt_in_project(db_session, proj.id, "second")
        p1 = await db_session.get(Prompt, id1)
        p2 = await db_session.get(Prompt, id2)
        assert p1.order_index < p2.order_index


# ---------------------------------------------------------------------------
# TestGetLatestForgeMetadata
# ---------------------------------------------------------------------------


class TestGetLatestForgeMetadata:
    @pytest.mark.asyncio
    async def test_returns_latest_completed(self, db_session):
        """Newest completed optimization is returned for a prompt."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session)
        prompt = await _seed_prompt(db_session, proj, "my prompt")
        await _seed(
            db_session, id="old-forge", prompt_id=prompt.id,
            status=OptimizationStatus.COMPLETED,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            task_type="coding",
        )
        await _seed(
            db_session, id="new-forge", prompt_id=prompt.id,
            status=OptimizationStatus.COMPLETED,
            created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            task_type="creative",
        )
        result = await repo.get_latest_forge_metadata([prompt.id])
        assert prompt.id in result
        assert result[prompt.id].id == "new-forge"
        assert result[prompt.id].task_type == "creative"

    @pytest.mark.asyncio
    async def test_ignores_non_completed(self, db_session):
        """Error/running optimizations are excluded."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session)
        prompt = await _seed_prompt(db_session, proj, "my prompt")
        await _seed(
            db_session, id="err-forge", prompt_id=prompt.id,
            status=OptimizationStatus.ERROR,
        )
        await _seed(
            db_session, id="run-forge", prompt_id=prompt.id,
            status=OptimizationStatus.RUNNING,
        )
        result = await repo.get_latest_forge_metadata([prompt.id])
        assert prompt.id not in result

    @pytest.mark.asyncio
    async def test_empty_input(self, db_session):
        """Empty prompt_ids list returns empty dict."""
        repo = OptimizationRepository(db_session)
        result = await repo.get_latest_forge_metadata([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_content_fallback(self, db_session):
        """Un-linked legacy records matched by content+project."""
        repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session, "legproj")
        prompt = await _seed_prompt(db_session, proj, "legacy prompt")
        await _seed(
            db_session, id="leg-forge", raw_prompt="legacy prompt",
            project="legproj", prompt_id=None,
            status=OptimizationStatus.COMPLETED,
            framework_applied="persona-assignment",
        )
        content_map = {prompt.id: ("legacy prompt", "legproj")}
        result = await repo.get_latest_forge_metadata(
            [prompt.id], content_map=content_map,
        )
        assert prompt.id in result
        assert result[prompt.id].id == "leg-forge"
        assert result[prompt.id].framework_applied == "persona-assignment"


# ---------------------------------------------------------------------------
# TestDeletePrompt — cascade-delete linked optimizations
# ---------------------------------------------------------------------------


class TestDeletePrompt:
    @pytest.mark.asyncio
    async def test_cascade_deletes_linked_optimizations(self, db_session):
        """Deleting a prompt should also delete all linked optimizations."""
        repo = ProjectRepository(db_session)
        opt_repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session)
        prompt = await _seed_prompt(db_session, proj, "cascade test")
        await _seed(db_session, id="linked-opt-1", prompt_id=prompt.id)
        await _seed(db_session, id="linked-opt-2", prompt_id=prompt.id)

        await repo.delete_prompt(prompt)

        assert await opt_repo.get_by_id("linked-opt-1") is None
        assert await opt_repo.get_by_id("linked-opt-2") is None

    @pytest.mark.asyncio
    async def test_unlinked_optimizations_unaffected(self, db_session):
        """Optimizations linked to a different prompt should survive."""
        repo = ProjectRepository(db_session)
        opt_repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session)
        prompt_a = await _seed_prompt(db_session, proj, "prompt A")
        prompt_b = await _seed_prompt(db_session, proj, "prompt B")
        await _seed(db_session, id="opt-a", prompt_id=prompt_a.id)
        await _seed(db_session, id="opt-b", prompt_id=prompt_b.id)

        await repo.delete_prompt(prompt_a)

        assert await opt_repo.get_by_id("opt-a") is None
        assert await opt_repo.get_by_id("opt-b") is not None

    @pytest.mark.asyncio
    async def test_returns_deleted_count(self, db_session):
        """Return value should match the count of deleted optimizations."""
        repo = ProjectRepository(db_session)
        proj = await _seed_project(db_session)
        prompt = await _seed_prompt(db_session, proj, "count test")
        await _seed(db_session, id="c1", prompt_id=prompt.id)
        await _seed(db_session, id="c2", prompt_id=prompt.id)
        await _seed(db_session, id="c3", prompt_id=prompt.id)

        deleted = await repo.delete_prompt(prompt)
        assert deleted == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_linked(self, db_session):
        """A prompt with no linked optimizations should return 0."""
        repo = ProjectRepository(db_session)
        proj = await _seed_project(db_session)
        prompt = await _seed_prompt(db_session, proj, "no links")

        deleted = await repo.delete_prompt(prompt)
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_deletes_unlinked_orphan_optimizations(self, db_session):
        """Deleting a prompt should also delete unlinked optimizations with
        matching project + raw_prompt (prevents startup backfill resurrection)."""
        repo = ProjectRepository(db_session)
        opt_repo = OptimizationRepository(db_session)
        proj = await _seed_project(db_session, name="orphan-proj")
        prompt = await _seed_prompt(db_session, proj, "orphan content")
        # Linked optimization (has prompt_id)
        await _seed(db_session, id="linked", prompt_id=prompt.id, project="orphan-proj", raw_prompt="orphan content")
        # Unlinked optimization (prompt_id=None, same project + content)
        await _seed(db_session, id="orphan", project="orphan-proj", raw_prompt="orphan content")
        # Unrelated optimization (different content, same project)
        await _seed(db_session, id="unrelated", project="orphan-proj", raw_prompt="different content")

        deleted = await repo.delete_prompt(prompt)
        assert deleted == 2  # linked + orphan
        assert await opt_repo.get_by_id("linked") is None
        assert await opt_repo.get_by_id("orphan") is None
        assert await opt_repo.get_by_id("unrelated") is not None
