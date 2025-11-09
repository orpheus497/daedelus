"""Tests for logging config."""
import pytest
import logging

def test_logging_setup():
    """Test logger initialization."""
    from daedelus.utils.logging_config import setup_logging
    setup_logging()
    logger = logging.getLogger("daedelus")
    assert logger is not None

def test_log_levels():
    """Test log level configuration."""
    from daedelus.utils.logging_config import setup_logging
    setup_logging(level=logging.DEBUG)
    logger = logging.getLogger("daedelus")
    assert logger.level <= logging.DEBUG
