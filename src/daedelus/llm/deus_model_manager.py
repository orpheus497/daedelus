"""
Deus LLM model manager with auto-detection and prioritization.

Manages the deus.gguf model lifecycle:
- Auto-detects deus.gguf in models directory
- Prioritizes deus.gguf over other models
- Falls back to available models if deus.gguf not found
- Prompts for model download if no models available
- Tracks growth and triggers fine-tuning at thresholds

The deus.gguf model is the continuously trained and fine-tuned model
that grows with user interactions.

Created by: orpheus497
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None  # type: ignore


class DeusModelManager:
    """
    Manager for deus.gguf model with auto-detection and prioritization.

    Model Priority:
    1. deus.gguf (if exists) - continuously trained personalized model
    2. daedelus_v*.gguf - versioned daedelus models
    3. Other .gguf files in the directory
    4. Prompt for download if none found

    Attributes:
        models_dir: Directory containing model files
        deus_model_path: Path to deus.gguf (if exists)
        fallback_model_path: Path to fallback model
        current_model: Currently loaded model instance
        commands_since_training: Counter for training threshold
    """

    # Model filenames in priority order
    DEUS_MODEL_NAME = "deus.gguf"

    def __init__(
        self,
        models_dir: Path,
        training_threshold: int = 500,
    ) -> None:
        """
        Initialize deus model manager.

        Args:
            models_dir: Directory containing models
            training_threshold: Number of commands before auto fine-tuning
        """
        self.models_dir = Path(models_dir).expanduser()
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.training_threshold = training_threshold
        self.commands_since_training = 0

        # Auto-detect models
        self.deus_model_path = None
        self.fallback_model_path = None
        self.current_model = None

        self._detect_models()

        logger.info(f"DeusModelManager initialized (models_dir={self.models_dir})")

    def _detect_models(self) -> None:
        """
        Detect available models in the models directory.

        Priority:
        1. deus.gguf
        2. daedelus_v*.gguf (highest version)
        3. Any other .gguf file
        """
        # Check for deus.gguf
        deus_path = self.models_dir / self.DEUS_MODEL_NAME
        if deus_path.exists():
            self.deus_model_path = deus_path
            logger.info(f"✓ Found deus.gguf model: {deus_path}")

        # Find all .gguf files
        all_gguf_files = list(self.models_dir.glob("*.gguf"))

        if not all_gguf_files and not self.deus_model_path:
            logger.warning(f"No .gguf models found in {self.models_dir}")
            return

        # Filter out deus.gguf for fallback search
        fallback_candidates = [
            f for f in all_gguf_files if f.name != self.DEUS_MODEL_NAME
        ]

        if not fallback_candidates:
            logger.info("No fallback models found (deus.gguf is the only model)")
            return

        # Prioritize daedelus_v* models
        daedelus_models = [f for f in fallback_candidates if f.name.startswith("daedelus_v")]

        if daedelus_models:
            # Sort by version number (extract from filename)
            def extract_version(path: Path) -> int:
                try:
                    # Extract version from "daedelus_v{N}.gguf"
                    version_str = path.stem.split("_v")[1]
                    return int(version_str)
                except (IndexError, ValueError):
                    return 0

            daedelus_models.sort(key=extract_version, reverse=True)
            self.fallback_model_path = daedelus_models[0]
            logger.info(f"Fallback model: {self.fallback_model_path.name}")
        else:
            # Use any other .gguf file as fallback
            self.fallback_model_path = fallback_candidates[0]
            logger.info(f"Fallback model: {self.fallback_model_path.name}")

    def get_model_path(self) -> Path | None:
        """
        Get the path to the model that should be used.

        Returns:
            Path to deus.gguf if exists, otherwise fallback model,
            or None if no models available
        """
        if self.deus_model_path and self.deus_model_path.exists():
            return self.deus_model_path
        elif self.fallback_model_path and self.fallback_model_path.exists():
            return self.fallback_model_path
        else:
            return None

    def load_model(
        self,
        context_length: int = 2048,
        n_gpu_layers: int = 0,
        verbose: bool = False,
    ) -> Any:
        """
        Load the appropriate model (deus.gguf or fallback).

        Args:
            context_length: Context window size
            n_gpu_layers: Number of layers to offload to GPU
            verbose: Enable verbose logging

        Returns:
            Loaded Llama model instance

        Raises:
            RuntimeError: If no models available or loading fails
        """
        if Llama is None:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus"
            )

        model_path = self.get_model_path()

        if model_path is None:
            raise RuntimeError(
                f"No models found in {self.models_dir}\n\n"
                "To get started:\n"
                "1. Download a model using: daedelus download-model\n"
                "2. Or manually place a .gguf model file in the models directory"
            )

        logger.info(f"Loading model: {model_path.name}")

        try:
            self.current_model = Llama(
                model_path=str(model_path),
                n_ctx=context_length,
                n_gpu_layers=n_gpu_layers,
                verbose=verbose,
            )

            logger.info(f"✓ Model loaded successfully: {model_path.name}")

            return self.current_model

        except Exception as e:
            logger.error(f"Failed to load model {model_path}: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e

    def has_deus_model(self) -> bool:
        """
        Check if deus.gguf model exists.

        Returns:
            True if deus.gguf exists, False otherwise
        """
        return self.deus_model_path is not None and self.deus_model_path.exists()

    def should_trigger_training(self, force: bool = False) -> bool:
        """
        Check if fine-tuning should be triggered.

        Training is triggered when:
        1. commands_since_training >= training_threshold, OR
        2. force=True (manual trigger)

        Args:
            force: Force training regardless of threshold

        Returns:
            True if training should be triggered
        """
        if force:
            return True

        return self.commands_since_training >= self.training_threshold

    def increment_command_counter(self) -> int:
        """
        Increment the commands counter and return current count.

        Returns:
            Current command count
        """
        self.commands_since_training += 1
        return self.commands_since_training

    def reset_command_counter(self) -> None:
        """Reset the commands counter after training."""
        self.commands_since_training = 0
        logger.debug("Command counter reset after training")

    def get_training_progress(self) -> dict[str, Any]:
        """
        Get current training progress information.

        Returns:
            Dictionary with training progress stats
        """
        progress_ratio = min(
            self.commands_since_training / self.training_threshold,
            1.0,
        )

        return {
            "commands_since_training": self.commands_since_training,
            "training_threshold": self.training_threshold,
            "progress_ratio": progress_ratio,
            "progress_percentage": int(progress_ratio * 100),
            "commands_until_training": max(
                0,
                self.training_threshold - self.commands_since_training,
            ),
        }

    def create_deus_from_training(
        self,
        trained_model_path: Path,
    ) -> None:
        """
        Create/update deus.gguf from newly trained model.

        This is called after fine-tuning to update the deus model.

        Args:
            trained_model_path: Path to newly trained/fine-tuned model
        """
        import shutil

        deus_path = self.models_dir / self.DEUS_MODEL_NAME

        logger.info(f"Creating deus.gguf from {trained_model_path}")

        # Backup existing deus.gguf if it exists
        if deus_path.exists():
            backup_path = self.models_dir / f"deus_backup_{int(__import__('time').time())}.gguf"
            logger.info(f"Backing up existing deus.gguf to {backup_path}")
            shutil.copy2(deus_path, backup_path)

        # Copy trained model to deus.gguf
        shutil.copy2(trained_model_path, deus_path)

        # Update detection
        self.deus_model_path = deus_path

        logger.info(f"✓ deus.gguf created/updated: {deus_path}")
        logger.info(f"  Size: {deus_path.stat().st_size / (1024**3):.2f} GB")

    def list_available_models(self) -> dict[str, Any]:
        """
        List all available models with metadata.

        Returns:
            Dictionary with model information
        """
        models = {
            "deus": None,
            "fallback": None,
            "all_models": [],
        }

        # Check deus.gguf
        if self.has_deus_model():
            models["deus"] = {
                "path": str(self.deus_model_path),
                "name": self.deus_model_path.name,
                "size_mb": self.deus_model_path.stat().st_size / (1024**2),
                "is_active": True,
            }

        # Check fallback
        if self.fallback_model_path and self.fallback_model_path.exists():
            models["fallback"] = {
                "path": str(self.fallback_model_path),
                "name": self.fallback_model_path.name,
                "size_mb": self.fallback_model_path.stat().st_size / (1024**2),
                "is_active": not self.has_deus_model(),
            }

        # List all .gguf files
        for gguf_file in self.models_dir.glob("*.gguf"):
            models["all_models"].append({
                "path": str(gguf_file),
                "name": gguf_file.name,
                "size_mb": gguf_file.stat().st_size / (1024**2),
                "is_deus": gguf_file.name == self.DEUS_MODEL_NAME,
            })

        return models

    def __repr__(self) -> str:
        """String representation."""
        deus_status = "found" if self.has_deus_model() else "not found"
        return f"DeusModelManager(deus={deus_status}, models_dir={self.models_dir})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Deus Model Manager Test")
    print("=" * 70)

    # Example usage
    from pathlib import Path

    models_dir = Path.home() / ".local/share/models"

    manager = DeusModelManager(models_dir)

    print(f"\nModel detection:")
    print(f"  Deus model: {manager.deus_model_path}")
    print(f"  Fallback model: {manager.fallback_model_path}")

    print(f"\nPriority model: {manager.get_model_path()}")

    print(f"\nTraining progress:")
    progress = manager.get_training_progress()
    print(f"  Commands since training: {progress['commands_since_training']}")
    print(f"  Progress: {progress['progress_percentage']}%")

    print(f"\nAvailable models:")
    models = manager.list_available_models()
    for model in models["all_models"]:
        print(f"  - {model['name']} ({model['size_mb']:.1f} MB)")
