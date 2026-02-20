#!/usr/bin/env bash
# PromptForge Development Environment Setup
# This script is idempotent — safe to run multiple times.
#
# Usage:
#   ./init.sh              Setup deps + start services (default)
#   ./init.sh stop         Stop all running services
#   ./init.sh restart      Stop then start (no reinstall)
#   ./init.sh status       Show running/stopped state + health details
#   ./init.sh test         Install test extras, run backend + frontend tests
#   ./init.sh seed         Populate example optimization data
#   ./init.sh mcp          Print MCP server config snippet for Claude Code
#   ./init.sh help         Show this usage message
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── Colors & Logging ────────────────────────────────────────────
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

log()     { echo -e "${CYAN}[PromptForge]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; }

# ─── Port Configuration ──────────────────────────────────────────
BACKEND_PORT=8000
FRONTEND_PORT=5199
MCP_PORT=8001
LOGS_DIR="$SCRIPT_DIR/logs"
BACKEND_PID_FILE="$LOGS_DIR/backend.pid"
FRONTEND_PID_FILE="$LOGS_DIR/frontend.pid"
MCP_PID_FILE="$LOGS_DIR/mcp.pid"

# Security / rate-limit defaults (overridden by .env below)
AUTH_TOKEN=""
RATE_LIMIT_RPM=60
RATE_LIMIT_OPTIMIZE_RPM=10

# read_env_config — load port config and security vars from .env if set.
_read_env_var() {
    # Usage: _read_env_var VARNAME — prints the value from .env or empty string
    grep -E "^\s*$1\s*=" "$SCRIPT_DIR/.env" 2>/dev/null \
        | tail -1 | cut -d= -f2 | tr -d '[:space:]"'"'" || true
}

read_env_config() {
    [ -f "$SCRIPT_DIR/.env" ] || return 0
    local val
    val=$(_read_env_var BACKEND_PORT);            if [ -n "$val" ]; then BACKEND_PORT="$val"; fi
    val=$(_read_env_var MCP_PORT);                 if [ -n "$val" ]; then MCP_PORT="$val"; fi
    val=$(_read_env_var AUTH_TOKEN);               if [ -n "$val" ]; then AUTH_TOKEN="$val"; fi
    val=$(_read_env_var RATE_LIMIT_RPM);           if [ -n "$val" ]; then RATE_LIMIT_RPM="$val"; fi
    val=$(_read_env_var RATE_LIMIT_OPTIMIZE_RPM);  if [ -n "$val" ]; then RATE_LIMIT_OPTIMIZE_RPM="$val"; fi
}

# Read once at startup (covers stop/status/mcp without do_setup)
read_env_config

# ─── Portable Helpers ─────────────────────────────────────────────

# find_port_pid PORT — return the PID listening on PORT (empty if none).
# Falls back through lsof → fuser → ss for portability.
find_port_pid() {
    local port=$1
    local pid=""

    if command -v lsof &>/dev/null; then
        pid=$(lsof -ti:"$port" 2>/dev/null | head -1 || true)
    fi

    if [ -z "$pid" ] && command -v fuser &>/dev/null; then
        # fuser sends PIDs to stderr — redirect to capture them
        pid=$(fuser "$port/tcp" 2>&1 | grep -oE '[0-9]+' | head -1 || true)
    fi

    if [ -z "$pid" ] && command -v ss &>/dev/null; then
        pid=$(ss -tlnp "sport = :$port" 2>/dev/null \
            | grep -oE 'pid=[0-9]+' | head -1 | grep -oE '[0-9]+' || true)
    fi

    echo "$pid"
}

# kill_pid_tree PID — kill a process and all its descendants.
# Walks the process tree via /proc to ensure orphaned children are caught
# (e.g. npm → node → vite, uvicorn parent → uvicorn worker).
kill_pid_tree() {
    local pid=$1 sig=${2:-TERM}
    # Collect children before killing parent (parent death may reparent them)
    local children
    children=$(pgrep -P "$pid" 2>/dev/null || true)
    for child in $children; do
        kill_pid_tree "$child" "$sig"
    done
    kill "-$sig" "$pid" 2>/dev/null || true
}

# kill_port PORT — kill the process listening on PORT, if any.
kill_port() {
    local port=$1
    local pid
    pid=$(find_port_pid "$port")
    if [ -n "$pid" ]; then
        kill_pid_tree "$pid"
        sleep 1
        # Force-kill if still alive
        if kill -0 "$pid" 2>/dev/null; then
            kill_pid_tree "$pid" 9
        fi
        return 0
    fi
    return 1
}

# wait_for_port_free PORT TIMEOUT — block until PORT has no listener.
wait_for_port_free() {
    local port=$1 timeout=${2:-5}
    local i
    for i in $(seq 1 "$timeout"); do
        local pid
        pid=$(find_port_pid "$port")
        if [ -z "$pid" ]; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# wait_for_url URL NAME TIMEOUT — poll URL until 2xx or timeout.
wait_for_url() {
    local url=$1 name=$2 timeout=${3:-30}
    for _ in $(seq 1 "$timeout"); do
        # --max-time 2: prevents blocking on SSE/streaming endpoints
        # Use -o /dev/null -w to check HTTP status (SSE returns 200 but never closes)
        local http_code
        http_code=$(curl -o /dev/null -s -w '%{http_code}' --max-time 2 "$url" 2>/dev/null || true)
        if [ "$http_code" = "200" ]; then
            success "$name is healthy at $url"
            return 0
        fi
        sleep 1
    done
    warn "$name not responding yet (check logs/)"
    return 1
}

# read_pid_file FILE — echo PID if file exists and process is alive, else clean up.
read_pid_file() {
    local file=$1
    if [ -f "$file" ]; then
        local pid
        pid=$(cat "$file" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
        rm -f "$file"
    fi
    return 1
}

# stop_service NAME PID_FILE PORT VERBOSE — stop one service reliably.
# Kills by PID file first (tree-kill), then ensures port is free.
# VERBOSE=1 prints status messages; 0 is silent.
stop_service() {
    local name=$1 pid_file=$2 port=$3 verbose=${4:-1}
    local stopped=false

    # Try PID file first
    local pid
    if pid=$(read_pid_file "$pid_file"); then
        kill_pid_tree "$pid"
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill_pid_tree "$pid" 9
        fi
        rm -f "$pid_file"
        stopped=true
    fi

    # Always check port — orphaned children may still hold it
    # (e.g. npm dies but vite child survives, or uvicorn reload worker)
    if kill_port "$port" 2>/dev/null; then
        stopped=true
    fi

    if $stopped; then
        if [ "$verbose" = "1" ]; then
            success "$name stopped"
        fi
        return 0
    fi

    return 1
}

# ─── Prerequisites ────────────────────────────────────────────────
# PYTHON — resolved once by check_prerequisites, used everywhere.
PYTHON=""

check_prerequisites() {
    log "Checking prerequisites..."

    # Prefer python3.14, fall back to python3
    if command -v python3.14 &>/dev/null; then
        PYTHON="python3.14"
    elif command -v python3 &>/dev/null; then
        PYTHON="python3"
    else
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

    PYTHON_VERSION=$($PYTHON --version | awk '{print $2}')
    NODE_VERSION=$(node --version)
    success "Python $PYTHON_VERSION detected ($(command -v $PYTHON))"

    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 14 ]; }; then
        error "Python >= 3.14 is required (found $PYTHON_VERSION)"
        exit 1
    fi

    success "Node.js $NODE_VERSION detected"
}

# ─── Provider Config Advisory ─────────────────────────────────────
check_provider_config() {
    if [ ! -f "$SCRIPT_DIR/.env" ]; then return 0; fi

    local has_key=false
    for key in ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY; do
        if grep -qE "^\s*${key}\s*=\s*.+" "$SCRIPT_DIR/.env" 2>/dev/null; then
            has_key=true
            break
        fi
    done

    if ! $has_key; then
        log "No API keys configured in .env — using Claude CLI (requires MAX subscription)"
        log "To use other providers, add keys to .env (see .env.example)"
    fi
}

# ─── Setup ────────────────────────────────────────────────────────
do_setup() {
    check_prerequisites

    mkdir -p "$SCRIPT_DIR/data"
    mkdir -p "$LOGS_DIR"
    success "Data and logs directories ready"

    # Backend
    log "Setting up backend..."
    cd "$SCRIPT_DIR/backend"

    if [ ! -d "venv" ]; then
        log "Creating Python virtual environment..."
        $PYTHON -m venv venv
        success "Virtual environment created"
    else
        success "Virtual environment already exists"
    fi

    source venv/bin/activate

    log "Installing Python dependencies..."
    pip install -q --upgrade pip
    pip install -q -e .
    success "Python dependencies installed"

    cd "$SCRIPT_DIR"

    # Frontend
    log "Setting up frontend..."
    cd "$SCRIPT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        log "Installing Node.js dependencies..."
        npm install
        success "Node.js dependencies installed"
    else
        success "Node.js dependencies already installed"
        npm install --prefer-offline 2>/dev/null || true
    fi

    cd "$SCRIPT_DIR"

    # Environment file
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        if [ -f "$SCRIPT_DIR/.env.example" ]; then
            cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
            success "Created .env from .env.example"
        fi
    else
        success ".env file already exists"
    fi

    # Re-read config in case .env was just created
    read_env_config

    check_provider_config
}

# ─── Start Services ───────────────────────────────────────────────
do_start() {
    log "Stopping any existing PromptForge processes..."
    stop_service "Backend" "$BACKEND_PID_FILE" "$BACKEND_PORT" 0 || true
    stop_service "Frontend" "$FRONTEND_PID_FILE" "$FRONTEND_PORT" 0 || true
    stop_service "MCP" "$MCP_PID_FILE" "$MCP_PORT" 0 || true

    # Wait for ports to be fully released before binding
    wait_for_port_free "$BACKEND_PORT" 5 || true
    wait_for_port_free "$FRONTEND_PORT" 5 || true
    wait_for_port_free "$MCP_PORT" 5 || true

    mkdir -p "$LOGS_DIR"

    # Guard: venv must exist
    if [ ! -d "$SCRIPT_DIR/backend/venv" ]; then
        error "Backend not set up yet. Run ./init.sh first."
        exit 1
    fi

    # Guard: node_modules must exist
    if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
        error "Frontend not set up yet. Run ./init.sh first."
        exit 1
    fi

    # Start backend — use venv python directly (no need for global $PYTHON)
    log "Starting backend server on port $BACKEND_PORT..."
    cd "$SCRIPT_DIR/backend"
    source venv/bin/activate

    nohup python -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        --reload \
        > "$LOGS_DIR/backend.log" 2>&1 &

    local backend_pid=$!
    echo $backend_pid > "$BACKEND_PID_FILE"
    success "Backend starting (PID: $backend_pid)"

    cd "$SCRIPT_DIR"

    # Start frontend
    log "Starting frontend dev server on port $FRONTEND_PORT..."
    cd "$SCRIPT_DIR/frontend"

    VITE_AUTH_TOKEN="$AUTH_TOKEN" BACKEND_PORT="$BACKEND_PORT" \
    nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
        > "$LOGS_DIR/frontend.log" 2>&1 &

    local frontend_pid=$!
    echo $frontend_pid > "$FRONTEND_PID_FILE"
    success "Frontend starting (PID: $frontend_pid)"

    cd "$SCRIPT_DIR"

    # Start MCP server (SSE transport with hot-reload)
    log "Starting MCP server on port $MCP_PORT..."
    cd "$SCRIPT_DIR/backend"
    source venv/bin/activate

    nohup python -m uvicorn app.mcp_server:app \
        --host 0.0.0.0 \
        --port "$MCP_PORT" \
        --reload \
        > "$LOGS_DIR/mcp.log" 2>&1 &

    local mcp_pid=$!
    echo $mcp_pid > "$MCP_PID_FILE"
    success "MCP server starting (PID: $mcp_pid)"

    cd "$SCRIPT_DIR"

    # Wait for health
    log "Waiting for services to be healthy..."
    local backend_ok=false frontend_ok=false mcp_ok=false

    if wait_for_url "http://localhost:$BACKEND_PORT/api/health" "Backend" 30; then
        backend_ok=true
    fi

    if wait_for_url "http://localhost:$FRONTEND_PORT" "Frontend" 30; then
        frontend_ok=true
    fi

    if wait_for_url "http://localhost:$MCP_PORT/sse" "MCP" 15; then
        mcp_ok=true
    fi

    # Fetch provider info from health endpoint
    local provider_info=""
    if $backend_ok; then
        provider_info=$(curl -sf "http://localhost:$BACKEND_PORT/api/health" 2>/dev/null \
            | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    p = d.get('llm_provider', d.get('provider', ''))
    if p: print(p)
except Exception: pass
" 2>/dev/null || true)
    fi

    # Summary banner
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  PromptForge Development Environment${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "  Backend API:    ${GREEN}http://localhost:$BACKEND_PORT${NC}"
    echo -e "  API Docs:       ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}"
    echo -e "  Frontend:       ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
    echo -e "  MCP Server:     ${GREEN}http://localhost:$MCP_PORT/sse${NC}"
    echo -e "  Health Check:   ${GREEN}http://localhost:$BACKEND_PORT/api/health${NC}"
    if [ -n "$provider_info" ]; then
        echo -e "  LLM Provider:   ${GREEN}$provider_info${NC}"
    fi
    echo ""
    if [ -n "$AUTH_TOKEN" ]; then
        echo -e "  Auth:           ${GREEN}enabled${NC} (Bearer token)"
    else
        echo -e "  Auth:           ${YELLOW}disabled${NC} (set AUTH_TOKEN to enable)"
    fi
    echo -e "  Rate limits:    ${GREEN}${RATE_LIMIT_RPM} rpm${NC} general, ${GREEN}${RATE_LIMIT_OPTIMIZE_RPM} rpm${NC} optimize"
    echo ""
    echo -e "  Backend PID:    $backend_pid"
    echo -e "  Frontend PID:   $frontend_pid"
    echo -e "  MCP PID:        $mcp_pid"
    echo ""
    echo -e "  Backend logs:   ${YELLOW}logs/backend.log${NC}"
    echo -e "  Frontend logs:  ${YELLOW}logs/frontend.log${NC}"
    echo -e "  MCP logs:       ${YELLOW}logs/mcp.log${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""

    if $backend_ok && $frontend_ok && $mcp_ok; then
        success "All services running! Ready for development."
    else
        warn "Some services may still be starting. Check logs."
    fi
}

# ─── Stop ─────────────────────────────────────────────────────────
do_stop() {
    log "Stopping PromptForge services..."

    local anything_stopped=false

    if stop_service "Backend" "$BACKEND_PID_FILE" "$BACKEND_PORT" 1; then
        anything_stopped=true
    fi

    if stop_service "Frontend" "$FRONTEND_PID_FILE" "$FRONTEND_PORT" 1; then
        anything_stopped=true
    fi

    if stop_service "MCP" "$MCP_PID_FILE" "$MCP_PORT" 1; then
        anything_stopped=true
    fi

    if $anything_stopped; then
        success "All services stopped."
    else
        log "No running services found."
    fi
}

# ─── Status ───────────────────────────────────────────────────────
do_status() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  PromptForge Service Status${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"

    # Backend
    local backend_status="${RED}stopped${NC}"
    local backend_pid
    if backend_pid=$(read_pid_file "$BACKEND_PID_FILE" 2>/dev/null); then
        backend_status="${GREEN}running${NC} (PID: $backend_pid)"
    else
        local port_pid
        port_pid=$(find_port_pid "$BACKEND_PORT")
        if [ -n "$port_pid" ]; then
            backend_status="${GREEN}running${NC} (PID: $port_pid, no PID file)"
        fi
    fi
    echo -e "  Backend:   $backend_status"

    # Frontend
    local frontend_status="${RED}stopped${NC}"
    local frontend_pid
    if frontend_pid=$(read_pid_file "$FRONTEND_PID_FILE" 2>/dev/null); then
        frontend_status="${GREEN}running${NC} (PID: $frontend_pid)"
    else
        local port_pid
        port_pid=$(find_port_pid "$FRONTEND_PORT")
        if [ -n "$port_pid" ]; then
            frontend_status="${GREEN}running${NC} (PID: $port_pid, no PID file)"
        fi
    fi
    echo -e "  Frontend:  $frontend_status"

    # MCP
    local mcp_status="${RED}stopped${NC}"
    local mcp_pid
    if mcp_pid=$(read_pid_file "$MCP_PID_FILE" 2>/dev/null); then
        mcp_status="${GREEN}running${NC} (PID: $mcp_pid)"
    else
        local port_pid
        port_pid=$(find_port_pid "$MCP_PORT")
        if [ -n "$port_pid" ]; then
            mcp_status="${GREEN}running${NC} (PID: $port_pid, no PID file)"
        fi
    fi
    echo -e "  MCP:       $mcp_status"

    # Security config
    echo ""
    if [ -n "$AUTH_TOKEN" ]; then
        echo -e "  Auth:          ${GREEN}enabled${NC} (Bearer token)"
    else
        echo -e "  Auth:          ${YELLOW}disabled${NC}"
    fi
    echo -e "  Rate limits:   ${RATE_LIMIT_RPM} rpm general, ${RATE_LIMIT_OPTIMIZE_RPM} rpm optimize"

    # Health details (single curl call)
    echo ""
    local health_json
    health_json=$(curl -sf "http://localhost:$BACKEND_PORT/api/health" 2>/dev/null || true)
    if [ -n "$health_json" ]; then
        echo -e "  ${BOLD}Health endpoint:${NC}"
        echo "$health_json" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for k, v in d.items():
        print(f'    {k}: {v}')
except Exception:
    print('    (could not parse response)')
" 2>/dev/null || echo -e "    $health_json"
    else
        echo -e "  Health endpoint: ${YELLOW}not reachable${NC}"
    fi

    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
}

# ─── Test ─────────────────────────────────────────────────────────
do_test() {
    check_prerequisites

    # Backend tests
    log "Installing backend test dependencies..."
    cd "$SCRIPT_DIR/backend"

    if [ ! -d "venv" ]; then
        error "Backend not set up yet. Run ./init.sh first."
        exit 1
    fi

    source venv/bin/activate
    pip install -q -e ".[test]"
    success "Test dependencies installed"

    log "Running backend tests..."
    $PYTHON -m pytest tests/ -v
    success "Backend tests complete"

    cd "$SCRIPT_DIR"

    # Frontend tests
    log "Running frontend tests..."
    cd "$SCRIPT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        error "Frontend not set up yet. Run ./init.sh first."
        exit 1
    fi

    npm run test
    success "Frontend tests complete"

    log "Running svelte-check..."
    npm run check
    success "Type checking complete"

    cd "$SCRIPT_DIR"
    success "All tests passed!"
}

# ─── Seed ─────────────────────────────────────────────────────────
do_seed() {
    log "Seeding example data..."
    cd "$SCRIPT_DIR/backend"

    if [ ! -d "venv" ]; then
        error "Backend not set up yet. Run ./init.sh first."
        exit 1
    fi

    source venv/bin/activate
    $PYTHON "$SCRIPT_DIR/scripts/seed_examples.py"
    success "Example data seeded"
    cd "$SCRIPT_DIR"
}

# ─── MCP Config ───────────────────────────────────────────────────
do_mcp() {
    echo -e "${CYAN}MCP server configuration (SSE transport):${NC}"
    echo ""
    cat <<EOF
{
  "mcpServers": {
    "promptforge": {
      "url": "http://localhost:$MCP_PORT/sse"
    }
  }
}
EOF
    echo ""
    log "The MCP server runs as a managed service on port $MCP_PORT with hot-reload."
    log "Start it with: ./init.sh  (starts all services including MCP)"
    echo ""
    log "Auto-discovery: Claude Code detects .mcp.json at the project root automatically."
}

# ─── Help ─────────────────────────────────────────────────────────
do_help() {
    echo -e "${CYAN}${BOLD}PromptForge${NC} — AI-powered prompt optimization"
    echo ""
    echo "Usage: ./init.sh [command]"
    echo ""
    echo "Commands:"
    echo "  (none)      Setup dependencies and start services (default)"
    echo "  stop        Stop all running services"
    echo "  restart     Stop then start services (no reinstall)"
    echo "  status      Show running/stopped state and health details"
    echo "  test        Install test extras, run backend + frontend tests"
    echo "  seed        Populate example optimization data"
    echo "  mcp         Print MCP server config snippet for Claude Code"
    echo "  help        Show this message"
    echo ""
    echo "Environment (set in .env):"
    echo "  BACKEND_PORT              Backend port (default: 8000)"
    echo "  MCP_PORT                  MCP server port (default: 8001)"
    echo "  AUTH_TOKEN                Bearer token for API auth (empty = disabled)"
    echo "  RATE_LIMIT_RPM            General rate limit (default: 60)"
    echo "  RATE_LIMIT_OPTIMIZE_RPM   Optimize endpoint limit (default: 10)"
    echo "  LLM_PROVIDER              LLM provider (auto-detect when empty)"
    echo "  See .env.example for all options."
}

# ─── Command Dispatcher ──────────────────────────────────────────
case "${1:-}" in
    stop)
        do_stop
        ;;
    restart)
        do_stop
        do_start
        ;;
    status)
        do_status
        ;;
    test)
        do_test
        ;;
    seed)
        do_seed
        ;;
    mcp)
        do_mcp
        ;;
    help|--help|-h)
        do_help
        ;;
    "")
        do_setup
        do_start
        ;;
    *)
        error "Unknown command: $1"
        echo ""
        do_help
        exit 1
        ;;
esac
