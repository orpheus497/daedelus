"""
Neovim Integration Plugin for Daedalus.

Provides commands to interact with Neovim for editing Daedalus files.

Created by: orpheus497
"""

import subprocess
import sys
from pathlib import Path

import click

from daedelus.core.plugin_interface import DaedalusAPI, DaedalusPlugin


class NeovimIntegration(DaedalusPlugin):
    """Plugin for Neovim editor integration."""

    def __init__(self, api: DaedalusAPI):
        """Initialize the Neovim integration plugin."""
        super().__init__(api)
        self.logger = api.get_logger()
        self.nvim_available = False

    def load(self) -> bool:
        """Load the plugin and check if Neovim is available."""
        try:
            result = subprocess.run(
                ["nvim", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                self.nvim_available = True
                version = result.stdout.split("\n")[0]
                self.logger.info(f"Neovim detected: {version}")
                return True
            else:
                self.logger.warning("Neovim not found - integration disabled")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.logger.warning("Neovim not found - integration disabled")
            return False

    def unload(self) -> None:
        """Unload the plugin."""
        self.logger.info("Neovim Integration plugin unloaded")

    def register_cli_commands(self) -> dict:
        """Register CLI commands."""

        @click.group("nvim")
        def nvim_group():
            """Neovim integration commands."""
            if not self.nvim_available:
                click.echo("⚠️  Neovim is not installed or not in PATH", err=True)
                sys.exit(1)

        @nvim_group.command("edit-config")
        def edit_config():
            """Open Daedalus configuration in Neovim."""
            try:
                self.api.require_permission("shell:execute")
                self.api.require_permission("config:read")

                config_path = self.api.get_config_path()
                if not config_path.exists():
                    click.echo(f"❌ Config file not found: {config_path}", err=True)
                    return 1

                self.logger.info(f"Opening config in Neovim: {config_path}")
                subprocess.run(["nvim", str(config_path)])

            except PermissionError as e:
                click.echo(f"❌ Permission denied: {e}", err=True)
                return 1
            except Exception as e:
                self.logger.error(f"Failed to open config: {e}")
                click.echo(f"❌ Error: {e}", err=True)
                return 1

        @nvim_group.command("edit-plugin")
        @click.argument("plugin_name")
        def edit_plugin(plugin_name: str):
            """Open a plugin's main file in Neovim."""
            try:
                self.api.require_permission("shell:execute")
                self.api.require_permission("filesystem:read")

                # Try internal plugins first
                internal_path = Path(f"src/daedelus/plugins/{plugin_name}/main.py")
                if internal_path.exists():
                    subprocess.run(["nvim", str(internal_path)])
                    return

                # Try external plugins
                external_path = self.api.get_data_dir() / f"plugins/{plugin_name}/main.py"
                if external_path.exists():
                    subprocess.run(["nvim", str(external_path)])
                    return

                click.echo(f"❌ Plugin not found: {plugin_name}", err=True)
                return 1

            except PermissionError as e:
                click.echo(f"❌ Permission denied: {e}", err=True)
                return 1
            except Exception as e:
                self.logger.error(f"Failed to open plugin: {e}")
                click.echo(f"❌ Error: {e}", err=True)
                return 1

        @nvim_group.command("history")
        @click.option("--limit", default=100, help="Number of recent commands to show")
        def edit_history(limit: int):
            """View command history in Neovim (read-only)."""
            try:
                self.api.require_permission("shell:execute")
                self.api.require_permission("database:read")

                # Get command history
                history = self.api.get_command_history(limit=limit)

                # Create temporary file
                import tempfile

                with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                    f.write("# Daedalus Command History\n")
                    f.write("# Recent commands (read-only)\n\n")
                    for entry in history:
                        timestamp = entry.get("timestamp", "N/A")
                        command = entry.get("command", "N/A")
                        cwd = entry.get("cwd", "N/A")
                        exit_code = entry.get("exit_code", "?")
                        f.write(f"[{timestamp}] ({exit_code}) {cwd}\n")
                        f.write(f"  {command}\n\n")
                    temp_path = f.name

                # Open in read-only mode
                subprocess.run(["nvim", "-R", temp_path])

                # Clean up
                Path(temp_path).unlink()

            except PermissionError as e:
                click.echo(f"❌ Permission denied: {e}", err=True)
                return 1
            except Exception as e:
                self.logger.error(f"Failed to view history: {e}")
                click.echo(f"❌ Error: {e}", err=True)
                return 1

        return {"nvim": nvim_group}
