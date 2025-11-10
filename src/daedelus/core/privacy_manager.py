"""
Privacy Manager for Daedelus.

Provides comprehensive privacy protection:
- Dynamic sensitive directory detection
- PII (Personally Identifiable Information) pattern recognition
- Credential and API key detection
- Configurable privacy levels
- Privacy audit logging
- Data anonymization

Protects user privacy by:
- Detecting and filtering sensitive commands
- Preventing logging of credentials
- Identifying PII in command arguments
- Providing granular privacy controls

Created by: orpheus497
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Set

logger = logging.getLogger(__name__)


class PrivacyLevel(Enum):
    """Privacy protection levels."""

    OFF = "off"  # No privacy filtering
    LOW = "low"  # Basic filtering (credentials only)
    MEDIUM = "medium"  # Standard filtering (credentials + common patterns)
    HIGH = "high"  # Aggressive filtering (maximum privacy)
    PARANOID = "paranoid"  # Extreme filtering (hash everything)


@dataclass
class PrivacyPattern:
    """Pattern for detecting sensitive information."""

    name: str
    pattern: Pattern[str]
    description: str
    severity: str  # low, medium, high, critical
    category: str  # credential, pii, path, api_key, token


@dataclass
class PrivacyViolation:
    """Detected privacy violation."""

    command: str
    violated_patterns: List[str]
    severity: str
    timestamp: float
    action_taken: str  # blocked, redacted, logged


@dataclass
class PrivacyConfig:
    """Privacy configuration."""

    level: PrivacyLevel = PrivacyLevel.MEDIUM
    excluded_paths: Set[str] = field(default_factory=set)
    excluded_patterns: List[Pattern[str]] = field(default_factory=list)
    allow_logging_cwd: bool = True
    allow_logging_env_vars: bool = False
    hash_sensitive_data: bool = True
    audit_privacy_violations: bool = True


class PrivacyManager:
    """
    Privacy manager for protecting sensitive information.

    Provides multi-layered privacy protection:
    1. Path-based filtering (sensitive directories)
    2. Pattern-based filtering (credentials, PII, API keys)
    3. Dynamic detection (environment variables, git remotes)
    4. Configurable privacy levels
    5. Audit logging for violations

    Example usage:
        manager = PrivacyManager()

        # Check if command should be logged
        if manager.should_log_command(cmd, cwd):
            log_command(cmd)

        # Redact sensitive information
        safe_cmd = manager.redact_sensitive(cmd)
        log_command(safe_cmd)

        # Check for privacy violations
        violations = manager.check_violations(cmd)
        if violations:
            logger.warning(f"Privacy violations: {violations}")
    """

    # Default sensitive directories
    DEFAULT_SENSITIVE_PATHS = {
        "~/.ssh",
        "~/.gnupg",
        "~/.password-store",
        "~/.config/pass",
        "~/.aws",
        "~/.kube",
        "~/.docker",
        "~/.config/gcloud",
        "~/.azure",
        "~/.config/gh",  # GitHub CLI
        "~/.netrc",
        "~/.gitconfig",  # May contain tokens
        "/etc/shadow",
        "/etc/passwd",
        "/etc/ssh",
    }

    def __init__(self, config: Optional[PrivacyConfig] = None) -> None:
        """
        Initialize privacy manager.

        Args:
            config: Privacy configuration (uses defaults if None)
        """
        self.config = config or PrivacyConfig()
        self.patterns = self._build_patterns()
        self.violations: List[PrivacyViolation] = []
        self.dynamic_sensitive_paths: Set[str] = set()
        self._discover_sensitive_paths()

    def _build_patterns(self) -> Dict[str, PrivacyPattern]:
        """
        Build comprehensive privacy patterns.

        Returns:
            Dictionary of privacy patterns
        """
        patterns = {}

        # API Keys and Tokens
        patterns["aws_access_key"] = PrivacyPattern(
            name="aws_access_key",
            pattern=re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
            description="AWS Access Key ID",
            severity="critical",
            category="api_key",
        )

        patterns["aws_secret_key"] = PrivacyPattern(
            name="aws_secret_key",
            pattern=re.compile(r"aws[_-]?secret[_-]?(?:access)?[_-]?key", re.IGNORECASE),
            description="AWS Secret Access Key",
            severity="critical",
            category="api_key",
        )

        patterns["github_token"] = PrivacyPattern(
            name="github_token",
            pattern=re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}", re.IGNORECASE),
            description="GitHub Personal Access Token",
            severity="critical",
            category="token",
        )

        patterns["generic_api_key"] = PrivacyPattern(
            name="generic_api_key",
            pattern=re.compile(r"api[_-]?key[=:\s]['\"]?[A-Za-z0-9_\-]{20,}['\"]?", re.IGNORECASE),
            description="Generic API Key",
            severity="high",
            category="api_key",
        )

        patterns["bearer_token"] = PrivacyPattern(
            name="bearer_token",
            pattern=re.compile(r"bearer\s+[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE),
            description="Bearer Token",
            severity="critical",
            category="token",
        )

        patterns["jwt_token"] = PrivacyPattern(
            name="jwt_token",
            pattern=re.compile(r"eyJ[A-Za-z0-9_\-]*\.eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*"),
            description="JWT Token",
            severity="critical",
            category="token",
        )

        # Passwords
        patterns["password_assignment"] = PrivacyPattern(
            name="password_assignment",
            pattern=re.compile(r"password[=:\s]['\"]?[^\s'\"]{6,}['\"]?", re.IGNORECASE),
            description="Password Assignment",
            severity="critical",
            category="credential",
        )

        patterns["password_flag"] = PrivacyPattern(
            name="password_flag",
            pattern=re.compile(r"(?:--?|/)(?:pass(?:word)?|pwd)[=:\s]", re.IGNORECASE),
            description="Password Flag",
            severity="critical",
            category="credential",
        )

        # Database Connection Strings
        patterns["db_connection_string"] = PrivacyPattern(
            name="db_connection_string",
            pattern=re.compile(
                r"(?:postgres|mysql|mongodb)://[^:]+:[^@]+@[^/]+",
                re.IGNORECASE,
            ),
            description="Database Connection String",
            severity="critical",
            category="credential",
        )

        # PII Patterns
        patterns["email_address"] = PrivacyPattern(
            name="email_address",
            pattern=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            description="Email Address",
            severity="medium",
            category="pii",
        )

        patterns["phone_number"] = PrivacyPattern(
            name="phone_number",
            pattern=re.compile(
                r"\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b"
            ),
            description="Phone Number",
            severity="medium",
            category="pii",
        )

        patterns["ssn"] = PrivacyPattern(
            name="ssn",
            pattern=re.compile(r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b"),
            description="Social Security Number",
            severity="critical",
            category="pii",
        )

        patterns["credit_card"] = PrivacyPattern(
            name="credit_card",
            pattern=re.compile(r"\b[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}\b"),
            description="Credit Card Number",
            severity="critical",
            category="pii",
        )

        # SSH and Private Keys
        patterns["ssh_private_key"] = PrivacyPattern(
            name="ssh_private_key",
            pattern=re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"),
            description="SSH Private Key",
            severity="critical",
            category="credential",
        )

        # Generic Secrets
        patterns["secret_keyword"] = PrivacyPattern(
            name="secret_keyword",
            pattern=re.compile(r"\b(?:secret|token|apikey|api_key)\b[=:\s]", re.IGNORECASE),
            description="Secret Keyword",
            severity="high",
            category="credential",
        )

        # Long hexadecimal strings (likely hashes or keys)
        patterns["hex_string"] = PrivacyPattern(
            name="hex_string",
            pattern=re.compile(r"\b[a-fA-F0-9]{32,}\b"),
            description="Long Hexadecimal String",
            severity="medium",
            category="credential",
        )

        # IP Addresses (internal)
        patterns["internal_ip"] = PrivacyPattern(
            name="internal_ip",
            pattern=re.compile(r"\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.[0-9]{1,3}\.[0-9]{1,3}\b"),
            description="Internal IP Address",
            severity="low",
            category="pii",
        )

        return patterns

    def _discover_sensitive_paths(self) -> None:
        """Dynamically discover sensitive directories on the system."""
        home = Path.home()

        # Check for common sensitive directories
        sensitive_patterns = [
            ".ssh",
            ".gnupg",
            ".password-store",
            ".aws",
            ".kube",
            ".docker",
            ".config/gcloud",
            ".azure",
            ".netrc",
        ]

        for pattern in sensitive_patterns:
            path = home / pattern
            if path.exists():
                self.dynamic_sensitive_paths.add(str(path))

        # Check for password manager directories
        password_managers = [
            ".config/keepassxc",
            ".config/bitwarden",
            ".config/1password",
            ".local/share/keyrings",
        ]

        for pm_path in password_managers:
            path = home / pm_path
            if path.exists():
                self.dynamic_sensitive_paths.add(str(path))

        logger.debug(f"Discovered {len(self.dynamic_sensitive_paths)} sensitive paths")

    def should_log_command(self, command: str, cwd: str) -> bool:
        """
        Determine if a command should be logged based on privacy settings.

        Args:
            command: Command string
            cwd: Current working directory

        Returns:
            True if command should be logged, False otherwise
        """
        # Check privacy level
        if self.config.level == PrivacyLevel.OFF:
            return True

        if self.config.level == PrivacyLevel.PARANOID:
            return False  # Never log in paranoid mode

        # Check if in sensitive directory
        if not self.config.allow_logging_cwd and self._is_sensitive_path(cwd):
            logger.debug(f"Blocking command in sensitive directory: {cwd}")
            return False

        # Check for privacy violations
        violations = self.check_violations(command)
        if violations:
            # Block commands with critical violations
            if any(v.severity == "critical" for v in violations):
                logger.warning(f"Blocking command with critical privacy violations")
                return False

            # In HIGH mode, block any violations
            if self.config.level == PrivacyLevel.HIGH:
                return False

        return True

    def _is_sensitive_path(self, path: str) -> bool:
        """
        Check if a path is in a sensitive directory.

        Args:
            path: Path to check

        Returns:
            True if path is sensitive
        """
        path_obj = Path(path).resolve()

        # Check default sensitive paths
        for sensitive in self.DEFAULT_SENSITIVE_PATHS:
            sensitive_path = Path(os.path.expanduser(sensitive)).resolve()
            try:
                if path_obj == sensitive_path or sensitive_path in path_obj.parents:
                    return True
            except Exception:
                continue

        # Check dynamically discovered paths
        for sensitive in self.dynamic_sensitive_paths:
            sensitive_path = Path(sensitive).resolve()
            try:
                if path_obj == sensitive_path or sensitive_path in path_obj.parents:
                    return True
            except Exception:
                continue

        # Check custom excluded paths
        for excluded in self.config.excluded_paths:
            excluded_path = Path(os.path.expanduser(excluded)).resolve()
            try:
                if path_obj == excluded_path or excluded_path in path_obj.parents:
                    return True
            except Exception:
                continue

        return False

    def check_violations(self, command: str) -> List[PrivacyViolation]:
        """
        Check command for privacy violations.

        Args:
            command: Command string

        Returns:
            List of detected violations
        """
        violations = []
        violated_patterns = []
        max_severity = "low"

        # Check against all patterns
        for pattern_name, pattern_obj in self.patterns.items():
            if pattern_obj.pattern.search(command):
                violated_patterns.append(pattern_name)

                # Track maximum severity
                if pattern_obj.severity == "critical":
                    max_severity = "critical"
                elif pattern_obj.severity == "high" and max_severity != "critical":
                    max_severity = "high"
                elif pattern_obj.severity == "medium" and max_severity not in ["critical", "high"]:
                    max_severity = "medium"

        # Check custom excluded patterns
        for pattern in self.config.excluded_patterns:
            if pattern.search(command):
                violated_patterns.append(f"custom_{pattern.pattern}")
                if max_severity == "low":
                    max_severity = "medium"

        if violated_patterns:
            violation = PrivacyViolation(
                command=self._hash_command(command) if self.config.hash_sensitive_data else command,
                violated_patterns=violated_patterns,
                severity=max_severity,
                timestamp=datetime.now().timestamp(),
                action_taken="detected",
            )
            violations.append(violation)

            # Log violation if auditing enabled
            if self.config.audit_privacy_violations:
                self._log_violation(violation)

        return violations

    def redact_sensitive(self, command: str) -> str:
        """
        Redact sensitive information from command.

        Args:
            command: Command string

        Returns:
            Command with sensitive data redacted
        """
        redacted = command

        # Redact based on privacy level
        if self.config.level == PrivacyLevel.PARANOID:
            # Hash entire command
            return self._hash_command(command)

        # Apply pattern-based redaction
        for pattern_name, pattern_obj in self.patterns.items():
            # Always redact critical patterns
            if pattern_obj.severity == "critical":
                redacted = pattern_obj.pattern.sub("[REDACTED]", redacted)
            # Redact high severity in MEDIUM+ modes
            elif pattern_obj.severity == "high" and self.config.level in [
                PrivacyLevel.MEDIUM,
                PrivacyLevel.HIGH,
            ]:
                redacted = pattern_obj.pattern.sub("[REDACTED]", redacted)
            # Redact medium severity in HIGH mode
            elif pattern_obj.severity == "medium" and self.config.level == PrivacyLevel.HIGH:
                redacted = pattern_obj.pattern.sub("[REDACTED]", redacted)

        return redacted

    def _hash_command(self, command: str) -> str:
        """
        Create a hash of the command for audit purposes.

        Args:
            command: Command string

        Returns:
            Hashed command identifier
        """
        hash_obj = hashlib.sha256(command.encode())
        return f"cmd_hash_{hash_obj.hexdigest()[:16]}"

    def _log_violation(self, violation: PrivacyViolation) -> None:
        """
        Log privacy violation to audit log.

        Args:
            violation: Privacy violation to log
        """
        try:
            # Get audit log path
            log_dir = Path.home() / ".local" / "share" / "daedelus"
            log_dir.mkdir(parents=True, exist_ok=True)
            audit_log = log_dir / "privacy_audit.jsonl"

            # Write violation
            with open(audit_log, "a") as f:
                json.dump(
                    {
                        "timestamp": violation.timestamp,
                        "command_hash": violation.command,
                        "patterns": violation.violated_patterns,
                        "severity": violation.severity,
                        "action": violation.action_taken,
                    },
                    f,
                )
                f.write("\n")

            self.violations.append(violation)

        except Exception as e:
            logger.error(f"Failed to log privacy violation: {e}")

    def get_privacy_report(self) -> Dict[str, any]:
        """
        Generate privacy report with statistics.

        Returns:
            Dictionary with privacy statistics
        """
        total_violations = len(self.violations)
        by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        by_category = {}

        for violation in self.violations:
            by_severity[violation.severity] += 1

            for pattern_name in violation.violated_patterns:
                if pattern_name in self.patterns:
                    category = self.patterns[pattern_name].category
                    by_category[category] = by_category.get(category, 0) + 1

        return {
            "total_violations": total_violations,
            "by_severity": by_severity,
            "by_category": by_category,
            "privacy_level": self.config.level.value,
            "sensitive_paths_monitored": len(self.dynamic_sensitive_paths),
            "patterns_active": len(self.patterns),
        }

    def clear_violations(self) -> None:
        """Clear violation history (useful for testing)."""
        self.violations = []
