"""
Tests for database module.

Tests the SQLite database with FTS5 full-text search,
command logging, session tracking, and retention policies.

Created by: orpheus497
"""

import time

import pytest

from daedelus.core.database import CommandDatabase as Database


def test_database_initialization(temp_dir):
    """Test database creation with proper schema."""
    db_path = temp_dir / "test.db"
    db = Database(db_path)

    assert db_path.exists()
    assert db.conn is not None

    # Verify tables exist
    cursor = db.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert "command_history" in tables
    assert "sessions" in tables
    assert "command_patterns" in tables

    db.close()


def test_log_command(test_db):
    """Test logging a single command."""
    command_id = test_db.log_command(
        command="git status",
        cwd="/home/user/project",
        exit_code=0,
        duration=0.05,
    )

    assert command_id is not None
    assert isinstance(command_id, str) and len(command_id) > 0

    # Verify command was stored
    cursor = test_db.conn.cursor()
    cursor.execute(
        "SELECT command, cwd, exit_code FROM command_history WHERE id = ?", (command_id,)
    )
    row = cursor.fetchone()

    assert row is not None
    assert row[0] == "git status"
    assert row[1] == "/home/user/project"
    assert row[2] == 0


def test_log_command_batch(test_db):
    """Test batch insert performance."""
    commands = [
        ("git status", "/home/user/project", 0, 0.05),
        ("git add .", "/home/user/project", 0, 0.12),
        ("git commit -m 'test'", "/home/user/project", 0, 0.23),
    ]

    start_time = time.time()

    for cmd, cwd, exit_code, duration in commands:
        test_db.log_command(cmd, cwd, exit_code, duration)

    elapsed = time.time() - start_time

    # Should be very fast (<100ms for 3 commands)
    assert elapsed < 0.1

    # Verify all commands were stored
    cursor = test_db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM command_history")
    count = cursor.fetchone()[0]

    assert count == 3


def test_get_recent_commands(test_db):
    """Test retrieving recent command history."""
    # Log some commands
    for i in range(10):
        test_db.log_command(
            command=f"echo {i}",
            cwd="/home/user",
            exit_code=0,
            duration=0.01,
        )

    # Get recent commands
    recent = test_db.get_recent_commands(n=5)

    assert len(recent) == 5
    # Should be in reverse chronological order
    assert recent[0]["command"] == "echo 9"
    assert recent[4]["command"] == "echo 5"


def test_search_commands_fts5(test_db):
    """Test FTS5 full-text search."""
    # Log commands with different content
    test_db.log_command("git status", "/home/user/project", 0, 0.05)
    test_db.log_command("git commit -m 'Fix bug'", "/home/user/project", 0, 0.23)
    test_db.log_command("pytest tests/", "/home/user/project", 0, 5.43)
    test_db.log_command("docker build -t app .", "/home/user/docker", 0, 30.0)

    # Search for git commands
    results = test_db.search_commands("git")
    assert len(results) >= 2
    assert all("git" in r["command"] for r in results)

    # Search for pytest
    results = test_db.search_commands("pytest")
    assert len(results) >= 1
    assert "pytest" in results[0]["command"]


def test_search_by_prefix(test_db):
    """Test prefix matching for autocomplete."""
    test_db.log_command("git status", "/home/user/project", 0, 0.05)
    test_db.log_command("git add .", "/home/user/project", 0, 0.12)
    test_db.log_command("git commit", "/home/user/project", 0, 0.23)
    test_db.log_command("python main.py", "/home/user/project", 0, 1.0)

    # Search for commands starting with "git"
    results = test_db.get_commands_by_prefix("git")

    assert len(results) >= 3
    assert all(r["command"].startswith("git") for r in results)


def test_get_command_stats(test_db):
    """Test frequency and success rate statistics."""
    # Log same command multiple times with different exit codes
    for i in range(5):
        test_db.log_command("pytest tests/", "/home/user/project", 0, 2.0)

    test_db.log_command("pytest tests/", "/home/user/project", 1, 2.0)  # Failure

    stats = test_db.get_command_stats("pytest tests/")

    assert stats is not None
    assert stats["count"] == 6
    assert stats["success_rate"] == pytest.approx(5 / 6, rel=0.01)


