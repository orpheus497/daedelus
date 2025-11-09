"""
Dependency checking and graceful degradation utilities for Daedelus.

Provides utilities for checking optional dependencies and providing helpful
error messages when they're missing.

Created by: orpheus497
"""

import importlib
import logging
import sys
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Exception raised when a required dependency is missing."""

    def __init__(self, package: str, feature: str, install_cmd: str) -> None:
        """
        Initialize dependency error.

        Args:
            package: Name of the missing package
            feature: Feature that requires the package
            install_cmd: Command to install the package
        """
        self.package = package
        self.feature = feature
        self.install_cmd = install_cmd

        message = (
            f"\n{'='*70}\n"
            f"Missing Dependency: {package}\n"
            f"{'='*70}\n\n"
            f"The '{feature}' feature requires the '{package}' package.\n\n"
            f"To install it, run:\n"
            f"  {install_cmd}\n\n"
            f"For full installation with all features:\n"
            f"  pip install 'daedelus[llm]'  # For LLM features\n"
            f"  pip install -e .[dev]        # For development\n"
            f"\n{'='*70}\n"
        )
        super().__init__(message)


# Dependency registry with installation information
DEPENDENCY_INFO: Dict[str, Dict[str, str]] = {
    "fasttext": {
        "feature": "FastText embeddings (Phase 1)",
        "install": "pip install fasttext==0.9.2",
        "extra": "",
    },
    "annoy": {
        "feature": "Annoy vector search (Phase 1)",
        "install": "pip install annoy==1.17.3",
        "extra": "",
    },
    "llama_cpp": {
        "feature": "LLM inference (Phase 2)",
        "install": "pip install 'daedelus[llm]'",
        "extra": "llm",
    },
    "transformers": {
        "feature": "Transformers/PEFT (Phase 2)",
        "install": "pip install 'daedelus[llm]'",
        "extra": "llm",
    },
    "peft": {
        "feature": "PEFT/LoRA fine-tuning (Phase 2)",
        "install": "pip install 'daedelus[llm]'",
        "extra": "llm",
    },
    "rich": {
        "feature": "Rich terminal UI",
        "install": "pip install rich>=13.0.0",
        "extra": "",
    },
    "textual": {
        "feature": "TUI dashboard",
        "install": "pip install textual>=0.40.0",
        "extra": "",
    },
    "jinja2": {
        "feature": "Command templates",
        "install": "pip install jinja2>=3.1.0",
        "extra": "",
    },
}


def check_dependency(package: str, raise_on_missing: bool = False) -> bool:
    """
    Check if a package is installed.

    Args:
        package: Package name to check
        raise_on_missing: If True, raise DependencyError if missing

    Returns:
        True if package is available, False otherwise

    Raises:
        DependencyError: If raise_on_missing=True and package not found
    """
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        if raise_on_missing and package in DEPENDENCY_INFO:
            info = DEPENDENCY_INFO[package]
            raise DependencyError(package, info["feature"], info["install"])
        return False


def require_dependency(
    package: str,
    feature_name: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to require a dependency for a function.

    Args:
        package: Package name required
        feature_name: Optional custom feature name for error message

    Returns:
        Decorator function

    Example:
        @require_dependency("llama_cpp", "LLM inference")
        def generate_text(prompt: str) -> str:
            from llama_cpp import Llama
            # ... implementation
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not check_dependency(package):
                info = DEPENDENCY_INFO.get(
                    package,
                    {
                        "feature": feature_name or f"function {func.__name__}",
                        "install": f"pip install {package}",
                    },
                )
                raise DependencyError(package, info["feature"], info["install"])
            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_missing_dependencies(packages: List[str]) -> List[str]:
    """
    Get list of missing packages from a list.

    Args:
        packages: List of package names to check

    Returns:
        List of missing package names
    """
    return [pkg for pkg in packages if not check_dependency(pkg)]


def get_available_features() -> Dict[str, bool]:
    """
    Get dictionary of available features based on installed dependencies.

    Returns:
        Dictionary mapping feature names to availability status
    """
    features = {
        "embeddings": check_dependency("fasttext") and check_dependency("annoy"),
        "llm": check_dependency("llama_cpp"),
        "peft": check_dependency("peft") and check_dependency("transformers"),
        "templates": check_dependency("jinja2"),
        "dashboard": check_dependency("textual"),
        "rich_ui": check_dependency("rich"),
    }
    return features


def print_dependency_status() -> None:
    """Print status of all optional dependencies."""
    print("\nDaedelus Dependency Status")
    print("=" * 70)

    features = get_available_features()

    print("\nCore Features (Phase 1):")
    print(f"  Embeddings (FastText): {'✓' if features['embeddings'] else '✗ MISSING'}")

    print("\nOptional Features (Phase 2):")
    print(f"  LLM Inference:         {'✓' if features['llm'] else '✗ MISSING'}")
    print(f"  PEFT Fine-tuning:      {'✓' if features['peft'] else '✗ MISSING'}")

    print("\nUI Enhancements:")
    print(f"  Rich Terminal UI:      {'✓' if features['rich_ui'] else '✗ MISSING'}")
    print(f"  TUI Dashboard:         {'✓' if features['dashboard'] else '✗ MISSING'}")
    print(f"  Command Templates:     {'✓' if features['templates'] else '✗ MISSING'}")

    print("\n" + "=" * 70)

    missing = get_missing_dependencies(list(DEPENDENCY_INFO.keys()))
    if missing:
        print(f"\nTo install missing dependencies:")
        print(f"  pip install 'daedelus[llm]'  # All Phase 2 features")
        print(f"  pip install -e .             # Core features only")
    else:
        print("\n✓ All dependencies installed!")


class OptionalDependency:
    """
    Context manager for optional dependency usage with fallback.

    Example:
        with OptionalDependency("llama_cpp") as llama:
            if llama.available:
                from llama_cpp import Llama
                model = Llama(...)
            else:
                # Fallback implementation
                logger.warning("LLM not available, using fallback")
    """

    def __init__(self, package: str) -> None:
        """
        Initialize optional dependency context.

        Args:
            package: Package name to check
        """
        self.package = package
        self.available = check_dependency(package)

    def __enter__(self) -> "OptionalDependency":
        """Enter context."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit context."""
        pass


