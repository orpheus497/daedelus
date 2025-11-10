"""
System Integration Module
==========================
Integrates all Daedelus subsystems into a cohesive whole:
- File operations
- Command execution
- Tool system
- Document ingestion
- Training data organization
- Memory tracking

Provides unified API for accessing all features.

Author: orpheus497
License: MIT
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.config import Config
from .file_operations import (
    FileOperationsManager,
    FilePermissionManager,
    FileMemoryTracker
)
from .command_executor import (
    CommandExecutor,
    CommandExecutionMemory,
    ExecutionMode,
    InteractiveShell
)
from .tool_system import (
    ToolRegistry,
    ToolExecutor,
    ToolDeveloper
)
from .safety import SafetyAnalyzer
from ..llm.document_ingestion import DocumentIngestionManager
from ..llm.training_data_organizer import TrainingDataOrganizer

logger = logging.getLogger(__name__)


class DaedelusIntegration:
    """
    Main integration class providing unified access to all Daedelus features.

    This class initializes and coordinates all subsystems:
    - File operations with permissions and memory
    - Command execution with safety checks
    - Tool/plugin system
    - Document ingestion for training
    - Training data organization

    Example:
        >>> integration = DaedelusIntegration()
        >>> integration.initialize()
        >>>
        >>> # Read a file
        >>> content = integration.file_ops.read_file("/path/to/file.txt")
        >>>
        >>> # Execute a command
        >>> result = integration.cmd_exec.execute("ls -la")
        >>>
        >>> # Ingest a document
        >>> integration.doc_ingest.ingest_document(Path("README.md"))
        >>>
        >>> # Collect training data
        >>> dataset = integration.training_organizer.collect_all_training_data()
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize integration.

        Args:
            config: Configuration instance (creates default if None)
            session_id: Optional session ID for tracking
        """
        self.config = config or Config()
        self.session_id = session_id or self._generate_session_id()

        # Initialize data directories
        self.data_dir = self.config.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Components (initialized on demand)
        self._file_ops: Optional[FileOperationsManager] = None
        self._cmd_exec: Optional[CommandExecutor] = None
        self._tool_executor: Optional[ToolExecutor] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._doc_ingest: Optional[DocumentIngestionManager] = None
        self._training_organizer: Optional[TrainingDataOrganizer] = None
        self._interactive_shell: Optional[InteractiveShell] = None

        # Shared components
        self._safety_analyzer: Optional[SafetyAnalyzer] = None

        logger.info(f"Daedelus integration initialized (session: {self.session_id})")

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        import uuid
        from datetime import datetime

        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def initialize(self, discover_tools: bool = True) -> None:
        """
        Initialize all subsystems.

        Args:
            discover_tools: If True, auto-discover tools on initialization
        """
        logger.info("Initializing all subsystems...")

        # Initialize file operations
        self._init_file_operations()

        # Initialize command execution
        self._init_command_execution()

        # Initialize tool system
        self._init_tool_system(discover_tools=discover_tools)

        # Initialize document ingestion
        self._init_document_ingestion()

        # Initialize training data organizer
        self._init_training_organizer()

        logger.info("✓ All subsystems initialized successfully")

    def _init_file_operations(self) -> None:
        """Initialize file operations subsystem"""
        logger.debug("Initializing file operations...")

        # Setup databases
        file_ops_db = self.data_dir / "file_operations.db"

        # Create permission manager
        permissions_config = self.data_dir / "file_permissions.json"
        permission_manager = FilePermissionManager(permissions_config)

        # Create memory tracker
        memory_tracker = FileMemoryTracker(file_ops_db)

        # Create file operations manager
        self._file_ops = FileOperationsManager(
            permission_manager=permission_manager,
            memory_tracker=memory_tracker,
            session_id=self.session_id
        )

        logger.debug("✓ File operations initialized")

    def _init_command_execution(self) -> None:
        """Initialize command execution subsystem"""
        logger.debug("Initializing command execution...")

        # Setup database
        cmd_exec_db = self.data_dir / "command_executions.db"

        # Create safety analyzer
        self._safety_analyzer = SafetyAnalyzer()

        # Create memory tracker
        memory_tracker = CommandExecutionMemory(cmd_exec_db)

        # Create command executor
        self._cmd_exec = CommandExecutor(
            safety_analyzer=self._safety_analyzer,
            memory_tracker=memory_tracker,
            session_id=self.session_id,
            default_timeout=self.config.get("command_execution.default_timeout", 300)
        )

        logger.debug("✓ Command execution initialized")

    def _init_tool_system(self, discover_tools: bool = True) -> None:
        """Initialize tool/plugin system"""
        logger.debug("Initializing tool system...")

        # Setup directories and database
        tools_db = self.data_dir / "tools.db"
        tools_dir = self.data_dir / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)

        # Create tool registry
        self._tool_registry = ToolRegistry(tools_db, tools_dir)

        # Create tool executor
        self._tool_executor = ToolExecutor(
            registry=self._tool_registry,
            session_id=self.session_id,
            require_permission_approval=self.config.get("tools.require_permission_approval", True)
        )

        # Auto-discover tools if enabled
        if discover_tools and self.config.get("tools.auto_discover", True):
            count = self._tool_registry.discover_tools()
            logger.info(f"Discovered {count} tools")

        logger.debug("✓ Tool system initialized")

    def _init_document_ingestion(self) -> None:
        """Initialize document ingestion subsystem"""
        logger.debug("Initializing document ingestion...")

        # Setup directories and database
        doc_ingest_db = self.data_dir / "document_ingestion.db"
        storage_path = self.data_dir / "ingested_documents"

        # Create document ingestion manager
        self._doc_ingest = DocumentIngestionManager(doc_ingest_db, storage_path)

        logger.debug("✓ Document ingestion initialized")

    def _init_training_organizer(self) -> None:
        """Initialize training data organizer"""
        logger.debug("Initializing training data organizer...")

        # Create training data organizer
        self._training_organizer = TrainingDataOrganizer(
            history_db=self.data_dir / "history.db",
            file_ops_db=self.data_dir / "file_operations.db",
            tool_db=self.data_dir / "tools.db",
            doc_ingest_db=self.data_dir / "document_ingestion.db",
            output_dir=self.data_dir / "training_data"
        )

        logger.debug("✓ Training data organizer initialized")

    @property
    def file_ops(self) -> FileOperationsManager:
        """Get file operations manager (lazy init)"""
        if self._file_ops is None:
            self._init_file_operations()
        return self._file_ops

    @property
    def cmd_exec(self) -> CommandExecutor:
        """Get command executor (lazy init)"""
        if self._cmd_exec is None:
            self._init_command_execution()
        return self._cmd_exec

    @property
    def tool_executor(self) -> ToolExecutor:
        """Get tool executor (lazy init)"""
        if self._tool_executor is None:
            self._init_tool_system()
        return self._tool_executor

    @property
    def tool_registry(self) -> ToolRegistry:
        """Get tool registry (lazy init)"""
        if self._tool_registry is None:
            self._init_tool_system()
        return self._tool_registry

    @property
    def doc_ingest(self) -> DocumentIngestionManager:
        """Get document ingestion manager (lazy init)"""
        if self._doc_ingest is None:
            self._init_document_ingestion()
        return self._doc_ingest

    @property
    def training_organizer(self) -> TrainingDataOrganizer:
        """Get training data organizer (lazy init)"""
        if self._training_organizer is None:
            self._init_training_organizer()
        return self._training_organizer

    @property
    def interactive_shell(self) -> InteractiveShell:
        """Get interactive shell (lazy init)"""
        if self._interactive_shell is None:
            self._interactive_shell = InteractiveShell(
                executor=self.cmd_exec,
                initial_cwd=os.getcwd(),
                initial_env=os.environ.copy()
            )
        return self._interactive_shell

    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics from all subsystems.

        Returns:
            Dictionary with statistics from all components
        """
        stats = {
            'session_id': self.session_id,
            'data_dir': str(self.data_dir),
            'subsystems': {}
        }

        # File operations stats
        if self._file_ops:
            try:
                stats['subsystems']['file_operations'] = self._file_ops.memory_tracker.get_statistics()
            except Exception as e:
                logger.error(f"Error getting file ops stats: {e}")
                stats['subsystems']['file_operations'] = {'error': str(e)}

        # Command execution stats
        if self._cmd_exec:
            try:
                stats['subsystems']['command_execution'] = self._cmd_exec.memory_tracker.get_statistics()
            except Exception as e:
                logger.error(f"Error getting cmd exec stats: {e}")
                stats['subsystems']['command_execution'] = {'error': str(e)}

        # Tool system stats
        if self._tool_registry:
            try:
                tools = self._tool_registry.list_tools()
                stats['subsystems']['tools'] = {
                    'total_tools': len(tools),
                    'enabled_tools': len([t for t in tools if t.enabled])
                }
            except Exception as e:
                logger.error(f"Error getting tool stats: {e}")
                stats['subsystems']['tools'] = {'error': str(e)}

        # Document ingestion stats
        if self._doc_ingest:
            try:
                stats['subsystems']['document_ingestion'] = self._doc_ingest.get_statistics()
            except Exception as e:
                logger.error(f"Error getting doc ingest stats: {e}")
                stats['subsystems']['document_ingestion'] = {'error': str(e)}

        # Training data stats
        if self._training_organizer:
            try:
                stats['subsystems']['training_data'] = self._training_organizer.get_statistics()
            except Exception as e:
                logger.error(f"Error getting training stats: {e}")
                stats['subsystems']['training_data'] = {'error': str(e)}

        return stats

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all subsystems.

        Returns:
            Dictionary with health status of each component
        """
        health = {
            'overall': 'healthy',
            'subsystems': {}
        }

        # Check file operations
        try:
            self.file_ops.get_metadata(Path.home())
            health['subsystems']['file_operations'] = 'healthy'
        except Exception as e:
            health['subsystems']['file_operations'] = f'unhealthy: {e}'
            health['overall'] = 'degraded'

        # Check command execution
        try:
            result = self.cmd_exec.execute("echo test", mode=ExecutionMode.DRY_RUN)
            health['subsystems']['command_execution'] = 'healthy'
        except Exception as e:
            health['subsystems']['command_execution'] = f'unhealthy: {e}'
            health['overall'] = 'degraded'

        # Check tool system
        try:
            tools = self.tool_registry.list_tools()
            health['subsystems']['tool_system'] = 'healthy'
        except Exception as e:
            health['subsystems']['tool_system'] = f'unhealthy: {e}'
            health['overall'] = 'degraded'

        # Check document ingestion
        try:
            stats = self.doc_ingest.get_statistics()
            health['subsystems']['document_ingestion'] = 'healthy'
        except Exception as e:
            health['subsystems']['document_ingestion'] = f'unhealthy: {e}'
            health['overall'] = 'degraded'

        # Check training organizer
        try:
            stats = self.training_organizer.get_statistics()
            health['subsystems']['training_organizer'] = 'healthy'
        except Exception as e:
            health['subsystems']['training_organizer'] = f'unhealthy: {e}'
            health['overall'] = 'degraded'

        return health

    def shutdown(self) -> None:
        """
        Gracefully shutdown all subsystems.
        """
        logger.info("Shutting down Daedelus integration...")

        # Kill any active processes
        if self._cmd_exec:
            active_processes = self._cmd_exec.get_active_processes()
            for proc_id in active_processes:
                self._cmd_exec.kill_process(proc_id)

        # Clear caches, close connections, etc.
        # Most components handle cleanup automatically via SQLite connection management

        logger.info("✓ Shutdown complete")


# Global singleton instance
_global_integration: Optional[DaedelusIntegration] = None


def get_integration(config: Optional[Config] = None) -> DaedelusIntegration:
    """
    Get global integration instance (singleton pattern).

    Args:
        config: Optional configuration (used only on first call)

    Returns:
        Global DaedelusIntegration instance
    """
    global _global_integration

    if _global_integration is None:
        _global_integration = DaedelusIntegration(config=config)

    return _global_integration


def initialize_integration(config: Optional[Config] = None, discover_tools: bool = True) -> DaedelusIntegration:
    """
    Initialize the global integration instance.

    Args:
        config: Optional configuration
        discover_tools: If True, auto-discover tools

    Returns:
        Initialized DaedelusIntegration instance
    """
    integration = get_integration(config)
    integration.initialize(discover_tools=discover_tools)
    return integration
