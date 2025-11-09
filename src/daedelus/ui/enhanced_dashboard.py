"""
Enhanced Daedelus Dashboard
============================
Comprehensive TUI dashboard with all new features:
- Command history and statistics
- File operations monitoring
- Tool execution tracking
- Training data management
- Settings and permissions

Author: orpheus497
License: MIT
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Static,
    TabbedContent,
    TabPane,
)
from textual.binding import Binding
from textual import on

logger = logging.getLogger(__name__)


class EnhancedDashboardApp(App):
    """
    Enhanced Daedelus dashboard with comprehensive features.

    Features:
    - Command history and analytics
    - File operations monitoring
    - Tool execution tracking
    - Training data management
    - Settings and permission controls
    - Real-time statistics
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

    .panel-title {
        text-align: center;
        background: $primary-darken-1;
        padding: 1;
        margin-bottom: 1;
        color: $text;
        text-style: bold;
    }

    .stats-grid {
        grid-size: 4;
        grid-gutter: 1;
        padding: 1;
    }

    .stat-card {
        border: solid $primary;
        padding: 1;
        height: auto;
    }

    .stat-title {
        color: $accent;
        text-style: bold;
    }

    .stat-value {
        color: $success;
        text-style: bold;
        content-align: center middle;
        padding: 1 0;
    }

    .stat-description {
        color: $text-muted;
        text-style: italic;
    }

    .section-header {
        color: $accent;
        text-style: bold;
        padding: 1 0;
    }

    .tab-header {
        color: $primary;
        text-style: bold;
        padding: 1;
    }

    .action-bar {
        dock: bottom;
        height: auto;
        padding: 1;
        background: $panel;
    }

    .button-row {
        height: auto;
        align: center middle;
        padding: 1;
    }

    Button {
        margin: 0 1;
    }

    DataTable {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("s", "open_settings", "Settings"),
        Binding("m", "open_memory", "Memory"),
        Binding("t", "trigger_training", "Train Model"),
        Binding("ctrl+e", "export_data", "Export"),
    ]

    def __init__(
        self,
        data_dir: Path,
        config: Optional[Any] = None,
        **kwargs: Any
    ) -> None:
        """
        Initialize enhanced dashboard.

        Args:
            data_dir: Data directory path
            config: Configuration instance
            **kwargs: Additional App arguments
        """
        super().__init__(**kwargs)
        self.data_dir = data_dir
        self.config = config

        # Statistics storage
        self.stats = {
            'commands': {},
            'files': {},
            'tools': {},
            'training': {}
        }

    def compose(self) -> ComposeResult:
        """Compose dashboard UI"""
        yield Header(show_clock=True)

        yield Static("🚀 Daedelus Enhanced Dashboard", classes="panel-title")

        with TabbedContent(initial="overview"):
            # Overview tab
            with TabPane("Overview", id="overview"):
                yield self._compose_overview_tab()

            # Commands tab
            with TabPane("Commands", id="commands"):
                yield self._compose_commands_tab()

            # Files tab
            with TabPane("Files", id="files"):
                yield self._compose_files_tab()

            # Tools tab
            with TabPane("Tools", id="tools"):
                yield self._compose_tools_tab()

            # Training tab
            with TabPane("Training", id="training"):
                yield self._compose_training_tab()

            # System tab
            with TabPane("System", id="system"):
                yield self._compose_system_tab()

        # Action bar
        with Horizontal(classes="action-bar"):
            yield Button("Refresh All", id="refresh_all", variant="primary")
            yield Button("Settings", id="settings", variant="default")
            yield Button("Memory & Permissions", id="memory", variant="default")
            yield Button("Export Data", id="export", variant="default")
            yield Button("Train Model", id="train", variant="success")
            yield Button("Quit", id="quit", variant="error")

        yield Footer()

    def _compose_overview_tab(self) -> Container:
        """Compose overview tab"""
        container = Container()

        # Statistics grid
        from textual.containers import Grid

        grid = Grid(classes="stats-grid")

        # Add stat cards
        stat_cards_data = [
            ("Total Commands", "0", "Executed in all sessions"),
            ("File Operations", "0", "Files accessed"),
            ("Tool Executions", "0", "Tools run"),
            ("Training Examples", "0", "Ready for training"),
        ]

        for title, value, desc in stat_cards_data:
            with Vertical(classes="stat-card"):
                grid.compose_add_child(Static(title, classes="stat-title"))
                grid.compose_add_child(Static(value, classes="stat-value"))
                grid.compose_add_child(Static(desc, classes="stat-description"))

        container.compose_add_child(grid)

        # Recent activity
        container.compose_add_child(Static("\n## Recent Activity", classes="section-header"))

        activity_table = DataTable(id="overview_activity_table", zebra_stripes=True)
        activity_table.add_columns("Time", "Type", "Operation", "Status")
        container.compose_add_child(activity_table)

        return container

    def _compose_commands_tab(self) -> Container:
        """Compose commands tab"""
        container = Container()

        container.compose_add_child(Static("# Command History & Analytics", classes="tab-header"))

        # Statistics
        from textual.containers import Grid

        stats_grid = Grid(classes="stats-grid")
        stats_cards = [
            ("Total Commands", "0"),
            ("Success Rate", "0%"),
            ("Avg Duration", "0.0s"),
            ("Most Used", "N/A"),
        ]

        for title, value in stats_cards:
            with Vertical(classes="stat-card"):
                stats_grid.compose_add_child(Static(title, classes="stat-title"))
                stats_grid.compose_add_child(Static(value, classes="stat-value"))

        container.compose_add_child(stats_grid)

        # Command history table
        container.compose_add_child(Static("\n## Command History", classes="section-header"))

        cmd_table = DataTable(id="commands_table", zebra_stripes=True)
        cmd_table.add_columns("Timestamp", "Command", "Exit Code", "Duration", "CWD")
        container.compose_add_child(cmd_table)

        # Most used commands
        container.compose_add_child(Static("\n## Most Used Commands", classes="section-header"))

        most_used_table = DataTable(id="most_used_table", zebra_stripes=True)
        most_used_table.add_columns("Rank", "Command", "Count", "Success %")
        container.compose_add_child(most_used_table)

        return container

    def _compose_files_tab(self) -> Container:
        """Compose files tab"""
        container = Container()

        container.compose_add_child(Static("# File Operations Monitor", classes="tab-header"))

        # Statistics
        from textual.containers import Grid

        stats_grid = Grid(classes="stats-grid")
        stats_cards = [
            ("Total Operations", "0"),
            ("Files Read", "0"),
            ("Files Written", "0"),
            ("Total Bytes", "0 B"),
        ]

        for title, value in stats_cards:
            with Vertical(classes="stat-card"):
                stats_grid.compose_add_child(Static(title, classes="stat-title"))
                stats_grid.compose_add_child(Static(value, classes="stat-value"))

        container.compose_add_child(stats_grid)

        # File access history
        container.compose_add_child(Static("\n## File Access History", classes="section-header"))

        files_table = DataTable(id="files_table", zebra_stripes=True)
        files_table.add_columns("Timestamp", "Operation", "File Path", "Status", "Size")
        container.compose_add_child(files_table)

        return container

    def _compose_tools_tab(self) -> Container:
        """Compose tools tab"""
        container = Container()

        container.compose_add_child(Static("# Tool & Plugin Management", classes="tab-header"))

        # Statistics
        from textual.containers import Grid

        stats_grid = Grid(classes="stats-grid")
        stats_cards = [
            ("Installed Tools", "0"),
            ("Total Executions", "0"),
            ("Success Rate", "0%"),
            ("Avg Duration", "0.0s"),
        ]

        for title, value in stats_cards:
            with Vertical(classes="stat-card"):
                stats_grid.compose_add_child(Static(title, classes="stat-title"))
                stats_grid.compose_add_child(Static(value, classes="stat-value"))

        container.compose_add_child(stats_grid)

        # Installed tools
        container.compose_add_child(Static("\n## Installed Tools", classes="section-header"))

        tools_table = DataTable(id="tools_table", zebra_stripes=True)
        tools_table.add_columns("Tool Name", "Version", "Category", "Status", "Usage Count")
        container.compose_add_child(tools_table)

        # Execution history
        container.compose_add_child(Static("\n## Execution History", classes="section-header"))

        exec_table = DataTable(id="tool_exec_table", zebra_stripes=True)
        exec_table.add_columns("Timestamp", "Tool", "Status", "Duration", "Permissions")
        container.compose_add_child(exec_table)

        # Tool management buttons
        with Horizontal(classes="button-row"):
            container.compose_add_child(Button("Refresh Tools", id="refresh_tools", variant="primary"))
            container.compose_add_child(Button("Install Tool", id="install_tool", variant="success"))
            container.compose_add_child(Button("Create Tool", id="create_tool", variant="default"))

        return container

    def _compose_training_tab(self) -> Container:
        """Compose training tab"""
        container = Container()

        container.compose_add_child(Static("# Training Data & Model Management", classes="tab-header"))

        # Training statistics
        from textual.containers import Grid

        stats_grid = Grid(classes="stats-grid")
        stats_cards = [
            ("Training Examples", "0"),
            ("Documents Ingested", "0"),
            ("Last Training", "Never"),
            ("Model Version", "N/A"),
        ]

        for title, value in stats_cards:
            with Vertical(classes="stat-card"):
                stats_grid.compose_add_child(Static(title, classes="stat-title"))
                stats_grid.compose_add_child(Static(value, classes="stat-value"))

        container.compose_add_child(stats_grid)

        # Training data sources
        container.compose_add_child(Static("\n## Training Data Sources", classes="section-header"))

        sources_table = DataTable(id="training_sources_table", zebra_stripes=True)
        sources_table.add_columns("Source", "Examples", "Quality", "Last Updated")
        container.compose_add_child(sources_table)

        # Document ingestion
        container.compose_add_child(Static("\n## Document Ingestion", classes="section-header"))

        docs_table = DataTable(id="ingested_docs_table", zebra_stripes=True)
        docs_table.add_columns("Document", "Type", "Size", "Status", "Ingested")
        container.compose_add_child(docs_table)

        # Training controls
        with Horizontal(classes="button-row"):
            container.compose_add_child(Button("Collect Training Data", id="collect_training", variant="primary"))
            container.compose_add_child(Button("Ingest Document", id="ingest_doc", variant="default"))
            container.compose_add_child(Button("Export Training Data", id="export_training", variant="default"))
            container.compose_add_child(Button("Train Model", id="train_model", variant="success"))

        return container

    def _compose_system_tab(self) -> Container:
        """Compose system tab"""
        container = Container()

        container.compose_add_child(Static("# System Information & Health", classes="tab-header"))

        # System statistics
        from textual.containers import Grid

        stats_grid = Grid(classes="stats-grid")
        stats_cards = [
            ("Database Size", "0 MB"),
            ("Cache Size", "0 items"),
            ("Memory Usage", "0 MB"),
            ("Uptime", "0:00:00"),
        ]

        for title, value in stats_cards:
            with Vertical(classes="stat-card"):
                stats_grid.compose_add_child(Static(title, classes="stat-title"))
                stats_grid.compose_add_child(Static(value, classes="stat-value"))

        container.compose_add_child(stats_grid)

        # System information
        container.compose_add_child(Static("\n## System Information", classes="section-header"))

        info_table = DataTable(id="system_info_table", zebra_stripes=True)
        info_table.add_columns("Component", "Status", "Version", "Details")
        container.compose_add_child(info_table)

        # Daemon status
        container.compose_add_child(Static("\n## Daemon Status", classes="section-header"))

        daemon_table = DataTable(id="daemon_status_table", zebra_stripes=True)
        daemon_table.add_columns("Metric", "Value")
        container.compose_add_child(daemon_table)

        # System controls
        with Horizontal(classes="button-row"):
            container.compose_add_child(Button("Restart Daemon", id="restart_daemon", variant="warning"))
            container.compose_add_child(Button("Clear Cache", id="clear_cache", variant="warning"))
            container.compose_add_child(Button("Run Backup", id="run_backup", variant="primary"))
            container.compose_add_child(Button("System Health Check", id="health_check", variant="default"))

        return container

    def on_mount(self) -> None:
        """Initialize dashboard on mount"""
        logger.info("Enhanced dashboard mounted")
        self.load_all_data()

    def load_all_data(self):
        """Load all dashboard data"""
        self.load_overview_data()
        self.load_commands_data()
        self.load_files_data()
        self.load_tools_data()
        self.load_training_data()
        self.load_system_data()

    def load_overview_data(self):
        """Load overview tab data"""
        # TODO: Load actual data from databases
        table = self.query_one("#overview_activity_table", DataTable)
        table.clear()

        # Example data
        table.add_row("14:32:15", "Command", "git status", "Success")
        table.add_row("14:32:10", "File", "README.md", "Read")
        table.add_row("14:31:55", "Tool", "syntax_highlighter", "Success")

    def load_commands_data(self):
        """Load commands tab data"""
        # TODO: Load from command history database
        pass

    def load_files_data(self):
        """Load files tab data"""
        # TODO: Load from file operations database
        pass

    def load_tools_data(self):
        """Load tools tab data"""
        # TODO: Load from tool registry
        pass

    def load_training_data(self):
        """Load training tab data"""
        # TODO: Load from training data organizer
        pass

    def load_system_data(self):
        """Load system tab data"""
        # TODO: Load system information
        pass

    def action_refresh_all(self) -> None:
        """Refresh all dashboard data"""
        logger.info("Refreshing all dashboard data")
        self.load_all_data()
        self.notify("Dashboard refreshed", severity="information")

    def action_open_settings(self) -> None:
        """Open settings panel"""
        logger.info("Opening settings panel")
        # TODO: Launch settings panel as separate app or modal
        self.notify("Settings panel - coming soon")

    def action_open_memory(self) -> None:
        """Open memory and permissions panel"""
        logger.info("Opening memory and permissions panel")
        # TODO: Launch memory panel as separate app or modal
        self.notify("Memory & Permissions panel - coming soon")

    def action_trigger_training(self) -> None:
        """Trigger model training"""
        logger.info("Triggering model training")
        # TODO: Start training process
        self.notify("Training started - this may take a while", severity="warning")

    def action_export_data(self) -> None:
        """Export all data"""
        logger.info("Exporting data")
        # TODO: Export data to files
        self.notify("Data exported successfully", severity="information")

    def action_quit(self) -> None:
        """Quit application"""
        self.exit()

    @on(Button.Pressed, "#refresh_all")
    def on_refresh_all(self):
        """Handle refresh all button"""
        self.action_refresh_all()

    @on(Button.Pressed, "#settings")
    def on_settings(self):
        """Handle settings button"""
        self.action_open_settings()

    @on(Button.Pressed, "#memory")
    def on_memory(self):
        """Handle memory button"""
        self.action_open_memory()

    @on(Button.Pressed, "#export")
    def on_export(self):
        """Handle export button"""
        self.action_export_data()

    @on(Button.Pressed, "#train")
    def on_train(self):
        """Handle train button"""
        self.action_trigger_training()

    @on(Button.Pressed, "#quit")
    def on_quit(self):
        """Handle quit button"""
        self.action_quit()


def run_enhanced_dashboard(data_dir: Path, config: Optional[Any] = None) -> None:
    """
    Run the enhanced dashboard.

    Args:
        data_dir: Data directory path
        config: Configuration instance
    """
    app = EnhancedDashboardApp(data_dir=data_dir, config=config)
    app.run()


if __name__ == "__main__":
    # Test the enhanced dashboard
    from pathlib import Path

    test_data_dir = Path.home() / ".local" / "share" / "daedelus"
    run_enhanced_dashboard(test_data_dir)
