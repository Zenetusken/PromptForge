#!/usr/bin/env bash
# Project Synthesis — service manager
# Usage: ./init.sh {start|stop|restart|status|logs|setup-vscode}
set -uo pipefail
# Note: -e intentionally omitted — we handle errors per-command

# ---------------------------------------------------------------------------
# Paths & ports
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
PID_DIR="$DATA_DIR/pids"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
PYTHON="$BACKEND_DIR/.venv/bin/python"
UVICORN="$BACKEND_DIR/.venv/bin/uvicorn"
VITE="$FRONTEND_DIR/node_modules/.bin/vite"

BACKEND_PORT=8000
MCP_PORT=8001
FRONTEND_PORT=5199

# Graceful shutdown timeout per service (seconds).
# Backend breakdown: uvicorn graceful drain (10s) + lifespan shutdown
#   Phase 1 SSE drain (0.1s) + Phase 2 bg tasks (2s) + Phase 3 extraction
#   drain (5s) + Phase 4-5 cleanup (1s) = ~18s total. Add margin.
declare -A STOP_TIMEOUT=([backend]=25 [mcp]=5 [frontend]=5)

# Startup readiness timeout per service (seconds).
# Backend needs 30-40s: uvicorn --reload fork + lifespan init (SQLite WAL,
# routing, taxonomy engine, index warm-load, domain services, migrations,
# backfills, strategy/agent watchers, warm-path timer start).
declare -A READY_TIMEOUT=([backend]=45 [mcp]=10 [frontend]=15)

# ---------------------------------------------------------------------------
# Output helpers (ANSI colors when stdout is a terminal)
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
    _RST='\033[0m' _GRN='\033[32m' _YLW='\033[33m' _RED='\033[31m'
    _CYN='\033[36m' _DIM='\033[90m' _BLD='\033[1m'
else
    _RST='' _GRN='' _YLW='' _RED='' _CYN='' _DIM='' _BLD=''
fi

_log()  { echo -e "${_CYN}[init.sh]${_RST} $*"; }
_ok()   { echo -e "  ${_GRN}✓${_RST} $*"; }
_fail() { echo -e "  ${_RED}✗${_RST} $*"; }
_warn() { echo -e "  ${_YLW}!${_RST} $*"; }
_info() { echo -e "  ${_DIM}$*${_RST}"; }

# ---------------------------------------------------------------------------
# Low-level utilities
# ---------------------------------------------------------------------------

_ensure_dirs() { mkdir -p "$DATA_DIR" "$PID_DIR" "$DATA_DIR/traces"; chmod 700 "$DATA_DIR"; }
_pid_file()    { echo "$PID_DIR/$1.pid"; }

_read_pid() {
    local f; f="$(_pid_file "$1")"
    [[ -f "$f" ]] && cat "$f"
}

_is_running() {
    local pid; pid="$(_read_pid "$1")"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

_svc_port() {
    case "$1" in
        backend)  echo "$BACKEND_PORT"  ;;
        mcp)      echo "$MCP_PORT"      ;;
        frontend) echo "$FRONTEND_PORT" ;;
    esac
}

_probe_port() {
    # $1 = port, $2 = optional HTTP health path (e.g. /api/health)
    # With health path: HTTP GET only — verifies the app is fully ready.
    # Without: TCP connect only — checks if anything listens on the port.
    local port="$1" health="${2:-}"
    if [[ -n "$health" ]]; then
        command -v curl &>/dev/null || return 1
        curl -sf --max-time 2 "http://127.0.0.1:${port}${health}" >/dev/null 2>&1
        return $?
    fi
    if command -v nc &>/dev/null; then
        nc -z 127.0.0.1 "$port" 2>/dev/null && return 0
    else
        (echo >/dev/tcp/127.0.0.1/"$port") 2>/dev/null && return 0
    fi
    return 1
}

_check_port_free() {
    # $1 = port, $2 = label
    if _probe_port "$1"; then
        _fail "Port $1 in use ($2). Run './init.sh stop' first."
        return 1
    fi
    return 0
}

