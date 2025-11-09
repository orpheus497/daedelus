"""
Comprehensive unit tests for Config.

Tests all major functionality:
- Configuration loading
- Default values
- User overrides
- Dynamic path resolution
- Deep merging
- Get/set with dot notation
- Save functionality

Created by: orpheus497
"""

import yaml

from daedelus.utils.config import Config


class TestConfigInit:
    """Test configuration initialization."""

    def test_init_creates_directories(self, temp_dir):
        """Test that init creates necessary directories."""
        config_path = temp_dir / "config.yaml"
        data_dir = temp_dir / "data"

        Config(config_path=config_path, data_dir=data_dir)

        assert config_path.parent.exists()
        assert data_dir.exists()

    def test_init_loads_defaults(self, temp_dir):
        """Test that defaults are loaded."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        assert config.config is not None
        assert "daemon" in config.config
        assert "model" in config.config
        assert "database" in config.config

    def test_init_sets_dynamic_paths(self, temp_dir):
        """Test that dynamic paths are set."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        assert config.config["daemon"]["socket_path"] is not None
        assert config.config["daemon"]["log_path"] is not None
        assert config.config["model"]["model_path"] is not None
        assert config.config["database"]["path"] is not None

    def test_init_without_existing_config(self, temp_dir):
        """Test initialization without existing config file."""
        config = Config(
            config_path=temp_dir / "nonexistent.yaml",
            data_dir=temp_dir / "data",
        )

        # Should use defaults
        assert config.config["model"]["embedding_dim"] == 128
        assert config.config["suggestions"]["max_suggestions"] == 5

    def test_init_with_existing_config(self, temp_dir):
        """Test initialization with existing config file."""
        config_path = temp_dir / "config.yaml"

        # Create config file with overrides
        user_config = {
            "model": {
                "embedding_dim": 256,
            },
            "suggestions": {
                "max_suggestions": 10,
            },
        }
        with open(config_path, "w") as f:
            yaml.dump(user_config, f)

        config = Config(config_path=config_path, data_dir=temp_dir / "data")

        # Should merge with defaults
        assert config.config["model"]["embedding_dim"] == 256
        assert config.config["suggestions"]["max_suggestions"] == 10
        # Defaults should still be there
        assert config.config["model"]["vocab_size"] == 50000


class TestDefaultConfig:
    """Test default configuration values."""

    def test_daemon_defaults(self, temp_dir):
        """Test daemon default configuration."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        assert config.config["daemon"]["startup_delay"] == 0.5
        assert config.config["daemon"]["max_workers"] == 4

    def test_model_defaults(self, temp_dir):
        """Test model default configuration."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        assert config.config["model"]["embedding_dim"] == 128
        assert config.config["model"]["vocab_size"] == 50000
        assert config.config["model"]["min_count"] == 2
        assert config.config["model"]["word_ngrams"] == 3
        assert config.config["model"]["epoch"] == 5

    def test_suggestions_defaults(self, temp_dir):
        """Test suggestions default configuration."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        assert config.config["suggestions"]["max_suggestions"] == 5
        assert config.config["suggestions"]["min_confidence"] == 0.3
        assert config.config["suggestions"]["context_window"] == 10

    def test_privacy_defaults(self, temp_dir):
        """Test privacy default configuration."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        assert config.config["privacy"]["history_retention_days"] == 90
        assert config.config["privacy"]["encrypt_sensitive"] is True
        assert len(config.config["privacy"]["excluded_paths"]) > 0


