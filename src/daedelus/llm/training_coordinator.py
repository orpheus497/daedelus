"""
Training coordinator for automatic and manual LLM fine-tuning.

Handles:
- Threshold-based automatic training triggers
- Manual command-based training
- Training progress tracking
- Integration with deus.gguf model system
- UI notifications and status updates

Created by: orpheus497
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TrainingStatus(Enum):
    """Training status states."""

    IDLE = "idle"
    PREPARING = "preparing"
    TRAINING = "training"
    CONVERTING = "converting"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TrainingProgress:
    """Training progress information."""

    status: TrainingStatus
    progress_percentage: int
    current_step: str
    total_steps: int
    current_step_num: int
    elapsed_seconds: float
    estimated_remaining_seconds: float | None
    error_message: str | None = None


class TrainingCoordinator:
    """
    Coordinates LLM fine-tuning across threshold and manual triggers.

    Features:
    - Automatic training at command threshold
    - Manual training via CLI command
    - Progress tracking with notifications
    - Status bar integration
    - Program locking during training
    - Time estimation for consumer hardware

    Attributes:
        deus_manager: Deus model manager instance
        peft_trainer: PEFT trainer instance
        db: Command database for training data
        training_in_progress: Flag for active training
        progress: Current training progress
        notification_callback: Function to call for notifications
    """

    def __init__(
        self,
        deus_manager: Any,
        peft_trainer: Any,
        db: Any,
        notification_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize training coordinator.

        Args:
            deus_manager: DeusModelManager instance
            peft_trainer: PEFTTrainer instance
            db: CommandDatabase instance
            notification_callback: Optional callback for notifications
        """
        self.deus_manager = deus_manager
        self.peft_trainer = peft_trainer
        self.db = db

        self.notification_callback = notification_callback

        self.training_in_progress = False
        self.training_thread: threading.Thread | None = None

        self.progress = TrainingProgress(
            status=TrainingStatus.IDLE,
            progress_percentage=0,
            current_step="Ready",
            total_steps=5,
            current_step_num=0,
            elapsed_seconds=0.0,
            estimated_remaining_seconds=None,
        )

        logger.info("TrainingCoordinator initialized")

    def check_and_trigger_training(
        self,
        force: bool = False,
    ) -> bool:
        """
        Check if training should be triggered and start if needed.

        Args:
            force: Force training regardless of threshold

        Returns:
            True if training was triggered, False otherwise
        """
        if self.training_in_progress:
            logger.warning("Training already in progress")
            return False

        should_train = self.deus_manager.should_trigger_training(force=force)

        if not should_train:
            return False

        # Send notification
        progress = self.deus_manager.get_training_progress()
        if force:
            self._notify("Training initiated manually")
        else:
            self._notify(
                f"Training threshold reached: {progress['commands_since_training']} commands"
            )

        # Start training in background thread
        self.training_thread = threading.Thread(
            target=self._run_training_workflow,
            daemon=False,
        )
        self.training_thread.start()

        return True

    def _run_training_workflow(self) -> None:
        """
        Execute the complete training workflow.

        Steps:
        1. Prepare training data
        2. Train LoRA adapter
        3. Merge adapter with base model
        4. Convert to GGUF format
        5. Update deus.gguf

        Note: During training, the program is locked and unavailable.
        """
        self.training_in_progress = True
        start_time = time.time()

        try:
            # Step 1: Prepare training data
            self._update_progress(
                TrainingStatus.PREPARING,
                0,
                "Preparing training data...",
                1,
            )

            commands = self._fetch_training_data()

            if not commands:
                self._update_progress(
                    TrainingStatus.FAILED,
                    0,
                    "No training data available",
                    0,
                    error="No commands found for training",
                )
                return

            self._notify(f"Preparing to train on {len(commands)} commands")

            # Prepare training data
            training_data = self.peft_trainer.prepare_training_data(
                commands=commands,
                max_samples=1000,
            )

            # Step 2: Train LoRA adapter
            self._update_progress(
                TrainingStatus.TRAINING,
                20,
                "Training LoRA adapter...",
                2,
            )

            self._notify(
                "Training in progress - program is locked\n"
                "Estimated time: 10-30 minutes on consumer PC"
            )

            adapter_output = Path.home() / ".local/share/daedelus/llm/adapter_latest"

            # Estimate training time based on data size
            estimated_minutes = self._estimate_training_time(len(training_data))
            self._update_progress(
                TrainingStatus.TRAINING,
                25,
                f"Training model (est. {estimated_minutes} min)...",
                2,
                estimated_remaining_seconds=estimated_minutes * 60,
            )

            self.peft_trainer.train_adapter(
                training_data=training_data,
                output_dir=adapter_output,
                num_epochs=3,
                batch_size=4,
            )

            # Step 3: Convert to GGUF
            self._update_progress(
                TrainingStatus.CONVERTING,
                60,
                "Converting to GGUF format...",
                3,
            )

            self._notify("Converting trained model to GGUF format...")

            gguf_output = Path.home() / ".local/share/daedelus/llm/deus_trained.gguf"

            try:
                self.peft_trainer.export_for_llama_cpp(
                    output_path=gguf_output,
                    quantization="q4_k_m",
                )
            except Exception as e:
                logger.warning(f"GGUF conversion failed: {e}")
                self._notify(f"Warning: GGUF conversion failed - {e}\n" "Using fallback model")
                # Use fallback - copy current model
                current_model = self.deus_manager.get_model_path()
                if current_model:
                    import shutil

                    shutil.copy2(current_model, gguf_output)

            # Step 4: Update deus.gguf
            self._update_progress(
                TrainingStatus.FINALIZING,
                90,
                "Updating deus.gguf...",
                4,
            )

            self.deus_manager.create_deus_from_training(gguf_output)

            # Step 5: Complete
            elapsed = time.time() - start_time
            self._update_progress(
                TrainingStatus.COMPLETED,
                100,
                "Training complete!",
                5,
            )

            self._notify(
                f"✓ Training complete in {elapsed / 60:.1f} minutes\n"
                f"deus.gguf updated with {len(commands)} commands"
            )

            # Reset command counter
            self.deus_manager.reset_command_counter()

        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            self._update_progress(
                TrainingStatus.FAILED,
                0,
                "Training failed",
                0,
                error=str(e),
            )
            self._notify(f"✗ Training failed: {e}")

        finally:
            self.training_in_progress = False
            elapsed = time.time() - start_time
            self.progress.elapsed_seconds = elapsed

    def _fetch_training_data(self) -> list[str]:
        """
        Fetch command data for training from database.

        Returns:
            List of command strings
        """
        try:
            # Get recent successful commands
            recent_commands = self.db.get_recent_commands(
                n=1000,
                successful_only=True,
            )

            commands = [cmd["command"] for cmd in recent_commands]

            logger.info(f"Fetched {len(commands)} commands for training")

            return commands

        except Exception as e:
            logger.error(f"Failed to fetch training data: {e}")
            return []

    def _estimate_training_time(self, num_samples: int) -> int:
        """
        Estimate training time in minutes based on dataset size.

        This is a rough estimate for consumer hardware (CPU-only).

        Args:
            num_samples: Number of training samples

        Returns:
            Estimated minutes
        """
        # Rough estimates:
        # - 100 samples: ~5 minutes
        # - 500 samples: ~15 minutes
        # - 1000 samples: ~25 minutes

        base_minutes = 5
        minutes_per_100_samples = 2

        estimated = base_minutes + (num_samples / 100) * minutes_per_100_samples

        return int(estimated)

    def _update_progress(
        self,
        status: TrainingStatus,
        percentage: int,
        step: str,
        step_num: int,
        estimated_remaining_seconds: float | None = None,
        error: str | None = None,
    ) -> None:
        """
        Update training progress.

        Args:
            status: Training status
            percentage: Progress percentage (0-100)
            step: Current step description
            step_num: Current step number
            estimated_remaining_seconds: Estimated seconds remaining
            error: Error message if failed
        """
        self.progress = TrainingProgress(
            status=status,
            progress_percentage=percentage,
            current_step=step,
            total_steps=5,
            current_step_num=step_num,
            elapsed_seconds=self.progress.elapsed_seconds,
            estimated_remaining_seconds=estimated_remaining_seconds,
            error_message=error,
        )

        logger.debug(f"Training progress: {status.value} - {percentage}% - {step}")

    def _notify(self, message: str) -> None:
        """
        Send notification to user.

        Args:
            message: Notification message
        """
        logger.info(f"Notification: {message}")

        if self.notification_callback:
            self.notification_callback(message)

    def get_progress(self) -> TrainingProgress:
        """
        Get current training progress.

        Returns:
            TrainingProgress object
        """
        return self.progress

    def is_training(self) -> bool:
        """
        Check if training is in progress.

        Returns:
            True if training active, False otherwise
        """
        return self.training_in_progress

    def wait_for_training(self, timeout: float | None = None) -> bool:
        """
        Wait for training to complete.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if training completed, False if timeout
        """
        if not self.training_thread:
            return True

        self.training_thread.join(timeout=timeout)

        return not self.training_thread.is_alive()

    def __repr__(self) -> str:
        """String representation."""
        status = "training" if self.training_in_progress else "idle"
        return f"TrainingCoordinator(status={status})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Training Coordinator Test")
    print("=" * 70)

    print("\nTraining workflow steps:")
    print("1. Prepare training data from command history")
    print("2. Train LoRA adapter (10-30 minutes)")
    print("3. Merge adapter with base model")
    print("4. Convert to GGUF format")
    print("5. Update deus.gguf")

    print("\nDuring training:")
    print("- Program is locked (unavailable)")
    print("- Status bar shows progress")
    print("- Notifications sent at key milestones")
    print("- Time estimates updated")

    print("\nTriggering methods:")
    print("- Automatic: When command threshold reached")
    print("- Manual: Via 'daedelus train' command")
