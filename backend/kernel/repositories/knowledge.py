"""Repository for kernel Knowledge Base — project knowledge for all apps."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel.models.knowledge import KnowledgeProfile, KnowledgeSource

logger = logging.getLogger(__name__)

MAX_SOURCES_PER_PROFILE = 50
MAX_SOURCE_CONTENT_CHARS = 100_000
VALID_SOURCE_TYPES = frozenset({"document", "paste", "api_reference", "specification", "notes"})

# Identity fields that support manual > auto-detected merge
_IDENTITY_FIELDS = ("language", "framework", "description", "test_framework")


class KnowledgeRepository:
    """Data access for kernel_knowledge_profiles and kernel_knowledge_sources.

    Registered as the ``"knowledge"`` kernel service (class, not instance).
    Instantiated per-request with an ``AsyncSession``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # Profiles                                                            #
    # ------------------------------------------------------------------ #

    async def get_profile(self, app_id: str, entity_id: str) -> dict | None:
        """Get a profile by app + entity, returning raw fields (no merge)."""
        result = await self.session.execute(
            select(KnowledgeProfile).where(
                KnowledgeProfile.app_id == app_id,
                KnowledgeProfile.entity_id == entity_id,
            )
        )
        profile = result.scalar_one_or_none()
        return self._profile_to_dict(profile) if profile else None

    async def get_profile_by_id(self, profile_id: str) -> dict | None:
        """Get a profile by its primary key."""
        profile = await self.session.get(KnowledgeProfile, profile_id)
        return self._profile_to_dict(profile) if profile else None

    async def get_or_create_profile(
        self, app_id: str, entity_id: str, name: str,
    ) -> dict:
        """Get existing profile or create one with the given name."""
        result = await self.session.execute(
            select(KnowledgeProfile).where(
                KnowledgeProfile.app_id == app_id,
                KnowledgeProfile.entity_id == entity_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile:
            return self._profile_to_dict(profile)

        now = datetime.now(timezone.utc)
        profile = KnowledgeProfile(
            app_id=app_id, entity_id=entity_id, name=name,
            created_at=now, updated_at=now,
        )
        self.session.add(profile)
        await self.session.flush()
        return self._profile_to_dict(profile)

    async def update_profile(self, profile_id: str, **fields) -> dict:
        """Update explicit profile fields (identity + metadata_json)."""
        profile = await self.session.get(KnowledgeProfile, profile_id)
        if not profile:
            raise ValueError(f"Profile {profile_id!r} not found")

        allowed = {"name", "language", "framework", "description",
                    "test_framework", "metadata_json"}
        for key, value in fields.items():
            if key in allowed:
                if key == "metadata_json" and isinstance(value, dict):
                    value = json.dumps(value)
                setattr(profile, key, value)

        profile.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return self._profile_to_dict(profile)

    async def update_auto_detected(
        self, profile_id: str, auto_fields: dict,
    ) -> dict:
        """Replace auto_detected_json (workspace sync shadow fields)."""
        profile = await self.session.get(KnowledgeProfile, profile_id)
        if not profile:
            raise ValueError(f"Profile {profile_id!r} not found")

        profile.auto_detected_json = json.dumps(auto_fields)
        profile.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return self._profile_to_dict(profile)

    async def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile and its sources.

        Explicitly deletes sources first for SQLite compatibility
        (PRAGMA foreign_keys may not be enabled).
        """
        await self.session.execute(
            delete(KnowledgeSource).where(KnowledgeSource.profile_id == profile_id)
        )
        result = await self.session.execute(
            delete(KnowledgeProfile).where(KnowledgeProfile.id == profile_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def list_profiles(self, app_id: str) -> list[dict]:
        """List all profiles for an app."""
        result = await self.session.execute(
            select(KnowledgeProfile)
            .where(KnowledgeProfile.app_id == app_id)
            .order_by(KnowledgeProfile.name)
        )
        return [self._profile_to_dict(p) for p in result.scalars().all()]

    async def resolve_profile(self, app_id: str, entity_id: str) -> dict | None:
        """Resolve profile with manual > auto-detected merge.

        For each identity field, explicit column value wins if non-null/non-empty,
        else falls back to the same key in auto_detected_json.
        """
        result = await self.session.execute(
            select(KnowledgeProfile).where(
                KnowledgeProfile.app_id == app_id,
                KnowledgeProfile.entity_id == entity_id,
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        base = self._profile_to_dict(profile)

        # Apply manual > auto-detected merge on identity fields
        auto = base["auto_detected"]
        for field in _IDENTITY_FIELDS:
            if not base[field]:
                base[field] = auto.get(field)

        return base

    # ------------------------------------------------------------------ #
    # Sources                                                             #
    # ------------------------------------------------------------------ #

    async def list_sources(
        self, profile_id: str, *, enabled_only: bool = False,
    ) -> list[dict]:
        """List sources for a profile, ordered by order_index."""
        stmt = select(KnowledgeSource).where(
            KnowledgeSource.profile_id == profile_id,
        )
        if enabled_only:
            stmt = stmt.where(KnowledgeSource.enabled.is_(True))
        stmt = stmt.order_by(KnowledgeSource.order_index)
        result = await self.session.execute(stmt)
        return [self._source_to_dict(s) for s in result.scalars().all()]

    async def get_source(self, source_id: str) -> dict | None:
        """Get a source by ID."""
        source = await self.session.get(KnowledgeSource, source_id)
        return self._source_to_dict(source) if source else None

    async def create_source(
        self,
        profile_id: str,
        title: str,
        content: str,
        source_type: str = "document",
    ) -> dict:
        """Create a new knowledge source attached to a profile."""
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Invalid source_type {source_type!r}; must be one of {sorted(VALID_SOURCE_TYPES)}"
            )
        if len(content) > MAX_SOURCE_CONTENT_CHARS:
            raise ValueError(
                f"Source content exceeds {MAX_SOURCE_CONTENT_CHARS} character limit"
            )

        count_stmt = select(func.count(KnowledgeSource.id)).where(
            KnowledgeSource.profile_id == profile_id,
        )
        count_result = await self.session.execute(count_stmt)
        current_count = count_result.scalar() or 0
        if current_count >= MAX_SOURCES_PER_PROFILE:
            raise ValueError(
                f"Maximum sources per profile ({MAX_SOURCES_PER_PROFILE}) exceeded"
            )

        max_stmt = select(func.max(KnowledgeSource.order_index)).where(
            KnowledgeSource.profile_id == profile_id,
        )
        max_result = await self.session.execute(max_stmt)
        max_order = max_result.scalar()
        next_order = 0 if max_order is None else max_order + 1

        now = datetime.now(timezone.utc)
        source = KnowledgeSource(
            profile_id=profile_id,
            title=title,
            content=content,
            source_type=source_type,
            char_count=len(content),
            order_index=next_order,
            created_at=now,
            updated_at=now,
        )
        self.session.add(source)
        await self.session.flush()
        return self._source_to_dict(source)

    async def update_source(self, source_id: str, **fields) -> dict:
        """Update a source's mutable fields."""
        source = await self.session.get(KnowledgeSource, source_id)
        if not source:
            raise ValueError(f"Source {source_id!r} not found")

        allowed = {"title", "content", "source_type", "enabled"}
        for key, value in fields.items():
            if key in allowed:
                if key == "source_type" and value not in VALID_SOURCE_TYPES:
                    raise ValueError(f"Invalid source_type {value!r}")
                if key == "content" and len(value) > MAX_SOURCE_CONTENT_CHARS:
                    raise ValueError(
                        f"Source content exceeds {MAX_SOURCE_CONTENT_CHARS} character limit"
                    )
                setattr(source, key, value)

        if "content" in fields:
            source.char_count = len(fields["content"])

        source.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return self._source_to_dict(source)

    async def delete_source(self, source_id: str) -> bool:
        """Delete a source by ID."""
        result = await self.session.execute(
            delete(KnowledgeSource).where(KnowledgeSource.id == source_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def reorder_sources(
        self, profile_id: str, source_ids: list[str],
    ) -> None:
        """Reorder sources for a profile. All source IDs must be provided."""
        stmt = select(KnowledgeSource).where(
            KnowledgeSource.profile_id == profile_id,
        )
        result = await self.session.execute(stmt)
        all_sources = {s.id: s for s in result.scalars().all()}

        unknown = set(source_ids) - set(all_sources)
        if unknown:
            raise ValueError(f"Source IDs not found in profile: {unknown}")

        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate source IDs in reorder request")

        missing = set(all_sources) - set(source_ids)
        if missing:
            raise ValueError(f"Reorder must include all sources; missing: {missing}")

        for idx, sid in enumerate(source_ids):
            all_sources[sid].order_index = idx

        await self.session.flush()

    async def get_source_count(self, profile_id: str) -> int:
        """Get the number of sources for a profile."""
        stmt = select(func.count(KnowledgeSource.id)).where(
            KnowledgeSource.profile_id == profile_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_source_counts(self, profile_ids: list[str]) -> dict[str, int]:
        """Batch-fetch source counts for multiple profiles in a single query."""
        if not profile_ids:
            return {}
        stmt = (
            select(KnowledgeSource.profile_id, func.count(KnowledgeSource.id))
            .where(KnowledgeSource.profile_id.in_(profile_ids))
            .group_by(KnowledgeSource.profile_id)
        )
        result = await self.session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        return {pid: counts.get(pid, 0) for pid in profile_ids}

    async def get_total_char_count(self, profile_id: str) -> int:
        """Get total character count across all sources for a profile."""
        stmt = select(func.coalesce(func.sum(KnowledgeSource.char_count), 0)).where(
            KnowledgeSource.profile_id == profile_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ------------------------------------------------------------------ #
    # Combined resolution                                                 #
    # ------------------------------------------------------------------ #

    async def resolve(self, app_id: str, entity_id: str) -> dict | None:
        """Resolve a profile (manual > auto merge) with its enabled sources.

        Returns ``{"profile": {merged fields}, "metadata": {...}, "sources": [...]}``
        or ``None`` if no profile exists.
        """
        resolved = await self.resolve_profile(app_id, entity_id)
        if not resolved:
            return None

        sources = await self.list_sources(resolved["id"], enabled_only=True)
        return {
            "profile": {
                "id": resolved["id"],
                "app_id": resolved["app_id"],
                "entity_id": resolved["entity_id"],
                "name": resolved["name"],
                "language": resolved["language"],
                "framework": resolved["framework"],
                "description": resolved["description"],
                "test_framework": resolved["test_framework"],
                "created_at": resolved["created_at"],
                "updated_at": resolved["updated_at"],
            },
            "metadata": resolved["metadata"],
            "auto_detected": resolved["auto_detected"],
            "sources": sources,
        }

    # ------------------------------------------------------------------ #
    # Serialization helpers                                               #
    # ------------------------------------------------------------------ #

    def _profile_to_dict(self, profile: KnowledgeProfile) -> dict:
        metadata = {}
        if profile.metadata_json:
            try:
                metadata = json.loads(profile.metadata_json)
            except (json.JSONDecodeError, TypeError):
                pass

        auto_detected = {}
        if profile.auto_detected_json:
            try:
                auto_detected = json.loads(profile.auto_detected_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "id": profile.id,
            "app_id": profile.app_id,
            "entity_id": profile.entity_id,
            "name": profile.name,
            "language": profile.language,
            "framework": profile.framework,
            "description": profile.description,
            "test_framework": profile.test_framework,
            "metadata": metadata,
            "auto_detected": auto_detected,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }

    def _source_to_dict(self, source: KnowledgeSource) -> dict:
        return {
            "id": source.id,
            "profile_id": source.profile_id,
            "title": source.title,
            "content": source.content,
            "source_type": source.source_type,
            "char_count": source.char_count,
            "enabled": source.enabled,
            "order_index": source.order_index,
            "created_at": source.created_at.isoformat() if source.created_at else None,
            "updated_at": source.updated_at.isoformat() if source.updated_at else None,
        }
