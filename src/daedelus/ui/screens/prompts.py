"""
Natural Language Prompts Screen for Dashboard.

Displays NLP prompts, their interpretations, generated commands,
user feedback, and accuracy metrics for training data collection.

Created by: orpheus497
"""

import logging
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static

from daedelus.ui.ipc_client import DashboardIPCClient

logger = logging.getLogger(__name__)


class PromptsScreen(Container):
    """
    Screen for viewing natural language prompts and their results.
    
    Displays:
    - All natural language prompts submitted
    - Interpretations and generated commands
    - User feedback (accepted/rejected)
    - Accuracy metrics
    - Training data export status
    """

    def __init__(self, ipc_client: DashboardIPCClient, **kwargs):
        """
        Initialize prompts screen.

        Args:
            ipc_client: IPC client for daemon communication
        """
        super().__init__(**kwargs)
        self.ipc_client = ipc_client

    def compose(self) -> ComposeResult:
        """Compose prompts screen widgets."""
        yield Label("Natural Language Prompts & Training Data", classes="section-title")
        
        # Metrics summary
        with Horizontal(classes="metrics-row"):
            yield Static("Total Prompts: 0", id="total-prompts")
            yield Static("Accepted: 0", id="accepted-prompts")
            yield Static("Rejected: 0", id="rejected-prompts")
            yield Static("Accuracy: 0%", id="prompt-accuracy")
        
        # Prompts table
        yield Label("Recent Prompts", classes="subsection-title")
        table = DataTable(id="prompts-table")
        table.add_columns(
            "Timestamp",
            "Prompt",
            "Intent",
            "Commands",
            "Feedback",
            "Confidence",
        )
        yield table
        
        # Actions
        with Horizontal(classes="button-row"):
            yield Button("Refresh", id="refresh-prompts", variant="primary")
            yield Button("Export Training Data", id="export-training", variant="success")
            yield Button("Clear History", id="clear-prompts", variant="error")

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.load_prompts()

    def load_prompts(self) -> None:
        """Load prompts from daemon."""
        try:
            # Request prompt history from daemon
            response = self.ipc_client.send_request("get_prompt_history", {"limit": 100})
            
            if response.get("status") == "ok":
                prompts = response.get("prompts", [])
                self._update_table(prompts)
                self._update_metrics(prompts)
            else:
                # Daemon might not have this feature yet, show mock data
                self._show_mock_data()
                
        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")
            self._show_mock_data()

    def _update_table(self, prompts: list[dict]) -> None:
        """Update the prompts table."""
        table = self.query_one("#prompts-table", DataTable)
        table.clear()
        
        for prompt in prompts:
            timestamp = prompt.get("timestamp", 0)
            timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            
            prompt_text = prompt.get("text", "")[:50]  # Truncate long prompts
            intent = prompt.get("intent", "unknown")
            commands = prompt.get("commands", [])
            commands_str = str(len(commands)) + " cmd(s)" if commands else "None"
            feedback = prompt.get("feedback", "pending")
            confidence = f"{prompt.get('confidence', 0.0):.2f}"
            
            # Color code feedback
            if feedback == "accepted":
                feedback_display = "[green]✓ Accepted[/green]"
            elif feedback == "rejected":
                feedback_display = "[red]✗ Rejected[/red]"
            else:
                feedback_display = "[yellow]⊙ Pending[/yellow]"
            
            table.add_row(
                timestamp_str,
                prompt_text,
                intent,
                commands_str,
                feedback_display,
                confidence,
            )

    def _update_metrics(self, prompts: list[dict]) -> None:
        """Update metrics displays."""
        total = len(prompts)
        accepted = sum(1 for p in prompts if p.get("feedback") == "accepted")
        rejected = sum(1 for p in prompts if p.get("feedback") == "rejected")
        accuracy = (accepted / total * 100) if total > 0 else 0.0
        
        self.query_one("#total-prompts", Static).update(f"Total Prompts: {total}")
        self.query_one("#accepted-prompts", Static).update(f"Accepted: {accepted}")
        self.query_one("#rejected-prompts", Static).update(f"Rejected: {rejected}")
        self.query_one("#prompt-accuracy", Static).update(f"Accuracy: {accuracy:.1f}%")

    def _show_mock_data(self) -> None:
        """Show mock data when daemon feature not available."""
        mock_prompts = [
            {
                "timestamp": datetime.now().timestamp() - 3600,
                "text": "update my system packages",
                "intent": "system_update",
                "commands": ["sudo dnf update -y"],
                "feedback": "accepted",
                "confidence": 0.95,
            },
            {
                "timestamp": datetime.now().timestamp() - 1800,
                "text": "find all python files",
                "intent": "action_search",
                "commands": ["find . -name '*.py'", "ls **/*.py"],
                "feedback": "accepted",
                "confidence": 0.88,
            },
            {
                "timestamp": datetime.now().timestamp() - 900,
                "text": "show me disk usage",
                "intent": "status_check",
                "commands": ["df -h", "du -sh *"],
                "feedback": "pending",
                "confidence": 0.75,
            },
            {
                "timestamp": datetime.now().timestamp() - 300,
                "text": "create a backup script",
                "intent": "write_script",
                "commands": ["bash /tmp/backup_script_123.sh"],
                "feedback": "accepted",
                "confidence": 0.82,
            },
        ]
        
        self._update_table(mock_prompts)
        self._update_metrics(mock_prompts)
        
        # Show info message
        info_label = self.query_one(".section-title", Label)
        info_label.update("Natural Language Prompts & Training Data [dim](Mock Data - Daemon feature pending)[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh-prompts":
            self.load_prompts()
        elif event.button.id == "export-training":
            self._export_training_data()
        elif event.button.id == "clear-prompts":
            self._clear_prompts()

    def _export_training_data(self) -> None:
        """Export training data to file."""
        try:
            response = self.ipc_client.send_request("export_prompt_training_data", {})
            
            if response.get("status") == "ok":
                export_path = response.get("export_path")
                self.app.notify(f"Training data exported to: {export_path}", severity="information")
            else:
                self.app.notify("Training data export not yet implemented", severity="warning")
                
        except Exception as e:
            logger.error(f"Failed to export training data: {e}")
            self.app.notify(f"Export failed: {e}", severity="error")

    def _clear_prompts(self) -> None:
        """Clear prompt history."""
        try:
            response = self.ipc_client.send_request("clear_prompt_history", {})
            
            if response.get("status") == "ok":
                self.load_prompts()
                self.app.notify("Prompt history cleared", severity="information")
            else:
                self.app.notify("Clear prompts not yet implemented", severity="warning")
                
        except Exception as e:
            logger.error(f"Failed to clear prompts: {e}")
            self.app.notify(f"Clear failed: {e}", severity="error")
