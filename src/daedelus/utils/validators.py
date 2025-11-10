"""
Input Validation Layer for Security and User Experience
========================================================
Centralized input validation to prevent security vulnerabilities and provide
helpful error messages.

Security Features:
- Path traversal prevention
- Command injection prevention
- SQL injection prevention
- Shell metacharacter blocking
- Type and range validation

Author: orpheus497
License: MIT
Created: 2025-11-10
"""

import re
from pathlib import Path
from typing import Any, List, Optional, Union

# Custom exceptions for different validation failures
class ValidationError(ValueError):
    """Base validation error."""
    pass


class SecurityError(Exception):
    """Security validation failed - potential attack detected."""
    pass


class InputValidator:
    """
    Centralized input validation utilities.

    Provides secure validation for all user inputs including:
    - File paths (with traversal prevention)
    - Query strings (with injection prevention)
    - Command arguments (with shell safety)
    - Configuration values (with type/range checking)
    - Model paths (with format validation)
    """

    # Security patterns - patterns that indicate potential attacks
    SHELL_METACHARACTERS = ['|', '&', ';', '\n', '>', '<', '`', '$', '(', ')', '{', '}', '*', '?', '[', ']']
    SQL_INJECTION_PATTERNS = [
        r"['\";].*(--)|(;)|(\b(OR|AND)\b.*=)",
        r"\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC)\b",
        r"(\%27)|(')|(--)|(\%23)|(#)",  # URL-encoded
    ]

    # Allowed base directories for file operations
    DEFAULT_ALLOWED_BASES = [
        Path.home() / '.local/share/daedelus',
        Path.home() / '.config/daedelus',
        Path.home() / '.cache/daedelus',
    ]

    @staticmethod
    def validate_model_path(
        path: Union[str, Path],
        must_exist: bool = True
    ) -> Path:
        """
        Validate model file path.

        Security checks:
        - Resolves to absolute path
        - Checks existence if required
        - Validates file extension
        - Checks reasonable file size

        Args:
            path: Path to model file
            must_exist: Whether file must exist

        Returns:
            Resolved absolute path

        Raises:
            FileNotFoundError: If file doesn't exist and must_exist=True
            ValueError: If path format is invalid
            SecurityError: If path is suspicious

        Example:
            >>> path = InputValidator.validate_model_path("~/.local/share/models/model.gguf")
            >>> print(path)
            Path('/home/user/.local/share/models/model.gguf')
        """
        try:
            path = Path(path).expanduser().resolve()
        except (ValueError, RuntimeError) as e:
            raise ValueError(f"Invalid path format: {e}")

        # Check existence
        if must_exist and not path.exists():
            raise FileNotFoundError(
                f"Model not found: {path}\n"
                f"Hint: Use 'daedelus model download' to download models or check the path"
            )

        # Check is file (not directory)
        if path.exists() and not path.is_file():
            raise ValueError(f"Not a file: {path}")

        # Check extension
        valid_extensions = ['.gguf', '.bin', '.pt', '.pth', '.safetensors', '.onnx']
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(
                f"Invalid model format: {path.suffix}\n"
                f"Supported formats: {', '.join(valid_extensions)}"
            )

        # Check size (reasonable for LLM model: 10MB - 100GB)
        if path.exists():
            size_bytes = path.stat().st_size
            size_mb = size_bytes / (1024**2)
            size_gb = size_bytes / (1024**3)

            if size_mb < 10:  # < 10MB
                raise ValueError(
                    f"Model suspiciously small: {size_mb:.1f}MB\n"
                    f"Typical models are 500MB - 10GB"
                )

            if size_gb > 100:  # > 100GB
                raise ValueError(
                    f"Model suspiciously large: {size_gb:.1f}GB\n"
                    f"Consider using a quantized model (Q4 or Q8)"
                )

        return path

    @staticmethod
    def validate_query(
        query: str,
        max_length: int = 1000,
        min_length: int = 1
    ) -> str:
        """
        Validate search query string.

        Security checks:
        - Length limits
        - Control character removal
        - SQL injection pattern detection

        Args:
            query: Query string
            max_length: Maximum allowed length
            min_length: Minimum required length

        Returns:
            Cleaned query string

        Raises:
            ValueError: If query is invalid
            SecurityError: If query contains suspicious patterns

        Example:
            >>> query = InputValidator.validate_query("git commit")
            >>> print(query)
            'git commit'
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        query = query.strip()

        # Check length
        if len(query) < min_length:
            raise ValueError(f"Query too short (minimum {min_length} character{'s' if min_length != 1 else ''})")

        if len(query) > max_length:
            raise ValueError(
                f"Query too long (maximum {max_length} characters)\n"
                f"Got: {len(query)} characters"
            )

        # Remove control characters but keep whitespace
        query = ''.join(char for char in query if char.isprintable() or char.isspace())

        # Check for SQL injection patterns (defense in depth)
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                raise SecurityError(
                    "Query contains potentially unsafe SQL patterns\n"
                    f"Pattern detected: {pattern}\n"
                    "Hint: Avoid SQL keywords and special characters in queries"
                )

        return query

    @staticmethod
    def validate_path_traversal(
        path: Union[str, Path],
        base_dir: Optional[Path] = None,
        must_exist: bool = False
    ) -> Path:
        """
        Prevent path traversal attacks.

        Security checks:
        - Resolves to absolute path
        - Validates path is within allowed directories
        - Checks for suspicious patterns (.., symlinks)

        Args:
            path: Path to validate
            base_dir: Base directory (if None, uses common allowed dirs)
            must_exist: Whether path must exist

        Returns:
            Validated absolute path

        Raises:
            SecurityError: If path traversal detected
            FileNotFoundError: If path doesn't exist and must_exist=True

        Example:
            >>> path = InputValidator.validate_path_traversal("data/file.txt")
            >>> print(path)
            Path('/home/user/.local/share/daedelus/data/file.txt')
        """
        try:
            path = Path(path).expanduser().resolve()
        except (ValueError, RuntimeError) as e:
            raise SecurityError(f"Invalid path: {e}")

        # Default allowed base directories
        if base_dir is None:
            allowed_bases = InputValidator.DEFAULT_ALLOWED_BASES + [Path.cwd()]
        else:
            allowed_bases = [base_dir.resolve()]

        # Check if path is within allowed directories
        is_allowed = False
        for base in allowed_bases:
            try:
                # Check if path is relative to base
                path.relative_to(base)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            raise SecurityError(
                f"Path outside allowed directories: {path}\n"
                f"Allowed directories:\n" +
                '\n'.join(f"  - {base}" for base in allowed_bases) +
                "\n\nHint: Use paths within ~/.local/share/daedelus, ~/.config/daedelus, or current directory"
            )

        # Check existence if required
        if must_exist and not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        # Check for symlinks (potential security risk)
        if path.exists() and path.is_symlink():
            # Follow symlink and re-validate
            real_path = path.resolve()
            return InputValidator.validate_path_traversal(real_path, base_dir, must_exist=False)

        return path

    @staticmethod
    def validate_command_arg(
        arg: str,
        allow_empty: bool = False
    ) -> str:
        """
        Validate command-line argument for safety.

        Security checks:
        - Empty string validation
        - Shell metacharacter detection
        - Null byte detection

        Args:
            arg: Argument to validate
            allow_empty: Whether to allow empty strings

        Returns:
            Validated argument

        Raises:
            ValueError: If argument is invalid
            SecurityError: If argument contains shell metacharacters

        Example:
            >>> arg = InputValidator.validate_command_arg("commit message")
            >>> print(arg)
            'commit message'
        """
        if not allow_empty and not arg:
            raise ValueError("Argument cannot be empty")

        # Check for null bytes (path/command injection)
        if '\x00' in arg:
            raise SecurityError("Argument contains null bytes")

        # Check for shell metacharacters
        dangerous_chars = []
        for char in InputValidator.SHELL_METACHARACTERS:
            if char in arg:
                dangerous_chars.append(char)

        if dangerous_chars:
            raise SecurityError(
                f"Argument contains shell metacharacters: {dangerous_chars}\n"
                f"Forbidden characters: {InputValidator.SHELL_METACHARACTERS}\n"
                "Hint: These characters could be used for command injection"
            )

        return arg

    @staticmethod
    def validate_config_value(
        value: Any,
        expected_type: type,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        allowed_values: Optional[List[Any]] = None
    ) -> Any:
        """
        Validate configuration value.

        Args:
            value: Value to validate
            expected_type: Expected Python type
            min_value: Minimum allowed value (for numbers)
            max_value: Maximum allowed value (for numbers)
            allowed_values: List of allowed values (enum-style)

        Returns:
            Validated value

        Raises:
            ValueError: If validation fails

        Example:
            >>> value = InputValidator.validate_config_value(10, int, min_value=1, max_value=100)
            >>> print(value)
            10
        """
        # Type check
        if not isinstance(value, expected_type):
            raise ValueError(
                f"Invalid type: expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )

        # Range check for numbers
        if isinstance(value, (int, float)):
            if min_value is not None and value < min_value:
                raise ValueError(
                    f"Value {value} below minimum {min_value}\n"
                    f"Hint: Use a value between {min_value} and {max_value or 'infinity'}"
                )
            if max_value is not None and value > max_value:
                raise ValueError(
                    f"Value {value} above maximum {max_value}\n"
                    f"Hint: Use a value between {min_value or '-infinity'} and {max_value}"
                )

        # Enum check
        if allowed_values is not None and value not in allowed_values:
            raise ValueError(
                f"Invalid value: {value}\n"
                f"Allowed values: {', '.join(map(str, allowed_values))}"
            )

        return value

    @staticmethod
    def validate_port(port: Union[int, str]) -> int:
        """
        Validate port number.

        Args:
            port: Port number (int or string)

        Returns:
            Valid port number

        Raises:
            ValueError: If port is invalid

        Example:
            >>> port = InputValidator.validate_port(8080)
            >>> print(port)
            8080
        """
        try:
            port = int(port)
        except (ValueError, TypeError):
            raise ValueError(f"Port must be an integer, got: {port}")

        if not (1 <= port <= 65535):
            raise ValueError(
                f"Port {port} out of valid range (1-65535)\n"
                f"Hint: Use a port between 1024 and 65535 (unprivileged ports)"
            )

        if port < 1024:
            import os
            if os.geteuid() != 0:  # Not root
                raise ValueError(
                    f"Port {port} requires root privileges (< 1024)\n"
                    f"Hint: Use a port >= 1024 for unprivileged execution"
                )

        return port

    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> str:
        """
        Validate URL format.

        Args:
            url: URL to validate
            allowed_schemes: List of allowed schemes (default: ['http', 'https'])

        Returns:
            Validated URL

        Raises:
            ValueError: If URL is invalid

        Example:
            >>> url = InputValidator.validate_url("https://example.com")
            >>> print(url)
            'https://example.com'
        """
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")

        url = url.strip()

        # Default allowed schemes
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']

        # Simple URL validation
        url_pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, url, re.IGNORECASE):
            raise ValueError(
                f"Invalid URL format: {url}\n"
                f"Hint: URLs should start with {' or '.join(allowed_schemes)}://"
            )

        # Check scheme
        scheme = url.split('://')[0].lower()
        if scheme not in allowed_schemes:
            raise ValueError(
                f"URL scheme '{scheme}' not allowed\n"
                f"Allowed schemes: {', '.join(allowed_schemes)}"
            )

        return url

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """
        Sanitize filename by removing/replacing dangerous characters.

        Args:
            filename: Original filename
            max_length: Maximum filename length

        Returns:
            Sanitized filename

        Example:
            >>> filename = InputValidator.sanitize_filename("my file!@#.txt")
            >>> print(filename)
            'my_file___.txt'
        """
        if not filename:
            raise ValueError("Filename cannot be empty")

        # Remove path separators and null bytes
        filename = filename.replace('/', '_').replace('\\', '_').replace('\x00', '')

        # Remove or replace other dangerous characters
        dangerous = ['<', '>', ':', '"', '|', '?', '*', '\n', '\r', '\t']
        for char in dangerous:
            filename = filename.replace(char, '_')

        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')

        # Ensure not empty after sanitization
        if not filename:
            filename = 'unnamed'

        # Truncate if too long
        if len(filename) > max_length:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            name = name[:max_length - len(ext) - 1]
            filename = f"{name}.{ext}" if ext else name

        return filename


class SecurityValidator:
    """
    Advanced security validation utilities.

    Provides additional security checks beyond basic input validation.
    """

    @staticmethod
    def validate_python_identifier(name: str) -> str:
        """
        Validate that a string is a valid Python identifier.

        Args:
            name: String to validate

        Returns:
            Validated identifier

        Raises:
            ValueError: If not a valid identifier
        """
        if not name.isidentifier():
            raise ValueError(
                f"Invalid Python identifier: {name}\n"
                "Hint: Must start with letter/underscore, contain only letters/digits/underscores"
            )

        # Check against Python keywords
        import keyword
        if keyword.iskeyword(name):
            raise ValueError(
                f"Cannot use Python keyword as identifier: {name}"
            )

        return name

    @staticmethod
    def validate_regex_pattern(pattern: str, max_length: int = 1000) -> str:
        """
        Validate regex pattern (prevent ReDoS attacks).

        Args:
            pattern: Regex pattern to validate
            max_length: Maximum pattern length

        Returns:
            Validated pattern

        Raises:
            ValueError: If pattern is invalid or dangerous
        """
        if len(pattern) > max_length:
            raise ValueError(
                f"Regex pattern too long ({len(pattern)} chars, max {max_length})\n"
                "Hint: Complex regexes can cause ReDoS attacks"
            )

        # Count repetition operators (*, +, {n,m})
        repetitions = pattern.count('*') + pattern.count('+') + pattern.count('{')
        if repetitions > 10:
            raise ValueError(
                f"Too many repetition operators in regex ({repetitions})\n"
                "Hint: Excessive repetitions can cause ReDoS attacks"
            )

        # Try to compile pattern
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        return pattern
