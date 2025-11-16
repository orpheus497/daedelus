# src/daedelus/core/plugin_interface.py
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import click

    from daedelus.core.permission_manager import PermissionManager


class DaedalusAPI:
    """
    The API object passed to plugins, providing safe access to core functionality.
    """

    def __init__(self, plugin_name: str, permission_manager: "PermissionManager | None" = None):
        self.plugin_name = plugin_name
        self.permission_manager = permission_manager
        self.logger = self._setup_logger()

    def get_logger(self) -> logging.Logger:
        """Returns a namespaced logger for the plugin."""
        return self.logger

    def _setup_logger(self) -> logging.Logger:
        """Sets up a logger for the plugin."""
        return logging.getLogger(f"daedelus.plugin.{self.plugin_name}")

    def has_permission(self, permission: str) -> bool:
        """
        Check if plugin has a specific permission.

        Args:
            permission: Permission string (e.g., "filesystem:read")

        Returns:
            True if permission is granted, False otherwise
        """
        if not self.permission_manager:
            self.logger.warning("Permission manager not available, allowing operation")
            return True

        return self.permission_manager.has_permission(self.plugin_name, permission)

    def require_permission(self, permission: str, action_description: str = "") -> None:
        """
        Require a permission and raise error if not granted.

        Args:
            permission: Permission string (e.g., "filesystem:read")
            action_description: Description of the action (for error message)

        Raises:
            PermissionError: If permission is not granted
        """
        if not self.permission_manager:
            self.logger.warning("Permission manager not available, allowing operation")
            return

        self.permission_manager.check_and_enforce(self.plugin_name, permission, action_description)

    def register_cli_command(self, command: "click.Command"):
        """
        Adds a new command to the `daedelus` CLI.

        This method should be implemented by the plugin loader.
        """
        raise NotImplementedError

    def get_command_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get recent command history.

        Requires: database:read permission

        Args:
            limit: Maximum number of commands to return

        Returns:
            List of command records

        Raises:
            PermissionError: If plugin lacks database:read permission
        """
        self.require_permission("database:read", "access command history")
        raise NotImplementedError("Must be implemented by plugin loader")

    def execute_shell_command(self, command: str) -> tuple[int, str, str]:
        """
        Execute a shell command.

        Requires: shell:execute permission

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (exit_code, stdout, stderr)

        Raises:
            PermissionError: If plugin lacks shell:execute permission
        """
        self.require_permission("shell:execute", f"execute command: {command}")
        raise NotImplementedError("Must be implemented by plugin loader")


class DaedalusPlugin(ABC):
    """
    The abstract base class that all Daedalus plugins must inherit from.
    """

    def __init__(self, api: "DaedalusAPI"):
        self.api = api
        self.logger = api.get_logger()

    @abstractmethod
    def load(self):
        """
        Called when the plugin is loaded. Use this to register commands,
        subscribe to events, etc.
        """
        pass

    @abstractmethod
    def unload(self):
        """Called when the plugin is unloaded or Daedalus is shutting down."""
        pass
