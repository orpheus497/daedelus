"""
Self-forging model manager for Daedelus.

Manages the transformation of Phi-3-mini into a personalized Daedelus LLM
through continuous fine-tuning and model merging.

The model evolves from generic Phi-3-mini to a specialized "Daedelus" model
that understands YOUR terminal usage patterns.

Created by: orpheus497
"""

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Import with graceful degradation
try:
    from huggingface_hub import hf_hub_download
    from tqdm import tqdm
    import requests
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    logger.warning("huggingface_hub not available - model download disabled")


@dataclass
class ModelInfo:
    """Information about a model."""

    name: str  # Model name (e.g., "daedelus_v1", "phi-3-mini")
    path: Path  # Path to model file
    size_bytes: int  # File size in bytes
    version: int  # Version number (0 for base Phi-3)
    created: datetime  # Creation timestamp
    checksum: str  # SHA256 checksum
    parent: Optional[str]  # Parent model name (for lineage tracking)
    training_commands: int  # Number of commands used for training
    metadata: Dict[str, str]  # Additional metadata


class ModelManager:
    """
    Manages the Daedelus model lifecycle: download, fine-tune, merge, evolve.

    Architecture:
    1. Bootstrap: Download Phi-3-mini as base model
    2. Initialize: Create daedelus_v1 from base
    3. Evolve: On each shutdown, fine-tune and create daedelus_v{N+1}
    4. Manage: Track lineage, versions, and roll back if needed

    Example Lifecycle:
        phi-3-mini.gguf (base, never modified)
            ↓ [initialize]
        daedelus_v1.gguf (first personalized version)
            ↓ [fine-tune session 1]
        daedelus_v2.gguf (after 100 commands)
            ↓ [fine-tune session 2]
        daedelus_v3.gguf (after 200 commands)
            ...
        daedelus_v47.gguf (fully specialized to YOUR usage)
    """

    # HuggingFace model registry
    MODEL_REGISTRY = {
        "phi-3-mini": {
            "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
            "filename": "Phi-3-mini-4k-instruct-q4.gguf",
            "size_mb": 2400,
            "description": "Microsoft Phi-3-mini 3.8B (Q4 quantized)",
            "checksum": None,  # Will be verified from HF
        },
        "phi-3-mini-fp16": {
            "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
            "filename": "Phi-3-mini-4k-instruct-fp16.gguf",
            "size_mb": 7600,
            "description": "Microsoft Phi-3-mini 3.8B (FP16)",
            "checksum": None,
        },
    }

    def __init__(self, models_dir: Path) -> None:
        """
        Initialize model manager.

        Args:
            models_dir: Directory for storing models
        """
        self.models_dir = Path(models_dir).expanduser()
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Metadata file
        self.metadata_file = self.models_dir / "models.json"
        self.metadata = self._load_metadata()

        logger.info(f"Model manager initialized: {self.models_dir}")

    def _load_metadata(self) -> Dict[str, ModelInfo]:
        """Load model metadata from JSON."""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, "r") as f:
                data = json.load(f)

            metadata = {}
            for name, info in data.items():
                metadata[name] = ModelInfo(
                    name=name,
                    path=Path(info["path"]),
                    size_bytes=info["size_bytes"],
                    version=info["version"],
                    created=datetime.fromisoformat(info["created"]),
                    checksum=info["checksum"],
                    parent=info.get("parent"),
                    training_commands=info.get("training_commands", 0),
                    metadata=info.get("metadata", {}),
                )
            return metadata

        except Exception as e:
            logger.error(f"Failed to load model metadata: {e}")
            return {}

    def _save_metadata(self) -> None:
        """Save model metadata to JSON."""
        data = {}
        for name, info in self.metadata.items():
            data[name] = {
                "path": str(info.path),
                "size_bytes": info.size_bytes,
                "version": info.version,
                "created": info.created.isoformat(),
                "checksum": info.checksum,
                "parent": info.parent,
                "training_commands": info.training_commands,
                "metadata": info.metadata,
            }

        with open(self.metadata_file, "w") as f:
            json.dump(data, f, indent=2)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096 * 1024), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def download_model(
        self,
        model_name: str = "phi-3-mini",
        force: bool = False,
    ) -> Path:
        """
        Download a base model from HuggingFace.

        Args:
            model_name: Model name from registry
            force: Force re-download if already exists

        Returns:
            Path to downloaded model file

        Raises:
            ValueError: If model not in registry
            RuntimeError: If download fails
        """
        if not HF_AVAILABLE:
            raise RuntimeError(
                "huggingface_hub not installed. "
                "Install with: pip install 'daedelus[llm]'"
            )

        if model_name not in self.MODEL_REGISTRY:
            available = ", ".join(self.MODEL_REGISTRY.keys())
            raise ValueError(f"Unknown model '{model_name}'. Available: {available}")

        model_info = self.MODEL_REGISTRY[model_name]
        target_path = self.models_dir / model_info["filename"]

        # Check if already exists
        if target_path.exists() and not force:
            logger.info(f"Model already exists: {target_path}")
            return target_path

        logger.info(f"Downloading {model_name} ({model_info['size_mb']}MB)...")
        logger.info(f"From: {model_info['repo']}")

        try:
            # Download from HuggingFace
            downloaded_path = hf_hub_download(
                repo_id=model_info["repo"],
                filename=model_info["filename"],
                local_dir=str(self.models_dir),
                local_dir_use_symlinks=False,
            )

            # Move to expected location if needed
            downloaded_path = Path(downloaded_path)
            if downloaded_path != target_path:
                shutil.move(str(downloaded_path), str(target_path))

            # Calculate checksum
            checksum = self._calculate_checksum(target_path)

            # Register in metadata
            self.metadata[model_name] = ModelInfo(
                name=model_name,
                path=target_path,
                size_bytes=target_path.stat().st_size,
                version=0,  # Base model
                created=datetime.now(),
                checksum=checksum,
                parent=None,
                training_commands=0,
                metadata={
                    "repo": model_info["repo"],
                    "description": model_info["description"],
                },
            )
            self._save_metadata()

            logger.info(f"✓ Downloaded: {target_path}")
            logger.info(f"  Size: {target_path.stat().st_size / (1024**3):.2f} GB")
            logger.info(f"  SHA256: {checksum[:16]}...")

            return target_path

        except Exception as e:
            logger.error(f"Download failed: {e}")
            if target_path.exists():
                target_path.unlink()
            raise RuntimeError(f"Failed to download {model_name}: {e}")

    def initialize_daedelus(self, base_model: str = "phi-3-mini") -> Path:
        """
        Initialize the first Daedelus model from base.

        Creates daedelus_v1.gguf by copying the base Phi-3 model.
        This is the starting point for personalization.

        Args:
            base_model: Base model name to use

        Returns:
            Path to initialized Daedelus model
        """
        # Ensure base model exists
        if base_model not in self.metadata:
            logger.info(f"Base model '{base_model}' not found, downloading...")
            self.download_model(base_model)

        base_info = self.metadata[base_model]
        daedelus_v1_path = self.models_dir / "daedelus_v1.gguf"

        # Check if already initialized
        if daedelus_v1_path.exists():
            logger.info("Daedelus already initialized")
            return daedelus_v1_path

        logger.info("Initializing Daedelus from base model...")

        # Copy base model to daedelus_v1
        shutil.copy2(base_info.path, daedelus_v1_path)

        # Register in metadata
        checksum = self._calculate_checksum(daedelus_v1_path)
        self.metadata["daedelus_v1"] = ModelInfo(
            name="daedelus_v1",
            path=daedelus_v1_path,
            size_bytes=daedelus_v1_path.stat().st_size,
            version=1,
            created=datetime.now(),
            checksum=checksum,
            parent=base_model,
            training_commands=0,
            metadata={
                "base_model": base_model,
                "description": "Initial Daedelus model (untuned)",
            },
        )
        self._save_metadata()

        # Create symlink to current
        current_link = self.models_dir / "current.gguf"
        if current_link.exists() or current_link.is_symlink():
            current_link.unlink()
        current_link.symlink_to(daedelus_v1_path.name)

        logger.info(f"✓ Initialized: {daedelus_v1_path}")
        logger.info("  Daedelus is ready to learn from your commands!")

        return daedelus_v1_path

    def get_current_model(self) -> Optional[ModelInfo]:
        """
        Get information about the currently active model.

        Returns:
            ModelInfo for current model, or None if not initialized
        """
        current_link = self.models_dir / "current.gguf"
        if not current_link.exists():
            return None

        # Resolve symlink
        actual_path = current_link.resolve()

        # Find in metadata
        for info in self.metadata.values():
            if info.path.resolve() == actual_path:
                return info

        return None

    def forge_next_version(
        self,
        adapter_path: Path,
        training_commands: int,
        notes: Optional[str] = None,
    ) -> Path:
        """
        Forge the next version of Daedelus by merging adapter.

        This is called after fine-tuning to create a new specialized model.

        Args:
            adapter_path: Path to LoRA adapter weights
            training_commands: Number of commands used for training
            notes: Optional notes about this version

        Returns:
            Path to new model version

        Note:
            Actual implementation requires transformers/PEFT for merging.
            This is a placeholder that demonstrates the architecture.
        """
        current = self.get_current_model()
        if not current:
            raise RuntimeError("No current model - initialize Daedelus first")

        next_version = current.version + 1
        next_model_path = self.models_dir / f"daedelus_v{next_version}.gguf"

        logger.info(f"Forging Daedelus v{next_version}...")
        logger.info(f"  Parent: {current.name}")
        logger.info(f"  Training commands: {training_commands}")

        # TODO: Actual implementation would:
        # 1. Load current model with transformers
        # 2. Load and merge LoRA adapter
        # 3. Re-quantize to GGUF format
        # 4. Save as next version
        #
        # For now, we create a placeholder (copy current model)
        # The actual merging will be implemented when PEFT training is active

        logger.warning("Model forging not yet implemented - creating placeholder")
        shutil.copy2(current.path, next_model_path)

        # Register new version
        checksum = self._calculate_checksum(next_model_path)
        self.metadata[f"daedelus_v{next_version}"] = ModelInfo(
            name=f"daedelus_v{next_version}",
            path=next_model_path,
            size_bytes=next_model_path.stat().st_size,
            version=next_version,
            created=datetime.now(),
            checksum=checksum,
            parent=current.name,
            training_commands=current.training_commands + training_commands,
            metadata={
                "notes": notes or "",
                "adapter_path": str(adapter_path),
                "session_commands": training_commands,
            },
        )
        self._save_metadata()

        # Update current symlink
        current_link = self.models_dir / "current.gguf"
        if current_link.exists() or current_link.is_symlink():
            current_link.unlink()
        current_link.symlink_to(next_model_path.name)

        logger.info(f"✓ Forged: {next_model_path}")
        logger.info(f"  Total training: {self.metadata[f'daedelus_v{next_version}'].training_commands} commands")

        return next_model_path

    def list_models(self) -> List[ModelInfo]:
        """
        List all available models.

        Returns:
            List of ModelInfo objects, sorted by version
        """
        models = list(self.metadata.values())
        models.sort(key=lambda m: m.version)
        return models

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """
        Get information about a specific model.

        Args:
            model_name: Model name

        Returns:
            ModelInfo if found, None otherwise
        """
        return self.metadata.get(model_name)

    def verify_model(self, model_name: str) -> bool:
        """
        Verify model file integrity.

        Args:
            model_name: Model name to verify

        Returns:
            True if checksum matches, False otherwise
        """
        info = self.metadata.get(model_name)
        if not info:
            logger.error(f"Model '{model_name}' not found in metadata")
            return False

        if not info.path.exists():
            logger.error(f"Model file not found: {info.path}")
            return False

        logger.info(f"Verifying {model_name}...")
        actual_checksum = self._calculate_checksum(info.path)

        if actual_checksum == info.checksum:
            logger.info("✓ Checksum verified")
            return True
        else:
            logger.error("✗ Checksum mismatch!")
            logger.error(f"  Expected: {info.checksum[:16]}...")
            logger.error(f"  Actual:   {actual_checksum[:16]}...")
            return False

    def get_lineage(self, model_name: str) -> List[str]:
        """
        Get the lineage of a model (chain of parents).

        Args:
            model_name: Model name

        Returns:
            List of model names from root to current
        """
        lineage = []
        current = model_name

        while current:
            lineage.append(current)
            info = self.metadata.get(current)
            if not info or not info.parent:
                break
            current = info.parent

        return list(reversed(lineage))

    def rollback(self, target_version: int) -> Path:
        """
        Rollback to a previous model version.

        Args:
            target_version: Version number to roll back to

        Returns:
            Path to rolled-back model

        Raises:
            ValueError: If version not found
        """
        target_name = f"daedelus_v{target_version}"
        if target_name not in self.metadata:
            raise ValueError(f"Version {target_version} not found")

        target_info = self.metadata[target_name]

        # Update current symlink
        current_link = self.models_dir / "current.gguf"
        if current_link.exists() or current_link.is_symlink():
            current_link.unlink()
        current_link.symlink_to(target_info.path.name)

        logger.info(f"✓ Rolled back to {target_name}")
        return target_info.path

    def cleanup_old_versions(self, keep_latest: int = 5) -> int:
        """
        Delete old model versions to save disk space.

        Args:
            keep_latest: Number of latest versions to keep

        Returns:
            Number of models deleted
        """
        # Get all daedelus versions
        daedelus_models = [
            info for info in self.metadata.values()
            if info.name.startswith("daedelus_v")
        ]
        daedelus_models.sort(key=lambda m: m.version, reverse=True)

        # Keep the latest N versions
        to_delete = daedelus_models[keep_latest:]

        deleted_count = 0
        for info in to_delete:
            logger.info(f"Deleting old version: {info.name}")
            if info.path.exists():
                info.path.unlink()
            del self.metadata[info.name]
            deleted_count += 1

        if deleted_count > 0:
            self._save_metadata()
            logger.info(f"✓ Deleted {deleted_count} old versions")

        return deleted_count


# CLI-friendly functions
def download_phi3(models_dir: Path) -> Path:
    """Download Phi-3-mini model."""
    manager = ModelManager(models_dir)
    return manager.download_model("phi-3-mini")


def initialize_daedelus(models_dir: Path) -> Path:
    """Initialize Daedelus from Phi-3."""
    manager = ModelManager(models_dir)
    return manager.initialize_daedelus()


if __name__ == "__main__":
    # Test the model manager
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ModelManager(Path(tmpdir) / "models")

        print("Daedelus Model Manager Test")
        print("=" * 70)
        print(f"Models directory: {manager.models_dir}")
        print()

        print("Available models in registry:")
        for name, info in ModelManager.MODEL_REGISTRY.items():
            print(f"  - {name}: {info['description']} ({info['size_mb']}MB)")
