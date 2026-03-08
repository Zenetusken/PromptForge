# Project Synthesis

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**AI-powered prompt optimization with a 5-stage analysis pipeline.**

Project Synthesis runs your prompts through a structured pipeline — **Explore → Analyze → Strategy → Optimize → Validate** — producing a measurably improved result with per-dimension scoring, diff view, and full trace visibility.

## Prerequisites

At least one LLM provider:

- **Option A (preferred)**: Claude Code CLI with Max subscription
  ```bash
  npm install -g @anthropic-ai/claude-code
  claude login
  ```
- **Option B**: Anthropic API key — copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`

## Quick Start

```bash
./init.sh          # Install dependencies and start all services
./init.sh status   # Check service status
./init.sh restart  # Restart all services
./init.sh stop     # Stop all services
```

## Services

| Service | Port | Purpose |
|---|---|---|
| API backend | 8000 | FastAPI + pipeline orchestration |
| Frontend | 5199 | SvelteKit UI |
| MCP server | 8001 | 13 tools for Claude Code integration |

## Pipeline stages

| Stage | What it does |
|---|---|
| **Explore** | Reads linked GitHub repository context (file tree, key files) |
| **Analyze** | Classifies prompt type, task domain, and complexity |
| **Strategy** | Selects the optimal optimization framework |
| **Optimize** | Rewrites the prompt using the chosen strategy |
| **Validate** | Scores the result across multiple dimensions (0–10) |

## MCP Server

Project Synthesis exposes 13 tools via MCP, accessible directly from Claude Code when this directory is open. See [docs/MCP.md](docs/MCP.md) for the full tool reference.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on branching, code style, and the PR process.

Found a security issue? See [SECURITY.md](SECURITY.md) for responsible disclosure instructions — do not open a public issue.

## License

Copyright 2026 Project Synthesis Contributors.
Licensed under the [Apache License, Version 2.0](LICENSE).
