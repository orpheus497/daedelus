"""
Utility modules for Daedelus.

Provides configuration management, logging, dependencies handling, and more.

Created by: orpheus497
"""

from daedelus.utils.backup import BackupManager
from daedelus.utils.config import Config
from daedelus.utils.dependencies import check_dependency, require_dependency
from daedelus.utils.fuzzy import FuzzyMatcher, get_matcher
from daedelus.utils.highlighting import SyntaxHighlighter, get_highlighter
from daedelus.utils.logging_config import setup_logging

__all__ = [
    "Config",
    "setup_logging",
    "check_dependency",
    "require_dependency",
    "FuzzyMatcher",
    "get_matcher",
    "SyntaxHighlighter",
    "get_highlighter",
    "BackupManager",
]
