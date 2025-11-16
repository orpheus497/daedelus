"""Tests for config module."""

from daedelus.utils.config import Config


def test_config_initialization(temp_dir):
    """Test config loading."""
    config = Config()
    assert config is not None


def test_get_value(test_config):
    """Test nested value access."""
    value = test_config.get("daemon.socket_path")
    assert value is not None


def test_set_value(test_config):
    """Test config updates."""
    test_config.set("test.key", "value")
    assert test_config.get("test.key") == "value"
