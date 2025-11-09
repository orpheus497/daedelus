"""
TUI dashboard for Daedelus statistics and insights.

Provides an interactive terminal UI for exploring command history and statistics.

Created by: orpheus497
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import with graceful degradation
try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Button, DataTable, Footer, Header, Static
    from rich.table import Table
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    logger.warning("textual not available - dashboard disabled")

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table as RichTable
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class DashboardApp(App):
    """
    Daedelus statistics dashboard TUI application.

    Displays:
    - Command usage statistics
    - Most used commands
    - Success rates
    - Learning progress
    - Session history
    """

    CSS = """
    Screen {
        background: $background;
    }

    Header {
        background: $primary;
        color: $text;
    }

    Footer {
        background: $primary;
        color: $text;
    }

    .stats-panel {
        height: auto;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }

    .data-table {
        height: auto;
        max-height: 20;
    }

    Button {
        margin: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "commands", "Top Commands"),
        ("s", "sessions", "Sessions"),
        ("e", "export", "Export"),
    ]

    def __init__(self, db_stats: Dict[str, Any], **kwargs: Any) -> None:
        """
        Initialize dashboard app.

        Args:
            db_stats: Database statistics dictionary
            **kwargs: Additional arguments for App
        """
        super().__init__(**kwargs)
        self.db_stats = db_stats

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)

        # Statistics overview
        yield Static(self._create_stats_overview(), classes="stats-panel")

        # Top commands table
        yield Static("Most Used Commands", id="commands-header")
        table = DataTable(id="commands-table", classes="data-table")
        table.add_columns("Command", "Count", "Success %")
        yield table

        # Control buttons
        with Horizontal():
            yield Button("Refresh", id="refresh-btn", variant="primary")
            yield Button("Export", id="export-btn")
            yield Button("Quit", id="quit-btn", variant="error")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self._populate_commands_table()

    def _create_stats_overview(self) -> str:
        """Create overview statistics display."""
        stats = self.db_stats
        total = stats.get("total_commands", 0)
        success = stats.get("successful_commands", 0)
        success_rate = stats.get("success_rate", 0)
        sessions = stats.get("total_sessions", 0)

        overview = f"""
[bold cyan]Daedelus Statistics Overview[/bold cyan]

[bold]Total Commands:[/bold] {total:,}
[bold]Successful:[/bold] {success:,} ({success_rate:.1f}%)
[bold]Sessions:[/bold] {sessions:,}
[bold]Database Size:[/bold] {stats.get('database_size_bytes', 0) / 1024:.2f} KB
"""
        return overview

    def _populate_commands_table(self) -> None:
        """Populate the commands table with data."""
        table = self.query_one("#commands-table", DataTable)

        # Mock data - in real implementation, would query database
        sample_commands = [
            ("git status", 142, 100.0),
            ("ls -la", 98, 100.0),
            ("cd ..", 87, 100.0),
            ("git commit", 54, 98.1),
            ("pytest", 43, 87.2),
        ]

        for cmd, count, success in sample_commands:
            table.add_row(cmd, str(count), f"{success:.1f}%")

    def action_refresh(self) -> None:
        """Refresh the dashboard data."""
        logger.info("Refreshing dashboard...")
        self._populate_commands_table()

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_export(self) -> None:
        """Export statistics."""
        logger.info("Exporting statistics...")
        # Would implement export functionality

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "refresh-btn":
            self.action_refresh()
        elif event.button.id == "export-btn":
            self.action_export()
        elif event.button.id == "quit-btn":
            self.action_quit()


def show_dashboard_rich(db_stats: Dict[str, Any]) -> None:
    """
    Show dashboard using Rich (fallback if Textual not available).

    Args:
        db_stats: Database statistics
    """
    if not RICH_AVAILABLE:
        print("Rich not available - install with: pip install rich")
        return

    console = Console()

    # Create statistics panel
    stats = db_stats
    total = stats.get("total_commands", 0)
    success = stats.get("successful_commands", 0)
    success_rate = stats.get("success_rate", 0)
    sessions = stats.get("total_sessions", 0)

    stats_table = RichTable(title="Daedelus Statistics", show_header=False)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")

    stats_table.add_row("Total Commands", f"{total:,}")
    stats_table.add_row("Successful", f"{success:,} ({success_rate:.1f}%)")
    stats_table.add_row("Sessions", f"{sessions:,}")
    stats_table.add_row("Database Size", f"{stats.get('database_size_bytes', 0) / 1024:.2f} KB")

    console.print(Panel(stats_table, title="[bold]Daedelus Dashboard[/bold]", border_style="blue"))

    # Create top commands table
    commands_table = RichTable(title="Most Used Commands")
    commands_table.add_column("Rank", style="dim")
    commands_table.add_column("Command", style="cyan")
    commands_table.add_column("Count", justify="right", style="green")
    commands_table.add_column("Success %", justify="right", style="yellow")

    # Sample data
    sample_commands = [
        ("git status", 142, 100.0),
        ("ls -la", 98, 100.0),
        ("cd ..", 87, 100.0),
        ("git commit", 54, 98.1),
        ("pytest", 43, 87.2),
    ]

    for i, (cmd, count, success) in enumerate(sample_commands, 1):
        commands_table.add_row(str(i), cmd, str(count), f"{success:.1f}%")

    console.print(commands_table)


def run_dashboard(db_stats: Dict[str, Any], use_tui: bool = True) -> None:
    """
    Run the dashboard interface.

    Args:
        db_stats: Database statistics dictionary
        use_tui: If True, use Textual TUI; otherwise use Rich fallback
    """
    if use_tui and TEXTUAL_AVAILABLE:
        app = DashboardApp(db_stats)
        app.run()
    elif RICH_AVAILABLE:
        show_dashboard_rich(db_stats)
    else:
        # Fallback to plain text
        print("\n" + "=" * 70)
        print("Daedelus Statistics Dashboard")
        print("=" * 70)
        print(f"\nTotal Commands: {db_stats.get('total_commands', 0):,}")
        print(f"Successful: {db_stats.get('successful_commands', 0):,}")
        print(f"Success Rate: {db_stats.get('success_rate', 0):.1f}%")
        print(f"Sessions: {db_stats.get('total_sessions', 0):,}")
        print("\n" + "=" * 70)


if __name__ == "__main__":
    # Test dashboard
    sample_stats = {
        "total_commands": 1247,
        "successful_commands": 1189,
        "success_rate": 95.3,
        "total_sessions": 42,
        "database_size_bytes": 1024 * 350,
    }

    print("Testing Daedelus Dashboard...")
    print(f"Textual available: {TEXTUAL_AVAILABLE}")
    print(f"Rich available: {RICH_AVAILABLE}")
    print()

    run_dashboard(sample_stats, use_tui=False)  # Use Rich fallback for testing
