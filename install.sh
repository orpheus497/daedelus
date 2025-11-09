#!/bin/bash
# Daedalus Installation Script
# Handles installation of all dependencies including FastText

set -e  # Exit on error

echo "=========================================="
echo "Daedalus Installation Script"
echo "=========================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if running in virtual environment (recommended)
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Recommended: python -m venv venv && source venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Installing dependencies..."
echo ""

# Install build dependencies first
echo "[1/4] Installing build dependencies..."
python -m pip install --upgrade pip setuptools wheel pybind11 numpy

# Install FastText separately with proper build environment
echo "[2/4] Installing FastText..."
python -m pip install pybind11-global
python -m pip install fasttext==0.9.2 || {
    echo "⚠️  FastText installation failed. Trying alternative method..."
    python -m pip install --no-build-isolation fasttext==0.9.2 || {
        echo "❌ FastText installation failed."
        echo "   You may need to install it manually or use a different Python version."
        echo "   Continuing with other dependencies..."
    }
}

# Install other dependencies
echo "[3/4] Installing other dependencies..."
python -m pip install annoy prompt-toolkit ptyprocess platformdirs pyyaml click

# Install Daedalus in development mode
echo "[4/4] Installing Daedalus..."
python -m pip install -e . || {
    echo "⚠️  Development install failed, trying alternative..."
    export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
    echo "Added to PYTHONPATH: $(pwd)/src"
}

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Run 'daedelus setup' to initialize"
echo "  2. Run 'daedelus start' to start the daemon"
echo "  3. Add shell integration to your .zshrc or .bashrc"
echo ""
echo "For shell integration:"
echo "  ZSH:  source \$(daedelus shell-integration zsh)"
echo "  Bash: source \$(daedelus shell-integration bash)"
echo "  Fish: source (daedelus shell-integration fish)"
echo ""
