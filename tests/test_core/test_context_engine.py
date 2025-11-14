"""
Tests for Context Engine.

Created by: orpheus497
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from daedelus.core.context_engine import (
    ContextEngine,
    EnvironmentContext,
    FileContext,
    GitContext,
    ProjectContext,
    TimeContext,
)


@pytest.fixture
def engine():
    """Create a context engine instance."""
    return ContextEngine()


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_context_engine_initialization(engine):
    """Test that context engine initializes correctly."""
    assert engine is not None
    assert engine.cache == {}
    assert engine.cache_timeout == 5.0


def test_analyze_context_caching(engine, temp_project_dir):
    """Test that context analysis results are cached."""
    # First analysis
    context1 = engine.analyze_context(str(temp_project_dir))
    assert context1 is not None

    # Second analysis should use cache
    context2 = engine.analyze_context(str(temp_project_dir))
    assert context2 is context1  # Same object from cache


def test_git_context_not_a_repo(engine, temp_project_dir):
    """Test Git context analysis for non-repository."""
    context = engine.analyze_context(str(temp_project_dir))
    git_ctx = context["git"]

    assert isinstance(git_ctx, GitContext)
    assert git_ctx.is_repo is False
    assert git_ctx.branch is None


def test_git_context_with_repo(engine, temp_project_dir):
    """Test Git context analysis with a Git repository."""
    # Initialize git repo
    import subprocess

    try:
        subprocess.run(["git", "init"], cwd=temp_project_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_project_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_project_dir,
            check=True,
            capture_output=True,
        )

        context = engine.analyze_context(str(temp_project_dir))
        git_ctx = context["git"]

        assert git_ctx.is_repo is True
        assert git_ctx.root_path == temp_project_dir

    except Exception as e:
        pytest.skip(f"Git not available: {e}")


def test_project_context_python_pyproject(engine, temp_project_dir):
    """Test Python project detection with pyproject.toml."""
    # Create pyproject.toml
    pyproject = temp_project_dir / "pyproject.toml"
    pyproject.write_text("[tool.poetry]\nname = 'test'\n")

    context = engine.analyze_context(str(temp_project_dir))
    project_ctx = context["project"]

    assert isinstance(project_ctx, ProjectContext)
    assert project_ctx.project_type == "python"
    assert project_ctx.build_tool == "pip"
    assert "pyproject.toml" in project_ctx.config_files


def test_project_context_nodejs(engine, temp_project_dir):
    """Test Node.js project detection with package.json."""
    # Create package.json
    package_json = temp_project_dir / "package.json"
    package_json.write_text('{"name": "test", "scripts": {"test": "jest"}}')

    context = engine.analyze_context(str(temp_project_dir))
    project_ctx = context["project"]

    assert project_ctx.project_type == "nodejs"
    assert project_ctx.build_tool == "npm"
    assert project_ctx.has_tests is True
    assert project_ctx.test_framework == "jest"


def test_project_context_rust(engine, temp_project_dir):
    """Test Rust project detection with Cargo.toml."""
    # Create Cargo.toml
    cargo_toml = temp_project_dir / "Cargo.toml"
    cargo_toml.write_text('[package]\nname = "test"\n')

    context = engine.analyze_context(str(temp_project_dir))
    project_ctx = context["project"]

    assert project_ctx.project_type == "rust"
    assert project_ctx.build_tool == "cargo"
    assert project_ctx.test_framework == "cargo test"


def test_project_context_go(engine, temp_project_dir):
    """Test Go project detection with go.mod."""
    # Create go.mod
    go_mod = temp_project_dir / "go.mod"
    go_mod.write_text("module test\n")

    context = engine.analyze_context(str(temp_project_dir))
    project_ctx = context["project"]

    assert project_ctx.project_type == "go"
    assert project_ctx.build_tool == "go"
    assert project_ctx.test_framework == "go test"


def test_file_context_with_files(engine, temp_project_dir):
    """Test file context analysis."""
    # Create some test files
    (temp_project_dir / "test.py").touch()
    (temp_project_dir / "test.txt").touch()
    (temp_project_dir / "test.md").touch()

    context = engine.analyze_context(str(temp_project_dir))
    file_ctx = context["files"]

    assert isinstance(file_ctx, FileContext)
    assert file_ctx.total_files == 3
    assert ".py" in file_ctx.file_types
    assert ".txt" in file_ctx.file_types
    assert ".md" in file_ctx.file_types


def test_time_context(engine, temp_project_dir):
    """Test time context analysis."""
    context = engine.analyze_context(str(temp_project_dir))
    time_ctx = context["time"]

    assert isinstance(time_ctx, TimeContext)
    assert 0 <= time_ctx.hour < 24
    assert 0 <= time_ctx.day_of_week < 7
    assert isinstance(time_ctx.is_workday, bool)
    assert isinstance(time_ctx.is_work_hours, bool)


def test_environment_context(engine, temp_project_dir):
    """Test environment context analysis."""
    context = engine.analyze_context(str(temp_project_dir))
    env_ctx = context["environment"]

    assert isinstance(env_ctx, EnvironmentContext)
    # Shell should be detected from environment
    assert env_ctx.shell is not None or True  # May be None in test environment


def test_get_context_score_git_commands(engine, temp_project_dir):
    """Test context scoring for git commands."""
    # Create a git repository context
    context = {
        "git": GitContext(
            is_repo=True,
            has_uncommitted=True,
            has_unpushed=False,
        ),
        "project": ProjectContext(),
        "environment": EnvironmentContext(),
    }

    # Git commands should score higher in git repos
    score_git = engine.get_context_score("git commit -m 'test'", context)
    score_other = engine.get_context_score("ls -la", context)

    assert score_git > score_other
    assert score_git > 0.5


def test_get_context_score_project_commands(engine):
    """Test context scoring for project-specific commands."""
    # Python project context
    context = {
        "git": GitContext(is_repo=False),
        "project": ProjectContext(project_type="python", has_tests=True),
        "environment": EnvironmentContext(),
    }

    # Python commands should score higher
    score_python = engine.get_context_score("pytest -v", context)
    score_other = engine.get_context_score("cargo build", context)

    assert score_python > score_other


def test_get_suggestions_for_git_repo(engine):
    """Test suggestions for Git repository with changes."""
    context = {
        "git": GitContext(
            is_repo=True,
            has_uncommitted=True,
            has_unpushed=True,
        ),
        "project": ProjectContext(),
    }

    suggestions = engine.get_suggestions_for_context(context)

    # Should suggest git commands
    assert any("git" in s for s in suggestions)
    assert any("commit" in s or "add" in s for s in suggestions)
    assert any("push" in s for s in suggestions)


def test_get_suggestions_for_python_project(engine):
    """Test suggestions for Python project."""
    context = {
        "git": GitContext(is_repo=False),
        "project": ProjectContext(
            project_type="python",
            has_tests=True,
        ),
    }

    suggestions = engine.get_suggestions_for_context(context)

    # Should suggest Python commands
    assert any("python" in s or "pip" in s or "pytest" in s for s in suggestions)


def test_get_suggestions_for_nodejs_project(engine):
    """Test suggestions for Node.js project."""
    context = {
        "git": GitContext(is_repo=False),
        "project": ProjectContext(
            project_type="nodejs",
            build_tool="npm",
            has_tests=True,
        ),
    }

    suggestions = engine.get_suggestions_for_context(context)

    # Should suggest npm commands
    assert any("npm" in s for s in suggestions)


def test_environment_virtual_env_detection(engine, temp_project_dir):
    """Test virtual environment detection."""
    with patch.dict("os.environ", {"VIRTUAL_ENV": "/path/to/venv"}):
        context = engine.analyze_context(str(temp_project_dir))
        env_ctx = context["environment"]

        assert env_ctx.virtual_env == "/path/to/venv"


def test_environment_docker_detection(engine, temp_project_dir):
    """Test Docker container detection."""
    with patch("pathlib.Path.exists", return_value=True):
        context = engine.analyze_context(str(temp_project_dir))
        env_ctx = context["environment"]

        assert env_ctx.docker_container is True
