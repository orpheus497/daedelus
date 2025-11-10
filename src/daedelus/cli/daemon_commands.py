"""
Daemon lifecycle management commands for Daedelus CLI.

Provides commands for starting, stopping, and managing the Daedelus daemon.

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

from daedelus.daemon.daemon import DaedelusDaemon
from daedelus.daemon.ipc import IPCClient
from daedelus.utils.config import Config

logger = logging.getLogger(__name__)


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


def ensure_daemon_running(config: Config, silent: bool = False) -> bool:
    """
    Ensure daemon is running, auto-start if needed.

    Args:
        config: Configuration object
        silent: If True, don't print messages

    Returns:
        True if daemon is running (or was started), False otherwise
    """
    if is_daemon_running(config):
        return True

    if not silent:
        click.echo("🚀 Auto-starting Daedelus daemon...")

    # Start daemon in background
    cmd = [sys.executable, "-m", "daedelus.daemon.daemon"]

    # Redirect output to log file
    log_path = Path(config.get("daemon.log_path"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(log_path, "a") as log_file:
            subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )

        # Wait a moment and check if it started
        time.sleep(1)

        if is_daemon_running(config):
            if not silent:
                click.echo("✅ Daemon started successfully")
            return True
        else:
            if not silent:
                click.echo(f"❌ Failed to start daemon. Check logs: {log_path}")
            return False

    except Exception as e:
        if not silent:
            click.echo(f"❌ Error starting daemon: {e}")
        return False


@click.command()
@click.pass_context
def setup(ctx: click.Context) -> None:
    """
    Set up Daedelus for first-time use.

    This command initializes Daedelus by creating:
      • Configuration file at ~/.config/daedelus/config.yaml
      • Data directory at ~/.local/share/daedelus/
      • Models directory at ~/.local/share/models/

    After setup, you'll need to:
      1. Start the daemon: daedelus start
      2. Add shell integration to your shell RC file
      3. (Optional) Download LLM model for advanced features

    Daedelus is designed and created by orpheus497.
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


@click.command()
@click.option(
    "--foreground",
    is_flag=True,
    help="Run in foreground (don't daemonize)",
)
@click.pass_context
def start(ctx: click.Context, foreground: bool) -> None:
    """
    Start the Daedelus daemon.

    The daemon runs in the background and:
      • Monitors your terminal commands
      • Learns from your usage patterns
      • Provides intelligent suggestions via shell integration
      • Builds local AI models from your interactions
      • Maintains complete privacy (no data leaves your machine)

    Use --foreground to run in the current terminal (useful for debugging).
    For automatic startup on boot, use: ./scripts/install-systemd-service.sh
    """
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


@click.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """
    Stop the Daedelus daemon.

    Gracefully shuts down the daemon and saves all learned data.
    Your command history and AI models are preserved for the next session.
    """
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


@click.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """Restart the Daedalus daemon."""
    ctx.invoke(stop)
    time.sleep(1)
    ctx.invoke(start)


@click.command()
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output in JSON format",
)
@click.pass_context
def status(ctx: click.Context, output_json: bool) -> None:
    """
    Show daemon status and statistics.

    Displays:
      • Daemon running state and uptime
      • Number of commands logged and learned
      • Suggestions generated
      • Database statistics and success rates
      • Overall learning progress

    Use --json for machine-readable output.
    """
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


def register_daemon_commands(cli: click.Group) -> None:
    """Register all daemon management commands."""
    cli.add_command(setup)
    cli.add_command(start)
    cli.add_command(stop)
    cli.add_command(restart)
    cli.add_command(status)
