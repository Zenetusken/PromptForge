# Contributing to PromptForge

Thank you for your interest in contributing to PromptForge! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.14+
- Node.js 22+
- Git

### Quick Start

```bash
git clone <repo-url>
cd PromptForge
chmod +x init.sh
./init.sh
```

This installs all dependencies and starts both backend (port 8000) and frontend (port 5199).

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -e ".[test]"
python -m uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Running Tests

```bash
# All tests
./init.sh test

# Backend only
cd backend && source venv/bin/activate && pytest

# Frontend only
cd frontend && npm run test && npm run check
```

## Code Style

- **Python**: Ruff (E/F/I/W rules), line length 100, target Python 3.14
- **TypeScript**: Strict mode, checked via `svelte-check`
- **Svelte**: Svelte 5 runes (`$state`, `$derived`, `$effect`)

## Making Changes

1. **Fork** the repository and create a feature branch from `main`
2. **Write tests** for new functionality
3. **Follow existing patterns** — check nearby code for conventions
4. **Keep commits focused** — one logical change per commit
5. **Run the full test suite** before submitting

## Pull Requests

- Describe what changed and why
- Reference any related issues
- Ensure all tests pass
- Keep PRs focused — large changes should be split into smaller PRs

## Adding an LLM Provider

PromptForge has a provider abstraction layer. To add a new provider:

1. Create `backend/app/providers/your_provider.py` implementing `LLMProvider`
2. Register it in `backend/app/providers/__init__.py` via `_registry.register()`
3. Add model entries to `backend/app/providers/models.py`
4. Add optional dependency to `backend/pyproject.toml`
5. Write tests in `backend/tests/test_your_provider.py`

## Reporting Issues

- Use GitHub Issues
- Include steps to reproduce
- Include error messages and logs
- Specify your Python/Node versions and OS

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
