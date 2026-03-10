"""Shared patterns and constants for codebase exploration.

Consolidates regex patterns and anchor file lists used across:
- ``codebase_tools.py``  (MCP agentic tools)
- ``repo_index_service.py`` (background embedding indexer)
- ``codebase_explorer.py`` (semantic explore phase)

Single source of truth — all consumers import from here.
"""

import re

# ── Outline regex ────────────────────────────────────────────────────────
#
# Matches function, class, interface, and type definitions across
# Python, JavaScript/TypeScript, Go, Rust, and other common languages.
#
# Uses [ \t]* (NOT \s*) for indent capture. In MULTILINE mode, \s
# matches \n which would cause the regex to match across line boundaries
# and produce off-by-one line numbers.
OUTLINE_PATTERNS = re.compile(
    r'^([ \t]*)'
    r'(def |async def |class |function |export function |export default function '
    r'|export class |export interface |export type |interface |type '
    r'|const .+ = \(|module\.exports|fn |pub fn |pub struct |pub enum |pub trait |impl )',
    re.MULTILINE,
)

# ── Anchor filenames ─────────────────────────────────────────────────────
#
# Deterministic high-value files that should always be included in
# codebase exploration, regardless of semantic relevance score.
# Used by both the explore phase (for file selection) and the
# repo summary tool (for orientation output).
ANCHOR_FILENAMES = frozenset({
    "README.md", "README.rst", "README",
    "package.json", "pyproject.toml", "Cargo.toml",
    "setup.py", "go.mod", "requirements.txt",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", "CLAUDE.md",
    "openapi.yaml", "openapi.json",
    "architecture.md", "ARCHITECTURE.md",
})
