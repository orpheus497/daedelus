"""
Command Execution Module
=========================
Provides secure command execution with:
- Permission checking and validation
- Session memory tracking
- Output capture and logging
- Safety analysis integration
- Sandbox support for untrusted commands

Author: orpheus497
License: MIT
"""

import json
import logging
import os
import pty
import select
import signal
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .safety import SafetyAnalyzer, SafetyLevel

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes for commands"""
    DIRECT = "direct"  # Run directly in shell
    SANDBOXED = "sandboxed"  # Run in restricted environment
    DRY_RUN = "dry_run"  # Don't actually execute


class ExecutionStatus(Enum):
    """Status of command execution"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"
    DENIED = "denied"


@dataclass
class CommandResult:
    """Result of a command execution"""
    command: str
    status: ExecutionStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    timestamp: float = 0.0
    session_id: Optional[str] = None
    cwd: str = ""
    environment: Dict[str, str] = None
    user_approved: bool = False
    safety_level: Optional[SafetyLevel] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.environment is None:
            self.environment = {}


class CommandExecutionMemory:
    """
    Tracks command execution history for session memory and training data.
    Integrates with the existing command_history database.
    """

    def __init__(self, db_path: Path):
        """
        Initialize execution memory tracker.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize/extend database schema for execution tracking"""
        with sqlite3.connect(self.db_path) as conn:
            # Add execution tracking table (extends command_history)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS command_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    command TEXT NOT NULL,
                    status TEXT NOT NULL,
                    exit_code INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    duration REAL,
                    session_id TEXT,
                    cwd TEXT,
                    environment TEXT,
                    user_approved INTEGER DEFAULT 0,
                    safety_level TEXT,
                    error_message TEXT,
                    execution_mode TEXT
                )
            """)

            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_timestamp ON command_executions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_session ON command_executions(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_status ON command_executions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_command ON command_executions(command)")

            conn.commit()

    def log_execution(self, result: CommandResult, execution_mode: ExecutionMode):
        """
        Log a command execution.

        Args:
            result: Command execution result
            execution_mode: Mode used for execution
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO command_executions (
                    timestamp, command, status, exit_code, stdout, stderr,
                    duration, session_id, cwd, environment, user_approved,
                    safety_level, error_message, execution_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.timestamp,
                result.command,
                result.status.value,
                result.exit_code,
                result.stdout,
                result.stderr,
                result.duration,
                result.session_id,
                result.cwd,
                json.dumps(result.environment),
                1 if result.user_approved else 0,
                result.safety_level.value if result.safety_level else None,
                result.error_message,
                execution_mode.value
            ))
            conn.commit()

    def get_recent_executions(self, limit: int = 100, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent command executions.

        Args:
            limit: Maximum number of records
            session_id: Optional session filter

        Returns:
            List of execution records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if session_id:
                cursor = conn.execute("""
                    SELECT * FROM command_executions
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM command_executions
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            records = []
            for row in cursor.fetchall():
                record = dict(row)
                if record['environment']:
                    record['environment'] = json.loads(record['environment'])
                records.append(record)

            return records

    def get_command_history(self, command_pattern: str) -> List[Dict[str, Any]]:
        """
        Get execution history for commands matching a pattern.

        Args:
            command_pattern: SQL LIKE pattern

        Returns:
            List of matching executions
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM command_executions
                WHERE command LIKE ?
                ORDER BY timestamp DESC
            """, (command_pattern,))

            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total executions
            total = conn.execute("SELECT COUNT(*) FROM command_executions").fetchone()[0]

            # By status
            by_status = {}
            for row in conn.execute("SELECT status, COUNT(*) as count FROM command_executions GROUP BY status"):
                by_status[row[0]] = row[1]

            # Success rate
            completed = by_status.get('completed', 0)
            success_rate = (completed / total * 100) if total > 0 else 0

            # Average duration
            avg_duration = conn.execute("SELECT AVG(duration) FROM command_executions WHERE status = 'completed'").fetchone()[0] or 0

            # Most used commands
            most_used = []
            for row in conn.execute("""
                SELECT command, COUNT(*) as count
                FROM command_executions
                GROUP BY command
                ORDER BY count DESC
                LIMIT 10
            """):
                most_used.append({'command': row[0], 'count': row[1]})

            return {
                'total_executions': total,
                'executions_by_status': by_status,
                'success_rate': success_rate,
                'average_duration': avg_duration,
                'most_used_commands': most_used
            }


class CommandExecutor:
    """
    Main interface for command execution with safety and memory tracking.
    """

    def __init__(
        self,
        safety_analyzer: SafetyAnalyzer,
        memory_tracker: CommandExecutionMemory,
        session_id: Optional[str] = None,
        default_timeout: int = 300
    ):
        """
        Initialize command executor.

        Args:
            safety_analyzer: Safety analyzer instance
            memory_tracker: Memory tracker instance
            session_id: Optional session ID
            default_timeout: Default timeout in seconds
        """
        self.safety_analyzer = safety_analyzer
        self.memory_tracker = memory_tracker
        self.session_id = session_id or f"exec_{os.getpid()}_{int(datetime.now().timestamp())}"
        self.default_timeout = default_timeout

        # Track active processes
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.process_lock = threading.Lock()

    def _check_safety(self, command: str) -> Tuple[SafetyLevel, List[str]]:
        """
        Check command safety.

        Args:
            command: Command to check

        Returns:
            Tuple of (safety_level, warnings)
        """
        analysis = self.safety_analyzer.analyze_command(command)
        return analysis.safety_level, analysis.warnings

    def execute(
        self,
        command: str,
        mode: ExecutionMode = ExecutionMode.DIRECT,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = True,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> CommandResult:
        """
        Execute a command with safety checking and logging.

        Args:
            command: Command to execute
            mode: Execution mode
            timeout: Timeout in seconds (None = no timeout)
            cwd: Working directory
            env: Environment variables
            capture_output: If True, capture stdout/stderr
            stream_callback: Optional callback for streaming output

        Returns:
            CommandResult object
        """
        start_time = time.time()
        timestamp = datetime.now().timestamp()

        result = CommandResult(
            command=command,
            status=ExecutionStatus.PENDING,
            timestamp=timestamp,
            session_id=self.session_id,
            cwd=cwd or os.getcwd(),
            environment=env or {}
        )

        # Safety check
        safety_level, warnings = self._check_safety(command)
        result.safety_level = safety_level

        if safety_level == SafetyLevel.BLOCKED:
            logger.error(f"Command blocked by safety analyzer: {command}")
            result.status = ExecutionStatus.DENIED
            result.error_message = "Command blocked due to safety concerns: " + "; ".join(warnings)
            self.memory_tracker.log_execution(result, mode)
            return result

        if safety_level in [SafetyLevel.DANGEROUS, SafetyLevel.WARNING]:
            logger.warning(f"Command has safety warnings ({safety_level.value}): {command}")
            logger.warning(f"Warnings: {warnings}")
            # TODO: Implement user confirmation prompt
            result.user_approved = True  # Simulated approval

        # Dry run mode
        if mode == ExecutionMode.DRY_RUN:
            logger.info(f"Dry run (not executing): {command}")
            result.status = ExecutionStatus.COMPLETED
            result.stdout = "[DRY RUN - Command not executed]"
            result.duration = time.time() - start_time
            self.memory_tracker.log_execution(result, mode)
            return result

        # Sandboxed mode
        if mode == ExecutionMode.SANDBOXED:
            return self._execute_sandboxed(command, result, timeout, cwd, env, capture_output, stream_callback)

        # Direct execution
        return self._execute_direct(command, result, timeout, cwd, env, capture_output, stream_callback)

    def _execute_direct(
        self,
        command: str,
        result: CommandResult,
        timeout: Optional[int],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        capture_output: bool,
        stream_callback: Optional[Callable[[str], None]]
    ) -> CommandResult:
        """Execute command directly in shell"""
        try:
            result.status = ExecutionStatus.RUNNING
            start_time = time.time()

            # Prepare environment
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)

            # Execute command
            if stream_callback:
                # Use PTY for real-time streaming
                process = self._execute_with_pty(command, cwd, exec_env, stream_callback)
                exit_code = process.wait(timeout=timeout or self.default_timeout)
                stdout_data = ""
                stderr_data = ""
            else:
                # Use subprocess for captured output
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    cwd=cwd,
                    env=exec_env,
                    text=True
                )

                # Track process
                process_id = f"{self.session_id}_{id(process)}"
                with self.process_lock:
                    self.active_processes[process_id] = process

                try:
                    stdout_data, stderr_data = process.communicate(timeout=timeout or self.default_timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout_data, stderr_data = process.communicate()
                    result.status = ExecutionStatus.TIMEOUT
                    result.error_message = f"Command timed out after {timeout or self.default_timeout} seconds"
                    exit_code = -1
                finally:
                    with self.process_lock:
                        self.active_processes.pop(process_id, None)

            # Record results
            result.exit_code = exit_code
            result.stdout = stdout_data or ""
            result.stderr = stderr_data or ""
            result.duration = time.time() - start_time

            if result.status != ExecutionStatus.TIMEOUT:
                result.status = ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED

            logger.info(f"Command executed: {command} (exit={exit_code}, duration={result.duration:.2f}s)")

        except Exception as e:
            logger.error(f"Command execution failed: {command} - {e}")
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            result.duration = time.time() - start_time

        # Log execution
        self.memory_tracker.log_execution(result, ExecutionMode.DIRECT)
        return result

    def _execute_sandboxed(
        self,
        command: str,
        result: CommandResult,
        timeout: Optional[int],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        capture_output: bool,
        stream_callback: Optional[Callable[[str], None]]
    ) -> CommandResult:
        """
        Execute command in sandboxed environment.

        Uses firejail or similar sandboxing if available.
        """
        # Check for sandboxing tools
        sandbox_cmd = None

        if self._check_command_exists("firejail"):
            # Firejail sandbox with network isolation
            sandbox_cmd = [
                "firejail",
                "--noprofile",
                "--private-tmp",
                "--noroot",
                "--net=none",
                "--quiet",
                "--shell=none",
                "--",
                "sh", "-c", command
            ]
        elif self._check_command_exists("bwrap"):
            # Bubblewrap sandbox
            sandbox_cmd = [
                "bwrap",
                "--ro-bind", "/usr", "/usr",
                "--ro-bind", "/lib", "/lib",
                "--ro-bind", "/lib64", "/lib64",
                "--ro-bind", "/bin", "/bin",
                "--ro-bind", "/sbin", "/sbin",
                "--tmpfs", "/tmp",
                "--unshare-all",
                "--die-with-parent",
                "sh", "-c", command
            ]
        else:
            logger.warning("No sandboxing tool found (firejail, bwrap), falling back to direct execution")
            return self._execute_direct(command, result, timeout, cwd, env, capture_output, stream_callback)

        # Execute in sandbox
        try:
            result.status = ExecutionStatus.RUNNING
            start_time = time.time()

            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)

            process = subprocess.Popen(
                sandbox_cmd,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                cwd=cwd,
                env=exec_env,
                text=True
            )

            stdout_data, stderr_data = process.communicate(timeout=timeout or self.default_timeout)
            exit_code = process.returncode

            result.exit_code = exit_code
            result.stdout = stdout_data or ""
            result.stderr = stderr_data or ""
            result.duration = time.time() - start_time
            result.status = ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED

            logger.info(f"Sandboxed command executed: {command} (exit={exit_code}, duration={result.duration:.2f}s)")

        except subprocess.TimeoutExpired:
            process.kill()
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = f"Sandboxed command timed out after {timeout or self.default_timeout} seconds"
            result.duration = time.time() - start_time

        except Exception as e:
            logger.error(f"Sandboxed execution failed: {command} - {e}")
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            result.duration = time.time() - start_time

        # Log execution
        self.memory_tracker.log_execution(result, ExecutionMode.SANDBOXED)
        return result

    def _execute_with_pty(
        self,
        command: str,
        cwd: Optional[str],
        env: Dict[str, str],
        stream_callback: Callable[[str], None]
    ) -> subprocess.Popen:
        """
        Execute command with PTY for real-time output streaming.

        Args:
            command: Command to execute
            cwd: Working directory
            env: Environment variables
            stream_callback: Callback for output lines

        Returns:
            Process object
        """
        master, slave = pty.openpty()

        process = subprocess.Popen(
            command,
            shell=True,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=cwd,
            env=env,
            preexec_fn=os.setsid
        )

        os.close(slave)

        # Stream output
        def stream_output():
            while True:
                try:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        data = os.read(master, 1024).decode('utf-8', errors='replace')
                        if data:
                            stream_callback(data)
                        else:
                            break
                    if process.poll() is not None:
                        break
                except Exception as e:
                    logger.error(f"Error streaming output: {e}")
                    break

        stream_thread = threading.Thread(target=stream_output, daemon=True)
        stream_thread.start()

        return process

    def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        return subprocess.run(
            ["which", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ).returncode == 0

    def kill_process(self, process_id: str) -> bool:
        """
        Kill an active process.

        Args:
            process_id: Process ID to kill

        Returns:
            True if killed, False if not found
        """
        with self.process_lock:
            process = self.active_processes.get(process_id)
            if process:
                try:
                    process.kill()
                    logger.info(f"Killed process: {process_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to kill process {process_id}: {e}")
                    return False
            return False

    def get_active_processes(self) -> List[str]:
        """Get list of active process IDs"""
        with self.process_lock:
            return list(self.active_processes.keys())


class InteractiveShell:
    """
    Interactive shell session with persistent state and memory.
    """

    def __init__(
        self,
        executor: CommandExecutor,
        initial_cwd: Optional[str] = None,
        initial_env: Optional[Dict[str, str]] = None
    ):
        """
        Initialize interactive shell.

        Args:
            executor: Command executor instance
            initial_cwd: Initial working directory
            initial_env: Initial environment variables
        """
        self.executor = executor
        self.cwd = initial_cwd or os.getcwd()
        self.env = initial_env or os.environ.copy()
        self.history: List[CommandResult] = []
        self.variables: Dict[str, str] = {}

    def execute_command(self, command: str, **kwargs) -> CommandResult:
        """
        Execute command in shell context.

        Args:
            command: Command to execute
            **kwargs: Additional arguments for executor

        Returns:
            CommandResult
        """
        # Handle cd command specially to maintain state
        if command.strip().startswith('cd '):
            new_dir = command.strip()[3:].strip()
            try:
                new_path = Path(new_dir).resolve() if new_dir else Path.home()
                os.chdir(new_path)
                self.cwd = str(new_path)

                result = CommandResult(
                    command=command,
                    status=ExecutionStatus.COMPLETED,
                    exit_code=0,
                    stdout=f"Changed directory to {self.cwd}",
                    timestamp=datetime.now().timestamp(),
                    session_id=self.executor.session_id,
                    cwd=self.cwd
                )
                self.history.append(result)
                return result

            except Exception as e:
                result = CommandResult(
                    command=command,
                    status=ExecutionStatus.FAILED,
                    exit_code=1,
                    stderr=str(e),
                    timestamp=datetime.now().timestamp(),
                    session_id=self.executor.session_id,
                    cwd=self.cwd
                )
                self.history.append(result)
                return result

        # Execute command with current context
        result = self.executor.execute(
            command,
            cwd=self.cwd,
            env=self.env,
            **kwargs
        )

        self.history.append(result)
        return result

    def get_history(self, limit: Optional[int] = None) -> List[CommandResult]:
        """Get command history for this shell session"""
        if limit:
            return self.history[-limit:]
        return self.history
