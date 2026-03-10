"""Repo Index Service — background indexing and semantic file retrieval.

Builds an embedding index of repository files on repo link, enabling
fast semantic retrieval during the explore phase. Replaces the 15-25 turn
agentic exploration loop with a deterministic vector search.

Usage::

    from app.services.repo_index_service import get_repo_index_service

    svc = get_repo_index_service()
    # Background: triggered on repo link
    await svc.build_index(token, "owner/repo", "main")
    # Foreground: during explore phase
    files = await svc.query_relevant_files("owner/repo", "main", "user prompt", top_k=20)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.repo_index import RepoFileIndex, RepoIndexMeta
from app.services.embedding_service import get_embedding_service
from app.services.github_service import (
    get_repo_tree,
    read_file_content,
)

logger = logging.getLogger(__name__)

# ── File classification ──────────────────────────────────────────────────

# Code files: worth reading for outlines (function/class signatures)
_CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".svelte", ".vue", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".kt", ".swift", ".scala", ".zig", ".lua", ".ex", ".exs",
    ".sh", ".bash", ".zsh",
})

# Doc files: embed path + first 100 chars
_DOC_EXTENSIONS = frozenset({".md", ".txt", ".rst", ".adoc"})

# Config/manifest files: embed path only
_CONFIG_EXTENSIONS = frozenset({
    ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg",
    ".env", ".env.example", ".env.local",
})

# Lock files and generated files: skip entirely
_SKIP_FILES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", "Cargo.lock",
    "go.sum", "composer.lock", "Gemfile.lock",
})

# Outline regex — matches function/class/interface definitions.
# Uses [ \t]* (not \s*) for indent capture to avoid matching across line
# boundaries (\s matches \n, which would cause off-by-one line numbers).
OUTLINE_PATTERNS = re.compile(
    r'^([ \t]*)'
    r'(def |async def |class |function |export function |export default function '
    r'|export class |export interface |export type |interface |type '
    r'|const .+ = \(|module\.exports|fn |pub fn |pub struct |pub enum |pub trait |impl )',
    re.MULTILINE,
)


@dataclass
class RankedFile:
    """A file ranked by semantic relevance to a query."""
    path: str
    score: float
    sha: str = ""
    size_bytes: int = 0
    outline: str = ""


@dataclass
class IndexStatus:
    """Status of a repo's embedding index."""
    status: str  # pending, building, ready, partial, failed, expired
    file_count: int = 0
    indexed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def is_ready(self) -> bool:
        return self.status in ("ready", "partial")

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now > exp


def _extract_outline(content: str, max_lines: int = 50) -> str:
    """Extract function/class signatures from file content.

    Reuses the same regex patterns as codebase_tools.py get_file_outline.
    Returns a condensed outline string.
    """
    all_lines = content.split("\n")
    outline_parts: list[str] = []

    for match in OUTLINE_PATTERNS.finditer(content):
        indent_len = len(match.group(1))
        # Include top-level (0) and class members (2–4 spaces); skip deep nesting
        if indent_len >= 8:
            continue
        line_no = content[: match.start()].count("\n") + 1
        if line_no <= len(all_lines):
            outline_parts.append(all_lines[line_no - 1].strip())
        if len(outline_parts) >= max_lines:
            break

    return "\n".join(outline_parts)


def _classify_file(path: str) -> str:
    """Classify a file as 'code', 'doc', 'config', or 'skip'."""
    filename = path.split("/")[-1]
    if filename in _SKIP_FILES:
        return "skip"
    # Check extension
    dot_pos = filename.rfind(".")
    if dot_pos >= 0:
        ext = filename[dot_pos:].lower()
        if ext in _CODE_EXTENSIONS:
            return "code"
        if ext in _DOC_EXTENSIONS:
            return "doc"
        if ext in _CONFIG_EXTENSIONS:
            return "config"
    # Files without extensions or unrecognized: treat as config (embed path only)
    return "config"


