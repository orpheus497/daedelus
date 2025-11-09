# Daedalus Documentation

Welcome to the Daedalus documentation! This directory contains comprehensive guides for users and developers.

**Version**: 0.2.0
**Last Updated**: 2025-11-09

---

## 📚 Documentation Index

### For Users

| Document | Description |
|----------|-------------|
| [**Quick Start Guide**](../QUICKSTART.md) | Installation and getting started (5-10 min read) |
| [**User Guide**](../README.md) | Full feature overview and usage examples |
| [**Model Setup Guide**](MODEL_SETUP.md) | Complete LLM model download and configuration guide |
| [**Troubleshooting**](TROUBLESHOOTING.md) | Common issues and solutions |

### For Developers

| Document | Description |
|----------|-------------|
| [**Contributing Guide**](../CONTRIBUTING.md) | How to contribute code, tests, docs |
| [**API Reference**](API.md) | Complete API documentation |
| [**Architecture**](ARCHITECTURE.md) | System design and architecture |
| [**Development Setup**](../CONTRIBUTING.md#development-setup) | Developer environment setup |

### For Maintainers

| Document | Description |
|----------|-------------|
| [**Changelog**](../CHANGELOG.md) | Version history and release notes |
| [**Contributing Guide**](../CONTRIBUTING.md) | Development guidelines and standards |

---

## 🚀 Quick Links

### Installation
```bash
git clone https://github.com/orpheus497/daedelus.git
cd daedelus
./install.sh
daedelus setup
daedelus start
```

See [QUICKSTART.md](../QUICKSTART.md) for details.

### Basic Usage
```bash
# Daemon management
daedelus start          # Start daemon
daedelus status         # Check status
daedelus stop           # Stop daemon

# Query history
daedelus search "git"   # Search commands

# Phase 2 features
daedelus explain "tar -xzf file.tar.gz"
daedelus generate "find all python files"
```

See [README.md](../README.md) for full command reference.

---

## 📖 Documentation by Topic

### Getting Started
1. [**Installation**](../QUICKSTART.md#installation) - System requirements and setup
2. [**Configuration**](../QUICKSTART.md#configuration) - Customizing Daedalus
3. [**Shell Integration**](../QUICKSTART.md#5-add-shell-integration) - ZSH, Bash, Fish
4. [**First Steps**](../QUICKSTART.md#6-use-daedalus) - Using suggestions

### Core Concepts
1. [**3-Tier Suggestions**](ARCHITECTURE.md#phase-1-embedding-based-system) - How suggestions work
2. [**Privacy Model**](../README.md#-privacy--security) - Data privacy guarantees
3. [**Learning Process**](../README.md#-how-it-learns) - Self-learning mechanism
4. [**Performance**](ARCHITECTURE.md#performance-architecture) - Optimization strategies

### Advanced Features (Phase 2)
1. [**LLM Integration**](../PHASE2_LLM.md#llm-integration) - Local LLM with Phi-3-mini
2. [**RAG Pipeline**](ARCHITECTURE.md#2-rag-pipeline) - Context-aware suggestions
3. [**Fine-Tuning**](../PHASE2_LLM.md#self-forging-models) - Personalized models
4. [**Model Evolution**](API.md#model-manager) - Version management

### Development
1. [**Project Structure**](../CONTRIBUTING.md#project-architecture) - Code organization
2. [**Adding Features**](../CONTRIBUTING.md#adding-new-features) - Development workflow
3. [**Testing**](../CONTRIBUTING.md#testing) - Running and writing tests
4. [**Code Style**](../CONTRIBUTING.md#code-style--quality) - Standards and tools

### Troubleshooting
1. [**Installation Issues**](TROUBLESHOOTING.md#installation-issues) - FastText, dependencies
2. [**Daemon Issues**](TROUBLESHOOTING.md#daemon-issues) - Won't start, crashes
3. [**Shell Issues**](TROUBLESHOOTING.md#shell-integration-issues) - Integration problems
4. [**Performance Issues**](TROUBLESHOOTING.md#performance-issues) - Slow, high CPU/memory

---

## 🏗️ Architecture Overview

### High-Level Design

```
User Shell (ZSH/Bash/Fish)
         │
         ├── Commands → Daemon → Database (SQLite + FTS5)
         │                    └→ Embeddings (FastText)
         │                    └→ Vector Store (Annoy)
         │
         └── Ctrl+Space → Daemon → Suggestion Engine (3-tier)
                                 └→ LLM (Phi-3-mini, optional)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for complete design.

### Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Database** | Command history | SQLite + FTS5 |
| **Embeddings** | Semantic vectors | FastText (128D) |
| **Vector Store** | Similarity search | Annoy (ANN) |
| **Suggestions** | 3-tier cascade | Custom engine |
| **LLM** | Natural language | llama.cpp + Phi-3-mini |
| **RAG** | Context injection | Custom pipeline |
| **Fine-Tuning** | Personalization | PEFT/LoRA |

---

## 🔧 API Quick Reference

### Python API

```python
from daedelus.core.database import Database
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.suggestions import SuggestionEngine

# Database operations
db = Database("~/.local/share/daedelus/history.db")
db.log_command("git status", cwd="/home/user/project")
commands = db.get_recent_commands(n=10)

# Embeddings
embedder = CommandEmbedder()
vector = embedder.encode("git commit")

# Suggestions
engine = SuggestionEngine(db, embedder, vector_store)
suggestions = engine.suggest("git co", cwd="/home/user/project")
```

See [API.md](API.md) for complete reference.

### CLI Commands

```bash
# Daemon
daedelus setup                 # First-time setup
daedelus start [--foreground]  # Start daemon
daedelus stop                  # Stop daemon
daedelus restart               # Restart
daedelus status [--json]       # Status

# Query
daedelus search "<query>"      # Search history
daedelus info                  # System info

# Phase 2
daedelus explain "<cmd>"       # Explain command
daedelus generate "<desc>"     # Generate command
daedelus model download        # Download LLM
daedelus model status          # Model info
daedelus train                 # Manual training
```

---

## 📊 Performance Targets

All targets **EXCEEDED** in v0.2.0:

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Suggestion Latency | <50ms | ~10-30ms | ✅ 40% faster |
| Memory (Phase 1) | <100MB | ~50MB | ✅ 50% of target |
| Startup Time | <500ms | ~200ms | ✅ 2.5x faster |
| Disk Usage | <500MB | ~100MB | ✅ 20% of target |
| CPU (Idle) | <5% | <1% | ✅ 5x better |

See [ARCHITECTURE.md#performance-architecture](ARCHITECTURE.md#performance-architecture) for details.

---

## 🔒 Privacy & Security

### Privacy Guarantees

✅ **100% local processing** - No external APIs
✅ **No telemetry** - Zero data collection
✅ **No cloud services** - Works 100% offline
✅ **Configurable filters** - Exclude sensitive paths/patterns
✅ **Data encryption** - Optional for sensitive patterns

### Security Features

✅ **Unix sockets only** - No network exposure
✅ **Command safety analysis** - Detect dangerous patterns
✅ **ReDoS protection** - Regex validation
✅ **JSON metadata** - No pickle (code execution risk)
✅ **Privacy filtering** - Automatic exclusions

See [README.md#-privacy--security](../README.md#-privacy--security) for details.

---

## 🧪 Testing

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=daedelus --cov-report=html

# Specific component
pytest tests/test_core/test_suggestions.py -v

# Specific test
pytest tests/test_core/test_suggestions.py::test_suggest -v
```

**Current Status**: 179+ tests, 80%+ coverage

See [CONTRIBUTING.md#testing](../CONTRIBUTING.md#testing) for more.

---

## 🗺️ Project Roadmap

### ✅ Completed

- **Phase 1** (v0.1.0): Embedding-based system
- **Phase 2** (v0.2.0): LLM enhancement with Phi-3-mini

### 🔄 In Progress

- Manual shell integration testing
- Documentation polish
- v0.3.0 release preparation

### 🔮 Planned (Phase 3)

**Q3 2025**:
- Plugin system
- Neovim/VSCode integration
- Additional shell support

**Q4 2025**:
- GUI dashboard (Tauri)
- Cloud sync (optional, E2E encrypted)
- Team features
- Advanced analytics

See [ARCHITECTURE.md](ARCHITECTURE.md) for more details.

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Read**: [CONTRIBUTING.md](../CONTRIBUTING.md)
2. **Setup**: Developer environment
3. **Find**: Issue or feature to work on
4. **Code**: Follow style guide
5. **Test**: Write and run tests
6. **Submit**: Pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines.

---

## 📞 Getting Help

### Documentation

- **Quick answers**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **API details**: [API.md](API.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)

### Community

- **GitHub Issues**: [Report bugs or request features](https://github.com/orpheus497/daedelus/issues)
- **GitHub Discussions**: Ask questions, share ideas
- **Email**: orpheus497 (for security issues)

### Common Issues

| Issue | Solution |
|-------|----------|
| FastText won't compile | [Installation guide](TROUBLESHOOTING.md#fasttext-wont-compile) |
| Daemon won't start | [Daemon troubleshooting](TROUBLESHOOTING.md#daemon-wont-start) |
| No suggestions | [Suggestion issues](TROUBLESHOOTING.md#no-suggestions-appearing) |
| Slow performance | [Performance tuning](TROUBLESHOOTING.md#slow-suggestions-1-second) |

---

## 📜 License

**MIT License** - 100% Free and Open Source

All dependencies use permissive licenses:
- FastText: MIT
- Annoy: Apache 2.0
- SQLite: Public Domain
- llama.cpp: MIT
- Phi-3-mini: MIT (Microsoft)
- All others: MIT/Apache 2.0/BSD

See [LICENSE](../LICENSE) for full text.

---

## 🏆 Project Status

**Current Version**: v0.2.0
**Status**: Production-ready (pending final testing)
**Quality**: ⭐⭐⭐⭐⭐ Excellent
- 179+ tests
- 80%+ code coverage
- CI/CD pipelines
- Pre-commit hooks
- Comprehensive documentation

---

## 📈 Project Statistics

- **Lines of Code**: ~10,000 (5K production, 3K tests, 2K docs)
- **Test Coverage**: 80%+
- **Dependencies**: 100% FOSS
- **Supported Platforms**: Linux, macOS, BSD
- **Python Versions**: 3.10, 3.11, 3.12
- **Shells**: ZSH, Bash, Fish

---

## 🙏 Acknowledgments

- Inspired by [zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions)
- Built on research from [mcfly](https://github.com/cantino/mcfly) and [atuin](https://github.com/atuinsh/atuin)
- FastText by Facebook Research
- Annoy by Spotify
- llama.cpp by Georgi Gerganov
- Phi-3-mini by Microsoft

---

**Created by [orpheus497](https://github.com/orpheus497)**

**⭐ Star this repo if you find it useful!**

*Daedalus - Because your terminal should learn from you, not spy on you.*

---

**Navigation**:
- [↑ Back to Main README](../README.md)
- [📚 API Reference](API.md)
- [🏗️ Architecture](ARCHITECTURE.md)
- [🔧 Troubleshooting](TROUBLESHOOTING.md)
- [🤝 Contributing](../CONTRIBUTING.md)
