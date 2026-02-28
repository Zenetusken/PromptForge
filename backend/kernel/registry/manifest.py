"""AppManifest — Pydantic model for app manifest.json files."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RouterDef(BaseModel):
    """A router to mount on the FastAPI app."""

    module: str = Field(min_length=1)
    prefix: str
    tags: list[str] = Field(default_factory=list)


class BackendManifest(BaseModel):
    """Backend-specific manifest entries."""

    routers: list[RouterDef] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    mcp_tools: str | None = None
    migrations_module: str | None = None


class WindowDef(BaseModel):
    """A window definition for the frontend shell."""

    id: str
    title: str
    icon: str = ""
    component: str = ""
    persistent: bool = False


class FileTypeDef(BaseModel):
    """A file type registration."""

    extension: str
    label: str
    icon: str = ""
    color: str = ""
    artifact_kind: str = ""


class CommandDef(BaseModel):
    """A command palette command."""

    id: str
    label: str
    category: str = ""
    shortcut: str = ""
    icon: str = ""


class ProcessTypeDef(BaseModel):
    """A process type for the process scheduler."""

    id: str
    label: str
    icon: str = ""
    stages: list[str] = Field(default_factory=list)


class StartMenuDef(BaseModel):
    """Start menu configuration."""

    pinned: list[str] = Field(default_factory=list)
    section: str = ""


class DesktopIconDef(BaseModel):
    """Desktop icon definition."""

    id: str
    label: str
    icon: str = ""
    action: str = ""
    color: str = ""
    type: str = ""


class SettingsDef(BaseModel):
    """App settings schema."""

    schema_: dict = Field(default_factory=dict, alias="schema")
    component: str = ""


class FrontendManifest(BaseModel):
    """Frontend-specific manifest entries."""

    windows: list[WindowDef] = Field(default_factory=list)
    file_types: list[FileTypeDef] = Field(default_factory=list)
    commands: list[CommandDef] = Field(default_factory=list)
    bus_events: list[str] = Field(default_factory=list)
    process_types: list[ProcessTypeDef] = Field(default_factory=list)
    start_menu: StartMenuDef | None = None
    desktop_icons: list[DesktopIconDef] = Field(default_factory=list)
    settings: SettingsDef | None = None


class AppManifest(BaseModel):
    """Complete app manifest parsed from manifest.json."""

    id: str = Field(min_length=1)
    version: str = "0.1.0"
    name: str = ""
    icon: str = ""
    accent_color: str = ""
    python_module: str = Field(min_length=1)
    entry_point: str = Field(min_length=1)
    requires_services: list[str] = Field(default_factory=list)

    backend: BackendManifest = Field(default_factory=BackendManifest)
    frontend: FrontendManifest = Field(default_factory=FrontendManifest)
