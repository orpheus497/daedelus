"""
Pytest configuration and shared fixtures for Daedalus tests.

Provides common fixtures used across all test modules.

Created by: orpheus497
"""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from daedelus.core.database import CommandDatabase
from daedelus.utils.config import Config


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for test data.

    Yields:
        Path to temporary directory (cleaned up after test)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_dir: Path) -> Config:
    """
    Create a test configuration with temporary paths.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Config instance with test settings
    """
    config_data = {
        "daemon": {
            "socket_path": str(temp_dir / "daemon.sock"),
            "log_path": str(temp_dir / "daemon.log"),
            "pid_path": str(temp_dir / "daemon.pid"),
        },
        "database": {
            "path": str(temp_dir / "history.db"),
        },
        "model": {
            "model_path": str(temp_dir / "embeddings.bin"),
            "embedding_dim": 128,
        },
        "vector_store": {
            "index_path": str(temp_dir / "index.ann"),
            "n_trees": 10,
        },
        "llm": {
            "enabled": False,  # Disable for most tests
            "model_path": str(temp_dir / "model.gguf"),
        },
    }

    # Create config with test data
    config = Config(config_path=None)
    config.data.update(config_data)
    config.data_dir = temp_dir
    config.config_dir = temp_dir

    return config


@pytest.fixture
def test_db(temp_dir: Path) -> Generator[CommandDatabase, None, None]:
    """
    Create a test database instance.

    Args:
        temp_dir: Temporary directory fixture

    Yields:
        CommandDatabase instance (closed after test)
    """
    db_path = temp_dir / "test.db"
    db = CommandDatabase(db_path)

    yield db

    db.close()


@pytest.fixture
def sample_commands() -> list[str]:
    """
    Provide sample commands for testing.

    Returns:
        List of realistic shell commands
    """
    return [
        "git status",
        "git commit -m 'Initial commit'",
        "git push origin main",
        "ls -la",
        "cd /home/user/project",
        "python main.py",
        "pip install requests",
        "docker build -t myapp .",
        "docker run -p 8000:8000 myapp",
        "npm install",
        "npm test",
        "pytest tests/ -v",
        "black src/",
        "ruff check .",
        "mypy src/",
    ]


@pytest.fixture
def sample_command_history() -> list[dict]:
    """
    Provide sample command history with metadata.

    Returns:
        List of command dictionaries with metadata
    """
    import time

    base_time = time.time()

    return [
        {
            "command": "git status",
            "cwd": "/home/user/project",
            "exit_code": 0,
            "duration": 0.05,
            "timestamp": base_time - 300,
        },
        {
            "command": "git add .",
            "cwd": "/home/user/project",
            "exit_code": 0,
            "duration": 0.12,
            "timestamp": base_time - 240,
        },
        {
            "command": "git commit -m 'Fix bug'",
            "cwd": "/home/user/project",
            "exit_code": 0,
            "duration": 0.23,
            "timestamp": base_time - 180,
        },
        {
            "command": "pytest tests/",
            "cwd": "/home/user/project",
            "exit_code": 0,
            "duration": 5.43,
            "timestamp": base_time - 120,
        },
        {
            "command": "git push origin main",
            "cwd": "/home/user/project",
            "exit_code": 0,
            "duration": 2.15,
            "timestamp": base_time - 60,
        },
    ]


@pytest.fixture
def mock_embeddings(monkeypatch):
    """
    Mock FastText embeddings to avoid training in tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    import numpy as np

    class MockEmbedder:
        def __init__(self, *args, **kwargs):
            self.dim = kwargs.get("dim", 128)

        def encode(self, text: str) -> np.ndarray:
            # Deterministic encoding based on text hash
            import hashlib

            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            np.random.seed(hash_val % (2**32))
            return np.random.randn(self.dim).astype(np.float32)

        def train(self, commands: list[str]) -> None:
            pass

        def save(self, path: Path) -> None:
            pass

        def load(self, path: Path) -> None:
            pass

    monkeypatch.setattr("daedelus.core.embeddings.CommandEmbedder", MockEmbedder)


@pytest.fixture
def mock_llm(monkeypatch):
    """
    Mock LLM inference to avoid loading models in tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """

    class MockLLM:
        def __init__(self, *args, **kwargs):
            self.model_path = kwargs.get("model_path")

        def generate(self, prompt: str, **kwargs) -> str:
            # Simple mock responses based on prompt keywords
            if "explain" in prompt.lower():
                return "This command lists files in the current directory."
            elif "generate" in prompt.lower():
                return "ls -la"
            elif "question" in prompt.lower():
                return "You can use the ls command to list files."
            else:
                return "Mock LLM response"

        def encode(self, text: str) -> list[float]:
            return [0.1] * 128

    monkeypatch.setattr("daedelus.llm.llm_manager.LLMManager", MockLLM)


@pytest.fixture(autouse=True)
def reset_logging():
    """
    Reset logging configuration before each test.

    This prevents log pollution between tests.
    """
    import logging

    # Clear all handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Reset to WARNING level
    root.setLevel(logging.WARNING)

    yield

    # Cleanup after test
    for handler in root.handlers[:]:
        root.removeHandler(handler)


@pytest.fixture
def mock_daemon_running(monkeypatch):
    """
    Mock daemon running state for IPC tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """

    def mock_is_running(*args, **kwargs):
        return True

    monkeypatch.setattr("daedelus.daemon.ipc.IPCClient._check_socket", mock_is_running)


# Performance test markers
def pytest_configure(config):
    """
    Register custom markers for pytest.

    Args:
        config: Pytest config object
    """
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line("markers", "llm: marks tests that require LLM models")
    config.addinivalue_line(
        "markers", "performance: marks tests that measure performance"
    )
