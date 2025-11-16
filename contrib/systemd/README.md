# Systemd Service Files for Daedelus

This directory contains systemd user service files for managing the Daedelus daemon automatically.

## Installation

### Option 1: Manual Installation

```bash
# Copy service files to systemd user directory
mkdir -p ~/.config/systemd/user
cp daedelus.service ~/.config/systemd/user/
cp daedelus.socket ~/.config/systemd/user/

# Reload systemd
systemctl --user daemon-reload

# Enable and start the service
systemctl --user enable daedelus.service
systemctl --user start daedelus.service

# Check status
systemctl --user status daedelus.service
```

### Option 2: Socket Activation (Recommended)

Socket activation starts the daemon only when needed:

```bash
# Enable socket activation
systemctl --user enable daedelus.socket
systemctl --user start daedelus.socket

# The daemon will start automatically when first accessed
```

## Enable at Login

To start the daemon automatically when you log in:

```bash
# Enable lingering (allows services to run when not logged in)
loginctl enable-linger $USER

# Enable the service
systemctl --user enable daedelus.service
```

## Commands

```bash
# Start daemon
systemctl --user start daedelus.service

# Stop daemon
systemctl --user stop daedelus.service

# Restart daemon
systemctl --user restart daedelus.service

# Check status
systemctl --user status daedelus.service

# View logs
journalctl --user -u daedelus.service -f
```

## Uninstallation

```bash
# Stop and disable service
systemctl --user stop daedelus.service
systemctl --user disable daedelus.service

# Remove service files
rm ~/.config/systemd/user/daedelus.service
rm ~/.config/systemd/user/daedelus.socket

# Reload systemd
systemctl --user daemon-reload
```

---

Created by: orpheus497
