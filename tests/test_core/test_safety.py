"""
Tests for command safety analysis.

Tests dangerous pattern detection and safety levels.

Created by: orpheus497
"""

import pytest
from daedelus.core.safety import SafetyAnalyzer


def test_safety_analyzer_init():
    """Test analyzer initialization."""
    analyzer = SafetyAnalyzer(level="warn")
    assert analyzer.level == "warn"


def test_detect_dangerous_rm():
    """Test rm -rf / detection."""
    analyzer = SafetyAnalyzer(level="warn")

    result = analyzer.check("rm -rf /")

    assert result.is_dangerous
    assert "rm" in result.reason.lower()


def test_detect_dd_overwrite():
    """Test dd device overwrite detection."""
    analyzer = SafetyAnalyzer(level="warn")

    result = analyzer.check("dd if=/dev/zero of=/dev/sda")

    assert result.is_dangerous
    assert "dd" in result.reason.lower()


def test_detect_fork_bomb():
    """Test fork bomb pattern detection."""
    analyzer = SafetyAnalyzer(level="warn")

    result = analyzer.check(":(){ :|:& };:")

    assert result.is_dangerous
    assert "fork" in result.reason.lower()


def test_safe_command_pass_through():
    """Test that normal commands pass."""
    analyzer = SafetyAnalyzer(level="warn")

    result = analyzer.check("git status")

    assert not result.is_dangerous


def test_safety_level_off():
    """Test disabled safety mode."""
    analyzer = SafetyAnalyzer(level="off")

    result = analyzer.check("rm -rf /")

    # Still detected but not enforced
    assert result.is_dangerous
    assert result.action == "allow"


def test_safety_level_block():
    """Test blocking mode."""
    analyzer = SafetyAnalyzer(level="block")

    result = analyzer.check("rm -rf /")

    assert result.is_dangerous
    assert result.action == "block"


def test_whitelist_patterns():
    """Test user whitelist."""
    analyzer = SafetyAnalyzer(
        level="warn",
        whitelist=["rm -rf ./build"]
    )

    result = analyzer.check("rm -rf ./build")

    assert not result.is_dangerous
