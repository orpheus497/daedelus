"""
Smoke tests for Daedalus.

Basic sanity checks to ensure the package is installed correctly
and core functionality works.

Created by: orpheus497
"""

import importlib
import sys

import pytest

import daedelus


def test_package_import():
    """Test that the daedelus package can be imported."""
    assert daedelus is not None
    assert hasattr(daedelus, "__version__")


def test_version_format():
    """Test that version string follows semantic versioning."""
    version = daedelus.__version__
    assert isinstance(version, str)
    assert len(version) > 0

    # Should be in format X.Y.Z
    parts = version.split(".")
    assert len(parts) >= 2  # At least major.minor


def test_version_number():
    """Test that version matches expected value."""
    assert daedelus.__version__ == "0.4.0"


def test_core_modules_importable():
    """Test that all core modules can be imported."""
    modules = [
        "daedelus.core.database",
        "daedelus.core.embeddings",
        "daedelus.core.vector_store",
        "daedelus.core.suggestions",
        "daedelus.core.safety",
        "daedelus.core.templates",
    ]

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert module is not None


def test_daemon_modules_importable():
    """Test that daemon modules can be imported."""
    modules = [
        "daedelus.daemon.daemon",
        "daedelus.daemon.ipc",
    ]

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert module is not None


def test_llm_modules_importable():
    """Test that LLM modules can be imported."""
    modules = [
        "daedelus.llm.llm_manager",
        "daedelus.llm.model_manager",
        "daedelus.llm.peft_trainer",
        "daedelus.llm.rag_pipeline",
        "daedelus.llm.command_explainer",
        "daedelus.llm.command_generator",
        "daedelus.llm.enhanced_suggestions",
        "daedelus.llm.web_search",
    ]

    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
            assert module is not None
        except ImportError as e:
            # LLM modules may have optional dependencies
            if "llama" in str(e) or "transformers" in str(e) or "peft" in str(e):
                pytest.skip(f"LLM dependencies not installed: {e}")
            else:
                raise


def test_utils_modules_importable():
    """Test that utility modules can be imported."""
    modules = [
        "daedelus.utils.config",
        "daedelus.utils.logging_config",
        "daedelus.utils.backup",
        "daedelus.utils.dependencies",
    ]

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert module is not None


def test_cli_module_importable():
    """Test that CLI module can be imported."""
    from daedelus.cli import main

    assert main is not None


def test_python_version():
    """Test that Python version meets minimum requirement."""
    assert sys.version_info >= (3, 10), "Python 3.10+ required"


def test_required_dependencies_available():
    """Test that required dependencies are available."""
    required = [
        "click",
        "numpy",
        "platformdirs",
        "yaml",  # pyyaml package, but imported as 'yaml'
    ]

    for package in required:
        try:
            importlib.import_module(package)
        except ImportError:
            pytest.fail(f"Required dependency '{package}' not available")


def test_optional_dependencies_check():
    """Test checking optional dependencies."""
    # These may or may not be available
    optional = [
        "fasttext",
        "annoy",
        "llama_cpp",
        "transformers",
        "peft",
    ]

    for package in optional:
        try:
            importlib.import_module(package)
            # If import succeeds, that's fine
        except ImportError:
            # If import fails, that's also fine for optional deps
            pass
