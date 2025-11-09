"""
Configuration management for Daedalus.

Handles loading, saving, and validating user configuration from YAML files.
Uses platform-specific directories for config and data storage.

Created by: orpheus497
"""

import copy
import logging
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_dir, user_data_dir

logger = logging.getLogger(__name__)


class Config:
    """
    Configuration manager for Daedalus.

    Provides a hierarchical configuration system with:
    - Default values
    - User overrides from config file
    - Runtime overrides

    Attributes:
        config_path: Path to the configuration file
        data_dir: Path to the data directory
        config: Dictionary containing all configuration values
    """

    # Default configuration values
    DEFAULT_CONFIG: dict[str, Any] = {
        "daemon": {
            "socket_path": None,  # Will be set dynamically
            "log_path": None,  # Will be set dynamically
            "pid_path": None,  # Will be set dynamically
            "startup_delay": 0.5,
            "max_workers": 4,
        },
        "model": {
            "embedding_dim": 128,
            "vocab_size": 50000,
            "model_path": None,  # Will be set dynamically
            "min_count": 2,
            "word_ngrams": 3,
            "epoch": 5,
        },
        "vector_store": {
            "index_type": "annoy",  # Phase 1: annoy, Phase 2: sqlite-vss
            "index_path": None,  # Will be set dynamically
            "n_trees": 10,
            "search_k": -1,  # -1 means use n_trees * n
        },
        "database": {
            "path": None,  # Will be set dynamically
            "backup_enabled": True,
            "backup_count": 5,
        },
        "privacy": {
            "excluded_paths": [
                "~/.ssh",
                "~/.gnupg",
                "~/.password-store",
            ],
            "excluded_patterns": [
                r"password",
                r"token",
                r"secret",
                r"api[_-]?key",
                r"aws[_-]?access",
            ],
            "history_retention_days": 90,
            "encrypt_sensitive": True,
        },
        "suggestions": {
            "max_suggestions": 5,
            "min_confidence": 0.3,
            "context_window": 10,  # Number of recent commands to consider
            "enable_fuzzy": True,
        },
        "performance": {
            "cache_size": 1000,
            "lazy_loading": True,
            "batch_size": 100,
        },
        # Phase 2 LLM settings (enabled by default)
        "llm": {
            "enabled": True,
            "model_path": None,
            "context_length": 2048,
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 100,
        },
        "peft": {
            "enabled": False,
            "adapter_path": None,
            "r": 8,
            "lora_alpha": 32,
            "lora_dropout": 0.1,
        },
    }

    def __init__(
        self,
        config_path: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file. If None, uses default location.
            data_dir: Path to data directory. If None, uses platform default.
        """
        # Set up directories
        self.config_dir = (
            Path(config_path).parent
            if config_path
            else Path(user_config_dir("daedelus", "orpheus497"))
        )
        self.data_dir = data_dir or Path(user_data_dir("daedelus", "orpheus497"))
        self.config_path = config_path or self.config_dir / "config.yaml"

        # Create directories if they don't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_config()

        # Set dynamic paths
        self._set_dynamic_paths()

        logger.info(f"Configuration loaded from {self.config_path}")

    def _load_config(self) -> dict[str, Any]:
        """
        Load configuration from file, falling back to defaults.

        Returns:
            Merged configuration dictionary
        """
        config = copy.deepcopy(self.DEFAULT_CONFIG)

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    user_config = yaml.safe_load(f) or {}

                # Deep merge user config into defaults
                config = self._deep_merge(config, user_config)
                logger.debug(f"Loaded user configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
                logger.info("Using default configuration")
        else:
            logger.info("No config file found, using defaults")

        return config

    def _set_dynamic_paths(self) -> None:
        """Set paths that depend on the data directory."""
        runtime_dir = self.data_dir / "runtime"
        runtime_dir.mkdir(exist_ok=True)

        # Daemon paths
        if self.config["daemon"]["socket_path"] is None:
            self.config["daemon"]["socket_path"] = str(runtime_dir / "daemon.sock")
        if self.config["daemon"]["log_path"] is None:
            self.config["daemon"]["log_path"] = str(self.data_dir / "daemon.log")
        if self.config["daemon"]["pid_path"] is None:
            self.config["daemon"]["pid_path"] = str(runtime_dir / "daemon.pid")

        # Model paths
        if self.config["model"]["model_path"] is None:
            self.config["model"]["model_path"] = str(self.data_dir / "model.bin")

        # Vector store paths
        if self.config["vector_store"]["index_path"] is None:
            self.config["vector_store"]["index_path"] = str(self.data_dir / "index")

        # Database path
        if self.config["database"]["path"] is None:
            self.config["database"]["path"] = str(self.data_dir / "history.db")

        # Phase 2 LLM paths - use shared models directory
        if self.config["llm"]["model_path"] is None:
            # Use ~/.local/share/models for shared model storage
            models_dir = Path.home() / ".local" / "share" / "models"
            self.config["llm"]["model_path"] = str(models_dir / "model.gguf")
        if self.config["peft"]["adapter_path"] is None:
            self.config["peft"]["adapter_path"] = str(self.data_dir / "llm" / "adapter")

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Dictionary with override values

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def save(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path (e.g., "daemon.socket_path")
            default: Default value if key not found

        Returns:
            Configuration value

        Example:
            >>> config = Config()
            >>> config.get("daemon.socket_path")
            '/home/user/.local/share/daedelus/runtime/daemon.sock'
        """
        keys = key_path.split(".")
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation.

        Args:
            key_path: Dot-separated path (e.g., "daemon.socket_path")
            value: Value to set

        Example:
            >>> config = Config()
            >>> config.set("suggestions.max_suggestions", 10)
        """
        keys = key_path.split(".")
        target = self.config

        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        target[keys[-1]] = value

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access."""
        return self.config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style assignment."""
        self.config[key] = value

    def __repr__(self) -> str:
        """String representation."""
        return f"Config(config_path={self.config_path}, data_dir={self.data_dir})"
