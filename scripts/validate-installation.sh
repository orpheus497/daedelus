#!/bin/bash
# Daedelus Installation Validation Script
# Verifies that installation completed successfully
# Created by: orpheus497

set -e

echo "=========================================="
echo "Daedelus Installation Validation"
echo "=========================================="
echo ""

PASSED=0
FAILED=0
WARNINGS=0

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

print_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

# 1. Check Python version
echo "[1/10] Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
    
    if [[ $PYTHON_MAJOR -ge 3 ]] && [[ $PYTHON_MINOR -ge 10 ]]; then
        print_pass "Python $PYTHON_VERSION (meets requirement: 3.10+)"
    else
        print_fail "Python $PYTHON_VERSION (requires 3.10+)"
    fi
else
    print_fail "Python3 not found"
fi
echo ""

# 2. Check if daedelus command is available
echo "[2/10] Checking daedelus CLI..."
if command -v daedelus &> /dev/null; then
    print_pass "daedelus command found"
    DAEDELUS_VERSION=$(daedelus --version 2>&1 || echo "unknown")
    echo "   Version: $DAEDELUS_VERSION"
else
    print_fail "daedelus command not found in PATH"
fi

if command -v deus &> /dev/null; then
    print_pass "deus alias found"
else
    print_warn "deus alias not found (optional)"
fi
echo ""

# 3. Check core dependencies
echo "[3/10] Checking core dependencies..."
PYTHON_CMD=$(command -v python3 || command -v python)

check_package() {
    if $PYTHON_CMD -c "import $1" 2>/dev/null; then
        print_pass "$1 installed"
    else
        print_fail "$1 not installed"
    fi
}

check_package "fasttext"
check_package "annoy"
check_package "click"
check_package "rich"
check_package "textual"
echo ""

# 4. Check if deprecated dependencies are removed
echo "[4/10] Checking for deprecated dependencies..."
if command -v pip3 &> /dev/null; then
    PIP_CMD=pip3
elif command -v pip &> /dev/null; then
    PIP_CMD=pip
fi

if [ -n "$PIP_CMD" ]; then
    THEFUZZ_INSTALLED=$($PIP_CMD list 2>/dev/null | grep -i "^thefuzz " | wc -l)
    LEVENSHTEIN_INSTALLED=$($PIP_CMD list 2>/dev/null | grep -i "^python-Levenshtein " | wc -l)
    
    if [ "$THEFUZZ_INSTALLED" -eq 0 ] && [ "$LEVENSHTEIN_INSTALLED" -eq 0 ]; then
        print_pass "No deprecated GPL dependencies found"
    else
        if [ "$THEFUZZ_INSTALLED" -gt 0 ]; then
            print_warn "thefuzz (GPL) still installed"
        fi
        if [ "$LEVENSHTEIN_INSTALLED" -gt 0 ]; then
            print_warn "python-Levenshtein (GPL) still installed"
        fi
    fi
    
    # Check for rapidfuzz replacement
    RAPIDFUZZ_INSTALLED=$($PIP_CMD list 2>/dev/null | grep -i "^rapidfuzz " | wc -l)
    if [ "$RAPIDFUZZ_INSTALLED" -gt 0 ]; then
        print_pass "rapidfuzz (MIT) installed"
    else
        print_fail "rapidfuzz not installed"
    fi
fi
echo ""

# 5. Check configuration directory
echo "[5/10] Checking configuration..."
CONFIG_DIR="$HOME/.config/daedelus"
if [ -d "$CONFIG_DIR" ]; then
    print_pass "Config directory exists: $CONFIG_DIR"
else
    print_warn "Config directory not yet created (run 'daedelus setup')"
fi
echo ""

# 6. Check data directory
echo "[6/10] Checking data directory..."
DATA_DIR="$HOME/.local/share/daedelus"
if [ -d "$DATA_DIR" ]; then
    print_pass "Data directory exists: $DATA_DIR"
else
    print_warn "Data directory not yet created (run 'daedelus setup')"
fi
echo ""

# 7. Check for running daemons
echo "[7/10] Checking for stale daemons..."
DAEMON_COUNT=$(pgrep -f "daedelus.daemon.daemon" 2>/dev/null | wc -l)
if [ "$DAEMON_COUNT" -eq 0 ]; then
    print_pass "No stale daemon processes"
else
    print_warn "Found $DAEMON_COUNT daemon process(es) running"
    echo "   Run 'daedelus stop' to stop them"
fi
echo ""

# 8. Check for stale PID/socket files
echo "[8/10] Checking for stale runtime files..."
PID_FILE="$HOME/.local/share/daedelus/runtime/daemon.pid"
SOCKET_FILE="$HOME/.local/share/daedelus/runtime/daemon.sock"

STALE_FILES=0
if [ -f "$PID_FILE" ]; then
    print_warn "Stale PID file exists"
    ((STALE_FILES++))
fi

if [ -S "$SOCKET_FILE" ]; then
    print_warn "Stale socket file exists"
    ((STALE_FILES++))
fi

if [ "$STALE_FILES" -eq 0 ]; then
    print_pass "No stale runtime files"
fi
echo ""

# 9. Check LLM dependencies (optional)
echo "[9/10] Checking LLM dependencies (optional)..."
if $PYTHON_CMD -c "import llama_cpp" 2>/dev/null; then
    print_pass "llama-cpp-python installed (Phase 2 enabled)"
else
    print_warn "llama-cpp-python not installed (Phase 2 disabled)"
fi

if $PYTHON_CMD -c "import transformers" 2>/dev/null; then
    print_pass "transformers installed"
else
    print_warn "transformers not installed (PEFT disabled)"
fi
echo ""

# 10. Check scripts
echo "[10/10] Checking installation scripts..."
SCRIPT_DIR="./scripts"
if [ -f "$SCRIPT_DIR/cleanup-daemon.sh" ]; then
    print_pass "cleanup-daemon.sh exists"
else
    print_warn "cleanup-daemon.sh not found"
fi

if [ -f "$SCRIPT_DIR/remove-deprecated-deps.sh" ]; then
    print_pass "remove-deprecated-deps.sh exists"
else
    print_warn "remove-deprecated-deps.sh not found"
fi
echo ""

# Summary
echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo -e "${GREEN}Passed:${NC}   $PASSED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "${RED}Failed:${NC}   $FAILED"
echo ""

if [ "$FAILED" -eq 0 ]; then
    echo "✅ Installation appears successful!"
    echo ""
    echo "Next steps:"
    echo "  1. Run 'daedelus setup' to initialize configuration"
    echo "  2. Run 'daedelus start' to start the daemon"
    echo "  3. Add shell integration to your ~/.bashrc or ~/.zshrc"
    echo ""
    exit 0
else
    echo "❌ Installation has issues that need attention."
    echo ""
    echo "Run './install.sh' again or check documentation."
    echo ""
    exit 1
fi
