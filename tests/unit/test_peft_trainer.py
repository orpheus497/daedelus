"""
Unit tests for PEFTTrainer.

Tests LoRA fine-tuning for personalization.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


class MockPeftModel:
    """Mock PEFT model."""

    def __init__(self, model, config):
        self.model = model
        self.config = config

    def save_pretrained(self, path):
        """Mock save."""
        Path(path).mkdir(parents=True, exist_ok=True)

    def print_trainable_parameters(self):
        """Mock print trainable params."""
        return "trainable params: 4,194,304 || all params: 3,821,079,552 || trainable%: 0.11"

    @staticmethod
    def from_pretrained(model, path):
        """Mock load."""
        return MockPeftModel(model, None)


class MockLoraConfig:
    """Mock LoRA config."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockAutoModel:
    """Mock AutoModelForCausalLM."""

    @staticmethod
    def from_pretrained(model_name, **kwargs):
        """Mock model loading."""
        mock_model = Mock()
        mock_model.model_name = model_name
        mock_model.kwargs = kwargs
        return mock_model


class MockAutoTokenizer:
    """Mock AutoTokenizer."""

    @staticmethod
    def from_pretrained(model_name):
        """Mock tokenizer loading."""
        mock_tokenizer = Mock()
        mock_tokenizer.model_name = model_name
        return mock_tokenizer


@pytest.fixture
def mock_peft_deps():
    """Mock PEFT dependencies."""
    with patch("daedelus.llm.peft_trainer.LoraConfig", MockLoraConfig), \
         patch("daedelus.llm.peft_trainer.get_peft_model", lambda m, c: MockPeftModel(m, c)), \
         patch("daedelus.llm.peft_trainer.PeftModel", MockPeftModel), \
         patch("daedelus.llm.peft_trainer.AutoModelForCausalLM", MockAutoModel), \
         patch("daedelus.llm.peft_trainer.AutoTokenizer", MockAutoTokenizer):
        yield


class TestPEFTTrainerImport:
    """Test PEFT trainer import."""

    def test_import_without_dependencies(self):
        """Test that module can be imported even without PEFT."""
        from daedelus.llm import peft_trainer
        assert peft_trainer is not None

    def test_missing_dependency_error(self):
        """Test that PEFTTrainer raises error if PEFT not installed."""
        with patch("daedelus.llm.peft_trainer.LoraConfig", None):
            from daedelus.llm.peft_trainer import PEFTTrainer

            with pytest.raises(ImportError, match="PEFT dependencies not installed"):
                PEFTTrainer()


class TestPEFTTrainerInit:
    """Test PEFT trainer initialization."""

    def test_init_basic(self, mock_peft_deps):
        """Test basic initialization."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        assert trainer.model_name == "microsoft/Phi-3-mini-4k-instruct"
        assert trainer.r == 8
        assert trainer.lora_alpha == 32
        assert trainer.lora_dropout == 0.1

    def test_init_custom_params(self, mock_peft_deps, tmp_path):
        """Test initialization with custom parameters."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        adapter_path = tmp_path / "adapter"

        trainer = PEFTTrainer(
            model_name="custom/model",
            adapter_path=adapter_path,
            r=16,
            lora_alpha=64,
            lora_dropout=0.2,
        )

        assert trainer.model_name == "custom/model"
        assert trainer.adapter_path == adapter_path
        assert trainer.r == 16
        assert trainer.lora_alpha == 64
        assert trainer.lora_dropout == 0.2

    def test_init_string_adapter_path(self, mock_peft_deps, tmp_path):
        """Test initialization with string adapter path."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        adapter_path = str(tmp_path / "adapter")

        trainer = PEFTTrainer(adapter_path=adapter_path)

        assert isinstance(trainer.adapter_path, Path)


class TestTrainingDataPreparation:
    """Test training data preparation."""

    def test_prepare_training_data_basic(self, mock_peft_deps):
        """Test basic training data preparation."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        commands = ["ls -la", "git status", "npm install"]
        data = trainer.prepare_training_data(commands)

        assert len(data) == 3
        assert all("instruction" in item for item in data)
        assert all("output" in item for item in data)

    def test_prepare_training_data_with_descriptions(self, mock_peft_deps):
        """Test preparation with custom descriptions."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        commands = ["ls -la", "git status"]
        descriptions = ["list all files", "check git status"]

        data = trainer.prepare_training_data(commands, descriptions)

        assert len(data) == 2
        assert "list all files" in data[0]["instruction"]
        assert "check git status" in data[1]["instruction"]

    def test_prepare_training_data_max_samples(self, mock_peft_deps):
        """Test limiting training samples."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        # Create 100 commands
        commands = [f"command{i}" for i in range(100)]

        # Limit to 50
        data = trainer.prepare_training_data(commands, max_samples=50)

        assert len(data) == 50

    def test_prepare_training_data_empty(self, mock_peft_deps):
        """Test preparation with empty command list."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        data = trainer.prepare_training_data([])

        assert len(data) == 0

    def test_prepare_training_data_format(self, mock_peft_deps):
        """Test training data format."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        commands = ["ls -la"]
        data = trainer.prepare_training_data(commands)

        # Check format
        assert data[0]["instruction"].startswith("Generate a shell command for:")
        assert data[0]["output"] == "ls -la"
        assert "input" in data[0]