class TestDeepMerge:
    """Test deep merge functionality."""

    def test_deep_merge_simple(self, temp_dir):
        """Test simple deep merge."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = config._deep_merge(base, override)

        assert result["a"] == 1
        assert result["b"] == 3
        assert result["c"] == 4

    def test_deep_merge_nested(self, temp_dir):
        """Test nested deep merge."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        base = {
            "level1": {
                "level2": {
                    "a": 1,
                    "b": 2,
                }
            }
        }
        override = {
            "level1": {
                "level2": {
                    "b": 99,
                    "c": 3,
                }
            }
        }

        result = config._deep_merge(base, override)

        assert result["level1"]["level2"]["a"] == 1
        assert result["level1"]["level2"]["b"] == 99
        assert result["level1"]["level2"]["c"] == 3

    def test_deep_merge_preserves_unrelated_keys(self, temp_dir):
        """Test that deep merge preserves unrelated keys."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        base = {"key1": {"a": 1, "b": 2}, "key2": {"x": 10}}
        override = {"key1": {"b": 99}}

        result = config._deep_merge(base, override)

        assert result["key1"]["a"] == 1
        assert result["key1"]["b"] == 99
        assert result["key2"]["x"] == 10


class TestGetSet:
    """Test get/set methods with dot notation."""

    def test_get_simple_key(self, temp_dir):
        """Test getting a simple key."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        value = config.get("model.embedding_dim")

        assert value == 128

    def test_get_nested_key(self, temp_dir):
        """Test getting a nested key."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        value = config.get("suggestions.max_suggestions")

        assert value == 5

    def test_get_nonexistent_key(self, temp_dir):
        """Test getting non-existent key returns default."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        value = config.get("nonexistent.key", default=42)

        assert value == 42

    def test_get_nonexistent_key_no_default(self, temp_dir):
        """Test getting non-existent key without default returns None."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        value = config.get("nonexistent.key")

        assert value is None

    def test_set_simple_key(self, temp_dir):
        """Test setting a simple key."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        config.set("model.embedding_dim", 256)

        assert config.get("model.embedding_dim") == 256

    def test_set_nested_key(self, temp_dir):
        """Test setting a nested key."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        config.set("suggestions.max_suggestions", 10)

        assert config.get("suggestions.max_suggestions") == 10

    def test_set_new_key(self, temp_dir):
        """Test setting a new key that doesn't exist."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        config.set("new.nested.key", "value")

        assert config.get("new.nested.key") == "value"


class TestDictAccess:
    """Test dictionary-style access."""

    def test_getitem(self, temp_dir):
        """Test dictionary-style get."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        value = config["model"]

        assert isinstance(value, dict)
        assert value["embedding_dim"] == 128

    def test_setitem(self, temp_dir):
        """Test dictionary-style set."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        config["custom_key"] = {"value": 42}

        assert config["custom_key"]["value"] == 42


class TestSave:
    """Test configuration saving."""

    def test_save_creates_file(self, temp_dir):
        """Test that save creates config file."""
        config_path = temp_dir / "config.yaml"
        config = Config(config_path=config_path, data_dir=temp_dir / "data")

        config.save()

        assert config_path.exists()

    def test_save_writes_config(self, temp_dir):
        """Test that saved config can be loaded."""
        config_path = temp_dir / "config.yaml"
        config = Config(config_path=config_path, data_dir=temp_dir / "data")

        # Modify config
        config.set("model.embedding_dim", 512)
        config.save()

        # Load saved config
        with open(config_path) as f:
            saved = yaml.safe_load(f)

        assert saved["model"]["embedding_dim"] == 512

    def test_save_and_reload(self, temp_dir):
        """Test save and reload preserves values."""
        config_path = temp_dir / "config.yaml"

        # Create and modify config
        config1 = Config(config_path=config_path, data_dir=temp_dir / "data")
        config1.set("suggestions.max_suggestions", 15)
        config1.save()

        # Reload
        config2 = Config(config_path=config_path, data_dir=temp_dir / "data")

        assert config2.get("suggestions.max_suggestions") == 15


class TestDynamicPaths:
    """Test dynamic path resolution."""

    def test_socket_path_set(self, temp_dir):
        """Test that socket path is set dynamically."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        socket_path = config.get("daemon.socket_path")

        assert socket_path is not None
        assert "daemon.sock" in socket_path

    def test_log_path_set(self, temp_dir):
        """Test that log path is set dynamically."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        log_path = config.get("daemon.log_path")

        assert log_path is not None
        assert "daemon.log" in log_path

    def test_model_path_set(self, temp_dir):
        """Test that model path is set dynamically."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        model_path = config.get("model.model_path")

        assert model_path is not None
        assert "model.bin" in model_path

    def test_database_path_set(self, temp_dir):
        """Test that database path is set dynamically."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        db_path = config.get("database.path")

        assert db_path is not None
        assert "history.db" in db_path


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_yaml_file(self, temp_dir):
        """Test handling of invalid YAML file."""
        config_path = temp_dir / "config.yaml"

        # Write invalid YAML
        with open(config_path, "w") as f:
            f.write("invalid: yaml: content:")

        # Should fall back to defaults without crashing
        config = Config(config_path=config_path, data_dir=temp_dir / "data")

        # Should have default values
        assert config.get("model.embedding_dim") == 128


class TestRepr:
    """Test string representation."""

    def test_repr(self, temp_dir):
        """Test __repr__ method."""
        config = Config(
            config_path=temp_dir / "config.yaml",
            data_dir=temp_dir / "data",
        )

        repr_str = repr(config)

        assert "Config" in repr_str
        assert str(config.config_path) in repr_str
        assert str(config.data_dir) in repr_str