def test_session_tracking(test_db):
    """Test session creation and management."""
    session_id = test_db.create_session()

    assert session_id is not None
    assert isinstance(session_id, str) and len(session_id) > 0

    # Log commands in session
    test_db.log_command("echo test", "/home/user", 0, 0.01, session_id=session_id)
    test_db.log_command("ls -la", "/home/user", 0, 0.02, session_id=session_id)

    # End session
    test_db.end_session(session_id)

    # Verify session was recorded
    cursor = test_db.conn.cursor()
    cursor.execute("SELECT total_commands, end_time FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()

    assert row is not None
    assert row[0] == 2  # total_commands
    assert row[1] is not None  # end_time


def test_command_sequences(test_db):
    """Test sequential pattern tracking."""
    # Log a sequence of related commands
    session_id = test_db.create_session()
    commands = ["git add .", "git commit -m 'test'", "git push origin main"]

    for cmd in commands:
        test_db.log_command(cmd, "/home/user/project", 0, 0.1, session_id=session_id)

    # Get command sequences
    sequences = test_db.get_command_sequences(min_length=2)

    assert len(sequences) > 0
    # Should find "git add" followed by "git commit"
    assert any("git add" in seq[0] and "git commit" in seq[1] for seq in sequences if len(seq) >= 2)


def test_cleanup_old_commands(test_db):
    """Test retention policy for old commands."""
    # Log old command (91 days ago)
    import uuid

    old_timestamp = time.time() - (91 * 24 * 60 * 60)

    # Create a session for old command
    session_id = test_db.create_session()

    cursor = test_db.conn.cursor()
    cursor.execute(
        "INSERT INTO command_history (id, command, cwd, timestamp, exit_code, duration, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "old command", "/home/user", old_timestamp, 0, 0.01, session_id),
    )
    test_db.conn.commit()

    # Log recent command
    test_db.log_command("new command", "/home/user", 0, 0.01)

    # Cleanup commands older than 90 days
    deleted_count = test_db.cleanup_old_commands(days=90)

    assert deleted_count >= 1

    # Verify old command was deleted
    cursor.execute("SELECT COUNT(*) FROM command_history WHERE command = 'old command'")
    assert cursor.fetchone()[0] == 0

    # Verify new command still exists
    cursor.execute("SELECT COUNT(*) FROM command_history WHERE command = 'new command'")
    assert cursor.fetchone()[0] == 1


def test_database_backup(test_db, temp_dir):
    """Test SQLite backup functionality."""
    # Log some data
    test_db.log_command("test command", "/home/user", 0, 0.01)

    # Create backup
    backup_path = temp_dir / "backup.db"
    test_db.backup(backup_path)

    assert backup_path.exists()

    # Verify backup contains data
    backup_db = Database(backup_path)
    cursor = backup_db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM command_history")
    count = cursor.fetchone()[0]

    assert count == 1
    backup_db.close()


def test_transaction_rollback(test_db):
    """Test transaction rollback on error."""
    # Log a command
    test_db.log_command("test", "/home/user", 0, 0.01)

    # Start transaction
    cursor = test_db.conn.cursor()
    cursor.execute("BEGIN")

    try:
        # Insert invalid data to trigger error
        cursor.execute("INSERT INTO command_history (command) VALUES (NULL)")
        test_db.conn.commit()
    except Exception:
        test_db.conn.rollback()

    # Verify database is still consistent
    cursor.execute("SELECT COUNT(*) FROM command_history")
    count = cursor.fetchone()[0]
    assert count == 1  # Only the first command


@pytest.mark.slow
def test_concurrent_access(test_db, temp_dir):
    """Test multi-process database safety."""
    import multiprocessing

    def worker(db_path, worker_id):
        db = Database(db_path)
        for i in range(10):
            db.log_command(f"worker {worker_id} command {i}", "/home/user", 0, 0.01)
        db.close()

    # Create workers
    processes = []
    for i in range(3):
        p = multiprocessing.Process(target=worker, args=(test_db.db_path, i))
        p.start()
        processes.append(p)

    # Wait for all workers
    for p in processes:
        p.join()

    # Verify all commands were logged
    cursor = test_db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM command_history")
    count = cursor.fetchone()[0]

    assert count == 30  # 3 workers × 10 commands


def test_get_commands_by_cwd(test_db):
    """Test filtering commands by directory."""
    test_db.log_command("git status", "/home/user/project1", 0, 0.05)
    test_db.log_command("git status", "/home/user/project2", 0, 0.05)
    test_db.log_command("ls -la", "/home/user/project1", 0, 0.02)

    results = test_db.get_commands_by_cwd("/home/user/project1")

    assert len(results) == 2
    assert all(r["cwd"] == "/home/user/project1" for r in results)


def test_get_commands_by_exit_code(test_db):
    """Test filtering by success/failure."""
    test_db.log_command("success1", "/home/user", 0, 0.01)
    test_db.log_command("failure1", "/home/user", 1, 0.01)
    test_db.log_command("success2", "/home/user", 0, 0.01)

    # Get successful commands
    successes = test_db.get_commands_by_exit_code(0)
    assert len(successes) == 2

    # Get failed commands
    failures = test_db.get_commands_by_exit_code(1)
    assert len(failures) == 1


def test_pattern_statistics(test_db):
    """Test pattern analysis and statistics."""
    # Log commands with patterns
    test_db.log_command("git commit -m 'message1'", "/home/user/project", 0, 0.2)
    test_db.log_command("git commit -m 'message2'", "/home/user/project", 0, 0.3)
    test_db.log_command("git commit -m 'message3'", "/home/user/project", 0, 0.2)

    # Update pattern statistics
    test_db.update_pattern_stats()

    # Get pattern stats
    cursor = test_db.conn.cursor()
    cursor.execute(
        "SELECT SUM(frequency), AVG(success_rate) FROM command_patterns WHERE command LIKE 'git commit%'"
    )
    row = cursor.fetchone()

    assert row is not None
    assert row[0] >= 3  # total frequency of all git commit patterns
    assert row[1] == 1.0  # average success_rate (all succeeded)


def test_invalid_command_data(test_db):
    """Test input validation and error handling."""
    # Test with None command (should handle gracefully)
    import sqlite3

    with pytest.raises((TypeError, ValueError, sqlite3.IntegrityError)):
        test_db.log_command(None, "/home/user", 0, 0.01)

    # Note: SQLite3 is flexible with types, so string exit codes may be accepted
    # depending on whether they can be coerced to integers


@pytest.mark.slow
@pytest.mark.performance
def test_large_dataset_performance(test_db):
    """Test performance with 10K+ commands."""
    start_time = time.time()

    # Insert 10,000 commands
    for i in range(10000):
        test_db.log_command(f"command_{i}", "/home/user", 0, 0.01)

    insert_time = time.time() - start_time

    # Should complete in reasonable time (<60 seconds)
    # Note: may be slower due to session management overhead
    assert insert_time < 60.0

    # Test query performance
    start_time = time.time()
    results = test_db.get_recent_commands(n=100)
    query_time = time.time() - start_time

    assert len(results) == 100
    # Query should be fast (<100ms)
    assert query_time < 0.1


def test_sqlite_timeout(test_db):
    """Test timeout handling for busy database."""
    # Database should have timeout set
    cursor = test_db.conn.cursor()
    cursor.execute("PRAGMA busy_timeout")
    timeout = cursor.fetchone()[0]

    # Should have reasonable timeout (>= 1 second)
    assert timeout >= 1000  # milliseconds


def test_vacuum_database(test_db):
    """Test database optimization."""
    # Log and delete commands to fragment database
    for i in range(100):
        test_db.log_command(f"command_{i}", "/home/user", 0, 0.01)

    cursor = test_db.conn.cursor()
    cursor.execute("DELETE FROM command_history WHERE command LIKE 'command_%'")
    test_db.conn.commit()

    # Get database size before vacuum
    cursor.execute("PRAGMA page_count")
    pages_before = cursor.fetchone()[0]

    # Vacuum database
    test_db.vacuum()

    # Database should be optimized
    cursor.execute("PRAGMA page_count")
    pages_after = cursor.fetchone()[0]

    # After vacuum, pages should be reduced or same
    assert pages_after <= pages_before


def test_wal_mode(test_db):
    """Test Write-Ahead Logging mode."""
    cursor = test_db.conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]

    # Should use WAL mode for better concurrency
    assert mode.upper() == "WAL"
