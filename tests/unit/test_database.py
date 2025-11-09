"""
Comprehensive unit tests for CommandDatabase.

Tests all major functionality:
- Schema initialization
- Session management
- Command insertion and retrieval
- FTS5 search
- Pattern statistics
- Cleanup operations
- Context queries

Created by: orpheus497
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from daedelus.core.database import CommandDatabase


class TestCommandDatabaseInit:
    """Test database initialization and schema creation."""

    def test_database_creation(self, temp_dir):
        """Test that database file is created."""
        db_path = temp_dir / "test.db"
        db = CommandDatabase(db_path)

        assert db_path.exists()
        assert db.db_path == db_path
        assert db.conn is not None

        db.close()

    def test_schema_initialization(self, temp_dir):
        """Test that all tables are created."""
        db = CommandDatabase(temp_dir / "test.db")

        # Check tables exist
        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "command_fts",
            "command_fts_config",
            "command_fts_content",
            "command_fts_data",
            "command_fts_docsize",
            "command_fts_idx",
            "command_history",
            "command_patterns",
            "command_sequences",
            "sessions",
        ]

        for table in ["command_history", "sessions", "command_patterns", "command_sequences"]:
            assert table in tables

        db.close()

    def test_foreign_keys_enabled(self, temp_dir):
        """Test that foreign keys are enabled."""
        db = CommandDatabase(temp_dir / "test.db")

        cursor = db.conn.execute("PRAGMA foreign_keys")
        fk_status = cursor.fetchone()[0]

        assert fk_status == 1  # Foreign keys enabled

        db.close()

    def test_indexes_created(self, temp_dir):
        """Test that indexes are created."""
        db = CommandDatabase(temp_dir / "test.db")

        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = [row[0] for row in cursor.fetchall()]

        expected = ["idx_command", "idx_cwd", "idx_exit_code", "idx_session", "idx_timestamp"]

        for idx in expected:
            assert idx in indexes

        db.close()


class TestSessionManagement:
    """Test session creation and management."""

    def test_create_session(self, test_db):
        """Test creating a new session."""
        session_id = test_db.create_session(shell="zsh", cwd="/home/user")

        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0

        # Verify session in database
        cursor = test_db.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        assert session is not None
        assert session["shell"] == "zsh"
        assert session["cwd"] == "/home/user"
        assert session["total_commands"] == 0

    def test_create_session_minimal(self, test_db):
        """Test creating session with minimal info."""
        session_id = test_db.create_session()

        assert session_id is not None

        cursor = test_db.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        assert session is not None
        assert session["shell"] is None
        assert session["cwd"] is None

    def test_end_session(self, test_db):
        """Test ending a session."""
        session_id = test_db.create_session(shell="bash", cwd="/tmp")

        # End session
        test_db.end_session(session_id)

        # Verify end_time is set
        cursor = test_db.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        assert session["end_time"] is not None
        assert session["end_time"] > session["start_time"]

    def test_multiple_sessions(self, test_db):
        """Test creating multiple sessions."""
        session1 = test_db.create_session(shell="zsh")
        session2 = test_db.create_session(shell="bash")
        session3 = test_db.create_session(shell="fish")

        assert session1 != session2 != session3

        cursor = test_db.conn.execute("SELECT COUNT(*) FROM sessions")
        count = cursor.fetchone()[0]

        assert count == 3


class TestCommandInsertion:
    """Test command insertion and retrieval."""

    def test_insert_command(self, test_db):
        """Test inserting a command."""
        session_id = test_db.create_session(shell="zsh", cwd="/tmp")

        cmd_id = test_db.insert_command(
            command="ls -la",
            cwd="/tmp",
            exit_code=0,
            session_id=session_id,
            duration=0.5,
        )

        assert cmd_id is not None

        # Verify command in database
        cursor = test_db.conn.execute("SELECT * FROM command_history WHERE id = ?", (cmd_id,))
        cmd = cursor.fetchone()

        assert cmd is not None
        assert cmd["command"] == "ls -la"
        assert cmd["cwd"] == "/tmp"
        assert cmd["exit_code"] == 0
        assert cmd["duration"] == 0.5
        assert cmd["session_id"] == session_id

    def test_insert_command_updates_session_count(self, test_db):
        """Test that inserting commands updates session count."""
        session_id = test_db.create_session()

        test_db.insert_command("cmd1", "/tmp", 0, session_id)
        test_db.insert_command("cmd2", "/tmp", 0, session_id)
        test_db.insert_command("cmd3", "/tmp", 0, session_id)

        cursor = test_db.conn.execute("SELECT total_commands FROM sessions WHERE id = ?", (session_id,))
        count = cursor.fetchone()[0]

        assert count == 3

    def test_insert_command_with_all_fields(self, test_db):
        """Test inserting command with all optional fields."""
        session_id = test_db.create_session()

        cmd_id = test_db.insert_command(
            command="git status",
            cwd="/home/user/project",
            exit_code=0,
            session_id=session_id,
            duration=1.2,
            output_length=500,
            shell="zsh",
            user="testuser",
            hostname="testhost",
        )

        cursor = test_db.conn.execute("SELECT * FROM command_history WHERE id = ?", (cmd_id,))
        cmd = cursor.fetchone()

        assert cmd["output_length"] == 500
        assert cmd["shell"] == "zsh"
        assert cmd["user"] == "testuser"
        assert cmd["hostname"] == "testhost"

    def test_insert_failed_command(self, test_db):
        """Test inserting a failed command."""
        session_id = test_db.create_session()

        cmd_id = test_db.insert_command(
            command="cat nonexistent.txt",
            cwd="/tmp",
            exit_code=1,
            session_id=session_id,
        )

        cursor = test_db.conn.execute("SELECT exit_code FROM command_history WHERE id = ?", (cmd_id,))
        exit_code = cursor.fetchone()[0]

        assert exit_code == 1


class TestCommandRetrieval:
    """Test command retrieval methods."""

    def test_get_recent_commands(self, test_db, sample_commands):
        """Test getting recent commands."""
        session_id = test_db.create_session()

        # Insert commands
        for cmd in sample_commands:
            test_db.insert_command(cmd, "/tmp", 0, session_id)

        # Get recent commands
        recent = test_db.get_recent_commands(n=5)

        assert len(recent) == 5
        # Should be in reverse chronological order
        assert recent[0]["command"] == sample_commands[-1]

    def test_get_recent_commands_successful_only(self, test_db):
        """Test getting only successful commands."""
        session_id = test_db.create_session()

        test_db.insert_command("success1", "/tmp", 0, session_id)
        test_db.insert_command("failure1", "/tmp", 1, session_id)
        test_db.insert_command("success2", "/tmp", 0, session_id)
        test_db.insert_command("failure2", "/tmp", 127, session_id)

        recent = test_db.get_recent_commands(n=10, successful_only=True)

        assert len(recent) == 2
        assert all(cmd["exit_code"] == 0 for cmd in recent)

    def test_get_session_commands(self, test_db):
        """Test getting commands from a specific session."""
        session1 = test_db.create_session()
        session2 = test_db.create_session()

        test_db.insert_command("cmd1", "/tmp", 0, session1)
        test_db.insert_command("cmd2", "/tmp", 0, session2)
        test_db.insert_command("cmd3", "/tmp", 0, session1)

        session1_cmds = test_db.get_session_commands(session1)

        assert len(session1_cmds) == 2
        assert session1_cmds[0]["command"] == "cmd1"
        assert session1_cmds[1]["command"] == "cmd3"


class TestFTS5Search:
    """Test FTS5 full-text search functionality."""

    def test_search_commands_basic(self, test_db):
        """Test basic FTS5 search."""
        session_id = test_db.create_session()

        test_db.insert_command("git status", "/project", 0, session_id)
        test_db.insert_command("git add .", "/project", 0, session_id)
        test_db.insert_command("git commit -m 'test'", "/project", 0, session_id)
        test_db.insert_command("ls -la", "/project", 0, session_id)

        results = test_db.search_commands("git")

        assert len(results) == 3
        assert all("git" in cmd["command"] for cmd in results)

    def test_search_commands_with_cwd_filter(self, test_db):
        """Test FTS5 search with directory filter."""
        session_id = test_db.create_session()

        test_db.insert_command("ls -la", "/home/user", 0, session_id)
        test_db.insert_command("ls -la", "/tmp", 0, session_id)
        test_db.insert_command("ls -la", "/home/user/project", 0, session_id)

        results = test_db.search_commands("ls", cwd_filter="/home/user")

        assert len(results) == 2
        assert all(cmd["cwd"].startswith("/home/user") for cmd in results)

    def test_search_commands_limit(self, test_db):
        """Test search result limit."""
        session_id = test_db.create_session()

        for i in range(50):
            test_db.insert_command(f"git command {i}", "/tmp", 0, session_id)

        results = test_db.search_commands("git", limit=10)

        assert len(results) == 10

    def test_search_commands_no_results(self, test_db):
        """Test search with no matching results."""
        session_id = test_db.create_session()
        test_db.insert_command("ls -la", "/tmp", 0, session_id)

        results = test_db.search_commands("nonexistent")

        assert len(results) == 0


class TestCommandContext:
    """Test command context retrieval."""

    def test_get_command_context(self, test_db):
        """Test getting command with surrounding context."""
        session_id = test_db.create_session()

        # Insert sequence of commands
        cmd_ids = []
        for i in range(10):
            cmd_id = test_db.insert_command(f"cmd{i}", "/tmp", 0, session_id)
            cmd_ids.append(cmd_id)

        # Get context for middle command
        before, target, after = test_db.get_command_context(cmd_ids[5], window=2)

        assert len(before) == 2
        assert len(after) == 2
        assert target["command"] == "cmd5"
        assert before[0]["command"] == "cmd3"
        assert before[1]["command"] == "cmd4"
        assert after[0]["command"] == "cmd6"
        assert after[1]["command"] == "cmd7"

    def test_get_command_context_at_start(self, test_db):
        """Test getting context for first command."""
        session_id = test_db.create_session()

        cmd_ids = []
        for i in range(5):
            cmd_id = test_db.insert_command(f"cmd{i}", "/tmp", 0, session_id)
            cmd_ids.append(cmd_id)

        before, target, after = test_db.get_command_context(cmd_ids[0], window=3)

        assert len(before) == 0
        assert len(after) == 3
        assert target["command"] == "cmd0"

    def test_get_command_context_at_end(self, test_db):
        """Test getting context for last command."""
        session_id = test_db.create_session()

        cmd_ids = []
        for i in range(5):
            cmd_id = test_db.insert_command(f"cmd{i}", "/tmp", 0, session_id)
            cmd_ids.append(cmd_id)

        before, target, after = test_db.get_command_context(cmd_ids[-1], window=3)

        assert len(before) == 3
        assert len(after) == 0
        assert target["command"] == "cmd4"

    def test_get_command_context_invalid_id(self, test_db):
        """Test getting context for non-existent command."""
        before, target, after = test_db.get_command_context("invalid-id")

        assert before == []
        assert target == {}
        assert after == []


class TestPatternStatistics:
    """Test pattern statistics tracking."""

    def test_update_pattern_statistics_new(self, test_db):
        """Test creating new pattern statistics."""
        test_db.update_pattern_statistics(
            context="/home/user",
            command="git status",
            success=True,
            duration=0.5,
        )

        cursor = test_db.conn.execute(
            "SELECT * FROM command_patterns WHERE context = ? AND command = ?",
            ("/home/user", "git status"),
        )
        pattern = cursor.fetchone()

        assert pattern is not None
        assert pattern["frequency"] == 1
        assert pattern["success_rate"] == 1.0
        assert pattern["avg_duration"] == 0.5

    def test_update_pattern_statistics_existing(self, test_db):
        """Test updating existing pattern statistics."""
        # Create initial pattern
        test_db.update_pattern_statistics("/tmp", "ls", True, 0.1)

        # Update pattern
        test_db.update_pattern_statistics("/tmp", "ls", True, 0.2)
        test_db.update_pattern_statistics("/tmp", "ls", False, 0.15)

        cursor = test_db.conn.execute(
            "SELECT * FROM command_patterns WHERE context = ? AND command = ?",
            ("/tmp", "ls"),
        )
        pattern = cursor.fetchone()

        assert pattern["frequency"] == 3
        # Success rate should be 2/3
        assert abs(pattern["success_rate"] - 0.6667) < 0.01

    def test_update_pattern_statistics_multiple_contexts(self, test_db):
        """Test same command in different contexts."""
        test_db.update_pattern_statistics("/home", "git status", True)
        test_db.update_pattern_statistics("/tmp", "git status", True)

        cursor = test_db.conn.execute("SELECT COUNT(*) FROM command_patterns")
        count = cursor.fetchone()[0]

        assert count == 2


class TestCleanupOperations:
    """Test data cleanup and maintenance."""

    def test_cleanup_old_data(self, test_db):
        """Test cleaning up old commands."""
        session_id = test_db.create_session()

        # Insert old command (manually set timestamp)
        old_timestamp = (datetime.now() - timedelta(days=100)).timestamp()
        test_db.conn.execute(
            """
            INSERT INTO command_history (id, timestamp, command, cwd, exit_code, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("old-id", old_timestamp, "old command", "/tmp", 0, session_id),
        )

        # Insert recent command
        test_db.insert_command("recent command", "/tmp", 0, session_id)

        test_db.conn.commit()

        # Cleanup with 90 day retention
        deleted = test_db.cleanup_old_data(retention_days=90)

        assert deleted == 1

        # Verify old command deleted
        cursor = test_db.conn.execute("SELECT COUNT(*) FROM command_history")
        remaining = cursor.fetchone()[0]

        assert remaining == 1

    def test_cleanup_no_old_data(self, test_db):
        """Test cleanup when no old data exists."""
        session_id = test_db.create_session()
        test_db.insert_command("recent", "/tmp", 0, session_id)

        deleted = test_db.cleanup_old_data(retention_days=30)

        assert deleted == 0


