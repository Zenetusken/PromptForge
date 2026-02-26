"""Deterministic codebase context extraction from repository data.

No LLM calls — fast and predictable. Analyzes marker files (package.json,
pyproject.toml, etc.) to build a CodebaseContext with language, framework,
conventions, and patterns.
"""

import json
import logging
import re

from app.schemas.context import CodebaseContext

logger = logging.getLogger(__name__)

# Marker files that identify project type
_MARKER_FILES = {
    "package.json": "javascript",
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
    "Package.swift": "swift",
    "pubspec.yaml": "dart",
}

# Framework detection from dependencies
_JS_FRAMEWORKS = {
    # More specific metapackage names first (checked in order)
    "@sveltejs/kit": "SvelteKit",
    "next": "Next.js",
    "nuxt": "Nuxt",
    "@angular/core": "Angular",
    "remix": "Remix",
    "astro": "Astro",
    # Base packages after their meta-frameworks
    "react": "React",
    "react-dom": "React",
    "svelte": "Svelte",
    "vue": "Vue",
    "angular": "Angular",
    "express": "Express",
    "fastify": "Fastify",
    "hono": "Hono",
    "solid-js": "SolidJS",
}

_PYTHON_FRAMEWORKS = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "aiohttp": "aiohttp",
    "sanic": "Sanic",
    "litestar": "Litestar",
    "streamlit": "Streamlit",
}

_JS_TEST_FRAMEWORKS = {
    "vitest": "Vitest",
    "jest": "Jest",
    "mocha": "Mocha",
    "cypress": "Cypress",
    "playwright": "Playwright",
    "@playwright/test": "Playwright",
    "@testing-library/react": "React Testing Library",
    "@testing-library/svelte": "Svelte Testing Library",
}

_PYTHON_TEST_FRAMEWORKS = {
    "pytest": "pytest",
    "unittest": "unittest",
    "nose2": "nose2",
    "hypothesis": "Hypothesis",
}

# Linter config files → convention strings
_LINTER_CONFIGS = {
    ".eslintrc": "ESLint configured",
    ".eslintrc.js": "ESLint configured",
    ".eslintrc.json": "ESLint configured",
    "eslint.config.js": "ESLint (flat config)",
    "eslint.config.mjs": "ESLint (flat config)",
    ".prettierrc": "Prettier configured",
    ".prettierrc.json": "Prettier configured",
    "prettier.config.js": "Prettier configured",
    "ruff.toml": "Ruff linter configured",
    "pyproject.toml:ruff": "Ruff linter configured",
    ".flake8": "Flake8 configured",
    ".pylintrc": "Pylint configured",
    "biome.json": "Biome configured",
    "biome.jsonc": "Biome configured",
    ".editorconfig": "EditorConfig defined",
    "tsconfig.json": "TypeScript strict mode",
    ".stylelintrc": "Stylelint configured",
}

# Directory patterns → architectural pattern strings
_DIR_PATTERNS = {
    "src/": "src/ source directory",
    "lib/": "lib/ shared library",
    "components/": "Component-based architecture",
    "api/": "API layer",
    "routes/": "Route-based organization",
    "pages/": "Pages-based routing",
    "models/": "Models layer (data access)",
    "services/": "Service layer pattern",
    "repositories/": "Repository pattern",
    "stores/": "State management stores",
    "utils/": "Utility modules",
    "hooks/": "Custom hooks",
    "middleware/": "Middleware layer",
    "tests/": "Dedicated test directory",
    "test/": "Dedicated test directory",
    "__tests__/": "Co-located test directory",
    "schemas/": "Schema-driven validation",
    "providers/": "Provider pattern",
}


def extract_context_from_repo(
    *,
    repo_metadata: dict | None = None,
    file_tree: list[str],
    file_contents: dict[str, str] | None = None,
) -> CodebaseContext:
    """Extract CodebaseContext from repository data.

    Args:
        repo_metadata: GitHub API repo response (language, description, etc.)
        file_tree: List of file paths in the repo
        file_contents: Dict of filename → content for marker files
    """
    file_contents = file_contents or {}
    repo_metadata = repo_metadata or {}

    language = _detect_language(repo_metadata, file_tree, file_contents)
    framework, framework_version = _detect_framework(language, file_contents)
    test_framework = _detect_test_framework(language, file_contents)
    conventions = _detect_conventions(file_tree, file_contents)
    patterns = _detect_patterns(file_tree)
    test_patterns = _detect_test_patterns(file_tree)

    # Build description from repo metadata (≤500 chars)
    description = repo_metadata.get("description", "")
    if description and len(description) > 500:
        description = description[:497] + "..."

    # Format framework string with version
    framework_str = None
    if framework:
        framework_str = f"{framework} {framework_version}" if framework_version else framework

    return CodebaseContext(
        language=language,
        framework=framework_str,
        description=description or None,
        conventions=conventions,
        patterns=patterns,
        test_framework=test_framework,
        test_patterns=test_patterns,
    )


