# Scripts Directory

Utility scripts for Daedelus installation, maintenance, and system integration.

Created by: orpheus497

---

## Installation Scripts

### `cleanup-daemon.sh`
**Purpose**: Clean up old installations before fresh install

**What it does**:
- Stops all running Daedelus daemons
- Kills orphaned daemon processes
- Removes stale PID and socket files
- Removes deprecated GPL dependencies
- Checks for zombie processes

**Usage**:
```bash
# Run manually
./scripts/cleanup-daemon.sh

# Runs automatically during install.sh
./install.sh
```

**When to use**:
- Before upgrading Daedelus
- When "address already in use" errors occur
- When multiple daemons are running
- When installation fails due to conflicts

---

### `remove-deprecated-deps.sh`
**Purpose**: Remove old GPL-licensed dependencies

**What it removes**:
- `thefuzz` (GPL-2.0) → Replaced with `rapidfuzz` (MIT)
- `python-Levenshtein` (GPL-2.0) → Replaced with `rapidfuzz` (MIT)

**Usage**:
```bash
# Run manually
./scripts/remove-deprecated-deps.sh

# Runs automatically during cleanup-daemon.sh
```

**When to use**:
- After upgrading from v0.2.0 or earlier
- When GPL license conflicts are reported
- When ensuring 100% permissive licensing

---

### `validate-installation.sh`
**Purpose**: Verify installation completed successfully

**What it checks**:
1. Python version (3.10+)
2. CLI commands (daedelus, deus)
3. Core dependencies (fasttext, annoy, click, etc.)
4. Deprecated dependencies removed
5. Configuration directory
6. Data directory
7. Stale daemon processes
8. Stale runtime files
9. LLM dependencies (optional)
10. Installation scripts present

**Usage**:
```bash
# After installation
./scripts/validate-installation.sh
```

**Output**:
- ✓ Green: Passed checks
- ⚠ Yellow: Warnings (non-critical)
- ✗ Red: Failed checks (critical)

---

## System Integration Scripts

### `install-systemd-service.sh`
**Purpose**: Install systemd service for auto-start on boot

**What it does**:
- Installs user systemd service
- Enables auto-start on login
- Configures proper permissions
- Sets up socket activation

**Usage**:
```bash
# Install service
./scripts/install-systemd-service.sh

# Service will start automatically on boot
```

**Requirements**:
- Linux with systemd
- User systemd support

**Files created**:
- `~/.config/systemd/user/daedelus.service`

---

### `uninstall-systemd-service.sh`
**Purpose**: Remove systemd service

**What it does**:
- Stops the service
- Disables auto-start
- Removes service files

**Usage**:
```bash
# Remove service
./scripts/uninstall-systemd-service.sh
```

---

## Script Execution Order

### Normal Installation
```
1. cleanup-daemon.sh (automatic)
   ├── Stops daemons
   ├── Removes stale files
   └── Removes deprecated deps
2. install.sh
   ├── Upgrades pip
   ├── Installs Daedelus
   └── Verifies installation
3. validate-installation.sh (optional)
   └── Confirms everything works
```

### Manual Cleanup
```
1. cleanup-daemon.sh
2. remove-deprecated-deps.sh (if needed)
3. validate-installation.sh (to verify)
```

### System Integration
```
1. install.sh (first)
2. install-systemd-service.sh (optional)
3. daemon starts automatically on boot
```

---

## Troubleshooting

### Script won't execute
```bash
# Make executable
chmod +x scripts/*.sh
```

### "Command not found" errors
```bash
# Ensure you're in the project root
cd /path/to/daedelus

# Run with bash explicitly
bash ./scripts/cleanup-daemon.sh
```

### Permission denied
```bash
# Don't run with sudo (uses user directories)
# Just make executable
chmod +x scripts/*.sh
./scripts/cleanup-daemon.sh
```

### Cleanup doesn't remove everything
```bash
# Force cleanup
pkill -9 -f daedelus.daemon.daemon
rm -f ~/.local/share/daedelus/runtime/*.pid
rm -f ~/.local/share/daedelus/runtime/*.sock
pip uninstall -y thefuzz python-Levenshtein
```

---

## Development

### Adding New Scripts

1. Create script in `scripts/` directory
2. Add shebang: `#!/bin/bash`
3. Add attribution: `# Created by: orpheus497`
4. Make executable: `chmod +x scripts/your-script.sh`
5. Document in this README
6. Test thoroughly
7. Update CHANGELOG.md

### Script Guidelines

- Use portable bash (no bashisms)
- Handle errors gracefully
- Provide clear output messages
- Support both interactive and non-interactive modes
- Don't require sudo unless absolutely necessary
- Test on multiple platforms (Linux, macOS, BSD)

### Testing Scripts

```bash
# Syntax check
bash -n scripts/your-script.sh

# Shellcheck (if available)
shellcheck scripts/your-script.sh

# Dry run
bash -x scripts/your-script.sh
```

---

## Script Details

### cleanup-daemon.sh
- **Lines**: 122
- **Language**: Bash
- **Dependencies**: pkill, pgrep, pip
- **Platforms**: Linux, macOS, BSD
- **Tested**: ✅ Python 3.10-3.14

### remove-deprecated-deps.sh
- **Lines**: 71
- **Language**: Bash
- **Dependencies**: pip
- **Platforms**: Linux, macOS, BSD, Windows (WSL)
- **Tested**: ✅ pip, pip3

### validate-installation.sh
- **Lines**: 212
- **Language**: Bash
- **Dependencies**: python3, pip, git
- **Platforms**: Linux, macOS, BSD
- **Output**: Colored (supports no-color terminals)
- **Tested**: ✅ All checks functional

### install-systemd-service.sh
- **Lines**: 89
- **Language**: Bash
- **Dependencies**: systemctl
- **Platforms**: Linux only
- **Tested**: ✅ User services

### uninstall-systemd-service.sh
- **Lines**: 53
- **Language**: Bash
- **Dependencies**: systemctl
- **Platforms**: Linux only
- **Tested**: ✅ Clean removal

---

## Version History

### v0.3.1 (2025-11-14)
- Added `cleanup-daemon.sh` - comprehensive cleanup
- Added `remove-deprecated-deps.sh` - GPL dependency removal
- Added `validate-installation.sh` - installation verification
- Enhanced `install.sh` with automatic cleanup

### v0.3.0 (2025-11-14)
- Added `install-systemd-service.sh`
- Added `uninstall-systemd-service.sh`

---

## See Also

- [Installation Guide](../QUICKSTART.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
- [Development Guide](../CONTRIBUTING.md)
- [CHANGELOG](../CHANGELOG.md)

---

**Created by orpheus497**

*Automating installation and maintenance for seamless user experience.*
