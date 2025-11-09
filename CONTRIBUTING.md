# Contributing to Daedalus

First off, thank you for considering contributing to Daedalus! 🎉

## Code of Conduct

Be respectful, collaborative, and constructive. We're all here to build something great.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce**
- **Expected vs actual behavior**
- **System information** (OS, Python version, shell)
- **Logs** from `~/.local/share/daedelus/daemon.log`

### Suggesting Features

Feature suggestions are welcome! Please:

- **Check existing feature requests** to avoid duplicates
- **Provide clear use cases** and examples
- **Consider Phase 1 vs Phase 2** scope

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Follow the code style** (Black + Ruff)
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Ensure tests pass**: `pytest tests/ -v`
6. **Submit the PR** with a clear description

## Development Setup

```bash
# Clone repository
git clone https://github.com/orpheus497/daedelus.git
cd daedelus

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode
pip install -e .[dev]

# Run tests
pytest tests/ -v --cov=daedelus
```

## Code Style

We use:

- **Black** for formatting: `black src/daedelus tests/`
- **Ruff** for linting: `ruff check src/daedelus tests/`
- **mypy** for type checking: `mypy src/daedelus`
- **Type hints** are required for all functions
- **Docstrings** (Google style) for all public APIs

## Testing

- Write tests for all new features
- Aim for >80% code coverage
- Use `pytest` fixtures from `tests/conftest.py`
- Run tests before submitting: `pytest tests/ -v`

## Commit Messages

- Use present tense ("Add feature" not "Added feature")
- Be descriptive but concise
- Reference issues when applicable: "Fix #123"

## Project Structure

```
daedelus/
├── src/daedelus/        # Core source code
├── shell_clients/       # Shell integration scripts
├── tests/               # Test suite
├── docs/                # Documentation
└── scripts/             # Utility scripts
```

## Attribution

Contributors will be acknowledged in:
- CHANGELOG.md
- README.md (Contributors section)

## Questions?

Open an issue or discussion on GitHub!

---

**Created by orpheus497**