_wait_port_free() {
    # Block until port is released or timeout (seconds).
    local port="$1" timeout="$2" t0=$SECONDS
    while (( SECONDS - t0 < timeout )); do
        _probe_port "$port" || return 0
        sleep 0.5
    done
    return 1
}

MAX_LOG_FILES=5

_rotate_log() {
    local log_file="$1"
    local force="${2:-}"
    if [ -f "$log_file" ]; then
        local size
        size=$(stat -c%s "$log_file" 2>/dev/null || stat -f%z "$log_file" 2>/dev/null || echo 0)
        if [ "$size" -gt 10485760 ] || [ "$force" = "force" ]; then
            mv "$log_file" "${log_file}.$(date +%Y%m%d_%H%M%S)"
            # Prune old rotated logs beyond MAX_LOG_FILES
            local count
            count=$(ls -1 "${log_file}."* 2>/dev/null | wc -l)
            if [ "$count" -gt "$MAX_LOG_FILES" ]; then
                ls -1t "${log_file}."* 2>/dev/null | tail -n +$((MAX_LOG_FILES + 1)) | xargs rm -f 2>/dev/null
            fi
        fi
    fi
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

preflight() {
    local ok=true

    if [[ ! -x "$PYTHON" ]]; then
        _fail "Python venv not found at $PYTHON"
        echo -e "       ${_DIM}cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt${_RST}"
        ok=false
    fi

    if [[ ! -x "$UVICORN" ]]; then
        _fail "uvicorn not in venv"
        echo -e "       ${_DIM}cd backend && source .venv/bin/activate && pip install -r requirements.txt${_RST}"
        ok=false
    fi

    if [[ ! -x "$VITE" ]]; then
        _fail "Vite not found at $VITE"
        echo -e "       ${_DIM}cd frontend && npm install${_RST}"
        ok=false
    fi

    if ! command -v node &>/dev/null; then
        _fail "Node.js not on PATH"
        ok=false
    fi

    [[ "$ok" = false ]] && { _log "Preflight failed."; exit 1; }
}

# ---------------------------------------------------------------------------
# Launch (non-blocking — spawn process, write PID file, return immediately)
# ---------------------------------------------------------------------------
# Returns: 0 = launched, 1 = already running, 2 = port conflict

_launch() {
    local name="$1"
    if _is_running "$name"; then
        _warn "$name already running (PID $(_read_pid "$name"))"
        return 1
    fi
    local port; port="$(_svc_port "$name")"
    _check_port_free "$port" "$name" || return 2
    _rotate_log "$DATA_DIR/${name}.log" force

    case "$name" in
        backend)
            cd "$BACKEND_DIR"
            # --reload-dir: restrict file watching to app/ (skips .venv, data, tests)
            # --timeout-graceful-shutdown: allow async lifespan shutdown to complete.
            #   Long-running ops (recluster) survive reloads via BaseException catch
            #   in split.py — structural changes commit before LLM calls, so partial
            #   work persists even if the task is cancelled.
            setsid "$UVICORN" app.main:asgi_app \
                --host 127.0.0.1 --port "$BACKEND_PORT" \
                --reload --reload-dir app \
                --timeout-graceful-shutdown 10 \
                </dev/null >> "$DATA_DIR/backend.log" 2>&1 &
            ;;
        mcp)
            cd "$BACKEND_DIR"
            setsid "$PYTHON" -m app.mcp_server \
                </dev/null >> "$DATA_DIR/mcp.log" 2>&1 &
            ;;
        frontend)
            # Use vite binary directly — avoids npx → sh → node wrapper layers.
            cd "$FRONTEND_DIR"
            setsid "$VITE" dev --port "$FRONTEND_PORT" --host 127.0.0.1 \
                </dev/null >> "$DATA_DIR/frontend.log" 2>&1 &
            ;;
    esac
    echo "$!" > "$(_pid_file "$name")"
    cd "$SCRIPT_DIR"
    return 0
}

