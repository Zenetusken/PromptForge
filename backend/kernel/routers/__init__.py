"""Kernel routers — system-level API endpoints.

All kernel routers are aggregated here for a single include in main.py.
"""

from fastapi import APIRouter

from kernel.routers.apps import router as apps_router
from kernel.routers.settings import router as settings_router
from kernel.routers.storage import router as storage_router

kernel_router = APIRouter()
kernel_router.include_router(apps_router)
kernel_router.include_router(settings_router)
kernel_router.include_router(storage_router)