def safe_import(package: str, fallback: Optional[Any] = None) -> Any:
    """
    Safely import a package with optional fallback.

    Args:
        package: Package name to import
        fallback: Optional fallback value if import fails

    Returns:
        Imported module or fallback value

    Example:
        llama = safe_import("llama_cpp", fallback=None)
        if llama is not None:
            # Use llama.cpp
        else:
            # Use fallback
    """
    try:
        return importlib.import_module(package)
    except ImportError:
        if fallback is not None:
            logger.debug(f"Package {package} not available, using fallback")
            return fallback
        info = DEPENDENCY_INFO.get(package, {})
        logger.warning(
            f"Package {package} not available. "
            f"Feature '{info.get('feature', 'unknown')}' will be disabled. "
            f"Install with: {info.get('install', f'pip install {package}')}"
        )
        return None


# Feature flags based on available dependencies
FEATURES = get_available_features()


def is_feature_available(feature: str) -> bool:
    """
    Check if a feature is available based on dependencies.

    Args:
        feature: Feature name (embeddings, llm, peft, templates, dashboard, rich_ui)

    Returns:
        True if feature is available, False otherwise
    """
    return FEATURES.get(feature, False)


def require_feature(feature: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to require a feature for a function.

    Args:
        feature: Feature name required

    Returns:
        Decorator function

    Example:
        @require_feature("llm")
        def generate_command(description: str) -> str:
            # ... implementation
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not is_feature_available(feature):
                raise DependencyError(
                    feature,
                    f"feature '{feature}'",
                    f"See 'daedelus info' for installation instructions",
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


if __name__ == "__main__":
    # Allow running as script to check dependencies
    print_dependency_status()
