"""
Tests for Subprocess Validator.

Created by: orpheus497
"""

import tempfile
from pathlib import Path

import pytest

from daedelus.core.subprocess_validator import (
    SecurityError,
    SubprocessValidationResult,
    SubprocessValidator,
)


@pytest.fixture
def validator():
    """Create a subprocess validator instance."""
    return SubprocessValidator(strict_mode=True)


@pytest.fixture
def lenient_validator():
    """Create a lenient subprocess validator."""
    return SubprocessValidator(strict_mode=False, allow_shell=True)


def test_validator_initialization(validator):
    """Test that validator initializes correctly."""
    assert validator is not None
    assert validator.strict_mode is True
    assert validator.allow_shell is False


def test_validate_safe_command(validator):
    """Test validation of safe commands."""
    safe_commands = [
        ["ls", "-la"],
        ["cat", "file.txt"],
        ["grep", "pattern", "file.txt"],
        ["find", ".", "-name", "*.py"],
    ]

    for cmd in safe_commands:
        result = validator.validate_command(cmd)
        assert result.is_safe is True
        assert result.risk_level in ["safe", "low"]


def test_validate_dangerous_command(validator):
    """Test validation of dangerous commands."""
    dangerous_commands = [
        ["rm", "-rf", "/"],
        ["dd", "if=/dev/zero", "of=/dev/sda"],
        ["mkfs.ext4", "/dev/sda1"],
        ["chmod", "-R", "777", "/"],
    ]

    for cmd in dangerous_commands:
        result = validator.validate_command(cmd)
        # Should have violations or high risk level
        assert len(result.violations) > 0 or result.risk_level in ["high", "critical"]


def test_validate_command_injection(validator):
    """Test detection of command injection attempts."""
    injection_attempts = [
        ["ls", "; rm -rf /"],
        ["cat", "file.txt | sh"],
        ["echo", "$(rm -rf /)"],
        ["grep", "pattern`whoami`"],
    ]

    for cmd in injection_attempts:
        result = validator.validate_command(cmd)
        assert result.is_safe is False
        assert len(result.violations) > 0


def test_validate_command_substitution(validator):
    """Test detection of command substitution."""
    commands_with_substitution = [
        ["echo", "$(date)"],
        ["cat", "`whoami`"],
        ["ls", "$USER"],
    ]

    for cmd in commands_with_substitution:
        result = validator.validate_command(cmd)
        # Should have violations
        assert len(result.violations) > 0


def test_validate_shell_command_not_allowed(validator):
    """Test that shell commands are blocked in strict mode."""
    result = validator.validate_shell_command("ls | grep test")
    assert result.is_safe is False
    assert any("Shell execution not allowed" in v for v in result.violations)


def test_validate_shell_command_allowed(lenient_validator):
    """Test that shell commands are allowed in lenient mode."""
    result = lenient_validator.validate_shell_command("ls | grep test")
    # May still have warnings but should pass basic validation
    assert len(result.violations) == 0 or result.risk_level != "critical"


def test_validate_path_traversal(validator):
    """Test detection of path traversal attempts."""
    commands_with_traversal = [
        ["cat", "../../../etc/passwd"],
        ["ls", "../../secret"],
        ["cd", "..\\..\\..\\"],
    ]

    for cmd in commands_with_traversal:
        result = validator.validate_command(cmd)
        # Should have warnings at minimum
        assert len(result.warnings) > 0 or len(result.violations) > 0


def test_validate_null_bytes(validator):
    """Test detection of null bytes in arguments."""
    result = validator.validate_command(["cat", "file\x00.txt"])
    assert result.is_safe is False
    assert any("Null byte" in v for v in result.violations)


def test_validate_long_argument(validator):
    """Test detection of excessively long arguments."""
    long_arg = "A" * 15000
    result = validator.validate_command(["echo", long_arg])
    # Should have warnings
    assert len(result.warnings) > 0


