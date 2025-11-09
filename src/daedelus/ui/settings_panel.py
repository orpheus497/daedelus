"""
Settings Management UI Component
=================================
Textual-based UI for managing all Daedelus settings including:
- File operation permissions
- Command execution settings
- Tool permissions
- Training data configuration
- System preferences

Author: orpheus497
License: MIT
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.reactive import reactive
from textual.binding import Binding
from textual import on

from ..utils.config import Config

logger = logging.getLogger(__name__)


class SettingItem(Container):
    """Individual setting item with label and control"""

    def __init__(
        self,
        name: str,
        label: str,
        description: str,
        value: Any,
        setting_type: str = "text",
        options: Optional[List[Any]] = None,
        **kwargs
    ):
        """
        Initialize setting item.

        Args:
            name: Setting name (key)
            label: Display label
            description: Description text
            value: Current value
            setting_type: Type of control (text, bool, select, number)
            options: Options for select type
        """
        super().__init__(**kwargs)
        self.setting_name = name
        self.setting_label = label
        self.setting_description = description
        self.setting_value = value
        self.setting_type = setting_type
        self.setting_options = options or []

    def compose(self) -> ComposeResult:
        """Compose setting item UI"""
        with Vertical(classes="setting-item"):
            yield Label(self.setting_label, classes="setting-label")
            yield Static(self.setting_description, classes="setting-description")

            if self.setting_type == "bool":
                yield Switch(value=bool(self.setting_value), id=f"setting_{self.setting_name}")

            elif self.setting_type == "select":
                yield Select(
                    options=[(str(opt), opt) for opt in self.setting_options],
                    value=self.setting_value,
                    id=f"setting_{self.setting_name}"
                )

            elif self.setting_type == "number":
                yield Input(
                    value=str(self.setting_value),
                    placeholder="Enter number",
                    type="integer" if isinstance(self.setting_value, int) else "number",
                    id=f"setting_{self.setting_name}"
                )

            else:  # text
                yield Input(
                    value=str(self.setting_value),
                    placeholder="Enter value",
                    id=f"setting_{self.setting_name}"
                )


class FilePermissionsTab(ScrollableContainer):
    """Tab for file operation permissions"""

    def __init__(self, config: Config, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose file permissions UI"""
        yield Static("# File Operation Permissions", classes="tab-header")
        yield Static("Configure which file operations require permission prompts", classes="tab-description")

        # Permission settings
        yield SettingItem(
            "file_ops.require_read_permission",
            "Require Read Permission",
            "Prompt before reading files",
            self.config.get("file_operations.require_read_permission", False),
            setting_type="bool"
        )

        yield SettingItem(
            "file_ops.require_write_permission",
            "Require Write Permission",
            "Prompt before writing files",
            self.config.get("file_operations.require_write_permission", True),
            setting_type="bool"
        )

        yield SettingItem(
            "file_ops.require_delete_permission",
            "Require Delete Permission",
            "Prompt before deleting files",
            self.config.get("file_operations.require_delete_permission", True),
            setting_type="bool"
        )

        # Excluded paths
        yield Static("\n## Excluded Paths", classes="section-header")
        yield Static("Files and directories that should never be accessed:", classes="section-description")

        yield DataTable(id="excluded_paths_table")

        with Horizontal(classes="button-row"):
            yield Button("Add Path", id="add_excluded_path", variant="primary")
            yield Button("Remove Selected", id="remove_excluded_path", variant="error")

        # Max file size
        yield Static("\n## Size Limits", classes="section-header")

        yield SettingItem(
            "file_ops.max_file_size",
            "Maximum File Size (MB)",
            "Maximum size of files that can be read",
            self.config.get("file_operations.max_file_size_mb", 10),
            setting_type="number"
        )


