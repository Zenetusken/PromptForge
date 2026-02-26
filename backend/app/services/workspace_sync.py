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

# Maximum chars for README content in documentation field
_README_MAX_CHARS = 3000

# Common dual-language combos: (backend_marker, frontend_marker) → label
_DUAL_LANGUAGE_COMBOS: list[tuple[str, str, str]] = [
    ("pyproject.toml", "package.json", "Python (backend) / TypeScript (frontend)"),
    ("requirements.txt", "package.json", "Python (backend) / TypeScript (frontend)"),
    ("setup.py", "package.json", "Python (backend) / TypeScript (frontend)"),
    ("go.mod", "package.json", "Go (backend) / TypeScript (frontend)"),
    ("Cargo.toml", "package.json", "Rust (backend) / TypeScript (frontend)"),
    ("pom.xml", "package.json", "Java (backend) / TypeScript (frontend)"),
    ("build.gradle", "package.json", "Java (backend) / TypeScript (frontend)"),
    ("Gemfile", "package.json", "Ruby (backend) / TypeScript (frontend)"),
    ("composer.json", "package.json", "PHP (backend) / TypeScript (frontend)"),
]

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
    "tsconfig.json": "TypeScript configured",
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

    # Extract README content for documentation field
    documentation = _extract_readme(file_contents)

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
        documentation=documentation,
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
    """Detect primary language from GitHub API field or marker files.

    Detects dual-language projects when marker files exist for multiple
    ecosystems (e.g. Python backend + TypeScript frontend).
    """
    # Check for dual-language projects first (before single-language shortcuts)
    dual = _detect_dual_language(file_contents, file_tree)
    if dual:
        return dual

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


def _detect_dual_language(
    file_contents: dict[str, str], file_tree: list[str],
) -> str | None:
    """Check for dual-language projects (e.g. Python backend + JS/TS frontend)."""
    def _has_marker(name: str) -> bool:
        return name in file_contents or any(
            f == name or f.endswith(f"/{name}") for f in file_tree
        )

    for backend_marker, frontend_marker, label in _DUAL_LANGUAGE_COMBOS:
        if _has_marker(backend_marker) and _has_marker(frontend_marker):
            # Check if frontend is actually TypeScript or JavaScript
            ts_config = _has_marker("tsconfig.json")
            if not ts_config and "TypeScript" in label:
                # Downgrade to JavaScript if no tsconfig
                label = label.replace("TypeScript", "JavaScript")
            return label

    return None


def _detect_framework(
    language: str | None, file_contents: dict[str, str],
) -> tuple[str | None, str | None]:
    """Detect framework and version from dependency files."""
    if not language:
        return None, None

    lang_lower = language.lower()

    # For dual-language projects like "Python (backend) / TypeScript (frontend)",
    # try both ecosystems and return the first framework found.
    has_js = "javascript" in lang_lower or "typescript" in lang_lower
    has_python = "python" in lang_lower

    # JavaScript / TypeScript
    if has_js:
        pkg_json = file_contents.get("package.json")
        if pkg_json:
            fw, ver = _parse_js_framework(pkg_json)
            if fw:
                return fw, ver

    # Python
    if has_python:
        toml = file_contents.get("pyproject.toml")
        if toml:
            fw, ver = _parse_python_framework(toml)
            if fw:
                return fw, ver
        reqs = file_contents.get("requirements.txt")
        if reqs:
            fw, ver = _parse_requirements_framework(reqs)
            if fw:
                return fw, ver

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
    has_js = "javascript" in lang_lower or "typescript" in lang_lower
    has_python = "python" in lang_lower

    if has_js:
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

    if has_python:
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
    """Detect code conventions from linter configs and project files.

    When actual config file content is available, parses key settings
    for richer convention strings (e.g. 'TypeScript strict mode enabled'
    with target/module details instead of just 'TypeScript configured').
    """
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

    # Parse actual config content for richer convention details
    conventions.extend(_parse_tsconfig_conventions(file_contents, seen))
    conventions.extend(_parse_ruff_conventions(file_contents, seen))
    conventions.extend(_parse_prettier_conventions(file_contents, seen))
    conventions.extend(_parse_eslint_conventions(file_contents, seen))

    return conventions


def _detect_patterns(file_tree: list[str]) -> list[str]:
    """Detect architectural patterns from directory structure and infra files."""
    patterns: list[str] = []
    seen = set()

    for dir_pattern, pattern_str in _DIR_PATTERNS.items():
        for path in file_tree:
            if dir_pattern in path and pattern_str not in seen:
                patterns.append(pattern_str)
                seen.add(pattern_str)
                break

    # Detect infrastructure patterns from specific files
    infra_markers: dict[str, str] = {
        "Dockerfile": "Containerized deployment",
        "docker-compose.yml": "Docker Compose orchestration",
        "docker-compose.yaml": "Docker Compose orchestration",
        "Makefile": "Make-based build system",
        "nx.json": "Monorepo (Nx)",
        "lerna.json": "Monorepo (Lerna)",
        "pnpm-workspace.yaml": "Monorepo (pnpm)",
        "turbo.json": "Monorepo (Turborepo)",
    }
    for marker, pattern_str in infra_markers.items():
        if pattern_str in seen:
            continue
        for path in file_tree:
            if path == marker or path.endswith(f"/{marker}"):
                patterns.append(pattern_str)
                seen.add(pattern_str)
                break

    # GitHub Actions CI/CD: check for .github/workflows/*.yml
    if not any("GitHub Actions" in p for p in seen):
        for path in file_tree:
            if ".github/workflows/" in path and (
                path.endswith(".yml") or path.endswith(".yaml")
            ):
                pattern_str = "GitHub Actions CI/CD"
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


