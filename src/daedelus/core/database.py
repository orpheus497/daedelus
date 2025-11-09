"""
SQLite database management for Daedalus command history.

Provides:
- Command history storage with full metadata
- FTS5 full-text search
- Session tracking
- Pattern statistics
- Efficient queries with proper indexing

Created by: orpheus497
"""

import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CommandDatabase:
    """
    SQLite database for storing and querying command history.

    Features:
    - Full command metadata (timestamp, duration, exit code, etc.)
    - FTS5 full-text search for command content
    - Session tracking and context
    - Statistics and pattern tracking
    - Automatic cleanup and retention policies

    Attributes:
        db_path: Path to the SQLite database file
        conn: SQLite connection object
    """

    # Database schema
    SCHEMA = """
    -- Main command history table
    CREATE TABLE IF NOT EXISTS command_history (
        id TEXT PRIMARY KEY,
        timestamp REAL NOT NULL,
        command TEXT NOT NULL,
        cwd TEXT NOT NULL,
        exit_code INTEGER NOT NULL,
        duration REAL,
        output_length INTEGER,
        session_id TEXT NOT NULL,
        shell TEXT,
        user TEXT,
        hostname TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    );

    -- Sessions table
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        start_time REAL NOT NULL,
        end_time REAL,
        shell TEXT,
        cwd TEXT,
        total_commands INTEGER DEFAULT 0
    );

    -- Pattern statistics
    CREATE TABLE IF NOT EXISTS command_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        context TEXT NOT NULL,
        command TEXT NOT NULL,
        frequency INTEGER DEFAULT 1,
        success_rate REAL DEFAULT 1.0,
        last_used REAL NOT NULL,
        avg_duration REAL,
        UNIQUE(context, command)
    );

    -- Command sequences (for pattern recognition)
    CREATE TABLE IF NOT EXISTS command_sequences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sequence TEXT NOT NULL,
        frequency INTEGER DEFAULT 1,
        last_used REAL NOT NULL,
        UNIQUE(sequence)
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_timestamp ON command_history(timestamp);
    CREATE INDEX IF NOT EXISTS idx_command ON command_history(command);
    CREATE INDEX IF NOT EXISTS idx_session ON command_history(session_id);
    CREATE INDEX IF NOT EXISTS idx_exit_code ON command_history(exit_code);
    CREATE INDEX IF NOT EXISTS idx_cwd ON command_history(cwd);

    -- FTS5 virtual table for full-text search
    CREATE VIRTUAL TABLE IF NOT EXISTS command_fts USING fts5(
        command,
        cwd,
        content='command_history',
        content_rowid='rowid'
    );

    -- Triggers to keep FTS in sync
    CREATE TRIGGER IF NOT EXISTS command_ai AFTER INSERT ON command_history BEGIN
        INSERT INTO command_fts(rowid, command, cwd)
        VALUES (new.rowid, new.command, new.cwd);
    END;

    CREATE TRIGGER IF NOT EXISTS command_ad AFTER DELETE ON command_history BEGIN
        DELETE FROM command_fts WHERE rowid = old.rowid;
    END;

    CREATE TRIGGER IF NOT EXISTS command_au AFTER UPDATE ON command_history BEGIN
        UPDATE command_fts SET command = new.command, cwd = new.cwd
        WHERE rowid = new.rowid;
    END;
    """

    def __init__(self, db_path: Path) -> None:
        """
        Initialize database connection and schema.

        Args:
            db_path: Path to SQLite database file

        Raises:
            sqlite3.Error: If database initialization fails
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Allow multi-threaded access
            timeout=30.0,  # 30 second timeout for busy database
        )
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries

        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Initialize schema
        self._init_schema()

        logger.info(f"Database initialized at {self.db_path}")

    def _init_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        try:
            self.conn.executescript(self.SCHEMA)
            self.conn.commit()
            logger.debug("Database schema initialized")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise

    def create_session(
        self,
        shell: str | None = None,
        cwd: str | None = None,
    ) -> str:
        """
        Create a new session.

        Args:
            shell: Shell type (bash, zsh, fish)
            cwd: Current working directory

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO sessions (id, start_time, shell, cwd)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, datetime.now().timestamp(), shell, cwd),
        )
        self.conn.commit()

        logger.debug(f"Created session {session_id}")
        return session_id

    def end_session(self, session_id: str) -> None:
        """
        Mark a session as ended.

        Args:
            session_id: Session ID to end
        """
        self.conn.execute(
            """
            UPDATE sessions
            SET end_time = ?
            WHERE id = ?
            """,
            (datetime.now().timestamp(), session_id),
        )
        self.conn.commit()

        logger.debug(f"Ended session {session_id}")

    def ensure_session_exists(
        self,
        session_id: str,
        shell: str | None = None,
        cwd: str | None = None,
    ) -> None:
        """
        Ensure a session exists in the database, creating it if necessary.

        This is useful when external clients (shell integrations) send commands
        with their own session IDs.

        Args:
            session_id: Session ID to check/create
            shell: Shell type (bash, zsh, fish)
            cwd: Current working directory
        """
        cursor = self.conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        )

        if cursor.fetchone() is None:
            # Session doesn't exist, create it
            self.conn.execute(
                """
                INSERT INTO sessions (id, start_time, shell, cwd)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, datetime.now().timestamp(), shell, cwd),
            )
            self.conn.commit()
            logger.debug(f"Auto-created session {session_id}")

    def insert_command(
        self,
        command: str,
        cwd: str,
        exit_code: int,
        session_id: str,
        duration: float | None = None,
        output_length: int | None = None,
        shell: str | None = None,
        user: str | None = None,
        hostname: str | None = None,
    ) -> str:
        """
        Insert a command execution record.

        Args:
            command: Command string
            cwd: Current working directory
            exit_code: Exit code (0 = success)
            session_id: Session ID
            duration: Execution duration in seconds
            output_length: Length of command output
            shell: Shell type
            user: Username
            hostname: Hostname

        Returns:
            Command ID
        """
        # Ensure session exists before inserting command (auto-create if needed)
        self.ensure_session_exists(session_id, shell=shell, cwd=cwd)

        command_id = str(uuid.uuid4())

        self.conn.execute(
            """
            INSERT INTO command_history
            (id, timestamp, command, cwd, exit_code, duration, output_length,
             session_id, shell, user, hostname)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command_id,
                datetime.now().timestamp(),
                command,
                cwd,
                exit_code,
                duration,
                output_length,
                session_id,
                shell,
                user,
                hostname,
            ),
        )

        # Update session command count
        self.conn.execute(
            """
            UPDATE sessions
            SET total_commands = total_commands + 1
            WHERE id = ?
            """,
            (session_id,),
        )

        self.conn.commit()

        logger.debug(f"Inserted command: {command[:50]}... (exit: {exit_code})")
        return command_id

    def get_recent_commands(
        self, n: int = 100, successful_only: bool = False
    ) -> list[dict[str, Any]]:
        """
        Get recent commands.

        Args:
            n: Number of commands to retrieve
            successful_only: If True, only return commands with exit_code=0

        Returns:
            List of command records
        """
        query = """
            SELECT * FROM command_history
            {}
            ORDER BY timestamp DESC
            LIMIT ?
        """.format(
            "WHERE exit_code = 0" if successful_only else ""
        )

        cursor = self.conn.execute(query, (n,))
        return [dict(row) for row in cursor.fetchall()]

    def search_commands(
        self,
        query: str,
        limit: int = 20,
        cwd_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search commands using FTS5 full-text search.

        Args:
            query: Search query (FTS5 syntax supported)
            limit: Maximum number of results
            cwd_filter: Optional filter by directory

        Returns:
            List of matching command records
        """
        if cwd_filter:
            sql = """
                SELECT c.* FROM command_history c
                JOIN command_fts fts ON c.rowid = fts.rowid
                WHERE command_fts MATCH ?
                  AND c.cwd LIKE ?
                ORDER BY c.timestamp DESC
                LIMIT ?
            """
            cursor = self.conn.execute(sql, (query, f"{cwd_filter}%", limit))
        else:
            sql = """
                SELECT c.* FROM command_history c
                JOIN command_fts fts ON c.rowid = fts.rowid
                WHERE command_fts MATCH ?
                ORDER BY c.timestamp DESC
                LIMIT ?
            """
            cursor = self.conn.execute(sql, (query, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_session_commands(self, session_id: str) -> list[dict[str, Any]]:
        """
        Get all commands from a specific session.

        Args:
            session_id: Session ID

        Returns:
            List of command records
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM command_history
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_command_context(
        self,
        command_id: str,
        window: int = 5,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        """
        Get command with surrounding context.

        Args:
            command_id: Command ID
            window: Number of commands before/after to include

        Returns:
            Tuple of (commands_before, target_command, commands_after)
        """
        # Get target command
        cursor = self.conn.execute(
            "SELECT * FROM command_history WHERE id = ?",
            (command_id,),
        )
        target = cursor.fetchone()
        if not target:
            return ([], {}, [])

        target_dict = dict(target)
        timestamp = target_dict["timestamp"]
        session_id = target_dict["session_id"]

        # Get commands before
        cursor = self.conn.execute(
            """
            SELECT * FROM command_history
            WHERE session_id = ? AND timestamp < ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, timestamp, window),
        )
        before = [dict(row) for row in cursor.fetchall()]
        before.reverse()  # Oldest first

        # Get commands after
        cursor = self.conn.execute(
            """
            SELECT * FROM command_history
            WHERE session_id = ? AND timestamp > ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (session_id, timestamp, window),
        )
        after = [dict(row) for row in cursor.fetchall()]

        return (before, target_dict, after)

    def update_pattern_statistics(
        self,
        context: str,
        command: str,
        success: bool,
        duration: float | None = None,
    ) -> None:
        """
        Update pattern statistics for learning.

        Args:
            context: Context identifier (e.g., directory or previous command)
            command: Command that was executed
            success: Whether command succeeded
            duration: Command duration
        """
        timestamp = datetime.now().timestamp()

        # Check if pattern exists
        cursor = self.conn.execute(
            "SELECT * FROM command_patterns WHERE context = ? AND command = ?",
            (context, command),
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing pattern
            old_freq = existing["frequency"]
            old_success_rate = existing["success_rate"]

            new_freq = old_freq + 1
            new_success_rate = (old_success_rate * old_freq + (1 if success else 0)) / new_freq

            self.conn.execute(
                """
                UPDATE command_patterns
                SET frequency = ?,
                    success_rate = ?,
                    last_used = ?,
                    avg_duration = ?
                WHERE context = ? AND command = ?
                """,
                (new_freq, new_success_rate, timestamp, duration, context, command),
            )
        else:
            # Insert new pattern
            self.conn.execute(
                """
                INSERT INTO command_patterns
                (context, command, frequency, success_rate, last_used, avg_duration)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (context, command, 1.0 if success else 0.0, timestamp, duration),
            )

        self.conn.commit()

    def cleanup_old_data(self, retention_days: int = 90) -> int:
        """
        Remove commands older than retention period.

        Args:
            retention_days: Number of days to keep

        Returns:
            Number of commands deleted
        """
        cutoff = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff.timestamp()

        cursor = self.conn.execute(
            "DELETE FROM command_history WHERE timestamp < ?",
            (cutoff_timestamp,),
        )
        deleted = cursor.rowcount
        self.conn.commit()

        logger.info(f"Cleaned up {deleted} old commands")
        return deleted

    def get_statistics(self) -> dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary of statistics
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM command_history")
        total_commands = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM command_history WHERE exit_code = 0")
        successful_commands = cursor.fetchone()[0]

        success_rate = (successful_commands / total_commands * 100) if total_commands > 0 else 0

        return {
            "total_commands": total_commands,
            "total_sessions": total_sessions,
            "successful_commands": successful_commands,
            "success_rate": success_rate,
            "database_size_bytes": self.db_path.stat().st_size,
        }

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self) -> "CommandDatabase":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        """String representation."""
        return f"CommandDatabase(db_path={self.db_path})"