class TestSimpleDescriptionGeneration:
    """Test simple description generation from commands."""

    def test_generate_simple_description_common_commands(self, mock_peft_deps):
        """Test generating descriptions for common commands."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        test_cases = [
            ("ls", "list files"),
            ("cd /home", "change directory"),
            ("git status", "git operation"),
            ("docker ps", "docker operation"),
            ("npm install", "npm operation"),
        ]

        for cmd, expected_substring in test_cases:
            desc = trainer._generate_simple_description(cmd)
            assert expected_substring in desc

    def test_generate_simple_description_flags(self, mock_peft_deps):
        """Test description generation with flags."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        test_cases = [
            ("ls -la", "all details"),
            ("ls -l", "long format"),
            ("ls -a", "hidden"),
        ]

        for cmd, expected_substring in test_cases:
            desc = trainer._generate_simple_description(cmd)
            assert expected_substring in desc

    def test_generate_simple_description_empty(self, mock_peft_deps):
        """Test description generation for empty command."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        desc = trainer._generate_simple_description("")

        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_generate_simple_description_unknown_command(self, mock_peft_deps):
        """Test description generation for unknown command."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        desc = trainer._generate_simple_description("unknowncmd --flag")

        assert isinstance(desc, str)
        assert "unknowncmd" in desc


class TestAdapterTraining:
    """Test LoRA adapter training."""

    def test_train_adapter_basic(self, mock_peft_deps, tmp_path):
        """Test basic adapter training."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer(adapter_path=tmp_path / "adapter")

        training_data = [
            {"instruction": "Generate: list files", "input": "", "output": "ls -la"},
            {"instruction": "Generate: check git", "input": "", "output": "git status"},
        ]

        # Should not raise an error
        trainer.train_adapter(training_data, output_dir=tmp_path / "output")

        # Check that files were created
        assert (tmp_path / "output" / "training_data.json").exists()
        assert (tmp_path / "output" / "adapter_config.json").exists()

    def test_train_adapter_empty_data(self, mock_peft_deps, tmp_path):
        """Test training with empty data."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer(adapter_path=tmp_path / "adapter")

        # Should handle gracefully
        trainer.train_adapter([], output_dir=tmp_path / "output")

    def test_train_adapter_no_output_dir(self, mock_peft_deps, tmp_path):
        """Test training without output directory."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer(adapter_path=tmp_path / "adapter")

        training_data = [
            {"instruction": "test", "input": "", "output": "test"},
        ]

        # Should use self.adapter_path
        trainer.train_adapter(training_data)

    def test_train_adapter_no_path_raises_error(self, mock_peft_deps):
        """Test training without any path raises error."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()  # No adapter path

        training_data = [
            {"instruction": "test", "input": "", "output": "test"},
        ]

        with pytest.raises(ValueError, match="No output directory"):
            trainer.train_adapter(training_data)

    def test_train_adapter_creates_directory(self, mock_peft_deps, tmp_path):
        """Test that training creates output directory."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        output_dir = tmp_path / "nonexistent" / "adapter"
        trainer = PEFTTrainer()

        training_data = [
            {"instruction": "test", "input": "", "output": "test"},
        ]

        trainer.train_adapter(training_data, output_dir=output_dir)

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_train_adapter_saves_config(self, mock_peft_deps, tmp_path):
        """Test that adapter config is saved."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer(
            adapter_path=tmp_path / "adapter",
            r=16,
            lora_alpha=64,
        )

        training_data = [
            {"instruction": "test", "input": "", "output": "test"},
        ]

        trainer.train_adapter(training_data, num_epochs=5)

        config_file = tmp_path / "adapter" / "adapter_config.json"
        assert config_file.exists()

        # Check config contents
        with open(config_file) as f:
            config = json.load(f)

        assert config["r"] == 16
        assert config["lora_alpha"] == 64
        assert config["num_epochs"] == 5


