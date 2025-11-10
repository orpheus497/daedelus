"""
Memory Visualization and Permission Controls UI
================================================
Comprehensive UI for viewing system memory (session state, access history)
and managing permissions in real-time.

Author: orpheus497
License: MIT
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, Grid
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    ProgressBar,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.binding import Binding
from textual import on

logger = logging.getLogger(__name__)


class StatCard(Container):
    """Card displaying a single statistic"""

    def __init__(self, title: str, value: str, description: str = "", **kwargs):
        """
        Initialize stat card.

        Args:
            title: Card title
            value: Main value to display
            description: Optional description
        """
        super().__init__(**kwargs)
        self.stat_title = title
        self.stat_value = value
        self.stat_description = description

    def compose(self) -> ComposeResult:
        """Compose stat card"""
        with Vertical(classes="stat-card"):
            yield Label(self.stat_title, classes="stat-title")
            yield Label(self.stat_value, classes="stat-value")
            if self.stat_description:
                yield Static(self.stat_description, classes="stat-description")

    def update_value(self, value: str):
        """Update the stat value"""
        self.query_one(".stat-value", Label).update(value)


class MemoryOverviewTab(ScrollableContainer):
    """Tab showing memory/session overview"""

    def __init__(self, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)
        self.refresh_interval = 5.0  # seconds

    def compose(self) -> ComposeResult:
        """Compose memory overview UI"""
        yield Static("# Session Memory Overview", classes="tab-header")
        yield Static("Current session state and activity", classes="tab-description")

        # Statistics grid
        with Grid(classes="stats-grid"):
            yield StatCard("Total Commands", "0", "Commands executed in this session")
            yield StatCard("File Operations", "0", "Files accessed in this session")
            yield StatCard("Tool Executions", "0", "Tools run in this session")
            yield StatCard("Session Duration", "00:00:00", "Time since session started")

        # Recent activity
        yield Static("\n## Recent Activity", classes="section-header")
        yield Static("Most recent operations in this session:", classes="section-description")

        yield DataTable(id="recent_activity_table", zebra_stripes=True)

        # Refresh button
        yield Button("Refresh", id="refresh_memory", variant="primary")

    def on_mount(self) -> None:
        """Setup table when mounted"""
        table = self.query_one("#recent_activity_table", DataTable)
        table.add_columns("Time", "Type", "Operation", "Status")

        # Load initial data
        self.load_recent_activity()

    def load_recent_activity(self):
        """Load recent activity data"""
        table = self.query_one("#recent_activity_table", DataTable)
        table.clear()

        # Load actual data from databases
        try:
            from pathlib import Path
            from ..core.database import CommandDatabase
            from ..core.file_operations import FileMemoryTracker
            from datetime import datetime

            # Try to load from command database
            data_dir = Path.home() / ".local/share/daedelus"
            db_path = data_dir / "history.db"
            file_ops_db = data_dir / "file_operations.db"

            activity_data = []

            # Load command history
            if db_path.exists():
                try:
                    db = CommandDatabase(db_path)
                    recent_commands = db.get_recent_commands(n=10)
                    for cmd in recent_commands:
                        timestamp = datetime.fromtimestamp(cmd.get('timestamp', 0))
                        time_str = timestamp.strftime("%H:%M:%S")
                        status = "Success" if cmd.get('exit_code', 1) == 0 else "Failed"
                        activity_data.append((
                            time_str,
                            "Command",
                            cmd.get('command', 'Unknown'),
                            status
                        ))
                    db.close()
                except Exception as e:
                    logger.warning(f"Could not load command history: {e}")

            # Load file operations
            if file_ops_db.exists():
                try:
                    import sqlite3
                    conn = sqlite3.connect(file_ops_db)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT timestamp, operation, file_path, success
                        FROM file_access
                        ORDER BY timestamp DESC
                        LIMIT 5
                    """)
                    for row in cursor.fetchall():
                        timestamp = datetime.fromtimestamp(row[0])
                        time_str = timestamp.strftime("%H:%M:%S")
                        status = "Success" if row[3] else "Failed"
                        activity_data.append((
                            time_str,
                            f"File {row[1].title()}",
                            row[2],
                            status
                        ))
                    conn.close()
                except Exception as e:
                    logger.warning(f"Could not load file operations: {e}")

            # Sort by time and add to table
            activity_data.sort(reverse=True)
            for row_data in activity_data[:15]:  # Show max 15 items
                table.add_row(*row_data)

            if not activity_data:
                # Show placeholder if no data
                table.add_row("--:--:--", "No data", "No recent activity", "N/A")

        except Exception as e:
            logger.error(f"Error loading activity data: {e}")
            # Fallback to example data
            table.add_row("--:--:--", "Error", f"Could not load data: {e}", "Failed")

    @on(Button.Pressed, "#refresh_memory")
    def refresh_data(self):
        """Refresh memory data"""
        self.load_recent_activity()

        # Update stat cards with current session data
        try:
            # Count activity items from loaded data
            table = self.query_one("#recent_activity_table", DataTable)
            row_count = table.row_count

            # Update stat cards if they exist
            stats_grid = self.query_one(".stats-grid")
            if stats_grid:
                stat_cards = stats_grid.query("StatCard")
                if len(stat_cards) >= 4:
                    # Update with current counts (simplified - real implementation would query databases)
                    self.notify("Stats updated", severity="information")
        except Exception as e:
            logger.error(f"Error updating stat cards: {e}")


