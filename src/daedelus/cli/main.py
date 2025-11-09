"""
Command-line interface for Daedalus.

Provides user commands for managing the daemon and querying history.

Created by: orpheus497
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import click

from daedelus import __version__
from daedelus.daemon.daemon import DaedelusDaemon
from daedelus.daemon.ipc import IPCClient
from daedelus.utils.config import Config
from daedelus.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    help="Path to config file",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v, -vv, -vvv)",
)
@click.pass_context
def cli(ctx: click.Context, config: Path | None, verbose: int) -> None:
    """
    Daedalus - Self-Learning Terminal Assistant

    A privacy-first, offline AI assistant that learns from your command usage.

    Created by: orpheus497
    """
    # Set up logging
    log_level = logging.WARNING
    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG

    setup_logging(console=True, level=log_level)

    # Load configuration
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config(config) if config else Config()


@cli.command()
@click.pass_context
def setup(ctx: click.Context) -> None:
    """
    Set up Daedalus for first-time use.

    Creates configuration file and data directories.
    """
    config: Config = ctx.obj["config"]

    click.echo("🚀 Setting up Daedalus...")

    # Create directories
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.config_dir.mkdir(parents=True, exist_ok=True)

    # Save default config
    if not config.config_path.exists():
        config.save()
        click.echo(f"✅ Created config: {config.config_path}")
    else:
        click.echo(f"ℹ️  Config already exists: {config.config_path}")

    click.echo(f"✅ Data directory: {config.data_dir}")

    # Shell integration instructions
    click.echo("\n📝 To enable shell integration, add to your shell RC file:")
    click.echo("\n  # For ZSH (~/.zshrc):")
    click.echo("  source $(daedelus shell-integration zsh)")
    click.echo("\n  # For Bash (~/.bashrc):")
    click.echo("  source $(daedelus shell-integration bash)")

    click.echo("\n✨ Setup complete! Run 'daedelus start' to begin.")


@cli.command()
@click.option(
    "--foreground",
    is_flag=True,
    help="Run in foreground (don't daemonize)",
)
@click.pass_context
def start(ctx: click.Context, foreground: bool) -> None:
    """Start the Daedalus daemon."""
    config: Config = ctx.obj["config"]

    # Check if already running
    if is_daemon_running(config):
        click.echo("⚠️  Daemon is already running")
        click.echo(f"PID file: {config.get('daemon.pid_path')}")
        return

    if foreground:
        # Run in foreground
        click.echo("🚀 Starting daemon in foreground...")
        click.echo("Press Ctrl+C to stop")

        daemon = DaedelusDaemon(config)
        try:
            daemon.start()
        except KeyboardInterrupt:
            click.echo("\n⏹️  Stopped by user")

    else:
        # Run in background
        click.echo("🚀 Starting daemon in background...")

        # Use subprocess to daemonize
        cmd = [sys.executable, "-m", "daedelus.daemon.daemon"]

        # Redirect output to log file
        log_path = Path(config.get("daemon.log_path"))
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as log_file:
            subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,  # Detach from terminal
            )

        # Wait a moment and check if it started
        time.sleep(1)

        if is_daemon_running(config):
            click.echo("✅ Daemon started successfully")
            click.echo(f"Log file: {log_path}")
        else:
            click.echo("❌ Failed to start daemon")
            click.echo(f"Check logs: {log_path}")


@cli.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop the Daedalus daemon."""
    config: Config = ctx.obj["config"]

    if not is_daemon_running(config):
        click.echo("ℹ️  Daemon is not running")
        return

    click.echo("⏹️  Stopping daemon...")

    # Get PID
    pid_path = Path(config.get("daemon.pid_path"))
    try:
        pid = int(pid_path.read_text().strip())

        # Send SIGTERM
        os.kill(pid, signal.SIGTERM)

        # Wait for shutdown
        for _ in range(10):
            time.sleep(0.5)
            if not is_daemon_running(config):
                click.echo("✅ Daemon stopped")
                return

        # Force kill if still running
        click.echo("⚠️  Daemon didn't stop gracefully, forcing...")
        os.kill(pid, signal.SIGKILL)
        pid_path.unlink(missing_ok=True)
        click.echo("✅ Daemon stopped (forced)")

    except (ProcessLookupError, ValueError) as e:
        click.echo(f"❌ Error stopping daemon: {e}")
        pid_path.unlink(missing_ok=True)


@cli.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """Restart the Daedalus daemon."""
    ctx.invoke(stop)
    time.sleep(1)
    ctx.invoke(start)


