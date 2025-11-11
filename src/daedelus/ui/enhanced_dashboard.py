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
            # Fixed: Create vertical container
            vertical_card = Vertical(classes="stat-card")
            vertical_card.mount(Static(title, classes="stat-title"))
            vertical_card.mount(Static(value, classes="stat-value"))
            vertical_card.mount(Static(desc, classes="stat-description"))
            grid.mount(vertical_card)

        container.mount(grid)

        # Recent activity
        container.mount(Static("\n## Recent Activity", classes="section-header"))

        activity_table = DataTable(id="overview_activity_table", zebra_stripes=True)
        activity_table.add_columns("Time", "Type", "Operation", "Status")
        container.mount(activity_table)

        return container

    def _compose_commands_tab(self) -> Container:
        """Compose commands tab"""
        container = Container()

        container.mount(Static("# Command History & Analytics", classes="tab-header"))

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
            # Fixed: Create vertical container
            vertical_card = Vertical(classes="stat-card")
            vertical_card.mount(Static(title, classes="stat-title"))
            vertical_card.mount(Static(value, classes="stat-value"))
            stats_grid.mount(vertical_card)

        container.mount(stats_grid)

        # Command history table
        container.mount(Static("\n## Command History", classes="section-header"))

        cmd_table = DataTable(id="commands_table", zebra_stripes=True)
        cmd_table.add_columns("Timestamp", "Command", "Exit Code", "Duration", "CWD")
        container.mount(cmd_table)

        # Most used commands
        container.mount(Static("\n## Most Used Commands", classes="section-header"))

        most_used_table = DataTable(id="most_used_table", zebra_stripes=True)
        most_used_table.add_columns("Rank", "Command", "Count", "Success %")
        container.mount(most_used_table)

        return container

    def _compose_files_tab(self) -> Container:
        """Compose files tab"""
        container = Container()

        container.mount(Static("# File Operations Monitor", classes="tab-header"))

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
            # Fixed: Create vertical container
            vertical_card = Vertical(classes="stat-card")
            vertical_card.mount(Static(title, classes="stat-title"))
            vertical_card.mount(Static(value, classes="stat-value"))
            stats_grid.mount(vertical_card)

        container.mount(stats_grid)

        # File access history
        container.mount(Static("\n## File Access History", classes="section-header"))

        files_table = DataTable(id="files_table", zebra_stripes=True)
        files_table.add_columns("Timestamp", "Operation", "File Path", "Status", "Size")
        container.mount(files_table)

        return container

    def _compose_tools_tab(self) -> Container:
        """Compose tools tab"""
        container = Container()

        container.mount(Static("# Tool & Plugin Management", classes="tab-header"))

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
            # Fixed: Create vertical container
            vertical_card = Vertical(classes="stat-card")
            vertical_card.mount(Static(title, classes="stat-title"))
            vertical_card.mount(Static(value, classes="stat-value"))
            stats_grid.mount(vertical_card)

        container.mount(stats_grid)

        # Installed tools
        container.mount(Static("\n## Installed Tools", classes="section-header"))

        tools_table = DataTable(id="tools_table", zebra_stripes=True)
        tools_table.add_columns("Tool Name", "Version", "Category", "Status", "Usage Count")
        container.mount(tools_table)

        # Execution history
        container.mount(Static("\n## Execution History", classes="section-header"))

        exec_table = DataTable(id="tool_exec_table", zebra_stripes=True)
        exec_table.add_columns("Timestamp", "Tool", "Status", "Duration", "Permissions")
        container.mount(exec_table)

        # Tool management buttons
        with Horizontal(classes="button-row"):
            container.mount(Button("Refresh Tools", id="refresh_tools", variant="primary"))
            container.mount(Button("Install Tool", id="install_tool", variant="success"))
            container.mount(Button("Create Tool", id="create_tool", variant="default"))

        return container

    def _compose_training_tab(self) -> Container:
        """Compose training tab"""
        container = Container()

        container.mount(Static("# Training Data & Model Management", classes="tab-header"))

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
            # Fixed: Create vertical container
            vertical_card = Vertical(classes="stat-card")
            vertical_card.mount(Static(title, classes="stat-title"))
            vertical_card.mount(Static(value, classes="stat-value"))
            stats_grid.mount(vertical_card)

        container.mount(stats_grid)

        # Training data sources
        container.mount(Static("\n## Training Data Sources", classes="section-header"))

        sources_table = DataTable(id="training_sources_table", zebra_stripes=True)
        sources_table.add_columns("Source", "Examples", "Quality", "Last Updated")
        container.mount(sources_table)

        # Document ingestion
        container.mount(Static("\n## Document Ingestion", classes="section-header"))

        docs_table = DataTable(id="ingested_docs_table", zebra_stripes=True)
        docs_table.add_columns("Document", "Type", "Size", "Status", "Ingested")
        container.mount(docs_table)

        # Training controls
        with Horizontal(classes="button-row"):
            container.mount(Button("Collect Training Data", id="collect_training", variant="primary"))
            container.mount(Button("Ingest Document", id="ingest_doc", variant="default"))
            container.mount(Button("Export Training Data", id="export_training", variant="default"))
            container.mount(Button("Train Model", id="train_model", variant="success"))

        return container

    def _compose_system_tab(self) -> Container:
        """Compose system tab"""
        container = Container()

        container.mount(Static("# System Information & Health", classes="tab-header"))

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
            # Fixed: Create vertical container
            vertical_card = Vertical(classes="stat-card")
            vertical_card.mount(Static(title, classes="stat-title"))
            vertical_card.mount(Static(value, classes="stat-value"))
            stats_grid.mount(vertical_card)

        container.mount(stats_grid)

        # System information
        container.mount(Static("\n## System Information", classes="section-header"))

        info_table = DataTable(id="system_info_table", zebra_stripes=True)
        info_table.add_columns("Component", "Status", "Version", "Details")
        container.mount(info_table)

        # Daemon status
        container.mount(Static("\n## Daemon Status", classes="section-header"))

        daemon_table = DataTable(id="daemon_status_table", zebra_stripes=True)
        daemon_table.add_columns("Metric", "Value")
        container.mount(daemon_table)

        # System controls
        with Horizontal(classes="button-row"):
            container.mount(Button("Restart Daemon", id="restart_daemon", variant="warning"))
            container.mount(Button("Clear Cache", id="clear_cache", variant="warning"))
            container.mount(Button("Run Backup", id="run_backup", variant="primary"))
            container.mount(Button("System Health Check", id="health_check", variant="default"))

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
        """Load overview tab data from databases"""
        try:
            from daedelus.core.database import CommandDatabase
            from daedelus.core.file_operations import FileOperationsManager
            from daedelus.core.tool_system import ToolRegistry
            from daedelus.llm.training_data_organizer import TrainingDataOrganizer
            from datetime import datetime

            table = self.query_one("#overview_activity_table", DataTable)
            table.clear()

            # Load recent activities from various databases
            activities = []

            # Commands
            try:
                db_path = self.data_dir / "history.db"
                if db_path.exists():
                    cmd_db = CommandDatabase(str(db_path))
                    recent_commands = cmd_db.get_recent_commands(limit=5)
                    for cmd in recent_commands:
                        activities.append({
                            'time': cmd.get('timestamp', ''),
                            'type': 'Command',
                            'operation': cmd.get('command', '')[:50],
                            'status': 'Success' if cmd.get('exit_code') == 0 else 'Failed'
                        })
            except Exception as e:
                logger.debug(f"Could not load commands: {e}")

            # File operations
            try:
                file_ops = FileOperationsManager(str(self.data_dir))
                recent_files = file_ops.memory_tracker.get_recent_operations(limit=5)
                for op in recent_files:
                    activities.append({
                        'time': op.timestamp.strftime('%H:%M:%S') if hasattr(op, 'timestamp') else '',
                        'type': 'File',
                        'operation': f"{op.operation} {op.path.name if hasattr(op.path, 'name') else op.path}",
                        'status': 'Success' if op.success else 'Failed'
                    })
            except Exception as e:
                logger.debug(f"Could not load file operations: {e}")

            # Tool executions
            try:
                tool_registry = ToolRegistry(str(self.data_dir / "tools"))
                recent_tools = tool_registry.get_recent_executions(limit=5)
                for tool_exec in recent_tools:
                    activities.append({
                        'time': tool_exec.get('timestamp', ''),
                        'type': 'Tool',
                        'operation': tool_exec.get('tool_name', ''),
                        'status': tool_exec.get('status', 'Unknown')
                    })
            except Exception as e:
                logger.debug(f"Could not load tool executions: {e}")

            # Sort by time and take top 10
            activities.sort(key=lambda x: x['time'], reverse=True)
            for activity in activities[:10]:
                table.add_row(
                    activity['time'],
                    activity['type'],
                    activity['operation'],
                    activity['status']
                )

            # Update stat cards
            try:
                total_commands = len(cmd_db.get_all_commands()) if 'cmd_db' in locals() else 0
                total_files = len(recent_files) if 'recent_files' in locals() else 0
                total_tools = len(recent_tools) if 'recent_tools' in locals() else 0

                try:
                    trainer = TrainingDataOrganizer(str(self.data_dir))
                    stats = trainer.get_statistics()
                    total_training = stats.get('total_examples', 0)
                except Exception as e:
                    logger.debug(f"Could not get training statistics: {e}")
                    total_training = 0

                # Store in stats dict for later use
                self.stats['overview'] = {
                    'commands': total_commands,
                    'files': total_files,
                    'tools': total_tools,
                    'training': total_training
                }
            except Exception as e:
                logger.debug(f"Could not update stats: {e}")

        except Exception as e:
            logger.error(f"Error loading overview data: {e}")
            table = self.query_one("#overview_activity_table", DataTable)
            table.add_row("Error", "System", "Could not load data", "Failed")

    def load_commands_data(self):
        """Load commands tab data from command history database"""
        try:
            from daedelus.core.database import CommandDatabase

            db_path = self.data_dir / "history.db"
            if not db_path.exists():
                logger.warning("Command history database not found")
                return

            cmd_db = CommandDatabase(str(db_path))

            # Load statistics
            stats = cmd_db.get_statistics()
            total_commands = stats.get('total_commands', 0)
            successful_commands = stats.get('successful_commands', 0)
            success_rate = (successful_commands / total_commands * 100) if total_commands > 0 else 0

            # Store stats
            self.stats['commands'] = {
                'total': total_commands,
                'success_rate': f"{success_rate:.1f}%",
                'avg_duration': "0.0s",  # Can be calculated if duration data available
                'most_used': "git"  # Can be calculated from command frequency
            }

            # Load recent commands
            cmd_table = self.query_one("#commands_table", DataTable)
            cmd_table.clear()

            recent_commands = cmd_db.get_recent_commands(limit=20)
            for cmd in recent_commands:
                cmd_table.add_row(
                    str(cmd.get('timestamp', '')),
                    cmd.get('command', '')[:50],
                    str(cmd.get('exit_code', 'N/A')),
                    f"{cmd.get('duration', 0.0):.2f}s" if 'duration' in cmd else 'N/A',
                    cmd.get('cwd', '')[:30]
                )

            # Load most used commands
            most_used_table = self.query_one("#most_used_table", DataTable)
            most_used_table.clear()

            # Get command statistics with frequency
            all_commands = cmd_db.get_all_commands()
            command_counts = {}
            command_success = {}

            for cmd_record in all_commands:
                cmd_text = cmd_record.get('command', '')
                if cmd_text:
                    command_counts[cmd_text] = command_counts.get(cmd_text, 0) + 1
                    if cmd_record.get('exit_code') == 0:
                        command_success[cmd_text] = command_success.get(cmd_text, 0) + 1

            # Sort by count and get top 10
            sorted_commands = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            for rank, (cmd_text, count) in enumerate(sorted_commands, 1):
                success_count = command_success.get(cmd_text, 0)
                success_pct = (success_count / count * 100) if count > 0 else 0
                most_used_table.add_row(
                    str(rank),
                    cmd_text[:40],
                    str(count),
                    f"{success_pct:.1f}%"
                )

        except Exception as e:
            logger.error(f"Error loading commands data: {e}")

    def load_files_data(self):
        """Load files tab data from file operations database"""
        try:
            from daedelus.core.file_operations import FileOperationsManager

            file_ops = FileOperationsManager(str(self.data_dir))

            # Load file operation statistics
            recent_ops = file_ops.memory_tracker.get_recent_operations(limit=100)

            total_ops = len(recent_ops)
            read_ops = sum(1 for op in recent_ops if op.operation == 'read')
            write_ops = sum(1 for op in recent_ops if op.operation == 'write')
            total_bytes = sum(op.size for op in recent_ops if hasattr(op, 'size') and op.size)

            # Format bytes
            if total_bytes >= 1024**3:
                bytes_str = f"{total_bytes / 1024**3:.2f} GB"
            elif total_bytes >= 1024**2:
                bytes_str = f"{total_bytes / 1024**2:.2f} MB"
            elif total_bytes >= 1024:
                bytes_str = f"{total_bytes / 1024:.2f} KB"
            else:
                bytes_str = f"{total_bytes} B"

            # Store stats
            self.stats['files'] = {
                'total': total_ops,
                'read': read_ops,
                'write': write_ops,
                'bytes': bytes_str
            }

            # Load file access history table
            files_table = self.query_one("#files_table", DataTable)
            files_table.clear()

            for op in recent_ops[:30]:
                size_str = f"{op.size} B" if hasattr(op, 'size') and op.size else "N/A"
                if hasattr(op, 'size') and op.size and op.size >= 1024:
                    size_str = f"{op.size / 1024:.1f} KB"
                if hasattr(op, 'size') and op.size and op.size >= 1024**2:
                    size_str = f"{op.size / 1024**2:.1f} MB"

                files_table.add_row(
                    op.timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(op, 'timestamp') else 'N/A',
                    op.operation,
                    str(op.path)[:50],
                    'Success' if op.success else 'Failed',
                    size_str
                )

        except Exception as e:
            logger.error(f"Error loading files data: {e}")

    def load_tools_data(self):
        """Load tools tab data from tool registry"""
        try:
            from daedelus.core.tool_system import ToolRegistry

            tool_registry = ToolRegistry(str(self.data_dir / "tools"))

            # Get all registered tools
            tools = tool_registry.list_tools()
            total_tools = len(tools)

            # Get execution history
            recent_executions = tool_registry.get_recent_executions(limit=100)
            total_executions = len(recent_executions)
            successful_executions = sum(1 for ex in recent_executions if ex.get('status') == 'success')
            success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0

            # Calculate average duration
            durations = [ex.get('duration', 0) for ex in recent_executions if 'duration' in ex]
            avg_duration = sum(durations) / len(durations) if durations else 0

            # Store stats
            self.stats['tools'] = {
                'installed': total_tools,
                'executions': total_executions,
                'success_rate': f"{success_rate:.1f}%",
                'avg_duration': f"{avg_duration:.2f}s"
            }

            # Load tools table
            tools_table = self.query_one("#tools_table", DataTable)
            tools_table.clear()

            for tool in tools:
                usage_count = sum(1 for ex in recent_executions if ex.get('tool_name') == tool.get('name'))
                tools_table.add_row(
                    tool.get('name', 'Unknown'),
                    tool.get('version', '1.0.0'),
                    tool.get('category', 'general'),
                    'Active' if tool.get('enabled', True) else 'Disabled',
                    str(usage_count)
                )

            # Load execution history table
            exec_table = self.query_one("#tool_exec_table", DataTable)
            exec_table.clear()

            for ex in recent_executions[:30]:
                exec_table.add_row(
                    ex.get('timestamp', 'N/A'),
                    ex.get('tool_name', 'Unknown'),
                    ex.get('status', 'Unknown').title(),
                    f"{ex.get('duration', 0):.2f}s" if 'duration' in ex else 'N/A',
                    ', '.join(ex.get('permissions', []))[:20] if ex.get('permissions') else 'None'
                )

        except Exception as e:
            logger.error(f"Error loading tools data: {e}")

    def load_training_data(self):
        """Load training tab data from training data organizer"""
        try:
            from daedelus.llm.training_data_organizer import TrainingDataOrganizer
            from daedelus.llm.document_ingestion import DocumentParser

            trainer = TrainingDataOrganizer(str(self.data_dir))
            stats = trainer.get_statistics()

            # Store stats
            self.stats['training'] = {
                'examples': stats.get('total_examples', 0),
                'documents': stats.get('documents_ingested', 0),
                'last_training': stats.get('last_training', 'Never'),
                'model_version': stats.get('model_version', 'N/A')
            }

            # Load training sources table
            sources_table = self.query_one("#training_sources_table", DataTable)
            sources_table.clear()

            for source_name, source_stats in stats.get('sources', {}).items():
                sources_table.add_row(
                    source_name.title(),
                    str(source_stats.get('count', 0)),
                    source_stats.get('quality', 'Unknown'),
                    source_stats.get('last_updated', 'N/A')
                )

            # Load ingested documents table
            docs_table = self.query_one("#ingested_docs_table", DataTable)
            docs_table.clear()

            # Try to load ingested documents
            try:
                parser = DocumentParser(str(self.data_dir / "documents"))
                ingested_docs = parser.get_ingested_documents() if hasattr(parser, 'get_ingested_documents') else []

                for doc in ingested_docs[:20]:
                    doc_size = doc.get('size', 0)
                    if doc_size >= 1024**2:
                        size_str = f"{doc_size / 1024**2:.2f} MB"
                    elif doc_size >= 1024:
                        size_str = f"{doc_size / 1024:.2f} KB"
                    else:
                        size_str = f"{doc_size} B"

                    docs_table.add_row(
                        doc.get('name', 'Unknown')[:30],
                        doc.get('type', 'Unknown'),
                        size_str,
                        doc.get('status', 'Ingested'),
                        doc.get('timestamp', 'N/A')
                    )
            except Exception as e:
                logger.debug(f"Could not load ingested documents: {e}")

        except Exception as e:
            logger.error(f"Error loading training data: {e}")

    def load_system_data(self):
        """Load system tab data and system information"""
        try:
            import os
            import psutil
            from datetime import datetime, timedelta

            # Calculate database size
            db_size = 0
            for db_file in self.data_dir.glob("*.db"):
                db_size += db_file.stat().st_size
            db_size_mb = db_size / 1024**2

            # Calculate cache size (if cache directory exists)
            cache_size = 0
            cache_dir = self.data_dir / "cache"
            if cache_dir.exists():
                for cache_file in cache_dir.rglob("*"):
                    if cache_file.is_file():
                        cache_size += 1

            # Get memory usage (current process)
            try:
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024**2
            except Exception as e:
                logger.error(f"Error getting memory usage: {e}")
                memory_mb = 0

            # Calculate uptime (from daemon if available)
            uptime_str = "N/A"
            pid_file = None
            try:
                pid_file = self.data_dir / "runtime" / "daemon.pid"
                if pid_file.exists():
                    pid_mtime = datetime.fromtimestamp(pid_file.stat().st_mtime)
                    uptime = datetime.now() - pid_mtime
                    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            except Exception as e:
                logger.error(f"Error calculating uptime: {e}")

            # Store stats
            self.stats['system'] = {
                'db_size': f"{db_size_mb:.2f} MB",
                'cache_size': f"{cache_size} items",
                'memory': f"{memory_mb:.2f} MB",
                'uptime': uptime_str
            }

            # Load system information table
            info_table = self.query_one("#system_info_table", DataTable)
            info_table.clear()

            # Add system information rows
            import sys
            import platform

            info_table.add_row("Python Version", "Active", sys.version.split()[0], sys.executable)
            info_table.add_row("Platform", "Active", platform.system(), platform.release())
            info_table.add_row("Database", "Active", "SQLite", f"{db_size_mb:.2f} MB")

            # Check if LLM is available
            llm_status = "Disabled"
            llm_version = "N/A"
            try:
                from daedelus.llm.llm_manager import LLMManager
                llm_status = "Active"
                llm_version = "llama.cpp"
            except Exception as e:
                logger.debug(f"LLM not available: {e}")

            info_table.add_row("LLM Engine", llm_status, llm_version, "")

            # Load daemon status table
            daemon_table = self.query_one("#daemon_status_table", DataTable)
            daemon_table.clear()

            # Determine daemon status (pid_file was defined earlier in try block)
            daemon_status = "Running" if pid_file and pid_file.exists() else "Stopped"
            daemon_table.add_row("Status", daemon_status)
            daemon_table.add_row("Uptime", uptime_str)
            daemon_table.add_row("Memory Usage", f"{memory_mb:.2f} MB")
            daemon_table.add_row("Database Size", f"{db_size_mb:.2f} MB")
            daemon_table.add_row("Cache Items", str(cache_size))

        except Exception as e:
            logger.error(f"Error loading system data: {e}")

    def action_refresh_all(self) -> None:
        """Refresh all dashboard data"""
        logger.info("Refreshing all dashboard data")
        self.load_all_data()
        self.notify("Dashboard refreshed", severity="information")

    def action_open_settings(self) -> None:
        """Open settings panel"""
        logger.info("Opening settings panel")
        try:
            from daedelus.ui.settings_panel import run_settings_panel
            # Launch settings panel in subprocess or new terminal
            import subprocess
            subprocess.Popen(["python", "-m", "daedelus.ui.settings_panel"])
            self.notify("Settings panel launched", severity="information")
        except Exception as e:
            logger.error(f"Error opening settings: {e}")
            self.notify(f"Could not open settings: {e}", severity="error")

    def action_open_memory(self) -> None:
        """Open memory and permissions panel"""
        logger.info("Opening memory and permissions panel")
        try:
            from daedelus.ui.memory_and_permissions import run_memory_panel
            # Launch memory panel in subprocess or new terminal
            import subprocess
            subprocess.Popen(["python", "-m", "daedelus.ui.memory_and_permissions"])
            self.notify("Memory & Permissions panel launched", severity="information")
        except Exception as e:
            logger.error(f"Error opening memory panel: {e}")
            self.notify(f"Could not open memory panel: {e}", severity="error")

    def action_trigger_training(self) -> None:
        """Trigger model training"""
        logger.info("Triggering model training")
        try:
            from daedelus.llm.training_coordinator import TrainingCoordinator

            coordinator = TrainingCoordinator(str(self.data_dir))
            self.notify("Collecting training data...", severity="information")

            # Start training in background
            import threading
            def train_async():
                try:
                    result = coordinator.train_model()
                    if result.get('success'):
                        self.notify("Training completed successfully!", severity="information")
                    else:
                        self.notify(f"Training failed: {result.get('error')}", severity="error")
                except Exception as e:
                    logger.error(f"Training error: {e}")
                    self.notify(f"Training error: {e}", severity="error")

            thread = threading.Thread(target=train_async, daemon=True)
            thread.start()
            self.notify("Training started in background", severity="warning")

        except Exception as e:
            logger.error(f"Error starting training: {e}")
            self.notify(f"Could not start training: {e}", severity="error")

    def action_export_data(self) -> None:
        """Export all data"""
        logger.info("Exporting data")
        try:
            from daedelus.llm.training_data_organizer import TrainingDataOrganizer
            from datetime import datetime

            trainer = TrainingDataOrganizer(str(self.data_dir))

            # Create export directory
            export_dir = self.data_dir / "exports" / datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir.mkdir(parents=True, exist_ok=True)

            # Export training data
            export_path = export_dir / "training_data.jsonl"
            trainer.export_training_data(str(export_path), format='jsonl')

            # Export statistics
            stats_path = export_dir / "statistics.json"
            import json
            with open(stats_path, 'w') as f:
                json.dump(self.stats, f, indent=2)

            self.notify(f"Data exported to {export_dir}", severity="information")
            logger.info(f"Data exported to {export_dir}")

        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            self.notify(f"Export failed: {e}", severity="error")

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