def extract_context_from_workspace_info(workspace_info: dict) -> CodebaseContext:
    """Extract CodebaseContext from Claude Code sync_workspace payload.

    The workspace_info dict may contain: repo_url, git_branch, file_tree,
    dependencies, and optionally a pre-analyzed context dict.
    """
    file_tree = workspace_info.get("file_tree", [])
    deps = workspace_info.get("dependencies", {})

    # Build synthetic file contents for dependency detection
    file_contents: dict[str, str] = {}
    if deps:
        # Mimic package.json structure for JS detection
        if any(k in deps for k in _JS_FRAMEWORKS):
            file_contents["package.json"] = json.dumps({"dependencies": deps})
        # Mimic pyproject.toml deps for Python detection
        elif any(k in deps for k in _PYTHON_FRAMEWORKS):
            file_contents["pyproject.toml"] = _build_toml_deps(deps)

    return extract_context_from_repo(
        file_tree=file_tree,
        file_contents=file_contents,
    )


def _detect_language(
    repo_metadata: dict, file_tree: list[str], file_contents: dict[str, str],
) -> str | None:
    """Detect primary language from GitHub API field or marker files."""
    # GitHub API language field is the primary signal
    gh_lang = repo_metadata.get("language")
    if gh_lang:
        return gh_lang

    # Fallback: check marker files
    for marker, lang in _MARKER_FILES.items():
        if marker in file_contents or any(f.endswith(marker) for f in file_tree):
            return lang

    # Last resort: file extension frequency
    ext_counts: dict[str, int] = {}
    ext_lang_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".go": "Go", ".rs": "Rust", ".java": "Java", ".rb": "Ruby",
        ".php": "PHP", ".swift": "Swift", ".dart": "Dart",
    }
    for path in file_tree:
        for ext, lang in ext_lang_map.items():
            if path.endswith(ext):
                ext_counts[lang] = ext_counts.get(lang, 0) + 1
    if ext_counts:
        return max(ext_counts, key=ext_counts.get)

    return None


def _detect_framework(
    language: str | None, file_contents: dict[str, str],
) -> tuple[str | None, str | None]:
    """Detect framework and version from dependency files."""
    if not language:
        return None, None

    lang_lower = language.lower()

    # JavaScript / TypeScript
    if lang_lower in ("javascript", "typescript"):
        pkg_json = file_contents.get("package.json")
        if pkg_json:
            return _parse_js_framework(pkg_json)

    # Python
    if lang_lower == "python":
        toml = file_contents.get("pyproject.toml")
        if toml:
            return _parse_python_framework(toml)
        reqs = file_contents.get("requirements.txt")
        if reqs:
            return _parse_requirements_framework(reqs)

    return None, None


def _parse_js_framework(pkg_json_str: str) -> tuple[str | None, str | None]:
    """Parse package.json for framework detection."""
    try:
        pkg = json.loads(pkg_json_str)
    except json.JSONDecodeError:
        return None, None

    all_deps = {}
    for key in ("dependencies", "devDependencies"):
        all_deps.update(pkg.get(key, {}))

    for dep_name, framework_name in _JS_FRAMEWORKS.items():
        if dep_name in all_deps:
            version = all_deps[dep_name].lstrip("^~>=<")
            return framework_name, version if version else None

    return None, None


def _parse_python_framework(toml_str: str) -> tuple[str | None, str | None]:
    """Parse pyproject.toml for framework detection (basic regex, no toml lib)."""
    # Look for [project.dependencies] or dependencies = [...]
    deps_section = re.search(
        r'\[project\]\s*.*?dependencies\s*=\s*\[(.*?)\]', toml_str, re.DOTALL,
    )
    if not deps_section:
        deps_section = re.search(r'dependencies\s*=\s*\[(.*?)\]', toml_str, re.DOTALL)
    if not deps_section:
        return None, None

    deps_text = deps_section.group(1)
    for dep_name, framework_name in _PYTHON_FRAMEWORKS.items():
        pattern = rf'["\']({dep_name}[^"\']*)["\']'
        match = re.search(pattern, deps_text, re.IGNORECASE)
        if match:
            dep_spec = match.group(1)
            version_match = re.search(r'[><=~!]+(.+)', dep_spec)
            version = version_match.group(1).strip() if version_match else None
            return framework_name, version

    return None, None


