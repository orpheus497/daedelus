"""
Training UI with status bars and notifications.

Provides visual feedback during model fine-tuning:
- Progress bars for training steps
- Real-time status updates
- Time estimates
- Notifications for key milestones
- Program lock indicator

Uses Rich library for terminal UI.

Created by: orpheus497
"""

import logging
import time
from datetime import timedelta
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from daedelus.llm.training_coordinator import TrainingProgress, TrainingStatus

logger = logging.getLogger(__name__)


class TrainingUI:
    """
    Terminal UI for training progress visualization.

    Features:
    - Multi-step progress tracking
    - Time elapsed and remaining
    - Status indicators
    - Program lock warning
    - Rich terminal formatting

    Attributes:
        console: Rich console instance
        progress: Rich Progress instance
        overall_task: Overall progress task ID
        current_task: Current step task ID
        live: Rich Live display
    """

    def __init__(self) -> None:
        """Initialize training UI."""
        self.console = Console()

        # Create progress bar
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

        self.overall_task: TaskID | None = None
        self.current_task: TaskID | None = None
        self.live: Live | None = None

        logger.info("TrainingUI initialized")

    def start_training_ui(
        self,
        total_steps: int = 5,
    ) -> None:
        """
        Start the training UI display.

        Args:
            total_steps: Total number of training steps
        """
        # Create overall progress task
        self.overall_task = self.progress.add_task(
            "[cyan]Overall Training Progress",
            total=100,
        )

        # Show initial message
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold yellow]⚠ Training In Progress ⚠[/bold yellow]\n\n"
                "The program is currently training the deus.gguf model.\n"
                "Please wait for training to complete.\n\n"
                "[dim]Estimated time: 10-30 minutes on consumer PC[/dim]",
                border_style="yellow",
                title="[bold]Training Active[/bold]",
            )
        )
        self.console.print()

    def update_progress(
        self,
        training_progress: TrainingProgress,
    ) -> None:
        """
        Update progress display.

        Args:
            training_progress: Current training progress info
        """
        if self.overall_task is None:
            self.start_training_ui()

        # Update overall progress
        self.progress.update(
            self.overall_task,
            completed=training_progress.progress_percentage,
            description=f"[cyan]{training_progress.current_step}",
        )

        # Show step info
        status_color = self._get_status_color(training_progress.status)

        step_text = (
            f"Step {training_progress.current_step_num}/{training_progress.total_steps}: "
            f"[{status_color}]{training_progress.current_step}[/{status_color}]"
        )

        self.console.print(step_text)

    def show_status_table(
        self,
        training_progress: TrainingProgress,
    ) -> Table:
        """
        Create status table with training information.

        Args:
            training_progress: Current training progress

        Returns:
            Rich Table with status info
        """
        table = Table(title="Training Status", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        # Status
        status_color = self._get_status_color(training_progress.status)
        status_text = Text(training_progress.status.value.upper(), style=status_color)
        table.add_row("Status", status_text)

        # Progress
        table.add_row(
            "Progress",
            f"{training_progress.progress_percentage}%",
        )

        # Current step
        table.add_row(
            "Step",
            f"{training_progress.current_step_num}/{training_progress.total_steps}",
        )

        # Elapsed time
        elapsed_str = str(timedelta(seconds=int(training_progress.elapsed_seconds)))
        table.add_row("Elapsed", elapsed_str)

        # Estimated remaining
        if training_progress.estimated_remaining_seconds:
            remaining_str = str(
                timedelta(seconds=int(training_progress.estimated_remaining_seconds))
            )
            table.add_row("Estimated Remaining", remaining_str)

        # Error if failed
        if training_progress.error_message:
            table.add_row(
                "Error",
                Text(training_progress.error_message, style="bold red"),
            )

        return table

    def show_completion_message(
        self,
        success: bool,
        elapsed_minutes: float,
        commands_trained: int = 0,
    ) -> None:
        """
        Show training completion message.

        Args:
            success: Whether training succeeded
            elapsed_minutes: Total elapsed time in minutes
            commands_trained: Number of commands used for training
        """
        if success:
            self.console.print()
            self.console.print(
                Panel.fit(
                    "[bold green]✓ Training Complete![/bold green]\n\n"
                    f"deus.gguf has been updated with {commands_trained} commands.\n"
                    f"Training completed in {elapsed_minutes:.1f} minutes.\n\n"
                    "[dim]The program is now available for use.[/dim]",
                    border_style="green",
                    title="[bold]Success[/bold]",
                )
            )
        else:
            self.console.print()
            self.console.print(
                Panel.fit(
                    "[bold red]✗ Training Failed[/bold red]\n\n"
                    "An error occurred during training.\n"
                    "Check logs for details.\n\n"
                    "[dim]The program is now available for use.[/dim]",
                    border_style="red",
                    title="[bold]Error[/bold]",
                )
            )

    def show_notification(
        self,
        message: str,
        level: str = "info",
    ) -> None:
        """
        Show notification message.

        Args:
            message: Notification message
            level: Notification level (info, warning, error, success)
        """
        color_map = {
            "info": "blue",
            "warning": "yellow",
            "error": "red",
            "success": "green",
        }

        color = color_map.get(level, "white")

        self.console.print(f"[{color}]ℹ {message}[/{color}]")

    def show_training_threshold_notification(
        self,
        commands_count: int,
        threshold: int,
    ) -> None:
        """
        Show notification when training threshold is reached.

        Args:
            commands_count: Current command count
            threshold: Training threshold
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold yellow]Training Threshold Reached[/bold yellow]\n\n"
                f"Commands since last training: {commands_count}\n"
                f"Threshold: {threshold}\n\n"
                "Fine-tuning will begin shortly...",
                border_style="yellow",
                title="[bold]Auto-Training[/bold]",
            )
        )
        self.console.print()

    def show_progress_towards_threshold(
        self,
        commands_count: int,
        threshold: int,
    ) -> None:
        """
        Show progress bar towards training threshold.

        Args:
            commands_count: Current command count
            threshold: Training threshold
        """
        percentage = min((commands_count / threshold) * 100, 100)

        # Create simple progress display
        bar_width = 40
        filled = int(bar_width * percentage / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        self.console.print()
        self.console.print(f"Training Progress: [{bar}] {percentage:.0f}%")
        self.console.print(f"{commands_count}/{threshold} commands until next training")
        self.console.print()

    def _get_status_color(self, status: TrainingStatus) -> str:
        """
        Get color for training status.

        Args:
            status: Training status

        Returns:
            Color name for Rich
        """
        color_map = {
            TrainingStatus.IDLE: "white",
            TrainingStatus.PREPARING: "cyan",
            TrainingStatus.TRAINING: "yellow",
            TrainingStatus.CONVERTING: "blue",
            TrainingStatus.FINALIZING: "magenta",
            TrainingStatus.COMPLETED: "green",
            TrainingStatus.FAILED: "red",
        }

        return color_map.get(status, "white")

    def __repr__(self) -> str:
        """String representation."""
        return "TrainingUI(console=Rich)"


class TrainingMonitor:
    """
    Monitor training progress and update UI.

    This runs in a separate thread to poll training progress
    and update the UI in real-time.
    """

    def __init__(
        self,
        training_coordinator: Any,
        ui: TrainingUI,
        update_interval: float = 1.0,
    ) -> None:
        """
        Initialize training monitor.

        Args:
            training_coordinator: TrainingCoordinator instance
            ui: TrainingUI instance
            update_interval: Update interval in seconds
        """
        self.coordinator = training_coordinator
        self.ui = ui
        self.update_interval = update_interval

        logger.info("TrainingMonitor initialized")

    def monitor_training(self) -> None:
        """
        Monitor training progress and update UI.

        This should be called in a separate thread.
        """
        self.ui.start_training_ui()

        while self.coordinator.is_training():
            # Get current progress
            progress = self.coordinator.get_progress()

            # Update UI
            self.ui.update_progress(progress)

            # Sleep
            time.sleep(self.update_interval)

        # Training complete - show final status
        final_progress = self.coordinator.get_progress()

        success = final_progress.status == TrainingStatus.COMPLETED

        self.ui.show_completion_message(
            success=success,
            elapsed_minutes=final_progress.elapsed_seconds / 60,
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"TrainingMonitor(interval={self.update_interval}s)"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Training UI Test")
    print("=" * 70)

    ui = TrainingUI()

    # Show threshold notification
    ui.show_training_threshold_notification(500, 500)

    # Show progress bar
    ui.show_progress_towards_threshold(450, 500)

    # Simulate training progress
    ui.start_training_ui(total_steps=5)

    # Show notifications
    ui.show_notification("Preparing training data...", level="info")
    ui.show_notification("Training started", level="warning")
    ui.show_notification("Training complete!", level="success")

    # Show completion
    ui.show_completion_message(success=True, elapsed_minutes=15.3, commands_trained=500)
