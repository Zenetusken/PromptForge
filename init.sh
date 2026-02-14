#!/usr/bin/env bash
# PromptForge Development Environment Setup
# This script is idempotent — safe to run multiple times.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${CYAN}[PromptForge]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# ─── 1. Check Prerequisites ────────────────────────────────────────
log "Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    error "Python 3 is required but not found"
    exit 1
fi

if ! command -v node &>/dev/null; then
    error "Node.js is required but not found"
    exit 1
fi

if ! command -v npm &>/dev/null; then
    error "npm is required but not found"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
NODE_VERSION=$(node --version)
success "Python $PYTHON_VERSION detected"

# Enforce minimum Python version 3.14
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 14 ]; }; then
    error "Python >= 3.14 is required (found $PYTHON_VERSION)"
    exit 1
fi

success "Node.js $NODE_VERSION detected"

# ─── 2. Create Data Directory ──────────────────────────────────────
mkdir -p "$SCRIPT_DIR/data"
success "Data directory ready"

# ─── 3. Backend Setup ──────────────────────────────────────────────
log "Setting up backend..."

cd "$SCRIPT_DIR/backend"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv venv
    success "Virtual environment created"
else
    success "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
log "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
success "Python dependencies installed"

cd "$SCRIPT_DIR"

# ─── 4. Frontend Setup ─────────────────────────────────────────────
log "Setting up frontend..."

cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    log "Installing Node.js dependencies..."
    npm install
    success "Node.js dependencies installed"
else
    success "Node.js dependencies already installed"
    # Still run install in case package.json changed
    npm install --prefer-offline 2>/dev/null || true
fi

cd "$SCRIPT_DIR"

# ─── 5. Environment File ───────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        success "Created .env from .env.example"
    fi
else
    success ".env file already exists"
fi

# ─── 6. Kill Existing Processes ────────────────────────────────────
log "Stopping any existing PromptForge processes..."

# Kill any existing backend on port 8000
if lsof -ti:8000 &>/dev/null; then
    kill $(lsof -ti:8000) 2>/dev/null || true
    sleep 1
    warn "Killed existing process on port 8000"
fi

# Kill any existing frontend on port 5173
if lsof -ti:5173 &>/dev/null; then
    kill $(lsof -ti:5173) 2>/dev/null || true
    sleep 1
    warn "Killed existing process on port 5173"
fi

# ─── 7. Start Backend ──────────────────────────────────────────────
log "Starting backend server..."

cd "$SCRIPT_DIR/backend"
source venv/bin/activate

# Start uvicorn in background
nohup python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > "$SCRIPT_DIR/logs/backend.log" 2>&1 &

BACKEND_PID=$!
echo $BACKEND_PID > "$SCRIPT_DIR/logs/backend.pid"
success "Backend starting (PID: $BACKEND_PID)"

cd "$SCRIPT_DIR"

# ─── 8. Start Frontend ─────────────────────────────────────────────
log "Starting frontend dev server..."

cd "$SCRIPT_DIR/frontend"

nohup npm run dev -- --host 0.0.0.0 \
    > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &

FRONTEND_PID=$!
echo $FRONTEND_PID > "$SCRIPT_DIR/logs/frontend.pid"
success "Frontend starting (PID: $FRONTEND_PID)"

cd "$SCRIPT_DIR"

# ─── 9. Wait for Health ────────────────────────────────────────────
log "Waiting for services to be healthy..."

# Wait for backend
BACKEND_READY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        BACKEND_READY=true
        break
    fi
    sleep 1
done

if $BACKEND_READY; then
    success "Backend is healthy at http://localhost:8000"
else
    warn "Backend not responding yet (check logs/backend.log)"
fi

# Wait for frontend
FRONTEND_READY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:5173 > /dev/null 2>&1; then
        FRONTEND_READY=true
        break
    fi
    sleep 1
done

if $FRONTEND_READY; then
    success "Frontend is healthy at http://localhost:5173"
else
    warn "Frontend not responding yet (check logs/frontend.log)"
fi

# ─── 10. Summary ───────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  PromptForge Development Environment${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "  Backend API:    ${GREEN}http://localhost:8000${NC}"
echo -e "  API Docs:       ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  Frontend:       ${GREEN}http://localhost:5173${NC}"
echo -e "  Health Check:   ${GREEN}http://localhost:8000/api/health${NC}"
echo ""
echo -e "  Backend PID:    $BACKEND_PID"
echo -e "  Frontend PID:   $FRONTEND_PID"
echo ""
echo -e "  Backend logs:   ${YELLOW}logs/backend.log${NC}"
echo -e "  Frontend logs:  ${YELLOW}logs/frontend.log${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

if $BACKEND_READY && $FRONTEND_READY; then
    success "All services running! Ready for development."
else
    warn "Some services may still be starting. Check logs."
fi
