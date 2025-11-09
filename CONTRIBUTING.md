# Contributing to Daedalus

First off, thank you for considering contributing to Daedalus! 🎉

This document provides guidelines and information to help you contribute effectively.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style & Quality](#code-style--quality)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Project Architecture](#project-architecture)
- [Release Process](#release-process)

---

## Code of Conduct

**Be respectful, collaborative, and constructive**. We're all here to build something great.

- Be welcoming to new contributors
- Be patient with questions
- Focus on the code, not the person
- Assume good intentions
- Give and accept constructive feedback gracefully

---

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates.

**Good bug reports include**:
- **Clear title** - Brief but descriptive
- **Description** - What happened vs what you expected
- **Steps to reproduce** - Numbered list of steps
- **System information**:
  ```bash
  daedelus info
  python --version
  uname -a  # or equivalent
  ```
- **Logs** - Relevant snippets from `~/.local/share/daedelus/daemon.log`
- **Configuration** - Relevant parts of `~/.config/daedelus/config.yaml`

**Example**:
```markdown
## Bug: Daemon crashes on startup with LLM enabled

**Description**: Daemon starts fine with Phase 1 only, but crashes immediately when LLM is enabled.

**Steps to Reproduce**:
1. Install daedelus: `pip install -e .`
2. Download GGUF model to `~/.local/share/models/model.gguf`
3. LLM is enabled by default in config
4. Start daemon: `daedelus start --foreground`
5. Daemon crashes with error...

**Expected**: Daemon starts and loads LLM model

**Actual**: Crash with error: "RuntimeError: Failed to load model..."

**System Info**:
- OS: Ubuntu 22.04
- Python: 3.11.5
- Daedalus: 0.2.0

**Logs**:
```
[ERROR] Failed to load LLM model: ...
```
```

### Suggesting Features

Feature suggestions are welcome! Please provide:

- **Clear use case** - Why is this needed?
- **Examples** - Show what it would look like
- **Scope** - Which phase does this fit into (1, 2, or 3)?
- **Alternatives** - What other approaches did you consider?

**Consider**:
- Does this align with Daedalus's privacy-first philosophy?
- Is it 100% FOSS compatible?
- Does it fit the current architecture?

### Contributing Code

We love code contributions! Here's how:

1. **Find or create an issue** - Discuss before coding
2. **Fork and clone** the repository
3. **Create a branch** - Use descriptive name: `feature/add-vim-plugin` or `fix/daemon-crash`
4. **Write code** - Follow our code style
5. **Add tests** - Cover new functionality
6. **Update docs** - Keep documentation in sync
7. **Submit PR** - Link to the issue

---

## Development Setup

### Prerequisites

- **Python 3.10, 3.11, or 3.12** (3.10+ required)
- **Git** for version control
- **Build tools** for FastText compilation
  ```bash
  # Ubuntu/Debian
  sudo apt install build-essential python3-dev

  # macOS
  xcode-select --install

  # Fedora
  sudo dnf install gcc-c++ python3-devel
  ```

### Initial Setup

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/daedelus.git
cd daedelus

# 3. Add upstream remote
git remote add upstream https://github.com/orpheus497/daedelus.git

# 4. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 5. Install in development mode
pip install -e .[dev]

# 6. Install Phase 2 dependencies (optional)
pip install -r requirements-llm.txt

# 7. Set up pre-commit hooks
pre-commit install
```

### Pre-Commit Hooks Setup

We use **pre-commit** to automatically check code quality before commits.

#### Installation

```bash
# Install pre-commit (included in requirements-dev.txt)
pip install pre-commit

# Install the git hook scripts
pre-commit install
```

#### What Gets Checked

Our pre-commit hooks run:
1. **Black** - Code formatting (auto-fixes)
2. **isort** - Import sorting (auto-fixes)
3. **Ruff** - Fast linting (some auto-fixes)
4. **mypy** - Type checking (must pass)
5. **Bandit** - Security scanning (must pass)
6. **File checks** - Trailing whitespace, EOF, large files, etc.

#### Running Hooks Manually

```bash
# Run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run mypy --all-files

# Skip hooks for a commit (use sparingly!)
git commit --no-verify -m "message"
```

#### Troubleshooting Pre-Commit

**Hook fails with "command not found"**:
```bash
# Reinstall hooks
pre-commit clean
pre-commit install
```

**Black/isort changes conflict**:
```bash
# Run multiple times until stable
pre-commit run --all-files
pre-commit run --all-files
```

**mypy errors**:
- Fix type hint issues
- Add `# type: ignore` comments (sparingly!)
- Update type stubs if needed

---

## Development Workflow

### 1. Create a Feature Branch

```bash
# Update main
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write code following our [code style](#code-style--quality)
- Add tests for new functionality
- Update documentation
- Run tests frequently

### 3. Commit Changes

```bash
# Stage changes
git add path/to/changed/files

# Commit (pre-commit hooks run automatically)
git commit -m "Add feature: description"

# If hooks fail, fix issues and retry
# Hooks auto-fix formatting, you just need to re-add and re-commit
git add -u
git commit -m "Add feature: description"
```

### 4. Keep Branch Updated

```bash
# Fetch upstream changes
git fetch upstream

# Rebase on main (keeps history clean)
git rebase upstream/main

# Or merge if rebase is problematic
git merge upstream/main
```

### 5. Push and Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create PR on GitHub
# Link to related issue
# Describe changes and why they're needed
```

---

## Code Style & Quality

### Python Style

We follow **Black** formatting with these conventions:

- **Line length**: 100 characters (Black default: 88, we use 100)
- **Quotes**: Double quotes for strings
- **Type hints**: Required for all functions
- **Docstrings**: Google style, required for public APIs

### Code Quality Tools

#### Black (Formatting)

```bash
# Format all code
black src/daedelus tests/

# Check without modifying
black --check src/daedelus tests/
```

Config in `pyproject.toml`:
```toml
[tool.black]
line-length = 100
target-version = ['py310', 'py311', 'py312']
```

#### isort (Import Sorting)

```bash
# Sort imports
isort src/daedelus tests/

# Check without modifying
isort --check src/daedelus tests/
```

Config in `pyproject.toml`:
```toml
[tool.isort]
profile = "black"
line_length = 100
```

#### Ruff (Linting)

```bash
# Check for issues
ruff check src/daedelus tests/

# Auto-fix issues
ruff check --fix src/daedelus tests/
```

Config in `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py310"
```

#### mypy (Type Checking)

```bash
# Type check
mypy src/daedelus

# Strict mode (recommended)
mypy --strict src/daedelus
```

Config in `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.10"
strict = true
```

#### Bandit (Security)

```bash
# Security scan
bandit -r src/daedelus

# With config file
bandit -c pyproject.toml -r src/daedelus
```

### Type Hints

**Always use type hints**:

```python
# Good
def suggest_commands(partial: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Get command suggestions."""
    ...

# Bad
def suggest_commands(partial, max_results=5):
    """Get command suggestions."""
    ...
```

**Use modern type syntax**:
```python
from typing import List, Dict, Optional, Any

# Function signature
def process(data: List[str], config: Optional[Dict[str, Any]] = None) -> bool:
    ...
```

### Docstrings

Use **Google style** docstrings:

```python
def train_model(commands: List[str], epochs: int = 3) -> Path:
    """Train embedding model on command history.

    Args:
        commands: List of command strings to train on
        epochs: Number of training epochs (default: 3)

    Returns:
        Path to saved model file

    Raises:
        RuntimeError: If training fails
        ValueError: If commands list is empty

    Example:
        >>> train_model(["ls -la", "git status"], epochs=5)
        PosixPath('/home/user/.local/share/daedelus/model.bin')
    """
    ...
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=daedelus --cov-report=html

# Run specific test file
pytest tests/test_embeddings.py -v

# Run specific test
pytest tests/test_embeddings.py::test_train_model -v

# Run tests matching pattern
pytest tests/ -k "embedding" -v
```

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_core/           # Core component tests
│   ├── test_database.py
│   ├── test_embeddings.py
│   ├── test_suggestions.py
│   └── test_vector_store.py
├── test_daemon/         # Daemon tests
│   ├── test_daemon.py
│   └── test_ipc.py
├── test_llm/            # LLM tests (Phase 2)
│   ├── test_llm_manager.py
│   ├── test_rag_pipeline.py
│   └── test_peft_trainer.py
└── test_integration/    # Integration tests
    └── test_full_pipeline.py
```

### Writing Tests

Use **pytest** with fixtures:

```python
import pytest
from daedelus.core.database import Database

@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database for testing."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db
    db.close()

def test_log_command(temp_db):
    """Test command logging."""
    temp_db.log_command("ls -la", cwd="/home/user", exit_code=0)
    commands = temp_db.get_recent_commands(n=1)
    assert len(commands) == 1
    assert commands[0]["command"] == "ls -la"
```

### Test Coverage

- **Target**: >80% coverage
- **Required**: All new code must have tests
- **Focus**: Critical paths, edge cases, error handling

```bash
# View coverage report
pytest --cov=daedelus --cov-report=html
# Open htmlcov/index.html in browser
```

---

## Documentation

### What to Document

1. **Code Documentation**:
   - All public functions, classes, methods
   - Complex algorithms (inline comments)
   - Non-obvious decisions (why, not what)

2. **User Documentation**:
   - README.md - Project overview
   - QUICKSTART.md - Getting started
   - docs/ - Detailed guides

3. **Developer Documentation**:
   - CONTRIBUTING.md - This file
   - .devdocs/ - Architectural decisions, session notes
   - API.md - API reference (when created)

### Documentation Style

- **Clear and concise** - No jargon unless necessary
- **Examples** - Show, don't just tell
- **Up-to-date** - Keep in sync with code changes
- **Searchable** - Use good headings and keywords

### Updating Documentation

When changing code:
- Update relevant docstrings
- Update user-facing documentation
- Update CHANGELOG.md
- Add examples if helpful

---

## Pull Request Process

### Before Submitting

- [ ] Code follows style guide
- [ ] All tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (under `[Unreleased]`)
- [ ] Pre-commit hooks pass
- [ ] No unnecessary files (build artifacts, IDE files, etc.)

### PR Title Format

Use conventional commits style:

```
feat: Add natural language command generation
fix: Resolve daemon crash on shutdown
docs: Update Phase 2 documentation
test: Add integration tests for RAG pipeline
refactor: Simplify vector store API
perf: Optimize embedding generation
chore: Update dependencies
```

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Related Issue
Fixes #123
Closes #456

## Changes Made
- Added feature X
- Fixed bug Y
- Updated documentation for Z

## Testing Done
- [ ] Unit tests added/updated
- [ ] Manual testing performed
- [ ] Integration tests pass
- [ ] Performance impact assessed

## Screenshots (if applicable)
[Add screenshots for UI changes]

## Checklist
- [ ] Code follows project style guide
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Pre-commit hooks pass
```

### Review Process

1. **Automated checks** run (CI/CD pipeline)
2. **Maintainer reviews** code
3. **Discussion** if changes needed
4. **Approval** and merge

**Be patient** - Reviews may take a few days.

---

## Project Architecture

### Overview

Daedalus uses a **hybrid architecture**:
- **Phase 1**: Fast embedding-based suggestions (<30ms)
- **Phase 2**: LLM enhancement for natural language (50-200ms)

### Directory Structure

```
daedelus/
├── .devdocs/                # Session documentation
├── .github/workflows/       # CI/CD pipelines
├── contrib/                 # Community contributions
│   └── systemd/             # Systemd service files
├── shell_clients/           # Shell integration scripts
│   ├── bash/
│   ├── fish/
│   └── zsh/
├── src/daedelus/            # Main source code
│   ├── cli/                 # CLI interface
│   │   └── main.py
│   ├── core/                # Core components (Phase 1)
│   │   ├── database.py      # SQLite + FTS5
│   │   ├── embeddings.py    # FastText embeddings
│   │   ├── vector_store.py  # Annoy vector search
│   │   ├── suggestions.py   # 3-tier suggestion engine
│   │   ├── safety.py        # Command safety analysis
│   │   └── templates.py     # Command templates
│   ├── daemon/              # Daemon architecture
│   │   ├── daemon.py        # Main daemon
│   │   └── ipc.py           # Unix socket IPC
│   ├── llm/                 # LLM components (Phase 2)
│   │   ├── llm_manager.py   # llama.cpp integration
│   │   ├── rag_pipeline.py  # RAG context injection
│   │   ├── command_explainer.py
│   │   ├── command_generator.py
│   │   ├── enhanced_suggestions.py
│   │   ├── peft_trainer.py  # LoRA fine-tuning
│   │   └── model_manager.py # Model versioning
│   ├── ui/                  # User interfaces
│   │   └── dashboard.py     # TUI dashboard
│   └── utils/               # Utilities
│       ├── config.py
│       ├── logging_config.py
│       ├── dependencies.py
│       └── backup.py
├── tests/                   # Test suite (179+ tests)
├── docs/                    # Documentation (to be created)
├── pyproject.toml           # Project configuration
├── requirements.txt         # Phase 1 dependencies
├── requirements-llm.txt     # Phase 2 dependencies
└── requirements-dev.txt     # Development dependencies
```

### Key Architectural Decisions

See `.devdocs/DECISIONS_LOG.md` for 25 architectural decision records (ADRs).

**Most Important**:
1. **Privacy-first** - 100% local processing, no external APIs
2. **FOSS compliance** - Only permissive licenses (MIT/Apache/BSD)
3. **Hybrid approach** - Fast Phase 1 + powerful Phase 2
4. **Type safety** - Comprehensive type hints throughout
5. **Daemon architecture** - Persistent background process

### Phase 1 Components

**Database** (`core/database.py`):
- SQLite with FTS5 for full-text search
- Stores command history, sessions, statistics
- ~5ms query time

**Embeddings** (`core/embeddings.py`):
- FastText subword-aware embeddings
- 128-dimensional vectors
- Handles typos and rare commands
- ~1ms encoding time

**Vector Store** (`core/vector_store.py`):
- Annoy for approximate nearest neighbor search
- Angular distance metric
- <10ms queries for 1M vectors
- Memory-mapped indexes

**Suggestion Engine** (`core/suggestions.py`):
- 3-tier cascade: exact → semantic → contextual
- Multi-factor ranking (recency, directory, success, frequency)
- Confidence scoring

### Phase 2 Components

**LLM Manager** (`llm/llm_manager.py`):
- llama.cpp integration
- Phi-3-mini model (Q4 quantized, ~2.4GB)
- 50-200ms inference on CPU

**RAG Pipeline** (`llm/rag_pipeline.py`):
- Context retrieval from command history
- Vector + database queries
- Prompt formatting

**PEFT Trainer** (`llm/peft_trainer.py`):
- LoRA fine-tuning (r=8, alpha=32)
- Real gradient descent (HuggingFace Trainer)
- Trains on daemon shutdown
- Export to GGUF for llama.cpp

**Model Manager** (`llm/model_manager.py`):
- Model versioning (v1 → v2 → v3 → vN)
- Adapter merging
- Lineage tracking
- Rollback capability

---

## Adding New Features

### Phase 1 Feature (Embeddings/DB)

1. **Design** - How does it fit into existing architecture?
2. **Implement** in appropriate module (`core/`, `utils/`)
3. **Add tests** in `tests/test_core/`
4. **Update CLI** if needed (`cli/main.py`)
5. **Document** in docstrings and user docs

**Example**: Adding command templates support
- Implemented in `core/templates.py`
- Uses existing database
- Integrated into suggestion engine
- Tested in `tests/test_core/test_templates.py`

### Phase 2 Feature (LLM)

1. **Check LLM availability** - Optional dependency
2. **Implement** in `llm/` module
3. **Integrate with RAG** if context-aware
4. **Add graceful fallback** to Phase 1
5. **Test with/without LLM** dependencies

**Example**: Command explainer
- Implemented in `llm/command_explainer.py`
- Uses RAG for context
- Falls back to basic explanation
- CLI command: `daedelus explain`

### Cross-Phase Feature

1. **Phase 1 implementation** - Fast, always available
2. **Phase 2 enhancement** - LLM-powered, optional
3. **Routing logic** - When to use Phase 2
4. **Fallback** - Phase 1 if Phase 2 fails

**Example**: Enhanced suggestions
- Phase 1: Embedding-based (always works)
- Phase 2: NL query detection + LLM generation
- Routing: Detect if natural language
- Fallback: Always return Phase 1 results

---

## Release Process

(For maintainers)

### Version Numbers

We follow **Semantic Versioning** (SemVer):
- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.2.0): New features, backwards-compatible
- **PATCH** (0.2.1): Bug fixes only

### Release Checklist

1. [ ] All tests pass on all supported platforms
2. [ ] CHANGELOG.md updated with release notes
3. [ ] Version bumped in `pyproject.toml`
4. [ ] Version bumped in `src/daedelus/__init__.py`
5. [ ] Documentation updated
6. [ ] Tag created: `git tag v0.2.0`
7. [ ] Pushed to GitHub: `git push --tags`
8. [ ] GitHub Actions builds and publishes to PyPI
9. [ ] GitHub Release created with notes
10. [ ] Announcement posted

---

## Getting Help

### Questions?

- **GitHub Discussions** - General questions, ideas
- **GitHub Issues** - Bugs, feature requests
- **Email** - orpheus497 (for security issues)

### Resources

- **Documentation**: See `docs/` and `.devdocs/`
- **Architecture**: `.devdocs/DECISIONS_LOG.md`
- **Code examples**: `tests/` directory
- **Session notes**: `.devdocs/SESSION_HANDOFF.md`

---

## Attribution

Contributors will be acknowledged in:
- **CHANGELOG.md** - Per-release contributions
- **README.md** - Contributors section
- **Git history** - Your commits!

---

## Questions?

Open an issue or discussion on GitHub!

---

**Thank you for contributing to Daedalus!**

**Created by [orpheus497](https://github.com/orpheus497)**
