"""Strategy template CRUD — list, read, and update strategy .md files."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import PROMPTS_DIR

router = APIRouter(prefix="/api", tags=["strategies"])

_strategies_dir = PROMPTS_DIR / "strategies"


class StrategyDetail(BaseModel):
    name: str
    content: str


class StrategyUpdate(BaseModel):
    content: str = Field(..., min_length=10, description="Markdown content")


@router.get("/strategies")
async def list_strategies() -> list[dict]:
    """List all available strategies with name and first-line description."""
    results = []
    if not _strategies_dir.is_dir():
        return results
    for path in sorted(_strategies_dir.glob("*.md")):
        name = path.stem
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        # Extract description: first non-empty, non-heading line
        description = ""
        for line in lines[1:]:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped
                break
        results.append({"name": name, "description": description})
    return results


@router.get("/strategies/{name}")
async def get_strategy(name: str) -> StrategyDetail:
    """Read the full content of a strategy .md file."""
    path = _strategies_dir / f"{name}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    content = path.read_text(encoding="utf-8")
    return StrategyDetail(name=name, content=content)


@router.put("/strategies/{name}")
async def update_strategy(name: str, body: StrategyUpdate) -> StrategyDetail:
    """Update a strategy .md file on disk. Hot-reloads on next pipeline call."""
    path = _strategies_dir / f"{name}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    path.write_text(body.content, encoding="utf-8")
    return StrategyDetail(name=name, content=body.content)
