#!/bin/bash
# Daedelus Daemon Cleanup Script
# Ensures clean slate before installation by removing old daemons and stale files
# Created by: orpheus497

set -e

echo "=========================================="
echo "Daedelus Cleanup Script"
echo "=========================================="
echo ""
echo "🧹 Cleaning up existing Daedelus installations..."
echo ""

# Function to safely check and stop daemon
stop_daemon_safe() {
    local cmd=$1
    if command -v "$cmd" &> /dev/null; then
        echo "  → Found '$cmd' command, attempting to stop daemon..."
        "$cmd" stop 2>/dev/null || true
        sleep 0.5
    fi
}

# 1. Stop any running daemons using CLI commands
echo "[1/5] Stopping daemons via CLI..."
stop_daemon_safe "daedelus"
stop_daemon_safe "deus"

# 2. Kill any orphaned daemon processes by name
echo "[2/5] Killing orphaned daemon processes..."
pkill -9 -f "daedelus.daemon.daemon" 2>/dev/null && echo "  → Killed daedelus.daemon.daemon processes" || echo "  → No orphaned processes found"
pkill -9 -f "daedelus-daemon" 2>/dev/null && echo "  → Killed daedelus-daemon processes" || true
pkill -9 -f "deus-daemon" 2>/dev/null && echo "  → Killed deus-daemon processes" || true

# 3. Remove stale runtime files (PID, sockets)
echo "[3/5] Removing stale runtime files..."

# Check multiple possible locations
RUNTIME_DIRS=(
    "$HOME/.local/share/daedelus/runtime"
    "$HOME/.local/share/daedalus/runtime"
    "/tmp/daedelus"
    "/var/run/daedelus"
)

for dir in "${RUNTIME_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "  → Cleaning $dir"
        rm -f "$dir/daemon.pid" 2>/dev/null || true
        rm -f "$dir/daemon.sock" 2>/dev/null || true
        rm -f "$dir"/*.pid 2>/dev/null || true
        rm -f "$dir"/*.sock 2>/dev/null || true
    fi
done

# Also check XDG_RUNTIME_DIR
if [ -n "$XDG_RUNTIME_DIR" ]; then
    rm -f "$XDG_RUNTIME_DIR/daedelus/"*.pid 2>/dev/null || true
    rm -f "$XDG_RUNTIME_DIR/daedelus/"*.sock 2>/dev/null || true
fi

echo "  → Runtime files cleaned"

# 4. Remove deprecated GPL-licensed dependencies
echo "[4/5] Removing deprecated dependencies..."

# Detect pip command
if command -v pip3 &> /dev/null; then
    PIP_CMD=pip3
elif command -v pip &> /dev/null; then
    PIP_CMD=pip
else
    echo "  ⚠️  Warning: pip not found, skipping dependency cleanup"
    PIP_CMD=""
fi

if [ -n "$PIP_CMD" ]; then
    # Check if deprecated packages are installed
    THEFUZZ_INSTALLED=$($PIP_CMD list 2>/dev/null | grep -i "^thefuzz " | wc -l)
    LEVENSHTEIN_INSTALLED=$($PIP_CMD list 2>/dev/null | grep -i "^python-Levenshtein " | wc -l)
    
    if [ "$THEFUZZ_INSTALLED" -gt 0 ] || [ "$LEVENSHTEIN_INSTALLED" -gt 0 ]; then
        echo "  → Removing deprecated GPL dependencies (thefuzz, python-Levenshtein)..."
        $PIP_CMD uninstall -y thefuzz python-Levenshtein 2>/dev/null || true
        echo "  → Deprecated dependencies removed"
    else
        echo "  → No deprecated dependencies found"
    fi
fi

# 5. Clean up any zombie processes (rare, but possible)
echo "[5/5] Checking for zombie processes..."
ZOMBIE_COUNT=$(ps aux | grep -i daedelus | grep -i defunct | wc -l)
if [ "$ZOMBIE_COUNT" -gt 0 ]; then
    echo "  ⚠️  Warning: Found $ZOMBIE_COUNT zombie processes"
    echo "  → These will be cleaned up automatically on next reboot"
else
    echo "  → No zombie processes found"
fi

echo ""
echo "=========================================="
echo "✅ Cleanup Complete!"
echo "=========================================="
echo ""
echo "All existing Daedelus daemons stopped"
echo "Stale runtime files removed"
echo "Deprecated dependencies cleaned"
echo ""
echo "Ready for fresh installation."
echo ""
