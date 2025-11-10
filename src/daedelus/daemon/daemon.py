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
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
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
        model_path = Path(self.config.get("model.model_path"))
        self.embedder = CommandEmbedder(
            model_path=model_path,
            embedding_dim=self.config.get("model.embedding_dim"),
            vocab_size=self.config.get("model.vocab_size"),
            min_count=self.config.get("model.min_count"),
            word_ngrams=self.config.get("model.word_ngrams"),
            epoch=self.config.get("model.epoch"),
        )

        # Try to load existing model, or train new one
        try:
            self.embedder.load()
            logger.info("Loaded existing embedding model")
        except FileNotFoundError:
            logger.info("No existing model found")
            # Try to train from existing commands if we have enough
            recent_commands = self.db.get_recent_commands(n=1000, successful_only=True)
            if len(recent_commands) >= 10:
                logger.info(
                    f"Found {len(recent_commands)} commands in database, training model..."
                )
                command_strings = [cmd["command"] for cmd in recent_commands]
                try:
                    self.embedder.train_from_corpus(command_strings)
                    self.embedder.save()
                    logger.info("Successfully trained and saved initial model")
                except Exception as e:
                    logger.warning(f"Failed to train initial model: {e}")
            else:
                logger.info("Not enough commands yet, will train after collecting data")

        # Vector store
        index_path = Path(self.config.get("vector_store.index_path"))
        self.vector_store = VectorStore(
            index_path=index_path,
            dim=self.config.get("model.embedding_dim"),
            n_trees=self.config.get("vector_store.n_trees"),
        )

        # Try to load existing index
        try:
            self.vector_store.load()
            logger.info("Loaded existing vector index")
        except FileNotFoundError:
            logger.info("No existing index found, will build on first use")

        # Suggestion engine
        self.suggestion_engine = SuggestionEngine(
            db=self.db,
            embedder=self.embedder,
            vector_store=self.vector_store,
            max_suggestions=self.config.get("suggestions.max_suggestions"),
            min_confidence=self.config.get("suggestions.min_confidence"),
        )

        # IPC server
        socket_path = self.config.get("daemon.socket_path")
        self.ipc_server = IPCServer(socket_path, handler=self)

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

                except socket.timeout:
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
            if self.embedder.model and self.vector_store.is_built():
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
            Search results
        """
        query = data.get("query", "")
        limit = data.get("limit", 20)

        results = self.db.search_commands(query, limit=limit)

        return {"results": results}

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

    # ========================================
    # Shutdown & Learning
    # ========================================

    def shutdown(self) -> None:
        """Graceful shutdown with model updates."""
        if not self.running:
            return

        logger.info("Shutting down daemon...")
        self.running = False

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
    # Set up logging
    config = Config()
    log_path = Path(config.get("daemon.log_path"))
    setup_logging(log_path, level=logging.INFO)

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
