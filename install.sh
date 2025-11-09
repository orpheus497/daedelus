#!/bin/bash
# Daedelus Installation Script
# Handles installation of all dependencies
# Compatible with Python 3.10+ on Linux, macOS, BSD

set -e  # Exit on error

echo "=========================================="
echo "Daedelus Installation Script"
echo "=========================================="
echo ""

# Detect Python command (python3 or python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "❌ Error: Python not found. Please install Python 3.10 or later."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')
echo "✓ Python version: $PYTHON_VERSION"

# Verify minimum Python version (3.10+)
if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 10 ]]; then
    echo "❌ Error: Python 3.10 or later required. Found: $PYTHON_VERSION"
    exit 1
fi

# Check if running in virtual environment (recommended)
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo ""
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Recommended: $PYTHON_CMD -m venv venv && source venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for C++ compiler (required for FastText and llama-cpp-python)
if ! command -v g++ &> /dev/null; then
    echo ""
    echo "❌ Error: g++ compiler not found."
    echo "   Required for building FastText and llama-cpp-python"
    echo ""
    echo "   Install build tools:"
    echo "   - Fedora:        sudo dnf install gcc-c++ python3-devel"
    echo "   - Debian/Ubuntu: sudo apt install build-essential python3-dev"
    echo "   - macOS:         xcode-select --install"
    exit 1
fi

echo "✓ Build tools found"
echo ""
echo "Installing Daedelus..."
echo ""

# Upgrade pip first
echo "[1/3] Upgrading pip and build tools..."
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel

# Install with all dependencies
echo "[2/3] Installing Daedelus with all dependencies..."
$PYTHON_CMD -m pip install -e . || {
    echo ""
    echo "❌ Installation failed."
    echo ""
    echo "Common issues:"
    echo "  - Missing C++ compiler (see above)"
    echo "  - Insufficient permissions (try adding --user flag)"
    echo "  - Network issues (check internet connection)"
    echo ""
    exit 1
}

# Verify installation
echo "[3/3] Verifying installation..."
if command -v daedelus &> /dev/null; then
    echo ""
    echo "=========================================="
    echo "✅ Installation Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Run 'daedelus setup' to initialize"
    echo "  2. Run 'daedelus start' to start the daemon"
    echo "  3. Add shell integration to your shell RC file"
    echo ""
    echo "Shell integration:"
    echo "  ZSH:  Add to ~/.zshrc:  source \$(daedelus shell-integration zsh)"
    echo "  Bash: Add to ~/.bashrc: source \$(daedelus shell-integration bash)"
    echo "  Fish: Add to config:    source (daedelus shell-integration fish)"
    echo ""
else
    echo ""
    echo "⚠️  Warning: 'daedelus' command not found in PATH"
    echo "   Activate your virtual environment: source venv/bin/activate"
    echo ""
fi
