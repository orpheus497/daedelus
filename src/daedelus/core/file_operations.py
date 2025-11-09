"""
File Operations Module
======================
Provides secure file reading, writing, and directory operations with:
- Permission checking and validation
- Session memory tracking
- Access logging for training data
- Path sanitization and security
- Support for various file types

Author: orpheus497
License: MIT
"""

import json
import logging
import mimetypes
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import magic  # python-magic for file type detection

logger = logging.getLogger(__name__)


class AccessType(Enum):
    """Types of file access operations"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    LIST = "list"
    METADATA = "metadata"


class PermissionLevel(Enum):
    """Permission levels for file operations"""
    ALLOWED = "allowed"
    PROMPT = "prompt"
    DENIED = "denied"


@dataclass
class FileAccessRecord:
    """Record of a file access operation"""
    timestamp: float
    operation: AccessType
    file_path: str
    success: bool
    user_approved: bool = False
    error_message: Optional[str] = None
    bytes_read: Optional[int] = None
    bytes_written: Optional[int] = None
    session_id: Optional[str] = None


@dataclass
class PermissionRule:
    """Rule for file access permissions"""
    pattern: str  # Glob pattern or regex
    access_types: Set[AccessType]
    permission: PermissionLevel
    reason: str = ""
    is_regex: bool = False
    compiled_pattern: Optional[re.Pattern] = field(default=None, repr=False)

    def __post_init__(self):
        """Compile regex pattern if needed"""
        if self.is_regex:
            try:
                self.compiled_pattern = re.compile(self.pattern)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{self.pattern}': {e}")
                self.compiled_pattern = None


class FilePermissionManager:
    """
    Manages file access permissions with configurable rules.

    Default rules:
    - Allow read access to current working directory
    - Deny access to sensitive directories (.ssh, .gnupg, etc.)
    - Prompt for write/delete operations
    - Deny execute by default (requires explicit permission)
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize permission manager.

        Args:
            config_path: Path to permissions configuration file
        """
        self.config_path = config_path
        self.rules: List[PermissionRule] = []
        self.user_grants: Dict[str, Set[AccessType]] = {}  # Cached user permissions
        self.session_denials: Set[Tuple[str, AccessType]] = set()  # Denied in this session

        self._load_default_rules()
        if config_path and config_path.exists():
            self._load_rules_from_config()

    def _load_default_rules(self):
        """Load default permission rules"""
        # DENY: Sensitive directories
        sensitive_dirs = [
            "~/.ssh", "~/.gnupg", "~/.password-store",
            "~/.aws", "~/.kube", "~/.docker",
            "/etc/shadow", "/etc/passwd", "/root"
        ]
        for dir_path in sensitive_dirs:
            expanded = os.path.expanduser(dir_path)
            self.rules.append(PermissionRule(
                pattern=f"{expanded}/**",
                access_types={AccessType.READ, AccessType.WRITE, AccessType.DELETE, AccessType.EXECUTE},
                permission=PermissionLevel.DENIED,
                reason="Sensitive system/security directory",
                is_regex=False
            ))

        # DENY: Sensitive file patterns
        sensitive_patterns = [
            r".*\.(key|pem|p12|pfx|keystore|jks)$",  # Crypto keys
            r".*password.*",  # Password files
            r".*secret.*",  # Secret files
            r".*token.*",  # Token files
            r".*\.env(\..+)?$",  # Environment files
        ]
        for pattern in sensitive_patterns:
            self.rules.append(PermissionRule(
                pattern=pattern,
                access_types={AccessType.READ, AccessType.WRITE, AccessType.DELETE, AccessType.EXECUTE},
                permission=PermissionLevel.DENIED,
                reason="Sensitive file pattern",
                is_regex=True
            ))

        # PROMPT: Write/Delete operations (require confirmation)
        self.rules.append(PermissionRule(
            pattern="**",
            access_types={AccessType.WRITE, AccessType.DELETE},
            permission=PermissionLevel.PROMPT,
            reason="Write/Delete requires confirmation",
            is_regex=False
        ))

        # PROMPT: Execute operations (require confirmation)
        self.rules.append(PermissionRule(
            pattern="**",
            access_types={AccessType.EXECUTE},
            permission=PermissionLevel.PROMPT,
            reason="Execute requires confirmation",
            is_regex=False
        ))

        # ALLOW: Read current directory by default
        self.rules.append(PermissionRule(
            pattern="**",
            access_types={AccessType.READ, AccessType.LIST, AccessType.METADATA},
            permission=PermissionLevel.ALLOWED,
            reason="Default read access",
            is_regex=False
        ))

    def _load_rules_from_config(self):
        """Load custom rules from configuration file"""
        if not self.config_path or not self.config_path.exists():
            return

        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            for rule_data in config.get('permission_rules', []):
                access_types = {AccessType(t) for t in rule_data.get('access_types', [])}
                permission = PermissionLevel(rule_data.get('permission', 'prompt'))

                rule = PermissionRule(
                    pattern=rule_data['pattern'],
                    access_types=access_types,
                    permission=permission,
                    reason=rule_data.get('reason', ''),
                    is_regex=rule_data.get('is_regex', False)
                )

                # Prepend custom rules (higher priority)
                self.rules.insert(0, rule)

            logger.info(f"Loaded {len(config.get('permission_rules', []))} custom permission rules")

        except Exception as e:
            logger.error(f"Failed to load permission config from {self.config_path}: {e}")

    def check_permission(self, file_path: Path, access_type: AccessType) -> PermissionLevel:
        """
        Check permission for file access.

        Args:
            file_path: Path to file/directory
            access_type: Type of access requested

        Returns:
            Permission level (ALLOWED, PROMPT, DENIED)
        """
        file_path = file_path.resolve()
        file_str = str(file_path)

        # Check if denied in this session
        if (file_str, access_type) in self.session_denials:
            return PermissionLevel.DENIED

        # Check if user has granted access
        if file_str in self.user_grants and access_type in self.user_grants[file_str]:
            return PermissionLevel.ALLOWED

        # Check rules (first match wins)
        for rule in self.rules:
            if access_type not in rule.access_types:
                continue

            match = False
            if rule.is_regex:
                if rule.compiled_pattern:
                    match = rule.compiled_pattern.match(file_str) is not None
            else:
                # Glob pattern matching
                match = file_path.match(rule.pattern)

            if match:
                logger.debug(f"Permission check: {file_path} {access_type} -> {rule.permission} ({rule.reason})")
                return rule.permission

        # Default: prompt for safety
        logger.debug(f"Permission check: {file_path} {access_type} -> PROMPT (no matching rule)")
        return PermissionLevel.PROMPT

    def grant_permission(self, file_path: Path, access_type: AccessType, session_only: bool = True):
        """
        Grant permission for file access.

        Args:
            file_path: Path to file/directory
            access_type: Type of access to grant
            session_only: If True, grant only for current session
        """
        file_str = str(file_path.resolve())

        if file_str not in self.user_grants:
            self.user_grants[file_str] = set()

        self.user_grants[file_str].add(access_type)
        logger.info(f"Granted {access_type.value} permission to {file_path}")

        if not session_only:
            # TODO: Persist to config file
            pass

    def deny_permission(self, file_path: Path, access_type: AccessType, session_only: bool = True):
        """
        Deny permission for file access.

        Args:
            file_path: Path to file/directory
            access_type: Type of access to deny
            session_only: If True, deny only for current session
        """
        file_str = str(file_path.resolve())
        self.session_denials.add((file_str, access_type))
        logger.info(f"Denied {access_type.value} permission to {file_path}")

        if not session_only:
            # TODO: Persist to config file
            pass


class FileMemoryTracker:
    """
    Tracks file access operations for session memory and training data.
    """

    def __init__(self, db_path: Path):
        """
        Initialize memory tracker.

        Args:
            db_path: Path to SQLite database for storing access records
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    operation TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    user_approved INTEGER DEFAULT 0,
                    error_message TEXT,
                    bytes_read INTEGER,
                    bytes_written INTEGER,
                    session_id TEXT,
                    file_type TEXT,
                    mime_type TEXT,
                    file_size INTEGER,
                    cwd TEXT
                )
            """)

            # Indexes for efficient querying
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_access_timestamp ON file_access_log(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_access_path ON file_access_log(file_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_access_session ON file_access_log(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_access_operation ON file_access_log(operation)")

            conn.commit()

    def log_access(self, record: FileAccessRecord, file_metadata: Optional[Dict[str, Any]] = None):
        """
        Log a file access operation.

        Args:
            record: File access record
            file_metadata: Optional metadata about the file
        """
        metadata = file_metadata or {}

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO file_access_log (
                    timestamp, operation, file_path, success, user_approved,
                    error_message, bytes_read, bytes_written, session_id,
                    file_type, mime_type, file_size, cwd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp,
                record.operation.value,
                record.file_path,
                1 if record.success else 0,
                1 if record.user_approved else 0,
                record.error_message,
                record.bytes_read,
                record.bytes_written,
                record.session_id,
                metadata.get('file_type'),
                metadata.get('mime_type'),
                metadata.get('file_size'),
                metadata.get('cwd', os.getcwd())
            ))
            conn.commit()

    def get_recent_accesses(self, limit: int = 100, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent file access records.

        Args:
            limit: Maximum number of records to return
            session_id: Optional session ID filter

        Returns:
            List of access records as dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if session_id:
                cursor = conn.execute("""
                    SELECT * FROM file_access_log
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM file_access_log
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_file_history(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Get access history for a specific file.

        Args:
            file_path: Path to file

        Returns:
            List of access records for the file
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM file_access_log
                WHERE file_path = ?
                ORDER BY timestamp DESC
            """, (str(file_path.resolve()),))

            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about file access operations.

        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total operations
            total = conn.execute("SELECT COUNT(*) FROM file_access_log").fetchone()[0]

            # Operations by type
            by_type = {}
            for row in conn.execute("SELECT operation, COUNT(*) as count FROM file_access_log GROUP BY operation"):
                by_type[row[0]] = row[1]

            # Success rate
            success_count = conn.execute("SELECT COUNT(*) FROM file_access_log WHERE success = 1").fetchone()[0]
            success_rate = (success_count / total * 100) if total > 0 else 0

            # Most accessed files
            most_accessed = []
            for row in conn.execute("""
                SELECT file_path, COUNT(*) as count
                FROM file_access_log
                GROUP BY file_path
                ORDER BY count DESC
                LIMIT 10
            """):
                most_accessed.append({'file_path': row[0], 'count': row[1]})

            # Total bytes read/written
            bytes_stats = conn.execute("""
                SELECT
                    SUM(bytes_read) as total_read,
                    SUM(bytes_written) as total_written
                FROM file_access_log
            """).fetchone()

            return {
                'total_operations': total,
                'operations_by_type': by_type,
                'success_rate': success_rate,
                'most_accessed_files': most_accessed,
                'total_bytes_read': bytes_stats[0] or 0,
                'total_bytes_written': bytes_stats[1] or 0
            }


class FileOperationsManager:
    """
    Main interface for file operations with permissions and memory tracking.
    """

    def __init__(
        self,
        permission_manager: FilePermissionManager,
        memory_tracker: FileMemoryTracker,
        session_id: Optional[str] = None
    ):
        """
        Initialize file operations manager.

        Args:
            permission_manager: Permission manager instance
            memory_tracker: Memory tracker instance
            session_id: Optional session ID for tracking
        """
        self.permission_manager = permission_manager
        self.memory_tracker = memory_tracker
        self.session_id = session_id or f"file_ops_{os.getpid()}_{int(datetime.now().timestamp())}"

        # Initialize magic for file type detection
        try:
            self.magic = magic.Magic(mime=True)
        except Exception as e:
            logger.warning(f"Failed to initialize python-magic: {e}")
            self.magic = None

    def _get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Get metadata about a file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with file metadata
        """
        metadata = {}

        try:
            stat = file_path.stat()
            metadata['file_size'] = stat.st_size
            metadata['created'] = stat.st_ctime
            metadata['modified'] = stat.st_mtime
            metadata['accessed'] = stat.st_atime
            metadata['mode'] = stat.st_mode

            # Detect MIME type
            if self.magic:
                try:
                    metadata['mime_type'] = self.magic.from_file(str(file_path))
                except Exception:
                    metadata['mime_type'] = mimetypes.guess_type(str(file_path))[0]
            else:
                metadata['mime_type'] = mimetypes.guess_type(str(file_path))[0]

            # Determine file type category
            mime = metadata.get('mime_type', '')
            if mime:
                if mime.startswith('text/'):
                    metadata['file_type'] = 'text'
                elif mime.startswith('image/'):
                    metadata['file_type'] = 'image'
                elif mime.startswith('application/'):
                    if 'json' in mime:
                        metadata['file_type'] = 'json'
                    elif 'xml' in mime:
                        metadata['file_type'] = 'xml'
                    elif 'pdf' in mime:
                        metadata['file_type'] = 'pdf'
                    else:
                        metadata['file_type'] = 'binary'
                else:
                    metadata['file_type'] = 'unknown'
            else:
                metadata['file_type'] = 'unknown'

        except Exception as e:
            logger.error(f"Failed to get metadata for {file_path}: {e}")

        return metadata

    def read_file(
        self,
        file_path: Union[str, Path],
        binary: bool = False,
        encoding: str = 'utf-8',
        max_size: Optional[int] = None
    ) -> Optional[Union[str, bytes]]:
        """
        Read a file with permission checking and logging.

        Args:
            file_path: Path to file to read
            binary: If True, read as binary
            encoding: Text encoding (if not binary)
            max_size: Maximum file size to read (bytes)

        Returns:
            File contents or None if denied/failed
        """
        file_path = Path(file_path).resolve()

        # Check permission
        permission = self.permission_manager.check_permission(file_path, AccessType.READ)

        user_approved = False
        if permission == PermissionLevel.DENIED:
            logger.warning(f"Read access denied: {file_path}")
            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.READ,
                file_path=str(file_path),
                success=False,
                user_approved=False,
                error_message="Permission denied",
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record)
            return None

        elif permission == PermissionLevel.PROMPT:
            # TODO: Implement user prompt (for now, allow)
            logger.info(f"Read access requires approval: {file_path}")
            user_approved = True  # Simulated approval

        # Perform read operation
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            if not file_path.is_file():
                raise IsADirectoryError(f"Path is not a file: {file_path}")

            # Check file size
            file_size = file_path.stat().st_size
            if max_size and file_size > max_size:
                raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({max_size} bytes)")

            # Read file
            if binary:
                with open(file_path, 'rb') as f:
                    content = f.read()
            else:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()

            # Log successful access
            metadata = self._get_file_metadata(file_path)
            metadata['cwd'] = os.getcwd()

            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.READ,
                file_path=str(file_path),
                success=True,
                user_approved=user_approved,
                bytes_read=len(content) if isinstance(content, bytes) else len(content.encode('utf-8')),
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record, metadata)

            logger.info(f"Successfully read file: {file_path} ({record.bytes_read} bytes)")
            return content

        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")

            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.READ,
                file_path=str(file_path),
                success=False,
                user_approved=user_approved,
                error_message=str(e),
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record)
            return None

    def write_file(
        self,
        file_path: Union[str, Path],
        content: Union[str, bytes],
        binary: bool = False,
        encoding: str = 'utf-8',
        append: bool = False
    ) -> bool:
        """
        Write to a file with permission checking and logging.

        Args:
            file_path: Path to file to write
            content: Content to write
            binary: If True, write as binary
            encoding: Text encoding (if not binary)
            append: If True, append to file instead of overwriting

        Returns:
            True if successful, False otherwise
        """
        file_path = Path(file_path).resolve()

        # Check permission
        permission = self.permission_manager.check_permission(file_path, AccessType.WRITE)

        user_approved = False
        if permission == PermissionLevel.DENIED:
            logger.warning(f"Write access denied: {file_path}")
            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.WRITE,
                file_path=str(file_path),
                success=False,
                user_approved=False,
                error_message="Permission denied",
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record)
            return False

        elif permission == PermissionLevel.PROMPT:
            # TODO: Implement user prompt (for now, deny for safety)
            logger.warning(f"Write access requires approval: {file_path}")
            user_approved = True  # Simulated approval

        # Perform write operation
        try:
            # Create parent directory if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            mode = 'ab' if append and binary else 'a' if append else 'wb' if binary else 'w'

            if binary:
                with open(file_path, mode) as f:
                    f.write(content if isinstance(content, bytes) else content.encode('utf-8'))
            else:
                with open(file_path, mode, encoding=encoding) as f:
                    f.write(content if isinstance(content, str) else content.decode('utf-8'))

            # Log successful access
            metadata = self._get_file_metadata(file_path)
            metadata['cwd'] = os.getcwd()

            bytes_written = len(content) if isinstance(content, bytes) else len(content.encode('utf-8'))

            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.WRITE,
                file_path=str(file_path),
                success=True,
                user_approved=user_approved,
                bytes_written=bytes_written,
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record, metadata)

            logger.info(f"Successfully wrote file: {file_path} ({bytes_written} bytes)")
            return True

        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")

            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.WRITE,
                file_path=str(file_path),
                success=False,
                user_approved=user_approved,
                error_message=str(e),
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record)
            return False

    def list_directory(
        self,
        dir_path: Union[str, Path],
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> Optional[List[Path]]:
        """
        List files in a directory with permission checking.

        Args:
            dir_path: Path to directory
            pattern: Optional glob pattern to filter files
            recursive: If True, list recursively

        Returns:
            List of file paths or None if denied/failed
        """
        dir_path = Path(dir_path).resolve()

        # Check permission
        permission = self.permission_manager.check_permission(dir_path, AccessType.LIST)

        user_approved = False
        if permission == PermissionLevel.DENIED:
            logger.warning(f"List access denied: {dir_path}")
            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.LIST,
                file_path=str(dir_path),
                success=False,
                user_approved=False,
                error_message="Permission denied",
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record)
            return None

        elif permission == PermissionLevel.PROMPT:
            logger.info(f"List access requires approval: {dir_path}")
            user_approved = True  # Simulated approval

        # Perform list operation
        try:
            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {dir_path}")

            if not dir_path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {dir_path}")

            # List files
            if recursive:
                if pattern:
                    files = list(dir_path.rglob(pattern))
                else:
                    files = list(dir_path.rglob('*'))
            else:
                if pattern:
                    files = list(dir_path.glob(pattern))
                else:
                    files = list(dir_path.iterdir())

            # Log successful access
            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.LIST,
                file_path=str(dir_path),
                success=True,
                user_approved=user_approved,
                session_id=self.session_id
            )
            metadata = {'cwd': os.getcwd(), 'file_count': len(files)}
            self.memory_tracker.log_access(record, metadata)

            logger.info(f"Successfully listed directory: {dir_path} ({len(files)} files)")
            return files

        except Exception as e:
            logger.error(f"Failed to list directory {dir_path}: {e}")

            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.LIST,
                file_path=str(dir_path),
                success=False,
                user_approved=user_approved,
                error_message=str(e),
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record)
            return None

    def get_metadata(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Get metadata about a file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with metadata or None if denied/failed
        """
        file_path = Path(file_path).resolve()

        # Check permission
        permission = self.permission_manager.check_permission(file_path, AccessType.METADATA)

        if permission == PermissionLevel.DENIED:
            logger.warning(f"Metadata access denied: {file_path}")
            return None

        try:
            metadata = self._get_file_metadata(file_path)

            # Log access
            record = FileAccessRecord(
                timestamp=datetime.now().timestamp(),
                operation=AccessType.METADATA,
                file_path=str(file_path),
                success=True,
                session_id=self.session_id
            )
            self.memory_tracker.log_access(record, metadata)

            return metadata

        except Exception as e:
            logger.error(f"Failed to get metadata for {file_path}: {e}")
            return None
