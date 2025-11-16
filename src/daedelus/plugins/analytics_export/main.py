"""
Analytics Export Plugin for Daedalus.

Provides commands to export command history analytics to various formats.

Created by: orpheus497
"""

import csv
import json
from pathlib import Path

import click

from daedelus.core.plugin_interface import DaedalusAPI, DaedalusPlugin


class AnalyticsExporter(DaedalusPlugin):
    """Plugin to export command history analytics."""

    def __init__(self, api: DaedalusAPI):
        """Initialize the analytics exporter plugin."""
        super().__init__(api)
        self.logger = api.get_logger()

    def load(self) -> bool:
        """Load the plugin."""
        self.logger.info("Analytics Export plugin loaded")
        return True

    def unload(self) -> None:
        """Unload the plugin."""
        self.logger.info("Analytics Export plugin unloaded")

    def register_cli_commands(self) -> dict:
        """Register CLI commands."""

        @click.group("export")
        def export_group():
            """Export command history data to various formats."""
            pass

        @export_group.command("analytics")
        @click.option(
            "--format",
            type=click.Choice(["json", "csv"]),
            default="json",
            help="Output format",
        )
        @click.option("--output", type=click.Path(), required=True, help="Output file path")
        @click.option(
            "--limit", type=int, default=1000, help="Maximum number of commands to export"
        )
        def export_analytics(format: str, output: str, limit: int):
            """Export command history analytics."""
            try:
                # Check permissions
                self.api.require_permission("database:read")
                self.api.require_permission("filesystem:write")

                # Get command history
                self.logger.info(f"Exporting {limit} commands to {output}")
                history = self.api.get_command_history(limit=limit)

                # Export based on format
                output_path = Path(output)
                if format == "json":
                    self._export_json(history, output_path)
                elif format == "csv":
                    self._export_csv(history, output_path)

                click.echo(f"✅ Exported {len(history)} commands to {output}")

            except PermissionError as e:
                click.echo(f"❌ Permission denied: {e}", err=True)
                return 1
            except Exception as e:
                self.logger.error(f"Export failed: {e}")
                click.echo(f"❌ Export failed: {e}", err=True)
                return 1

        @export_group.command("summary")
        @click.option("--output", type=click.Path(), required=True, help="Output file path")
        def export_summary(output: str):
            """Export a summary of command usage statistics."""
            try:
                self.api.require_permission("database:read")
                self.api.require_permission("filesystem:write")

                # Get analytics data
                analytics = self.api.get_analytics_data()

                # Write summary
                output_path = Path(output)
                with open(output_path, "w") as f:
                    json.dump(analytics, f, indent=2, default=str)

                click.echo(f"✅ Exported analytics summary to {output}")

            except Exception as e:
                self.logger.error(f"Summary export failed: {e}")
                click.echo(f"❌ Export failed: {e}", err=True)
                return 1

        return {"export": export_group}

    def _export_json(self, history: list, output_path: Path) -> None:
        """Export history to JSON format."""
        with open(output_path, "w") as f:
            json.dump(history, f, indent=2, default=str)

    def _export_csv(self, history: list, output_path: Path) -> None:
        """Export history to CSV format."""
        if not history:
            return

        # Get all keys from the first record
        keys = history[0].keys()

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(history)
