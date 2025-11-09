"""
Tests for embeddings module.

Tests FastText command embeddings with subword support.

Created by: orpheus497
"""

import numpy as np
import pytest
from pathlib import Path

from daedelus.core.embeddings import CommandEmbedder


def test_embedder_initialization(temp_dir):
    """Test embedder creation."""
    embedder = CommandEmbedder(dim=128)
    assert embedder.dim == 128


@pytest.mark.slow
def test_train_model(temp_dir, sample_commands):
    """Test FastText model training."""
    embedder = CommandEmbedder(dim=128)
    model_path = temp_dir / "test_model.bin"

    embedder.train(sample_commands, model_path=model_path)

    assert model_path.exists()


def test_encode_command(temp_dir):
    """Test single command encoding."""
    embedder = CommandEmbedder(dim=128)
    vector = embedder.encode("git status")

    assert vector.shape == (128,)
    assert vector.dtype == np.float32


def test_encode_batch(temp_dir, sample_commands):
    """Test batch encoding."""
    embedder = CommandEmbedder(dim=128)
    vectors = embedder.encode_batch(sample_commands[:5])

    assert vectors.shape == (5, 128)


def test_similarity_calculation(temp_dir):
    """Test cosine similarity."""
    embedder = CommandEmbedder(dim=128)

    v1 = embedder.encode("git status")
    v2 = embedder.encode("git status")  # Same command
    v3 = embedder.encode("python main.py")  # Different

    sim_same = embedder.similarity(v1, v2)
    sim_diff = embedder.similarity(v1, v3)

    assert sim_same > sim_diff


def test_subword_handling(temp_dir):
    """Test typo tolerance via subwords."""
    embedder = CommandEmbedder(dim=128)

    correct = embedder.encode("python")
    typo = embedder.encode("pyton")  # Missing 'h'

    # Should be similar due to subword overlap
    sim = embedder.similarity(correct, typo)
    assert sim > 0.5


def test_save_load_model(temp_dir):
    """Test model persistence."""
    embedder = CommandEmbedder(dim=128)
    model_path = temp_dir / "model.bin"

    # Train and save
    embedder.train(["git status", "ls -la"], model_path=model_path)
    embedder.save(model_path)

    # Load in new instance
    embedder2 = CommandEmbedder(dim=128)
    embedder2.load(model_path)

    # Should produce same encodings
    v1 = embedder.encode("git status")
    v2 = embedder2.encode("git status")

    assert np.allclose(v1, v2)


def test_context_encoding(temp_dir):
    """Test encoding with context."""
    embedder = CommandEmbedder(dim=128)

    cmd = "git commit"
    cwd = "/home/user/project"
    history = ["git add .", "git status"]

    vector = embedder.encode_with_context(cmd, cwd, history)

    assert vector.shape == (128,)


def test_empty_input(temp_dir):
    """Test empty string handling."""
    embedder = CommandEmbedder(dim=128)

    with pytest.raises(ValueError):
        embedder.encode("")


def test_long_command(temp_dir):
    """Test long command encoding."""
    embedder = CommandEmbedder(dim=128)

    long_cmd = "a" * 1000
    vector = embedder.encode(long_cmd)

    assert vector.shape == (128,)


@pytest.mark.performance
def test_encoding_performance(temp_dir):
    """Test encoding latency (<1ms)."""
    import time

    embedder = CommandEmbedder(dim=128)

    start = time.time()
    for _ in range(100):
        embedder.encode("git status")
    elapsed = time.time() - start

    avg_time = elapsed / 100
    assert avg_time < 0.001  # <1ms per encoding


def test_unicode_handling(temp_dir):
    """Test non-ASCII characters."""
    embedder = CommandEmbedder(dim=128)

    unicode_cmd = "echo 你好世界"
    vector = embedder.encode(unicode_cmd)

    assert vector.shape == (128,)


def test_special_characters(temp_dir):
    """Test shell special characters."""
    embedder = CommandEmbedder(dim=128)

    special = "ls | grep test && echo done"
    vector = embedder.encode(special)

    assert vector.shape == (128,)
