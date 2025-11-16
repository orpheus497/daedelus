"""
PEFT (Parameter-Efficient Fine-Tuning) trainer for Daedelus.

Implements LoRA-based fine-tuning on user's command patterns to personalize
the LLM during daemon shutdown.

Created by: orpheus497
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    PEFT_AVAILABLE = True
except ImportError as e:
    torch = None  # type: ignore
    LoraConfig = None  # type: ignore
    get_peft_model = None  # type: ignore
    PeftModel = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    DataCollatorForLanguageModeling = None  # type: ignore
    Trainer = None  # type: ignore
    TrainingArguments = None  # type: ignore
    Dataset = None  # type: ignore
    PEFT_AVAILABLE = False
    PEFT_IMPORT_ERROR = str(e)


class PEFTTrainer:
    """
    PEFT trainer for personalizing LLM on user's command patterns.

    Uses LoRA (Low-Rank Adaptation) to fine-tune efficiently without
    modifying the base model.

    Attributes:
        model_name: Base model name (e.g., "microsoft/Phi-3-mini-4k-instruct")
        adapter_path: Path to save/load LoRA adapters
        r: LoRA rank (dimensionality)
        lora_alpha: LoRA scaling parameter
        lora_dropout: Dropout probability
    """

    def __init__(
        self,
        model_name: str = "microsoft/Phi-3-mini-4k-instruct",
        adapter_path: Path | None = None,
        r: int = 8,
        lora_alpha: int = 32,
        lora_dropout: float = 0.1,
    ) -> None:
        """
        Initialize PEFT trainer.

        Args:
            model_name: HuggingFace model name
            adapter_path: Path to save/load adapters
            r: LoRA rank (higher = more parameters, better adaptation)
            lora_alpha: LoRA alpha (scaling factor)
            lora_dropout: Dropout probability
        """
        if not PEFT_AVAILABLE:
            raise ImportError(
                f"PEFT dependencies not fully installed: {PEFT_IMPORT_ERROR}\n"
                "Install with: pip install datasets peft transformers accelerate torch"
            )

        self.model_name = model_name
        self.adapter_path = Path(adapter_path) if adapter_path else None
        self.r = r
        self.lora_alpha = lora_alpha
        self.lora_dropout = lora_dropout

        self.model = None
        self.tokenizer = None

        logger.info(f"PEFTTrainer initialized for {model_name}")

    def prepare_training_data(
        self,
        commands: list[str],
        descriptions: list[str] | None = None,
        max_samples: int = 1000,
    ) -> list[dict[str, str]]:
        """
        Prepare training data from command history.

        Creates (description, command) pairs for fine-tuning.

        Args:
            commands: List of command strings
            descriptions: Optional descriptions (if None, generates simple ones)
            max_samples: Maximum number of training samples

        Returns:
            List of training examples

        Example:
            >>> trainer = PEFTTrainer()
            >>> training_data = trainer.prepare_training_data(
            ...     ["ls -la", "git status"],
            ...     ["list all files", "check git status"]
            ... )
        """
        if not commands:
            logger.warning("No commands provided for training")
            return []

        # Limit to max_samples
        commands = commands[:max_samples]

        training_data = []

        for i, cmd in enumerate(commands):
            # Get description
            if descriptions and i < len(descriptions):
                desc = descriptions[i]
            else:
                # Generate simple description from command
                desc = self._generate_simple_description(cmd)

            # Format as instruction-following example
            example = {
                "instruction": f"Generate a shell command for: {desc}",
                "input": "",
                "output": cmd,
            }

            training_data.append(example)

        logger.info(f"Prepared {len(training_data)} training examples")
        return training_data

    def train_adapter(
        self,
        training_data: list[dict[str, str]],
        output_dir: Path | None = None,
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 1e-4,
        validation_split: float = 0.1,
        resume_from_checkpoint: str | None = None,
    ) -> dict[str, float]:
        """
        Train LoRA adapter on user's command patterns with validation and checkpointing.

        Args:
            training_data: List of training examples
            output_dir: Directory to save adapter (uses self.adapter_path if None)
            num_epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
            validation_split: Fraction of data to use for validation (0.0-1.0)
            resume_from_checkpoint: Path to checkpoint to resume from

        Returns:
            Dictionary with training and validation metrics

        Features:
            - Validation split for model evaluation
            - Automatic checkpointing with resume capability
            - Evaluation metrics (loss, perplexity)
            - Training quality assessment
        """
        if not training_data:
            logger.warning("No training data provided")
            return {}

        output_dir = output_dir or self.adapter_path
        if output_dir is None:
            raise ValueError("No output directory specified for adapter")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Training LoRA adapter on {len(training_data)} examples...")
        logger.info(f"Validation split: {validation_split * 100:.1f}%")

        # Check if CUDA is available
        use_cuda = False
        try:
            use_cuda = torch.cuda.is_available()
            if use_cuda:
                logger.info(f"✅ CUDA available: {torch.cuda.device_count()} GPU(s) detected")
                logger.info(f"   GPU: {torch.cuda.get_device_name(0)}")
                logger.info(f"   CUDA Version: {torch.version.cuda}")
            else:
                logger.info("ℹ️  CUDA not available - training will use CPU (slower)")
                logger.info("   For GPU acceleration, run: scripts/fix_cuda_pytorch.sh")
        except Exception as e:
            str(e)
            logger.warning(f"⚠️  CUDA check failed: {e}")
            logger.warning("   Falling back to CPU mode")
            use_cuda = False

        # Load base model
        logger.info("Loading base model...")
        if use_cuda:
            try:
                # Try 8-bit quantization on CUDA
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    load_in_8bit=True,
                    device_map="auto",
                )
                logger.info("Using 8-bit quantization on CUDA")
            except Exception as e:
                logger.warning(f"8-bit quantization failed: {e}, falling back to CPU")
                use_cuda = False

        if not use_cuda:
            # CPU-only mode - no quantization
            logger.info("Using CPU mode (no quantization)")
            logger.warning("⚠️  CPU training is significantly slower than GPU training")
            logger.info("   Expected training time: ~10-30 minutes (vs ~1-3 min on GPU)")
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                dtype=torch.float32,  # Updated from torch_dtype to dtype
                low_cpu_mem_usage=True,
            )

        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        # Set padding token if not present
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id

        # Configure LoRA
        peft_config = LoraConfig(
            r=self.r,
            lora_alpha=self.lora_alpha,
            lora_dropout=self.lora_dropout,
            target_modules=["q_proj", "v_proj"],  # Attention modules
            bias="none",
            task_type="CAUSAL_LM",
        )

        # Apply LoRA
        model = get_peft_model(model, peft_config)

        logger.info(f"Trainable parameters: {model.print_trainable_parameters()}")

        # Format training data
        formatted_texts = []
        for example in training_data:
            # Format as chat for Phi-3
            text = f"<|user|>\n{example['instruction']}<|end|>\n<|assistant|>\n{example['output']}<|end|>"
            formatted_texts.append(text)

        # Save formatted data for inspection
        data_file = output_dir / "training_data.json"
        with open(data_file, "w") as f:
            json.dump(training_data, f, indent=2)

        logger.info(f"Training data saved to {data_file}")

        # Tokenize training data
        logger.info("Tokenizing training data...")

        def tokenize_function(examples: dict[str, list[str]]) -> dict[str, list]:
            """Tokenize examples for training."""
            tokenized = tokenizer(
                examples["text"],
                truncation=True,
                max_length=512,
                padding="max_length",
                return_tensors=None,
            )
            # For causal LM, labels are the same as input_ids
            tokenized["labels"] = tokenized["input_ids"].copy()
            return tokenized

        # Create HuggingFace Dataset
        dataset_dict = {"text": formatted_texts}
        dataset = Dataset.from_dict(dataset_dict)

        # Tokenize dataset
        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names,
        )

        logger.info(f"Dataset tokenized: {len(tokenized_dataset)} examples")

        # Split into train and validation sets
        train_dataset = tokenized_dataset
        eval_dataset = None

        if validation_split > 0.0 and len(tokenized_dataset) > 10:
            # Only split if we have enough data
            split_idx = int(len(tokenized_dataset) * (1 - validation_split))

            # Shuffle before splitting for better validation
            import random

            indices = list(range(len(tokenized_dataset)))
            random.shuffle(indices)

            train_indices = indices[:split_idx]
            eval_indices = indices[split_idx:]

            train_dataset = tokenized_dataset.select(train_indices)
            eval_dataset = tokenized_dataset.select(eval_indices)

            logger.info(
                f"Split dataset: {len(train_dataset)} train, {len(eval_dataset)} validation"
            )
        else:
            logger.info("Validation disabled (insufficient data or validation_split=0)")

        # Configure training arguments with evaluation
        training_args = TrainingArguments(
            output_dir=str(output_dir / "checkpoints"),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,  # Evaluation batch size
            gradient_accumulation_steps=4,  # Effective batch size = 4 * batch_size
            learning_rate=learning_rate,
            warmup_steps=100,
            logging_steps=10,
            eval_strategy="epoch" if eval_dataset else "no",  # Evaluate each epoch
            save_strategy="epoch",
            save_total_limit=2,  # Keep only 2 latest checkpoints
            load_best_model_at_end=True if eval_dataset else False,  # Load best model
            metric_for_best_model="eval_loss" if eval_dataset else None,
            fp16=True,  # Mixed precision training
            optim="adamw_torch",
            report_to="none",  # Disable wandb/tensorboard
            logging_dir=str(output_dir / "logs"),
            remove_unused_columns=False,
        )

        # Create data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False,  # Causal LM, not masked LM
        )

        # Initialize trainer with evaluation dataset
        logger.info("Initializing trainer...")
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,  # Add validation dataset
            data_collator=data_collator,
        )

        # Execute training loop with gradient descent
        logger.info("Starting training loop...")
        if resume_from_checkpoint:
            logger.info(f"Resuming from checkpoint: {resume_from_checkpoint}")

        try:
            train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)

            # Log training metrics
            logger.info("Training completed successfully!")
            logger.info(f"Training loss: {train_result.training_loss:.4f}")
            logger.info(f"Training steps: {train_result.global_step}")

            # Calculate perplexity (exp(loss))
            import math

            train_perplexity = math.exp(train_result.training_loss)
            logger.info(f"Training perplexity: {train_perplexity:.2f}")

            # Collect metrics
            metrics = {
                "training_loss": float(train_result.training_loss),
                "training_perplexity": float(train_perplexity),
                "global_step": train_result.global_step,
                "num_epochs": num_epochs,
                "num_train_examples": len(train_dataset),
                "num_eval_examples": len(eval_dataset) if eval_dataset else 0,
            }

            # Add evaluation metrics if available
            if eval_dataset:
                logger.info("Running final evaluation...")
                eval_result = trainer.evaluate()
                eval_loss = eval_result.get("eval_loss", 0.0)
                eval_perplexity = math.exp(eval_loss) if eval_loss > 0 else 0.0

                logger.info(f"Evaluation loss: {eval_loss:.4f}")
                logger.info(f"Evaluation perplexity: {eval_perplexity:.2f}")

                metrics["eval_loss"] = float(eval_loss)
                metrics["eval_perplexity"] = float(eval_perplexity)

                # Quality assessment
                if eval_perplexity < 10.0:
                    quality = "excellent"
                elif eval_perplexity < 20.0:
                    quality = "good"
                elif eval_perplexity < 50.0:
                    quality = "acceptable"
                else:
                    quality = "poor"

                metrics["quality_assessment"] = quality
                logger.info(f"Model quality: {quality} (perplexity: {eval_perplexity:.2f})")

            # Save metrics
            metrics_file = output_dir / "training_metrics.json"
            with open(metrics_file, "w") as f:
                json.dump(metrics, f, indent=2)

        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

        # Save final adapter
        logger.info(f"Saving trained adapter to {output_dir}...")
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)

        # Save config with enhanced metadata
        config_file = output_dir / "adapter_config.json"
        with open(config_file, "w") as f:
            json.dump(
                {
                    "model_name": self.model_name,
                    "r": self.r,
                    "lora_alpha": self.lora_alpha,
                    "lora_dropout": self.lora_dropout,
                    "num_examples": len(training_data),
                    "num_train_examples": len(train_dataset),
                    "num_eval_examples": len(eval_dataset) if eval_dataset else 0,
                    "num_epochs": num_epochs,
                    "batch_size": batch_size,
                    "learning_rate": learning_rate,
                    "validation_split": validation_split,
                },
                f,
                indent=2,
            )

        logger.info("Adapter training complete")
        return metrics

    def load_adapter(self, adapter_path: Path | None = None) -> None:
        """
        Load a trained LoRA adapter.

        Args:
            adapter_path: Path to adapter directory

        Raises:
            FileNotFoundError: If adapter not found
        """
        adapter_path = Path(adapter_path or self.adapter_path)

        if not adapter_path.exists():
            raise FileNotFoundError(f"Adapter not found: {adapter_path}")

        logger.info(f"Loading adapter from {adapter_path}...")

        # Load base model
        base_model = AutoModelForCausalLM.from_pretrained(self.model_name)

        # Load adapter
        self.model = PeftModel.from_pretrained(base_model, str(adapter_path))
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        logger.info("Adapter loaded successfully")

    def _generate_simple_description(self, command: str) -> str:
        """
        Generate a simple description from command.

        Args:
            command: Shell command

        Returns:
            Simple description

        Example:
            >>> desc = trainer._generate_simple_description("ls -la")
            >>> print(desc)  # "list files with all details"
        """
        # Simple rule-based description generation
        cmd_parts = command.split()

        if not cmd_parts:
            return "execute command"

        base_cmd = cmd_parts[0]

        # Common command patterns
        descriptions = {
            "ls": "list files",
            "cd": "change directory",
            "git": "git operation",
            "docker": "docker operation",
            "python": "run python",
            "npm": "npm operation",
            "cat": "display file",
            "grep": "search text",
            "find": "find files",
            "rm": "remove files",
            "cp": "copy files",
            "mv": "move files",
            "tar": "archive files",
            "curl": "make HTTP request",
        }

        base_desc = descriptions.get(base_cmd, f"run {base_cmd}")

        # Add flags info
        if "-la" in command or "-al" in command:
            base_desc += " with all details"
        elif "-l" in command:
            base_desc += " in long format"
        elif "-a" in command:
            base_desc += " including hidden"

        return base_desc

    def export_for_llama_cpp(
        self,
        output_path: Path,
        quantization: str = "q4_k_m",
        llama_cpp_path: Path | None = None,
    ) -> None:
        """
        Export adapter for use with llama.cpp.

        Merges the LoRA adapter with the base model and converts to GGUF format
        for use with llama.cpp inference.

        Args:
            output_path: Path for exported GGUF model
            quantization: Quantization format (q4_k_m, q8_0, f16, etc.)
            llama_cpp_path: Path to llama.cpp repository (auto-detect if None)

        Raises:
            RuntimeError: If conversion fails or tools not found
            FileNotFoundError: If adapter not loaded
        """
        logger.info(f"Exporting adapter to {output_path}...")

        if self.model is None:
            raise FileNotFoundError(
                "No adapter loaded. Call load_adapter() first or train a new adapter."
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Step 1: Merge adapter with base model
        logger.info("Merging LoRA adapter with base model...")
        try:
            merged_model = self.model.merge_and_unload()
        except AttributeError:
            logger.error("Model does not have merge_and_unload method. Loading adapter first...")
            # If model is not a PeftModel, try loading the adapter
            if self.adapter_path and self.adapter_path.exists():
                base_model = AutoModelForCausalLM.from_pretrained(self.model_name)
                peft_model = PeftModel.from_pretrained(base_model, str(self.adapter_path))
                merged_model = peft_model.merge_and_unload()
            else:
                raise

        # Step 2: Save merged model in HuggingFace format
        logger.info("Saving merged model in HuggingFace format...")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "merged_model"
            merged_model.save_pretrained(temp_path)
            self.tokenizer.save_pretrained(temp_path)

            logger.info(f"Merged model saved to temporary directory: {temp_path}")

            # Step 3: Find llama.cpp tools
            if llama_cpp_path is None:
                # Try to auto-detect llama.cpp
                possible_paths = [
                    Path.home() / "llama.cpp",
                    Path("/usr/local/llama.cpp"),
                    Path("/opt/llama.cpp"),
                ]

                for path in possible_paths:
                    if path.exists() and (path / "convert.py").exists():
                        llama_cpp_path = path
                        break

                if llama_cpp_path is None:
                    logger.warning("llama.cpp not found. Trying system-wide python scripts...")
                    # Try to find convert.py in PATH
                    try:
                        result = subprocess.run(
                            ["which", "convert-hf-to-gguf.py"],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if result.returncode == 0:
                            llama_cpp_path = Path(result.stdout.strip()).parent
                    except Exception:
                        pass

            if llama_cpp_path is None or not llama_cpp_path.exists():
                raise RuntimeError(
                    "llama.cpp tools not found. Please install llama.cpp and provide path.\n"
                    "Clone from: https://github.com/ggerganov/llama.cpp"
                )

            logger.info(f"Using llama.cpp from: {llama_cpp_path}")

            # Step 4: Convert to GGUF using convert.py
            logger.info("Converting to GGUF format (f16)...")
            temp_gguf = temp_path.parent / "model_f16.gguf"

            convert_script = llama_cpp_path / "convert.py"
            if not convert_script.exists():
                # Try newer script name
                convert_script = llama_cpp_path / "convert-hf-to-gguf.py"

            if not convert_script.exists():
                raise FileNotFoundError(
                    f"Conversion script not found in {llama_cpp_path}. "
                    "Expected convert.py or convert-hf-to-gguf.py"
                )

            try:
                result = subprocess.run(
                    [
                        "python",
                        str(convert_script),
                        str(temp_path),
                        "--outfile",
                        str(temp_gguf),
                        "--outtype",
                        "f16",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=600,  # 10 minute timeout
                )
                logger.debug(f"Conversion output: {result.stdout}")
                logger.info("✓ Converted to GGUF (f16)")

            except subprocess.CalledProcessError as e:
                logger.error(f"Conversion failed: {e.stderr}")
                raise RuntimeError(f"GGUF conversion failed: {e.stderr}") from e
            except subprocess.TimeoutExpired as e:
                raise RuntimeError("Conversion timed out after 10 minutes") from e

            # Step 5: Quantize to target format
            if quantization != "f16":
                logger.info(f"Quantizing to {quantization}...")

                quantize_binary = llama_cpp_path / "quantize"
                if not quantize_binary.exists():
                    # Try in build directory
                    quantize_binary = llama_cpp_path / "build" / "bin" / "quantize"

                if not quantize_binary.exists():
                    logger.warning(
                        "Quantize binary not found. Saving as f16. "
                        "Build llama.cpp to enable quantization."
                    )
                    # Just copy f16 version
                    import shutil

                    shutil.copy2(temp_gguf, output_path)
                else:
                    try:
                        result = subprocess.run(
                            [
                                str(quantize_binary),
                                str(temp_gguf),
                                str(output_path),
                                quantization.upper(),
                            ],
                            capture_output=True,
                            text=True,
                            check=True,
                            timeout=600,
                        )
                        logger.debug(f"Quantization output: {result.stdout}")
                        logger.info(f"✓ Quantized to {quantization}")

                    except subprocess.CalledProcessError as e:
                        logger.error(f"Quantization failed: {e.stderr}")
                        raise RuntimeError(f"Quantization failed: {e.stderr}") from e
                    except subprocess.TimeoutExpired as e:
                        raise RuntimeError("Quantization timed out after 10 minutes") from e
            else:
                # Just copy f16 version
                import shutil

                shutil.copy2(temp_gguf, output_path)

        # Step 6: Verify output
        if not output_path.exists():
            raise RuntimeError(f"Export failed: output file not created at {output_path}")

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Export complete: {output_path}")
        logger.info(f"  Size: {file_size_mb:.1f} MB")
        logger.info(f"  Format: GGUF ({quantization})")

        return

    def __repr__(self) -> str:
        """String representation."""
        return f"PEFTTrainer(model={self.model_name}, r={self.r})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("PEFTTrainer example - requires PEFT dependencies")

    # Example training workflow:
    print("\nExample training workflow:")
    print("1. Collect command history from database")
    print("2. Prepare training data (command, description pairs)")
    print("3. Train LoRA adapter (during daemon shutdown)")
    print("4. Save adapter for future use")
    print("5. Load adapter when LLM is initialized")

    # Example training data:
    example_data = [
        {
            "instruction": "Generate a shell command for: list all files including hidden",
            "input": "",
            "output": "ls -la",
        },
        {
            "instruction": "Generate a shell command for: check git status",
            "input": "",
            "output": "git status",
        },
        {
            "instruction": "Generate a shell command for: copy file to server",
            "input": "",
            "output": "scp file.txt user@server:/path/",
        },
    ]

    print("\nExample training data format:")
    print(json.dumps(example_data[0], indent=2))
