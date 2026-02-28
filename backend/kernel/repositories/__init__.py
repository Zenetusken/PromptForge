"""Kernel repositories — data access for kernel-owned tables."""

from kernel.repositories.app_settings import AppSettingsRepository
from kernel.repositories.app_storage import AppStorageRepository

__all__ = ["AppSettingsRepository", "AppStorageRepository"]
