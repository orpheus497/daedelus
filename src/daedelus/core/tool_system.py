"""
Tool/Plugin Development and Execution System
=============================================
Provides a sandboxed environment for creating, managing, and executing
custom tools and plugins with:
- Tool discovery and registration
- Permission-based execution
- Sandboxed runtime environment
- Tool development templates
- Memory tracking for tool usage
- Tool marketplace/sharing capabilities

Author: orpheus497
License: MIT
"""

import ast
import hashlib
import importlib.util
import inspect
import json
import logging
import os
import signal
import sqlite3
import sys
import tempfile
import textwrap
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type

# RestrictedPython for secure code execution
try:
    from RestrictedPython import compile_restricted, safe_globals, safe_builtins
    from RestrictedPython.Guards import guarded_inplacevar
    RESTRICTED_PYTHON_AVAILABLE = True
except ImportError:
    RESTRICTED_PYTHON_AVAILABLE = False
    logger.warning(
        "RestrictedPython not available - tool sandboxing will use basic exec() (INSECURE). "
        "Install with: pip install RestrictedPython>=6.2"
    )

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


class ToolPermission(Enum):
    """Permission levels for tools"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    NETWORK = "network"
    COMMAND_EXEC = "command_exec"
    SYSTEM_INFO = "system_info"
    USER_INPUT = "user_input"


class ToolCategory(Enum):
    """Categories of tools"""
    UTILITY = "utility"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    TRANSFORMATION = "transformation"
    AUTOMATION = "automation"
    INTEGRATION = "integration"
    CUSTOM = "custom"


@dataclass
class ToolMetadata:
    """Metadata about a tool"""
    name: str
    version: str
    description: str
    author: str
    category: ToolCategory
    permissions: Set[ToolPermission]
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created: Optional[float] = None
    updated: Optional[float] = None
    usage_count: int = 0
    enabled: bool = True


@dataclass
class ToolExecutionResult:
    """Result of tool execution"""
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: float = 0.0
    session_id: Optional[str] = None
    permission_granted: bool = False


class BaseTool(ABC):
    """
    Abstract base class for all tools.

    Custom tools must inherit from this class and implement the execute method.
    """

    def __init__(self, metadata: ToolMetadata):
        """
        Initialize tool.

        Args:
            metadata: Tool metadata
        """
        self.metadata = metadata
        self.logger = logging.getLogger(f"tool.{metadata.name}")

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool output (any type)

        Raises:
            Exception: If execution fails
        """
        pass

    def validate_inputs(self, **kwargs) -> bool:
        """
        Validate input parameters.

        Args:
            **kwargs: Parameters to validate

        Returns:
            True if valid, False otherwise
        """
        return True

    def get_help(self) -> str:
        """
        Get help text for the tool.

        Returns:
            Help text describing usage
        """
        return self.metadata.description

    def get_parameters(self) -> Dict[str, Any]:
        """
        Get parameter schema for the tool.

        Returns:
            Dictionary describing expected parameters
        """
        sig = inspect.signature(self.execute)
        params = {}

        for name, param in sig.parameters.items():
            params[name] = {
                'name': name,
                'type': param.annotation.__name__ if param.annotation != inspect.Parameter.empty else 'any',
                'default': param.default if param.default != inspect.Parameter.empty else None,
                'required': param.default == inspect.Parameter.empty
            }

        return params


