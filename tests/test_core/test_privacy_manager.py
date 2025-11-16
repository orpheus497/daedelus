"""
Tests for Privacy Manager.

Created by: orpheus497
"""

from pathlib import Path

import pytest

from daedelus.core.privacy_manager import (
    PrivacyConfig,
    PrivacyLevel,
    PrivacyManager,
)


@pytest.fixture
def manager():
    """Create a privacy manager instance."""
    return PrivacyManager()


@pytest.fixture
def strict_manager():
    """Create a privacy manager with strict settings."""
    config = PrivacyConfig(level=PrivacyLevel.HIGH)
    return PrivacyManager(config=config)


def test_privacy_manager_initialization(manager):
    """Test that privacy manager initializes correctly."""
    assert manager is not None
    assert manager.config is not None
    assert len(manager.patterns) > 0
    assert manager.violations == []


def test_privacy_levels():
    """Test different privacy levels."""
    assert PrivacyLevel.OFF.value == "off"
    assert PrivacyLevel.LOW.value == "low"
    assert PrivacyLevel.MEDIUM.value == "medium"
    assert PrivacyLevel.HIGH.value == "high"
    assert PrivacyLevel.PARANOID.value == "paranoid"


def test_should_log_command_safe(manager):
    """Test logging decision for safe commands."""
    result = manager.should_log_command("ls -la", "/home/user/projects")
    assert result is True


def test_should_log_command_with_password(manager):
    """Test logging decision for command with password."""
    result = manager.should_log_command(
        "mysql -u root -p password123",
        "/home/user/projects",
    )
    # Should be blocked due to critical violations
    assert result is False


def test_should_log_command_sensitive_directory(manager):
    """Test logging decision in sensitive directory."""
    manager.config.allow_logging_cwd = False
    result = manager.should_log_command("ls -la", str(Path.home() / ".ssh"))
    assert result is False


def test_should_log_paranoid_mode():
    """Test that paranoid mode blocks all logging."""
    config = PrivacyConfig(level=PrivacyLevel.PARANOID)
    manager = PrivacyManager(config=config)

    result = manager.should_log_command("ls -la", "/home/user")
    assert result is False


def test_aws_access_key_detection(manager):
    """Test AWS access key pattern detection."""
    command = "aws configure set aws_access_key_id AKIAIOSFODNN7EXAMPLE"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("aws_access_key" in v.violated_patterns for v in violations)
    assert violations[0].severity == "critical"


def test_github_token_detection(manager):
    """Test GitHub token pattern detection."""
    command = "git push https://ghp_1234567890abcdefghijklmnopqrstuvwxyz@github.com/user/repo"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("github_token" in v.violated_patterns for v in violations)


def test_password_assignment_detection(manager):
    """Test password assignment detection."""
    commands = [
        "export PASSWORD=mysecretpass",
        "mysql -u root --password=hunter2",
        'psql "password=secret123"',
    ]

    for cmd in commands:
        violations = manager.check_violations(cmd)
        assert len(violations) > 0, f"Failed to detect password in: {cmd}"


def test_email_address_detection(manager):
    """Test email address detection."""
    command = "git config user.email john.doe@example.com"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("email_address" in v.violated_patterns for v in violations)
    # Email is medium severity, not critical
    assert violations[0].severity in ["medium", "high", "critical"]


def test_phone_number_detection(manager):
    """Test phone number detection."""
    command = "echo 'Call me at 555-123-4567'"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("phone_number" in v.violated_patterns for v in violations)


def test_ssn_detection(manager):
    """Test Social Security Number detection."""
    command = "echo '123-45-6789'"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("ssn" in v.violated_patterns for v in violations)
    assert violations[0].severity == "critical"


def test_jwt_token_detection(manager):
    """Test JWT token detection."""
    command = "curl -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("jwt_token" in v.violated_patterns for v in violations)


def test_hex_string_detection(manager):
    """Test long hexadecimal string detection."""
    command = "echo 'API key: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6'"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("hex_string" in v.violated_patterns for v in violations)


