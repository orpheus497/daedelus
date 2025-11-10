"""
Subprocess Security Validator for Daedelus.

Provides comprehensive security validation for all subprocess operations:
- Command injection prevention
- Argument validation and sanitization
- Shell expansion safety checks
- Path traversal prevention
- Resource limit enforcement
- Audit logging for all subprocess calls

Ensures that all subprocess.run(), subprocess.Popen(), and os.system()
calls are secure and properly validated.

Created by: orpheus497
"""

import json
import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class SubprocessValidationResult:
    """Result of subprocess validation."""

    is_safe: bool
    risk_level: str  # safe, low, medium, high, critical
    violations: List[str]
    sanitized_command: Optional[List[str]] = None
    warnings: List[str] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


class SubprocessValidator:
    """
    Security validator for subprocess operations.

    Validates all subprocess calls for security risks:
    - Command injection vulnerabilities
    - Dangerous command patterns
    - Unsafe shell expansions
    - Path traversal attempts
    - Resource exhaustion

    Example usage:
        validator = SubprocessValidator()

        # Validate before execution
        result = validator.validate_command(["ls", "-la", user_input])
        if not result.is_safe:
            raise SecurityError(f"Unsafe command: {result.violations}")

        # Use sanitized command
        subprocess.run(result.sanitized_command, check=True)

        # Validate shell command
        shell_result = validator.validate_shell_command(f"find . -name '{pattern}'")
        if shell_result.is_safe:
            subprocess.run(shell_result.sanitized_command, shell=True)
    """

    # Dangerous commands that should never be executed without validation
    DANGEROUS_COMMANDS = {
        "rm", "rmdir", "dd", "mkfs", "fdisk", "parted", "wipefs",
        "shred", "chmod", "chown", "kill", "killall", "pkill",
        "systemctl", "shutdown", "reboot", "halt", "poweroff",
        "iptables", "firewall-cmd", "ufw", "apt-get", "yum",
        "dnf", "pacman", "brew", "pip", "npm", "gem", "cargo",
    }

    # Commands that are safe for most operations
    SAFE_COMMANDS = {
        "ls", "cat", "echo", "pwd", "cd", "grep", "find", "which",
        "wc", "sort", "uniq", "head", "tail", "less", "more",
        "date", "cal", "uptime", "whoami", "hostname", "uname",
    }

    # Dangerous argument patterns
    DANGEROUS_PATTERNS = [
        r";\s*(?:rm|dd|mkfs|shutdown)",  # Command chaining
        r"\$\(.*\)",  # Command substitution
        r"`.*`",  # Backtick command substitution
        r">\s*/dev/",  # Writing to devices
        r"\|\s*(?:sh|bash|zsh|fish)",  # Pipe to shell
        r"&\s*$",  # Background execution
        r"rm\s+-rf\s+/",  # Dangerous rm patterns
        r"chmod\s+-R\s+777",  # Dangerous chmod
        r":\(\)\{",  # Fork bomb pattern
    ]

    def __init__(
        self,
        allow_shell: bool = False,
        audit_log_path: Optional[Path] = None,
        strict_mode: bool = True,
    ) -> None:
        """
        Initialize subprocess validator.

        Args:
            allow_shell: Whether to allow shell=True (default: False)
            audit_log_path: Path to audit log file
            strict_mode: Enable strict validation mode
        """
        self.allow_shell = allow_shell
        self.strict_mode = strict_mode

        if audit_log_path is None:
            audit_log_path = Path.home() / ".local" / "share" / "daedelus" / "subprocess_audit.jsonl"

        self.audit_log_path = audit_log_path
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_command(
        self,
        command: Union[str, List[str]],
        shell: bool = False,
        cwd: Optional[str] = None,
    ) -> SubprocessValidationResult:
        """
        Validate a subprocess command for security issues.

        Args:
            command: Command to validate (list or string)
            shell: Whether command will use shell=True
            cwd: Working directory for command

        Returns:
            SubprocessValidationResult with validation details
        """
        violations = []
        warnings = []
        risk_level = "safe"

        # Convert string command to list if needed
        if isinstance(command, str):
            if not shell:
                # Parse as shell command
                try:
                    command_list = shlex.split(command)
                except ValueError as e:
                    violations.append(f"Invalid shell syntax: {e}")
                    return SubprocessValidationResult(
                        is_safe=False,
                        risk_level="high",
                        violations=violations,
                    )
            else:
                command_list = [command]
        else:
            command_list = command

        if not command_list:
            violations.append("Empty command")
            return SubprocessValidationResult(
                is_safe=False,
                risk_level="high",
                violations=violations,
            )

        # Check if shell is required but not allowed
        if shell and not self.allow_shell:
            violations.append("Shell execution not allowed in strict mode")
            risk_level = "critical"

        # Validate base command
        base_command = command_list[0] if command_list else ""
        cmd_validation = self._validate_base_command(base_command)
        violations.extend(cmd_validation[0])
        risk_level = max(risk_level, cmd_validation[1], key=self._risk_level_value)

        # Validate arguments
        if len(command_list) > 1:
            arg_validation = self._validate_arguments(command_list[1:])
            violations.extend(arg_validation[0])
            warnings.extend(arg_validation[1])
            risk_level = max(risk_level, arg_validation[2], key=self._risk_level_value)

        # Check for dangerous patterns in full command
        full_command_str = " ".join(command_list) if isinstance(command, list) else command
        pattern_violations = self._check_dangerous_patterns(full_command_str)
        violations.extend(pattern_violations[0])
        risk_level = max(risk_level, pattern_violations[1], key=self._risk_level_value)

        # Validate working directory
        if cwd:
            cwd_validation = self._validate_cwd(cwd)
            if not cwd_validation[0]:
                violations.extend(cwd_validation[1])
                risk_level = "medium"

        # Sanitize command
        sanitized = self._sanitize_command(command_list)

        # Determine if safe
        is_safe = len(violations) == 0 and risk_level in ["safe", "low"]

        # Log validation
        self._audit_log(
            command=full_command_str,
            is_safe=is_safe,
            risk_level=risk_level,
            violations=violations,
        )

        return SubprocessValidationResult(
            is_safe=is_safe,
            risk_level=risk_level,
            violations=violations,
            sanitized_command=sanitized,
            warnings=warnings,
        )

    def validate_shell_command(self, command: str) -> SubprocessValidationResult:
        """
        Validate a shell command string.

        Args:
            command: Shell command string

        Returns:
            SubprocessValidationResult
        """
        return self.validate_command(command, shell=True)

    def _validate_base_command(self, command: str) -> Tuple[List[str], str]:
        """
        Validate the base command.

        Args:
            command: Base command name

        Returns:
            Tuple of (violations, risk_level)
        """
        violations = []
        risk_level = "safe"

        # Check if command contains path traversal
        if "/" in command or "\\" in command:
            # Validate path
            cmd_path = Path(command)
            if not cmd_path.exists():
                violations.append(f"Command path does not exist: {command}")
                risk_level = "medium"
            elif not os.access(cmd_path, os.X_OK):
                violations.append(f"Command is not executable: {command}")
                risk_level = "medium"

        # Check if command is in dangerous list
        cmd_name = Path(command).name if "/" in command else command
        if cmd_name in self.DANGEROUS_COMMANDS:
            if self.strict_mode:
                violations.append(f"Dangerous command requires explicit approval: {cmd_name}")
                risk_level = "high"
            else:
                risk_level = "medium"

        # Check for shell metacharacters in command name
        shell_metacharacters = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\n"]
        if any(char in command for char in shell_metacharacters):
            violations.append(f"Shell metacharacters in command name: {command}")
            risk_level = "critical"

        return violations, risk_level

    def _validate_arguments(
        self, arguments: List[str]
    ) -> Tuple[List[str], List[str], str]:
        """
        Validate command arguments.

        Args:
            arguments: List of command arguments

        Returns:
            Tuple of (violations, warnings, risk_level)
        """
        violations = []
        warnings = []
        risk_level = "safe"

        for arg in arguments:
            # Check for command injection attempts
            if ";" in arg or "|" in arg:
                violations.append(f"Potential command injection in argument: {arg}")
                risk_level = "high"

            # Check for command substitution
            if "$(" in arg or "`" in arg:
                violations.append(f"Command substitution in argument: {arg}")
                risk_level = "high"

            # Check for path traversal
            if "../" in arg or "..\\" in arg:
                warnings.append(f"Path traversal pattern in argument: {arg}")
                if risk_level == "safe":
                    risk_level = "low"

            # Check for null bytes
            if "\x00" in arg:
                violations.append(f"Null byte in argument: {arg}")
                risk_level = "critical"

            # Check for excessively long arguments (potential buffer overflow)
            if len(arg) > 10000:
                warnings.append(f"Excessively long argument ({len(arg)} chars)")
                if risk_level == "safe":
                    risk_level = "low"

        return violations, warnings, risk_level

    def _check_dangerous_patterns(self, command: str) -> Tuple[List[str], str]:
        """
        Check for dangerous patterns in full command.

        Args:
            command: Full command string

        Returns:
            Tuple of (violations, risk_level)
        """
        violations = []
        risk_level = "safe"

        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(f"Dangerous pattern detected: {pattern}")
                risk_level = "critical"

        return violations, risk_level

    def _validate_cwd(self, cwd: str) -> Tuple[bool, List[str]]:
        """
        Validate working directory.

        Args:
            cwd: Working directory path

        Returns:
            Tuple of (is_valid, violations)
        """
        violations = []

        try:
            cwd_path = Path(cwd).resolve()

            # Check if directory exists
            if not cwd_path.exists():
                violations.append(f"Working directory does not exist: {cwd}")
                return False, violations

            # Check if it's actually a directory
            if not cwd_path.is_dir():
                violations.append(f"Working directory is not a directory: {cwd}")
                return False, violations

            # Check for path traversal to sensitive directories
            sensitive_dirs = ["/etc", "/sys", "/proc", "/dev"]
            for sensitive in sensitive_dirs:
                sensitive_path = Path(sensitive)
                if cwd_path == sensitive_path or sensitive_path in cwd_path.parents:
                    violations.append(f"Working directory in sensitive location: {cwd}")
                    return False, violations

        except Exception as e:
            violations.append(f"Error validating working directory: {e}")
            return False, violations

        return True, violations

    def _sanitize_command(self, command: List[str]) -> List[str]:
        """
        Sanitize command arguments.

        Args:
            command: Command as list

        Returns:
            Sanitized command list
        """
        sanitized = []

        for part in command:
            # Remove null bytes
            part = part.replace("\x00", "")

            # Remove trailing semicolons and pipes
            part = part.rstrip(";|&")

            # Limit length
            if len(part) > 10000:
                part = part[:10000]

            sanitized.append(part)

        return sanitized

    def _risk_level_value(self, level: str) -> int:
        """
        Convert risk level to numeric value for comparison.

        Args:
            level: Risk level string

        Returns:
            Numeric value
        """
        values = {
            "safe": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }
        return values.get(level, 0)

    def _audit_log(
        self,
        command: str,
        is_safe: bool,
        risk_level: str,
        violations: List[str],
    ) -> None:
        """
        Log subprocess validation to audit log.

        Args:
            command: Command that was validated
            is_safe: Whether command passed validation
            risk_level: Risk level assessment
            violations: List of violations found
        """
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "command": command[:500],  # Limit length
                "is_safe": is_safe,
                "risk_level": risk_level,
                "violations": violations,
            }

            with open(self.audit_log_path, "a") as f:
                json.dump(entry, f)
                f.write("\n")

        except Exception as e:
            logger.error(f"Failed to write subprocess audit log: {e}")

    def get_safe_wrapper(
        self,
        command: List[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        """
        Execute subprocess with automatic validation.

        Args:
            command: Command to execute
            **kwargs: Arguments to pass to subprocess.run()

        Returns:
            CompletedProcess result

        Raises:
            SecurityError: If command fails validation
        """
        # Validate command
        result = self.validate_command(
            command=command,
            shell=kwargs.get("shell", False),
            cwd=kwargs.get("cwd"),
        )

        if not result.is_safe:
            raise SecurityError(
                f"Command failed security validation: {', '.join(result.violations)}"
            )

        # Use sanitized command
        safe_command = result.sanitized_command or command

        # Execute with safe defaults
        safe_kwargs = {
            "check": kwargs.get("check", False),
            "capture_output": kwargs.get("capture_output", True),
            "text": kwargs.get("text", True),
            "timeout": kwargs.get("timeout", 30),  # Default 30s timeout
            "cwd": kwargs.get("cwd"),
            "env": kwargs.get("env"),
        }

        # Never allow shell in strict mode
        if self.strict_mode:
            safe_kwargs["shell"] = False
        else:
            safe_kwargs["shell"] = kwargs.get("shell", False)

        return subprocess.run(safe_command, **safe_kwargs)


class SecurityError(Exception):
    """Raised when a security validation fails."""

    pass
