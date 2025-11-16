# src/daedelus/core/plugin_loader.py
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
import yaml

from daedelus.core.plugin_interface import DaedalusAPI, DaedalusPlugin

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Handles the discovery, loading, and management of plugins.
    """

    def __init__(
        self,
        internal_plugin_dir: Path,
        external_plugin_dir: Path,
        cli_cache_path: Path,
        permission_manager: "Any | None" = None,
    ):
        self.internal_plugin_dir = internal_plugin_dir
        self.external_plugin_dir = external_plugin_dir
        self.cli_cache_path = cli_cache_path
        self.permission_manager = permission_manager
        self.loaded_plugins: list[DaedalusPlugin] = []
        self.cli_commands: dict[str, dict[str, str]] = {}

    def discover_and_load_plugins(self):
        """
        Scans the plugin directories, validates, and loads all found plugins.
        """
        logger.info("Starting plugin discovery...")
        self.cli_commands = {}  # Reset on each load
        plugin_paths = self._scan_for_plugins()

        for plugin_path in plugin_paths:
            self._load_plugin(plugin_path)

        logger.info(f"Discovered and loaded {len(self.loaded_plugins)} plugins.")
        self._write_cli_commands_cache()

    def _scan_for_plugins(self) -> list[Path]:
        """
        Scans the internal and external plugin directories for valid plugins.
        A valid plugin is a directory containing a 'plugin.yaml' file.
        """
        plugin_paths = []

        # Scan internal plugins
        if self.internal_plugin_dir.is_dir():
            for potential_plugin in self.internal_plugin_dir.iterdir():
                if (potential_plugin / "plugin.yaml").is_file():
                    plugin_paths.append(potential_plugin)

        # Scan external plugins
        if self.external_plugin_dir.is_dir():
            for potential_plugin in self.external_plugin_dir.iterdir():
                if (potential_plugin / "plugin.yaml").is_file():
                    plugin_paths.append(potential_plugin)

        logger.debug(f"Found potential plugin paths: {plugin_paths}")
        return plugin_paths

    def _load_plugin(self, plugin_path: Path):
        """
        Loads a single plugin from the given path.
        """
        try:
            # 1. Read and validate manifest
            manifest = self._read_and_validate_manifest(plugin_path)
            plugin_name = manifest.get("plugin", {}).get("name", "unknown")
            logger.debug(f"Loading plugin '{plugin_name}' from {plugin_path}")

            # 2. Request permissions if permission manager available
            requested_permissions = manifest.get("plugin", {}).get("permissions", [])
            if self.permission_manager and requested_permissions:
                approved = self.permission_manager.request_permissions(
                    plugin_name,
                    requested_permissions,
                    auto_approve=True,  # Auto-approve during daemon startup
                )

                # Check if any permissions were denied
                denied = [p for p, granted in approved.items() if not granted]
                if denied:
                    logger.warning(
                        f"Plugin '{plugin_name}' was denied permissions: {denied}. "
                        "The plugin may not function correctly."
                    )

            # 3. Add plugin directory to sys.path for import
            sys.path.insert(0, str(plugin_path))

            # 4. Import the main class
            module_name, class_name = manifest["plugin"]["main_class"].split(":")
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)

            # 5. Instantiate the plugin with a patched API
            api = DaedalusAPI(plugin_name=plugin_name, permission_manager=self.permission_manager)

            def register_cli_command(command: "click.Command"):
                """Patched method to register a CLI command."""
                if not command.name:
                    logger.warning(
                        f"Plugin '{plugin_name}' tried to register a command with no name."
                    )
                    return
                # Get the callback function to extract module name
                callback_func = command.callback if hasattr(command, "callback") else None
                module_name = callback_func.__module__ if callback_func else "main"
                function_name = callback_func.__name__ if callback_func else command.name

                self.cli_commands[command.name] = {
                    "module": module_name,
                    "function": function_name,
                    "path": str(plugin_path),
                }
                logger.info(f"CLI command '{command.name}' registered by plugin '{plugin_name}'")

            api.register_cli_command = register_cli_command
            plugin_instance = plugin_class(api=api)

            # 6. Call the load method
            plugin_instance.load()

            # 7. Add to loaded plugins
            self.loaded_plugins.append(plugin_instance)
            logger.info(f"Successfully loaded plugin '{plugin_name}'")

        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {e}", exc_info=True)
        finally:
            # 8. Clean up sys.path
            if str(plugin_path) in sys.path:
                sys.path.remove(str(plugin_path))

    def _read_and_validate_manifest(self, plugin_path: Path) -> dict[str, Any]:
        """Reads and performs basic validation on the plugin.yaml manifest."""
        manifest_path = plugin_path / "plugin.yaml"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Manifest file not found in {plugin_path}")

        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        if not isinstance(manifest, dict) or "plugin" not in manifest:
            raise ValueError("Manifest must be a dictionary with a 'plugin' key.")

        plugin_meta = manifest["plugin"]
        required_keys = ["name", "version", "author", "description", "main_class"]
        for key in required_keys:
            if key not in plugin_meta:
                raise ValueError(f"Manifest is missing required key: 'plugin.{key}'")

        return manifest

    def _write_cli_commands_cache(self):
        """Writes the collected CLI commands to a JSON cache file."""
        try:
            with open(self.cli_cache_path, "w") as f:
                json.dump(self.cli_commands, f, indent=2)
            logger.info(
                f"Wrote {len(self.cli_commands)} CLI commands to cache: {self.cli_cache_path}"
            )
        except Exception as e:
            logger.error(f"Failed to write CLI command cache: {e}", exc_info=True)

    def get_loaded_plugins(self) -> list[DaedalusPlugin]:
        """
        Returns the list of successfully loaded plugin instances.
        """
        return self.loaded_plugins
