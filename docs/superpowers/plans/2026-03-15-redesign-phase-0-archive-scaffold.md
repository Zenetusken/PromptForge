# Phase 0: Archive & Scaffold — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Archive the v2 codebase and create a clean project skeleton with database migrations for the redesigned application.

**Architecture:** Move all current source to `archive/v2/`, create the new `backend/`, `frontend/`, and `prompts/` directory structures, initialize Alembic with all 9 tables, and verify the skeleton is functional.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy (async), Alembic, aiosqlite, SvelteKit 2, Tailwind CSS 4

**Spec:** `docs/superpowers/specs/2026-03-15-project-synthesis-redesign.md`
**Protocol:** `docs/superpowers/plans/2026-03-15-redesign-orchestration-protocol.md`

---

## Chunk 1: Archive & Scaffold

### Task 1: Archive v2 Source

**Files:**
- Create: `archive/v2/` (move all current source here)
- Modify: `.gitignore`

- [ ] **Step 1: Create archive directory and move v2 source**

```bash
mkdir -p archive/v2
# Move all current application source (not docs/specs/plans)
mv backend archive/v2/
mv frontend archive/v2/
mv init.sh archive/v2/ 2>/dev/null || true
mv docker-compose.yml archive/v2/ 2>/dev/null || true
mv Dockerfile archive/v2/ 2>/dev/null || true
mv nginx archive/v2/ 2>/dev/null || true
mv .env* archive/v2/ 2>/dev/null || true
mv data archive/v2/ 2>/dev/null || true
```

- [ ] **Step 2: Add archive to .gitignore**

The archive is for local reference only — v2 code is preserved in git history at its original paths. The archive directory won't exist after a fresh `git clone`.

Add to `.gitignore`:
```
# Archived v2 source (local reference only — v2 preserved in git history)
archive/
```

- [ ] **Step 3: Verify archive is complete**

```bash
ls archive/v2/backend/app/main.py  # should exist
ls archive/v2/frontend/package.json  # should exist
```

Expected: both files exist.

- [ ] **Step 4: Commit archive**

```bash
git add -A
git commit -m "chore: archive v2 source to archive/v2/"
```

---

### Task 2: Create Backend Skeleton

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/_version.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/providers/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/dependencies/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/requirements.txt`
- Create: `backend/pyproject.toml`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/app/services
mkdir -p backend/app/routers
mkdir -p backend/app/providers
mkdir -p backend/app/schemas
mkdir -p backend/app/dependencies
mkdir -p backend/tests
```

- [ ] **Step 2: Create `backend/app/_version.py`**

```python
__version__ = "0.1.0-dev"
```

- [ ] **Step 3: Create `backend/app/__init__.py`**

```python
from app._version import __version__

__all__ = ["__version__"]
```

- [ ] **Step 4: Create `backend/app/config.py`**

```python
"""Application configuration via pydantic-settings."""

import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Provider ---
    ANTHROPIC_API_KEY: str = ""

    # --- GitHub OAuth ---
    GITHUB_OAUTH_CLIENT_ID: str = ""
    GITHUB_OAUTH_CLIENT_SECRET: str = ""

    # --- Security ---
    SECRET_KEY: str = ""

    # --- Embedding ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- Rate Limiting ---
    OPTIMIZE_RATE_LIMIT: str = "10/minute"
    REFINE_RATE_LIMIT: str = "10/minute"
    FEEDBACK_RATE_LIMIT: str = "30/minute"
    DEFAULT_RATE_LIMIT: str = "60/minute"

    # --- Passthrough ---
    BIAS_CORRECTION_FACTOR: float = 0.85

    # --- Context Budget ---
    MAX_CONTEXT_TOKENS: int = 80000
    MAX_RAW_PROMPT_CHARS: int = 200000
    MAX_GUIDANCE_CHARS: int = 20000
    MAX_CODEBASE_CONTEXT_CHARS: int = 100000
    MAX_ADAPTATION_CHARS: int = 5000
    EXPLORE_MAX_PROMPT_CHARS: int = 20000
    EXPLORE_MAX_CONTEXT_CHARS: int = 700000
    EXPLORE_MAX_FILES: int = 40
    EXPLORE_TOTAL_LINE_BUDGET: int = 15000

    # --- Network ---
    TRUSTED_PROXIES: str = "127.0.0.1"
    FRONTEND_URL: str = "http://localhost:5199"

    # --- Traces ---
    TRACE_RETENTION_DAYS: int = 30

    # --- Database ---
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'synthesis.db'}"

    def resolve_secret_key(self) -> str:
        """Auto-generate SECRET_KEY if not set, persist to data/.app_secrets."""
        if self.SECRET_KEY:
            return self.SECRET_KEY
        secrets_file = DATA_DIR / ".app_secrets"
        if secrets_file.exists():
            return secrets_file.read_text().strip()
        key = secrets.token_urlsafe(64)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text(key)
        secrets_file.chmod(0o600)
        return key


settings = Settings()
```