def _extract_readme(file_contents: dict[str, str]) -> str | None:
    """Extract and truncate README content for the documentation field."""
    readme = file_contents.get("README.md")
    if not readme:
        return None

    # Strip HTML tags if present, keep markdown
    readme = re.sub(r"<[^>]+>", "", readme)
    # Strip leading/trailing whitespace
    readme = readme.strip()

    if not readme:
        return None

    if len(readme) > _README_MAX_CHARS:
        readme = readme[:_README_MAX_CHARS] + "\n... (truncated)"

    return readme


def _parse_tsconfig_conventions(
    file_contents: dict[str, str], seen: set[str],
) -> list[str]:
    """Parse tsconfig.json for specific TypeScript settings."""
    result: list[str] = []
    tsconfig_str = file_contents.get("tsconfig.json", "")
    if not tsconfig_str:
        return result

    try:
        tsconfig = json.loads(tsconfig_str)
        opts = tsconfig.get("compilerOptions", {})

        if opts.get("strict") is True:
            conv = "TypeScript strict mode enabled"
            if conv not in seen:
                result.append(conv)
                seen.add(conv)

        target = opts.get("target")
        if target:
            conv = f"TypeScript target: {target}"
            if conv not in seen:
                result.append(conv)
                seen.add(conv)

        module = opts.get("module")
        if module:
            conv = f"TypeScript module: {module}"
            if conv not in seen:
                result.append(conv)
                seen.add(conv)

    except (json.JSONDecodeError, TypeError):
        pass

    return result


def _parse_ruff_conventions(
    file_contents: dict[str, str], seen: set[str],
) -> list[str]:
    """Parse pyproject.toml [tool.ruff] or ruff.toml for Ruff settings."""
    result: list[str] = []

    # Check ruff.toml first, then pyproject.toml
    ruff_content = file_contents.get("ruff.toml", "")
    if not ruff_content:
        pyproject = file_contents.get("pyproject.toml", "")
        if "[tool.ruff]" in pyproject:
            ruff_content = pyproject

    if not ruff_content:
        return result

    # Extract line-length
    match = re.search(r'line-length\s*=\s*(\d+)', ruff_content)
    if match:
        conv = f"Ruff line-length: {match.group(1)}"
        if conv not in seen:
            result.append(conv)
            seen.add(conv)

    # Extract target-version
    match = re.search(r'target-version\s*=\s*["\']?(py\d+)["\']?', ruff_content)
    if match:
        conv = f"Ruff target: {match.group(1)}"
        if conv not in seen:
            result.append(conv)
            seen.add(conv)

    return result


def _parse_prettier_conventions(
    file_contents: dict[str, str], seen: set[str],
) -> list[str]:
    """Parse .prettierrc/.prettierrc.json for formatting conventions."""
    result: list[str] = []

    prettier_str = file_contents.get(".prettierrc", "") or file_contents.get(
        ".prettierrc.json", "",
    )
    if not prettier_str:
        return result

    try:
        config = json.loads(prettier_str)

        parts: list[str] = []
        if "semi" in config:
            parts.append("semicolons" if config["semi"] else "no semicolons")
        if "singleQuote" in config:
            parts.append("single quotes" if config["singleQuote"] else "double quotes")
        if "tabWidth" in config:
            parts.append(f"tab width {config['tabWidth']}")

        if parts:
            conv = f"Prettier: {', '.join(parts)}"
            if conv not in seen:
                result.append(conv)
                seen.add(conv)

    except (json.JSONDecodeError, TypeError):
        pass

    return result


def _parse_eslint_conventions(
    file_contents: dict[str, str], seen: set[str],
) -> list[str]:
    """Parse ESLint config for plugin detection."""
    result: list[str] = []

    eslint_str = ""
    for key in (".eslintrc.json", ".eslintrc.js", "eslint.config.js"):
        if key in file_contents:
            eslint_str = file_contents[key]
            break

    if not eslint_str:
        return result

    # Detect TypeScript ESLint plugin
    if "@typescript-eslint" in eslint_str:
        conv = "@typescript-eslint plugin active"
        if conv not in seen:
            result.append(conv)
            seen.add(conv)

    # Detect React/hooks plugin
    if "eslint-plugin-react" in eslint_str or "react-hooks" in eslint_str:
        conv = "ESLint React/hooks rules"
        if conv not in seen:
            result.append(conv)
            seen.add(conv)

    return result


def _build_toml_deps(deps: dict) -> str:
    """Build a synthetic pyproject.toml dependencies section from a dict."""
    items = ", ".join(f'"{k}>={v}"' for k, v in deps.items())
    return f"[project]\ndependencies = [{items}]"
