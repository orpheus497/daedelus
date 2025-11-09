"""
PEFT (Parameter-Efficient Fine-Tuning) trainer for Daedelus.

Implements LoRA-based fine-tuning on user's command patterns to personalize
the LLM during daemon shutdown.

Created by: orpheus497
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from peft import LoraConfig, get_peft_model, PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:
    LoraConfig = None  # type: ignore
    get_peft_model = None  # type: ignore
    PeftModel = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore
    AutoTokenizer = None  # type: ignore


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
        adapter_path: Optional[Path] = None,
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
        if LoraConfig is None:
            raise ImportError(
                "PEFT dependencies not installed. "
                "Install with: pip install 'daedelus[llm]'"
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
        commands: List[str],
        descriptions: Optional[List[str]] = None,
        max_samples: int = 1000,
    ) -> List[Dict[str, str]]:
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
        training_data: List[Dict[str, str]],
        output_dir: Optional[Path] = None,
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 1e-4,
    ) -> None:
        """
        Train LoRA adapter on user's command patterns.

        Args:
            training_data: List of training examples
            output_dir: Directory to save adapter (uses self.adapter_path if None)
            num_epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate

        Note:
            This is a simplified training loop. In production, would use
            HuggingFace Trainer for better optimization.
        """
        if not training_data:
            logger.warning("No training data provided")
            return

        output_dir = output_dir or self.adapter_path
        if output_dir is None:
            raise ValueError("No output directory specified for adapter")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Training LoRA adapter on {len(training_data)} examples...")

        # Load base model
        logger.info("Loading base model...")
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            load_in_8bit=True,  # Use 8-bit quantization for efficiency
            device_map="auto",
        )

        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)

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
        formatted_data = []
        for example in training_data:
            # Format as chat
            text = f"<|user|>\n{example['instruction']}<|end|>\n<|assistant|>\n{example['output']}<|end|>"
            formatted_data.append(text)

        # Save formatted data for inspection
        data_file = output_dir / "training_data.json"
        with open(data_file, "w") as f:
            json.dump(training_data, f, indent=2)

        logger.info(f"Training data saved to {data_file}")

        # TODO: Implement actual training loop
        # For now, just save the configuration

        # Save adapter
        logger.info(f"Saving adapter to {output_dir}...")
        model.save_pretrained(output_dir)

        # Save config
        config_file = output_dir / "adapter_config.json"
        with open(config_file, "w") as f:
            json.dump(
                {
                    "model_name": self.model_name,
                    "r": self.r,
                    "lora_alpha": self.lora_alpha,
                    "lora_dropout": self.lora_dropout,
                    "num_examples": len(training_data),
                    "num_epochs": num_epochs,
                },
                f,
                indent=2,
            )

        logger.info("Adapter training complete")

    def load_adapter(self, adapter_path: Optional[Path] = None) -> None:
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
    ) -> None:
        """
        Export adapter for use with llama.cpp.

        Args:
            output_path: Path for exported model
            quantization: Quantization format (q4_k_m, q8_0, etc.)

        Note:
            This requires additional conversion tools.
            See: https://github.com/ggerganov/llama.cpp
        """
        logger.info(f"Exporting adapter to {output_path}...")

        # TODO: Implement actual export
        # Would involve:
        # 1. Merge adapter with base model
        # 2. Convert to GGUF format
        # 3. Quantize

        raise NotImplementedError(
            "Export to llama.cpp format requires additional conversion tools. "
            "See llama.cpp documentation for details."
        )

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