class ToolRegistry:
    """
    Registry for managing available tools.
    """

    def __init__(self, db_path: Path, tools_dir: Path):
        """
        Initialize tool registry.

        Args:
            db_path: Path to database for tool metadata
            tools_dir: Directory containing tool plugins
        """
        self.db_path = db_path
        self.tools_dir = tools_dir
        self.tools_dir.mkdir(parents=True, exist_ok=True)

        self.registered_tools: Dict[str, Type[BaseTool]] = {}
        self.tool_instances: Dict[str, BaseTool] = {}

        self._init_database()

    def _init_database(self):
        """Initialize database schema for tool registry"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_registry (
                    name TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    description TEXT,
                    author TEXT,
                    category TEXT,
                    permissions TEXT,
                    dependencies TEXT,
                    tags TEXT,
                    created REAL,
                    updated REAL,
                    usage_count INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    source_path TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    tool_name TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    duration REAL,
                    session_id TEXT,
                    error_message TEXT,
                    permission_granted INTEGER DEFAULT 0
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_exec_timestamp ON tool_executions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_exec_name ON tool_executions(tool_name)")

            conn.commit()

    def register_tool(self, tool_class: Type[BaseTool], source_path: Optional[Path] = None) -> bool:
        """
        Register a tool class.

        Args:
            tool_class: Tool class to register
            source_path: Optional path to source file

        Returns:
            True if registered successfully
        """
        try:
            # Create instance to get metadata
            temp_instance = tool_class(ToolMetadata(
                name="temp",
                version="0.0.0",
                description="",
                author="",
                category=ToolCategory.CUSTOM,
                permissions=set()
            ))

            metadata = temp_instance.metadata

            # Store in registry
            self.registered_tools[metadata.name] = tool_class

            # Save to database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tool_registry (
                        name, version, description, author, category, permissions,
                        dependencies, tags, created, updated, enabled, source_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metadata.name,
                    metadata.version,
                    metadata.description,
                    metadata.author,
                    metadata.category.value,
                    json.dumps([p.value for p in metadata.permissions]),
                    json.dumps(metadata.dependencies),
                    json.dumps(metadata.tags),
                    metadata.created or datetime.now().timestamp(),
                    datetime.now().timestamp(),
                    1 if metadata.enabled else 0,
                    str(source_path) if source_path else None
                ))
                conn.commit()

            logger.info(f"Registered tool: {metadata.name} v{metadata.version}")
            return True

        except Exception as e:
            logger.error(f"Failed to register tool: {e}")
            return False

    def load_tool(self, name: str) -> Optional[BaseTool]:
        """
        Load a tool instance.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        if name in self.tool_instances:
            return self.tool_instances[name]

        if name not in self.registered_tools:
            logger.warning(f"Tool not found: {name}")
            return None

        try:
            # Load metadata from database
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM tool_registry WHERE name = ?", (name,)).fetchone()

                if not row:
                    return None

                metadata = ToolMetadata(
                    name=row['name'],
                    version=row['version'],
                    description=row['description'],
                    author=row['author'],
                    category=ToolCategory(row['category']),
                    permissions={ToolPermission(p) for p in json.loads(row['permissions'])},
                    dependencies=json.loads(row['dependencies']) if row['dependencies'] else [],
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    created=row['created'],
                    updated=row['updated'],
                    usage_count=row['usage_count'],
                    enabled=bool(row['enabled'])
                )

            # Create instance
            tool_class = self.registered_tools[name]
            instance = tool_class(metadata)

            self.tool_instances[name] = instance
            return instance

        except Exception as e:
            logger.error(f"Failed to load tool {name}: {e}")
            return None

    def discover_tools(self) -> int:
        """
        Discover and load tools from tools directory.

        Returns:
            Number of tools discovered
        """
        count = 0

        for file_path in self.tools_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            try:
                # Load module
                spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                if not spec or not spec.loader:
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[file_path.stem] = module
                spec.loader.exec_module(module)

                # Find tool classes
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseTool) and obj != BaseTool:
                        if self.register_tool(obj, file_path):
                            count += 1

            except Exception as e:
                logger.error(f"Failed to load tool from {file_path}: {e}")

        logger.info(f"Discovered {count} tools")
        return count

    def list_tools(self, category: Optional[ToolCategory] = None, enabled_only: bool = True) -> List[ToolMetadata]:
        """
        List available tools.

        Args:
            category: Optional category filter
            enabled_only: If True, only return enabled tools

        Returns:
            List of tool metadata
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM tool_registry WHERE 1=1"
            params = []

            if category:
                query += " AND category = ?"
                params.append(category.value)

            if enabled_only:
                query += " AND enabled = 1"

            query += " ORDER BY name"

            tools = []
            for row in conn.execute(query, params):
                metadata = ToolMetadata(
                    name=row['name'],
                    version=row['version'],
                    description=row['description'],
                    author=row['author'],
                    category=ToolCategory(row['category']),
                    permissions={ToolPermission(p) for p in json.loads(row['permissions'])},
                    dependencies=json.loads(row['dependencies']) if row['dependencies'] else [],
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    created=row['created'],
                    updated=row['updated'],
                    usage_count=row['usage_count'],
                    enabled=bool(row['enabled'])
                )
                tools.append(metadata)

            return tools

    def unregister_tool(self, name: str) -> bool:
        """
        Unregister a tool.

        Args:
            name: Tool name

        Returns:
            True if unregistered successfully
        """
        try:
            self.registered_tools.pop(name, None)
            self.tool_instances.pop(name, None)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM tool_registry WHERE name = ?", (name,))
                conn.commit()

            logger.info(f"Unregistered tool: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unregister tool {name}: {e}")
            return False


class ToolExecutor:
    """
    Executes tools with permission checking and sandboxing.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        session_id: Optional[str] = None,
        require_permission_approval: bool = True
    ):
        """
        Initialize tool executor.

        Args:
            registry: Tool registry instance
            session_id: Optional session ID
            require_permission_approval: If True, prompt for permission approval
        """
        self.registry = registry
        self.session_id = session_id or f"tool_{os.getpid()}_{int(datetime.now().timestamp())}"
        self.require_permission_approval = require_permission_approval

        # Track granted permissions per tool
        self.granted_permissions: Dict[str, Set[ToolPermission]] = {}

    def execute_tool(
        self,
        tool_name: str,
        sandboxed: bool = False,
        **kwargs
    ) -> ToolExecutionResult:
        """
        Execute a tool with permission checking.

        Args:
            tool_name: Name of tool to execute
            sandboxed: If True, execute in sandbox
            **kwargs: Tool parameters

        Returns:
            ToolExecutionResult
        """
        import time
        start_time = time.time()

        result = ToolExecutionResult(
            tool_name=tool_name,
            success=False,
            timestamp=datetime.now().timestamp(),
            session_id=self.session_id
        )

        try:
            # Load tool
            tool = self.registry.load_tool(tool_name)
            if not tool:
                result.error = f"Tool not found: {tool_name}"
                self._log_execution(result)
                return result

            # Check if enabled
            if not tool.metadata.enabled:
                result.error = f"Tool is disabled: {tool_name}"
                self._log_execution(result)
                return result

            # Check permissions
            if not self._check_permissions(tool):
                result.error = "Permission denied"
                self._log_execution(result)
                return result

            result.permission_granted = True

            # Validate inputs
            if not tool.validate_inputs(**kwargs):
                result.error = "Invalid input parameters"
                self._log_execution(result)
                return result

            # Execute tool
            if sandboxed:
                output = self._execute_sandboxed(tool, kwargs)
            else:
                output = tool.execute(**kwargs)

            result.success = True
            result.output = output

            # Update usage count
            self._increment_usage(tool_name)

        except Exception as e:
            logger.error(f"Tool execution failed ({tool_name}): {e}")
            logger.debug(traceback.format_exc())
            result.error = str(e)

        finally:
            result.duration = time.time() - start_time
            self._log_execution(result)

        return result

    def _check_permissions(self, tool: BaseTool) -> bool:
        """
        Check if tool has required permissions.

        Args:
            tool: Tool to check

        Returns:
            True if permissions granted
        """
        tool_name = tool.metadata.name
        required_perms = tool.metadata.permissions

        # Check if already granted
        if tool_name in self.granted_permissions:
            if required_perms.issubset(self.granted_permissions[tool_name]):
                return True

        # If no permissions required, allow
        if not required_perms:
            return True

        # Check if approval required
        if self.require_permission_approval:
            logger.info(f"Tool {tool_name} requires permissions: {[p.value for p in required_perms]}")

            # Prompt user for permission
            try:
                import click
                perms_str = ", ".join([p.value for p in required_perms])
                message = f"Tool '{tool_name}' requires these permissions: {perms_str}. Grant access?"

                if click.confirm(message, default=False):
                    # User approved - grant permissions
                    if tool_name not in self.granted_permissions:
                        self.granted_permissions[tool_name] = set()
                    self.granted_permissions[tool_name].update(required_perms)
                    logger.info(f"Permissions granted to tool {tool_name}")
                    return True
                else:
                    # User denied
                    logger.info(f"Permissions denied for tool {tool_name}")
                    return False
            except Exception as e:
                # If we can't prompt (non-interactive), default to deny for security
                logger.warning(f"Could not prompt for permissions (non-interactive?): {e}")
                return False

        return True

    def _validate_tool_code(self, source: str, tool_name: str) -> tuple[bool, Optional[str]]:
        """
        Validate tool code using AST analysis.

        Args:
            source: Tool source code
            tool_name: Tool name for logging

        Returns:
            Tuple of (is_valid, error_message)
        """
        ALLOWED_IMPORTS = {'json', 'datetime', 're', 'math', 'collections', 'itertools'}
        FORBIDDEN_NAMES = {
            'exec', 'eval', 'compile', '__import__', 'open', 'file',
            'input', 'raw_input', 'reload', 'breakpoint',
            'exit', 'quit', 'help', 'license', 'copyright', 'credits'
        }

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Walk AST and check for forbidden operations
        for node in ast.walk(tree):
            # Check for forbidden names
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                return False, f"Forbidden operation: {node.id}"

            # Check for forbidden function calls
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'id') and node.func.id in FORBIDDEN_NAMES:
                    return False, f"Forbidden function call: {node.func.id}"

            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in ALLOWED_IMPORTS:
                        return False, f"Forbidden import: {alias.name}"

            # Check from imports
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module not in ALLOWED_IMPORTS:
                    return False, f"Forbidden import from: {node.module}"

        return True, None

    def _audit_log_execution(
        self,
        tool_name: str,
        source: str,
        params: Dict[str, Any],
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Log tool execution to audit log for security monitoring.

        Args:
            tool_name: Name of the tool
            source: Tool source code
            params: Parameters passed
            success: Whether execution succeeded
            error: Error message if failed
        """
        audit_log_path = Path.home() / '.local/share/daedelus/audit.jsonl'
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'tool_execution',
            'tool_name': tool_name,
            'code_hash': hashlib.sha256(source.encode()).hexdigest(),
            'param_keys': list(params.keys()),
            'success': success,
            'error': error,
        }

        try:
            with open(audit_log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

    def _execute_sandboxed(self, tool: BaseTool, params: Dict[str, Any]) -> Any:
        """
        Execute tool in sandboxed environment using RestrictedPython.

        This method provides defense-in-depth security:
        1. AST validation to detect forbidden operations
        2. RestrictedPython compilation for safe execution
        3. Timeout enforcement to prevent infinite loops
        4. Audit logging for security monitoring

        Args:
            tool: Tool to execute
            params: Parameters

        Returns:
            Tool output

        Raises:
            SecurityError: If code validation fails
            TimeoutError: If execution exceeds timeout
            RuntimeError: If execution fails
        """
        tool_name = tool.metadata.name
        timeout = 5.0  # 5 second timeout for tool execution

        try:
            # Get execute method code
            source = inspect.getsource(tool.execute)

            # Step 1: AST Validation
            is_valid, error_msg = self._validate_tool_code(source, tool_name)
            if not is_valid:
                logger.error(f"Tool {tool_name} failed validation: {error_msg}")
                self._audit_log_execution(tool_name, source, params, False, error_msg)
                raise SecurityError(f"Tool code validation failed: {error_msg}")

            # Step 2: Use RestrictedPython if available, otherwise fall back
            if RESTRICTED_PYTHON_AVAILABLE:
                return self._execute_with_restricted_python(
                    tool, tool_name, source, params, timeout
                )
            else:
                logger.warning(
                    f"Executing tool {tool_name} with INSECURE basic sandbox. "
                    "Install RestrictedPython for security: pip install RestrictedPython>=6.2"
                )
                return self._execute_with_basic_sandbox(
                    tool, tool_name, source, params, timeout
                )

        except Exception as e:
            self._audit_log_execution(tool_name, source if 'source' in locals() else '', params, False, str(e))
            raise

    def _execute_with_restricted_python(
        self,
        tool: BaseTool,
        tool_name: str,
        source: str,
        params: Dict[str, Any],
        timeout: float
    ) -> Any:
        """
        Execute tool using RestrictedPython (SECURE).

        Args:
            tool: Tool instance
            tool_name: Tool name
            source: Tool source code
            params: Parameters
            timeout: Execution timeout in seconds

        Returns:
            Tool output
        """
        # Compile with RestrictedPython
        byte_code = compile_restricted(
            source,
            filename=f'<tool:{tool_name}>',
            mode='exec'
        )

        if byte_code.errors:
            error_msg = f"RestrictedPython compilation errors: {byte_code.errors}"
            logger.error(error_msg)
            raise SecurityError(error_msg)

        # Set up restricted environment
        restricted_globals = {
            '__builtins__': safe_builtins,
            '_getattr_': getattr,
            '_getitem_': lambda obj, key: obj[key],
            '_write_': lambda obj: obj,
            '_inplacevar_': guarded_inplacevar,
            **safe_globals,
            # Allowed safe modules
            'json': __import__('json'),
            'datetime': __import__('datetime'),
            're': __import__('re'),
            'math': __import__('math'),
            'collections': __import__('collections'),
            'itertools': __import__('itertools'),
        }

        restricted_locals = {'params': params}

        # Execute with timeout using signal
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Tool execution timeout after {timeout}s")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))

        try:
            # Execute the compiled code
            exec(byte_code.code, restricted_globals, restricted_locals)

            # Call execute function
            execute_func = restricted_locals.get('execute')
            if execute_func:
                result = execute_func(tool, **params)
                self._audit_log_execution(tool_name, source, params, True)
                return result
            else:
                raise RuntimeError("Execute method not found in sandbox")

        finally:
            signal.alarm(0)  # Cancel alarm
            signal.signal(signal.SIGALRM, old_handler)  # Restore handler

    def _execute_with_basic_sandbox(
        self,
        tool: BaseTool,
        tool_name: str,
        source: str,
        params: Dict[str, Any],
        timeout: float
    ) -> Any:
        """
        Execute tool using basic sandbox (INSECURE - fallback only).

        This is a fallback when RestrictedPython is not available.
        It provides minimal security and should not be used in production.

        Args:
            tool: Tool instance
            tool_name: Tool name
            source: Tool source code
            params: Parameters
            timeout: Execution timeout in seconds

        Returns:
            Tool output
        """
        # Create isolated namespace with limited builtins
        sandbox_globals = {
            '__builtins__': {
                'len': len, 'str': str, 'int': int, 'float': float,
                'bool': bool, 'list': list, 'dict': dict, 'tuple': tuple,
                'set': set, 'range': range, 'enumerate': enumerate,
                'zip': zip, 'map': map, 'filter': filter,
                'sum': sum, 'min': min, 'max': max, 'abs': abs,
                'round': round, 'sorted': sorted, 'reversed': reversed,
                'any': any, 'all': all, 'print': print,
            }
        }

        sandbox_locals = {'params': params}

        # Execute with timeout
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Tool execution timeout after {timeout}s")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))

        try:
            # Compile and execute
            code = compile(source, f'<tool:{tool_name}>', 'exec')
            exec(code, sandbox_globals, sandbox_locals)

            # Call execute function
            execute_func = sandbox_locals.get('execute')
            if execute_func:
                result = execute_func(tool, **params)
                self._audit_log_execution(tool_name, source, params, True)
                return result
            else:
                raise RuntimeError("Execute method not found in sandbox")

        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def _log_execution(self, result: ToolExecutionResult):
        """Log tool execution to database"""
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.execute("""
                INSERT INTO tool_executions (
                    timestamp, tool_name, success, duration,
                    session_id, error_message, permission_granted
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.timestamp,
                result.tool_name,
                1 if result.success else 0,
                result.duration,
                result.session_id,
                result.error,
                1 if result.permission_granted else 0
            ))
            conn.commit()

    def _increment_usage(self, tool_name: str):
        """Increment usage count for tool"""
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.execute("""
                UPDATE tool_registry
                SET usage_count = usage_count + 1
                WHERE name = ?
            """, (tool_name,))
            conn.commit()


