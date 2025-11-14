"""Tests for dashboard module."""

import pytest


def test_dashboard_init(test_db):
    """Test dashboard initialization."""
    try:
        from daedelus.ui.dashboard import Dashboard

        dashboard = Dashboard(test_db)
        assert dashboard is not None
    except ImportError:
        pytest.skip("Textual not installed")