def _parse_requirements_framework(reqs_str: str) -> tuple[str | None, str | None]:
    """Parse requirements.txt for framework detection."""
    for line in reqs_str.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for dep_name, framework_name in _PYTHON_FRAMEWORKS.items():
            if line.lower().startswith(dep_name):
                version_match = re.search(r'[><=~!]+(.+)', line)
                version = version_match.group(1).strip() if version_match else None
                return framework_name, version

    return None, None


def _detect_test_framework(
    language: str | None, file_contents: dict[str, str],
) -> str | None:
    """Detect test framework from dependencies."""
    if not language:
        return None

    lang_lower = language.lower()

    if lang_lower in ("javascript", "typescript"):
        pkg_json = file_contents.get("package.json")
        if pkg_json:
            try:
                pkg = json.loads(pkg_json)
                dev_deps = pkg.get("devDependencies", {})
                all_deps = {**pkg.get("dependencies", {}), **dev_deps}
                for dep_name, fw_name in _JS_TEST_FRAMEWORKS.items():
                    if dep_name in all_deps:
                        return fw_name
            except json.JSONDecodeError:
                pass

    if lang_lower == "python":
        toml = file_contents.get("pyproject.toml", "")
        reqs = file_contents.get("requirements.txt", "")
        combined = toml + reqs
        for dep_name, fw_name in _PYTHON_TEST_FRAMEWORKS.items():
            if dep_name in combined.lower():
                return fw_name

    return None


def _detect_conventions(
    file_tree: list[str], file_contents: dict[str, str],
) -> list[str]:
    """Detect code conventions from linter configs and project files."""
    conventions: list[str] = []
    seen = set()

    for config_file, convention_str in _LINTER_CONFIGS.items():
        if ":" in config_file:
            # Check for subsection (e.g., "pyproject.toml:ruff")
            filename, section = config_file.split(":", 1)
            content = file_contents.get(filename, "")
            if f"[tool.{section}]" in content or f"[{section}]" in content:
                if convention_str not in seen:
                    conventions.append(convention_str)
                    seen.add(convention_str)
        else:
            if config_file in file_contents or any(
                f.endswith(config_file) or f == config_file for f in file_tree
            ):
                if convention_str not in seen:
                    conventions.append(convention_str)
                    seen.add(convention_str)

    return conventions


def _detect_patterns(file_tree: list[str]) -> list[str]:
    """Detect architectural patterns from directory structure."""
    patterns: list[str] = []
    seen = set()

    for dir_pattern, pattern_str in _DIR_PATTERNS.items():
        for path in file_tree:
            if dir_pattern in path and pattern_str not in seen:
                patterns.append(pattern_str)
                seen.add(pattern_str)
                break

    return patterns


def _detect_test_patterns(file_tree: list[str]) -> list[str]:
    """Detect test patterns from file organization."""
    patterns: list[str] = []

    # Check for common test directory structures
    has_tests_dir = any("/tests/" in f or f.startswith("tests/") for f in file_tree)
    has_test_dir = any("/test/" in f or f.startswith("test/") for f in file_tree)
    has_spec_files = any(f.endswith(".spec.ts") or f.endswith(".spec.js") for f in file_tree)
    has_test_files = any(f.endswith(".test.ts") or f.endswith(".test.js") for f in file_tree)
    has_pytest_files = any(f.startswith("test_") or "/test_" in f for f in file_tree)

    if has_tests_dir:
        patterns.append("Separate tests/ directory")
    if has_test_dir:
        patterns.append("Separate test/ directory")
    if has_spec_files:
        patterns.append("*.spec.{ts,js} co-located test files")
    if has_test_files:
        patterns.append("*.test.{ts,js} co-located test files")
    if has_pytest_files:
        patterns.append("test_*.py pytest naming convention")

    return patterns


def _build_toml_deps(deps: dict) -> str:
    """Build a synthetic pyproject.toml dependencies section from a dict."""
    items = ", ".join(f'"{k}>={v}"' for k, v in deps.items())
    return f"[project]\ndependencies = [{items}]"