- [ ] **Step 5: Create `backend/app/main.py`**

```python
"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app._version import __version__
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    settings.SECRET_KEY = settings.resolve_secret_key()
    yield
    # Shutdown


app = FastAPI(
    title="Project Synthesis",
    version=__version__,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5199"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ASGI app for uvicorn
asgi_app = app
```

- [ ] **Step 6: Create empty `__init__.py` files**

```bash
touch backend/app/services/__init__.py
touch backend/app/routers/__init__.py
touch backend/app/providers/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/dependencies/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 7: Create `backend/tests/conftest.py`**

```python
"""Shared test fixtures."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# No custom event_loop fixture needed — pytest-asyncio manages it
# automatically with asyncio_mode = "auto" in pyproject.toml.


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Import models to register them
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await engine.dispose()
```

- [ ] **Step 8: Create `backend/requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy[asyncio]>=2.0.0
aiosqlite>=0.20.0
alembic>=1.13.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
anthropic>=0.40.0
httpx>=0.27.0
python-multipart>=0.0.9
cryptography>=43.0.0
textstat>=0.7.0
sentence-transformers>=3.0.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
pytest-cov>=5.0.0
ruff>=0.5.0
```

- [ ] **Step 9: Create `backend/pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

- [ ] **Step 10: Create virtual environment and install dependencies**

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Expected: clean install, no errors.

- [ ] **Step 11: Verify pytest discovers test directory**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ --collect-only 2>&1 | head -5
```

Expected: "no tests ran" or "collected 0 items" (no errors).

- [ ] **Step 12: Commit backend skeleton**

```bash
git add backend/
git commit -m "chore: create backend skeleton with config and dependencies"
```

---

### Task 3: Create Database Models & Alembic Migrations

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Create `backend/app/models.py`**

All 9 tables from spec Sections 6 and 13:

```python
"""SQLAlchemy models — all tables for the application."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# --- Core tables (Section 6) ---