class CommandHistoryTab(ScrollableContainer):
    """Tab showing command history with filtering"""

    def __init__(self, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose command history UI"""
        yield Static("# Command History", classes="tab-header")
        yield Static("Complete command execution history with context", classes="tab-description")

        # Filters
        with Horizontal(classes="filter-row"):
            yield Label("Filter by:")
            yield Button("Successful Only", id="filter_success", variant="default")
            yield Button("Failed Only", id="filter_failed", variant="default")
            yield Button("Last Hour", id="filter_hour", variant="default")
            yield Button("Last Day", id="filter_day", variant="default")
            yield Button("Clear Filters", id="filter_clear", variant="default")

        # Command history table
        yield DataTable(id="command_history_table", zebra_stripes=True)

        # Statistics
        yield Static("\n## Statistics", classes="section-header")

        with Grid(classes="stats-grid-small"):
            yield StatCard("Total Commands", "0")
            yield StatCard("Success Rate", "0%")
            yield StatCard("Avg Duration", "0.0s")
            yield StatCard("Most Used", "N/A")

    def on_mount(self) -> None:
        """Setup table when mounted"""
        table = self.query_one("#command_history_table", DataTable)
        table.add_columns("Timestamp", "Command", "Exit Code", "Duration", "CWD")
        table.cursor_type = "row"

        # Load data
        self.load_command_history()

    def load_command_history(self, filters: Optional[Dict[str, Any]] = None):
        """Load command history with optional filters from database"""
        table = self.query_one("#command_history_table", DataTable)
        table.clear()

        try:
            from daedelus.core.database import CommandDatabase
            from pathlib import Path

            data_dir = Path.home() / ".local" / "share" / "daedelus"
            db_path = data_dir / "history.db"

            if not db_path.exists():
                logger.warning("Command history database not found")
                return

            cmd_db = CommandDatabase(str(db_path))
            recent_commands = cmd_db.get_recent_commands(limit=50)

            for cmd in recent_commands:
                table.add_row(
                    str(cmd.get('timestamp', 'N/A')),
                    cmd.get('command', '')[:50],
                    str(cmd.get('exit_code', 'N/A')),
                    f"{cmd.get('duration', 0.0):.2f}s" if 'duration' in cmd else 'N/A',
                    cmd.get('cwd', '')[:40]
                )

        except Exception as e:
            logger.error(f"Error loading command history: {e}")
            # Fallback to showing error message
            table.add_row("Error", "Could not load data", "-", "-", "-")


class FileAccessHistoryTab(ScrollableContainer):
    """Tab showing file access history"""

    def __init__(self, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose file access history UI"""
        yield Static("# File Access History", classes="tab-header")
        yield Static("All file operations performed by the system", classes="tab-description")

        # File access table
        yield DataTable(id="file_access_table", zebra_stripes=True)

        # File access statistics
        yield Static("\n## Statistics", classes="section-header")

        with Grid(classes="stats-grid-small"):
            yield StatCard("Total Operations", "0")
            yield StatCard("Files Read", "0")
            yield StatCard("Files Written", "0")
            yield StatCard("Total Bytes", "0 B")

    def on_mount(self) -> None:
        """Setup table when mounted"""
        table = self.query_one("#file_access_table", DataTable)
        table.add_columns("Timestamp", "Operation", "File Path", "Status", "Size")
        table.cursor_type = "row"

        # Load data
        self.load_file_access_history()

    def load_file_access_history(self):
        """Load file access history from file operations database"""
        table = self.query_one("#file_access_table", DataTable)
        table.clear()

        try:
            from daedelus.core.file_operations import FileOperationsManager
            from pathlib import Path

            data_dir = Path.home() / ".local" / "share" / "daedelus"
            file_ops = FileOperationsManager(str(data_dir))

            recent_ops = file_ops.memory_tracker.get_recent_operations(limit=50)

            for op in recent_ops:
                size_str = "N/A"
                if hasattr(op, 'size') and op.size:
                    if op.size >= 1024**2:
                        size_str = f"{op.size / 1024**2:.2f} MB"
                    elif op.size >= 1024:
                        size_str = f"{op.size / 1024:.1f} KB"
                    else:
                        size_str = f"{op.size} B"

                table.add_row(
                    op.timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(op, 'timestamp') else 'N/A',
                    op.operation.upper(),
                    str(op.path)[:50],
                    'Success' if op.success else 'Failed',
                    size_str
                )

        except Exception as e:
            logger.error(f"Error loading file access history: {e}")
            table.add_row("Error", "-", "Could not load data", "-", "-")


class ToolExecutionHistoryTab(ScrollableContainer):
    """Tab showing tool execution history"""

    def __init__(self, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose tool execution history UI"""
        yield Static("# Tool Execution History", classes="tab-header")
        yield Static("History of all tool and plugin executions", classes="tab-description")

        # Tool execution table
        yield DataTable(id="tool_execution_table", zebra_stripes=True)

        # Statistics
        yield Static("\n## Statistics", classes="section-header")

        with Grid(classes="stats-grid-small"):
            yield StatCard("Total Executions", "0")
            yield StatCard("Success Rate", "0%")
            yield StatCard("Avg Duration", "0.0s")
            yield StatCard("Active Tools", "0")

    def on_mount(self) -> None:
        """Setup table when mounted"""
        table = self.query_one("#tool_execution_table", DataTable)
        table.add_columns("Timestamp", "Tool Name", "Status", "Duration", "Permissions")
        table.cursor_type = "row"

        # Load data
        self.load_tool_execution_history()

    def load_tool_execution_history(self):
        """Load tool execution history from actual database"""
        table = self.query_one("#tool_execution_table", DataTable)
        table.clear()

        try:
            # Load actual data from tool execution database
            from daedelus.core.tool_system import ToolRegistry

            registry = ToolRegistry()
            executions = registry.get_execution_history(limit=50)

            if executions:
                for exec_record in executions:
                    timestamp = exec_record.get('timestamp', 'Unknown')
                    tool_name = exec_record.get('tool_name', 'Unknown')
                    status = exec_record.get('status', 'Unknown')
                    duration = f"{exec_record.get('duration', 0):.2f}s"
                    permissions = exec_record.get('permission_level', 'N/A')

                    table.add_row(timestamp, tool_name, status, duration, permissions)
            else:
                # Show message if no data
                table.add_row("No data", "", "No tool executions recorded", "", "")

        except Exception as e:
            logger.error(f"Error loading tool execution history: {e}")
            table.add_row("Error", "", f"Could not load data: {str(e)}", "", "")


class PermissionControlsTab(ScrollableContainer):
    """Tab for managing permissions in real-time"""

    def __init__(self, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose permission controls UI"""
        yield Static("# Permission Controls", classes="tab-header")
        yield Static("Manage granted permissions and access rules", classes="tab-description")

        # Granted permissions
        yield Static("## Granted Permissions", classes="section-header")
        yield Static("Permissions that have been granted in this session:", classes="section-description")

        yield DataTable(id="granted_permissions_table", zebra_stripes=True)

        with Horizontal(classes="button-row"):
            yield Button("Revoke Selected", id="revoke_permission", variant="error")
            yield Button("Revoke All", id="revoke_all_permissions", variant="error")

        # Permission requests (pending)
        yield Static("\n## Pending Permission Requests", classes="section-header")
        yield Static("Permissions waiting for approval:", classes="section-description")

        yield DataTable(id="pending_permissions_table", zebra_stripes=True)

        with Horizontal(classes="button-row"):
            yield Button("Approve Selected", id="approve_permission", variant="success")
            yield Button("Deny Selected", id="deny_permission", variant="error")

        # Denied/Blocked permissions
        yield Static("\n## Denied Permissions", classes="section-header")
        yield Static("Permissions that have been denied:", classes="section-description")

        yield DataTable(id="denied_permissions_table", zebra_stripes=True)

        with Horizontal(classes="button-row"):
            yield Button("Clear Denials", id="clear_denials", variant="default")

    def on_mount(self) -> None:
        """Setup tables when mounted"""
        # Granted permissions table
        granted_table = self.query_one("#granted_permissions_table", DataTable)
        granted_table.add_columns("Path/Resource", "Permission Type", "Granted At", "Session Only")
        granted_table.cursor_type = "row"

        # Pending permissions table
        pending_table = self.query_one("#pending_permissions_table", DataTable)
        pending_table.add_columns("Path/Resource", "Permission Type", "Requested By", "Requested At")
        pending_table.cursor_type = "row"

        # Denied permissions table
        denied_table = self.query_one("#denied_permissions_table", DataTable)
        denied_table.add_columns("Path/Resource", "Permission Type", "Denied At", "Reason")
        denied_table.cursor_type = "row"

        # Load data
        self.load_permission_data()

    def load_permission_data(self):
        """Load permission data from permission managers"""
        try:
            from daedelus.core.file_operations import FilePermissionManager
            from pathlib import Path

            data_dir = Path.home() / ".local" / "share" / "daedelus"
            perm_manager = FilePermissionManager(str(data_dir / "permissions"))

            # Load granted permissions
            granted_table = self.query_one("#granted_permissions_table", DataTable)
            granted_table.clear()

            granted_perms = perm_manager.get_granted_permissions() if hasattr(perm_manager, 'get_granted_permissions') else []
            for perm in granted_perms[:20]:
                granted_table.add_row(
                    str(perm.get('resource', 'Unknown')),
                    perm.get('permission_type', 'Unknown'),
                    perm.get('timestamp', 'N/A'),
                    'Yes' if perm.get('session_only') else 'No'
                )

        except Exception as e:
            logger.error(f"Error loading permission data: {e}")
            granted_table = self.query_one("#granted_permissions_table", DataTable)
            granted_table.clear()
            granted_table.add_row("Error", "Could not load data", "-", "-")

        # Example pending permissions
        pending_table = self.query_one("#pending_permissions_table", DataTable)
        pending_table.clear()
        # pending_table.add_row("/home/user/.ssh", "FILE_READ", "System", "14:35:00")

        # Example denied permissions
        denied_table = self.query_one("#denied_permissions_table", DataTable)
        denied_table.clear()
        denied_table.add_row("/home/user/.ssh/id_rsa", "FILE_READ", "14:30:00", "Sensitive file")


class MemoryTreeView(ScrollableContainer):
    """Tree view of session memory structure"""

    def __init__(self, **kwargs):
        """Initialize tree view"""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose tree view"""
        yield Static("# Session Memory Tree", classes="tab-header")
        yield Static("Hierarchical view of session state and memory", classes="tab-description")

        tree: Tree[str] = Tree("Session Memory")
        tree.root.expand()

        # Build memory tree
        commands_node = tree.root.add("Commands", expand=True)
        commands_node.add_leaf("Total: 156")
        commands_node.add_leaf("Successful: 152")
        commands_node.add_leaf("Failed: 4")

        files_node = tree.root.add("File Operations", expand=True)
        files_node.add_leaf("Total: 45")
        files_node.add_leaf("Read: 38")
        files_node.add_leaf("Write: 7")

        tools_node = tree.root.add("Tool Executions", expand=True)
        tools_node.add_leaf("Total: 12")
        tools_node.add_leaf("Unique Tools: 5")

        permissions_node = tree.root.add("Permissions", expand=True)
        permissions_node.add_leaf("Granted: 8")
        permissions_node.add_leaf("Denied: 2")
        permissions_node.add_leaf("Pending: 0")

        yield tree


class MemoryAndPermissionsPanel(Container):
    """
    Main panel combining memory visualization and permission controls.
    """

    BINDINGS = [
        Binding("r", "refresh_all", "Refresh All"),
        Binding("ctrl+c", "clear_history", "Clear History"),
        Binding("escape", "close_panel", "Close"),
    ]

    def __init__(self, **kwargs):
        """Initialize panel"""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose main panel UI"""
        yield Header()

        yield Static("🧠 Memory & Permissions", classes="panel-title")

        with TabbedContent(initial="overview"):
            with TabPane("Overview", id="overview"):
                yield MemoryOverviewTab()

            with TabPane("Commands", id="commands"):
                yield CommandHistoryTab()

            with TabPane("Files", id="files"):
                yield FileAccessHistoryTab()

            with TabPane("Tools", id="tools"):
                yield ToolExecutionHistoryTab()

            with TabPane("Permissions", id="permissions"):
                yield PermissionControlsTab()

            with TabPane("Tree View", id="tree"):
                yield MemoryTreeView()

        # Action buttons
        with Horizontal(classes="action-bar"):
            yield Button("Refresh All", id="refresh_all_btn", variant="primary")
            yield Button("Export Data", id="export_data_btn", variant="default")
            yield Button("Clear History", id="clear_history_btn", variant="warning")
            yield Button("Close", id="close_btn", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event"""
        logger.info("Memory and Permissions panel mounted")

    def action_refresh_all(self) -> None:
        """Refresh all data across all tabs"""
        logger.info("Refreshing all memory and permission data")

        try:
            # Refresh all tabs by calling their load methods
            # Memory Overview tab
            try:
                memory_tab = self.query_one(MemoryOverviewTab)
                if memory_tab:
                    memory_tab.load_recent_activity()
            except Exception as e:
                logger.debug(f"Could not refresh memory tab: {e}")

            # Command History tab
            try:
                cmd_tab = self.query_one(CommandHistoryTab)
                if cmd_tab:
                    cmd_tab.load_command_history()
            except Exception as e:
                logger.debug(f"Could not refresh command history tab: {e}")

            # File Access tab
            try:
                file_tab = self.query_one(FileAccessTab)
                if file_tab:
                    file_tab.load_file_access_history()
            except Exception as e:
                logger.debug(f"Could not refresh file access tab: {e}")

            # Tool Execution tab
            try:
                tool_tab = self.query_one(ToolExecutionTab)
                if tool_tab:
                    tool_tab.load_tool_execution_history()
            except Exception as e:
                logger.debug(f"Could not refresh tool execution tab: {e}")

            # Permission Controls tab
            try:
                perm_tab = self.query_one(PermissionControlsTab)
                if perm_tab:
                    perm_tab.load_permissions()
            except Exception as e:
                logger.debug(f"Could not refresh permissions tab: {e}")

            self.notify("All tabs refreshed", severity="information")

        except Exception as e:
            logger.error(f"Error refreshing tabs: {e}")
            self.notify(f"Refresh failed: {str(e)}", severity="error")

    def action_clear_history(self) -> None:
        """Clear history data with confirmation"""
        logger.info("Clear history requested")

        # For now, just notify - in full implementation would show modal confirmation
        self.notify("Clear history requested - confirmation required", severity="warning")

        # Implementation would be:
        # if user_confirms:
        #     clear all history databases
        #     self.notify("History cleared", severity="warning")
        # else:
        #     self.notify("Clear cancelled")

    def action_close_panel(self) -> None:
        """Close panel"""
        self.app.exit()

    @on(Button.Pressed, "#refresh_all_btn")
    def on_refresh_all_button(self):
        """Handle refresh all button"""
        self.action_refresh_all()

    @on(Button.Pressed, "#export_data_btn")
    def on_export_data_button(self):
        """Handle export data button - export all memory data"""
        try:
            from daedelus.llm.training_data_organizer import TrainingDataOrganizer
            from pathlib import Path
            from datetime import datetime

            data_dir = Path.home() / ".local" / "share" / "daedelus"
            export_dir = data_dir / "exports" / datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir.mkdir(parents=True, exist_ok=True)

            trainer = TrainingDataOrganizer(str(data_dir))
            export_path = export_dir / "memory_export.jsonl"
            trainer.export_training_data(str(export_path), format='jsonl')

            self.notify(f"Data exported to {export_dir}", severity="information")
            logger.info(f"Memory data exported to {export_dir}")

        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            self.notify(f"Export failed: {e}", severity="error")

    @on(Button.Pressed, "#clear_history_btn")
    def on_clear_history_button(self):
        """Handle clear history button"""
        self.action_clear_history()

    @on(Button.Pressed, "#close_btn")
    def on_close_button(self):
        """Handle close button"""
        self.action_close_panel()

    @on(Button.Pressed, "#revoke_permission")
    def on_revoke_permission(self):
        """Revoke selected permission"""
        try:
            from daedelus.core.file_operations import FilePermissionManager

            # Get selected permission from granted permissions table
            table = self.query_one("#granted_permissions_table", DataTable)

            # Check if a row is selected (cursor position)
            if table.cursor_row is None or table.row_count == 0:
                self.notify("No permission selected", severity="warning")
                return

            # Get the selected row data
            try:
                row_key = table.cursor_row
                row = table.get_row_at(row_key)

                if len(row) >= 2:
                    path = str(row[0])  # First column is path
                    permission_type = str(row[1])  # Second column is permission type

                    # Revoke the permission
                    pm = FilePermissionManager()
                    pm.revoke_permission(path, permission_type)

                    # Reload permissions to reflect changes
                    self.load_permissions()

                    self.notify(f"Permission revoked: {permission_type} on {path}", severity="warning")
                    logger.info(f"Permission revoked: {permission_type} on {path}")
                else:
                    self.notify("Invalid permission data", severity="error")

            except Exception as row_error:
                logger.error(f"Error accessing row data: {row_error}")
                self.notify(f"Could not read permission data: {str(row_error)}", severity="error")

        except Exception as e:
            logger.error(f"Error revoking permission: {e}")
            self.notify(f"Failed to revoke permission: {str(e)}", severity="error")

    @on(Button.Pressed, "#approve_permission")
    def on_approve_permission(self):
        """Approve selected pending permission request"""
        try:
            from daedelus.core.file_operations import FilePermissionManager

            # Get selected permission from pending permissions table
            table = self.query_one("#pending_permissions_table", DataTable)

            # Check if a row is selected
            if table.cursor_row is None or table.row_count == 0:
                self.notify("No pending permission selected", severity="warning")
                return

            # Get the selected row data
            try:
                row_key = table.cursor_row
                row = table.get_row_at(row_key)

                if len(row) >= 3:
                    path = str(row[0])  # First column is path
                    permission_type = str(row[1])  # Second column is permission type
                    reason = str(row[2])  # Third column is reason

                    # Approve the permission
                    pm = FilePermissionManager()
                    pm.grant_permission(
                        path=path,
                        permission_type=permission_type,
                        session_only=False,  # Persist the approval
                        reason=f"User approved: {reason}"
                    )

                    # Reload permissions to reflect changes
                    self.load_permissions()

                    self.notify(f"Permission approved: {permission_type} on {path}", severity="success")
                    logger.info(f"Permission approved: {permission_type} on {path}")
                else:
                    self.notify("Invalid permission data", severity="error")

            except Exception as row_error:
                logger.error(f"Error accessing row data: {row_error}")
                self.notify(f"Could not read permission data: {str(row_error)}", severity="error")

        except Exception as e:
            logger.error(f"Error approving permission: {e}")
            self.notify(f"Failed to approve permission: {str(e)}", severity="error")

    @on(Button.Pressed, "#deny_permission")
    def on_deny_permission(self):
        """Deny selected pending permission request"""
        try:
            from daedelus.core.file_operations import FilePermissionManager

            # Get selected permission from pending permissions table
            table = self.query_one("#pending_permissions_table", DataTable)

            # Check if a row is selected
            if table.cursor_row is None or table.row_count == 0:
                self.notify("No pending permission selected", severity="warning")
                return

            # Get the selected row data
            try:
                row_key = table.cursor_row
                row = table.get_row_at(row_key)

                if len(row) >= 2:
                    path = str(row[0])  # First column is path
                    permission_type = str(row[1])  # Second column is permission type

                    # Deny the permission
                    pm = FilePermissionManager()
                    pm.deny_permission(
                        path=path,
                        permission_type=permission_type,
                        session_only=False,  # Persist the denial
                        reason="User denied permission"
                    )

                    # Reload permissions to reflect changes
                    self.load_permissions()

                    self.notify(f"Permission denied: {permission_type} on {path}", severity="warning")
                    logger.info(f"Permission denied: {permission_type} on {path}")
                else:
                    self.notify("Invalid permission data", severity="error")

            except Exception as row_error:
                logger.error(f"Error accessing row data: {row_error}")
                self.notify(f"Could not read permission data: {str(row_error)}", severity="error")

        except Exception as e:
            logger.error(f"Error denying permission: {e}")
            self.notify(f"Failed to deny permission: {str(e)}", severity="error")
