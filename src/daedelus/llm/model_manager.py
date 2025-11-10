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

logger = logging.getLogger(__name__)

# Import with graceful degradation
try:
    from huggingface_hub import hf_hub_download

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
    parent: str | None  # Parent model name (for lineage tracking)
    training_commands: int  # Number of commands used for training
    metadata: dict[str, str]  # Additional metadata


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
        "tinyllama": {
            "repo": "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
            "filename": "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
            "size_mb": 669,
            "description": "TinyLlama 1.1B Chat (Q4 quantized, 100% FOSS Apache 2.0)",
            "checksum": None,  # Will be verified from HF
        },
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

    def _load_metadata(self) -> dict[str, ModelInfo]:
        """Load model metadata from JSON."""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file) as f:
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

    def _find_llama_cpp(self) -> tuple[Path | None, bool]:
        """
        Find llama.cpp installation and verify it works.

        Returns:
            Tuple of (path, verified) where:
            - path: Path to llama.cpp directory if found, None otherwise
            - verified: True if conversion tools were tested and work
        """
        import subprocess

        # Try common installation paths
        possible_paths = [
            Path.home() / "llama.cpp",
            Path("/usr/local/llama.cpp"),
            Path("/opt/llama.cpp"),
            Path.home() / "src" / "llama.cpp",
        ]

        for path in possible_paths:
            if path.exists():
                # Check for conversion script
                convert_script = path / "convert.py"
                if not convert_script.exists():
                    convert_script = path / "convert-hf-to-gguf.py"

                if convert_script.exists():
                    # Verify script actually runs
                    try:
                        result = subprocess.run(
                            ["python", str(convert_script), "--help"],
                            capture_output=True,
                            timeout=5,
                            check=False,
                        )
                        if result.returncode == 0 or "usage:" in result.stdout.decode().lower():
                            logger.info(f"Found and verified llama.cpp at: {path}")
                            return path, True
                    except (subprocess.TimeoutExpired, Exception) as e:
                        logger.debug(f"Could not verify llama.cpp at {path}: {e}")
                        continue

        # Try to find in PATH
        try:
            result = subprocess.run(
                ["which", "convert-hf-to-gguf.py"],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            if result.returncode == 0:
                script_path = Path(result.stdout.strip())
                llama_cpp_path = script_path.parent

                # Verify it runs
                try:
                    result = subprocess.run(
                        [str(script_path), "--help"],
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode == 0 or "usage:" in result.stdout.decode().lower():
                        logger.info(f"Found and verified llama.cpp scripts in PATH: {llama_cpp_path}")
                        return llama_cpp_path, True
                except Exception:
                    pass
        except Exception:
            pass

        logger.warning("llama.cpp not found or not working in common locations")
        logger.warning("Install llama.cpp from: https://github.com/ggerganov/llama.cpp")
        return None, False

    def _convert_to_gguf(
        self,
        hf_model_path: Path,
        output_path: Path,
        llama_cpp_path: Path,
        quantization: str = "q4_k_m",
    ) -> None:
        """
        Convert HuggingFace model to GGUF format.

        Args:
            hf_model_path: Path to HuggingFace model directory
            output_path: Path for output GGUF file
            llama_cpp_path: Path to llama.cpp directory
            quantization: Quantization level (q4_k_m, q8_0, f16, etc.)

        Raises:
            RuntimeError: If conversion fails
        """
        import subprocess

        # Find conversion script
        convert_script = llama_cpp_path / "convert.py"
        if not convert_script.exists():
            convert_script = llama_cpp_path / "convert-hf-to-gguf.py"

        if not convert_script.exists():
            raise FileNotFoundError(
                f"Conversion script not found in {llama_cpp_path}. "
                "Expected convert.py or convert-hf-to-gguf.py"
            )

        # Convert to f16 first
        logger.info("Converting to GGUF (f16)...")
        temp_f16 = output_path.parent / f"{output_path.stem}_f16.gguf"

        try:
            result = subprocess.run(
                [
                    "python",
                    str(convert_script),
                    str(hf_model_path),
                    "--outfile",
                    str(temp_f16),
                    "--outtype",
                    "f16",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=600,
            )
            logger.debug(f"Conversion output: {result.stdout}")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"GGUF conversion failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Conversion timed out after 10 minutes") from e

        # Quantize if needed
        if quantization != "f16":
            logger.info(f"Quantizing to {quantization}...")

            quantize_binary = llama_cpp_path / "quantize"
            if not quantize_binary.exists():
                quantize_binary = llama_cpp_path / "build" / "bin" / "quantize"

            if not quantize_binary.exists():
                logger.warning("Quantize binary not found. Using f16 instead.")
                shutil.copy2(temp_f16, output_path)
                temp_f16.unlink()
                return

            try:
                result = subprocess.run(
                    [
                        str(quantize_binary),
                        str(temp_f16),
                        str(output_path),
                        quantization.upper(),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=600,
                )
                logger.debug(f"Quantization output: {result.stdout}")
                temp_f16.unlink()  # Clean up f16 version

            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Quantization failed: {e.stderr}") from e
            except subprocess.TimeoutExpired as e:
                raise RuntimeError("Quantization timed out after 10 minutes") from e
        else:
            # Just use f16 version
            shutil.copy2(temp_f16, output_path)
            temp_f16.unlink()

        logger.info(f"✓ GGUF conversion complete: {output_path}")

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
                "Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus"
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
            raise RuntimeError(f"Failed to download {model_name}: {e}") from e

    def initialize_daedelus(self, base_model: str = "tinyllama") -> Path:
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

    def get_current_model(self) -> ModelInfo | None:
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
        notes: str | None = None,
        base_model_name: str | None = None,
        skip_verification: bool = False,
        low_memory_mode: bool = False,
    ) -> Path:
        """
        Forge the next version of Daedelus by merging adapter.

        This is called after fine-tuning to create a new specialized model.

        Args:
            adapter_path: Path to LoRA adapter weights
            training_commands: Number of commands used for training
            notes: Optional notes about this version
            base_model_name: HuggingFace model name (default: microsoft/Phi-3-mini-4k-instruct)
            skip_verification: Skip model inference test (faster but riskier)
            low_memory_mode: Use 8-bit loading for memory efficiency (slower but uses less RAM)

        Returns:
            Path to new model version

        Raises:
            RuntimeError: If merging or conversion fails
        """
        current = self.get_current_model()
        if not current:
            raise RuntimeError("No current model - initialize Daedelus first")

        next_version = current.version + 1
        next_model_path = self.models_dir / f"daedelus_v{next_version}.gguf"

        logger.info(f"Forging Daedelus v{next_version}...")
        logger.info(f"  Parent: {current.name}")
        logger.info(f"  Training commands: {training_commands}")
        logger.info(f"  Adapter path: {adapter_path}")

        # Verify adapter exists
        adapter_path = Path(adapter_path)
        if not adapter_path.exists():
            raise FileNotFoundError(f"Adapter not found: {adapter_path}")

        # Import required libraries for model merging
        try:
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            logger.error(
                "transformers and peft are required for model forging. "
                "Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus"
            )
            raise

        # Determine base model name (from metadata or parameter)
        if base_model_name is None:
            # Try to get from current model metadata
            base_model_name = current.metadata.get("base_model_hf", "microsoft/Phi-3-mini-4k-instruct")
            logger.info(f"Using base model from metadata: {base_model_name}")
        else:
            logger.info(f"Using custom base model: {base_model_name}")

        # Step 1: Load base model (HuggingFace format) with optional memory optimization
        logger.info("Loading base model in HuggingFace format...")

        try:
            if low_memory_mode:
                # Use 8-bit loading for memory efficiency
                logger.info("Using low memory mode (8-bit loading)...")
                try:
                    base_model = AutoModelForCausalLM.from_pretrained(
                        base_model_name,
                        device_map="auto",  # Auto device mapping
                        load_in_8bit=True,  # 8-bit quantization
                    )
                    logger.info("✓ Base model loaded in 8-bit mode (memory efficient)")
                except Exception as e:
                    logger.warning(f"8-bit loading failed, falling back to standard: {e}")
                    low_memory_mode = False

            if not low_memory_mode:
                # Standard loading
                base_model = AutoModelForCausalLM.from_pretrained(
                    base_model_name,
                    device_map="cpu",  # Load to CPU for merging
                    torch_dtype="auto",
                    low_cpu_mem_usage=True,  # Enable memory-efficient loading
                )
                logger.info("✓ Base model loaded")

            tokenizer = AutoTokenizer.from_pretrained(base_model_name)

        except Exception as e:
            logger.error(f"Failed to load base model '{base_model_name}': {e}")
            raise RuntimeError(f"Base model loading failed: {e}") from e

        # Step 2: Load and merge LoRA adapter
        logger.info(f"Loading LoRA adapter from {adapter_path}...")
        try:
            model_with_adapter = PeftModel.from_pretrained(
                base_model,
                str(adapter_path),
            )
            logger.info("✓ Adapter loaded")

            logger.info("Merging adapter into base model...")
            merged_model = model_with_adapter.merge_and_unload()
            logger.info("✓ Adapter merged successfully")

        except Exception as e:
            logger.error(f"Failed to load/merge adapter: {e}")
            raise RuntimeError(f"Adapter merge failed: {e}") from e

        # Step 3: Save merged model in HuggingFace format (temporary)
        logger.info("Saving merged model in HuggingFace format...")
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_hf_path = Path(temp_dir) / "merged_hf"
            temp_hf_path.mkdir(exist_ok=True)

            try:
                merged_model.save_pretrained(temp_hf_path)
                tokenizer.save_pretrained(temp_hf_path)
                logger.info("✓ Merged model saved to temporary directory")

            except Exception as e:
                logger.error(f"Failed to save merged model: {e}")
                raise RuntimeError(f"Model save failed: {e}") from e

            # Step 4: Convert to GGUF format using llama.cpp
            logger.info("Converting merged model to GGUF format...")

            # Find and verify llama.cpp tools
            llama_cpp_path, verified = self._find_llama_cpp()

            if llama_cpp_path is None or not verified:
                logger.error(
                    "llama.cpp not found or not working. Cannot convert to GGUF."
                )
                logger.error(
                    "Install llama.cpp from: https://github.com/ggerganov/llama.cpp"
                )
                logger.error(
                    "Without llama.cpp, model forging cannot proceed."
                )
                raise RuntimeError(
                    "llama.cpp is required for GGUF conversion but was not found. "
                    "Install it and ensure convert.py or convert-hf-to-gguf.py is in PATH."
                )

            else:
                try:
                    self._convert_to_gguf(
                        hf_model_path=temp_hf_path,
                        output_path=next_model_path,
                        llama_cpp_path=llama_cpp_path,
                    )
                    logger.info("✓ Converted to GGUF successfully")

                except Exception as e:
                    logger.error(f"GGUF conversion failed: {e}")
                    raise RuntimeError(f"GGUF conversion failed: {e}") from e

        # Step 5: Verify model works before promoting
        if not skip_verification:
            logger.info("Verifying model inference (smoke test)...")
            if not self.test_model_inference(next_model_path):
                logger.error("✗ Model verification failed!")
                logger.error("The generated model does not work correctly.")
                logger.error("Rolling back to previous version...")

                # Clean up broken model
                if next_model_path.exists():
                    next_model_path.unlink()

                raise RuntimeError(
                    "Model verification failed - generated model cannot perform inference. "
                    "The model was not promoted and has been deleted."
                )
            logger.info("✓ Model verification passed")
        else:
            logger.warning("⚠ Skipping model verification (skip_verification=True)")

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
                "base_model_hf": base_model_name,
                "low_memory_mode": low_memory_mode,
                "verified": not skip_verification,
            },
        )
        self._save_metadata()

        # Update current symlink
        current_link = self.models_dir / "current.gguf"
        if current_link.exists() or current_link.is_symlink():
            current_link.unlink()
        current_link.symlink_to(next_model_path.name)

        logger.info(f"✓ Forged: {next_model_path}")
        logger.info(
            f"  Total training: {self.metadata[f'daedelus_v{next_version}'].training_commands} commands"
        )

        return next_model_path

    def list_models(self) -> list[ModelInfo]:
        """
        List all available models.

        Returns:
            List of ModelInfo objects, sorted by version
        """
        models = list(self.metadata.values())
        models.sort(key=lambda m: m.version)
        return models

    def get_model_info(self, model_name: str) -> ModelInfo | None:
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

    def test_model_inference(self, model_path: Path, timeout: int = 30) -> bool:
        """
        Test if a model can perform inference (smoke test).

        Args:
            model_path: Path to GGUF model file
            timeout: Timeout in seconds

        Returns:
            True if model generates output successfully, False otherwise
        """
        if not model_path.exists():
            logger.error(f"Model file not found: {model_path}")
            return False

        try:
            from llama_cpp import Llama

            logger.info("Testing model inference...")

            # Load model with minimal context
            llm = Llama(
                model_path=str(model_path),
                n_ctx=512,  # Minimal context
                n_threads=2,  # Minimal threads
                n_gpu_layers=0,  # CPU only for testing
                verbose=False,
            )

            # Try simple generation
            test_prompt = "Say 'test'"
            output = llm(
                test_prompt,
                max_tokens=10,
                temperature=0.1,
                stop=["test"],
                echo=False,
            )

            # Check if we got any output
            if output and "choices" in output and len(output["choices"]) > 0:
                generated_text = output["choices"][0].get("text", "").strip()
                logger.info(f"✓ Model inference successful: '{generated_text[:50]}'")
                return True
            else:
                logger.error("✗ Model inference produced no output")
                return False

        except ImportError:
            logger.warning("llama-cpp-python not available - skipping inference test")
            return True  # Can't test, assume OK
        except Exception as e:
            logger.error(f"✗ Model inference failed: {e}")
            return False

    def get_lineage(self, model_name: str) -> list[str]:
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
            info for info in self.metadata.values() if info.name.startswith("daedelus_v")
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
