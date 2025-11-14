"""
Overview screen for the Daedelus dashboard.
"""

import logging

from textual.app import ComposeResult
from textual.widgets import DataTable, Log, Static

logger = logging.getLogger(__name__)


class OverviewScreen(Static):
    """A widget to display the overview screen."""

    def __init__(self, ipc_client=None, **kwargs):
        super().__init__(**kwargs)
        self.ipc_client = ipc_client
        self.stats_table = DataTable()
        self.log_viewer = Log(max_lines=100)

    def compose(self) -> ComposeResult:
        """Create child widgets for the overview screen."""
        yield Static("[bold]Daemon Status[/bold]", classes="header")
        yield self.stats_table
        yield Static("\n[bold]Live Logs[/bold]", classes="header")
        yield self.log_viewer

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.stats_table.add_columns("Metric", "Value")
        self.update_status()
        self.log_viewer.write_line("Log viewer initialized...")

        if self.ipc_client and self.ipc_client.is_connected():
            self.log_viewer.write_line("[green]Connected to daemon successfully[/green]")
        else:
            self.log_viewer.write_line(
                "[yellow]Daemon not connected - displaying mock data[/yellow]"
            )

    def update_status(self) -> None:
        """Update daemon status display with live or mock data."""

        if self.ipc_client:
            status = self.ipc_client.get_daemon_status()
        else:
            status = self._get_mock_status()

        self.stats_table.clear()

        uptime_seconds = status.get("uptime_seconds", 0)
        uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"

        daemon_status = status.get("status", "N/A")
        if daemon_status == "running":
            status_display = f"[green]{daemon_status}[/green]"
        elif daemon_status == "disconnected":
            status_display = f"[red]{daemon_status}[/red]"
        else:
            status_display = f"[yellow]{daemon_status}[/yellow]"

        self.stats_table.add_row("Status", status_display)
        self.stats_table.add_row("Uptime", uptime_str)
        self.stats_table.add_row("Session ID", status.get("session_id", "N/A"))
        self.stats_table.add_row("Requests Handled", str(status.get("requests_handled", 0)))
        self.stats_table.add_row("Commands Logged", str(status.get("commands_logged", 0)))
        self.stats_table.add_row(
            "Suggestions Generated", str(status.get("suggestions_generated", 0))
        )

        db_stats = status.get("database", {})
        self.stats_table.add_row("DB Commands", str(db_stats.get("total_commands", 0)))

        vector_stats = status.get("vector_store", {})
        self.stats_table.add_row("Vector Index Size", str(vector_stats.get("num_items", 0)))

    def _get_mock_status(self):
        """Return mock status for when IPC client is not available."""
        return {
            "status": "running (mock)",
            "uptime_seconds": 12345,
            "session_id": "mock-session-id",
            "requests_handled": 123,
            "commands_logged": 456,
            "suggestions_generated": 789,
            "database": {"total_commands": 1234},
            "vector_store": {"num_items": 5678},
        }