class Optimization(Base):
    __tablename__ = "optimizations"

    id = Column(String, primary_key=True, default=_uuid)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    raw_prompt = Column(Text, nullable=False)
    optimized_prompt = Column(Text, nullable=True)
    task_type = Column(String, nullable=True)
    strategy_used = Column(String, nullable=True)
    changes_summary = Column(Text, nullable=True)
    score_clarity = Column(Float, nullable=True)
    score_specificity = Column(Float, nullable=True)
    score_structure = Column(Float, nullable=True)
    score_faithfulness = Column(Float, nullable=True)
    score_conciseness = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    provider = Column(String, nullable=True)
    model_used = Column(String, nullable=True)
    scoring_mode = Column(String, nullable=True)  # independent / self_rated
    duration_ms = Column(Integer, nullable=True)
    repo_full_name = Column(String, nullable=True)
    codebase_context_snapshot = Column(Text, nullable=True)
    status = Column(String, default="completed", nullable=False)  # completed / failed / interrupted
    trace_id = Column(String, nullable=True)
    tokens_total = Column(Integer, nullable=True)
    tokens_by_phase = Column(JSON, nullable=True)
    context_sources = Column(JSON, nullable=True)
    original_scores = Column(JSON, nullable=True)
    score_deltas = Column(JSON, nullable=True)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(String, primary_key=True, default=_uuid)
    optimization_id = Column(String, ForeignKey("optimizations.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    rating = Column(String, nullable=False)  # thumbs_up / thumbs_down
    comment = Column(Text, nullable=True)


class StrategyAffinity(Base):
    __tablename__ = "strategy_affinities"

    id = Column(String, primary_key=True, default=_uuid)
    task_type = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    thumbs_up = Column(Integer, default=0, nullable=False)
    thumbs_down = Column(Integer, default=0, nullable=False)
    approval_rate = Column(Float, default=0.0, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


# --- Ported tables (GitHub/Embedding) ---
# These match the v2 schema closely to minimize friction when porting services in Phase 2.

class GitHubToken(Base):
    __tablename__ = "github_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, unique=True)
    token_encrypted = Column(LargeBinary, nullable=False)  # Fernet-encrypted, matches v2
    token_type = Column(String, default="oauth", nullable=False)
    github_user_id = Column(String, nullable=True)
    github_login = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    refresh_token_encrypted = Column(LargeBinary, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class LinkedRepo(Base):
    __tablename__ = "linked_repos"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False)
    full_name = Column(String, nullable=False)  # matches v2 column name
    default_branch = Column(String, default="main", nullable=False)
    branch = Column(String, nullable=True)  # active working branch (distinct from default)
    language = Column(String, nullable=True)
    linked_at = Column(DateTime, default=_utcnow, nullable=False)  # matches v2 column name


class RepoFileIndex(Base):
    __tablename__ = "repo_file_index"

    id = Column(String, primary_key=True, default=_uuid)
    repo_full_name = Column(String, nullable=False, index=True)
    branch = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_sha = Column(String, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    outline = Column(Text, nullable=True)
    embedding = Column(LargeBinary, nullable=True)  # numpy bytes (384*4=1536), matches v2
    updated_at = Column(DateTime, default=_utcnow, nullable=False)


class RepoIndexMeta(Base):
    __tablename__ = "repo_index_meta"

    id = Column(String, primary_key=True, default=_uuid)
    repo_full_name = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    file_count = Column(Integer, default=0, nullable=False)
    head_sha = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    indexed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        # One index per (repo, branch) — matches v2 composite unique
        {"sqlite_autoincrement": False},
    )


# --- Refinement tables (Section 13) ---
# RefinementBranch defined first since RefinementTurn has FK to it.

class RefinementBranch(Base):
    __tablename__ = "refinement_branches"

    id = Column(String, primary_key=True, default=_uuid)
    optimization_id = Column(String, ForeignKey("optimizations.id"), nullable=False)
    parent_branch_id = Column(String, nullable=True)
    forked_at_version = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class RefinementTurn(Base):
    __tablename__ = "refinement_turns"

    id = Column(String, primary_key=True, default=_uuid)
    optimization_id = Column(String, ForeignKey("optimizations.id"), nullable=False)
    version = Column(Integer, nullable=False)
    branch_id = Column(String, ForeignKey("refinement_branches.id"), nullable=False)
    parent_version = Column(Integer, nullable=True)
    refinement_request = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    scores = Column(JSON, nullable=True)
    deltas = Column(JSON, nullable=True)
    deltas_from_original = Column(JSON, nullable=True)
    strategy_used = Column(String, nullable=True)
    suggestions = Column(JSON, nullable=True)
    trace_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
```

- [ ] **Step 2: Initialize Alembic**

```bash
cd backend && source .venv/bin/activate && alembic init alembic
```

- [ ] **Step 3: Configure `backend/alembic.ini`**

Update `sqlalchemy.url` line:
```ini
sqlalchemy.url = sqlite+aiosqlite:///%(here)s/../data/synthesis.db
```

- [ ] **Step 4: Configure `backend/alembic/env.py`**

Replace the default `env.py` with async support:

```python
"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Generate initial migration**

```bash
cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "initial schema - all 9 tables"
```

Expected: migration file created in `alembic/versions/`.

- [ ] **Step 6: Run migration**

```bash
mkdir -p ../data
cd backend && source .venv/bin/activate && alembic upgrade head
```

Expected: tables created in `data/synthesis.db`.

- [ ] **Step 7: Verify tables exist**

```bash
cd backend && source .venv/bin/activate && python -c "
import sqlite3
conn = sqlite3.connect('../data/synthesis.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print(sorted(tables))
conn.close()
"
```

Expected: `['alembic_version', 'feedbacks', 'github_tokens', 'linked_repos', 'optimizations', 'refinement_branches', 'refinement_turns', 'repo_file_index', 'repo_index_meta', 'strategy_affinities']`

- [ ] **Step 8: Enable WAL mode**

Add to `backend/app/main.py` lifespan startup (inside the `async with` block, after `settings.SECRET_KEY = ...`):

```python
from app.config import DATA_DIR
import aiosqlite

# Enable WAL mode for SQLite read/write concurrency
db_path = DATA_DIR / "synthesis.db"
if db_path.exists():
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
```

- [ ] **Step 9: Commit database models and migrations**

```bash
git add backend/app/models.py backend/alembic.ini backend/alembic/
git commit -m "feat: add database models and initial Alembic migration (9 tables)"
```

---

### Task 4: Create Prompts Skeleton

**Files:**
- Create: `prompts/` directory with all template files (placeholder content)
- Create: `prompts/strategies/` with all 6 strategy files
- Create: `prompts/manifest.json`
- Create: `prompts/README.md`

- [ ] **Step 1: Create prompts directory structure**

```bash
mkdir -p prompts/strategies
```

- [ ] **Step 2: Create placeholder template files**

Each file gets a minimal placeholder that includes the required `{{variables}}` from the manifest so startup validation will pass. Real content is written in Phase 1.

```bash
# Templates with variables (placeholders for now)
for f in agent-guidance analyze optimize scoring explore adaptation; do
    echo "# ${f} — placeholder (Phase 1 will add real content)" > "prompts/${f}.md"
done

# Refinement templates (Phase 4)
for f in refine suggest; do
    echo "# ${f} — placeholder (Phase 4 will add real content)" > "prompts/${f}.md"
done

# Passthrough (Phase 2)
echo "# passthrough — placeholder (Phase 2 will add real content)" > "prompts/passthrough.md"

# Strategy files (static content, Phase 1)
for f in chain-of-thought few-shot role-playing structured-output meta-prompting auto; do
    echo "# ${f} strategy — placeholder (Phase 1 will add real content)" > "prompts/strategies/${f}.md"
done
```

- [ ] **Step 3: Create `prompts/manifest.json`**

```json
{
  "agent-guidance.md": {"required": [], "optional": []},
  "analyze.md": {"required": ["raw_prompt", "available_strategies"], "optional": []},
  "optimize.md": {"required": ["raw_prompt", "strategy_instructions", "analysis_summary"], "optional": ["codebase_guidance", "codebase_context", "adaptation_state"]},
  "scoring.md": {"required": [], "optional": []},
  "explore.md": {"required": ["raw_prompt", "file_contents", "file_paths"], "optional": []},
  "adaptation.md": {"required": ["task_type_affinities"], "optional": []},
  "refine.md": {"required": ["current_prompt", "refinement_request", "original_prompt", "strategy_instructions"], "optional": ["codebase_guidance", "codebase_context", "adaptation_state"]},
  "suggest.md": {"required": ["optimized_prompt", "scores", "weaknesses", "strategy_used"], "optional": []},
  "passthrough.md": {"required": ["raw_prompt", "scoring_rubric_excerpt"], "optional": ["strategy_instructions", "codebase_guidance", "codebase_context", "adaptation_state"]}
}
```

- [ ] **Step 4: Create `prompts/README.md`**

```markdown
# Prompt Templates

All prompts for the optimization pipeline are stored as Markdown files in this directory.
Templates use `{{variable}}` syntax for dynamic substitution and XML tags for structured sections.

## Template Syntax

- `{{variable_name}}` — replaced at runtime by prompt_loader.py
- Variables with no value are omitted entirely, including surrounding XML tags
- Data goes at the TOP of the template, instructions at the BOTTOM

## Editing Templates

Templates are hot-reloaded — edit any file and the next optimization uses the updated version.
No app restart needed.

## Variable Reference

See `manifest.json` for required and optional variables per template.
See the spec for the full variable reference table.

## Strategy Files

Strategy templates in `strategies/` are static content (no variables).
Their full text is loaded by strategy_loader.py and injected as `{{strategy_instructions}}`.
```

- [ ] **Step 5: Commit prompts skeleton**

```bash
git add prompts/
git commit -m "chore: create prompts directory skeleton with manifest and placeholders"
```

---

### Task 5: Create Frontend Skeleton

**Files:**
- Create: `frontend/` with SvelteKit 2 project

- [ ] **Step 1: Create SvelteKit project**

```bash
npx sv create frontend --template minimal --types ts --no-add-ons
cd frontend && npm install
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Configure port 5199 in `frontend/vite.config.ts`**

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
    plugins: [tailwindcss(), sveltekit()],
    server: {
        port: 5199,
    },
});
```

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 4: Commit frontend skeleton**

```bash
git add frontend/
git commit -m "chore: create SvelteKit frontend skeleton on port 5199"
```

---

### Task 6: Create Data Directory & Write Handoff

**Files:**
- Create: `data/traces/` directory
- Create: `docs/superpowers/plans/handoffs/handoff-phase-0.json`

- [ ] **Step 1: Create data directories**

```bash
mkdir -p data/traces
echo "*.db" > data/.gitignore
echo "traces/" >> data/.gitignore
echo ".app_secrets" >> data/.gitignore
```

- [ ] **Step 2: Verify all exit conditions**

```bash
# 1. Archive exists (local only — won't exist after fresh git clone)
test -d archive/v2/backend && echo "PASS: v2 archived locally"

# 2. Backend skeleton
cd backend && source .venv/bin/activate && python -m pytest tests/ --collect-only 2>&1 | tail -1

# 3. Database tables
python -c "
import sqlite3
conn = sqlite3.connect('../data/synthesis.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
assert len(tables) == 10, f'Expected 10 tables (9 + alembic_version), got {len(tables)}: {tables}'
print(f'PASS: {len(tables)} tables created')
conn.close()
"

# 4. Prompts skeleton
test -f ../prompts/manifest.json && echo "PASS: manifest.json exists"
ls ../prompts/strategies/*.md | wc -l  # should be 6

# 5. Frontend
cd ../frontend && npm run check 2>&1 | tail -1

# 6. Data directory
test -d ../data/traces && echo "PASS: data/traces exists"
```

- [ ] **Step 3: Write handoff artifact**

Create `docs/superpowers/plans/handoffs/handoff-phase-0.json`:

```json
{
  "phase": 0,
  "status": "completed",
  "timestamp": "",
  "summary": "Project skeleton created. v2 archived. All 9 tables migrated. Backend, frontend, and prompts directories ready.",

  "files_created": [
    "backend/app/main.py",
    "backend/app/config.py",
    "backend/app/_version.py",
    "backend/app/models.py",
    "backend/alembic.ini",
    "backend/alembic/env.py",
    "backend/tests/conftest.py",
    "backend/requirements.txt",
    "backend/pyproject.toml",
    "prompts/manifest.json",
    "prompts/README.md",
    "frontend/vite.config.ts"
  ],
  "files_modified": [".gitignore"],

  "entry_conditions_met": ["First phase — no entry conditions"],

  "exit_conditions": {
    "all_passed": true,
    "tests_total": 0,
    "tests_passed": 0,
    "coverage_percent": 0,
    "verification_commands": [
      {"cmd": "ls archive/v2/backend/app/main.py", "result": "exists"},
      {"cmd": "cd backend && pytest --collect-only", "result": "0 items"},
      {"cmd": "sqlite3 check — 10 tables", "result": "PASS"},
      {"cmd": "ls prompts/strategies/*.md | wc -l", "result": "6"},
      {"cmd": "cd frontend && npm run check", "result": "PASS"}
    ]
  },

  "warnings": [],

  "next_phase_context": {
    "critical_interfaces": [
      "app.models.Base is the SQLAlchemy declarative base — import from here",
      "app.config.settings is the singleton Settings instance",
      "app.main.app is the FastAPI application — add routers here",
      "All prompt templates are placeholders — Phase 1 writes real content"
    ],
    "env_vars_required": [],
    "known_limitations": [
      "All prompt templates are placeholder content — require Phase 1 to populate",
      "No routers attached to FastAPI app yet",
      "Frontend is bare SvelteKit skeleton — no components"
    ],
    "alembic_revision": "001_initial_schema"
  }
}
```

- [ ] **Step 4: Commit handoff and data directory**

```bash
mkdir -p docs/superpowers/plans/handoffs
git add data/.gitignore docs/superpowers/plans/handoffs/handoff-phase-0.json
git commit -m "chore: Phase 0 complete — project skeleton ready for implementation"
```
