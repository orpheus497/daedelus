# Daedalus Shell Integration

This directory contains shell integration scripts for Daedalus.

## Installation

### ZSH

Add to your `~/.zshrc`:

```bash
source /path/to/daedelus/shell_clients/zsh/daedelus.plugin.zsh
```

Or use the CLI helper:

```bash
echo "source $(daedelus shell-integration zsh)" >> ~/.zshrc
```

### Bash

Add to your `~/.bashrc`:

```bash
source /path/to/daedelus/shell_clients/bash/daedelus.bash
```

Or use the CLI helper:

```bash
echo "source $(daedelus shell-integration bash)" >> ~/.bashrc
```

### Fish

Add to your `~/.config/fish/config.fish`:

```fish
source /path/to/daedelus/shell_clients/fish/daedelus.fish
```

Or use the CLI helper:

```fish
echo "source (daedelus shell-integration fish)" >> ~/.config/fish/config.fish
```

## Features

All shell integrations provide:

- **Automatic Command Logging**: Every command you run is logged to Daedalus
- **Intelligent Suggestions**: Press `Ctrl+Space` to get context-aware suggestions
- **Session Tracking**: Commands are grouped by shell session
- **Non-Intrusive**: Runs asynchronously, won't slow down your shell

## Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+Space` | Get suggestions for current command |
| `Alt+Enter` | Accept suggestion (ZSH only) |

## Customization

### ZSH

Set these variables in your `.zshrc` before sourcing the plugin:

```bash
# Custom socket path
export DAEDELUS_SOCKET="$HOME/.local/share/daedelus/runtime/daemon.sock"

# Custom keybinding (default: Ctrl+Space)
export DAEDELUS_KEYBIND="^X"  # Ctrl+X instead

# Disable auto-suggestions
export DAEDELUS_AUTO_SUGGEST=0

# Suggestion delay in milliseconds
export DAEDELUS_SUGGEST_DELAY=300
```

### Bash

```bash
# Custom socket path
export DAEDELUS_SOCKET="$HOME/.local/share/daedelus/runtime/daemon.sock"

# Custom keybinding (default: Ctrl+Space)
export DAEDELUS_KEYBIND="\\C-x"  # Ctrl+X instead
```

### Fish

```fish
# Custom socket path
set -g DAEDELUS_SOCKET "$HOME/.local/share/daedelus/runtime/daemon.sock"
```

## Troubleshooting

### Daemon Not Running

If you see "Daedelus daemon not running", start it:

```bash
daedelus start
```

### Cannot Communicate with Daemon

Check the socket path:

```bash
ls -la ~/.local/share/daedelus/runtime/daemon.sock
```

Check daemon status:

```bash
daedelus status
```

### No Suggestions Appearing

1. Make sure you've used the shell for a while (Daedalus needs data)
2. Check that commands are being logged:

```bash
daedelus status  # Check "commands_logged" count
```

3. Search your history to verify data:

```bash
daedelus search "git"
```

## How It Works

1. **Command Logging**: Uses shell hooks (`preexec`/`precmd` for ZSH/Bash, `fish_postexec` for Fish) to capture commands
2. **IPC Communication**: Sends JSON messages to daemon via Unix domain socket
3. **Asynchronous**: All communication happens in the background
4. **Suggestions**: Queries daemon with current buffer, directory, and recent history

## Performance

- **Latency**: <1ms for command logging (asynchronous)
- **Suggestions**: <50ms for suggestion retrieval
- **Memory**: Negligible shell overhead

## Privacy

All data stays local:
- Commands logged to local SQLite database
- IPC via Unix domain socket (no network)
- No telemetry or external communication

## See Also

- [Main README](../../README.md) - Project overview
- [Configuration](../../docs/configuration.md) - Daemon configuration
- [CLI Reference](../../docs/cli.md) - Command-line interface
