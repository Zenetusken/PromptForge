"""Shared context resolution — kernel Knowledge Base → per-request override.

Single entry point for resolving project context, used by both REST endpoints
and MCP tools. Eliminates duplication between routers/optimize.py and mcp_server.py.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.promptforge.repositories.project import ProjectRepository
from apps.promptforge.schemas.context import (
    CodebaseContext,
    codebase_context_from_dict,
    codebase_context_from_kernel,
    merge_contexts,
)


async def resolve_project_context(
    db: AsyncSession,
    project_name: str | None,
    explicit_dict: dict[str, Any] | None = None,
) -> CodebaseContext | None:
    """Resolve project context: kernel Knowledge Base → per-request override.

    1. If project_name is given, try the kernel Knowledge Base first
       (KnowledgeRepository.resolve handles manual > auto-detected merge + sources).
    2. If no kernel profile exists, fall back to legacy three-layer resolution
       (workspace → manual profile → legacy sources).
    3. Merge the result with any explicit per-request override.

    Parameters
    ----------
    db:
        Active database session.
    project_name:
        PromptForge project name (triggers project-level resolution).
    explicit_dict:
        Optional per-request codebase_context dict from the API caller.

    Returns
    -------
    Resolved CodebaseContext or None if no context is available.
    """
    explicit = codebase_context_from_dict(explicit_dict)

    kernel_ctx = None
    if project_name:
        # Try kernel Knowledge Base first
        project = await ProjectRepository(db).get_by_name(project_name)
        if project:
            from kernel.repositories.knowledge import KnowledgeRepository

            knowledge_repo = KnowledgeRepository(db)
            resolved_knowledge = await knowledge_repo.resolve("promptforge", project.id)
            if resolved_knowledge:
                kernel_ctx = codebase_context_from_kernel(resolved_knowledge)

        # Fallback to legacy resolution if no kernel profile
        if kernel_ctx is None:
            from apps.promptforge.repositories.workspace import WorkspaceRepository
            from apps.promptforge.schemas.context import SourceDocument

            workspace = await WorkspaceRepository(db).get_workspace_context_by_project_name(
                project_name,
            )
            manual = await ProjectRepository(db).get_context_by_name(project_name)
            kernel_ctx = merge_contexts(workspace, manual)

            # Legacy source attachment
            from apps.promptforge.repositories.source import SourceRepository

            sources = await SourceRepository(db).get_enabled_by_project_name(project_name)
            if sources:
                source_docs = [
                    SourceDocument(
                        title=s.title, content=s.content, source_type=s.source_type,
                    )
                    for s in sources
                ]
                if kernel_ctx is not None:
                    kernel_ctx.sources = source_docs
                else:
                    kernel_ctx = CodebaseContext(sources=source_docs)

    return merge_contexts(kernel_ctx, explicit)
