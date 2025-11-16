"""
Analytics screen for the Daedelus dashboard.
"""

import logging

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

logger = logging.getLogger(__name__)


class AnalyticsScreen(Static):
    """A widget to display analytics."""

    def __init__(self, ipc_client=None, **kwargs):
        super().__init__(**kwargs)
        self.ipc_client = ipc_client
        self.top_commands_table = DataTable()
        self.analytics_data = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the analytics screen."""
        yield Static("[bold]Analytics[/bold]", classes="header")
        yield Static("", id="success-rate-display")
        yield Static("\n[bold]Most Used Commands[/bold]", classes="header")
        yield self.top_commands_table

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.top_commands_table.add_columns("Command", "Count")
        self.update_analytics()

    def update_analytics(self) -> None:
        """Update analytics display with live or mock data."""
        if self.ipc_client and self.ipc_client.is_connected():
            try:
                self.analytics_data = self.ipc_client.get_analytics_data()
            except Exception as e:
                logger.error(f"Failed to fetch analytics: {e}")
                self.analytics_data = self._get_mock_analytics()
        else:
            self.analytics_data = self._get_mock_analytics()

        # Update success rate display
        success_rate_widget = self.query_one("#success-rate-display", Static)
        total_cmds = self.analytics_data.get("total_commands", 0)
        success_rate = self.analytics_data.get("success_rate", 0.0)
        success_rate_widget.update(
            f"Total Commands: [bold]{total_cmds}[/bold] | "
            f"Unique: [bold]{self.analytics_data.get('unique_commands', 0)}[/bold] | "
            f"Success Rate: [bold green]{success_rate:.1f}%[/bold green]"
        )

        # Update top commands
        self.top_commands_table.clear()
        most_used = self.analytics_data.get("most_used_commands", [])

        if most_used:
            for command, count in most_used:
                self.top_commands_table.add_row(command, str(count))
        else:
            self.top_commands_table.add_row("No data available", "0")

    def _get_mock_analytics(self):
        """Return mock analytics when daemon is not available."""
        return {
            "total_commands": 1234,
            "unique_commands": 456,
            "successful_commands": 1100,
            "success_rate": 89.1,
            "most_used_commands": [
                ("git status", 152),
                ("ls -la", 121),
                ("cd ..", 98),
                ("daedelus dashboard", 75),
                ("pytest", 62),
                ("git commit", 55),
            ],
            "total_sessions": 45,
        }