class ToolDeveloper:
    """
    Helps develop new tools with templates and validation.
    """

    @staticmethod
    def create_tool_template(
        name: str,
        category: ToolCategory,
        permissions: List[ToolPermission],
        output_path: Path
    ) -> bool:
        """
        Create a new tool from template.

        Args:
            name: Tool name
            category: Tool category
            permissions: Required permissions
            output_path: Path to save tool file

        Returns:
            True if created successfully
        """
        template = textwrap.dedent(f'''
            """
            {name} Tool
            {'=' * (len(name) + 5)}

            [Add description here]

            Author: [Your name]
            Created: {datetime.now().strftime('%Y-%m-%d')}
            """

            from daedelus.core.tool_system import BaseTool, ToolMetadata, ToolCategory, ToolPermission
            from typing import Any


            class {name.replace('_', ' ').title().replace(' ', '')}Tool(BaseTool):
                """
                {name} tool implementation.
                """

                def __init__(self, metadata: ToolMetadata):
                    """Initialize tool"""
                    super().__init__(metadata or ToolMetadata(
                        name="{name}",
                        version="0.1.0",
                        description="[Add description]",
                        author="[Your name]",
                        category=ToolCategory.{category.name},
                        permissions={{{', '.join(f'ToolPermission.{p.name}' for p in permissions)}}},
                        tags=[]
                    ))

                def execute(self, **kwargs) -> Any:
                    """
                    Execute the tool.

                    This method must be overridden to implement the actual tool functionality.
                    The example below shows the expected structure of the return value.

                    Args:
                        **kwargs: Tool parameters (specific to your tool implementation)

                    Returns:
                        Tool output (typically Dict containing status, message, and data)

                    Example Implementation:
                        def execute(self, input_file: str, output_format: str = 'json') -> Dict[str, Any]:
                            try:
                                # Your tool logic here
                                data = self.process_file(input_file, output_format)
                                return {{
                                    'status': 'success',
                                    'message': f'Processed {{input_file}} successfully',
                                    'data': data
                                }}
                            except Exception as e:
                                self.logger.error(f"Tool execution failed: {{e}}")
                                return {{
                                    'status': 'error',
                                    'message': str(e),
                                    'data': None
                                }}
                    """
                    # TEMPLATE: Replace this with your actual tool implementation
                    self.logger.info(f"Executing {name} with params: {{kwargs}}")

                    # Example structure - modify as needed
                    result = {{
                        'status': 'success',
                        'message': 'Tool executed successfully',
                        'data': {{}}
                    }}

                    return result

                def validate_inputs(self, **kwargs) -> bool:
                    """
                    Validate input parameters before execution.

                    Override this method to implement custom validation logic for your tool.
                    This is called automatically before execute() to ensure inputs are safe.

                    Args:
                        **kwargs: Parameters to validate (specific to your tool)

                    Returns:
                        True if all inputs are valid, False otherwise

                    Example Implementation:
                        def validate_inputs(self, input_file: str, output_format: str = 'json') -> bool:
                            # Check file exists and is readable
                            if not Path(input_file).exists():
                                self.logger.error(f"Input file not found: {{input_file}}")
                                return False

                            if not os.access(input_file, os.R_OK):
                                self.logger.error(f"Cannot read input file: {{input_file}}")
                                return False

                            # Validate output format
                            valid_formats = ['json', 'xml', 'csv']
                            if output_format not in valid_formats:
                                self.logger.error(f"Invalid format: {{output_format}}")
                                return False

                            return True
                    """
                    # TEMPLATE: Add your validation logic here
                    # Default: accept all inputs (override for custom validation)
                    return True

                def get_help(self) -> str:
                    """Get help text for the tool"""
                    return """
                    {name} Tool Help
                    {'=' * (len(name) + 10)}

                    Usage:
                        Execute this tool with the following parameters:

                        [Add parameter documentation here]

                    Examples:
                        [Add usage examples here]
                    """
        ''').strip()

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(template)

            logger.info(f"Created tool template: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create tool template: {e}")
            return False

    @staticmethod
    def validate_tool_code(tool_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate tool code for safety and correctness.

        Args:
            tool_path: Path to tool file

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        try:
            with open(tool_path, 'r') as f:
                code = f.read()

            # Parse AST
            tree = ast.parse(code)

            # Check for dangerous patterns
            dangerous_imports = ['os', 'subprocess', 'sys', 'eval', 'exec', '__import__']

            for node in ast.walk(tree):
                # Check imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(d in alias.name for d in dangerous_imports):
                            errors.append(f"Potentially dangerous import: {alias.name}")

                if isinstance(node, ast.ImportFrom):
                    if node.module and any(d in node.module for d in dangerous_imports):
                        errors.append(f"Potentially dangerous import: {node.module}")

                # Check for eval/exec calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', '__import__']:
                            errors.append(f"Dangerous function call: {node.func.id}")

            # Check for BaseTool subclass
            has_tool_class = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == 'BaseTool':
                            has_tool_class = True
                            break

            if not has_tool_class:
                errors.append("No BaseTool subclass found")

            return len(errors) == 0, errors

        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
            return False, errors

        except Exception as e:
            errors.append(f"Validation error: {e}")
            return False, errors
