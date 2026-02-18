# PromptForge — Intelligent Prompt Optimization Engine

A self-adaptive prompt optimization web app that transforms raw, unstructured prompts into properly structured, improved, and optimized versions using a 3-step AI pipeline.

## Tech Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy async / aiosqlite
- **Frontend**: SvelteKit 2 (Svelte 5) / Tailwind CSS 4 / Vite
- **LLM**: claude-agent-sdk (zero API cost with Claude Max subscription)
- **Streaming**: Server-Sent Events (SSE) for real-time pipeline updates
- **Database**: SQLite
- **MCP Server**: FastMCP for Claude Code integration

## Quick Start

```bash
# Make init script executable and run it
chmod +x init.sh
./init.sh
```

This will:
1. Install Python and Node.js dependencies
2. Create the SQLite database
3. Start the backend on http://localhost:8000
4. Start the frontend on http://localhost:5199
5. Wait for both services to be healthy

## Development

### Backend (port 8000)
```bash
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend (port 5199)
```bash
cd frontend
npm run dev
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/optimize` | Start optimization pipeline (SSE stream) |
| GET | `/api/optimize/{id}` | Get optimization by ID |
| POST | `/api/optimize/{id}/retry` | Re-run optimization |
| GET | `/api/history` | List optimizations (paginated) |
| DELETE | `/api/history/{id}` | Delete optimization |
| GET | `/api/history/stats` | Dashboard statistics |
| GET | `/api/health` | Health check |

### MCP Server

PromptForge exposes its engine as an MCP server for Claude Code integration:

```bash
# Test the MCP server
cd backend
python -m app.mcp_server
```

## Pipeline

1. **Analyze** — Classify the prompt type and identify weaknesses/strengths
2. **Optimize** — Transform the prompt using recommended frameworks (CO-STAR, RISEN, etc.)
3. **Validate** — Score the optimization on clarity, specificity, structure, faithfulness

## Project Structure

```
promptforge/
├── backend/           # FastAPI application
│   └── app/
│       ├── main.py          # App entry point
│       ├── config.py        # Settings
│       ├── database.py      # SQLAlchemy async setup
│       ├── models/          # ORM models
│       ├── schemas/         # Pydantic schemas
│       ├── routers/         # API endpoints
│       ├── services/        # Business logic
│       ├── prompts/         # LLM system prompts
│       └── mcp_server.py    # MCP server
├── frontend/          # SvelteKit application
│   └── src/
│       ├── routes/          # Pages
│       └── lib/
│           ├── components/  # Svelte components
│           ├── stores/      # State management
│           ├── api/         # API client
│           └── utils/       # Utilities
├── data/              # SQLite database
├── logs/              # Server logs
├── init.sh            # Setup script
└── feature_list.json  # Test cases for autonomous development
```
