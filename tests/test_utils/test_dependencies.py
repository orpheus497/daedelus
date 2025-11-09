"""Tests for dependency management."""
import pytest

def test_check_dependency_available():
    """Test dependency checking."""
    from daedelus.utils.dependencies import check_dependency
    result = check_dependency("click")  # Always available
    assert result is True

def test_graceful_degradation():
    """Test handling missing dependencies."""
    from daedelus.utils.dependencies import check_dependency
    result = check_dependency("nonexistent_package_xyz")
    assert result is False
