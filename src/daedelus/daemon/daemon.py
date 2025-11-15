"""
Main daemon for Daedalus.

The daemon is a persistent background process that:
- Listens for IPC requests from shell clients
- Manages command history database
- Provides intelligent suggestions
- Learns from user behavior
- Updates models on shutdown

Created by: orpheus497
"""

import logging
import os
import re
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.plugin_interface import DaedalusPlugin
from daedelus.core.plugin_loader import PluginLoader
from daedelus.core.suggestions import SuggestionEngine
from daedelus.core.vector_store import VectorStore
from daedelus.daemon.ipc import IPCServer
from daedelus.utils.config import Config
from daedelus.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


class DaedelusDaemon:
    """
    Main Daedalus daemon process.

    Orchestrates all components:
    - IPC server for shell communication
    - Command database
    - Embedding model
    - Vector store
    - Suggestion engine

    Lifecycle:
    1. Initialize all components
    2. Start IPC server
    3. Handle requests in event loop
    4. Graceful shutdown with learning update
    """

    def __init__(self, config: Config | None = None) -> None:
        """
        Initialize daemon with configuration.

        Args:
            config: Configuration object (creates default if None)
        """
        self.config = config or Config()
        self.running = False
        self.session_id = str(uuid.uuid4())

        # Components (initialized in start())
        self.db: CommandDatabase | None = None
        self.embedder: CommandEmbedder | None = None
        self.vector_store: VectorStore | None = None
        self.suggestion_engine: SuggestionEngine | None = None
        self.ipc_server: IPCServer | None = None
        self.plugin_loader: PluginLoader | None = None
        self.plugins: list[DaedalusPlugin] = []

        # LLM components (optional, only initialized if enabled in config)
        self.llm_manager = None
        self.command_explainer = None
        self.command_generator = None
        self.ai_interpreter = None

        # Privacy filtering
        self._excluded_paths: list[Path] = []
        self._excluded_patterns: list[re.Pattern] = []
        self._load_privacy_filters()

        # Statistics
        self.stats = {
            "start_time": None,
            "requests_handled": 0,
            "commands_logged": 0,
            "suggestions_generated": 0,
            "commands_filtered": 0,  # Privacy filtered commands
        }

        logger.info(f"Daemon initialized (session: {self.session_id})")

    def start(self) -> None:
        """
        Start daemon in foreground.

        For background mode, use start_background().
        """
        logger.info("Starting Daedalus daemon...")

        try:
            # Initialize components
            self._initialize_components()

            # Set up signal handlers
            self._setup_signal_handlers()

            # Start IPC server
            self.ipc_server.start()

            # Mark as running
            self.running = True
            self.stats["start_time"] = time.time()

            # Write PID file
            self._write_pid_file()

            logger.info("Daemon started successfully")
            logger.info(f"Listening on {self.config.get('daemon.socket_path')}")

            # Main event loop
            self._run_event_loop()

        except Exception as e:
            logger.error(f"Failed to start daemon: {e}", exc_info=True)
            self.shutdown()
            raise

    def _initialize_components(self) -> None:
        """Initialize all daemon components."""
        logger.info("Initializing components...")

        # Database
        db_path = self.config.get("database.path")
        self.db = CommandDatabase(Path(db_path))

        # Create session
        self.session_id = self.db.create_session(
            shell=os.environ.get("SHELL"),
            cwd=os.getcwd(),
        )

        # Embedding model
        # logger.info("Step 3/7: Initializing embedding model...")
        # model_path = Path(self.config.get("model.model_path"))
        # self.embedder = CommandEmbedder(
        #     model_path=model_path,
        #     embedding_dim=self.config.get("model.embedding_dim"),
        #     vocab_size=self.config.get("model.vocab_size"),
        #     min_count=self.config.get("model.min_count"),
        #     word_ngrams=self.config.get("model.word_ngrams"),
        #     epoch=self.config.get("model.epoch"),
        # )
        # logger.info("Step 3/7: Embedding model initialized.")
        self.embedder = None  # Explicitly set to None

        # Try to load existing model, or train new one
        # try:
        #     self.embedder.load()
        #     logger.info("Loaded existing embedding model")
        # except (FileNotFoundError, AttributeError):
        #     logger.info("No existing model found, attempting to train...")
        #     recent_commands = self.db.get_recent_commands(n=1000, successful_only=True)
        #     if len(recent_commands) >= 10:
        #         command_strings = [cmd["command"] for cmd in recent_commands]
        #         try:
        #             self.embedder.train_from_corpus(command_strings)
        #             self.embedder.save()
        #             logger.info("Successfully trained and saved initial model")
        #         except Exception as e:
        #             logger.warning(f"Failed to train initial model: {e}")
        #     else:
        #         logger.info("Not enough commands to train initial model.")

        # Vector store
        # logger.info("Step 4/7: Initializing vector store...")
        # index_path = Path(self.config.get("vector_store.index_path"))
        # self.vector_store = VectorStore(
        #     index_path=index_path,
        #     dim=self.config.get("model.embedding_dim"),
        #     n_trees=self.config.get("vector_store.n_trees"),
        # )
        # try:
        #     self.vector_store.load()
        #     logger.info("Loaded existing vector index")
        # except FileNotFoundError:
        #     logger.info("No existing index found.")
        # logger.info("Step 4/7: Vector store initialized.")
        self.vector_store = None  # Explicitly set to None

        # Suggestion engine
        # logger.info("Step 5/7: Initializing suggestion engine...")
        # self.suggestion_engine = SuggestionEngine(
        #     db=self.db,
        #     embedder=self.embedder,
        #     vector_store=self.vector_store,
        #     max_suggestions=self.config.get("suggestions.max_suggestions"),
        #     min_confidence=self.config.get("suggestions.min_confidence"),
        # )
        # logger.info("Step 5/7: Suggestion engine initialized.")
        self.suggestion_engine = None  # Explicitly set to None

        # IPC server
        logger.info("Step 6/7: Initializing IPC server...")
        socket_path = self.config.get("daemon.socket_path")
        self.ipc_server = IPCServer(socket_path, handler=self)
        logger.info("Step 6/7: IPC server initialized.")

        # Plugin Loader
        logger.info("Initializing plugin system...")
        from daedelus.core.permission_manager import PermissionManager

        internal_plugin_dir = Path(__file__).parent.parent / "plugins"
        external_plugin_dir = Path.home() / ".local" / "share" / "daedelus" / "plugins"

        # Initialize permission manager
        permission_manager = PermissionManager(self.config.data_dir)

        self.plugin_loader = PluginLoader(
            internal_plugin_dir=internal_plugin_dir,
            external_plugin_dir=external_plugin_dir,
            cli_cache_path=self.config.data_dir / "cli_commands.json",
            permission_manager=permission_manager,
        )
        self.plugin_loader.discover_and_load_plugins()
        self.plugins = self.plugin_loader.get_loaded_plugins()
        logger.info(f"Loaded {len(self.plugins)} plugins.")

        # Initialize LLM components if enabled
        self._initialize_llm_components()

        logger.info("All components initialized")

    def _load_privacy_filters(self) -> None:
        """Load and compile privacy filtering rules."""
        # Load excluded paths
        excluded_paths = self.config.get("privacy.excluded_paths", [])
        self._excluded_paths = [Path(p).expanduser() for p in excluded_paths]

        # Load and compile excluded patterns
        excluded_patterns = self.config.get("privacy.excluded_patterns", [])
        self._excluded_patterns = []
        for pattern in excluded_patterns:
            try:
                # Validate pattern complexity to prevent ReDoS
                if len(pattern) > 1000:
                    logger.warning(f"Privacy pattern too long, skipping: {pattern[:50]}...")
                    continue
                if pattern.count("*") > 10 or pattern.count("+") > 10:
                    logger.warning(f"Privacy pattern too complex, skipping: {pattern[:50]}...")
                    continue

                # Compile and add pattern
                compiled = re.compile(pattern, re.IGNORECASE)
                self._excluded_patterns.append(compiled)
                logger.debug(f"Added privacy pattern: {pattern}")
            except re.error as e:
                logger.warning(f"Invalid privacy pattern '{pattern}': {e}")

        if self._excluded_paths or self._excluded_patterns:
            logger.info(
                f"Privacy filters loaded: {len(self._excluded_paths)} paths, "
                f"{len(self._excluded_patterns)} patterns"
            )

    def _initialize_llm_components(self) -> None:
        """Initialize LLM components if enabled in configuration."""
        try:
            # Check if LLM is enabled in config
            llm_enabled = self.config.get("llm.enabled", False)
            if not llm_enabled:
                logger.info("LLM features disabled in configuration")
                return

            # Import LLM components
            from daedelus.llm.command_explainer import CommandExplainer
            from daedelus.llm.command_generator import CommandGenerator
            from daedelus.llm.llm_manager import LLMManager

            # Get model path from config
            model_path = Path(self.config.get("llm.model_path"))

            if not model_path.exists():
                logger.warning(f"LLM model not found at {model_path}, LLM features disabled")
                return

            logger.info("Initializing LLM components...")

            # Initialize LLM manager with 60-second timeout
            self.llm_manager = LLMManager(
                model_path=model_path,
                context_length=self.config.get("llm.context_length", 2048),
                temperature=self.config.get("llm.temperature", 0.7),
                default_timeout=60.0,  # 60-second timeout for all LLM operations
            )

            # Initialize explainer and generator
            self.command_explainer = CommandExplainer(self.llm_manager)
            self.command_generator = CommandGenerator(self.llm_manager)
            
            # Initialize AI interpreter
            from daedelus.llm.ai_interpreter import AIInterpreter
            self.ai_interpreter = AIInterpreter(
                self.llm_manager,
                command_generator=self.command_generator,
                cache_dir=self.config.data_dir / "interpreter_cache"
            )

            logger.info("LLM components initialized successfully")

        except ImportError as e:
            logger.warning(f"LLM dependencies not available: {e}")
            self.llm_manager = None
            self.command_explainer = None
            self.command_generator = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM components: {e}", exc_info=True)
            self.llm_manager = None
            self.command_explainer = None
            self.command_generator = None

    def _should_filter_command(self, command: str, cwd: str) -> bool:
        """
        Check if command should be filtered based on privacy settings.

        Args:
            command: Command string
            cwd: Current working directory

        Returns:
            True if command should be filtered (not logged), False otherwise
        """
        # Check excluded paths
        cwd_path = Path(cwd).expanduser().resolve()
        for excluded_path in self._excluded_paths:
            try:
                excluded_resolved = excluded_path.resolve()
                # Check if cwd is the excluded path or a subdirectory
                if cwd_path == excluded_resolved or excluded_resolved in cwd_path.parents:
                    logger.debug(f"Filtering command in excluded path: {cwd}")
                    return True
            except (ValueError, OSError):
                # Path resolution failed, skip this check
                continue

        # Check excluded patterns
        for pattern in self._excluded_patterns:
            if pattern.search(command):
                logger.debug(f"Filtering command matching pattern: {pattern.pattern}")
                return True

        return False

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.shutdown()

    def _write_pid_file(self) -> None:
        """Write PID to file for daemon management."""
        pid_path = Path(self.config.get("daemon.pid_path"))
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()))

    def _run_event_loop(self) -> None:
        """Main event loop - handle IPC connections."""
        # Set socket timeout to allow checking self.running periodically
        self.ipc_server.socket.settimeout(1.0)

        while self.running:
            try:
                try:
                    # Accept connection (with timeout)
                    conn, addr = self.ipc_server.socket.accept()

                    # Handle in foreground (for simplicity)
                    # In production, could use threading or async
                    self.ipc_server.handle_connection(conn, addr)

                    self.stats["requests_handled"] += 1

                except TimeoutError:
                    # Normal timeout, check if we should continue
                    continue

            except Exception as e:
                if self.running:  # Only log if not shutting down
                    logger.error(f"Error in event loop: {e}", exc_info=True)

        logger.info("Daemon event loop exiting gracefully")

    # ========================================
    # IPC Message Handlers
    # ========================================

    def handle_suggest(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle suggestion request.

        Args:
            data: Request data with 'partial', 'cwd', 'history'

        Returns:
            Response with 'suggestions' list
        """
        if not self.suggestion_engine:
            logger.warning("Suggestion engine not available, returning empty suggestion list.")
            return {"suggestions": []}

        partial = data.get("partial", "")
        cwd = data.get("cwd")
        history = data.get("history", [])

        logger.debug(f"Suggestion request: partial='{partial}'")

        # Get suggestions
        suggestions = self.suggestion_engine.get_suggestions(
            partial=partial,
            cwd=cwd,
            history=history,
        )

        self.stats["suggestions_generated"] += len(suggestions)

        return {"suggestions": suggestions}

    def handle_log_command(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle command logging request.

        Args:
            data: Command execution data

        Returns:
            Success response
        """
        command = data.get("command", "")
        exit_code = data.get("exit_code", 0)
        duration = data.get("duration")
        cwd = data.get("cwd", os.getcwd())
        session_id = data.get("session_id", self.session_id)

        # Privacy filtering: Check if command should be logged
        if self._should_filter_command(command, cwd):
            self.stats["commands_filtered"] += 1
            logger.debug("Command filtered by privacy settings")
            return {"status": "filtered", "reason": "privacy"}

        # Insert into database
        self.db.insert_command(
            command=command,
            cwd=cwd,
            exit_code=exit_code,
            session_id=session_id,
            duration=duration,
        )

        # Update pattern statistics
        if exit_code == 0:  # Only learn from successful commands
            self.db.update_pattern_statistics(
                context=cwd,
                command=command,
                success=True,
                duration=duration,
            )

            # Add to vector store if model is ready
            if (
                self.embedder
                and self.embedder.model
                and self.vector_store
                and self.vector_store.is_built()
            ):
                try:
                    self.embedder.encode_command(command)
                    # Note: Can't add to built index, will rebuild on shutdown
                except Exception as e:
                    logger.debug(f"Skipping embedding: {e}")

        self.stats["commands_logged"] += 1

        return {"status": "logged"}

    def handle_complete(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle completion request.

        Args:
            data: Completion context

        Returns:
            Completion options
        """
        # Completions are similar to suggestions
        return self.handle_suggest(data)

    def handle_search(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle history search request.

        Args:
            data: Search query

        Returns:
            Search results (list of command records or strings based on format parameter)
        """
        if not self.db:
            logger.warning("Database not available, returning empty search results.")
            return {"results": []}

        query = (data.get("query", "") or "").strip()
        limit = int(data.get("limit", 20) or 20)
        format_type = data.get("format", "string")  # "string" or "full"

        try:
            if not query:
                # When no query provided, return recent commands
                rows = self.db.get_recent_commands(n=limit, successful_only=False)
            else:
                # Full-text search when query provided
                rows = self.db.search_commands(query, limit=limit)

            # Return based on requested format
            if format_type == "full":
                # Return full command records (for dashboard)
                results = []
                for r in rows:
                    if isinstance(r, dict):
                        results.append(r)
                    elif isinstance(r, str):
                        # Convert string to dict format
                        results.append({"command": r})
                return {"results": results[:limit]}
            else:
                # Normalize to list of command strings (for shell)
                commands: list[str] = []
                for r in rows:
                    if isinstance(r, dict) and "command" in r:
                        commands.append(r["command"])
                    elif isinstance(r, str):
                        commands.append(r)
                return {"results": commands[:limit]}
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return {"results": []}

    def handle_ping(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle ping request (health check)."""
        return {"status": "alive", "uptime": time.time() - self.stats["start_time"]}

    def handle_status(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle status request."""
        uptime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0

        db_stats = self.db.get_statistics() if self.db else {}
        vector_stats = self.vector_store.get_statistics() if self.vector_store else {}

        return {
            "status": "running" if self.running else "stopped",
            "uptime_seconds": uptime,
            "session_id": self.session_id,
            "requests_handled": self.stats["requests_handled"],
            "commands_logged": self.stats["commands_logged"],
            "suggestions_generated": self.stats["suggestions_generated"],
            "database": db_stats,
            "vector_store": vector_stats,
        }

    def handle_shutdown(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle shutdown request."""
        logger.info("Shutdown requested via IPC")
        self.shutdown()
        return {"status": "shutting_down"}

    def handle_get_analytics(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle analytics data request from GUI.

        Returns:
            Dictionary with comprehensive analytics data
        """
        self.stats["requests_handled"] += 1

        if not self.db:
            return {
                "total_commands": 0,
                "unique_commands": 0,
                "successful_commands": 0,
                "success_rate": 0.0,
                "most_used_commands": [],
                "total_sessions": 0,
            }

        try:
            analytics = self.db.get_analytics_data()
            return analytics
        except Exception as e:
            logger.error(f"Failed to get analytics: {e}", exc_info=True)
            return {
                "error": str(e),
                "total_commands": 0,
                "unique_commands": 0,
                "successful_commands": 0,
                "success_rate": 0.0,
                "most_used_commands": [],
                "total_sessions": 0,
            }

    def handle_get_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle configuration get request from GUI.

        Args:
            data: {"key": "config.key.path"}

        Returns:
            Dictionary with configuration value
        """
        self.stats["requests_handled"] += 1

        key = data.get("key")
        if not key:
            return {"error": "No key specified"}

        try:
            value = self.config.get(key)
            return {"key": key, "value": value}
        except Exception as e:
            logger.error(f"Failed to get config key '{key}': {e}")
            return {"error": str(e), "key": key, "value": None}

    def handle_set_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle configuration set request from GUI.

        Args:
            data: {"key": "config.key.path", "value": <new_value>}

        Returns:
            Dictionary with success status
        """
        self.stats["requests_handled"] += 1

        key = data.get("key")
        value = data.get("value")

        if not key:
            return {"error": "No key specified", "success": False}

        try:
            self.config.set(key, value)
            self.config.save()
            logger.info(f"Config updated: {key} = {value}")
            return {"success": True, "key": key, "value": value}
        except Exception as e:
            logger.error(f"Failed to set config key '{key}': {e}")
            return {"error": str(e), "success": False}

    def handle_stream_logs(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle log streaming request from GUI.

        Note: This is a placeholder. Full implementation would require
        a different IPC mechanism (e.g., websocket, long-polling).

        Returns:
            Dictionary with recent log entries
        """
        self.stats["requests_handled"] += 1

        # For now, return a message indicating this feature is not yet implemented
        return {
            "supported": False,
            "message": "Log streaming requires enhanced IPC mechanism",
            "suggestion": "Check daemon.log file directly for now",
        }

    def handle_explain(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle request to explain a command using LLM.

        Args:
            data: Request data with 'command' key

        Returns:
            Response with explanation or error
        """
        self.stats["requests_handled"] += 1
        command = data.get("command", "").strip()

        if not command:
            return {"status": "error", "message": "No command provided"}

        try:
            # Check if LLM is available
            if not hasattr(self, "llm_manager") or self.llm_manager is None:
                return {
                    "status": "unavailable",
                    "message": "LLM is not available - enable in config",
                    "explanation": "LLM features are disabled or not configured",
                }

            # Use command explainer if available
            from daedelus.llm.command_explainer import CommandExplainer

            explainer = CommandExplainer(self.llm_manager)
            explanation = explainer.explain(command)

            return {"status": "success", "command": command, "explanation": explanation}

        except ImportError:
            return {
                "status": "unavailable",
                "message": "LLM components not available",
                "explanation": "Please install LLM dependencies",
            }
        except Exception as e:
            logger.error(f"Failed to explain command: {e}")
            return {
                "status": "error",
                "message": str(e),
                "explanation": f"Error generating explanation: {e}",
            }

    def handle_explain_command(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle request to explain a command using LLM.

        Args:
            data: Request data with 'command' key

        Returns:
            Response with explanation or error
        """
        command = data.get("command", "").strip()

        if not command:
            return {"error": "No command provided"}

        # Check if LLM components are available
        if not self.command_explainer:
            return {
                "error": "LLM features not enabled",
                "explanation": "LLM is not configured or model not found. Enable llm.enabled in config and ensure model is downloaded.",
            }

        try:
            # Generate explanation
            explanation = self.command_explainer.explain_command(command)
            return {"explanation": explanation, "command": command}

        except Exception as e:
            logger.error(f"Failed to explain command: {e}", exc_info=True)
            return {"error": str(e)}

    def handle_generate_command(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle request to generate a command from natural language description.

        Args:
            data: Request data with 'description' key

        Returns:
            Response with generated command or error
        """
        description = data.get("description", "").strip()

        if not description:
            return {"error": "No description provided"}

        # Check if LLM components are available
        if not self.command_generator:
            return {
                "error": "LLM features not enabled",
                "command": "",
            }

        try:
            # Get optional parameters
            return_multiple = data.get("return_multiple", False)
            cwd = data.get("cwd")
            history = data.get("history")

            # Generate command(s)
            result = self.command_generator.generate_command(
                description=description,
                cwd=cwd,
                history=history,
                return_multiple=return_multiple,
            )

            if return_multiple:
                return {"commands": result}
            else:
                return {"command": result}

        except Exception as e:
            logger.error(f"Failed to generate command: {e}", exc_info=True)
            return {"error": str(e), "command": ""}

    def handle_get_stats(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle statistics request.

        Returns command usage statistics in format expected by REPL.

        Args:
            data: Request data (unused)

        Returns:
            Statistics dictionary
        """
        if not self.db:
            return {
                "total_commands": 0,
                "unique_commands": 0,
                "success_rate": 0.0,
                "most_used": "N/A",
                "top_commands": [],
            }

        try:
            # Get database statistics
            db_stats = self.db.get_statistics()

            # Get top commands
            recent = self.db.get_recent_commands(n=1000, successful_only=True)

            # Count command frequencies
            from collections import Counter

            command_counts = Counter([cmd["command"] for cmd in recent])
            top_commands = command_counts.most_common(10)

            # Calculate success rate
            total = db_stats.get("total_commands", 0)
            successful = db_stats.get("successful_commands", 0)
            success_rate = (successful / total * 100) if total > 0 else 0.0

            # Get most used command
            most_used = top_commands[0][0] if top_commands else "N/A"

            return {
                "total_commands": total,
                "unique_commands": db_stats.get("unique_commands", 0),
                "success_rate": success_rate,
                "most_used": most_used,
                "top_commands": top_commands,
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}", exc_info=True)
            return {
                "total_commands": 0,
                "unique_commands": 0,
                "success_rate": 0.0,
                "most_used": "N/A",
                "top_commands": [],
            }

    def handle_interpret_natural_language(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle natural language interpretation request.

        Args:
            data: Request with "text", "cwd", "session_id"

        Returns:
            Interpretation result with intent, action, commands, explanation
        """
        if not self.llm_manager:
            return {
                "status": "error",
                "error": "LLM not enabled. Run 'daedelus model setup' to enable AI features."
            }

        text = data.get("text", "").strip()
        if not text:
            return {"status": "error", "error": "No text provided"}

        try:
            # Initialize AI interpreter if not already done
            if not hasattr(self, 'ai_interpreter') or not self.ai_interpreter:
                from daedelus.llm.ai_interpreter import AIInterpreter
                self.ai_interpreter = AIInterpreter(
                    self.llm_manager,
                    command_generator=self.command_generator,
                    cache_dir=self.config.data_dir / "interpreter_cache"
                )

            # Get context
            cwd = data.get("cwd", os.getcwd())
            history = []
            if self.db:
                recent = self.db.get_recent_commands(n=10, successful_only=True)
                history = [cmd["command"] for cmd in recent]

            # Interpret
            result = self.ai_interpreter.interpret(
                text,
                cwd=cwd,
                history=history,
                session_id=data.get("session_id")
            )

            # Log prompt to database for training data collection
            if self.db:
                try:
                    prompt_id = self.db.insert_nlp_prompt(
                        prompt_text=text,
                        intent=result.intent,
                        intent_confidence=result.confidence,
                        generated_commands=result.commands,
                        cwd=cwd,
                        session_id=data.get("session_id") or self.session_id,
                    )
                    logger.debug(f"Logged NLP prompt: {prompt_id}")
                except Exception as e:
                    logger.warning(f"Failed to log NLP prompt: {e}")

            return {
                "status": "ok",
                "intent": result.intent,
                "action": result.action,
                "commands": result.commands,
                "explanation": result.explanation,
                "confidence": result.confidence,
            }

        except Exception as e:
            logger.error(f"Natural language interpretation failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_write_script(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle script writing request.

        Args:
            data: Request with "description", "cwd"

        Returns:
            Script path and content
        """
        if not self.llm_manager:
            return {
                "status": "error",
                "error": "LLM not enabled. Run 'daedelus model setup' to enable AI features."
            }

        description = data.get("description", "").strip()
        if not description:
            return {"status": "error", "error": "No description provided"}

        try:
            # Initialize AI interpreter if not already done
            if not hasattr(self, 'ai_interpreter') or not self.ai_interpreter:
                from daedelus.llm.ai_interpreter import AIInterpreter
                self.ai_interpreter = AIInterpreter(
                    self.llm_manager,
                    command_generator=self.command_generator,
                    cache_dir=self.config.data_dir / "interpreter_cache"
                )

            cwd = data.get("cwd", os.getcwd())
            result = self.ai_interpreter.write_script(description, cwd=cwd)

            if result.script_path:
                return {
                    "status": "ok",
                    "script_path": result.script_path,
                    "script_content": result.script_content,
                    "language": self.ai_interpreter._detect_script_language(description),
                }
            else:
                return {
                    "status": "error",
                    "error": result.explanation
                }

        except Exception as e:
            logger.error(f"Script writing failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_read_file(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle file reading request with optional AI analysis.

        Args:
            data: Request with "file_path", "analyze"

        Returns:
            File content and optional analysis
        """
        if not self.llm_manager:
            return {
                "status": "error",
                "error": "LLM not enabled. Run 'daedelus model setup' to enable AI features."
            }

        file_path = data.get("file_path", "").strip()
        if not file_path:
            return {"status": "error", "error": "No file path provided"}

        try:
            # Initialize AI interpreter if not already done
            if not hasattr(self, 'ai_interpreter') or not self.ai_interpreter:
                from daedelus.llm.ai_interpreter import AIInterpreter
                self.ai_interpreter = AIInterpreter(
                    self.llm_manager,
                    command_generator=self.command_generator,
                    cache_dir=self.config.data_dir / "interpreter_cache"
                )

            analyze = data.get("analyze", True)
            result = self.ai_interpreter.read_file(file_path, analyze=analyze)

            if result.file_content is not None:
                # Detect file type
                from pathlib import Path
                ext = Path(file_path).suffix.lstrip('.')
                file_type = ext if ext else "text"
                
                return {
                    "status": "ok",
                    "content": result.file_content,
                    "analysis": result.explanation if analyze else "",
                    "file_type": file_type,
                }
            else:
                return {
                    "status": "error",
                    "error": result.explanation
                }

        except Exception as e:
            logger.error(f"File reading failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_write_file(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle file writing request with AI assistance.

        Args:
            data: Request with "file_path", "description", "cwd"

        Returns:
            Success status and written file path
        """
        if not self.llm_manager:
            return {
                "status": "error",
                "error": "LLM not enabled. Run 'daedelus model setup' to enable AI features."
            }

        file_path = data.get("file_path", "").strip()
        description = data.get("description", "").strip()
        
        if not file_path or not description:
            return {"status": "error", "error": "File path and description required"}

        try:
            # Initialize AI interpreter if not already done
            if not hasattr(self, 'ai_interpreter') or not self.ai_interpreter:
                from daedelus.llm.ai_interpreter import AIInterpreter
                self.ai_interpreter = AIInterpreter(
                    self.llm_manager,
                    command_generator=self.command_generator,
                    cache_dir=self.config.data_dir / "interpreter_cache"
                )

            cwd = data.get("cwd", os.getcwd())
            result = self.ai_interpreter.write_file(file_path, description, cwd=cwd)

            if result.action == "create":
                return {
                    "status": "ok",
                    "file_path": file_path,
                    "message": result.explanation,
                }
            else:
                return {
                    "status": "error",
                    "error": result.explanation
                }

        except Exception as e:
            logger.error(f"File writing failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_get_prompt_history(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle request for NLP prompt history.

        Args:
            data: Request data with optional "limit", "feedback_filter", "intent_filter"

        Returns:
            List of prompts with metadata
        """
        if not self.db:
            return {"status": "error", "error": "Database not available"}

        try:
            limit = data.get("limit", 100)
            feedback_filter = data.get("feedback_filter")
            intent_filter = data.get("intent_filter")

            prompts = self.db.get_nlp_prompts(
                limit=limit,
                feedback_filter=feedback_filter,
                intent_filter=intent_filter,
            )

            return {"status": "ok", "prompts": prompts}

        except Exception as e:
            logger.error(f"Failed to get prompt history: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_update_prompt_feedback(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle update of prompt feedback.

        Args:
            data: Request with "prompt_id", "feedback", optional "executed_command", "exit_code"

        Returns:
            Success status
        """
        if not self.db:
            return {"status": "error", "error": "Database not available"}

        try:
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                return {"status": "error", "error": "No prompt_id provided"}

            feedback = data.get("feedback")
            executed_command = data.get("executed_command")
            exit_code = data.get("exit_code")

            self.db.update_nlp_prompt_feedback(
                prompt_id=prompt_id,
                executed_command=executed_command,
                exit_code=exit_code,
                feedback=feedback,
            )

            return {"status": "ok"}

        except Exception as e:
            logger.error(f"Failed to update prompt feedback: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_export_prompt_training_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle export of training data to file.

        Args:
            data: Request data (optional "output_path")

        Returns:
            Export path and count
        """
        if not self.db:
            return {"status": "error", "error": "Database not available"}

        try:
            output_path = data.get("output_path")
            if not output_path:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = self.config.data_dir / f"training_data_{timestamp}.json"
            else:
                output_path = Path(output_path)

            count = self.db.export_training_data(output_path)

            return {
                "status": "ok",
                "export_path": str(output_path),
                "count": count,
            }

        except Exception as e:
            logger.error(f"Failed to export training data: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_clear_prompt_history(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle clearing of prompt history.

        Args:
            data: Request data with optional "older_than_days"

        Returns:
            Number of prompts deleted
        """
        if not self.db:
            return {"status": "error", "error": "Database not available"}

        try:
            older_than_days = data.get("older_than_days")
            count = self.db.clear_nlp_prompts(older_than_days=older_than_days)

            return {"status": "ok", "deleted": count}

        except Exception as e:
            logger.error(f"Failed to clear prompt history: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_search_knowledge_base(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle knowledge base search request.

        Args:
            data: Request with "query"

        Returns:
            Search results with relevant sections
        """
        query = data.get("query", "").strip()
        
        if not query:
            return {"status": "error", "error": "No query provided"}

        try:
            # Initialize knowledge retriever if needed
            from daedelus.core.knowledge_retriever import KnowledgeRetriever
            
            retriever = KnowledgeRetriever(db_path=self.config.data_dir / "history.db")
            results = retriever.search(query, limit=3, source="redbook")
            
            if not results:
                return {
                    "status": "ok",
                    "explanation": f"No results found for '{query}' in The Redbook.\n\nTry:\n- Different keywords\n- More general terms\n- Check `/redbook` for available topics"
                }
            
            # Format results with LLM if available
            if self.llm_manager:
                context = "\n\n".join([r.get_context(max_length=1500) for r in results])
                
                prompt = f"""Based on The Redbook knowledge base, answer this query:

Query: {query}

Relevant sections from The Redbook:

{context}

Provide a clear, actionable answer with examples where appropriate. Include relevant commands."""

                try:
                    explanation = self.llm_manager.generate(prompt, max_tokens=1000, timeout=60.0)
                except Exception as e:
                    logger.warning(f"LLM generation failed, using fallback: {e}")
                    # Fallback: just show the sections
                    explanation = f"# Results for '{query}'\n\n" + context
            else:
                # No LLM: just format the raw sections
                explanation = f"# Results for '{query}'\n\n"
                for i, result in enumerate(results, 1):
                    explanation += f"## {i}. {result.title}\n\n{result.content[:500]}...\n\n"
            
            return {
                "status": "ok",
                "explanation": explanation,
                "result_count": len(results)
            }
            
        except Exception as e:
            logger.error(f"Knowledge base search failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def handle_knowledge_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Handle request for knowledge base summary.

        Returns:
            Summary of available knowledge base content
        """
        try:
            # Get stats from database
            from daedelus.core.knowledge_retriever import KnowledgeRetriever
            
            retriever = KnowledgeRetriever(db_path=self.config.data_dir / "history.db")
            
            # Try to get summary from database
            import sqlite3
            conn = sqlite3.connect(self.config.data_dir / "history.db")
            cursor = conn.cursor()
            
            # Check if knowledge_base table exists
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='table' AND name='knowledge_base'
            """)
            
            if cursor.fetchone()[0] == 0:
                conn.close()
                return {
                    "status": "ok",
                    "explanation": """# The Redbook Knowledge Base

The Redbook is a comprehensive Linux terminal mastery guide by orpheus497.

**Status**: Not yet indexed. Run `daedelus ingest redbook` to index the knowledge base.

Once indexed, you can:
- Search with `/redbook <query>`
- Get command explanations
- Find solutions to common tasks
- Learn best practices

**Topics Covered**:
- Package management
- System administration
- Security & permissions
- Networking
- Shell scripting
- And much more!"""
                }
            
            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM knowledge_base WHERE source='redbook'")
            total_sections = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT chapter) FROM knowledge_base WHERE source='redbook'")
            total_chapters = cursor.fetchone()[0]
            
            conn.close()
            
            explanation = f"""# The Redbook Knowledge Base

**Comprehensive Linux Terminal Mastery Guide** by orpheus497

## 📊 Statistics
- **{total_chapters}** chapters indexed
- **{total_sections}** sections available
- Full-text search enabled

## 🔍 How to Use
```bash
/redbook package management      # Search for topics
/redbook how to configure SSH    # Natural language queries
/redbook systemd services        # Find specific info
```

## 📚 Coverage
The Redbook covers essential Linux topics:
- Package management (apt, dnf, pacman)
- System administration
- User & permission management
- Networking & firewall configuration
- Shell scripting & automation
- Security best practices
- Performance tuning
- Troubleshooting
- And much more!

## 💡 Pro Tips
- Use specific keywords for better results
- Try natural language questions
- Check multiple topics for comprehensive understanding

**Ready to explore!** Try `/redbook <your question>` now."""

            return {
                "status": "ok",
                "explanation": explanation,
                "total_sections": total_sections,
                "total_chapters": total_chapters
            }
            
        except Exception as e:
            logger.error(f"Knowledge summary failed: {e}", exc_info=True)
            return {
                "status": "ok",
                "explanation": """# The Redbook Knowledge Base

**Linux Terminal Mastery Guide** by orpheus497

The Redbook provides comprehensive coverage of Linux command-line tools and best practices.

**Search**: `/redbook <topic>` to find information
**Topics**: Package management, networking, security, scripting, and more

*Note: Knowledge base may need indexing. Run `daedelus ingest redbook` if searches fail.*"""
            }

    # ========================================
    # Shutdown & Learning
    # ========================================

    def shutdown(self) -> None:
        """Graceful shutdown with model updates."""
        if not self.running:
            return

        logger.info("Shutting down daemon...")
        self.running = False

        # Unload plugins
        for plugin in self.plugins:
            try:
                logger.info(f"Unloading plugin '{plugin.api.plugin_name}'...")
                plugin.unload()
            except Exception as e:
                logger.error(f"Error unloading plugin '{plugin.api.plugin_name}': {e}")

        # Stop accepting new connections
        if self.ipc_server:
            try:
                self.ipc_server.stop()
            except Exception as e:
                logger.error(f"Error stopping IPC server: {e}")

        # Update models from session data
        self._update_models()

        # End session
        if self.db:
            try:
                self.db.end_session(self.session_id)
                self.db.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")

        # Remove PID file
        try:
            pid_path = Path(self.config.get("daemon.pid_path"))
            pid_path.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")

        # Print statistics
        uptime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        logger.info("Daemon statistics:")
        logger.info(f"  Uptime: {uptime:.1f}s")
        logger.info(f"  Requests: {self.stats['requests_handled']}")
        logger.info(f"  Commands logged: {self.stats['commands_logged']}")
        logger.info(f"  Commands filtered: {self.stats['commands_filtered']}")
        logger.info(f"  Suggestions: {self.stats['suggestions_generated']}")

        logger.info("Daemon stopped")

    def _update_models(self) -> None:
        """Update embedding model and vector index from session data."""
        logger.info("Updating models from session data...")

        try:
            # Get all successful commands from database
            commands = self.db.get_recent_commands(n=10000, successful_only=True)

            if len(commands) < 10:
                logger.info("Not enough data to update models")
                return

            # Extract command strings
            command_strings = [cmd["command"] for cmd in commands]

            # Retrain/update embedder if needed
            if not self.embedder.model or len(commands) > 100:
                logger.info(f"Training embedder on {len(command_strings)} commands...")
                self.embedder.train_from_corpus(command_strings)

            # Rebuild vector store
            logger.info("Rebuilding vector index...")
            embeddings = [self.embedder.encode_command(cmd) for cmd in command_strings]

            metadata_list = [
                {
                    "timestamp": cmd["timestamp"],
                    "cwd": cmd["cwd"],
                    "exit_code": cmd["exit_code"],
                }
                for cmd in commands
            ]

            self.vector_store.rebuild(embeddings, command_strings, metadata_list)
            self.vector_store.save()

            logger.info("Models updated successfully")

        except Exception as e:
            logger.error(f"Error updating models: {e}", exc_info=True)


# Entry point for daemon script
def main() -> int:
    """Main entry point for daemon."""
    # Ensure unbuffered output for daemon mode
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # Set up logging
    config = Config()
    log_path = Path(config.get("daemon.log_path"))
    # Disable console logging for daemon mode (stdout/stderr are redirected)
    setup_logging(log_path, level=logging.INFO, console=False)

    logger.info("=" * 60)
    logger.info("Daedalus Daemon Starting")
    logger.info("=" * 60)

    try:
        daemon = DaedelusDaemon(config)
        daemon.start()
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
