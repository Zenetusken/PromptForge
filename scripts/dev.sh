#!/usr/bin/env bash
# PromptForge Development Script
# Starts both the backend API server and the frontend dev server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PromptForge development servers...${NC}"

# Create data directory if it doesn't exist
mkdir -p "$PROJECT_DIR/data"

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill 0 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${GREEN}Starting backend on http://localhost:8000...${NC}"
cd "$PROJECT_DIR/backend"
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend (if it exists)
if [ -d "$PROJECT_DIR/frontend" ] && [ -f "$PROJECT_DIR/frontend/package.json" ]; then
    echo -e "${GREEN}Starting frontend on http://localhost:5199...${NC}"
    cd "$PROJECT_DIR/frontend"
    npm run dev &
    FRONTEND_PID=$!
else
    echo -e "${YELLOW}Frontend not yet scaffolded. Skipping frontend server.${NC}"
    echo -e "${YELLOW}Run 'npx sv create frontend' from the project root to scaffold SvelteKit.${NC}"
fi

echo -e "${GREEN}PromptForge is running!${NC}"
echo -e "  Backend API:  http://localhost:8000"
echo -e "  API Docs:     http://localhost:8000/docs"
echo -e "  Frontend:     http://localhost:5199"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers.${NC}"

# Wait for background processes
wait