class CommandExecutionTab(ScrollableContainer):
    """Tab for command execution settings"""

    def __init__(self, config: Config, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose command execution UI"""
        yield Static("# Command Execution Settings", classes="tab-header")
        yield Static("Configure command execution behavior and safety", classes="tab-description")

        # Safety settings
        yield SettingItem(
            "cmd_exec.enable_safety_analysis",
            "Enable Safety Analysis",
            "Analyze commands for dangerous patterns before execution",
            self.config.get("command_execution.enable_safety_analysis", True),
            setting_type="bool"
        )

        yield SettingItem(
            "cmd_exec.block_dangerous_commands",
            "Block Dangerous Commands",
            "Automatically block commands flagged as dangerous",
            self.config.get("command_execution.block_dangerous_commands", True),
            setting_type="bool"
        )

        yield SettingItem(
            "cmd_exec.prompt_for_warnings",
            "Prompt for Warning Commands",
            "Prompt user confirmation for commands with warnings",
            self.config.get("command_execution.prompt_for_warnings", True),
            setting_type="bool"
        )

        # Execution settings
        yield Static("\n## Execution Behavior", classes="section-header")

        yield SettingItem(
            "cmd_exec.default_timeout",
            "Default Timeout (seconds)",
            "Maximum execution time for commands",
            self.config.get("command_execution.default_timeout", 300),
            setting_type="number"
        )

        yield SettingItem(
            "cmd_exec.capture_output",
            "Capture Output",
            "Capture stdout/stderr from executed commands",
            self.config.get("command_execution.capture_output", True),
            setting_type="bool"
        )

        yield SettingItem(
            "cmd_exec.log_all_executions",
            "Log All Executions",
            "Log all command executions to database",
            self.config.get("command_execution.log_all_executions", True),
            setting_type="bool"
        )


class ToolPermissionsTab(ScrollableContainer):
    """Tab for tool/plugin permissions"""

    def __init__(self, config: Config, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose tool permissions UI"""
        yield Static("# Tool & Plugin Permissions", classes="tab-header")
        yield Static("Configure permissions for tools and plugins", classes="tab-description")

        # Tool settings
        yield SettingItem(
            "tools.require_permission_approval",
            "Require Permission Approval",
            "Prompt for approval before executing tools with permissions",
            self.config.get("tools.require_permission_approval", True),
            setting_type="bool"
        )

        yield SettingItem(
            "tools.enable_sandboxing",
            "Enable Sandboxing",
            "Execute tools in sandboxed environment when possible",
            self.config.get("tools.enable_sandboxing", False),
            setting_type="bool"
        )

        yield SettingItem(
            "tools.auto_discover",
            "Auto-Discover Tools",
            "Automatically discover and load tools from plugins directory",
            self.config.get("tools.auto_discover", True),
            setting_type="bool"
        )

        # Tool permissions table
        yield Static("\n## Installed Tools", classes="section-header")
        yield Static("Manage installed tools and their permissions:", classes="section-description")

        yield DataTable(id="tools_table")

        with Horizontal(classes="button-row"):
            yield Button("Refresh Tools", id="refresh_tools", variant="primary")
            yield Button("Enable/Disable", id="toggle_tool", variant="default")


class TrainingDataTab(ScrollableContainer):
    """Tab for training data configuration"""

    def __init__(self, config: Config, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose training data UI"""
        yield Static("# Training Data Configuration", classes="tab-header")
        yield Static("Configure how data is collected and organized for model training", classes="tab-description")

        # Data collection settings
        yield SettingItem(
            "training.collect_command_history",
            "Collect Command History",
            "Include command history in training data",
            self.config.get("training.collect_command_history", True),
            setting_type="bool"
        )

        yield SettingItem(
            "training.collect_file_operations",
            "Collect File Operations",
            "Include file operations in training data",
            self.config.get("training.collect_file_operations", True),
            setting_type="bool"
        )

        yield SettingItem(
            "training.collect_tool_executions",
            "Collect Tool Executions",
            "Include tool executions in training data",
            self.config.get("training.collect_tool_executions", True),
            setting_type="bool"
        )

        yield SettingItem(
            "training.collect_documents",
            "Collect Ingested Documents",
            "Include ingested documents in training data",
            self.config.get("training.collect_documents", True),
            setting_type="bool"
        )

        # Training triggers
        yield Static("\n## Training Triggers", classes="section-header")

        yield SettingItem(
            "training.auto_train",
            "Automatic Training",
            "Automatically trigger training when threshold is reached",
            self.config.get("training.auto_train", True),
            setting_type="bool"
        )

        yield SettingItem(
            "training.command_threshold",
            "Command Threshold",
            "Number of new commands before triggering training",
            self.config.get("training.command_threshold", 500),
            setting_type="number"
        )

        # Data quality
        yield Static("\n## Data Quality", classes="section-header")

        yield SettingItem(
            "training.min_quality",
            "Minimum Quality Level",
            "Minimum quality level for training data",
            self.config.get("training.min_quality", "medium"),
            setting_type="select",
            options=["high", "medium", "low"]
        )

        yield SettingItem(
            "training.exclude_sensitive",
            "Exclude Sensitive Data",
            "Automatically exclude sensitive data from training",
            self.config.get("training.exclude_sensitive", True),
            setting_type="bool"
        )


class SystemPreferencesTab(ScrollableContainer):
    """Tab for system preferences"""

    def __init__(self, config: Config, **kwargs):
        """Initialize tab"""
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose system preferences UI"""
        yield Static("# System Preferences", classes="tab-header")
        yield Static("General system configuration and preferences", classes="tab-description")

        # General settings
        yield SettingItem(
            "system.log_level",
            "Log Level",
            "Logging verbosity level",
            self.config.get("system.log_level", "INFO"),
            setting_type="select",
            options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )

        yield SettingItem(
            "system.enable_telemetry",
            "Enable Telemetry",
            "Send anonymous usage statistics (100% local, no external calls)",
            self.config.get("system.enable_telemetry", False),
            setting_type="bool"
        )

        # Performance settings
        yield Static("\n## Performance", classes="section-header")

        yield SettingItem(
            "system.cache_size",
            "Cache Size",
            "Number of items to keep in cache",
            self.config.get("performance.cache_size", 1000),
            setting_type="number"
        )

        yield SettingItem(
            "system.lazy_loading",
            "Lazy Loading",
            "Load models and resources on-demand to save memory",
            self.config.get("performance.lazy_loading", True),
            setting_type="bool"
        )

        # Backup settings
        yield Static("\n## Backup & Retention", classes="section-header")

        yield SettingItem(
            "system.auto_backup",
            "Automatic Backups",
            "Automatically backup databases daily",
            self.config.get("backup.enabled", True),
            setting_type="bool"
        )

        yield SettingItem(
            "system.backup_retention_days",
            "Backup Retention (days)",
            "Number of days to keep backups",
            self.config.get("backup.retention_days", 7),
            setting_type="number"
        )

        yield SettingItem(
            "system.history_retention_days",
            "History Retention (days)",
            "Number of days to keep command history",
            self.config.get("privacy.history_retention_days", 90),
            setting_type="number"
        )


class SettingsPanel(Container):
    """
    Main settings panel with tabbed interface.
    """

    BINDINGS = [
        Binding("ctrl+s", "save_settings", "Save Settings"),
        Binding("ctrl+r", "reload_settings", "Reload Settings"),
        Binding("escape", "close_panel", "Close"),
    ]

    settings_modified = reactive(False)

    def __init__(self, config: Config, **kwargs):
        """
        Initialize settings panel.

        Args:
            config: Configuration instance
        """
        super().__init__(**kwargs)
        self.config = config
        self.original_config = config.config.copy()

    def compose(self) -> ComposeResult:
        """Compose settings panel UI"""
        yield Header()

        yield Static("⚙️  Daedelus Settings", classes="panel-title")

        with TabbedContent(initial="file_permissions"):
            with TabPane("File Permissions", id="file_permissions"):
                yield FilePermissionsTab(self.config)

            with TabPane("Command Execution", id="command_execution"):
                yield CommandExecutionTab(self.config)

            with TabPane("Tool Permissions", id="tool_permissions"):
                yield ToolPermissionsTab(self.config)

            with TabPane("Training Data", id="training_data"):
                yield TrainingDataTab(self.config)

            with TabPane("System", id="system_preferences"):
                yield SystemPreferencesTab(self.config)

        # Status bar
        with Horizontal(classes="status-bar"):
            yield Label(id="status_label")
            with Horizontal(classes="button-group"):
                yield Button("Save", id="save_button", variant="success")
                yield Button("Reset", id="reset_button", variant="warning")
                yield Button("Close", id="close_button", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event"""
        self.update_status("Settings loaded")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch toggle"""
        self.settings_modified = True
        self.update_status("Settings modified (not saved)")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change"""
        self.settings_modified = True
        self.update_status("Settings modified (not saved)")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select change"""
        self.settings_modified = True
        self.update_status("Settings modified (not saved)")

    @on(Button.Pressed, "#save_button")
    def action_save_settings(self) -> None:
        """Save settings"""
        try:
            # Collect all setting values
            settings_to_save = {}

            # Iterate through all setting items
            for item in self.query(SettingItem):
                setting_id = f"setting_{item.setting_name}"
                widget = self.query_one(f"#{setting_id}", expect_type=None)

                if isinstance(widget, Switch):
                    value = widget.value
                elif isinstance(widget, Select):
                    value = widget.value
                elif isinstance(widget, Input):
                    value = widget.value
                else:
                    continue

                # Parse setting name and update config
                parts = item.setting_name.split('.')
                if len(parts) == 2:
                    section, key = parts
                    if section not in settings_to_save:
                        settings_to_save[section] = {}
                    settings_to_save[section][key] = value

            # Update config
            for section, values in settings_to_save.items():
                for key, value in values.items():
                    self.config.set(f"{section}.{key}", value)

            # Save to file
            self.config.save()

            self.settings_modified = False
            self.update_status("Settings saved successfully", success=True)

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            self.update_status(f"Error saving settings: {e}", error=True)

    @on(Button.Pressed, "#reset_button")
    def action_reload_settings(self) -> None:
        """Reload settings from file"""
        try:
            # Reload config by re-instantiating from the same path
            self.config = Config(self.config.config_path, self.config.data_dir)
            self.settings_modified = False
            self.update_status("Settings reloaded from file", success=True)

            # Refresh UI
            self.refresh()

        except Exception as e:
            logger.error(f"Failed to reload settings: {e}")
            self.update_status(f"Error reloading settings: {e}", error=True)

    @on(Button.Pressed, "#close_button")
    def action_close_panel(self) -> None:
        """Close settings panel"""
        if self.settings_modified:
            # TODO: Show confirmation dialog
            pass

        self.app.exit()

    def update_status(self, message: str, success: bool = False, error: bool = False) -> None:
        """
        Update status message.

        Args:
            message: Status message
            success: If True, show as success
            error: If True, show as error
        """
        status_label = self.query_one("#status_label", Label)

        if success:
            status_label.update(f"✓ {message}")
            status_label.add_class("status-success")
        elif error:
            status_label.update(f"✗ {message}")
            status_label.add_class("status-error")
        else:
            status_label.update(message)
            status_label.remove_class("status-success")
            status_label.remove_class("status-error")
