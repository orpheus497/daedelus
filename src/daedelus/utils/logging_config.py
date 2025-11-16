"""
Logging configuration for Daedalus.

Provides a centralized logging setup with:
- File and console handlers
- Colored output for terminal
- Rotation for log files
- Debug mode support

Created by: orpheus497
"""

import logging
import logging.handlers
import sys
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to log levels in terminal output.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{self.BOLD}{levelname}{self.RESET}"

        # Format the message
        result = super().format(record)

        # Reset levelname for other handlers
        record.levelname = levelname

        return result


def setup_logging(
    log_path: Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
    debug: bool = False,
) -> logging.Logger:
    """
    Set up logging for Daedalus.

    Args:
        log_path: Path to log file. If None, only console logging.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Whether to log to console
        debug: Enable debug mode (more verbose logging)

    Returns:
        Configured logger instance

    Example:
        >>> from pathlib import Path
        >>> logger = setup_logging(Path("~/.local/share/daedelus/daemon.log"))
        >>> logger.info("Daemon started")
    """
    # Get root logger for daedelus
    logger = logging.getLogger("daedelus")

    # Set level
    if debug:
        level = logging.DEBUG

    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler (if enabled)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Use colored formatter for console
        console_format = "%(levelname)s | %(name)s | %(message)s"
        console_formatter = ColoredFormatter(console_format)
        console_handler.setFormatter(console_formatter)

        logger.addHandler(console_handler)

    # File handler (if log_path provided)
    if log_path:
        log_path = Path(log_path).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use rotating file handler (max 10MB, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(level)

        # File gets more detailed format
        file_format = (
            "%(asctime)s | %(levelname)-8s | %(name)s | " "%(funcName)s:%(lineno)d | %(message)s"
        )
        file_formatter = logging.Formatter(file_format, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)

        # Force immediate flush to prevent buffering issues in daemon mode
        class FlushingRotatingFileHandler(logging.handlers.RotatingFileHandler):
            def emit(self, record):
                super().emit(record)
                self.flush()

        # Replace handler with flushing version
        file_handler = FlushingRotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)

        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Log the initialization
    logger.info("Logging initialized")
    if log_path:
        logger.debug(f"Log file: {log_path}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name under the daedelus namespace.

    Args:
        name: Logger name (will be prefixed with 'daedelus.')

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger("daemon")
        >>> logger.info("Starting daemon")
        INFO | daedelus.daemon | Starting daemon
    """
    return logging.getLogger(f"daedelus.{name}")


# Example usage for testing
if __name__ == "__main__":
    # Test with console only
    logger = setup_logging(debug=True)
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

    # Test with file logging
    logger2 = setup_logging(Path("/tmp/daedelus_test.log"), debug=True)
    logger2.info("Testing file logging")
