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

# Pre-installation cleanup
echo "=========================================="
echo "Pre-Installation Cleanup"
echo "=========================================="
echo ""

if [ -f "./scripts/cleanup-daemon.sh" ]; then
    echo "Running cleanup script..."
    bash ./scripts/cleanup-daemon.sh
else
    echo "⚠️  Cleanup script not found, performing basic cleanup..."
    # Inline cleanup if script doesn't exist
    if command -v daedelus &> /dev/null; then
        daedelus stop 2>/dev/null || true
    fi
    if command -v deus &> /dev/null; then
        deus stop 2>/dev/null || true
    fi
    pkill -9 -f "daedelus.daemon.daemon" 2>/dev/null || true
    
    # Remove deprecated dependencies
    if command -v pip3 &> /dev/null; then
        pip3 uninstall -y thefuzz python-Levenshtein 2>/dev/null || true
    elif command -v pip &> /dev/null; then
        pip uninstall -y thefuzz python-Levenshtein 2>/dev/null || true
    fi
    echo "✓ Basic cleanup complete"
fi

echo ""
echo "=========================================="
echo "Installing Daedelus..."
echo "=========================================="
echo ""

# Upgrade pip first
echo "[1/4] Upgrading pip and build tools..."
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel

# Install with all dependencies
echo "[2/4] Installing Daedelus with all dependencies..."
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
echo "[3/4] Verifying installation..."
if command -v daedelus &> /dev/null; then
    echo ""
    
    # Post-installation verification
    echo "[4/4] Post-installation verification..."
    
    # Verify deprecated dependencies are gone
    if command -v pip3 &> /dev/null; then
        PIP_CMD=pip3
    elif command -v pip &> /dev/null; then
        PIP_CMD=pip
    fi
    
    THEFUZZ_CHECK=$($PIP_CMD list 2>/dev/null | grep -i "^thefuzz " | wc -l)
    RAPIDFUZZ_CHECK=$($PIP_CMD list 2>/dev/null | grep -i "^rapidfuzz " | wc -l)
    
    if [ "$THEFUZZ_CHECK" -gt 0 ]; then
        echo "⚠️  Warning: Deprecated 'thefuzz' still installed (will be auto-removed on next run)"
    fi
    
    if [ "$RAPIDFUZZ_CHECK" -eq 0 ]; then
        echo "⚠️  Warning: 'rapidfuzz' not installed (installation may have failed)"
    else
        echo "✓ Dependencies verified (rapidfuzz installed)"
    fi
    
    # Verify no daemons running
    DAEMON_COUNT=$(pgrep -f "daedelus.daemon.daemon" | wc -l)
    if [ "$DAEMON_COUNT" -gt 0 ]; then
        echo "✓ Clean environment (no stale daemons)"
    fi
    
    echo ""
    echo "=========================================="
    echo "✅ Installation Complete!"
    echo "=========================================="
    echo ""

    # Offer to run setup automatically
    read -p "Run 'daedelus setup' now? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        echo ""
        echo "Running daedelus setup..."
        daedelus setup || {
            echo "⚠️  Setup encountered an error, but you can run it manually later"
        }
        echo ""
    fi

    # Detect user's shell
    USER_SHELL=$(basename "$SHELL")
    echo "Detected shell: $USER_SHELL"
    echo ""

    # Offer to add shell integration automatically
    if [[ "$USER_SHELL" == "zsh" ]] || [[ "$USER_SHELL" == "bash" ]] || [[ "$USER_SHELL" == "fish" ]]; then
        echo "Shell integration can be automatically added to your shell config."
        read -p "Add shell integration to your $USER_SHELL config? (Y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            if [[ "$USER_SHELL" == "zsh" ]]; then
                RC_FILE="$HOME/.zshrc"
                INTEGRATION_LINE="source \$(daedelus shell-integration zsh)"
            elif [[ "$USER_SHELL" == "bash" ]]; then
                RC_FILE="$HOME/.bashrc"
                INTEGRATION_LINE="source \$(daedelus shell-integration bash)"
            elif [[ "$USER_SHELL" == "fish" ]]; then
                RC_FILE="$HOME/.config/fish/config.fish"
                INTEGRATION_LINE="source (daedelus shell-integration fish)"
                mkdir -p "$HOME/.config/fish"
            fi

            # Check if already added
            if grep -q "daedelus shell-integration" "$RC_FILE" 2>/dev/null; then
                echo "✓ Shell integration already present in $RC_FILE"
            else
                echo "" >> "$RC_FILE"
                echo "# Daedelus shell integration" >> "$RC_FILE"
                echo "$INTEGRATION_LINE" >> "$RC_FILE"
                echo "✓ Added shell integration to $RC_FILE"
                echo ""
                echo "⚠️  Please restart your shell or run:"
                echo "   source $RC_FILE"
            fi
        else
            echo ""
            echo "To add shell integration manually later:"
            echo "  ZSH:  Add to ~/.zshrc:  source \$(daedelus shell-integration zsh)"
            echo "  Bash: Add to ~/.bashrc: source \$(daedelus shell-integration bash)"
            echo "  Fish: Add to config:    source (daedelus shell-integration fish)"
        fi
    else
        echo "Shell integration:"
        echo "  ZSH:  Add to ~/.zshrc:  source \$(daedelus shell-integration zsh)"
        echo "  Bash: Add to ~/.bashrc: source \$(daedelus shell-integration bash)"
        echo "  Fish: Add to config:    source (daedelus shell-integration fish)"
    fi

    echo ""

    # Offer to start daemon
    read -p "Start the Daedelus daemon now? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        echo ""
        echo "Starting daemon..."
        daedelus start --background || {
            echo "⚠️  Failed to start daemon. You can start it manually with:"
            echo "   daedelus start"
        }
    else
        echo ""
        echo "To start the daemon later, run:"
        echo "  daedelus start"
    fi

    echo ""
    echo "=========================================="
    echo "Installation and Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Quick commands:"
    echo "  daedelus status      # Check daemon status"
    echo "  daedelus repl        # Launch interactive mode"
    echo "  daedelus --help      # See all commands"
    echo ""
    echo "For systemd auto-start on boot:"
    echo "  ./scripts/install-systemd-service.sh"
    echo ""
else
    echo ""
    echo "⚠️  Warning: 'daedelus' command not found in PATH"
    echo "   Activate your virtual environment: source venv/bin/activate"
    echo ""
fi