def test_validate_working_directory(validator):
    """Test validation of working directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Valid directory
        result = validator.validate_command(["ls"], cwd=tmpdir)
        assert len(result.violations) == 0

        # Invalid directory
        result = validator.validate_command(["ls"], cwd="/nonexistent/path/12345")
        assert len(result.violations) > 0


def test_validate_sensitive_directory(validator):
    """Test validation blocks access to sensitive directories."""
    sensitive_dirs = ["/etc", "/sys", "/proc", "/dev"]

    for sensitive_dir in sensitive_dirs:
        result = validator.validate_command(["ls"], cwd=sensitive_dir)
        assert len(result.violations) > 0


def test_sanitize_command(validator):
    """Test command sanitization."""
    dirty_commands = [
        ["echo", "test;"],
        ["cat", "file|"],
        ["ls", "dir&"],
    ]

    for cmd in dirty_commands:
        result = validator.validate_command(cmd)
        assert result.sanitized_command is not None
        # Sanitized command should not have trailing special chars
        for part in result.sanitized_command:
            assert not part.endswith(";")
            assert not part.endswith("|")
            assert not part.endswith("&")


def test_sanitize_null_bytes(validator):
    """Test that null bytes are removed during sanitization."""
    result = validator.validate_command(["cat", "file\x00name.txt"])
    assert result.sanitized_command is not None
    assert "\x00" not in result.sanitized_command[1]


def test_dangerous_patterns_detection(validator):
    """Test detection of dangerous command patterns."""
    dangerous_patterns = [
        "rm -rf /home",
        "dd if=/dev/zero of=/dev/sda",
        "chmod -R 777 /var",
        ":(){:|:&};:",  # Fork bomb
    ]

    for pattern in dangerous_patterns:
        result = validator.validate_shell_command(pattern)
        assert result.is_safe is False
        assert result.risk_level in ["high", "critical"]


def test_fork_bomb_detection(validator):
    """Test detection of fork bomb pattern."""
    fork_bomb = ":(){:|:&};:"
    result = validator.validate_shell_command(fork_bomb)
    assert result.is_safe is False
    assert result.risk_level == "critical"


def test_device_write_detection(validator):
    """Test detection of writes to device files."""
    commands = [
        "echo test > /dev/sda",
        "cat data > /dev/sdb1",
    ]

    for cmd in commands:
        result = validator.validate_shell_command(cmd)
        assert result.is_safe is False
        assert len(result.violations) > 0


def test_safe_commands_allowed(validator):
    """Test that safe commands are explicitly allowed."""
    for cmd_name in SubprocessValidator.SAFE_COMMANDS:
        result = validator.validate_command([cmd_name])
        # Safe commands should pass base validation
        assert result.risk_level in ["safe", "low"]


def test_dangerous_commands_flagged(validator):
    """Test that dangerous commands are flagged."""
    for cmd_name in SubprocessValidator.DANGEROUS_COMMANDS:
        result = validator.validate_command([cmd_name])
        # Dangerous commands should be flagged in strict mode
        if validator.strict_mode:
            assert result.risk_level in ["medium", "high", "critical"] or len(result.violations) > 0


def test_get_safe_wrapper_with_safe_command(validator):
    """Test safe wrapper execution with safe command."""
    # This will actually execute, so use a very safe command
    try:
        result = validator.get_safe_wrapper(["echo", "test"])
        assert result is not None
        assert result.returncode == 0
    except SecurityError:
        pytest.fail("Safe command should not raise SecurityError")


def test_get_safe_wrapper_with_unsafe_command(validator):
    """Test safe wrapper blocks unsafe commands."""
    with pytest.raises(SecurityError):
        validator.get_safe_wrapper(["rm", "-rf", "/"])


def test_audit_logging(validator):
    """Test that validations are logged to audit file."""
    validator.validate_command(["ls", "-la"])

    # Check that audit log exists
    assert validator.audit_log_path.parent.exists()


def test_risk_level_ordering(validator):
    """Test that risk levels can be properly compared."""
    levels = ["safe", "low", "medium", "high", "critical"]

    for i, level1 in enumerate(levels):
        for j, level2 in enumerate(levels):
            val1 = validator._risk_level_value(level1)
            val2 = validator._risk_level_value(level2)

            if i < j:
                assert val1 < val2
            elif i == j:
                assert val1 == val2
            else:
                assert val1 > val2


def test_empty_command(validator):
    """Test validation of empty command."""
    result = validator.validate_command([])
    assert result.is_safe is False
    assert any("Empty command" in v for v in result.violations)


def test_command_with_shell_metacharacters_in_name(validator):
    """Test detection of shell metacharacters in command name."""
    result = validator.validate_command(["ls;rm"])
    assert result.is_safe is False
    assert result.risk_level == "critical"


def test_validation_result_structure(validator):
    """Test that validation result has correct structure."""
    result = validator.validate_command(["ls", "-la"])

    assert isinstance(result, SubprocessValidationResult)
    assert isinstance(result.is_safe, bool)
    assert isinstance(result.risk_level, str)
    assert isinstance(result.violations, list)
    assert isinstance(result.warnings, list)
    assert result.sanitized_command is None or isinstance(result.sanitized_command, list)


def test_string_command_parsing(validator):
    """Test parsing of string commands."""
    result = validator.validate_command("ls -la /home")
    assert result.sanitized_command is not None
    assert len(result.sanitized_command) == 3
    assert result.sanitized_command[0] == "ls"


def test_invalid_shell_syntax(validator):
    """Test handling of invalid shell syntax."""
    result = validator.validate_command("ls -la 'unclosed")
    assert result.is_safe is False
    assert any("Invalid shell syntax" in v for v in result.violations)