class TestAdapterLoading:
    """Test LoRA adapter loading."""

    def test_load_adapter_basic(self, mock_peft_deps, tmp_path):
        """Test basic adapter loading."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        # Create mock adapter directory
        adapter_path = tmp_path / "adapter"
        adapter_path.mkdir()
        (adapter_path / "adapter_config.json").write_text("{}")

        trainer = PEFTTrainer(adapter_path=adapter_path)
        trainer.load_adapter()

        assert trainer.model is not None
        assert trainer.tokenizer is not None

    def test_load_adapter_from_path(self, mock_peft_deps, tmp_path):
        """Test loading adapter from specific path."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        adapter_path = tmp_path / "adapter"
        adapter_path.mkdir()
        (adapter_path / "adapter_config.json").write_text("{}")

        trainer = PEFTTrainer()
        trainer.load_adapter(adapter_path)

        assert trainer.model is not None

    def test_load_adapter_not_found(self, mock_peft_deps, tmp_path):
        """Test loading non-existent adapter."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        with pytest.raises(FileNotFoundError):
            trainer.load_adapter(tmp_path / "nonexistent")


class TestExportForLlamaCpp:
    """Test export to llama.cpp format."""

    def test_export_not_implemented(self, mock_peft_deps, tmp_path):
        """Test that export raises NotImplementedError."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()

        with pytest.raises(NotImplementedError):
            trainer.export_for_llama_cpp(tmp_path / "export.gguf")


class TestRepr:
    """Test string representation."""

    def test_repr(self, mock_peft_deps):
        """Test __repr__ method."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer(r=16)
        repr_str = repr(trainer)

        assert "PEFTTrainer" in repr_str
        assert "r=16" in repr_str


class TestIntegration:
    """Test integration scenarios."""

    def test_full_training_workflow(self, mock_peft_deps, tmp_path):
        """Test complete training workflow."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        # Create trainer
        trainer = PEFTTrainer(adapter_path=tmp_path / "adapter")

        # Prepare data
        commands = [
            "ls -la",
            "git status",
            "npm install",
            "docker ps",
            "cd /home",
        ]

        training_data = trainer.prepare_training_data(commands)

        # Train
        trainer.train_adapter(training_data, num_epochs=3)

        # Verify output
        assert (tmp_path / "adapter" / "training_data.json").exists()
        assert (tmp_path / "adapter" / "adapter_config.json").exists()

    def test_save_and_load_workflow(self, mock_peft_deps, tmp_path):
        """Test save and load workflow."""
        from daedelus.llm.peft_trainer import PEFTTrainer

        # Train and save
        trainer1 = PEFTTrainer(adapter_path=tmp_path / "adapter")
        training_data = [
            {"instruction": "test", "input": "", "output": "test"},
        ]
        trainer1.train_adapter(training_data)

        # Load in new trainer
        trainer2 = PEFTTrainer(adapter_path=tmp_path / "adapter")
        trainer2.load_adapter()

        assert trainer2.model is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
