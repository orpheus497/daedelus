"""
Permission Manager for Daedalus Plugin System.

Handles plugin permission requests, user approval prompts,
and permission enforcement.

Created by: orpheus497
"""

import json
import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class Permission(Enum):
    """Available plugin permissions."""

    # Filesystem permissions
    FILESYSTEM_READ = "filesystem:read"
    FILESYSTEM_WRITE = "filesystem:write"

    # Network permissions
    NETWORK_REQUESTS = "network:requests"
    NETWORK_SERVER = "network:server"

    # Shell permissions
    SHELL_EXECUTE = "shell:execute"
    SHELL_READ_ENV = "shell:read_env"

    # Database permissions
    DATABASE_READ = "database:read"
    DATABASE_WRITE = "database:write"

    # System permissions
    SYSTEM_INFO = "system:info"


class PermissionManager:
    """
    Manages plugin permissions and user approvals.

    Stores permission grants in JSON file for persistence.
    Provides methods to check, request, and revoke permissions.
    """

    def __init__(self, data_dir: Path):
        """
        Initialize Permission Manager.

        Args:
            data_dir: Directory to store permissions database
        """
        self.data_dir = Path(data_dir)
        self.permissions_file = self.data_dir / "plugin_permissions.json"
        self.permissions: dict[str, dict[str, bool]] = {}
        self._load_permissions()

    def _load_permissions(self) -> None:
        """Load permissions from file."""
        if self.permissions_file.exists():
            try:
                with open(self.permissions_file) as f:
                    self.permissions = json.load(f)
                logger.info(f"Loaded permissions for {len(self.permissions)} plugins")
            except Exception as e:
                logger.error(f"Failed to load permissions: {e}")
                self.permissions = {}
        else:
            self.permissions = {}
            self._save_permissions()

    def _save_permissions(self) -> None:
        """Save permissions to file."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.permissions_file, "w") as f:
                json.dump(self.permissions, f, indent=2)
            logger.debug("Permissions saved")
        except Exception as e:
            logger.error(f"Failed to save permissions: {e}")

    def has_permission(self, plugin_name: str, permission: str) -> bool:
        """
        Check if plugin has a specific permission.

        Args:
            plugin_name: Name of the plugin
            permission: Permission string (e.g., "filesystem:read")

        Returns:
            True if permission is granted, False otherwise
        """
        plugin_perms = self.permissions.get(plugin_name, {})
        return plugin_perms.get(permission, False)

    def request_permissions(
        self, plugin_name: str, requested_permissions: list[str], auto_approve: bool = False
    ) -> dict[str, bool]:
        """
        Request permissions for a plugin.

        If permissions were previously approved, returns cached result.
        Otherwise, prompts user for approval (or auto-approves if specified).

        Args:
            plugin_name: Name of the plugin
            requested_permissions: List of permission strings
            auto_approve: If True, automatically approve all permissions (for testing)

        Returns:
            Dictionary mapping permission -> granted status
        """
        # Initialize plugin permissions if not exists
        if plugin_name not in self.permissions:
            self.permissions[plugin_name] = {}

        plugin_perms = self.permissions[plugin_name]
        results = {}
        needs_prompt = False

        # Check which permissions need approval
        for perm in requested_permissions:
            if perm in plugin_perms:
                # Already have a decision
                results[perm] = plugin_perms[perm]
            else:
                # Need to request approval
                needs_prompt = True
                results[perm] = False

        # If all permissions already decided, return cached results
        if not needs_prompt:
            return results

        # Need user approval
        if auto_approve:
            # Auto-approve all (for testing/development)
            for perm in requested_permissions:
                results[perm] = True
                plugin_perms[perm] = True
            logger.info(f"Auto-approved permissions for {plugin_name}: {requested_permissions}")
        else:
            # Prompt user (in production, this would show a UI dialog)
            approval = self._prompt_user_approval(plugin_name, requested_permissions)
            for perm in requested_permissions:
                granted = approval.get(perm, False)
                results[perm] = granted
                plugin_perms[perm] = granted

        self._save_permissions()
        return results

    def _prompt_user_approval(self, plugin_name: str, permissions: list[str]) -> dict[str, bool]:
        """
        Prompt user for permission approval.

        In CLI mode, prints to console and reads input.
        In GUI mode, would show a dialog.

        Args:
            plugin_name: Name of the plugin
            permissions: List of permission strings

        Returns:
            Dictionary mapping permission -> granted status
        """
        print(f"\n{'='*60}")
        print(f"Plugin '{plugin_name}' is requesting permissions:")
        print(f"{'='*60}")

        for perm in permissions:
            print(f"  • {perm}")
            desc = self._get_permission_description(perm)
            if desc:
                print(f"    {desc}")

        print(f"{'='*60}")

        # For now, auto-approve in non-interactive mode
        # In production, this should block and wait for user input
        try:
            response = input("Approve these permissions? [y/N]: ").strip().lower()
            approved = response in ["y", "yes"]
        except (EOFError, KeyboardInterrupt):
            # Non-interactive or interrupted - deny by default
            approved = False

        # Grant all or none for simplicity (could be per-permission in production)
        return dict.fromkeys(permissions, approved)

    def _get_permission_description(self, permission: str) -> str:
        """Get human-readable description of permission."""
        descriptions = {
            "filesystem:read": "Read files and directories",
            "filesystem:write": "Write, modify, or delete files",
            "network:requests": "Make HTTP/HTTPS requests to external servers",
            "network:server": "Start a network server",
            "shell:execute": "Execute shell commands",
            "shell:read_env": "Read environment variables",
            "database:read": "Read command history database",
            "database:write": "Modify command history database",
            "system:info": "Access system information",
        }
        return descriptions.get(permission, "")

    def revoke_permission(self, plugin_name: str, permission: str) -> None:
        """
        Revoke a specific permission from a plugin.

        Args:
            plugin_name: Name of the plugin
            permission: Permission to revoke
        """
        if plugin_name in self.permissions:
            self.permissions[plugin_name][permission] = False
            self._save_permissions()
            logger.info(f"Revoked permission {permission} from {plugin_name}")

    def revoke_all_permissions(self, plugin_name: str) -> None:
        """
        Revoke all permissions from a plugin.

        Args:
            plugin_name: Name of the plugin
        """
        if plugin_name in self.permissions:
            del self.permissions[plugin_name]
            self._save_permissions()
            logger.info(f"Revoked all permissions from {plugin_name}")

    def get_plugin_permissions(self, plugin_name: str) -> dict[str, bool]:
        """
        Get all permissions for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dictionary of permission -> granted status
        """
        return self.permissions.get(plugin_name, {}).copy()

    def get_all_permissions(self) -> dict[str, dict[str, bool]]:
        """
        Get all plugin permissions.

        Returns:
            Dictionary mapping plugin_name -> {permission -> granted}
        """
        return self.permissions.copy()

    def check_and_enforce(
        self, plugin_name: str, permission: str, action_description: str = ""
    ) -> None:
        """
        Check permission and raise error if not granted.

        Args:
            plugin_name: Name of the plugin
            permission: Permission to check
            action_description: Description of the action (for error message)

        Raises:
            PermissionError: If permission is not granted
        """
        if not self.has_permission(plugin_name, permission):
            msg = f"Plugin '{plugin_name}' does not have permission: {permission}"
            if action_description:
                msg += f" (required for: {action_description})"
            raise PermissionError(msg)
