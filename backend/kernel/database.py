"""Kernel database migrations — tables owned by the kernel itself.

Runs BEFORE app-specific migrations in init_db(). All statements use
CREATE TABLE IF NOT EXISTS for idempotency.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

KERNEL_MIGRATIONS: list[str] = [
    # --- Per-app settings ---
    "CREATE TABLE IF NOT EXISTS app_settings ("
    "  id TEXT PRIMARY KEY,"
    "  app_id TEXT NOT NULL,"
    "  key TEXT NOT NULL,"
    "  value TEXT NOT NULL DEFAULT '{}',"
    "  created_at TIMESTAMP NOT NULL,"
    "  updated_at TIMESTAMP NOT NULL,"
    "  UNIQUE(app_id, key)"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_app_settings_app_id ON app_settings (app_id)",
    # --- Per-app document collections ---
    "CREATE TABLE IF NOT EXISTS app_collections ("
    "  id TEXT PRIMARY KEY,"
    "  app_id TEXT NOT NULL,"
    "  name TEXT NOT NULL,"
    "  parent_id TEXT REFERENCES app_collections(id) ON DELETE CASCADE,"
    "  created_at TIMESTAMP NOT NULL,"
    "  updated_at TIMESTAMP NOT NULL,"
    "  UNIQUE(app_id, name, parent_id)"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_app_collections_app_id ON app_collections (app_id)",
    # --- Per-app documents ---
    "CREATE TABLE IF NOT EXISTS app_documents ("
    "  id TEXT PRIMARY KEY,"
    "  app_id TEXT NOT NULL,"
    "  collection_id TEXT REFERENCES app_collections(id) ON DELETE CASCADE,"
    "  name TEXT NOT NULL,"
    "  content_type TEXT NOT NULL DEFAULT 'application/json',"
    "  content TEXT NOT NULL DEFAULT '{}',"
    "  metadata_json TEXT,"
    "  created_at TIMESTAMP NOT NULL,"
    "  updated_at TIMESTAMP NOT NULL"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_app_documents_app_id ON app_documents (app_id)",
    "CREATE INDEX IF NOT EXISTS ix_app_documents_collection_id"
    " ON app_documents (collection_id)",
]


async def run_kernel_migrations(conn: AsyncConnection) -> None:
    """Apply kernel-owned table migrations."""
    for stmt in KERNEL_MIGRATIONS:
        try:
            await conn.execute(text(stmt))
            logger.debug("Kernel migration applied: %s", stmt[:60])
        except OperationalError:
            logger.debug("Kernel migration skipped (already applied): %s", stmt[:60])
