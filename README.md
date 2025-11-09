# Daedalus

<div align="center">

**Self-Learning Terminal Assistant with Adaptive AI Micro-Model**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

*Created by [orpheus497](https://github.com/orpheus497)*

</div>

---

## 🎯 What is Daedalus?

Daedalus is a **persistent, self-learning terminal assistant** that builds its own AI model from scratch through your usage patterns. Unlike tools that rely on external APIs or pre-trained models, Daedalus creates intelligence locally, learns from YOUR workflow, and keeps everything 100% private.

### Core Innovation

```
Traditional Tools          Daedalus
================          =========
Cloud API calls    →      100% local processing
Pre-trained models →      Self-training from scratch
Generic suggestions →     Personalized to YOUR workflow
Privacy concerns   →      Data never leaves your machine
Requires internet  →      Works 100% offline
```

## ✨ Features

- 🧠 **Self-Teaching AI** - Builds its own neural network from your command history
- ⚡ **Ultra-Lightweight** - <100MB RAM, <500MB disk, <50ms suggestions
- 🔒 **Privacy-First** - Everything stays on your machine. No telemetry. Ever.
- 🚀 **Real-Time Suggestions** - Intelligent command completion as you type
- 🎯 **Context-Aware** - Understands your current directory, recent commands, and patterns
- 🔄 **Continuous Learning** - Automatically improves from every session
- 🌐 **Cross-Platform** - Linux, macOS, BSD (Windows via WSL)
- 🎨 **Shell Integration** - ZSH, Bash, Fish support

## 🏗️ Architecture

Daedalus uses a **hybrid architecture** with two phases:

### Phase 1: Embedding-Based System ✅
```
FastText Embeddings → Annoy Vector Search → Pattern Learning
├── Command similarity matching
├── Context-aware suggestions
└── Incremental model updates
```

### Phase 2: LLM Enhancement ✅ (Current)
```
Phase 1 + llama.cpp (TinyLlama) → RAG Pipeline → PEFT/LoRA Fine-Tuning
├── Natural language command explanations
├── Command generation from descriptions
├── Q&A about shell commands
└── Personalized model fine-tuning
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/orpheus497/daedelus.git
cd daedelus

# Quick install (recommended)
chmod +x install.sh
./install.sh

# Or manual install
pip install -e .
```

**Requirements**: Python 3.10+, C++ compiler (g++)

### Setup

```bash
# Initialize Daedalus
daedelus setup

# Start the daemon
daedelus start

# Check status
daedelus status
```

### Shell Integration

Add to your shell RC file:

**ZSH** (`~/.zshrc`):
```bash
source $(daedelus shell-integration zsh)
```

**Bash** (`~/.bashrc`):
```bash
source $(daedelus shell-integration bash)
```

**Fish** (`~/.config/fish/config.fish`):
```fish
source (daedelus shell-integration fish)
```

## 📖 Usage

### Basic Commands

```bash
# Daemon management
daedelus start          # Start daemon in background
daedelus stop           # Stop daemon
daedelus restart        # Restart daemon
daedelus status         # Show status and statistics

# Query history
daedelus search "git"   # Search command history
daedelus info           # Show system information

# LLM Features (Phase 2)
daedelus explain "ls -la"              # Explain what a command does
daedelus generate "find all python files"  # Generate command from description
daedelus ask "how do I compress a directory"  # Ask questions about shell commands
daedelus websearch "latest python best practices"  # Search web with AI summary
```

### Shell Usage

Once integrated, Daedalus works automatically:

1. **Type commands normally** - Daedalus learns silently in the background
2. **Press `Ctrl+Space`** (or Tab) - Get intelligent suggestions
3. **Keep working** - Daedalus gets smarter with every command

### Example Session

```bash
$ cd myproject/
$ git st<Ctrl+Space>
  → git status
  → git stash
  → git stash list

$ git commit -m<Ctrl+Space>
  → git commit -m "Update README"        # Learns from your commit messages
  → git commit -m "Fix bug in parser"
  → git commit -m "Add new feature"
```

## 🧠 How It Learns

### Data Collection
- ✅ Command strings
- ✅ Working directory
- ✅ Exit codes (success/failure)
- ✅ Execution time
- ✅ Command sequences

### Learning Process

1. **Real-Time Logging** - Every command is logged to SQLite database
2. **Pattern Recognition** - Identifies frequently used commands and sequences
3. **Embedding Generation** - Creates semantic vectors using FastText
4. **Index Building** - Stores embeddings in Annoy index for fast search
5. **On-Shutdown Learning** - Updates models when daemon stops

### Suggestion Algorithm (3-Tier Cascade)

```
Tier 1: Exact Prefix Match
  ↓ (if insufficient)
Tier 2: Semantic Similarity (embeddings)
  ↓ (if insufficient)
Tier 3: Contextual Patterns (sequences)
```

## 🔒 Privacy & Security

### What Daedalus DOES

✅ Store commands locally in SQLite
✅ Build local AI models from your usage
✅ Encrypt sensitive data patterns
✅ Respect `.gitignore`-style exclusions
✅ Allow easy data export and deletion

### What Daedalus DOESN'T DO

❌ **NO** external API calls
❌ **NO** cloud services
❌ **NO** telemetry or analytics
❌ **NO** data sharing
❌ **NO** internet requirements after initial setup

### Privacy Controls

Configure in `~/.config/daedelus/config.yaml`:

```yaml
privacy:
  excluded_paths:
    - ~/.ssh
    - ~/.gnupg
    - ~/.password-store

  excluded_patterns:
    - password
    - token
    - secret
    - api[_-]?key

  history_retention_days: 90
  encrypt_sensitive: true
```

## ⚙️ Configuration

Full configuration at `~/.config/daedelus/config.yaml`:

```yaml
# Daemon settings
daemon:
  socket_path: ~/.local/share/daedelus/runtime/daemon.sock
  log_path: ~/.local/share/daedelus/daemon.log

# Phase 1 Model settings (Embeddings)
model:
  embedding_dim: 128
  vocab_size: 50000
  min_count: 2

# Phase 2 LLM settings
llm:
  enabled: true
  model_path: ~/.local/share/models/model.gguf  # Place your GGUF model here
  context_length: 2048
  temperature: 0.7

# Suggestion settings
suggestions:
  max_suggestions: 5
  min_confidence: 0.3
  context_window: 10

# Privacy settings
privacy:
  excluded_paths: [~/.ssh, ~/.gnupg]
  history_retention_days: 90
```

### LLM Model Setup

Daedalus uses GGUF-format models for LLM features. You can use any GGUF model compatible with llama.cpp.

#### Option 1: Download TinyLlama (Recommended)

TinyLlama is recommended for most users (small, fast, 100% FOSS with Apache 2.0 license):

```bash
# Create models directory
mkdir -p ~/.local/share/models

# Download TinyLlama 1.1B Chat Q4 quantized model (~669MB)
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf

# Move to Daedalus models directory (note: no need to rename - auto-detected)
mv tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf ~/.local/share/models/

# Restart Daedalus to load the model
daedelus restart
```

#### Option 2: Use a Different Model

You can use any GGUF model from Hugging Face or other sources:

**Popular Options:**
- **Llama-3.2-1B** - Very fast, lightweight (~1GB)
- **Mistral-7B** - More capable, larger (~4GB)
- **Qwen2.5** - Strong multilingual support (~3GB)
- **TinyLlama-1.1B** - Ultra-lightweight (~600MB)

**Download Steps:**

```bash
# Example: Download TinyLlama (very small and fast)
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf

# Place it in the models directory with the expected name
mv tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf ~/.local/share/models/model.gguf
```

#### Changing Model Settings

You can configure which model to use by editing the config file:

```bash
# Open config file
nano ~/.config/daedelus/config.yaml
```

**Change the model path:**
```yaml
llm:
  enabled: true
  model_path: ~/.local/share/models/model.gguf  # Change this path
  context_length: 2048   # Increase for longer context (uses more RAM)
  temperature: 0.7       # 0.0 = deterministic, 1.0 = creative
```

**Alternative: Use a specific model file without renaming:**
```yaml
llm:
  enabled: true
  model_path: ~/.local/share/models/my-custom-model.gguf
  context_length: 4096
  temperature: 0.5
```

**Or set via CLI:**
```bash
daedelus config set llm.model_path ~/.local/share/models/my-model.gguf
daedelus config set llm.temperature 0.8
daedelus config set llm.context_length 4096

# Restart to apply changes
daedelus restart
```

#### Model Selection Guide

Choose based on your hardware and needs:

| Model | Size | RAM | Speed | Use Case |
|-------|------|-----|-------|----------|
| TinyLlama-1.1B | ~669MB | 2GB | ⚡⚡⚡ | **Recommended** - 100% FOSS, fast |
| Phi-3-mini | ~2.4GB | 4GB | ⚡⚡ | More capable, larger |
| Qwen2.5-3B | ~3GB | 6GB | ⚡ | Multilingual support |
| Mistral-7B | ~4GB | 8GB | ⚡ | More capable, slower |

#### Troubleshooting

**Model not found error:**
```bash
# Check what Daedalus is looking for
daedelus info

# Verify file exists
ls -lh ~/.local/share/models/

# Check config
daedelus config get llm.model_path
```

**Out of memory error:**
- Use a smaller quantization (Q4 instead of Q8)
- Use a smaller model (TinyLlama instead of Mistral)
- Reduce context_length in config

**Model loads slowly:**
- This is normal on first load
- Subsequent loads use RAM cache
- Consider using a smaller model

---

**📖 For complete model setup documentation, see [docs/MODEL_SETUP.md](docs/MODEL_SETUP.md)**

This comprehensive guide covers:
- All available models and comparisons
- Step-by-step download instructions
- Advanced configuration options
- Performance tuning
- Troubleshooting

## 📊 Performance

| Metric | Target | Achieved |
|--------|--------|----------|
| RAM Usage (Idle) | <100MB | ✅ ~50MB |
| Suggestion Latency | <50ms | ✅ ~10-30ms |
| Startup Time | <500ms | ✅ ~200ms |
| Disk Space | <500MB | ✅ ~100MB |
| CPU (Idle) | <5% | ✅ <1% |

## 🛠️ Development

### Tech Stack

**Phase 1 (Current):**
- **Language**: Python 3.10+ with type hints
- **Embeddings**: FastText (MIT)
- **Vector Search**: Annoy (Apache 2.0)
- **Database**: SQLite with FTS5
- **Terminal**: ptyprocess, prompt-toolkit
- **CLI**: Click

**Phase 2 (Current):**
- **LLM**: llama.cpp + TinyLlama (GGUF, 100% FOSS)
- **Vector DB**: sqlite-vss
- **Fine-Tuning**: PEFT/LoRA
- **Framework**: transformers, accelerate
- **All LLM dependencies included by default**

### Project Structure

```
daedelus/
├── src/daedelus/
│   ├── core/
│   │   ├── database.py        # SQLite + FTS5 command history
│   │   ├── embeddings.py      # FastText command embeddings
│   │   ├── vector_store.py    # Annoy similarity search
│   │   └── suggestions.py     # 3-tier suggestion engine
│   ├── daemon/
│   │   ├── daemon.py          # Main daemon orchestrator
│   │   └── ipc.py             # Unix socket IPC protocol
│   ├── cli/
│   │   └── main.py            # CLI interface (Click)
│   └── utils/
│       ├── config.py          # Configuration management
│       └── logging_config.py  # Colored logging
├── shell_clients/
│   ├── zsh/                   # ZSH plugin
│   ├── bash/                  # Bash integration
│   └── fish/                  # Fish integration
├── tests/                     # Pytest test suite
└── docs/                      # Documentation

```

### Running Tests

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest tests/ -v --cov=daedelus

# Type checking
mypy src/daedelus

# Linting
ruff check src/daedelus

# Formatting
black src/daedelus

# Security scanning
bandit -r src/daedelus
```

## 🗺️ Roadmap

### ✅ Phase 1: Embedding-Based System (COMPLETE)
- [x] Project structure and configuration
- [x] SQLite database with FTS5 search
- [x] FastText embedding model
- [x] Annoy vector similarity search
- [x] Daemon architecture with IPC
- [x] 3-tier suggestion engine
- [x] CLI interface
- [x] Shell integration (ZSH, Bash, Fish)

### ✅ Phase 2: LLM Enhancement (COMPLETE)
- [x] llama.cpp integration
- [x] TinyLlama model support (GGUF, 100% FOSS)
- [x] RAG pipeline for context injection
- [x] PEFT/LoRA fine-tuning infrastructure
- [x] Natural language command explanations (`daedelus explain`)
- [x] Command generation from descriptions (`daedelus generate`)
- [x] Q&A for shell commands (`daedelus ask`)
- [x] LLM dependencies included by default
- [x] Model path: `~/.local/share/models/`

### 🔮 Phase 3: Advanced Features (Q3-Q4 2025)
- [ ] Multi-language support
- [ ] Plugin system
- [ ] GUI dashboard
- [ ] Vim/Neovim integration
- [ ] Cloud sync (optional, encrypted)
- [ ] Team sharing features

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

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
pytest tests/

# Format code
black src/daedelus
ruff check --fix src/daedelus
```

## 🗑️ Uninstalling

To completely remove Daedalus:

```bash
# Run the uninstall script
./uninstall.sh
```

The script will:
1. Stop the daemon
2. Guide you through removing shell integration
3. Uninstall the Python package
4. Optionally remove configuration files
5. Optionally remove data (command history, models, etc.)
6. Optionally remove downloaded LLM models

You can choose what to keep and what to remove during the process.

**Manual Uninstall**:
```bash
# Stop daemon
daedelus stop

# Uninstall package
pip uninstall daedelus

# Remove data and config (optional)
rm -rf ~/.config/daedelus
rm -rf ~/.local/share/daedelus
rm -f ~/.local/share/models/model.gguf

# Remove shell integration from your RC files
```

## 📜 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) file for details.

All dependencies are FOSS (Free and Open Source Software) with permissive licenses:
- FastText: MIT
- Annoy: Apache 2.0
- SQLite: Public Domain
- Click: BSD-3-Clause
- All others: MIT/Apache 2.0/BSD

## 🙏 Acknowledgments

- Inspired by [zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions)
- Built on research from [mcfly](https://github.com/cantino/mcfly) and [atuin](https://github.com/atuinsh/atuin)
- FastText by Facebook Research
- Annoy by Spotify
- llama.cpp by Georgi Gerganov (Phase 2)

## 📧 Contact

Created by **orpheus497**

- GitHub: [@orpheus497](https://github.com/orpheus497)
- Issues: [GitHub Issues](https://github.com/orpheus497/daedelus/issues)

---

<div align="center">

**⭐ Star this repo if you find it useful!**

*Daedalus - Because your terminal should learn from you, not spy on you.*

</div>