@cli.command()
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output in JSON format",
)
@click.pass_context
def status(ctx: click.Context, output_json: bool) -> None:
    """Show daemon status."""
    config: Config = ctx.obj["config"]

    if not is_daemon_running(config):
        if output_json:
            import json

            click.echo(json.dumps({"status": "stopped"}))
        else:
            click.echo("⚫ Daemon is not running")
        return

    # Query daemon via IPC
    try:
        client = IPCClient(config.get("daemon.socket_path"))
        status_data = client.status()

        if output_json:
            import json

            click.echo(json.dumps(status_data, indent=2))
        else:
            click.echo("🟢 Daemon is running")
            click.echo(f"\nUptime: {status_data.get('uptime_seconds', 0):.1f}s")
            click.echo(f"Requests handled: {status_data.get('requests_handled', 0)}")
            click.echo(f"Commands logged: {status_data.get('commands_logged', 0)}")
            click.echo(f"Suggestions generated: {status_data.get('suggestions_generated', 0)}")

            if "database" in status_data:
                db = status_data["database"]
                click.echo("\nDatabase:")
                click.echo(f"  Total commands: {db.get('total_commands', 0)}")
                click.echo(f"  Success rate: {db.get('success_rate', 0):.1f}%")

    except Exception as e:
        click.echo(f"❌ Error querying daemon: {e}")


@cli.command()
@click.argument("query")
@click.option(
    "-n",
    "--limit",
    default=20,
    help="Number of results",
)
@click.pass_context
def search(ctx: click.Context, query: str, limit: int) -> None:
    """Search command history."""
    config: Config = ctx.obj["config"]

    if not is_daemon_running(config):
        click.echo("❌ Daemon is not running. Start it with 'daedelus start'")
        return

    try:
        client = IPCClient(config.get("daemon.socket_path"))
        from daedelus.daemon.ipc import IPCMessage, MessageType

        msg = IPCMessage(MessageType.SEARCH, {"query": query, "limit": limit})
        response = client.send_message(msg)

        if response.type == MessageType.ERROR:
            click.echo(f"❌ {response.data.get('error')}")
            return

        results = response.data.get("results", [])

        if not results:
            click.echo("No results found")
            return

        click.echo(f"Found {len(results)} results:\n")
        for result in results:
            cmd = result.get("command", "")
            timestamp = result.get("timestamp", 0)
            cwd = result.get("cwd", "")

            from datetime import datetime

            time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

            click.echo(f"  {time_str} | {cwd}")
            click.echo(f"    {cmd}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@cli.command()
@click.argument("shell", type=click.Choice(["zsh", "bash", "fish"]))
def shell_integration(shell: str) -> None:
    """Print path to shell integration script."""
    import sys

    import daedelus

    # Get the package installation directory
    package_dir = Path(daedelus.__file__).parent.parent.parent

    # Map shell to integration file
    integration_files = {
        "zsh": "shell_clients/zsh/daedelus.plugin.zsh",
        "bash": "shell_clients/bash/daedelus.bash",
        "fish": "shell_clients/fish/daedelus.fish",
    }

    integration_path = package_dir / integration_files[shell]

    if integration_path.exists():
        # Print the path (for sourcing in shell RC file)
        click.echo(str(integration_path))
    else:
        click.echo(f"Error: Integration file not found: {integration_path}", err=True)
        click.echo(f"Expected location: {integration_path}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show system information."""
    config: Config = ctx.obj["config"]

    click.echo("Daedalus System Information")
    click.echo("=" * 40)
    click.echo(f"Version: {__version__}")
    click.echo(f"Config: {config.config_path}")
    click.echo(f"Data dir: {config.data_dir}")
    click.echo(f"Socket: {config.get('daemon.socket_path')}")
    click.echo(f"Log: {config.get('daemon.log_path')}")
    click.echo(f"Database: {config.get('database.path')}")
    click.echo(f"Model: {config.get('model.model_path')}")

    db_path = Path(config.get("database.path"))
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        click.echo(f"\nDatabase size: {size_mb:.2f} MB")


# Helper functions


def is_daemon_running(config: Config) -> bool:
    """Check if daemon is running."""
    pid_path = Path(config.get("daemon.pid_path"))

    if not pid_path.exists():
        return False

    try:
        pid = int(pid_path.read_text().strip())

        # Check if process exists
        os.kill(pid, 0)  # Doesn't actually kill, just checks
        return True

    except (ProcessLookupError, ValueError):
        # Stale PID file
        pid_path.unlink(missing_ok=True)
        return False


def main() -> int:
    """Main entry point."""
    try:
        cli(obj={})
        return 0
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
