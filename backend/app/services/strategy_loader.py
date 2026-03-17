"""Strategy file discovery, loading, and frontmatter parsing.

Strategy files are Markdown in prompts/strategies/ with optional YAML frontmatter:

    ---
    tagline: reasoning
    description: Guide the AI through explicit reasoning steps.
    ---

    # Chain of Thought Strategy
    ...

The frontmatter is stripped before injection into optimizer/refiner templates.
The system is fully adaptive — adding/removing .md files is auto-detected.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Regex to extract YAML frontmatter between --- delimiters
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML-like frontmatter from markdown content.

    Returns (metadata_dict, body_without_frontmatter).
    If no frontmatter, returns ({}, original_content).
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    body = content[match.end():]
    return meta, body


class StrategyLoader:
    """Discovers and loads strategy files from the strategies directory.

    Fully adaptive: strategies are discovered from disk on each call.
    No hardcoded list — adding/removing .md files changes available strategies.
    """

    def __init__(self, strategies_dir: Path) -> None:
        self.strategies_dir = strategies_dir

    def list_strategies(self) -> list[str]:
        """Return sorted list of available strategy names (without .md extension)."""
        if not self.strategies_dir.exists():
            return []
        return sorted(p.stem for p in self.strategies_dir.glob("*.md"))

    def load(self, name: str) -> str:
        """Load a strategy file by name, stripping frontmatter.

        Returns the body content (without YAML frontmatter) for injection
        into optimizer/refiner templates.
        """
        path = self.strategies_dir / f"{name}.md"
        if not path.exists():
            available = self.list_strategies()
            raise FileNotFoundError(
                "Strategy '%s' not found at %s. Available strategies: %s"
                % (name, path, ", ".join(available) if available else "none")
            )
        content = path.read_text(encoding="utf-8")
        _, body = _parse_frontmatter(content)
        logger.debug("Loaded strategy %s (%d chars)", name, len(body))
        return body

    def load_metadata(self, name: str) -> dict[str, Any]:
        """Load frontmatter metadata for a strategy.

        Returns dict with keys: name, tagline, description.
        Falls back to extracting description from first content line if no frontmatter.
        """
        path = self.strategies_dir / f"{name}.md"
        if not path.exists():
            return {"name": name, "tagline": "", "description": ""}

        content = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)

        # Frontmatter values
        tagline = meta.get("tagline", "")
        description = meta.get("description", "")

        # Fallback: extract description from first non-heading, non-empty line
        if not description:
            for line in body.strip().splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    description = stripped
                    break

        return {
            "name": name,
            "tagline": tagline,
            "description": description,
        }

    def list_with_metadata(self) -> list[dict[str, Any]]:
        """Return all strategies with their frontmatter metadata."""
        return [self.load_metadata(name) for name in self.list_strategies()]

    def format_available(self) -> str:
        """Format available strategies as a bullet list for the analyzer prompt.

        Includes taglines when available for richer context.
        """
        results = []
        for meta in self.list_with_metadata():
            name = meta["name"]
            tagline = meta.get("tagline", "")
            if tagline:
                results.append(f"- {name} ({tagline})")
            else:
                results.append(f"- {name}")
        return "\n".join(results) if results else "No strategies available."

    def validate(self) -> None:
        """Verify strategies directory is non-empty. Raises RuntimeError if empty."""
        strategies = self.list_strategies()
        if not strategies:
            raise RuntimeError(
                f"No strategy files found in {self.strategies_dir}. "
                f"At least one .md file is required."
            )
        logger.info(
            "Strategy validation passed: %d strategies available", len(strategies),
        )
