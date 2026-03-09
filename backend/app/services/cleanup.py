"""Background cleanup service.

Runs periodic sweeps to remove stale data: expired tokens, old linked repos,
and permanently purge soft-deleted optimizations after a retention period.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.database import async_session
from app.models.auth import RefreshToken
from app.models.github import GitHubToken, LinkedRepo
from app.models.optimization import Optimization

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 3600  # 1 hour


async def sweep_expired_tokens() -> None:
    """Delete expired or revoked-and-old RefreshToken rows."""
    now = datetime.now(timezone.utc)
    old_revoked_cutoff = now - timedelta(days=30)

    async with async_session() as session:
        await session.execute(
            delete(RefreshToken).where(
                (RefreshToken.expires_at < now)
                | (
                    (RefreshToken.revoked.is_(True))
                    & (RefreshToken.created_at < old_revoked_cutoff)
                )
            )
        )
        await session.commit()
    logger.debug("sweep_expired_tokens: completed")


async def sweep_expired_github_tokens() -> None:
    """Delete GitHubToken rows that expired more than 24 hours ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    async with async_session() as session:
        await session.execute(
            delete(GitHubToken).where(GitHubToken.expires_at < cutoff)
        )
        await session.commit()
    logger.debug("sweep_expired_github_tokens: completed")


async def sweep_old_linked_repos() -> None:
    """Delete LinkedRepo rows that were linked more than 30 days ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    async with async_session() as session:
        await session.execute(
            delete(LinkedRepo).where(LinkedRepo.linked_at < cutoff)
        )
        await session.commit()
    logger.debug("sweep_old_linked_repos: completed")


async def sweep_soft_deleted_optimizations() -> None:
    """Permanently delete Optimization rows soft-deleted more than 7 days ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    async with async_session() as session:
        await session.execute(
            delete(Optimization).where(
                Optimization.deleted_at.isnot(None),
                Optimization.deleted_at < cutoff,
            )
        )
        await session.commit()
    logger.debug("sweep_soft_deleted_optimizations: completed")


async def run_cleanup_cycle() -> None:
    """Run all 4 sweeps with isolated error handling.

    A failure in one sweep does not prevent the others from running.
    """
    sweeps = [
        ("expired_tokens", sweep_expired_tokens),
        ("expired_github_tokens", sweep_expired_github_tokens),
        ("old_linked_repos", sweep_old_linked_repos),
        ("soft_deleted_optimizations", sweep_soft_deleted_optimizations),
    ]
    for name, sweep_fn in sweeps:
        try:
            await sweep_fn()
        except Exception:
            logger.warning("Cleanup sweep '%s' failed", name, exc_info=True)


async def cleanup_loop() -> None:
    """Infinite loop: sleep then run a cleanup cycle. Handles CancelledError gracefully."""
    logger.info("Cleanup loop started (interval=%ds)", CLEANUP_INTERVAL_SECONDS)
    try:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            await run_cleanup_cycle()
    except asyncio.CancelledError:
        logger.info("Cleanup loop cancelled")
        raise
