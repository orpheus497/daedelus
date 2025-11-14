"""
History screen for the Daedelus dashboard.
"""

import datetime
import logging

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Markdown, Static

logger = logging.getLogger(__name__)


class HistoryScreen(Static):
    """A widget to display the command history screen."""

    def __init__(self, ipc_client=None, **kwargs):
        super().__init__(**kwargs)
        self.ipc_client = ipc_client
        self.history_table = DataTable()
        self.filter_input = Input(placeholder="Filter history...")
        self.details_pane = Markdown(id="details-pane")
        self.current_history = []

    def compose(self) -> ComposeResult:
        """Create child widgets for the history screen."""
        yield Static("[bold]Command History[/bold]", classes="header")
        yield self.filter_input
        with Horizontal():
            with Vertical(id="history-table-container"):
                yield self.history_table
            with Vertical(id="history-details-container"):
                yield self.details_pane

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.history_table.add_columns("Timestamp", "Directory", "Command", "Exit Code")
        self.history_table.cursor_type = "row"
        self.update_history_table()
        self.details_pane.update("*Click on a command to see details*")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle changes to the filter input."""
        self.update_history_table(event.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the history table."""
        row_index = event.cursor_row
        command_text = self.history_table.get_cell_at((row_index, 2))

        # Show command details
        explanation = f"### Command: `{command_text}`\n\n"
        explanation += "**Details:**\n\n"

        if row_index < len(self.current_history):
            entry = self.current_history[row_index]
            explanation += f"- **Directory:** {entry.get('directory', entry.get('cwd', 'N/A'))}\n"
            explanation += f"- **Exit Code:** {entry.get('exit_code', 'N/A')}\n"

            if "timestamp" in entry:
                explanation += f"- **Time:** {entry['timestamp']}\n"

            if "duration" in entry:
                explanation += f"- **Duration:** {entry['duration']}s\n"

        # Get explanation from daemon if connected
        if self.ipc_client and self.ipc_client.is_connected():
            explanation += "\n**Explanation:**\n\n"
            explanation += self.ipc_client.explain_command(command_text)
        else:
            explanation += "\n*Note: Connect to daemon for command explanations.*"

        self.details_pane.update(explanation)

    def update_history_table(self, filter_str: str = "") -> None:
        """Update the history table with data, optionally filtered."""
        self.history_table.clear()

        # Fetch history from daemon or use mock data
        if self.ipc_client and self.ipc_client.is_connected():
            try:
                self.current_history = self.ipc_client.get_command_history(
                    limit=100, search=filter_str if filter_str else None
                )
            except Exception as e:
                logger.error(f"Failed to fetch history: {e}")
                self.current_history = self._get_mock_history()
        else:
            self.current_history = self._get_mock_history()
            if filter_str:
                self.current_history = [
                    entry
                    for entry in self.current_history
                    if filter_str.lower() in entry["command"].lower()
                ]

        for entry in self.current_history:
            # Handle case where entry might be a string instead of dict
            if isinstance(entry, str):
                # Convert string to dict format
                entry = {"command": entry}
            
            # Handle both timestamp formats
            ts_str = entry.get("timestamp", "")
            if isinstance(ts_str, datetime.datetime):
                ts_str = ts_str.strftime("%Y-%m-%d %H:%M:%S")
            elif not ts_str:
                ts_str = "N/A"

            directory = entry.get("directory", entry.get("cwd", "N/A"))
            command = entry.get("command", "N/A")
            exit_code = entry.get("exit_code", -1)

            exit_code_str = (
                f"[green]{exit_code}[/green]" if exit_code == 0 else f"[red]{exit_code}[/red]"
            )

            self.history_table.add_row(
                ts_str,
                directory,
                command,
                exit_code_str,
            )

    def _get_mock_history(self):
        """Return mock history data when daemon is not available."""
        return [
            {
                "timestamp": (datetime.datetime.now() - datetime.timedelta(minutes=1)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "directory": "/home/user/project",
                "command": "ls -la",
                "exit_code": 0,
            },
            {
                "timestamp": (datetime.datetime.now() - datetime.timedelta(minutes=5)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "directory": "/home/user/project",
                "command": "git status",
                "exit_code": 0,
            },
            {
                "timestamp": (datetime.datetime.now() - datetime.timedelta(minutes=12)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "directory": "/home/user/project",
                "command": "pytest",
                "exit_code": 1,
            },
        ]