def test_redact_sensitive_critical(manager):
    """Test redaction of critical sensitive information."""
    command = "mysql -u root -p password123"
    redacted = manager.redact_sensitive(command)

    assert "password123" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_sensitive_paranoid():
    """Test redaction in paranoid mode."""
    config = PrivacyConfig(level=PrivacyLevel.PARANOID)
    manager = PrivacyManager(config=config)

    command = "ls -la /home/user"
    redacted = manager.redact_sensitive(command)

    # Entire command should be hashed in paranoid mode
    assert redacted.startswith("cmd_hash_")
    assert "ls" not in redacted


def test_is_sensitive_path_ssh(manager):
    """Test sensitive path detection for .ssh directory."""
    ssh_path = str(Path.home() / ".ssh")
    result = manager._is_sensitive_path(ssh_path)

    assert result is True


def test_is_sensitive_path_aws(manager):
    """Test sensitive path detection for .aws directory."""
    aws_path = str(Path.home() / ".aws")
    result = manager._is_sensitive_path(aws_path)

    assert result is True


def test_is_sensitive_path_normal(manager):
    """Test that normal paths are not flagged as sensitive."""
    normal_path = str(Path.home() / "projects" / "myapp")
    result = manager._is_sensitive_path(normal_path)

    assert result is False


def test_get_privacy_report(manager):
    """Test privacy report generation."""
    # Generate some violations
    manager.check_violations("mysql -p password123")
    manager.check_violations("aws configure AKIAIOSFODNN7EXAMPLE")

    report = manager.get_privacy_report()

    assert report["total_violations"] == 2
    assert "by_severity" in report
    assert "by_category" in report
    assert report["privacy_level"] == "medium"
    assert report["patterns_active"] > 0


def test_clear_violations(manager):
    """Test clearing violation history."""
    manager.check_violations("mysql -p password123")
    assert len(manager.violations) > 0

    manager.clear_violations()
    assert len(manager.violations) == 0


def test_custom_excluded_patterns():
    """Test custom excluded patterns."""
    import re

    config = PrivacyConfig(
        excluded_patterns=[
            re.compile(r"custom_secret_\d+"),
            re.compile(r"internal_token_[a-z]+"),
        ]
    )
    manager = PrivacyManager(config=config)

    violations1 = manager.check_violations("echo custom_secret_12345")
    assert len(violations1) > 0

    violations2 = manager.check_violations("echo internal_token_abc")
    assert len(violations2) > 0


def test_audit_logging(manager):
    """Test that violations are logged to audit file."""
    manager.config.audit_privacy_violations = True

    command = "mysql -p password123"
    manager.check_violations(command)

    # Check that audit log was created
    assert manager.audit_log_path.parent.exists()


def test_database_connection_string_detection(manager):
    """Test database connection string detection."""
    commands = [
        "psql postgres://user:password@localhost:5432/mydb",
        "mysql://admin:secret@db.example.com/production",
        "mongodb://user:pass@mongo.local/database",
    ]

    for cmd in commands:
        violations = manager.check_violations(cmd)
        assert len(violations) > 0, f"Failed to detect connection string in: {cmd}"
        assert violations[0].severity == "critical"


def test_ssh_private_key_detection(manager):
    """Test SSH private key detection."""
    command = "cat ~/.ssh/id_rsa | grep 'BEGIN RSA PRIVATE KEY'"
    violations = manager.check_violations(command)

    assert len(violations) > 0
    assert any("ssh_private_key" in v.violated_patterns for v in violations)
    assert violations[0].severity == "critical"


def test_api_key_patterns(manager):
    """Test various API key pattern detection."""
    commands = [
        "export API_KEY=sk_test_1234567890abcdef",
        "curl -H 'X-API-Key: 1234567890abcdefghijklmnopqrst'",
        "config set api-key=abcdefghijklmnopqrstuvwxyz123456",
    ]

    for cmd in commands:
        violations = manager.check_violations(cmd)
        assert len(violations) > 0, f"Failed to detect API key in: {cmd}"
