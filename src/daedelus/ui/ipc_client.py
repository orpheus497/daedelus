"""
IPC client wrapper for GUI dashboard.

Provides high-level methods for the dashboard to communicate with the daemon.
"""

import logging
from pathlib import Path
from typing import Any

from daedelus.daemon.ipc import IPCClient, IPCMessage, MessageType
from daedelus.utils.config import Config

logger = logging.getLogger(__name__)


class DashboardIPCClient:
    """High-level IPC client for dashboard operations."""

    def __init__(self, socket_path: str | None = None):
        """
        Initialize dashboard IPC client.

        Args:
            socket_path: Path to daemon socket. If None, reads from config.
        """
        if socket_path is None:
            config = Config()
            socket_path = config.get("daemon.socket_path", "")
            if not socket_path:
                socket_path = str(Path.home() / ".local/share/daedelus/runtime/daemon.sock")

        # Use longer timeout for LLM operations (30 seconds)
        self.client = IPCClient(socket_path, timeout=30.0)
        self._connected = False

    def is_connected(self) -> bool:
        """Check if daemon is reachable."""
        try:
            response = self.client.send_message(IPCMessage(MessageType.PING, {}))
            self._connected = response.type == MessageType.SUCCESS
            return self._connected
        except Exception as e:
            logger.debug(f"Daemon not reachable: {e}")
            self._connected = False
            return False

    def get_daemon_status(self) -> dict[str, Any]:
        """
        Get daemon status information.

        Returns:
            Dictionary with status information
        """
        try:
            response = self.client.send_message(IPCMessage(MessageType.STATUS, {}))
            if response.type == MessageType.SUCCESS:
                return response.data
            else:
                logger.error(f"Error getting status: {response.data}")
                return self._mock_status()
        except Exception as e:
            logger.warning(f"Failed to get daemon status: {e}")
            return self._mock_status()

    def get_command_history(
        self, limit: int = 100, offset: int = 0, search: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get command history.

        Args:
            limit: Maximum number of commands to return
            offset: Offset for pagination
            search: Optional search query

        Returns:
            List of command records
        """
        try:
            data = {"limit": limit, "offset": offset, "format": "full"}
            if search:
                data["query"] = search

            response = self.client.send_message(IPCMessage(MessageType.SEARCH, data))

            if response.type == MessageType.SUCCESS:
                return response.data.get("results", [])
            else:
                logger.error(f"Error getting history: {response.data}")
                return []
        except Exception as e:
            logger.warning(f"Failed to get command history: {e}")
            return []

    def get_analytics_data(self) -> dict[str, Any]:
        """
        Get analytics/statistics data.

        Returns:
            Dictionary with analytics data
        """
        try:
            response = self.client.send_message(IPCMessage(MessageType.GET_ANALYTICS, {}))

            if response.type == MessageType.SUCCESS:
                return response.data
            else:
                logger.error(f"Error getting analytics: {response.data}")
                return self._mock_analytics()
        except Exception as e:
            logger.warning(f"Failed to get analytics: {e}")
            return self._mock_analytics()

    def get_config_value(self, key: str) -> Any:
        """
        Get configuration value.

        Args:
            key: Configuration key (dot-separated)

        Returns:
            Configuration value
        """
        try:
            response = self.client.send_message(IPCMessage(MessageType.GET_CONFIG, {"key": key}))

            if response.type == MessageType.SUCCESS:
                return response.data.get("value")
            else:
                logger.error(f"Error getting config: {response.data}")
                # Fallback to direct config read
                config = Config()
                return config.get(key)
        except Exception as e:
            logger.warning(f"Failed to get config value '{key}': {e}")
            # Fallback to direct config read
            try:
                config = Config()
                return config.get(key)
            except Exception as fallback_error:
                logger.debug(f"Config fallback also failed: {fallback_error}")
                return None

    def set_config_value(self, key: str, value: Any) -> bool:
        """
        Set configuration value.

        Args:
            key: Configuration key (dot-separated)
            value: New value

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.client.send_message(
                IPCMessage(MessageType.SET_CONFIG, {"key": key, "value": value})
            )

            if response.type == MessageType.SUCCESS:
                return response.data.get("success", False)
            else:
                logger.error(f"Error setting config: {response.data}")
                return False
        except Exception as e:
            logger.warning(f"Failed to set config value '{key}': {e}")
            return False

    def explain_command(self, command: str) -> str:
        """
        Get an explanation of a command using LLM.

        Args:
            command: Command to explain

        Returns:
            Explanation text or fallback message
        """
        try:
            response = self.client.send_message(
                IPCMessage(MessageType.EXPLAIN, {"command": command})
            )

            if response.type == MessageType.SUCCESS:
                return response.data.get("explanation", "No explanation available")
            else:
                return response.data.get("explanation", "Error getting explanation")
        except Exception as e:
            logger.warning(f"Failed to explain command: {e}")
            return "Command explanation unavailable (daemon not connected)"

    def _mock_analytics(self) -> dict[str, Any]:
        """Return mock analytics when daemon is unreachable."""
        return {
            "total_commands": 1234,
            "unique_commands": 456,
            "successful_commands": 1100,
            "success_rate": 89.1,
            "most_used_commands": [
                ("git status", 152),
                ("ls -la", 121),
                ("cd ..", 98),
            ],
            "total_sessions": 45,
        }

    def _mock_status(self) -> dict[str, Any]:
        """Return mock status when daemon is unreachable."""
        return {
            "status": "disconnected",
            "uptime_seconds": 0,
            "session_id": "N/A",
            "requests_handled": 0,
            "commands_logged": 0,
            "suggestions_generated": 0,
            "database": {"total_commands": 0, "unique_commands": 0},
            "vector_store": {"num_items": 0},
        }
