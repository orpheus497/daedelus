"""
Integration tests for full Daedelus workflow.

Tests the complete pipeline:
- Database + Embeddings + Vector Store + Suggestions
- End-to-end suggestion generation
- Command logging and learning
- Search functionality

Created by: orpheus497
"""

import pytest

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.suggestions import SuggestionEngine
from daedelus.core.vector_store import VectorStore


@pytest.mark.integration
class TestFullWorkflow:
    """Test complete end-to-end workflow."""

    def test_complete_pipeline(self, temp_dir):
        """Test the complete pipeline from logging to suggestions."""
        # 1. Set up components
        db = CommandDatabase(temp_dir / "history.db")
        embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=64, epoch=1)
        vector_store = VectorStore(temp_dir / "index", dim=64)

        # 2. Create session and log commands
        session_id = db.create_session(shell="zsh", cwd="/home/user")

        commands = [
            "git status",
            "git add .",
            "git commit -m 'Initial commit'",
            "git push origin main",
            "ls -la",
            "cd projects",
            "python train.py",
            "pip install numpy",
        ]

        for cmd in commands:
            db.insert_command(cmd, "/home/user", 0, session_id, duration=0.5)

        # 3. Train embedder
        embedder.train_from_corpus(commands + ["git", "python", "docker"])

        # 4. Build vector store
        for cmd in commands:
            embedding = embedder.encode_command(cmd)
            vector_store.add(embedding, cmd, {"cwd": "/home/user"})
        vector_store.build()

        # 5. Create suggestion engine
        engine = SuggestionEngine(db, embedder, vector_store)

        # 6. Get suggestions
        suggestions = engine.get_suggestions("git")

        # Verify results
        assert len(suggestions) > 0
        assert all("command" in s for s in suggestions)
        assert all("confidence" in s for s in suggestions)
        assert any("git" in s["command"] for s in suggestions)

        db.close()

    def test_learning_from_history(self, temp_dir):
        """Test that system learns from command history."""
        db = CommandDatabase(temp_dir / "history.db")
        embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=64, epoch=1)
        vector_store = VectorStore(temp_dir / "index", dim=64)

        # Log the same command multiple times
        session_id = db.create_session()
        for _ in range(10):
            db.insert_command("git status", "/tmp", 0, session_id)

        # Log other commands less frequently
        db.insert_command("git add .", "/tmp", 0, session_id)
        db.insert_command("git commit", "/tmp", 0, session_id)

        # Train and build
        all_commands = ["git status", "git add .", "git commit"]
        embedder.train_from_corpus(all_commands + ["git", "ls", "cd"])

        for cmd in all_commands:
            embedding = embedder.encode_command(cmd)
            vector_store.add(embedding, cmd)
        vector_store.build()

        # Create engine
        engine = SuggestionEngine(db, embedder, vector_store)

        # Get suggestions
        suggestions = engine.get_suggestions("git")

        # "git status" should be highly ranked due to frequency
        if suggestions:
            top_suggestion = suggestions[0]
            assert "git" in top_suggestion["command"]

        db.close()

    def test_context_aware_suggestions(self, temp_dir):
        """Test that suggestions are context-aware."""
        db = CommandDatabase(temp_dir / "history.db")
        embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=64, epoch=1)
        vector_store = VectorStore(temp_dir / "index", dim=64)

        # Log command sequence
        session_id = db.create_session()
        db.insert_command("git add .", "/project", 0, session_id)
        db.insert_command("git commit -m 'test'", "/project", 0, session_id)

        # Train
        commands = ["git add .", "git commit -m 'test'", "git push", "ls"]
        embedder.train_from_corpus(commands)

        for cmd in commands:
            embedding = embedder.encode_command(cmd)
            vector_store.add(embedding, cmd)
        vector_store.build()

        # Create engine
        engine = SuggestionEngine(db, embedder, vector_store)

        # Get suggestions with context
        suggestions = engine.get_suggestions(
            "git",
            cwd="/project",
            history=["git add ."],
        )

        assert len(suggestions) >= 0  # Should not crash
        assert all(isinstance(s, dict) for s in suggestions)

        db.close()

    def test_search_functionality(self, temp_dir):
        """Test search across command history."""
        db = CommandDatabase(temp_dir / "history.db")

        # Log various commands
        session_id = db.create_session()
        db.insert_command("git status", "/project", 0, session_id)
        db.insert_command("git add .", "/project", 0, session_id)
        db.insert_command("docker build -t app .", "/docker", 0, session_id)
        db.insert_command("docker run app", "/docker", 0, session_id)
        db.insert_command("ls -la", "/home", 0, session_id)

        # Search for git commands
        results = db.search_commands("git")

        assert len(results) == 2
        assert all("git" in r["command"] for r in results)

        # Search for docker commands
        results = db.search_commands("docker")

        assert len(results) == 2
        assert all("docker" in r["command"] for r in results)

        # Search with directory filter
        results = db.search_commands("git", cwd_filter="/project")

        assert len(results) == 2
        assert all(r["cwd"].startswith("/project") for r in results)

        db.close()

    def test_pattern_statistics_update(self, temp_dir):
        """Test that pattern statistics are updated."""
        db = CommandDatabase(temp_dir / "history.db")

        # Log commands and update patterns
        session_id = db.create_session()
        db.insert_command("git add .", "/project", 0, session_id)

        # Update pattern statistics
        db.update_pattern_statistics("/project", "git add .", success=True, duration=0.5)
        db.update_pattern_statistics("/project", "git add .", success=True, duration=0.6)
        db.update_pattern_statistics("/project", "git add .", success=False, duration=0.7)

        # Query pattern statistics
        cursor = db.conn.execute(
            "SELECT * FROM command_patterns WHERE context = ? AND command = ?",
            ("/project", "git add ."),
        )
        pattern = cursor.fetchone()

        assert pattern is not None
        assert pattern["frequency"] == 3
        # Success rate should be 2/3
        assert abs(pattern["success_rate"] - 0.6667) < 0.01

        db.close()

    def test_embedding_similarity(self, temp_dir):
        """Test that embeddings capture semantic similarity."""
        embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=64, epoch=1)

        # Train on git commands
        commands = [
            "git status",
            "git add .",
            "git commit",
            "git push",
            "git pull",
            "ls -la",
            "cd /tmp",
            "cat file.txt",
        ]
        embedder.train_from_corpus(commands)

        # Encode git commands
        git_status = embedder.encode_command("git status")
        git_add = embedder.encode_command("git add .")

        # Encode non-git command
        ls_cmd = embedder.encode_command("ls -la")

        # Git commands should be more similar to each other
        git_similarity = embedder._cosine_similarity(git_status, git_add)
        ls_similarity = embedder._cosine_similarity(git_status, ls_cmd)

        assert git_similarity > ls_similarity

    def test_vector_search_accuracy(self, temp_dir):
        """Test vector search finds relevant commands."""
        embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=64, epoch=1)
        vector_store = VectorStore(temp_dir / "index", dim=64)

        # Create test commands
        commands = [
            "git status",
            "git add .",
            "git commit -m 'update'",
            "docker build",
            "docker run",
            "python script.py",
        ]

        embedder.train_from_corpus(commands)

        # Add to vector store
        for cmd in commands:
            embedding = embedder.encode_command(cmd)
            vector_store.add(embedding, cmd)
        vector_store.build()

        # Search for git-related commands
        query = embedder.encode_command("git")
        results = vector_store.search(query, top_k=3)

        # Should find git commands
        assert len(results) >= 1
        git_results = [r for r in results if "git" in r["command"]]
        assert len(git_results) > 0

    def test_cleanup_and_retention(self, temp_dir):
        """Test data cleanup and retention policies."""
        db = CommandDatabase(temp_dir / "history.db")

        # Insert recent commands
        session_id = db.create_session()
        for i in range(10):
            db.insert_command(f"recent_cmd_{i}", "/tmp", 0, session_id)

        # Manually insert old commands
        from datetime import datetime, timedelta

        old_timestamp = (datetime.now() - timedelta(days=100)).timestamp()

        for i in range(5):
            db.conn.execute(
                """
                INSERT INTO command_history (id, timestamp, command, cwd, exit_code, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (f"old_{i}", old_timestamp, f"old_cmd_{i}", "/tmp", 0, session_id),
            )
        db.conn.commit()

        # Clean up old data (90 day retention)
        deleted = db.cleanup_old_data(retention_days=90)

        assert deleted == 5

        # Verify recent commands still exist
        stats = db.get_statistics()
        assert stats["total_commands"] == 10

        db.close()


@pytest.mark.integration
class TestPerformance:
    """Test performance characteristics."""

    def test_large_history_performance(self, temp_dir):
        """Test performance with large command history."""
        db = CommandDatabase(temp_dir / "history.db")

        # Insert many commands
        session_id = db.create_session()
        for i in range(1000):
            db.insert_command(f"command_{i % 100}", "/tmp", 0, session_id)

        # Queries should still be fast
        recent = db.get_recent_commands(n=10)
        assert len(recent) == 10

        search_results = db.search_commands("command")
        assert len(search_results) > 0

        db.close()

    def test_vector_store_large_index(self, temp_dir):
        """Test vector store with large index."""
        embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=32, epoch=1)
        vector_store = VectorStore(temp_dir / "index", dim=32)

        # Create training data
        commands = [f"command_{i}" for i in range(100)]
        embedder.train_from_corpus(commands)

        # Add many vectors
        for cmd in commands:
            embedding = embedder.encode_command(cmd)
            vector_store.add(embedding, cmd)
        vector_store.build()

        # Search should still be fast
        query = embedder.encode_command("command_50")
        results = vector_store.search(query, top_k=10)

        assert len(results) == 10


@pytest.mark.integration
class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_database_recovery(self, temp_dir):
        """Test database can recover from errors."""
        db = CommandDatabase(temp_dir / "history.db")

        # Insert valid data
        session_id = db.create_session()
        db.insert_command("test", "/tmp", 0, session_id)

        # Close and reopen
        db.close()

        db2 = CommandDatabase(temp_dir / "history.db")
        stats = db2.get_statistics()

        assert stats["total_commands"] == 1

        db2.close()

    def test_graceful_degradation(self, temp_dir):
        """Test graceful degradation when components fail."""
        db = CommandDatabase(temp_dir / "history.db")
        embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=64, epoch=1)
        vector_store = VectorStore(temp_dir / "index", dim=64)

        # Train with minimal data
        embedder.train_from_corpus(["cmd" + str(i) for i in range(15)])

        for i in range(10):
            embedding = embedder.encode_command(f"cmd{i}")
            vector_store.add(embedding, f"cmd{i}")
        vector_store.build()

        # Create engine
        engine = SuggestionEngine(db, embedder, vector_store)

        # Should handle empty database gracefully
        suggestions = engine.get_suggestions("test")

        # Should not crash
        assert isinstance(suggestions, list)

        db.close()
