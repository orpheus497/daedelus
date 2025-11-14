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
import resource
import select
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .safety import SafetyAnalyzer, SafetyLevel, SafetyReport
from .subprocess_validator import SubprocessValidator

logger = logging.getLogger(__name__)


class ProcessTreeNode:
    """Represents a process and its children in the process tree."""

    def __init__(self, pid: int, pgid: int, parent_pid: int | None = None):
        self.pid = pid
        self.pgid = pgid
        self.parent_pid = parent_pid
        self.children: list[ProcessTreeNode] = []
        self.start_time = time.time()
        self.cpu_usage = 0.0
        self.memory_usage = 0  # bytes

    def add_child(self, child: "ProcessTreeNode") -> None:
        """Add a child process node."""
        self.children.append(child)

    def get_all_pids(self) -> list[int]:
        """Get all PIDs in this subtree."""
        pids = [self.pid]
        for child in self.children:
            pids.extend(child.get_all_pids())
        return pids

    def update_resource_usage(self) -> None:
        """Update CPU and memory usage from /proc."""
        try:
            # Read CPU usage from /proc/[pid]/stat
            with open(f"/proc/{self.pid}/stat") as f:
                stat_data = f.read().split()
                # Fields 13-16 are CPU time
                utime = int(stat_data[13])  # User mode time
                stime = int(stat_data[14])  # Kernel mode time
                self.cpu_usage = (utime + stime) / os.sysconf(os.sysconf_names["SC_CLK_TCK"])

            # Read memory usage from /proc/[pid]/status
            with open(f"/proc/{self.pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        # Resident Set Size in KB
                        self.memory_usage = int(line.split()[1]) * 1024
                        break
        except (OSError, FileNotFoundError, IndexError):
            # Process may have terminated
            pass


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
class ResourceUsage:
    """Resource usage statistics for a command."""

    cpu_time: float = 0.0  # Total CPU time in seconds
    max_memory: int = 0  # Peak memory usage in bytes
    child_processes: int = 0  # Number of child processes spawned

    def __str__(self) -> str:
        """Human-readable resource usage."""
        mem_mb = self.max_memory / (1024 * 1024)
        return f"CPU: {self.cpu_time:.2f}s, Mem: {mem_mb:.1f}MB, Children: {self.child_processes}"


@dataclass
class CommandResult:
    """Result of a command execution"""

    command: str
    status: ExecutionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    timestamp: float = 0.0
    session_id: str | None = None
    cwd: str = ""
    environment: dict[str, str] = None
    user_approved: bool = False
    safety_level: SafetyLevel | None = None
    error_message: str | None = None
    resource_usage: ResourceUsage | None = None
    process_tree_size: int = 0  # Number of processes in tree

    def __post_init__(self):
        if self.environment is None:
            self.environment = {}
        if self.resource_usage is None:
            self.resource_usage = ResourceUsage()


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
            conn.execute(
                """
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
            """
            )

            # Indexes
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_timestamp ON command_executions(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_session ON command_executions(session_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_status ON command_executions(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_command ON command_executions(command)"
            )

            conn.commit()

    def log_execution(self, result: CommandResult, execution_mode: ExecutionMode):
        """
        Log a command execution.

        Args:
            result: Command execution result
            execution_mode: Mode used for execution
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO command_executions (
                    timestamp, command, status, exit_code, stdout, stderr,
                    duration, session_id, cwd, environment, user_approved,
                    safety_level, error_message, execution_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
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
                    execution_mode.value,
                ),
            )
            conn.commit()

    def get_recent_executions(
        self, limit: int = 100, session_id: str | None = None
    ) -> list[dict[str, Any]]:
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
                cursor = conn.execute(
                    """
                    SELECT * FROM command_executions
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (session_id, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM command_executions
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (limit,),
                )

            records = []
            for row in cursor.fetchall():
                record = dict(row)
                if record["environment"]:
                    record["environment"] = json.loads(record["environment"])
                records.append(record)

            return records

    def get_command_history(self, command_pattern: str) -> list[dict[str, Any]]:
        """
        Get execution history for commands matching a pattern.

        Args:
            command_pattern: SQL LIKE pattern

        Returns:
            List of matching executions
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM command_executions
                WHERE command LIKE ?
                ORDER BY timestamp DESC
            """,
                (command_pattern,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> dict[str, Any]:
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
            for row in conn.execute(
                "SELECT status, COUNT(*) as count FROM command_executions GROUP BY status"
            ):
                by_status[row[0]] = row[1]

            # Success rate
            completed = by_status.get("completed", 0)
            success_rate = (completed / total * 100) if total > 0 else 0

            # Average duration
            avg_duration = (
                conn.execute(
                    "SELECT AVG(duration) FROM command_executions WHERE status = 'completed'"
                ).fetchone()[0]
                or 0
            )

            # Most used commands
            most_used = []
            for row in conn.execute(
                """
                SELECT command, COUNT(*) as count
                FROM command_executions
                GROUP BY command
                ORDER BY count DESC
                LIMIT 10
            """
            ):
                most_used.append({"command": row[0], "count": row[1]})

            return {
                "total_executions": total,
                "executions_by_status": by_status,
                "success_rate": success_rate,
                "average_duration": avg_duration,
                "most_used_commands": most_used,
            }


class CommandExecutor:
    """
    Main interface for command execution with safety and memory tracking.

    Enhanced with:
    - Process tree tracking and management
    - Resource limits (CPU, memory, file descriptors)
    - Process group cleanup
    - Resource usage monitoring
    """

    def __init__(
        self,
        safety_analyzer: SafetyAnalyzer,
        memory_tracker: CommandExecutionMemory,
        session_id: str | None = None,
        default_timeout: int = 300,
        max_memory_mb: int | None = None,
        max_cpu_time: int | None = None,
        max_file_descriptors: int | None = None,
    ):
        """
        Initialize command executor.

        Args:
            safety_analyzer: Safety analyzer instance
            memory_tracker: Memory tracker instance
            session_id: Optional session ID
            default_timeout: Default timeout in seconds
            max_memory_mb: Maximum memory in MB (None = no limit)
            max_cpu_time: Maximum CPU time in seconds (None = no limit)
            max_file_descriptors: Maximum file descriptors (None = no limit)
        """
        self.safety_analyzer = safety_analyzer
        self.memory_tracker = memory_tracker
        self.session_id = session_id or f"exec_{os.getpid()}_{int(datetime.now().timestamp())}"
        self.default_timeout = default_timeout

        # Resource limits
        self.max_memory_mb = max_memory_mb
        self.max_cpu_time = max_cpu_time
        self.max_file_descriptors = max_file_descriptors

        # Track active processes with process trees
        self.active_processes: dict[str, subprocess.Popen] = {}
        self.process_trees: dict[str, ProcessTreeNode] = {}
        self.process_lock = threading.Lock()
        # Validate subprocess commands before execution
        self.subproc_validator = SubprocessValidator(allow_shell=True, strict_mode=True)

    def _set_resource_limits(self) -> None:
        """
        Set resource limits for child process (called in preexec_fn).

        Uses ulimit to constrain CPU, memory, and file descriptors.
        """
        if self.max_cpu_time:
            # CPU time limit in seconds
            resource.setrlimit(resource.RLIMIT_CPU, (self.max_cpu_time, self.max_cpu_time))

        if self.max_memory_mb:
            # Memory limit in bytes
            max_memory_bytes = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))

        if self.max_file_descriptors:
            # File descriptor limit
            resource.setrlimit(
                resource.RLIMIT_NOFILE, (self.max_file_descriptors, self.max_file_descriptors)
            )

        # Create new process group for easier cleanup
        os.setpgrp()

    def _build_process_tree(self, root_pid: int) -> ProcessTreeNode:
        """
        Build process tree from /proc filesystem.

        Args:
            root_pid: Root process PID

        Returns:
            ProcessTreeNode representing the tree
        """
        try:
            # Get process group ID
            pgid = os.getpgid(root_pid)
            root = ProcessTreeNode(root_pid, pgid)

            # Recursively find children
            self._find_children(root)

            return root
        except (ProcessLookupError, PermissionError):
            # Process may have terminated
            return ProcessTreeNode(root_pid, root_pid)

    def _find_children(self, node: ProcessTreeNode) -> None:
        """
        Recursively find child processes using /proc.

        Args:
            node: Parent node to populate with children
        """
        try:
            # Scan /proc for child processes
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue

                try:
                    pid = int(entry)
                    with open(f"/proc/{pid}/stat") as f:
                        stat_data = f.read()
                        # Extract parent PID (4th field)
                        parent_pid = int(stat_data.split(")")[1].split()[1])

                        if parent_pid == node.pid:
                            # Found a child
                            pgid = os.getpgid(pid)
                            child = ProcessTreeNode(pid, pgid, node.pid)
                            child.update_resource_usage()
                            node.add_child(child)
                            # Recursively find grandchildren
                            self._find_children(child)
                except (FileNotFoundError, ValueError, IndexError, PermissionError):
                    continue
        except OSError:
            pass

    def _kill_process_tree(self, process_id: str) -> int:
        """
        Kill entire process tree (parent and all children).

        Args:
            process_id: Process ID to kill

        Returns:
            Number of processes killed
        """
        killed_count = 0

        with self.process_lock:
            process = self.active_processes.get(process_id)
            if not process:
                return 0

            try:
                # Build current process tree
                tree = self._build_process_tree(process.pid)
                all_pids = tree.get_all_pids()

                logger.info(f"Killing process tree for {process_id}: {len(all_pids)} processes")

                # Kill all processes in tree
                for pid in all_pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                        killed_count += 1
                        logger.debug(f"Killed PID {pid}")
                    except ProcessLookupError:
                        # Already dead
                        pass
                    except PermissionError:
                        logger.warning(f"Permission denied killing PID {pid}")

                # Also try to kill the entire process group
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                    logger.debug(f"Killed process group {pgid}")
                except (ProcessLookupError, PermissionError):
                    pass

            except Exception as e:
                logger.error(f"Error killing process tree: {e}")

            finally:
                # Clean up tracking
                self.active_processes.pop(process_id, None)
                self.process_trees.pop(process_id, None)

        return killed_count

    def _monitor_resources(self, process_id: str, interval: float = 1.0) -> None:
        """
        Monitor process tree resource usage in background thread.

        Args:
            process_id: Process ID to monitor
            interval: Check interval in seconds
        """
        while True:
            with self.process_lock:
                process = self.active_processes.get(process_id)
                if not process:
                    break

                # Check if process still running
                if process.poll() is not None:
                    break

                try:
                    # Build and update process tree
                    tree = self._build_process_tree(process.pid)
                    tree.update_resource_usage()
                    self.process_trees[process_id] = tree

                    # Update resource usage for all children
                    for child in tree.children:
                        child.update_resource_usage()

                except Exception as e:
                    logger.debug(f"Error monitoring resources: {e}")
                    break

            time.sleep(interval)

    def _check_safety(self, command: str) -> SafetyReport:
        """
        Check command safety.

        Args:
            command: Command to check

        Returns:
            SafetyReport object containing safety analysis
        """
        # Use analyze() to get full safety report
        report = self.safety_analyzer.analyze(command)
        return report

    def execute(
        self,
        command: str,
        mode: ExecutionMode = ExecutionMode.DIRECT,
        timeout: int | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        stream_callback: Callable[[str], None] | None = None,
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
            environment=env or {},
        )

        # Safety check
        safety_report = self._check_safety(command)
        result.safety_level = safety_report.level

        if safety_report.level == SafetyLevel.BLOCKED:
            logger.error(f"Command blocked by safety analyzer: {command}")
            result.status = ExecutionStatus.DENIED
            result.error_message = "Command blocked due to safety concerns: " + "; ".join(
                safety_report.warnings
            )
            self.memory_tracker.log_execution(result, mode)
            return result

        if safety_report.level in [SafetyLevel.DANGEROUS, SafetyLevel.WARNING]:
            logger.warning(f"Command has safety warnings ({safety_report.level.value}): {command}")
            logger.warning(f"Warnings: {safety_report.warnings}")

            # Prompt user for confirmation
            # Get overall risk score from safety report
            if safety_report.risk_score and hasattr(safety_report.risk_score, "overall_risk"):
                overall_risk = safety_report.risk_score.overall_risk
            else:
                # Fallback: estimate risk from safety level
                overall_risk = 0.9 if safety_report.level == SafetyLevel.DANGEROUS else 0.6

            user_approved = self._prompt_user_for_confirmation(command, overall_risk, safety_report)

            if not user_approved:
                logger.info(f"User denied execution of command: {command}")
                result.status = ExecutionStatus.DENIED
                result.error_message = "Command execution denied by user"
                self.memory_tracker.log_execution(result, mode)
                return result

            result.user_approved = True

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
            return self._execute_sandboxed(
                command, result, timeout, cwd, env, capture_output, stream_callback
            )

        # Direct execution
        return self._execute_direct(
            command, result, timeout, cwd, env, capture_output, stream_callback
        )

    def _execute_direct(
        self,
        command: str,
        result: CommandResult,
        timeout: int | None,
        cwd: str | None,
        env: dict[str, str] | None,
        capture_output: bool,
        stream_callback: Callable[[str], None] | None,
    ) -> CommandResult:
        """
        Execute command directly in shell with process tree tracking and resource limits.

        Enhanced with:
        - Process group creation for clean termination
        - Resource limits (CPU, memory, file descriptors)
        - Process tree tracking and monitoring
        - Resource usage collection
        """
        try:
            result.status = ExecutionStatus.RUNNING
            start_time = time.time()

            # Prepare environment
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)

            # Security validation (subprocess)
            vres = self.subproc_validator.validate_command(
                command, shell=True, cwd=cwd or os.getcwd()
            )
            if not vres.is_safe:
                result.status = ExecutionStatus.DENIED
                result.error_message = (
                    f"Command failed security validation: {', '.join(vres.violations)}"
                )
                self.memory_tracker.log_execution(result, ExecutionMode.DIRECT)
                return result

            # Execute command
            if stream_callback:
                # Use PTY for real-time streaming
                process = self._execute_with_pty(command, cwd, exec_env, stream_callback)
                exit_code = process.wait(timeout=timeout or self.default_timeout)
                stdout_data = ""
                stderr_data = ""
            else:
                # Use subprocess for captured output with resource limits
                # preexec_fn will set resource limits and create process group
                preexec = (
                    self._set_resource_limits
                    if any([self.max_memory_mb, self.max_cpu_time, self.max_file_descriptors])
                    else os.setpgrp
                )

                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    cwd=cwd,
                    env=exec_env,
                    text=True,
                    preexec_fn=preexec,  # Set resource limits and create process group
                )

                # Track process
                process_id = f"{self.session_id}_{id(process)}"
                with self.process_lock:
                    self.active_processes[process_id] = process

                # Start resource monitoring in background
                monitor_thread = threading.Thread(
                    target=self._monitor_resources, args=(process_id,), daemon=True
                )
                monitor_thread.start()

                try:
                    stdout_data, stderr_data = process.communicate(
                        timeout=timeout or self.default_timeout
                    )
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    # Kill entire process tree, not just parent
                    logger.warning(f"Command timed out, killing process tree: {command}")
                    killed = self._kill_process_tree(process_id)
                    stdout_data, stderr_data = process.communicate()
                    result.status = ExecutionStatus.TIMEOUT
                    result.error_message = f"Command timed out after {timeout or self.default_timeout} seconds (killed {killed} processes)"
                    exit_code = -1
                finally:
                    # Collect final resource usage
                    tree = self.process_trees.get(process_id)
                    if tree:
                        tree.update_resource_usage()
                        # Calculate total resource usage
                        total_cpu = tree.cpu_usage
                        max_memory = tree.memory_usage
                        child_count = len(tree.get_all_pids()) - 1  # Exclude root

                        for child in tree.children:
                            child.update_resource_usage()
                            total_cpu += child.cpu_usage
                            max_memory = max(max_memory, child.memory_usage)

                        result.resource_usage = ResourceUsage(
                            cpu_time=total_cpu, max_memory=max_memory, child_processes=child_count
                        )
                        result.process_tree_size = len(tree.get_all_pids())

                    # Clean up
                    with self.process_lock:
                        self.active_processes.pop(process_id, None)
                        self.process_trees.pop(process_id, None)

            # Record results
            result.exit_code = exit_code
            result.stdout = stdout_data or ""
            result.stderr = stderr_data or ""
            result.duration = time.time() - start_time

            if result.status != ExecutionStatus.TIMEOUT:
                result.status = (
                    ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED
                )

            logger.info(
                f"Command executed: {command} "
                f"(exit={exit_code}, duration={result.duration:.2f}s, "
                f"processes={result.process_tree_size}, resources={result.resource_usage})"
            )

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
        timeout: int | None,
        cwd: str | None,
        env: dict[str, str] | None,
        capture_output: bool,
        stream_callback: Callable[[str], None] | None,
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
                "sh",
                "-c",
                command,
            ]
        elif self._check_command_exists("bwrap"):
            # Bubblewrap sandbox
            sandbox_cmd = [
                "bwrap",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind",
                "/lib64",
                "/lib64",
                "--ro-bind",
                "/bin",
                "/bin",
                "--ro-bind",
                "/sbin",
                "/sbin",
                "--tmpfs",
                "/tmp",
                "--unshare-all",
                "--die-with-parent",
                "sh",
                "-c",
                command,
            ]
        else:
            logger.warning(
                "No sandboxing tool found (firejail, bwrap), falling back to direct execution"
            )
            return self._execute_direct(
                command, result, timeout, cwd, env, capture_output, stream_callback
            )

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
                text=True,
            )

            stdout_data, stderr_data = process.communicate(timeout=timeout or self.default_timeout)
            exit_code = process.returncode

            result.exit_code = exit_code
            result.stdout = stdout_data or ""
            result.stderr = stderr_data or ""
            result.duration = time.time() - start_time
            result.status = ExecutionStatus.COMPLETED if exit_code == 0 else ExecutionStatus.FAILED

            logger.info(
                f"Sandboxed command executed: {command} (exit={exit_code}, duration={result.duration:.2f}s)"
            )

        except subprocess.TimeoutExpired:
            process.kill()
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = (
                f"Sandboxed command timed out after {timeout or self.default_timeout} seconds"
            )
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
        cwd: str | None,
        env: dict[str, str],
        stream_callback: Callable[[str], None],
    ) -> subprocess.Popen:
        """
        Execute command with PTY for real-time output streaming.

        Enhanced with resource limits and proper cleanup.

        Args:
            command: Command to execute
            cwd: Working directory
            env: Environment variables
            stream_callback: Callback for output lines

        Returns:
            Process object
        """
        master, slave = pty.openpty()

        try:
            # preexec_fn will set resource limits and create process group
            preexec = (
                self._set_resource_limits
                if any([self.max_memory_mb, self.max_cpu_time, self.max_file_descriptors])
                else os.setsid
            )

            process = subprocess.Popen(
                command,
                shell=True,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                cwd=cwd,
                env=env,
                preexec_fn=preexec,
            )

            os.close(slave)

            # Stream output with proper exception handling
            def stream_output():
                try:
                    while True:
                        try:
                            ready, _, _ = select.select([master], [], [], 0.1)
                            if ready:
                                data = os.read(master, 1024).decode("utf-8", errors="replace")
                                if data:
                                    stream_callback(data)
                                else:
                                    break
                            if process.poll() is not None:
                                break
                        except OSError as e:
                            logger.debug(f"PTY read error (process may have terminated): {e}")
                            break
                except Exception as e:
                    logger.error(f"Error streaming output: {e}")
                finally:
                    # Clean up master fd
                    try:
                        os.close(master)
                    except OSError:
                        pass

            stream_thread = threading.Thread(target=stream_output, daemon=True)
            stream_thread.start()

            return process

        except Exception:
            # Clean up on error
            try:
                os.close(slave)
            except OSError:
                pass
            try:
                os.close(master)
            except OSError:
                pass
            raise

    def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        return (
            subprocess.run(
                ["which", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode
            == 0
        )

    def _prompt_user_for_confirmation(
        self, command: str, risk_score: float, safety_report: SafetyReport
    ) -> bool:
        """
        Prompt user for confirmation before executing dangerous command.

        Args:
            command: Command to execute
            risk_score: Risk score from safety analysis (0.0-1.0)
            safety_report: Detailed safety report

        Returns:
            True if user confirms, False otherwise
        """
        try:
            # Check if running in interactive terminal
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                logger.warning(
                    "Non-interactive environment detected, auto-denying dangerous command"
                )
                return False

            # Try to import click and rich for nice formatting
            try:
                import click
                from rich.console import Console
                from rich.panel import Panel
                from rich.text import Text

                console = Console()

                # Display risk information
                risk_text = Text()

                # Risk level indicator
                if risk_score >= 0.8:
                    risk_text.append("⚠️  CRITICAL RISK\n", style="bold red")
                elif risk_score >= 0.6:
                    risk_text.append("⚡ HIGH RISK\n", style="bold yellow")
                elif risk_score >= 0.4:
                    risk_text.append("⚠️  MEDIUM RISK\n", style="bold orange")
                else:
                    risk_text.append("ℹ️  LOW RISK\n", style="bold blue")

                risk_text.append(f"Risk Score: {risk_score:.1%}\n\n", style="bold")

                # Add command being executed
                risk_text.append("Command: ", style="bold cyan")
                risk_text.append(f"{command}\n\n", style="white")

                # Add safety warnings
                if safety_report.warnings:
                    risk_text.append("Warnings:\n", style="bold underline red")
                    for warning in safety_report.warnings:
                        risk_text.append(f"  • {warning}\n", style="yellow")
                    risk_text.append("\n")

                # Display panel
                console.print(
                    Panel(
                        risk_text,
                        title="⚠️  Safety Check",
                        border_style="red" if risk_score >= 0.8 else "yellow",
                        padding=(1, 2),
                    )
                )

                # Prompt for confirmation
                return click.confirm("Do you want to proceed with this command?", default=False)

            except ImportError:
                # Fallback to simple text prompt if rich/click not available
                print(f"\n{'='*60}")
                print("⚠️  SAFETY WARNING")
                print(f"{'='*60}")
                print(f"Command: {command}")
                print(f"Risk Score: {risk_score:.1%}")

                if safety_report.warnings:
                    print("\nWarnings:")
                    for warning in safety_report.warnings:
                        print(f"  • {warning}")

                if safety_report.suggestions:
                    print("\nSuggestions:")
                    for suggestion in safety_report.suggestions:
                        print(f"  • {suggestion}")

                print(f"\n{'='*60}")

                response = input("Proceed with execution? (y/N): ").strip().lower()
                return response in ["y", "yes"]

        except Exception as e:
            logger.error(f"Error in confirmation prompt: {e}")
            # Fail safe: deny by default
            return False

    def kill_process(self, process_id: str, kill_tree: bool = True) -> int:
        """
        Kill an active process (and optionally its entire process tree).

        Args:
            process_id: Process ID to kill
            kill_tree: If True, kill entire process tree (default: True)

        Returns:
            Number of processes killed (0 if not found)
        """
        if kill_tree:
            # Kill entire process tree
            return self._kill_process_tree(process_id)
        else:
            # Kill only the parent process
            with self.process_lock:
                process = self.active_processes.get(process_id)
                if process:
                    try:
                        process.kill()
                        self.active_processes.pop(process_id, None)
                        logger.info(f"Killed process: {process_id}")
                        return 1
                    except Exception as e:
                        logger.error(f"Failed to kill process {process_id}: {e}")
                        return 0
                return 0

    def get_active_processes(self) -> list[str]:
        """Get list of active process IDs"""
        with self.process_lock:
            return list(self.active_processes.keys())

    def get_process_tree_info(self, process_id: str) -> dict[str, Any] | None:
        """
        Get detailed process tree information.

        Args:
            process_id: Process ID to query

        Returns:
            Dictionary with process tree information, or None if not found
        """
        with self.process_lock:
            tree = self.process_trees.get(process_id)
            if not tree:
                return None

            tree.update_resource_usage()

            def node_to_dict(node: ProcessTreeNode) -> dict[str, Any]:
                return {
                    "pid": node.pid,
                    "pgid": node.pgid,
                    "parent_pid": node.parent_pid,
                    "cpu_usage": node.cpu_usage,
                    "memory_usage": node.memory_usage,
                    "uptime": time.time() - node.start_time,
                    "children": [node_to_dict(child) for child in node.children],
                }

            return node_to_dict(tree)


class InteractiveShell:
    """
    Interactive shell session with persistent state and memory.
    """

    def __init__(
        self,
        executor: CommandExecutor,
        initial_cwd: str | None = None,
        initial_env: dict[str, str] | None = None,
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
        self.history: list[CommandResult] = []
        self.variables: dict[str, str] = {}

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
        if command.strip().startswith("cd "):
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
                    cwd=self.cwd,
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
                    cwd=self.cwd,
                )
                self.history.append(result)
                return result

        # Execute command with current context
        result = self.executor.execute(command, cwd=self.cwd, env=self.env, **kwargs)

        self.history.append(result)
        return result

    def get_history(self, limit: int | None = None) -> list[CommandResult]:
        """Get command history for this shell session"""
        if limit:
            return self.history[-limit:]
        return self.history
