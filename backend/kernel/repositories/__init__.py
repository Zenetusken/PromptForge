"""Kernel repositories — data access for kernel-owned tables."""

from kernel.repositories.app_settings import AppSettingsRepository
from kernel.repositories.app_storage import AppStorageRepository
from kernel.repositories.knowledge import KnowledgeRepository

__all__ = ["AppSettingsRepository", "AppStorageRepository", "KnowledgeRepository"]
