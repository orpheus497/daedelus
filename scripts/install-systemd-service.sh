#!/usr/bin/env bash
# Install Daedelus systemd service for current user
# This allows Daedelus daemon to start automatically on boot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Installing Daedelus systemd service...${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo -e "${RED}ERROR: Do not run this script as root!${NC}"
   echo "This script installs a user service, run it as your regular user."
   exit 1
fi

# Create user systemd directory if it doesn't exist
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

# Copy service file
SERVICE_FILE="${PROJECT_ROOT}/systemd/daedelus.service"
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}ERROR: Service file not found: ${SERVICE_FILE}${NC}"
    exit 1
fi

cp "$SERVICE_FILE" "${SYSTEMD_USER_DIR}/daedelus.service"
echo -e "${GREEN}✓${NC} Service file copied to ${SYSTEMD_USER_DIR}"

# Reload systemd daemon
systemctl --user daemon-reload
echo -e "${GREEN}✓${NC} Systemd daemon reloaded"

# Enable the service
systemctl --user enable daedelus.service
echo -e "${GREEN}✓${NC} Service enabled (will start on boot)"

# Enable lingering (allows user services to run when not logged in)
loginctl enable-linger "$USER"
echo -e "${GREEN}✓${NC} User lingering enabled"

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Available commands:"
echo "  systemctl --user start daedelus     # Start daemon now"
echo "  systemctl --user stop daedelus      # Stop daemon"
echo "  systemctl --user status daedelus    # Check status"
echo "  systemctl --user restart daedelus   # Restart daemon"
echo "  systemctl --user disable daedelus   # Disable auto-start"
echo ""
echo -e "${YELLOW}Note:${NC} The daemon will now start automatically on boot."
echo "To start it now, run: systemctl --user start daedelus"