# ---------------------------------------------------------------------------
# Await readiness (parallel port polling for all launched services)
# ---------------------------------------------------------------------------

_await_ready() {
    # Polls readiness for named services.  Sets FAILED_SERVICES (global)
    # to the list of services that did not become ready in time.
    local -a names=("$@")
    local -A ready health
    FAILED_SERVICES=()
    for n in "${names[@]}"; do
        ready[$n]=0
        health[$n]=""
    done
    health[backend]="/api/health"

    local t0=$SECONDS max_t=0
    for n in "${names[@]}"; do
        (( ${READY_TIMEOUT[$n]} > max_t )) && max_t=${READY_TIMEOUT[$n]}
    done

    while (( SECONDS - t0 <= max_t )); do
        local pending=false
        for n in "${names[@]}"; do
            (( ${ready[$n]} != 0 )) && continue
            local elapsed=$(( SECONDS - t0 ))
            local port; port="$(_svc_port "$n")"
            local pid; pid="$(_read_pid "$n")"

            # Detect process death during startup
            if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
                ready[$n]=2
                _fail "$n exited during startup — check data/${n}.log"
                continue
            fi

            if _probe_port "$port" "${health[$n]:-}"; then
                ready[$n]=1
                _ok "$n ready ${_DIM}(PID $pid, port $port)${_RST}"
            elif (( elapsed >= ${READY_TIMEOUT[$n]} )); then
                ready[$n]=2
                _warn "$n not responding after ${READY_TIMEOUT[$n]}s — check data/${n}.log"
            else
                pending=true
            fi
        done
        $pending || break
        sleep 1
    done

    # Collect failed services
    for n in "${names[@]}"; do
        if (( ${ready[$n]} == 2 )); then
            FAILED_SERVICES+=("$n")
        fi
    done
}

# ---------------------------------------------------------------------------
# Retry logic — exponential backoff per failed service
# ---------------------------------------------------------------------------

