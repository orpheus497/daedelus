#!/usr/bin/env bash
# Uninstall Daedelus systemd service

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Uninstalling Daedelus systemd service...${NC}"

# Stop the service if running
if systemctl --user is-active --quiet daedelus.service; then
    systemctl --user stop daedelus.service
    echo -e "${GREEN}✓${NC} Service stopped"
fi

# Disable the service
if systemctl --user is-enabled --quiet daedelus.service 2>/dev/null; then
    systemctl --user disable daedelus.service
    echo -e "${GREEN}✓${NC} Service disabled"
fi

# Remove service file
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SYSTEMD_USER_DIR}/daedelus.service"

if [ -f "$SERVICE_FILE" ]; then
    rm "$SERVICE_FILE"
    echo -e "${GREEN}✓${NC} Service file removed"
fi

# Reload systemd daemon
systemctl --user daemon-reload
echo -e "${GREEN}✓${NC} Systemd daemon reloaded"

echo ""
echo -e "${GREEN}Uninstallation complete!${NC}"
echo ""
echo -e "${YELLOW}Note:${NC} User lingering is still enabled."
echo "To disable it, run: loginctl disable-linger $USER"