class TestStatistics:
    """Test database statistics."""

    def test_get_statistics(self, test_db):
        """Test getting database statistics."""
        session_id = test_db.create_session()

        test_db.insert_command("cmd1", "/tmp", 0, session_id)
        test_db.insert_command("cmd2", "/tmp", 1, session_id)
        test_db.insert_command("cmd3", "/tmp", 0, session_id)

        stats = test_db.get_statistics()

        assert stats["total_commands"] == 3
        assert stats["total_sessions"] == 1
        assert stats["successful_commands"] == 2
        assert abs(stats["success_rate"] - 66.67) < 0.1
        assert stats["database_size_bytes"] > 0

    def test_get_statistics_empty(self, test_db):
        """Test statistics for empty database."""
        stats = test_db.get_statistics()

        assert stats["total_commands"] == 0
        assert stats["total_sessions"] == 0
        assert stats["successful_commands"] == 0
        assert stats["success_rate"] == 0


class TestContextManager:
    """Test context manager protocol."""

    def test_context_manager(self, temp_dir):
        """Test using database as context manager."""
        db_path = temp_dir / "test.db"

        with CommandDatabase(db_path) as db:
            session_id = db.create_session()
            db.insert_command("test", "/tmp", 0, session_id)

        # Database should be closed after context
        # Verify we can open it again
        db2 = CommandDatabase(db_path)
        stats = db2.get_statistics()
        assert stats["total_commands"] == 1
        db2.close()


class TestRepr:
    """Test string representation."""

    def test_repr(self, test_db):
        """Test __repr__ method."""
        repr_str = repr(test_db)

        assert "CommandDatabase" in repr_str
        assert str(test_db.db_path) in repr_str
