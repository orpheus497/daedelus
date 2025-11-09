"""
Smoke tests for Daedalus.

Basic sanity checks to ensure the package is importable and
core components can be instantiated.

Created by: orpheus497
"""

import tempfile
from pathlib import Path

import pytest


def test_package_imports():
    """Test that all main modules can be imported."""
    # Core imports
    from daedelus import __version__

    # Daemon imports
    # Utils imports

    assert __version__ == "0.2.0"


def test_config_creation():
    """Test configuration can be created."""
    from daedelus.utils.config import Config

    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(
            config_path=Path(tmpdir) / "config.yaml",
            data_dir=Path(tmpdir) / "data",
        )

        assert config.config is not None
        assert config.config_path.parent.exists()
        assert config.data_dir.exists()


def test_database_creation():
    """Test database can be created and initialized."""
    from daedelus.core.database import CommandDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = CommandDatabase(db_path)

        # Check database file was created
        assert db_path.exists()

        # Check can create session
        session_id = db.create_session(shell="zsh", cwd="/tmp")
        assert session_id is not None

        # Check can insert command
        cmd_id = db.insert_command(
            command="ls -la",
            cwd="/tmp",
            exit_code=0,
            session_id=session_id,
            duration=0.5,
        )
        assert cmd_id is not None

        # Check can retrieve commands
        commands = db.get_recent_commands(n=10)
        assert len(commands) == 1
        assert commands[0]["command"] == "ls -la"

        db.close()


def test_embedder_creation():
    """Test embedder can be created."""
    from daedelus.core.embeddings import CommandEmbedder

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "model.bin"
        embedder = CommandEmbedder(model_path=model_path, embedding_dim=64)

        assert embedder.embedding_dim == 64
        assert embedder.model_path == model_path


def test_vector_store_creation():
    """Test vector store can be created."""
    from daedelus.core.vector_store import VectorStore

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = Path(tmpdir) / "index"
        store = VectorStore(index_path=index_path, dim=64)

        assert store.dim == 64
        assert store.index_path == index_path


def test_ipc_message_serialization():
    """Test IPC messages can be serialized and deserialized."""
    from daedelus.daemon.ipc import IPCMessage, MessageType

    # Create message
    msg = IPCMessage(
        MessageType.SUGGEST,
        {"partial": "git", "cwd": "/tmp", "history": ["ls", "cd /tmp"]},
    )

    # Serialize
    json_str = msg.to_json()
    assert "suggest" in json_str
    assert "git" in json_str

    # Deserialize
    msg2 = IPCMessage.from_json(json_str)
    assert msg2.type == MessageType.SUGGEST
    assert msg2.data["partial"] == "git"
    assert msg2.data["cwd"] == "/tmp"
    assert len(msg2.data["history"]) == 2


def test_cli_imports():
    """Test CLI can be imported."""
    from daedelus.cli.main import cli

    assert cli is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
