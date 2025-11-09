"""
Pytest configuration and fixtures for Daedalus tests.

Created by: orpheus497
"""

import tempfile
from pathlib import Path

import pytest

from daedelus.core.database import CommandDatabase
from daedelus.utils.config import Config


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that's cleaned up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_dir):
    """Provide a test configuration."""
    config = Config(
        config_path=temp_dir / "config.yaml",
        data_dir=temp_dir / "data",
    )
    return config


@pytest.fixture
def test_db(temp_dir):
    """Provide a test database."""
    db_path = temp_dir / "test.db"
    db = CommandDatabase(db_path)
    yield db
    db.close()


@pytest.fixture
def sample_commands():
    """Provide sample command data for testing."""
    return [
        "git status",
        "git add .",
        "git commit -m 'Update'",
        "git push origin main",
        "ls -la",
        "cd projects",
        "python train.py",
        "pip install numpy",
        "docker build -t myapp .",
        "docker run -p 8080:8080 myapp",
    ]
