"""App registry — discovery, loading, and lifecycle management for installed apps."""

from kernel.registry.hooks import AppBase
from kernel.registry.manifest import AppManifest

__all__ = ["AppBase", "AppManifest"]