class RepoIndexService:
    """Manages repo file embedding indexes for semantic retrieval."""

    async def build_index(
        self,
        token: str,
        repo_full_name: str,
        branch: str,
    ) -> None:
        """Build the embedding index for a repository.

        Called as a background task on repo link. Fetches the file tree,
        reads outlines for code files, embeds everything, and persists
        to the database.

        Args:
            token: Decrypted GitHub access token.
            repo_full_name: Repository full name (owner/repo).
            branch: Branch to index.
        """
        start = time.monotonic()
        logger.info("Building repo index for %s@%s", repo_full_name, branch)

        async with async_session() as session:
            # Upsert meta record → building
            await self._upsert_meta(session, repo_full_name, branch, "building")
            await session.commit()

        try:
            # 1. Fetch file tree
            tree = await get_repo_tree(token, repo_full_name, branch)
            if not tree:
                async with async_session() as session:
                    await self._upsert_meta(
                        session, repo_full_name, branch, "failed",
                        error_message="Empty tree — repo may be empty or branch missing",
                    )
                    await session.commit()
                return

            # Cap to configured limit
            max_files = settings.REPO_INDEX_MAX_FILES
            if len(tree) > max_files:
                logger.warning(
                    "Repo %s@%s has %d files, capping index to %d",
                    repo_full_name, branch, len(tree), max_files,
                )
                tree = tree[:max_files]

            # 2. Classify files and read outlines for code files
            entries_to_index: list[dict] = []
            code_entries: list[dict] = []

            for entry in tree:
                file_type = _classify_file(entry["path"])
                if file_type == "skip":
                    continue
                entries_to_index.append({**entry, "type": file_type})
                if file_type == "code":
                    code_entries.append(entry)

            # 3. Read code file contents in parallel for outline extraction
            semaphore = asyncio.Semaphore(settings.EXPLORE_FILE_READ_CONCURRENCY)
            outlines: dict[str, str] = {}  # path → outline

            async def _read_and_extract(entry: dict) -> None:
                async with semaphore:
                    sha = entry.get("sha", "")
                    if not sha:
                        return
                    try:
                        content = await read_file_content(token, repo_full_name, sha)
                        if content:
                            outline = _extract_outline(content)
                            if outline:
                                outlines[entry["path"]] = outline
                    except Exception as e:
                        logger.debug("Outline read failed for %s: %s", entry["path"], e)

            # Read outlines concurrently
            tasks = [_read_and_extract(e) for e in code_entries]
            await asyncio.gather(*tasks, return_exceptions=True)

            # 4. Build embedding texts
            embedding_texts: list[str] = []
            embedding_entries: list[dict] = []

            for entry in entries_to_index:
                path = entry["path"]
                outline = outlines.get(path, "")
                file_type = entry["type"]

                if file_type == "code" and outline:
                    text = f"{path} | {outline}"
                elif file_type == "doc":
                    # We could read first 100 chars but that would require
                    # another GitHub read; just embed the path for docs
                    text = path
                else:
                    text = path

                embedding_texts.append(text)
                embedding_entries.append({
                    "path": path,
                    "sha": entry.get("sha", ""),
                    "size_bytes": entry.get("size_bytes", 0),
                    "outline": outline,
                })

            # 5. Batch embed
            embed_svc = get_embedding_service(settings.EMBEDDING_MODEL)
            if not await embed_svc.ensure_loaded():
                logger.error("Embedding model failed to load — storing without embeddings")
                async with async_session() as session:
                    await self._upsert_meta(
                        session, repo_full_name, branch, "failed",
                        error_message="Embedding model unavailable",
                    )
                    await session.commit()
                return

            vectors = await embed_svc.embed_texts(embedding_texts)
            if vectors.size == 0:
                async with async_session() as session:
                    await self._upsert_meta(
                        session, repo_full_name, branch, "failed",
                        error_message="Embedding produced empty vectors",
                    )
                    await session.commit()
                return

            # 6. Persist to database
            async with async_session() as session:
                # Clear existing entries for this repo/branch
                await session.execute(
                    delete(RepoFileIndex).where(
                        RepoFileIndex.repo_full_name == repo_full_name,
                        RepoFileIndex.branch == branch,
                    )
                )

                # Bulk insert new entries
                now = datetime.now(timezone.utc)
                for i, entry in enumerate(embedding_entries):
                    record = RepoFileIndex(
                        repo_full_name=repo_full_name,
                        branch=branch,
                        file_path=entry["path"],
                        file_sha=entry["sha"],
                        file_size_bytes=entry["size_bytes"],
                        outline=entry["outline"] or None,
                        embedding=vectors[i].tobytes(),
                        indexed_at=now,
                    )
                    session.add(record)

                # Update meta
                status = "ready" if len(outlines) > 0 else "partial"
                await self._upsert_meta(
                    session, repo_full_name, branch, status,
                    file_count=len(embedding_entries),
                )
                await session.commit()

            elapsed = time.monotonic() - start
            logger.info(
                "Repo index built for %s@%s: %d files indexed (%d outlines) in %.1fs",
                repo_full_name, branch, len(embedding_entries), len(outlines), elapsed,
            )

        except Exception as e:
            logger.error("Failed to build index for %s@%s: %s", repo_full_name, branch, e)
            try:
                async with async_session() as session:
                    await self._upsert_meta(
                        session, repo_full_name, branch, "failed",
                        error_message=str(e)[:500],
                    )
                    await session.commit()
            except Exception:
                pass

    async def query_relevant_files(
        self,
        repo_full_name: str,
        branch: str,
        prompt: str,
        top_k: int = 20,
    ) -> list[RankedFile]:
        """Query the index for files most relevant to a prompt.

        Args:
            repo_full_name: Repository full name.
            branch: Branch that was indexed.
            prompt: User's prompt text to match against.
            top_k: Number of results to return.

        Returns:
            List of RankedFile sorted by descending relevance score.
        """
        embed_svc = get_embedding_service()

        # Load all embeddings for this repo/branch
        async with async_session() as session:
            result = await session.execute(
                select(RepoFileIndex).where(
                    RepoFileIndex.repo_full_name == repo_full_name,
                    RepoFileIndex.branch == branch,
                )
            )
            records = result.scalars().all()

        if not records:
            logger.warning("No index entries for %s@%s", repo_full_name, branch)
            return []

        # Build numpy array from stored embeddings
        paths: list[str] = []
        shas: list[str] = []
        sizes: list[int] = []
        outlines: list[str] = []
        vecs: list[np.ndarray] = []

        for rec in records:
            paths.append(rec.file_path)
            shas.append(rec.file_sha or "")
            sizes.append(rec.file_size_bytes or 0)
            outlines.append(rec.outline or "")
            vecs.append(np.frombuffer(rec.embedding, dtype=np.float32))

        index_vecs = np.stack(vecs)  # (N, 384)

        # Embed the prompt
        query_vec = await embed_svc.embed_single(prompt)
        if query_vec.size == 0:
            return []

        # Cosine search
        ranked = embed_svc.cosine_search(query_vec, index_vecs, top_k=top_k)

        return [
            RankedFile(
                path=paths[idx],
                score=float(score),
                sha=shas[idx],
                size_bytes=sizes[idx],
                outline=outlines[idx],
            )
            for idx, score in ranked
        ]

    async def get_index_status(
        self,
        repo_full_name: str,
        branch: str,
    ) -> IndexStatus:
        """Get the current status of a repo's embedding index."""
        async with async_session() as session:
            result = await session.execute(
                select(RepoIndexMeta).where(
                    RepoIndexMeta.repo_full_name == repo_full_name,
                    RepoIndexMeta.branch == branch,
                )
            )
            meta = result.scalar_one_or_none()

        if meta is None:
            return IndexStatus(status="none")

        status = IndexStatus(
            status=meta.status,
            file_count=meta.file_count or 0,
            indexed_at=meta.indexed_at,
            expires_at=meta.expires_at,
            error_message=meta.error_message,
        )

        # Auto-mark expired
        if status.is_expired and status.status in ("ready", "partial"):
            status.status = "expired"

        return status

    async def invalidate_index(
        self,
        repo_full_name: str,
        branch: str,
    ) -> None:
        """Delete all index entries and meta for a repo/branch."""
        async with async_session() as session:
            await session.execute(
                delete(RepoFileIndex).where(
                    RepoFileIndex.repo_full_name == repo_full_name,
                    RepoFileIndex.branch == branch,
                )
            )
            await session.execute(
                delete(RepoIndexMeta).where(
                    RepoIndexMeta.repo_full_name == repo_full_name,
                    RepoIndexMeta.branch == branch,
                )
            )
            await session.commit()
        logger.info("Invalidated index for %s@%s", repo_full_name, branch)

    async def _upsert_meta(
        self,
        session: AsyncSession,
        repo_full_name: str,
        branch: str,
        status: str,
        file_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Create or update the index metadata record."""
        result = await session.execute(
            select(RepoIndexMeta).where(
                RepoIndexMeta.repo_full_name == repo_full_name,
                RepoIndexMeta.branch == branch,
            )
        )
        meta = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        ttl_hours = settings.REPO_INDEX_TTL_HOURS
        expires_at = now + timedelta(hours=ttl_hours) if status in ("ready", "partial") else None

        if meta is None:
            meta = RepoIndexMeta(
                repo_full_name=repo_full_name,
                branch=branch,
                status=status,
                file_count=file_count,
                indexed_at=now if status in ("ready", "partial") else None,
                expires_at=expires_at,
                error_message=error_message,
            )
            session.add(meta)
        else:
            meta.status = status
            if file_count is not None:
                meta.file_count = file_count
            if status in ("ready", "partial"):
                meta.indexed_at = now
                meta.expires_at = expires_at
            meta.error_message = error_message


# ── Module-level singleton ──────────────────────────────────────────────────

_instance: Optional[RepoIndexService] = None


def get_repo_index_service() -> RepoIndexService:
    """Get or create the repo index service singleton."""
    global _instance
    if _instance is None:
        _instance = RepoIndexService()
    return _instance