_retry_service() {
    # Retry a single failed service up to 3 times with exponential backoff.
    # Returns 0 on success, 1 on final failure.
    local svc="$1"
    local max_retries=3
    local delay=2

    for attempt in $(seq 1 "$max_retries"); do
        # Stop the failed process FIRST (releases port)
        stop_service "$svc" 2>/dev/null

        # Wait for port to be fully released before retrying
        local port; port="$(_svc_port "$svc")"
        if ! _wait_port_free "$port" 10; then
            _warn "[RETRY $attempt/$max_retries] $svc port $port still in use after 10s"
        fi

        _warn "[RETRY $attempt/$max_retries] $svc — retrying in ${delay}s"
        sleep "$delay"

        _launch "$svc"
        local rc=$?
        case $rc in
            1) return 0 ;;  # already running
            2) return 1 ;;  # port conflict
        esac

        # Wait for just this service
        FAILED_SERVICES=()
        _await_ready "$svc"
        if (( ${#FAILED_SERVICES[@]} == 0 )); then
            return 0  # success
        fi

        delay=$(( delay * 2 ))  # 2s -> 4s -> 8s
    done

    # Final failure
    local last_err
    last_err=$(tail -1 "$DATA_DIR/${svc}.log" 2>/dev/null || echo "no log available")
    _fail "$svc failed after $max_retries retries: $last_err"
    return 1
}

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

start_services() {
    preflight
    _ensure_dirs
    local t0=$SECONDS
    _log "Starting services..."

    # Launch all three processes concurrently (no cross-dependencies at startup).
    local -a to_await=()
    for svc in backend mcp frontend; do
        _launch "$svc"
        case $? in
            0) to_await+=("$svc") ;;   # freshly launched — wait for readiness
            1) ;;                       # already running (warning printed)
            2) exit 1 ;;               # port conflict — abort
        esac
    done

    if (( ${#to_await[@]} > 0 )); then
        _await_ready "${to_await[@]}"
    fi

    # Retry any services that failed initial readiness
    local any_failed=false
    if (( ${#FAILED_SERVICES[@]} > 0 )); then
        _log "Retrying ${#FAILED_SERVICES[@]} failed service(s)..."
        local -a still_failed=()
        for svc in "${FAILED_SERVICES[@]}"; do
            if ! _retry_service "$svc"; then
                still_failed+=("$svc")
                any_failed=true
            fi
        done
        if $any_failed; then
            _fail "Services failed to start: ${still_failed[*]}"
            exit 1
        fi
    fi

    echo ""
    _log "Ready in $(( SECONDS - t0 ))s — logs: data/{backend,frontend,mcp}.log"

    # Auto-setup VS Code bridge (non-fatal, silent when up-to-date)
    _ensure_vscode_bridge
}

# ---------------------------------------------------------------------------
# VS Code bridge — detection, status, and auto-setup
# ---------------------------------------------------------------------------
# Shared by: start_services (auto-install), show_status (display),
#            do_restart (via start_services), setup-vscode (delegated).
#
# State is gathered once per invocation into _VS_* globals, then consumed
# by display or install logic.  All VS Code operations are non-fatal —
# service start/stop never fails due to bridge issues.
# ---------------------------------------------------------------------------

# ── Detection ────────────────────────────────────────────────────

_detect_vscode_bins() {
    # Returns ALL found VS Code binaries (one per line), deduplicated by
    # resolved symlink target.  Handles snap, flatpak, WSL, macOS, custom.
    local -A seen=()

    # Strategy 1: PATH lookup (covers standard, snap symlinks, user aliases)
    for bin in code code-insiders codium code-oss; do
        local path
        path=$(command -v "$bin" 2>/dev/null) || continue
        local resolved
        resolved=$(readlink -f "$path" 2>/dev/null || echo "$path")
        [[ -z "${seen[$resolved]:-}" ]] || continue
        seen[$resolved]=1
        echo "$path"
    done

    # Strategy 2: Known install directories not on PATH
    for dir in /snap/bin /usr/bin /usr/local/bin \
               /usr/share/code/bin /usr/share/code-insiders/bin \
               "$HOME/.local/bin" "$HOME/Applications" \
               "/Applications/Visual Studio Code.app/Contents/Resources/app/bin" \
               "/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin" \
               "/Applications/VSCodium.app/Contents/Resources/app/bin" \
               "/mnt/c/Program Files/Microsoft VS Code/bin"; do
        [[ -d "$dir" ]] || continue
        for bin in code code-insiders codium code-oss; do
            [[ -x "$dir/$bin" ]] || continue
            local resolved
            resolved=$(readlink -f "$dir/$bin" 2>/dev/null || echo "$dir/$bin")
            [[ -z "${seen[$resolved]:-}" ]] || continue
            seen[$resolved]=1
            echo "$dir/$bin"
        done
    done

    # Strategy 3: Flatpak
    if command -v flatpak &>/dev/null; then
        for app_id in com.visualstudio.code com.visualstudio.code.insiders com.vscodium.codium; do
            flatpak info "$app_id" &>/dev/null 2>&1 || continue
            local key="flatpak:$app_id"
            [[ -z "${seen[$key]:-}" ]] || continue
            seen[$key]=1
            echo "flatpak run $app_id"
        done
    fi
}

_run_vscode() {
    # Timeout-guarded VS Code CLI wrapper.  Prevents hangs from WSL interop,
    # remote extensions, or unresponsive snap/flatpak wrappers.
    local cmd="$1"; shift
    if [[ "$cmd" == flatpak\ run\ * ]]; then
        timeout 10 bash -c "$cmd $(printf '%q ' "$@")" 2>/dev/null
    else
        timeout 10 "$cmd" "$@" 2>/dev/null
    fi
}

_vscode_label() {
    # Human-readable label: "code (snap)", "code-insiders", "codium (flatpak)"
    local cmd="$1"
    if [[ "$cmd" == flatpak\ run\ * ]]; then
        echo "${cmd##*run } (flatpak)"
    elif [[ "$cmd" == /snap/* ]]; then
        echo "$(basename "$cmd") (snap)"
    else
        basename "$cmd"
    fi
}

# ── State gathering ──────────────────────────────────────────────

# Globals populated by _gather_vscode_state (called once per invocation)
_VS_GATHERED=false
_VS_BINS=()           # Validated VS Code binaries
_VS_PRIMARY=""        # First working binary (used for display)
_VS_PRIMARY_LABEL=""  # Human label for primary
_VS_PRIMARY_VER=""    # VS Code version of primary
_VS_BRIDGE_VER=""     # Installed bridge version (empty = not installed)
_VS_VSIX_VER=""       # Available .vsix version
_VS_VSIX_PATH=""      # Path to .vsix file
_VS_MCP_JSON=false    # .vscode/mcp.json exists and valid
_VS_SAMPLING_OK=false # sampling pre-approved in settings.json

_gather_vscode_state() {
    # Idempotent — only runs once per process.
    $_VS_GATHERED && return 0
    _VS_GATHERED=true

    # Find .vsix
    _VS_VSIX_PATH=$(ls -t "$SCRIPT_DIR/VSGithub/mcp-copilot-extension"/mcp-copilot-bridge-*.vsix 2>/dev/null | head -1)
    [[ -n "$_VS_VSIX_PATH" ]] && \
        _VS_VSIX_VER=$(basename "$_VS_VSIX_PATH" | sed 's/.*bridge-\(.*\)\.vsix/\1/')

    # Detect binaries — validate each is responsive via _run_vscode (10s timeout)
    local line
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        if _run_vscode "$line" --version >/dev/null 2>&1; then
            _VS_BINS+=("$line")
        fi
    done < <(_detect_vscode_bins 2>/dev/null)

    # Primary binary info
    if (( ${#_VS_BINS[@]} > 0 )); then
        _VS_PRIMARY="${_VS_BINS[0]}"
        _VS_PRIMARY_LABEL=$(_vscode_label "$_VS_PRIMARY")
        _VS_PRIMARY_VER=$(_run_vscode "$_VS_PRIMARY" --version | head -1)

        # Bridge extension version
        _VS_BRIDGE_VER=$(_run_vscode "$_VS_PRIMARY" --list-extensions --show-versions \
                         | grep -i "mcp-copilot-bridge" | sed 's/.*@//' || true)
    fi

    # Config file checks
    local mcp_json="$SCRIPT_DIR/.vscode/mcp.json"
    if [[ -f "$mcp_json" ]] && grep -q '"synthesis_mcp"' "$mcp_json" 2>/dev/null; then
        _VS_MCP_JSON=true
    fi

    local settings="$SCRIPT_DIR/.vscode/settings.json"
    if [[ -f "$settings" ]] && grep -q 'serverSampling' "$settings" 2>/dev/null \
       && grep -q 'synthesis_mcp' "$settings" 2>/dev/null; then
        _VS_SAMPLING_OK=true
    fi
}

# ── Status display ───────────────────────────────────────────────

_show_vscode_status() {
    # Displays VS Code integration status.  Call after _gather_vscode_state.
    # Used by: show_status (full), start_services (compact post-start).
    local mode="${1:-full}"  # "full" or "compact"

    _gather_vscode_state

    if [[ "$mode" == "full" ]]; then
        echo ""
        _log "VS Code integration:"
    fi

    # No VS Code detected
    if (( ${#_VS_BINS[@]} == 0 )); then
        if [[ "$mode" == "full" ]]; then
            echo -e "  ${_DIM}○ vscode    not detected${_RST}"
            echo -e "  ${_DIM}○ bridge    –${_RST}"
            echo -e "  ${_DIM}○ sampling  unavailable${_RST}"
            echo ""
            _info "Install VS Code to unlock the sampling pipeline."
            _info "Copilot's LLM runs full optimization (analyze → optimize"
            _info "→ score → suggest) in your IDE — no API key needed."
        else
            echo ""
            _warn "VS Code not detected — sampling pipeline unavailable"
            _info "Install VS Code + run ./init.sh setup-vscode to enable"
        fi
        return 1
    fi

    # VS Code found — show IDE status
    if [[ "$mode" == "full" ]]; then
        echo -e "  ${_GRN}●${_RST} vscode    ${_DIM}${_VS_PRIMARY_LABEL} v${_VS_PRIMARY_VER}${_RST}"
        if (( ${#_VS_BINS[@]} > 1 )); then
            _info "          + $(( ${#_VS_BINS[@]} - 1 )) other installation(s) detected"
        fi
    fi

    # Bridge extension status
    if [[ -n "$_VS_BRIDGE_VER" ]]; then
        if [[ "$mode" == "full" ]]; then
            if [[ "$_VS_BRIDGE_VER" == "$_VS_VSIX_VER" ]]; then
                echo -e "  ${_GRN}●${_RST} bridge    ${_DIM}v${_VS_BRIDGE_VER} (up to date)${_RST}"
            elif [[ -n "$_VS_VSIX_VER" ]]; then
                echo -e "  ${_YLW}●${_RST} bridge    ${_DIM}v${_VS_BRIDGE_VER} (v${_VS_VSIX_VER} available — run ./init.sh setup-vscode)${_RST}"
            else
                echo -e "  ${_GRN}●${_RST} bridge    ${_DIM}v${_VS_BRIDGE_VER}${_RST}"
            fi
        fi
    else
        if [[ "$mode" == "full" ]]; then
            echo -e "  ${_RED}○${_RST} bridge    ${_DIM}not installed — run ./init.sh setup-vscode${_RST}"
        fi
    fi

    # Sampling pipeline readiness
    if [[ "$mode" == "full" ]]; then
        if [[ -n "$_VS_BRIDGE_VER" ]] && $_VS_SAMPLING_OK; then
            echo -e "  ${_GRN}●${_RST} sampling  ${_DIM}pre-approved, pipeline ready${_RST}"
        elif [[ -n "$_VS_BRIDGE_VER" ]] && ! $_VS_SAMPLING_OK; then
            echo -e "  ${_YLW}●${_RST} sampling  ${_DIM}bridge installed but not pre-approved in settings.json${_RST}"
        else
            echo -e "  ${_DIM}○ sampling  bridge required — run ./init.sh setup-vscode${_RST}"
        fi
    fi

    # Native MCP discovery
    if [[ "$mode" == "full" ]]; then
        if $_VS_MCP_JSON; then
            echo -e "  ${_GRN}●${_RST} mcp.json  ${_DIM}native discovery enabled${_RST}"
        else
            echo -e "  ${_YLW}○${_RST} mcp.json  ${_DIM}missing — run: git checkout .vscode/mcp.json${_RST}"
        fi
    fi

    # Compact mode — single summary line after start/restart
    if [[ "$mode" == "compact" ]]; then
        if [[ -n "$_VS_BRIDGE_VER" ]] && $_VS_SAMPLING_OK; then
            echo ""
            _ok "VS Code bridge v${_VS_BRIDGE_VER} — sampling pipeline ready"
        elif [[ -n "$_VS_BRIDGE_VER" ]]; then
            echo ""
            _ok "VS Code bridge v${_VS_BRIDGE_VER} installed"
        fi
        # If bridge is missing, _ensure_vscode_bridge handles the messaging
    fi

    return 0
}

# ── Auto-install (called after start/restart) ────────────────────

_ensure_vscode_bridge() {
    # Auto-installs or updates the bridge into all detected VS Code binaries.
    # Non-fatal — never blocks service startup.  Silent when up-to-date.

    _gather_vscode_state

    # No .vsix to install
    [[ -z "$_VS_VSIX_PATH" ]] && return 0

    # No VS Code — show hint (unless status already showed it)
    if (( ${#_VS_BINS[@]} == 0 )); then
        _show_vscode_status compact
        return 0
    fi

    # Install/update across all detected installations
    local any_action=false
    local any_failure=false
    for code_cmd in "${_VS_BINS[@]}"; do
        local installed
        installed=$(_run_vscode "$code_cmd" --list-extensions --show-versions 2>/dev/null \
                    | grep -i "mcp-copilot-bridge" | sed 's/.*@//' || true)

        # Already at target version — skip
        [[ "$installed" == "$_VS_VSIX_VER" ]] && continue

        # Print header on first action
        if ! $any_action; then
            echo ""
            any_action=true
        fi

        local label
        label=$(_vscode_label "$code_cmd")
        if [[ -z "$installed" ]]; then
            _log "Installing bridge v${_VS_VSIX_VER} into ${label}..."
        else
            _log "Updating bridge in ${label} (${installed} → ${_VS_VSIX_VER})..."
        fi

        local output
        output=$(_run_vscode "$code_cmd" --install-extension "$_VS_VSIX_PATH" --force 2>&1)
        if [[ $? -eq 0 ]]; then
            _ok "Bridge v${_VS_VSIX_VER} → ${label}"
        else
            any_failure=true
            _warn "Failed for ${label}: ${output%%$'\n'*}"
        fi
    done

    if $any_failure; then
        _info "Retry with: ./init.sh setup-vscode"
    fi

    # After any install/update, re-gather ALL state for accurate display
    if $any_action; then
        _VS_GATHERED=false
        _VS_BINS=()
        _VS_PRIMARY="" _VS_PRIMARY_LABEL="" _VS_PRIMARY_VER=""
        _VS_BRIDGE_VER=""
        _VS_VSIX_VER="" _VS_VSIX_PATH=""
        _VS_MCP_JSON=false _VS_SAMPLING_OK=false
        _gather_vscode_state
    fi

    # Show compact status (bridge version + sampling readiness)
    _show_vscode_status compact
}

# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

stop_service() {
    local name="$1"
    local pid; pid="$(_read_pid "$name")"

    # Stale PID file — try pattern match as fallback
    if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
        case "$name" in
            backend)  pid=$(pgrep -f -u "$(id -u)" "uvicorn app.main:asgi_app" 2>/dev/null | head -1) ;;
            mcp)      pid=$(pgrep -f -u "$(id -u)" "python.*app\.mcp_server" 2>/dev/null | head -1) ;;
            frontend) pid=$(pgrep -f -u "$(id -u)" "vite dev.*${FRONTEND_PORT}" 2>/dev/null | head -1) ;;
        esac
    fi

    if [[ -z "$pid" ]]; then
        echo -e "  ${_DIM}– $name already stopped${_RST}"
        rm -f "$(_pid_file "$name")"
        return 0
    fi

    local timeout=${STOP_TIMEOUT[$name]}

    # Phase 1: SIGTERM to the process only (not the process group).
    # For uvicorn --reload this lets the supervisor forward SIGTERM to the
    # worker, which runs the async lifespan shutdown (routing, extraction
    # tasks with 5s wait_for, warm-path timer, strategy file watcher).
    # Sending SIGTERM to the entire group simultaneously would bypass the
    # supervisor's orderly child shutdown and cause force-kills.
    kill "$pid" 2>/dev/null
    local t0=$SECONDS
    while (( SECONDS - t0 < timeout )) && kill -0 "$pid" 2>/dev/null; do
        sleep 0.5
    done

    # Phase 2: SIGKILL the entire process group if still alive.
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        sleep 0.2
        _warn "$name force-killed (PID $pid)"
    else
        _ok "$name stopped (PID $pid)"
    fi

    rm -f "$(_pid_file "$name")"

    # Phase 3: Kill orphaned workers still holding the port.
    # uvicorn --reload runs supervisor + worker in the same process group
    # (via setsid).  If the supervisor exits before the worker finishes
    # its async lifespan shutdown, the port stays in use.  Catch these
    # strays by checking the port after the PID is gone.
    local port; port="$(_svc_port "$name")"
    if _probe_port "$port" && command -v lsof &>/dev/null; then
        local stray
        stray=$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null | head -1)
        if [[ -n "$stray" ]]; then
            # Re-verify the PID still holds the port (avoid TOCTOU race)
            local verify
            verify=$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null | head -1)
            if [[ "$verify" == "$stray" ]]; then
                kill "$stray" 2>/dev/null
                local w=0
                while (( w < 3 )) && kill -0 "$stray" 2>/dev/null; do
                    sleep 0.5; (( w++ ))
                done
                if kill -0 "$stray" 2>/dev/null; then
                    kill -9 "$stray" 2>/dev/null
                fi
                _warn "$name orphan worker killed (PID $stray, port $port)"
            fi
        fi
    fi
}

stop_services() {
    _log "Stopping services..."
    # Drain order: frontend (user traffic) → MCP (tool calls) → backend (data layer)
    stop_service frontend
    stop_service mcp
    stop_service backend
}

# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------

do_restart() {
    stop_services

    # Verify ports are released.  Backend lifespan shutdown can take
    # up to 25s (taxonomy drain + warm path cancel + extraction tasks),
    # so allow 15s for port release — enough for graceful shutdown to
    # complete, short enough to surface stuck processes quickly.
    local need_wait=false
    for p in $BACKEND_PORT $MCP_PORT $FRONTEND_PORT; do
        _probe_port "$p" && { need_wait=true; break; }
    done
    if $need_wait; then
        echo -e "  ${_DIM}Waiting for ports to release...${_RST}"
        for p in $BACKEND_PORT $MCP_PORT $FRONTEND_PORT; do
            _wait_port_free "$p" 15 || { _fail "Port $p still in use after 15s"; exit 1; }
        done
    fi

    start_services
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

show_status() {
    _log "Service status:"
    for name in backend mcp frontend; do
        local pid port health_path=""
        pid="$(_read_pid "$name")"
        port="$(_svc_port "$name")"
        [[ "$name" = "backend" ]] && health_path="/api/health"

        local padded
        printf -v padded '%-9s' "$name"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            if _probe_port "$port" "$health_path"; then
                echo -e "  ${_GRN}●${_RST} ${padded}${_DIM}pid $pid  port $port${_RST}"
            else
                echo -e "  ${_YLW}●${_RST} ${padded}${_DIM}pid $pid  port $port  (not responding)${_RST}"
            fi
        else
            echo -e "  ${_DIM}○ ${padded}stopped${_RST}"
            [[ -n "$pid" ]] && rm -f "$(_pid_file "$name")"
        fi
    done

    _show_vscode_status full
    return 0
}

# ---------------------------------------------------------------------------
# Logs (tail all available)
# ---------------------------------------------------------------------------

show_logs() {
    local -a files=()
    for f in "$DATA_DIR"/{backend,frontend,mcp}.log; do
        [[ -f "$f" ]] && files+=("$f")
    done
    if (( ${#files[@]} == 0 )); then
        _warn "No log files found in $DATA_DIR/"
        return 1
    fi
    tail -f "${files[@]}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

case "${1:-start}" in
    start)   start_services ;;
    stop)    stop_services ;;
    restart) do_restart ;;
    status)  show_status ;;
    logs)    show_logs ;;
    setup-vscode) shift; "$SCRIPT_DIR/scripts/setup-vscode.sh" "$@" ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|setup-vscode}"
        echo ""
        echo "  start         Start all services (backend, MCP, frontend)"
        echo "  stop          Graceful stop (SIGTERM → wait → SIGKILL)"
        echo "  restart       Stop then start"
        echo "  status        Show service health with PIDs"
        echo "  logs          Tail all service logs"
        echo "  setup-vscode  Install VS Code bridge extension for sampling pipeline"
        exit 1
        ;;
esac
