"""
Context Engine for Daedelus.

Provides intelligent context awareness for command suggestions:
- Git repository detection and branch-aware suggestions
- Project type detection (Python, Node.js, Rust, Go, Java, etc.)
- Recent file modification tracking
- Time-of-day pattern learning
- Directory-based context awareness
- Environment variable detection

This enables context-specific suggestions like:
- "git push" when on a feature branch with uncommitted changes
- "npm test" in a Node.js project
- "cargo build" in a Rust project
- "pytest" in a Python project with tests/

Created by: orpheus497
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GitContext:
    """Git repository context information."""

    is_repo: bool
    branch: str | None = None
    has_uncommitted: bool = False
    has_unpushed: bool = False
    remote_url: str | None = None
    root_path: Path | None = None
    is_detached: bool = False


@dataclass
class ProjectContext:
    """Project type and configuration context."""

    project_type: str | None = None  # python, nodejs, rust, go, java, etc.
    build_tool: str | None = None  # pip, npm, cargo, go, maven, gradle
    test_framework: str | None = None  # pytest, jest, cargo test, go test
    config_files: list[str] = None  # pyproject.toml, package.json, Cargo.toml
    has_tests: bool = False
    has_ci: bool = False  # .github/workflows, .gitlab-ci.yml, etc.

    def __post_init__(self) -> None:
        if self.config_files is None:
            self.config_files = []


@dataclass
class FileContext:
    """File system context information."""

    recently_modified: list[Path]  # Files modified in last 5 minutes
    recently_created: list[Path]  # Files created in last 5 minutes
    file_types: set[str]  # Extensions present in directory
    total_files: int


@dataclass
class TimeContext:
    """Time-based context information."""

    hour: int  # 0-23
    day_of_week: int  # 0-6 (Monday = 0)
    is_workday: bool
    is_work_hours: bool  # 9am-5pm on workdays


@dataclass
class EnvironmentContext:
    """Environment and system context."""

    virtual_env: str | None = None  # Active virtual environment
    conda_env: str | None = None  # Active conda environment
    docker_container: bool = False  # Running inside Docker
    ssh_connection: bool = False  # Connected via SSH
    shell: str | None = None  # bash, zsh, fish


class ContextEngine:
    """
    Context engine for intelligent command suggestions.

    Analyzes the current working directory, git status, project type,
    recent activity, and other contextual factors to provide better
    command suggestions.

    Example usage:
        engine = ContextEngine()
        context = engine.analyze_context("/path/to/project")

        # Use context for suggestions
        if context.git.is_repo and context.git.has_uncommitted:
            suggest("git add .")
            suggest("git commit -m 'message'")

        if context.project.project_type == "python":
            suggest("pytest")
            suggest("python -m pip install -e .")
    """

    def __init__(self) -> None:
        """Initialize the context engine."""
        self.cache: dict[str, Any] = {}
        self.cache_timeout = 5.0  # Cache context for 5 seconds

    def analyze_context(self, cwd: str) -> dict[str, Any]:
        """
        Analyze the current context for a given directory.

        Args:
            cwd: Current working directory path

        Returns:
            Dictionary containing all context information
        """
        cwd_path = Path(cwd).resolve()

        # Check cache
        cache_key = str(cwd_path)
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_timeout:
                return cached_data

        # Gather all context
        context = {
            "git": self._analyze_git_context(cwd_path),
            "project": self._analyze_project_context(cwd_path),
            "files": self._analyze_file_context(cwd_path),
            "time": self._analyze_time_context(),
            "environment": self._analyze_environment_context(),
        }

        # Update cache
        self.cache[cache_key] = (context, datetime.now())

        return context

    def _analyze_git_context(self, cwd: Path) -> GitContext:
        """
        Analyze Git repository context.

        Args:
            cwd: Current working directory

        Returns:
            GitContext with repository information
        """
        try:
            # Check if in a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2.0,
            )

            if result.returncode != 0:
                return GitContext(is_repo=False)

            # Get branch name
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
            is_detached = branch == "HEAD"

            # Check for uncommitted changes
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            has_uncommitted = bool(status_result.stdout.strip())

            # Check for unpushed commits
            unpushed_result = subprocess.run(
                ["git", "log", "@{u}..", "--oneline"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            has_unpushed = bool(unpushed_result.stdout.strip())

            # Get remote URL
            remote_result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else None

            # Get repository root
            root_result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            root_path = Path(root_result.stdout.strip()) if root_result.returncode == 0 else None

            return GitContext(
                is_repo=True,
                branch=branch,
                has_uncommitted=has_uncommitted,
                has_unpushed=has_unpushed,
                remote_url=remote_url,
                root_path=root_path,
                is_detached=is_detached,
            )

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.debug(f"Git context analysis failed: {e}")
            return GitContext(is_repo=False)

    def _analyze_project_context(self, cwd: Path) -> ProjectContext:
        """
        Analyze project type and build configuration.

        Args:
            cwd: Current working directory

        Returns:
            ProjectContext with project information
        """
        context = ProjectContext()

        # Python project detection
        if (cwd / "pyproject.toml").exists():
            context.project_type = "python"
            context.build_tool = "pip"
            context.config_files.append("pyproject.toml")

            # Check for test framework
            if (cwd / "pytest.ini").exists() or (cwd / "tests").exists():
                context.test_framework = "pytest"
                context.has_tests = True

        elif (cwd / "setup.py").exists():
            context.project_type = "python"
            context.build_tool = "setuptools"
            context.config_files.append("setup.py")

        elif (cwd / "requirements.txt").exists():
            context.project_type = "python"
            context.build_tool = "pip"
            context.config_files.append("requirements.txt")

        # Node.js project detection
        elif (cwd / "package.json").exists():
            context.project_type = "nodejs"
            context.config_files.append("package.json")

            # Detect package manager
            if (cwd / "package-lock.json").exists():
                context.build_tool = "npm"
            elif (cwd / "yarn.lock").exists():
                context.build_tool = "yarn"
            elif (cwd / "pnpm-lock.yaml").exists():
                context.build_tool = "pnpm"
            else:
                context.build_tool = "npm"

            # Check for test framework
            try:
                with open(cwd / "package.json") as f:
                    pkg = json.load(f)
                    scripts = pkg.get("scripts", {})
                    if "test" in scripts:
                        context.has_tests = True
                        # Detect test framework
                        if "jest" in scripts.get("test", ""):
                            context.test_framework = "jest"
                        elif "mocha" in scripts.get("test", ""):
                            context.test_framework = "mocha"
                        elif "vitest" in scripts.get("test", ""):
                            context.test_framework = "vitest"
            except Exception:
                pass

        # Rust project detection
        elif (cwd / "Cargo.toml").exists():
            context.project_type = "rust"
            context.build_tool = "cargo"
            context.test_framework = "cargo test"
            context.config_files.append("Cargo.toml")
            context.has_tests = (cwd / "tests").exists() or (cwd / "src").exists()

        # Go project detection
        elif (cwd / "go.mod").exists():
            context.project_type = "go"
            context.build_tool = "go"
            context.test_framework = "go test"
            context.config_files.append("go.mod")
            # Go tests are typically *_test.go files
            context.has_tests = any(cwd.glob("**/*_test.go"))

        # Java/Maven project detection
        elif (cwd / "pom.xml").exists():
            context.project_type = "java"
            context.build_tool = "maven"
            context.config_files.append("pom.xml")
            context.has_tests = (cwd / "src" / "test").exists()

        # Java/Gradle project detection
        elif (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
            context.project_type = "java"
            context.build_tool = "gradle"
            context.config_files.append("build.gradle")
            context.has_tests = (cwd / "src" / "test").exists()

        # Ruby project detection
        elif (cwd / "Gemfile").exists():
            context.project_type = "ruby"
            context.build_tool = "bundler"
            context.config_files.append("Gemfile")
            context.has_tests = (cwd / "spec").exists() or (cwd / "test").exists()

        # Check for CI/CD configuration
        context.has_ci = any(
            [
                (cwd / ".github" / "workflows").exists(),
                (cwd / ".gitlab-ci.yml").exists(),
                (cwd / ".circleci").exists(),
                (cwd / "Jenkinsfile").exists(),
                (cwd / ".travis.yml").exists(),
            ]
        )

        return context

    def _analyze_file_context(self, cwd: Path) -> FileContext:
        """
        Analyze recent file activity.

        Args:
            cwd: Current working directory

        Returns:
            FileContext with file activity information
        """
        recently_modified = []
        recently_created = []
        file_types = set()
        total_files = 0

        now = datetime.now()
        five_minutes_ago = now - timedelta(minutes=5)

        try:
            # Scan directory (non-recursive for performance)
            for item in cwd.iterdir():
                if item.is_file():
                    total_files += 1

                    # Track file extensions
                    if item.suffix:
                        file_types.add(item.suffix)

                    # Check modification time
                    try:
                        mtime = datetime.fromtimestamp(item.stat().st_mtime)
                        if mtime > five_minutes_ago:
                            recently_modified.append(item)

                        # Check creation time (approximate)
                        ctime = datetime.fromtimestamp(item.stat().st_ctime)
                        if ctime > five_minutes_ago:
                            recently_created.append(item)
                    except Exception:
                        continue

        except Exception as e:
            logger.debug(f"File context analysis failed: {e}")

        return FileContext(
            recently_modified=recently_modified[:10],  # Limit to 10 most recent
            recently_created=recently_created[:10],
            file_types=file_types,
            total_files=total_files,
        )

    def _analyze_time_context(self) -> TimeContext:
        """
        Analyze time-based context.

        Returns:
            TimeContext with time information
        """
        now = datetime.now()
        hour = now.hour
        day_of_week = now.weekday()  # 0 = Monday, 6 = Sunday

        is_workday = day_of_week < 5  # Monday-Friday
        is_work_hours = is_workday and 9 <= hour < 17

        return TimeContext(
            hour=hour,
            day_of_week=day_of_week,
            is_workday=is_workday,
            is_work_hours=is_work_hours,
        )

    def _analyze_environment_context(self) -> EnvironmentContext:
        """
        Analyze environment and system context.

        Returns:
            EnvironmentContext with environment information
        """
        context = EnvironmentContext()

        # Virtual environment detection
        context.virtual_env = os.environ.get("VIRTUAL_ENV")
        context.conda_env = os.environ.get("CONDA_DEFAULT_ENV")

        # Docker detection
        context.docker_container = (
            Path("/.dockerenv").exists() or os.environ.get("DOCKER_CONTAINER") == "true"
        )

        # SSH connection detection
        context.ssh_connection = bool(os.environ.get("SSH_CONNECTION"))

        # Shell detection
        shell = os.environ.get("SHELL", "")
        if shell:
            context.shell = Path(shell).name

        return context

    def _get_ctx_value(self, ctx: Any, key: str, default: Any = None) -> Any:
        """Helper to get value from context (dict or dataclass)."""
        if ctx is None:
            return default
        if isinstance(ctx, dict):
            return ctx.get(key, default)
        return getattr(ctx, key, default)

    def get_context_score(self, command: str, context: dict[str, Any]) -> float:
        """
        Calculate relevance score for a command based on context.

        Args:
            command: Command string
            context: Context dictionary from analyze_context()

        Returns:
            Relevance score (0.0 - 1.0), higher = more relevant
        """
        score = 0.5  # Base score

        git_ctx = context.get("git")
        project_ctx = context.get("project")
        env_ctx = context.get("environment")

        # Git command scoring
        if git_ctx and self._get_ctx_value(git_ctx, "is_repo"):
            if command.startswith("git"):
                score += 0.3

                # Boost specific git commands based on state
                has_uncommitted = self._get_ctx_value(git_ctx, "has_uncommitted", False)
                has_unpushed = self._get_ctx_value(git_ctx, "has_unpushed", False)

                if has_uncommitted:
                    if "git add" in command or "git commit" in command:
                        score += 0.2

                if has_unpushed:
                    if "git push" in command:
                        score += 0.2

        # Project-specific command scoring
        if project_ctx:
            project_type = self._get_ctx_value(project_ctx, "project_type")
            self._get_ctx_value(project_ctx, "build_tool")

            if project_type == "python":
                if any(cmd in command for cmd in ["python", "pip", "pytest", "poetry"]):
                    score += 0.3
            elif project_type == "nodejs":
                if any(cmd in command for cmd in ["npm", "node", "yarn", "pnpm"]):
                    score += 0.3
            elif project_type == "rust":
                if any(cmd in command for cmd in ["cargo", "rustc", "rust"]):
                    score += 0.3
            elif project_type == "go":
                if command.startswith("go "):
                    score += 0.3

            # Boost test commands in projects with tests
            has_tests = self._get_ctx_value(project_ctx, "has_tests", False)
            if has_tests:
                test_keywords = ["test", "pytest", "jest", "mocha", "cargo test", "go test"]
                if any(kw in command for kw in test_keywords):
                    score += 0.2

        # Virtual environment scoring
        if env_ctx:
            if self._get_ctx_value(env_ctx, "virtual_env") or self._get_ctx_value(
                env_ctx, "conda_env"
            ):
                if any(cmd in command for cmd in ["pip", "python", "conda"]):
                    score += 0.1

        # Clamp score to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    def get_suggestions_for_context(self, context: dict[str, Any]) -> list[str]:
        """
        Generate context-aware command suggestions.

        Args:
            context: Context dictionary from analyze_context()

        Returns:
            List of suggested commands
        """
        suggestions = []

        git_ctx = context.get("git")
        project_ctx = context.get("project")

        # Git suggestions
        if git_ctx and self._get_ctx_value(git_ctx, "is_repo"):
            if self._get_ctx_value(git_ctx, "has_uncommitted"):
                suggestions.append("git status")
                suggestions.append("git diff")
                suggestions.append("git add .")
                suggestions.append("git commit -m 'Update'")

            if self._get_ctx_value(git_ctx, "has_unpushed"):
                suggestions.append("git push")

            if not self._get_ctx_value(git_ctx, "has_uncommitted") and not self._get_ctx_value(
                git_ctx, "has_unpushed"
            ):
                suggestions.append("git pull")

        # Project-specific suggestions
        if project_ctx:
            project_type = self._get_ctx_value(project_ctx, "project_type")

            if project_type == "python":
                suggestions.extend(
                    [
                        "python -m pip install -e .",
                        "python -m pip install -r requirements.txt",
                    ]
                )
                if self._get_ctx_value(project_ctx, "has_tests"):
                    suggestions.append("pytest")
                    suggestions.append("pytest -v")

            elif project_type == "nodejs":
                build_tool = self._get_ctx_value(project_ctx, "build_tool", "npm")
                suggestions.extend([f"{build_tool} install", f"{build_tool} run dev"])
                if self._get_ctx_value(project_ctx, "has_tests"):
                    suggestions.append(f"{build_tool} test")

            elif project_type == "rust":
                suggestions.extend(["cargo build", "cargo run"])
                if self._get_ctx_value(project_ctx, "has_tests"):
                    suggestions.append("cargo test")

            elif project_type == "go":
                suggestions.extend(["go build", "go run ."])
                if self._get_ctx_value(project_ctx, "has_tests"):
                    suggestions.append("go test ./...")

        return suggestions[:5]  # Limit to top 5 suggestions
