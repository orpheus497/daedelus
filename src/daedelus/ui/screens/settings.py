"""
Settings screen for the Daedelus dashboard.
"""

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Static

logger = logging.getLogger(__name__)


class SettingsScreen(Static):
    """A widget to display and edit settings."""

    def __init__(self, ipc_client=None, **kwargs):
        super().__init__(**kwargs)
        self.ipc_client = ipc_client
        self.settings_table = DataTable()
        self.edit_input = Input(placeholder="Enter new value...")
        self.save_button = Button("Save", variant="success")
        self.cancel_button = Button("Cancel", variant="default")
        self.status_label = Label("")
        self.selected_setting = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the settings screen."""
        yield Static("[bold]Settings[/bold]", classes="header")
        yield Static("Click a setting to edit • Changes apply immediately")
        yield self.settings_table
        with Vertical(id="edit-panel", classes="hidden"):
            yield Static("Edit Setting:", classes="edit-label")
            yield self.edit_input
            with Horizontal():
                yield self.save_button
                yield self.cancel_button
            yield self.status_label

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.settings_table.add_columns("Setting", "Value")
        self.settings_table.cursor_type = "row"
        self.update_settings()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection to edit setting."""
        row_index = event.cursor_row
        setting_key = self.settings_table.get_cell_at((row_index, 0))
        current_value = self.settings_table.get_cell_at((row_index, 1))

        self.selected_setting = setting_key
        self.edit_input.value = str(current_value)

        # Show edit panel
        edit_panel = self.query_one("#edit-panel")
        edit_panel.remove_class("hidden")
        self.edit_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button == self.save_button:
            self._save_setting()
        elif event.button == self.cancel_button:
            self._cancel_edit()

    def _save_setting(self) -> None:
        """Save the edited setting value."""
        if not self.selected_setting:
            return

        new_value = self.edit_input.value

        try:
            if self.ipc_client and self.ipc_client.is_connected():
                success = self.ipc_client.set_config_value(self.selected_setting, new_value)
                if success:
                    self.status_label.update("[green]✓ Setting saved![/green]")
                    self.update_settings()
                else:
                    self.status_label.update("[red]✗ Failed to save setting[/red]")
            else:
                self.status_label.update(
                    "[yellow]⚠ Daemon not connected - changes not saved[/yellow]"
                )

        except Exception as e:
            logger.error(f"Failed to save setting: {e}")
            self.status_label.update(f"[red]✗ Error: {e}[/red]")

        # Hide edit panel after a delay
        self.set_timer(2.0, self._cancel_edit)

    def _cancel_edit(self) -> None:
        """Cancel editing and hide the edit panel."""
        edit_panel = self.query_one("#edit-panel")
        edit_panel.add_class("hidden")
        self.selected_setting = None
        self.status_label.update("")

    def update_settings(self) -> None:
        """Update settings display."""
        if self.ipc_client:
            # Read settings from config
            settings = {
                "suggestions.max_suggestions": self.ipc_client.get_config_value(
                    "suggestions.max_suggestions"
                ),
                "suggestions.min_confidence": self.ipc_client.get_config_value(
                    "suggestions.min_confidence"
                ),
                "privacy.history_retention_days": self.ipc_client.get_config_value(
                    "privacy.history_retention_days"
                ),
                "llm.enabled": self.ipc_client.get_config_value("llm.enabled"),
                "llm.model_path": self.ipc_client.get_config_value("llm.model_path"),
            }
        else:
            settings = self._get_mock_settings()

        self.settings_table.clear()
        for key, value in settings.items():
            if value is None:
                value = "N/A"
            self.settings_table.add_row(key, str(value))

    def _get_mock_settings(self):
        """Return mock settings when daemon is not available."""
        return {
            "suggestions.max_suggestions": 5,
            "suggestions.min_confidence": 0.3,
            "privacy.history_retention_days": 90,
            "llm.enabled": True,
            "llm.model_path": "~/.local/share/models/tinyllama.gguf",
        }
