"""Tests for PEFT trainer."""

import pytest


def test_peft_trainer_init(temp_dir):
    """Test PEFT trainer initialization."""
    try:
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()
        assert trainer is not None
    except ImportError:
        pytest.skip("PEFT dependencies not installed")


def test_prepare_training_data():
    """Test training data preparation."""
    try:
        from daedelus.llm.peft_trainer import PEFTTrainer

        trainer = PEFTTrainer()
        commands = ["git status", "ls -la"]
        data = trainer.prepare_training_data(commands)
        assert isinstance(data, list)
    except ImportError:
        pytest.skip("PEFT dependencies not installed")
