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

    -- Natural language prompts and interpretations (for training data)
    CREATE TABLE IF NOT EXISTS nlp_prompts (
        id TEXT PRIMARY KEY,
        timestamp REAL NOT NULL,
        prompt_text TEXT NOT NULL,
        intent TEXT,
        intent_confidence REAL,
        generated_commands TEXT,
        selected_command TEXT,
        executed_command TEXT,
        exit_code INTEGER,
        feedback TEXT,
        cwd TEXT,
        session_id TEXT,
        embedding_vector TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_timestamp ON command_history(timestamp);
    CREATE INDEX IF NOT EXISTS idx_command ON command_history(command);
    CREATE INDEX IF NOT EXISTS idx_session ON command_history(session_id);
    CREATE INDEX IF NOT EXISTS idx_exit_code ON command_history(exit_code);
    CREATE INDEX IF NOT EXISTS idx_cwd ON command_history(cwd);
    CREATE INDEX IF NOT EXISTS idx_nlp_timestamp ON nlp_prompts(timestamp);
    CREATE INDEX IF NOT EXISTS idx_nlp_intent ON nlp_prompts(intent);
    CREATE INDEX IF NOT EXISTS idx_nlp_feedback ON nlp_prompts(feedback);

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

        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode = WAL")

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
        Get database statistics with optimized single-query aggregation.

        Returns:
            Dictionary of statistics

        Performance:
            Uses single aggregated query instead of 3 separate queries
            for 3x better performance on large databases.
        """
        # Optimized: Single query with aggregation instead of 3 separate queries
        cursor = self.conn.execute(
            """
            SELECT
                COUNT(*) as total_commands,
                SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) as successful_commands,
                (SELECT COUNT(*) FROM sessions) as total_sessions
            FROM command_history
        """
        )

        row = cursor.fetchone()
        total_commands = row[0]
        successful_commands = row[1]
        total_sessions = row[2]

        success_rate = (successful_commands / total_commands * 100) if total_commands > 0 else 0

        return {
            "total_commands": total_commands,
            "total_sessions": total_sessions,
            "successful_commands": successful_commands,
            "success_rate": success_rate,
            "database_size_bytes": self.db_path.stat().st_size,
        }

    def optimize_database(self) -> dict[str, Any]:
        """
        Optimize database by running VACUUM and ANALYZE.

        This reclaims unused space, defragments the database,
        and updates query optimizer statistics.

        Returns:
            Dictionary with optimization results

        Performance:
            Should be run periodically (weekly/monthly) for best performance.
            May take several seconds on large databases.
        """
        size_before = self.db_path.stat().st_size

        logger.info("Starting database optimization...")

        # VACUUM reclaims space and defragments
        self.conn.execute("VACUUM")

        # ANALYZE updates query optimizer statistics
        self.conn.execute("ANALYZE")

        # Commit and ensure changes are flushed
        self.conn.commit()

        size_after = self.db_path.stat().st_size
        size_saved = size_before - size_after
        size_saved_mb = size_saved / (1024 * 1024)

        logger.info(f"Database optimization complete. Saved {size_saved_mb:.2f} MB")

        return {
            "size_before_bytes": size_before,
            "size_after_bytes": size_after,
            "size_saved_bytes": size_saved,
            "size_saved_mb": size_saved_mb,
        }

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """
        Get all sessions from the database.

        Returns:
            List of session records with metadata
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM sessions
            ORDER BY start_time DESC
        """
        )
        return [dict(row) for row in cursor.fetchall()]

    def batch_insert_commands(self, commands: list[dict[str, Any]]) -> int:
        """
        Batch insert multiple commands for improved performance.

        Args:
            commands: List of command dictionaries with keys:
                     command, cwd, exit_code, session_id, duration, etc.

        Returns:
            Number of commands inserted

        Performance:
            Uses executemany() for 10-100x better performance than
            individual inserts when inserting large batches.
        """
        if not commands:
            return 0

        # Prepare data tuples
        data = []
        for cmd in commands:
            command_id = str(uuid.uuid4())
            timestamp = cmd.get("timestamp", datetime.now().timestamp())

            # Ensure session exists
            session_id = cmd["session_id"]
            self.ensure_session_exists(session_id, shell=cmd.get("shell"), cwd=cmd.get("cwd"))

            data.append(
                (
                    command_id,
                    timestamp,
                    cmd["command"],
                    cmd["cwd"],
                    cmd["exit_code"],
                    cmd.get("duration"),
                    cmd.get("output_length"),
                    session_id,
                    cmd.get("shell"),
                    cmd.get("user"),
                    cmd.get("hostname"),
                )
            )

        # Batch insert
        self.conn.executemany(
            """
            INSERT INTO command_history
            (id, timestamp, command, cwd, exit_code, duration, output_length,
             session_id, shell, user, hostname)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )

        self.conn.commit()
        logger.info(f"Batch inserted {len(data)} commands")

        return len(data)

    # ========================================
    # Test Compatibility Methods
    # ========================================

    def log_command(
        self,
        command: str,
        cwd: str,
        exit_code: int,
        duration: float | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Compatibility wrapper for insert_command().
        Auto-creates session if not provided.
        """
        if session_id is None:
            # Get or create current session
            cursor = self.conn.execute(
                "SELECT id FROM sessions WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                session_id = row[0]
            else:
                session_id = self.create_session()

        return self.insert_command(
            command=command,
            cwd=cwd,
            exit_code=exit_code,
            session_id=session_id,
            duration=duration,
            **kwargs,
        )

    def cleanup_old_commands(self, days: int = 90) -> int:
        """Alias for cleanup_old_data()."""
        return self.cleanup_old_data(retention_days=days)

    def get_commands_by_prefix(self, prefix: str, n: int = 100) -> list[dict[str, Any]]:
        """Get commands starting with given prefix."""
        cursor = self.conn.execute(
            """
            SELECT * FROM command_history
            WHERE command LIKE ? || '%'
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (prefix, n),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_commands_by_cwd(self, cwd: str, n: int = 100) -> list[dict[str, Any]]:
        """Get commands from a specific directory."""
        cursor = self.conn.execute(
            """
            SELECT * FROM command_history
            WHERE cwd = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (cwd, n),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_commands_by_exit_code(self, exit_code: int, n: int = 100) -> list[dict[str, Any]]:
        """Get commands with specific exit code."""
        cursor = self.conn.execute(
            """
            SELECT * FROM command_history
            WHERE exit_code = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (exit_code, n),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_command_stats(self, command: str) -> dict[str, Any] | None:
        """Get statistics for a specific command."""
        cursor = self.conn.execute(
            """
            SELECT
                COUNT(*) as count,
                AVG(CASE WHEN exit_code = 0 THEN 1.0 ELSE 0.0 END) as success_rate,
                AVG(duration) as avg_duration
            FROM command_history
            WHERE command = ?
            """,
            (command,),
        )
        row = cursor.fetchone()
        if row and row[0] > 0:
            return {
                "count": row[0],
                "success_rate": row[1],
                "avg_duration": row[2],
            }
        return None

    def get_command_sequences(self, min_length: int = 2, n: int = 100) -> list[list[str]]:
        """Get command sequences from session history."""
        cursor = self.conn.execute(
            """
            SELECT command FROM command_history
            WHERE session_id IN (
                SELECT DISTINCT session_id FROM command_history
            )
            ORDER BY session_id, timestamp
            """
        )

        # Group commands by session
        current_sequence = []
        sequences = []

        for row in cursor.fetchall():
            current_sequence.append(row[0])
            if len(current_sequence) >= min_length:
                sequences.append(current_sequence[-min_length:])

        return sequences[:n]

    def update_pattern_stats(self) -> None:
        """Analyze all commands and update pattern statistics."""
        # Get all commands and update patterns based on them
        cursor = self.conn.execute(
            """
            SELECT command, cwd as context, exit_code, duration
            FROM command_history
            """
        )
        for row in cursor.fetchall():
            self.update_pattern_statistics(
                context=row[1],  # cwd
                command=row[0],  # command
                success=(row[2] == 0),  # exit_code == 0
                duration=row[3],  # duration
            )

    def vacuum(self) -> None:
        """Alias for optimize_database()."""
        self.optimize_database()

    def get_most_used_commands(self, limit: int = 20) -> list[tuple[str, int]]:
        """
        Get most frequently used commands.

        Args:
            limit: Maximum number of commands to return

        Returns:
            List of (command, count) tuples ordered by frequency
        """
        cursor = self.conn.execute(
            """
            SELECT command, COUNT(*) as count
            FROM command_history
            GROUP BY command
            ORDER BY count DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_analytics_data(self) -> dict[str, Any]:
        """
        Get comprehensive analytics data for dashboard.

        Returns:
            Dictionary with analytics metrics
        """
        # Get basic stats
        stats = self.get_statistics()

        # Get most used commands
        most_used = self.get_most_used_commands(limit=10)

        # Get unique command count
        cursor = self.conn.execute("SELECT COUNT(DISTINCT command) FROM command_history")
        unique_commands = cursor.fetchone()[0]

        return {
            "total_commands": stats["total_commands"],
            "unique_commands": unique_commands,
            "successful_commands": stats["successful_commands"],
            "success_rate": stats["success_rate"],
            "most_used_commands": most_used,
            "total_sessions": stats["total_sessions"],
        }

    def backup(self, backup_path: Path) -> None:
        """Create a backup of the database."""
        import shutil

        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        # Close connection, copy file, reopen
        self.conn.close()
        shutil.copy2(self.db_path, backup_path)
        # Reopen connection
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        logger.info(f"Database backed up to {backup_path}")

    # ========================================
    # NLP Prompts & Training Data
    # ========================================

    def insert_nlp_prompt(
        self,
        prompt_text: str,
        intent: str | None = None,
        intent_confidence: float | None = None,
        generated_commands: list[str] | None = None,
        selected_command: str | None = None,
        cwd: str | None = None,
        session_id: str | None = None,
        embedding_vector: list[float] | None = None,
    ) -> str:
        """
        Insert a natural language prompt for training data collection.

        Args:
            prompt_text: The user's natural language prompt
            intent: Classified intent type
            intent_confidence: Confidence score for intent classification
            generated_commands: List of commands generated from the prompt
            selected_command: Command selected by user (if any)
            cwd: Current working directory
            session_id: Session ID
            embedding_vector: Optional embedding vector for the prompt

        Returns:
            Prompt ID
        """
        prompt_id = str(uuid.uuid4())
        timestamp = datetime.now().timestamp()

        # Serialize commands list to JSON string
        import json
        commands_json = json.dumps(generated_commands) if generated_commands else None
        embedding_json = json.dumps(embedding_vector) if embedding_vector else None

        self.conn.execute(
            """
            INSERT INTO nlp_prompts (
                id, timestamp, prompt_text, intent, intent_confidence,
                generated_commands, selected_command, cwd, session_id, embedding_vector
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                timestamp,
                prompt_text,
                intent,
                intent_confidence,
                commands_json,
                selected_command,
                cwd,
                session_id,
                embedding_json,
            ),
        )
        self.conn.commit()

        logger.debug(f"Inserted NLP prompt: {prompt_id}")
        return prompt_id

    def update_nlp_prompt_feedback(
        self,
        prompt_id: str,
        executed_command: str | None = None,
        exit_code: int | None = None,
        feedback: str | None = None,
    ) -> None:
        """
        Update feedback for an NLP prompt after execution.

        Args:
            prompt_id: Prompt ID
            executed_command: The actual command that was executed
            exit_code: Exit code of executed command
            feedback: User feedback ("accepted", "rejected", "modified")
        """
        self.conn.execute(
            """
            UPDATE nlp_prompts
            SET executed_command = ?,
                exit_code = ?,
                feedback = ?
            WHERE id = ?
            """,
            (executed_command, exit_code, feedback, prompt_id),
        )
        self.conn.commit()

        logger.debug(f"Updated NLP prompt feedback: {prompt_id}")

    def get_nlp_prompts(
        self,
        limit: int = 100,
        feedback_filter: str | None = None,
        intent_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get NLP prompts for training data analysis.

        Args:
            limit: Maximum number of prompts to return
            feedback_filter: Filter by feedback type ("accepted", "rejected", "pending", etc.)
            intent_filter: Filter by intent type

        Returns:
            List of prompt records
        """
        import json

        query = "SELECT * FROM nlp_prompts WHERE 1=1"
        params = []

        if feedback_filter:
            if feedback_filter == "pending":
                query += " AND (feedback IS NULL OR feedback = '')"
            else:
                query += " AND feedback = ?"
                params.append(feedback_filter)

        if intent_filter:
            query += " AND intent = ?"
            params.append(intent_filter)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, tuple(params))
        prompts = []

        for row in cursor.fetchall():
            prompt = dict(row)
            # Parse JSON fields
            if prompt.get("generated_commands"):
                try:
                    prompt["commands"] = json.loads(prompt["generated_commands"])
                except json.JSONDecodeError:
                    prompt["commands"] = []
            else:
                prompt["commands"] = []

            if prompt.get("embedding_vector"):
                try:
                    prompt["embedding"] = json.loads(prompt["embedding_vector"])
                except json.JSONDecodeError:
                    prompt["embedding"] = None
            else:
                prompt["embedding"] = None

            # Set feedback to "pending" if None
            if not prompt.get("feedback"):
                prompt["feedback"] = "pending"

            # Add confidence field for consistency
            prompt["confidence"] = prompt.get("intent_confidence", 0.0)

            # Add text field for consistency
            prompt["text"] = prompt.get("prompt_text", "")

            prompts.append(prompt)

        return prompts

    def get_nlp_training_data(
        self, min_confidence: float = 0.5, only_accepted: bool = True
    ) -> list[dict[str, Any]]:
        """
        Get high-quality training data from NLP prompts.

        Args:
            min_confidence: Minimum confidence threshold
            only_accepted: Only return accepted prompts

        Returns:
            List of training examples
        """
        import json

        query = """
            SELECT * FROM nlp_prompts
            WHERE intent_confidence >= ?
        """
        params = [min_confidence]

        if only_accepted:
            query += " AND feedback = 'accepted'"

        query += " ORDER BY timestamp DESC"

        cursor = self.conn.execute(query, tuple(params))
        training_data = []

        for row in cursor.fetchall():
            example = dict(row)
            # Parse JSON fields
            if example.get("generated_commands"):
                try:
                    example["commands"] = json.loads(example["generated_commands"])
                except json.JSONDecodeError:
                    example["commands"] = []

            training_data.append(example)

        logger.info(f"Retrieved {len(training_data)} training examples")
        return training_data

    def export_training_data(self, output_path: Path) -> int:
        """
        Export all training data to JSON file.

        Args:
            output_path: Path to output JSON file

        Returns:
            Number of examples exported
        """
        import json

        training_data = self.get_nlp_training_data(min_confidence=0.0, only_accepted=False)

        with open(output_path, "w") as f:
            json.dump(training_data, f, indent=2)

        logger.info(f"Exported {len(training_data)} training examples to {output_path}")
        return len(training_data)

    def clear_nlp_prompts(self, older_than_days: int | None = None) -> int:
        """
        Clear NLP prompt history.

        Args:
            older_than_days: Only clear prompts older than N days (None = all)

        Returns:
            Number of prompts deleted
        """
        if older_than_days:
            cutoff = datetime.now().timestamp() - (older_than_days * 86400)
            cursor = self.conn.execute(
                "DELETE FROM nlp_prompts WHERE timestamp < ?", (cutoff,)
            )
        else:
            cursor = self.conn.execute("DELETE FROM nlp_prompts")

        deleted = cursor.rowcount
        self.conn.commit()

        logger.info(f"Deleted {deleted} NLP prompts")
        return deleted

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
