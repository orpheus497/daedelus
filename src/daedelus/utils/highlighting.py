"""
Syntax highlighting utilities for Daedelus.

Uses Pygments for syntax highlighting of shell commands, code, and output.

Created by: orpheus497
"""

from pathlib import Path

from pygments import highlight
from pygments.formatters import TerminalFormatter, Terminal256Formatter
from pygments.lexers import (
    BashLexer,
    BashSessionLexer,
    PythonLexer,
    SqlLexer,
    get_lexer_by_name,
    guess_lexer,
)
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound
from rich.console import Console
from rich.syntax import Syntax


class SyntaxHighlighter:
    """
    Syntax highlighter for shell commands and code.

    Supports:
    - Shell commands (Bash/ZSH)
    - Python code
    - SQL queries
    - Auto-detection of language
    - Multiple color schemes
    """

    def __init__(self, style: str = "monokai", use_rich: bool = True) -> None:
        """
        Initialize syntax highlighter.

        Args:
            style: Pygments color scheme (monokai, vim, native, etc.)
            use_rich: Use Rich library for better formatting
        """
        self.style = style
        self.use_rich = use_rich
        self.console = Console() if use_rich else None

        # Pre-create common lexers for performance
        self.bash_lexer = BashLexer()
        self.python_lexer = PythonLexer()
        self.sql_lexer = SqlLexer()
        self.session_lexer = BashSessionLexer()

        # Formatter for terminal output
        try:
            self.formatter = Terminal256Formatter(style=style)
        except ClassNotFound:
            self.formatter = TerminalFormatter()

    def highlight_shell(self, command: str) -> str:
        """
        Highlight a shell command.

        Args:
            command: Shell command string

        Returns:
            Highlighted command string
        """
        if self.use_rich and self.console:
            # Use Rich Syntax for better rendering
            syntax = Syntax(command, "bash", theme=self.style, background_color="default")
            # Capture Rich output as string
            with self.console.capture() as capture:
                self.console.print(syntax)
            return capture.get().strip()
        else:
            return highlight(command, self.bash_lexer, self.formatter).strip()

    def highlight_python(self, code: str) -> str:
        """
        Highlight Python code.

        Args:
            code: Python code string

        Returns:
            Highlighted code string
        """
        if self.use_rich and self.console:
            syntax = Syntax(code, "python", theme=self.style, background_color="default")
            with self.console.capture() as capture:
                self.console.print(syntax)
            return capture.get().strip()
        else:
            return highlight(code, self.python_lexer, self.formatter).strip()

    def highlight_sql(self, query: str) -> str:
        """
        Highlight SQL query.

        Args:
            query: SQL query string

        Returns:
            Highlighted query string
        """
        if self.use_rich and self.console:
            syntax = Syntax(query, "sql", theme=self.style, background_color="default")
            with self.console.capture() as capture:
                self.console.print(syntax)
            return capture.get().strip()
        else:
            return highlight(query, self.sql_lexer, self.formatter).strip()

    def highlight_auto(self, text: str, language: str | None = None) -> str:
        """
        Highlight text with automatic language detection.

        Args:
            text: Text to highlight
            language: Optional language hint (bash, python, sql, etc.)

        Returns:
            Highlighted text string
        """
        if not text:
            return text

        if self.use_rich and self.console:
            # Guess language if not provided
            if not language:
                # Simple heuristics for common cases
                if text.strip().startswith(("$", "#", "sudo", "ls", "cd", "git")):
                    language = "bash"
                elif text.strip().startswith(("def ", "class ", "import ", "from ")):
                    language = "python"
                elif any(
                    kw in text.upper() for kw in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE"]
                ):
                    language = "sql"
                else:
                    language = "bash"  # Default to bash

            syntax = Syntax(text, language, theme=self.style, background_color="default")
            with self.console.capture() as capture:
                self.console.print(syntax)
            return capture.get().strip()
        else:
            # Use Pygments auto-detection
            try:
                if language:
                    lexer = get_lexer_by_name(language)
                else:
                    lexer = guess_lexer(text)
            except ClassNotFound:
                lexer = self.bash_lexer

            return highlight(text, lexer, self.formatter).strip()

    def highlight_file(self, file_path: Path) -> str:
        """
        Highlight file contents based on extension.

        Args:
            file_path: Path to file

        Returns:
            Highlighted file contents
        """
        if not file_path.exists():
            return f"File not found: {file_path}"

        try:
            content = file_path.read_text()

            # Determine language from extension
            ext = file_path.suffix.lstrip(".")
            language_map = {
                "py": "python",
                "sh": "bash",
                "bash": "bash",
                "zsh": "bash",
                "fish": "fish",
                "sql": "sql",
                "js": "javascript",
                "ts": "typescript",
                "json": "json",
                "yaml": "yaml",
                "yml": "yaml",
                "toml": "toml",
                "md": "markdown",
                "rst": "rst",
                "c": "c",
                "cpp": "cpp",
                "h": "c",
                "go": "go",
                "rs": "rust",
                "rb": "ruby",
            }

            language = language_map.get(ext, "bash")

            if self.use_rich and self.console:
                syntax = Syntax.from_path(
                    str(file_path), theme=self.style, background_color="default"
                )
                with self.console.capture() as capture:
                    self.console.print(syntax)
                return capture.get().strip()
            else:
                return self.highlight_auto(content, language=language)

        except Exception as e:
            return f"Error highlighting file: {e}"


# Global highlighter instance
_highlighter: SyntaxHighlighter | None = None


def get_highlighter(style: str = "monokai") -> SyntaxHighlighter:
    """
    Get or create global syntax highlighter instance.

    Args:
        style: Pygments color scheme

    Returns:
        SyntaxHighlighter instance
    """
    global _highlighter
    if _highlighter is None:
        _highlighter = SyntaxHighlighter(style=style)
    return _highlighter
