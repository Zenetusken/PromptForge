# PromptForge — Intelligent Prompt Optimization Engine

PromptForge is a self-adaptive prompt optimization webapp that transforms raw, unstructured prompts into properly structured, improved, and optimized versions using Claude AI models.

## Architecture

- **Frontend**: SvelteKit 2 (Svelte 5) + Tailwind CSS 4 — port 5199
- **Backend**: Python FastAPI — port 8000
- **MCP Server**: FastMCP (streamable HTTP) — port 8001 | WebSocket backward-compat on port 8000
- **Database**: SQLite via aiosqlite + SQLAlchemy async

## Quick Start

```bash
# Start all services
./init.sh

# Or start individually
./init.sh setup   # Install dependencies
./init.sh         # Start all services
./init.sh status  # Check service status
./init.sh stop    # Stop all services
```

## Prerequisites

At least ONE LLM provider:

- **Option A (preferred)**: Claude Code CLI with Max subscription
  ```bash
  npm install -g @anthropic-ai/claude-code
  claude login
  ```

- **Option B**: Anthropic API key
  ```bash
  cp .env.example .env
  # Edit .env and set ANTHROPIC_API_KEY
  ```

## Features

- **5-Stage Pipeline**: Explore → Analyze → Strategy → Optimize → Validate
- **Auto-Detection**: Automatically selects the best available LLM provider
- **Model Routing**: Each stage uses the optimal Claude model (Haiku/Sonnet/Opus)
- **GitHub Integration**: Link repos for codebase-aware optimization
- **Real-time Streaming**: SSE-powered pipeline progress
- **MCP Server**: 13 tools accessible from Claude Code (see [docs/MCP.md](docs/MCP.md))
- **Developer Workbench UI**: VS Code-inspired 5-zone layout
- **Industrial Cyberpunk Theme**: Flat neon contour aesthetic

## Environment Variables

See `.env.example` for all configuration options.

## Project Structure

```
├── backend/          # FastAPI backend (port 8000)
├── frontend/         # SvelteKit frontend (port 5199)
├── scripts/          # Utility scripts
├── data/             # SQLite database (gitignored)
├── init.sh           # Setup and run script
├── docker-compose.yml
└── .mcp.json         # MCP server config for Claude Code
```
