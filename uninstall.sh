#!/usr/bin/env bash
# Daedalus Uninstall Script
# Safely removes Daedalus and optionally cleans up data
# Created by: orpheus497

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/daedelus"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/daedelus"
MODELS_DIR="${HOME}/.local/share/models"
VENV_DIR="./venv"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   Daedalus Uninstall Script${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Function to ask yes/no questions
ask_yes_no() {
    local prompt="$1"
    local default="${2:-n}"

    while true; do
        if [ "$default" = "y" ]; then
            read -p "$(echo -e ${YELLOW}$prompt [Y/n]: ${NC})" yn
            yn=${yn:-y}
        else
            read -p "$(echo -e ${YELLOW}$prompt [y/N]: ${NC})" yn
            yn=${yn:-n}
        fi

        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

# 1. Stop the daemon if running
echo -e "${BLUE}[1/6]${NC} Checking for running daemon..."
if command -v daedelus &> /dev/null; then
    if daedelus status &> /dev/null; then
        echo -e "${YELLOW}Stopping daemon...${NC}"
        daedelus stop || true
        sleep 1
    fi
fi
echo -e "${GREEN}✓${NC} Daemon stopped"
echo ""

# 2. Remove shell integration
echo -e "${BLUE}[2/6]${NC} Removing shell integration..."
echo -e "${YELLOW}Please manually remove these lines from your shell config:${NC}"
echo ""
echo -e "  ${RED}# From ~/.zshrc:${NC}"
echo -e "  ${RED}source \$(daedelus shell-integration zsh)${NC}"
echo ""
echo -e "  ${RED}# From ~/.bashrc:${NC}"
echo -e "  ${RED}source \$(daedelus shell-integration bash)${NC}"
echo ""
echo -e "  ${RED}# From ~/.config/fish/config.fish:${NC}"
echo -e "  ${RED}source (daedelus shell-integration fish)${NC}"
echo ""

if ask_yes_no "Have you removed the shell integration?" "n"; then
    echo -e "${GREEN}✓${NC} Shell integration noted for removal"
else
    echo -e "${YELLOW}⚠${NC}  Remember to remove shell integration manually!"
fi
echo ""

# 3. Uninstall Python package
echo -e "${BLUE}[3/6]${NC} Uninstalling daedelus package..."
if pip show daedelus &> /dev/null; then
    echo -e "${YELLOW}Uninstalling via pip...${NC}"
    pip uninstall -y daedelus || true
    echo -e "${GREEN}✓${NC} Package uninstalled"
else
    echo -e "${YELLOW}Package not found in pip (may be dev install)${NC}"
fi

# Remove virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    if ask_yes_no "Remove virtual environment at $VENV_DIR?" "y"; then
        rm -rf "$VENV_DIR"
        echo -e "${GREEN}✓${NC} Virtual environment removed"
    fi
fi
echo ""

# 4. Remove configuration
echo -e "${BLUE}[4/6]${NC} Configuration files..."
if [ -d "$CONFIG_DIR" ]; then
    echo -e "  Found: ${CONFIG_DIR}"
    if ask_yes_no "Remove configuration files?" "y"; then
        rm -rf "$CONFIG_DIR"
        echo -e "${GREEN}✓${NC} Configuration removed"
    else
        echo -e "${YELLOW}⚠${NC}  Configuration kept at: $CONFIG_DIR"
    fi
else
    echo -e "${GREEN}✓${NC} No configuration found"
fi
echo ""

# 5. Remove data
echo -e "${BLUE}[5/6]${NC} Data files..."
if [ -d "$DATA_DIR" ]; then
    # Calculate size
    DATA_SIZE=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
    echo -e "  Found: ${DATA_DIR} (${DATA_SIZE})"
    echo -e "${YELLOW}  This includes:${NC}"
    echo -e "    - Command history database"
    echo -e "    - Learned embedding models"
    echo -e "    - Vector indices"
    echo -e "    - Daemon logs"

    if ask_yes_no "Remove ALL data? (Cannot be undone!)" "n"; then
        rm -rf "$DATA_DIR"
        echo -e "${GREEN}✓${NC} Data removed"
    else
        echo -e "${YELLOW}⚠${NC}  Data kept at: $DATA_DIR"
        echo -e "${YELLOW}   You can manually remove it later if needed${NC}"
    fi
else
    echo -e "${GREEN}✓${NC} No data found"
fi
echo ""

# 6. Remove LLM models
echo -e "${BLUE}[6/6]${NC} LLM models..."
DAEDELUS_MODEL="${MODELS_DIR}/model.gguf"
if [ -f "$DAEDELUS_MODEL" ]; then
    MODEL_SIZE=$(du -sh "$DAEDELUS_MODEL" 2>/dev/null | cut -f1)
    echo -e "  Found: ${DAEDELUS_MODEL} (${MODEL_SIZE})"
    echo -e "${YELLOW}  Note: This is in a shared models directory${NC}"
    echo -e "${YELLOW}  Other applications may use ~/.local/share/models/${NC}"

    if ask_yes_no "Remove daedelus LLM model?" "n"; then
        rm -f "$DAEDELUS_MODEL"
        echo -e "${GREEN}✓${NC} Model removed"

        # Check if models directory is empty
        if [ -d "$MODELS_DIR" ] && [ -z "$(ls -A $MODELS_DIR 2>/dev/null)" ]; then
            if ask_yes_no "Models directory is empty. Remove it?" "y"; then
                rmdir "$MODELS_DIR"
                echo -e "${GREEN}✓${NC} Models directory removed"
            fi
        fi
    else
        echo -e "${YELLOW}⚠${NC}  Model kept at: $DAEDELUS_MODEL"
    fi
elif [ -d "$MODELS_DIR" ]; then
    echo -e "${YELLOW}⚠${NC}  Models directory exists but no daedelus model found"
else
    echo -e "${GREEN}✓${NC} No LLM models found"
fi
echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}   Uninstall Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Final Steps:${NC}"
echo -e "  1. Restart your shell or run: ${BLUE}source ~/.zshrc${NC} (or ~/.bashrc)"
echo -e "  2. Remove shell integration lines (if not done yet)"
echo ""

# Check what remains
REMAINS=""
[ -d "$CONFIG_DIR" ] && REMAINS="${REMAINS}\n  - Config: $CONFIG_DIR"
[ -d "$DATA_DIR" ] && REMAINS="${REMAINS}\n  - Data: $DATA_DIR"
[ -f "$DAEDELUS_MODEL" ] && REMAINS="${REMAINS}\n  - Model: $DAEDELUS_MODEL"

if [ -n "$REMAINS" ]; then
    echo -e "${YELLOW}Files kept (you chose not to remove):${NC}"
    echo -e "$REMAINS"
    echo ""
    echo -e "${YELLOW}You can manually remove these later if desired.${NC}"
else
    echo -e "${GREEN}All daedelus files removed!${NC}"
fi

echo ""
echo -e "${BLUE}Thank you for trying Daedalus!${NC}"
echo -e "Feedback and issues: ${BLUE}https://github.com/orpheus497/daedelus/issues${NC}"
echo ""
