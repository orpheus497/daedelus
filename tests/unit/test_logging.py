"""
Comprehensive unit tests for logging configuration.

Tests all major functionality:
- ColoredFormatter
- setup_logging function
- Console and file handlers
- Log rotation
- Debug mode
- get_logger function

Created by: orpheus497
"""

import logging

from daedelus.utils.logging_config import ColoredFormatter, get_logger, setup_logging


class TestColoredFormatter:
    """Test ColoredFormatter class."""

    def test_formatter_creation(self):
        """Test creating colored formatter."""
        formatter = ColoredFormatter("%(levelname)s | %(message)s")

        assert formatter is not None

    def test_formatter_formats_record(self):
        """Test that formatter can format a record."""
        formatter = ColoredFormatter("%(levelname)s | %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "INFO" in result
        assert "Test message" in result

    def test_formatter_adds_colors(self):
        """Test that formatter adds color codes."""
        formatter = ColoredFormatter("%(levelname)s")
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should contain ANSI color codes
        assert "\033[" in result

    def test_formatter_different_levels(self):
        """Test formatter with different log levels."""
        formatter = ColoredFormatter("%(levelname)s")

        levels = [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]

        for level in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="Message",
                args=(),
                exc_info=None,
            )
            result = formatter.format(record)
            assert result is not None


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_console_only(self):
        """Test setup with console only."""
        logger = setup_logging(console=True)

        assert logger is not None
        assert logger.name == "daedelus"
        assert len(logger.handlers) > 0

    def test_setup_logging_with_file(self, temp_dir):
        """Test setup with file logging."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False)

        assert logger is not None
        assert log_path.exists()

    def test_setup_logging_creates_log_dir(self, temp_dir):
        """Test that setup creates log directory if needed."""
        log_path = temp_dir / "nested" / "dir" / "test.log"

        setup_logging(log_path=log_path)

        assert log_path.parent.exists()

    def test_setup_logging_console_and_file(self, temp_dir):
        """Test setup with both console and file."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=True)

        # Should have 2 handlers (console + file)
        assert len(logger.handlers) == 2

    def test_setup_logging_debug_mode(self):
        """Test setup with debug mode."""
        logger = setup_logging(debug=True)

        assert logger.level == logging.DEBUG

    def test_setup_logging_custom_level(self):
        """Test setup with custom level."""
        logger = setup_logging(level=logging.WARNING, console=True)

        assert logger.level == logging.WARNING

    def test_setup_logging_no_propagate(self):
        """Test that logger doesn't propagate to root."""
        logger = setup_logging(console=True)

        assert logger.propagate is False

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup clears existing handlers."""
        # Set up once
        logger1 = setup_logging(console=True)
        num_handlers_1 = len(logger1.handlers)

        # Set up again
        logger2 = setup_logging(console=True)
        num_handlers_2 = len(logger2.handlers)

        # Should have same number of handlers (not double)
        assert num_handlers_2 == num_handlers_1

    def test_setup_logging_file_creates_parent_dir(self, temp_dir):
        """Test that file logging creates parent directory."""
        log_path = temp_dir / "subdir" / "test.log"

        setup_logging(log_path=log_path)

        assert log_path.parent.exists()

    def test_setup_logging_writes_to_file(self, temp_dir):
        """Test that logging actually writes to file."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False)
        logger.info("Test message")

        # Force flush
        for handler in logger.handlers:
            handler.flush()

        assert log_path.exists()
        content = log_path.read_text()
        assert "Test message" in content


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger."""
        logger = get_logger("test")

        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_get_logger_namespaced(self):
        """Test that logger is properly namespaced."""
        logger = get_logger("test")

        assert logger.name == "daedelus.test"

    def test_get_logger_different_names(self):
        """Test getting loggers with different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "daedelus.module1"
        assert logger2.name == "daedelus.module2"

    def test_get_logger_inherits_config(self):
        """Test that sub-logger inherits configuration."""
        # Set up parent logger
        setup_logging(level=logging.DEBUG, console=False)

        # Get child logger
        child_logger = get_logger("child")

        # Child should have same level as parent
        assert child_logger.level == logging.NOTSET  # Inherits from parent


class TestLogRotation:
    """Test log file rotation."""

    def test_rotating_handler_configured(self, temp_dir):
        """Test that rotating file handler is configured."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False)

        # Check that at least one handler is RotatingFileHandler
        has_rotating = any(
            isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers
        )

        assert has_rotating

    def test_rotating_handler_max_bytes(self, temp_dir):
        """Test that rotating handler has max bytes set."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False)

        rotating_handler = next(
            h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
        )

        assert rotating_handler.maxBytes == 10 * 1024 * 1024  # 10MB

    def test_rotating_handler_backup_count(self, temp_dir):
        """Test that rotating handler has backup count set."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False)

        rotating_handler = next(
            h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
        )

        assert rotating_handler.backupCount == 5


class TestLogFormats:
    """Test log formatting."""

    def test_console_format(self):
        """Test console log format."""
        logger = setup_logging(console=True)

        console_handler = next(
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.handlers.RotatingFileHandler)
        )

        # Should use ColoredFormatter
        assert isinstance(console_handler.formatter, ColoredFormatter)

    def test_file_format(self, temp_dir):
        """Test file log format."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False)

        file_handler = logger.handlers[0]

        # Should have detailed format
        assert file_handler.formatter is not None


class TestLoggingOutput:
    """Test actual logging output."""

    def test_log_info_message(self, temp_dir):
        """Test logging an info message."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False, level=logging.INFO)
        logger.info("Info message")

        for handler in logger.handlers:
            handler.flush()

        content = log_path.read_text()
        assert "INFO" in content
        assert "Info message" in content

    def test_log_error_message(self, temp_dir):
        """Test logging an error message."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False, level=logging.ERROR)
        logger.error("Error message")

        for handler in logger.handlers:
            handler.flush()

        content = log_path.read_text()
        assert "ERROR" in content
        assert "Error message" in content

    def test_log_debug_filtered_by_level(self, temp_dir):
        """Test that debug messages are filtered by level."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False, level=logging.INFO)
        logger.debug("Debug message")  # Should be filtered out

        for handler in logger.handlers:
            handler.flush()

        content = log_path.read_text()
        assert "Debug message" not in content

    def test_log_debug_shown_in_debug_mode(self, temp_dir):
        """Test that debug messages are shown in debug mode."""
        log_path = temp_dir / "test.log"

        logger = setup_logging(log_path=log_path, console=False, debug=True)
        logger.debug("Debug message")

        for handler in logger.handlers:
            handler.flush()

        content = log_path.read_text()
        assert "DEBUG" in content
        assert "Debug message" in content


class TestMultipleLoggers:
    """Test multiple logger instances."""

    def test_multiple_child_loggers(self):
        """Test creating multiple child loggers."""
        setup_logging(console=False)

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        logger1.info("From module1")
        logger2.info("From module2")

        # Should not crash and loggers should be different
        assert logger1.name != logger2.name
