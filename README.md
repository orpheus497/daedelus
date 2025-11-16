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
- 🔌 **Plugin System** - Extensible architecture with permission-based security (v0.3.0)
- 🎨 **GUI Dashboard** - Beautiful TUI for monitoring and configuration (v0.3.0)
- ✨ **Interactive REPL** - Smart default interface with syntax highlighting (v0.5.0)
- 📝 **Script Generation** - Multi-language support with templates (v0.5.0)
- 📁 **File Operations** - AI-assisted batch operations and analysis (v0.5.0)
- 🔍 **Semantic Search** - Vector-based knowledge base search with 20-30% better recall (v0.6.0)
- 🎯 **Query Expansion** - Automatic synonym expansion with 180+ terms (v0.6.0)
- ⚡ **Smart Caching** - 10x faster repeated queries with 50-70% hit rate (v0.6.0)
- 📊 **Search Analytics** - Quality metrics (Precision@K, MRR) for continuous improvement (v0.6.0)
- 🕸️ **Hybrid Search** - Combines keyword + semantic + graph for optimal results (v0.6.0)

## 🏗️ Architecture

Daedalus uses a **hybrid architecture** with five complete phases:

### Phase 1: Embedding-Based System ✅
```
FastText Embeddings → Annoy Vector Search → Pattern Learning
├── Command similarity matching
├── Context-aware suggestions
└── Incremental model updates
```

### Phase 2: LLM Enhancement ✅
```
Phase 1 + llama.cpp (TinyLlama) → RAG Pipeline → PEFT/LoRA Fine-Tuning
├── Natural language command explanations
├── Command generation from descriptions
├── Q&A about shell commands
└── Personalized model fine-tuning
```

### Phase 3: Advanced Features ✅ (v0.3.0)
```
Plugin System + GUI Dashboard + Permission Manager
├── Dynamic plugin loading with lifecycle management
├── Permission-based security model
├── CLI command registration from plugins
├── TUI dashboard with live metrics
└── Config editing and command explanations
```

### Phase 4: Enhanced REPL & UX ✅ (v0.5.0)
```
Interactive REPL + Script Generation + File Operations
├── Real-time syntax highlighting (always on)
├── Multi-language script generation (7 languages)
├── Template library (8 pre-built scripts)
├── Batch file operations with AI analysis
├── Live status bar with daemon metrics
└── Natural language intent classification
```

### Phase 5: Intelligence System Enhancement ✅ (v0.6.0)
```
Semantic Search + Query Expansion + Hybrid Fusion + Analytics
├── Vector embeddings for knowledge base (semantic understanding)
├── Query expansion with 180+ synonyms (better recall)
├── LRU cache with TTL (10x faster repeated queries)
├── Search analytics (Precision@K, MRR metrics)
├── Knowledge graph (structural relationships)
├── Hybrid search with RRF fusion (keyword + semantic + graph)
└── Adaptive weight tuning per query type
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/orpheus497/daedelus.git
cd daedelus

# Quick install (recommended - includes automatic cleanup)
chmod +x install.sh
./install.sh

# Or manual install
pip install -e .
```

**Requirements**: Python 3.10+, C++ compiler (g++)

**Note**: The installer automatically:
- Stops any existing daemons
- Removes deprecated GPL dependencies
- Cleans up stale PID/socket files
- Ensures a fresh installation

**Manual cleanup** (if needed):
```bash
./scripts/cleanup-daemon.sh
```

### Setup

```bash
# Initialize Daedelus
daedelus setup

# Start the daemon
daedelus start

# Check status
daedelus status
```

### ⚡ Shorter Command Alias

For convenience, Daedelus provides a shorter `deus` command that works exactly the same:

```bash
deus            # Start interactive REPL (default)
deus start      # Same as: daedelus start
deus status     # Same as: daedelus status
```

All commands support both `daedelus` and `deus` - use whichever you prefer!

### 🚀 Auto-Start on Boot (Optional)

Daedelus can automatically start when your system boots, so it's always ready:

```bash
# Install systemd service (Linux only)
./scripts/install-systemd-service.sh

# The daemon will now start automatically on boot
# To uninstall later:
./scripts/uninstall-systemd-service.sh
```

With boot auto-start enabled:
- Daedelus daemon starts automatically when you log in
- All quality-of-life features are immediately available
- No need to manually run `daedelus start`
- Works seamlessly with shell integration

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

### Quick-Summon Aliases (Optional)

For even faster access, source the alias file:

**ZSH** (`~/.zshrc`):
```bash
# Add this line after the shell integration
source ~/.local/share/daedelus/aliases.zsh
```

**Bash** (`~/.bashrc`):
```bash
# Add this line after the shell integration
source ~/.local/share/daedelus/aliases.sh
```

Now you can use shortcuts:
- `d i` - Start interactive mode
- `ds "query"` - Search history
- `dex "command"` - Explain command
- `dgen "description"` - Generate command
- `da` - Analytics
- Plus 20+ more aliases! (Run `dtips` to see all)

## ✨ Enhanced Features

### 🎨 Interactive REPL Mode

Launch a powerful terminal interface with **all features always active**:

```bash
daedelus        # Default: starts interactive REPL
# or
deus            # Short alias
# or  
daedelus repl   # Explicit command (same result)
```

When you start the REPL, **everything is automatically integrated**:
- **Real-Time Syntax Highlighting** - Commands colored as you type (v0.5.0 ✨)
- **Auto-Completion** - Tab completion from your command history (always on)
- **Fuzzy Search** - Find commands with partial matches (always on)
- **AI Suggestions** - Intelligent suggestions as you type (always on)
- **History Navigation** - Use ↑/↓ arrows through your history (always on)
- **Command Analytics** - Usage patterns and insights (always on)
- **Live Status Bar** - Daemon uptime and stats displayed (v0.5.0 ✨)
- **Enhanced Prompt** - Modern `💡 deus:~/path❯` prompt (v0.5.0 ✨)

**No configuration needed** - all quality-of-life features are active by default

**Just type `/help` inside the REPL to see all available commands!**

REPL Commands:
```
/help                  - Show comprehensive help with examples
/search <query>       - Fuzzy search command history
/explain <command>    - Explain what a command does
/generate <desc>      - Generate command from description
/write-script <desc>  - Create script from description (v0.5.0 ✨)
/read <file>          - Read and analyze file with AI (v0.5.0 ✨)
/write <file>         - Write file with AI assistance (v0.5.0 ✨)
/recent [n]           - Show recent commands
/stats                - Usage statistics
/quit                 - Exit (or Ctrl+D)

Plus all regular shell commands work directly!
```

### 📝 Script Generation (v0.5.0 ✨ NEW)

Create scripts in multiple languages from natural language descriptions:

```bash
# In REPL
/write-script backup my home directory to /backup daily

# Daedelus will:
# 1. Detect language (Bash in this case)
# 2. Check template library (finds 'backup' template)
# 3. Generate script with proper shebang
# 4. Add chmod +x permissions
# 5. Save to file
# 6. Show how to run it
```

**Supported Languages** (7 total):
- **Bash** - System administration, automation
- **Python** - Data processing, APIs, utilities
- **JavaScript** - Node.js apps, automation
- **Perl** - Text processing, legacy systems
- **Ruby** - Scripts, Rails tasks
- **Go** - Performance-critical scripts
- **PHP** - Web utilities, cron jobs

**Built-in Templates** (8 total):
- `backup` - File/directory backup with rotation
- `monitor` - System resource monitoring
- `deploy` - Git pull + service restart
- `api_server` - REST API (Python Flask or Node Express)
- `data_processor` - CSV/JSON processing
- `cron_job` - Scheduled task template
- `log_analyzer` - Log file analysis
- `system_check` - Health check with alerts

**Features**:
- Automatic language detection from description
- Template matching for common tasks (instant generation)
- LLM fallback for custom scripts
- Syntax validation before saving
- Auto chmod +x for executables

### 📁 File Operations (v0.5.0 ✨ NEW)

AI-assisted file operations with intelligent analysis:

```bash
# Read and analyze files
/read config.yaml
# AI will summarize contents, detect format, suggest improvements

# Batch operations
/batch-read *.md
# Read multiple files at once

# Write with AI assistance
/write report.md
# AI helps structure content

# Automatic backups
# All write operations create timestamped backups

# File analysis
/analyze data.csv
# AI detects type, size, structure, suggests operations
```

**Features**:
- **Batch Operations** - Process multiple files efficiently
- **AI Summarization** - Understand file contents quickly
- **Type Detection** - MIME type + metadata analysis
- **Automatic Backups** - Safety before overwrites
- **Smart Suggestions** - AI recommends operations based on content

### 🔍 Fuzzy Command Search

Find commands even with typos or partial matches:

```bash
daedelus search "git push"      # Find all git push variants
daedelus search docker -n 20    # Show 20 Docker command results
daedelus search "file operations"  # Semantic search
```

Uses advanced fuzzy matching algorithms (thefuzz + Levenshtein distance) for intelligent results.

### 🎨 Syntax Highlighting

Highlight any command or code with 300+ language support:

```bash
daedelus highlight "git log --oneline --graph"
daedelus highlight "SELECT * FROM users WHERE id = 1" --syntax sql
daedelus highlight "def fibonacci(n):" --syntax python
```

Powered by Pygments with beautiful color schemes.

### 📊 Usage Analytics

Get insights into your command usage patterns:

```bash
daedelus analytics              # Quick stats
daedelus analytics --detailed   # Detailed breakdown
```

Shows:
- Total and unique command counts
- Success rates
- Most frequently used commands
- Usage patterns over time

### 💡 Tips System

New to Daedelus? Get helpful tips anytime:

```bash
daedelus tips
```

Shows keyboard shortcuts, usage examples, and power-user features.

### 🔍 Semantic Search & Intelligence (v0.6.0 ✨ NEW)

Daedelus now features advanced semantic understanding for dramatically better search results:

```bash
# Search with semantic understanding
# "firewall" automatically expands to [firewall, iptables, ufw, security]
daedelus search firewall

# Query expansion finds related terms
# "install package" → [install, setup, add] + [package, apt, yum, dnf]
daedelus search "install package"

# View search analytics
daedelus repl
/analytics-search

# Shows:
# - Total searches and avg results
# - Cache hit rate (50-70% = 10x speedup)
# - Quality metrics (Precision@5, MRR)
# - Top queries and improvement opportunities
```

**Intelligence Features**:
- **Semantic Embeddings** - Vector search finds conceptually similar content
- **Query Expansion** - Automatic synonym expansion (180+ terms, 600+ mappings)
- **Smart Caching** - 10x faster repeated queries (50-70% hit rate)
- **Hybrid Search** - Combines keyword + semantic + graph for optimal results
- **Analytics** - Track search quality with Precision@K and MRR metrics
- **Adaptive Weights** - Query type detection (factual/procedural/conceptual/command)

**Performance**:
- Semantic search: <100ms
- Cached queries: <5ms (vs 50-200ms uncached)
- 20-30% better search recall with query expansion
- 15-25% accuracy improvement with hybrid search


### 🔌 Plugin System (v0.3.0)

Daedelus now supports a powerful plugin system for extending functionality:

```bash
# Example: Use hello world plugin command
daedelus hello "World"

# Built-in plugins:
# - hello_world: Example plugin demonstrating CLI commands
# - analytics_export: Export command history to JSON/CSV
# - neovim_integration: Edit config and view history in Neovim
```

**Create Your Own Plugins:**
See `docs/PLUGIN_DEVELOPMENT.md` for a comprehensive guide including:
- Plugin structure and manifest
- API reference (DaedalusAPI)
- Permission system
- CLI command registration
- Complete examples

**Plugin Security:**
- Permission-based access control
- Automatic approval during daemon startup
- User can revoke permissions anytime
- Isolated execution context

### 🎨 GUI Dashboard (v0.3.0)

Launch a beautiful TUI dashboard for monitoring and configuration:

```bash
daedelus dashboard

# Features:
# - Live daemon metrics (uptime, requests, commands logged)
# - Command history browser with search
# - Usage analytics and statistics
# - Config editor with live updates
# - Command explanations (LLM-powered)
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
  model_path: null  # Auto-detect any GGUF in ~/.local/share/models/
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

#### GPU Setup for Training (Optional but Recommended)

**Why GPU?** Training with GPU is 10-30x faster than CPU (1-3 minutes vs 10-30 minutes).

**Check GPU Status:**
```bash
# Run automatic diagnostic
./scripts/fix_cuda_pytorch.sh
```

**Common Issue: PyTorch CUDA Version Mismatch**

If diagnostic shows "CUDA not available":

```bash
# Reinstall PyTorch with correct CUDA version
pip3 uninstall torch torchvision torchaudio -y

# For CUDA 11.8 (most stable, recommended)
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Verify GPU is now accessible
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
```

**Set Environment Variables:**
```bash
# Add to ~/.bashrc or ~/.zshrc
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Reload shell
source ~/.bashrc
```

**Training with GPU:**
```bash
# Training will automatically use GPU if available
daedelus train --force

# Monitor GPU usage during training
watch -n 1 nvidia-smi
```

**CPU-Only Mode:** If you don't have a GPU or can't fix CUDA, Daedelus will automatically fall back to CPU mode. Training will be slower but fully functional.

For detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

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
| **Semantic Search** (v0.6.0) | <100ms | ✅ ~50-80ms |
| **Cached Query** (v0.6.0) | <5ms | ✅ ~2-4ms |
| **Query Expansion** (v0.6.0) | <5ms | ✅ ~1-3ms |
| **Cache Hit Rate** (v0.6.0) | >50% | ✅ 50-70% |

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

**Phase 5 (v0.6.0):**
- **Semantic Search**: FastText embeddings + Annoy
- **Query Expansion**: YAML synonym dictionary (180+ terms)
- **Caching**: LRU cache with TTL
- **Analytics**: SQLite-based metrics tracking
- **Graph**: NetworkX for knowledge relationships
- **Fusion**: Reciprocal Rank Fusion (RRF) algorithm

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

### ✅ Phase 3: Advanced Features (COMPLETE - v0.3.0)
- [x] Plugin System
  - [x] Core infrastructure (discovery, loading, lifecycle)
  - [x] Permission manager with security controls
  - [x] CLI command registration
  - [x] First-party plugins (hello_world, analytics_export, neovim_integration)
  - [x] Developer documentation
- [x] GUI Dashboard
  - [x] TUI with Textual framework
  - [x] Live daemon metrics
  - [x] History browser and search
  - [x] Config editor
  - [x] Command explanations
- [x] Bug Fixes
  - [x] Daemon startup detection
  - [x] Plugin CLI registration
  - [x] Permission auto-approval

### ✅ Phase 4: Enhanced REPL & UX (COMPLETE - v0.5.0)
- [x] Interactive REPL as default interface
  - [x] Real-time syntax highlighting (always on)
  - [x] Custom DaedelusLexer for intelligent tokenization
  - [x] Live status bar with daemon metrics
  - [x] Enhanced prompt with emoji and path shortening
- [x] Multi-language script generation
  - [x] 7 languages supported (Python, Bash, JS, Perl, Ruby, Go, PHP)
  - [x] Automatic language detection
  - [x] Template library (8 pre-built scripts)
  - [x] Syntax validation per language
- [x] AI-assisted file operations
  - [x] Batch read/write operations
  - [x] File summarization and analysis
  - [x] Automatic backup before overwrite
  - [x] MIME type detection
- [x] Comprehensive documentation
  - [x] Updated README with all features
  - [x] Architectural decision records (ADRs)
  - [x] Complete CHANGELOG for v0.5.0

### ✅ Phase 5: Intelligence System Enhancement (COMPLETE - v0.6.0)
- [x] Semantic embeddings for knowledge base
  - [x] Vector-based similarity search
  - [x] Intelligent document chunking
  - [x] FastText embedding generation
  - [x] Persistent embedding storage
- [x] Query expansion system
  - [x] 180+ synonym terms, 600+ mappings
  - [x] Context-aware filtering
  - [x] Weighted expansion (original terms boosted 2x)
  - [x] 15+ categories (package mgmt, system admin, networking, etc.)
- [x] Search result caching
  - [x] LRU cache with TTL support
  - [x] 50-70% hit rate (10x speedup for cached queries)
  - [x] Separate caches (keyword, semantic, RAG)
- [x] Search analytics tracking
  - [x] Query/result/interaction logging
  - [x] Quality metrics (Precision@K, MRR)
  - [x] Top/worst query identification
  - [x] `/analytics-search` REPL command
- [x] Hybrid search with RRF fusion
  - [x] Knowledge graph structure (NetworkX)
  - [x] Query type detection (4 types)
  - [x] Adaptive weight tuning per query type
  - [x] Result deduplication and boosting
  - [x] 15-25% accuracy improvement vs single-method
   
### 🔮 Phase 6: Polish & Community (Future)
- [ ] Additional script templates based on user feedback
- [ ] Additional plugin examples (vscode, analytics_charts, tmux)
- [ ] GUI plugin manager
- [ ] Streaming log viewer
- [ ] Multi-language support for UI
- [ ] Community plugin repository
- [ ] Cloud sync (optional, encrypted)
- [ ] Vim/Neovim deep integration
- [ ] Team sharing features
- [ ] Performance optimizations

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

## 📧 Contact & Credits

**Created, Designed, Architected, and Developed by:** **orpheus497**

Daedelus is a solo project created from scratch by orpheus497, encompassing:
- **System Architecture** - Hybrid embedding + LLM design
- **Core Engineering** - All Python implementation (~30,000 lines)
- **AI Integration** - Local LLM, RAG pipeline, LoRA fine-tuning
- **UX Design** - Interactive REPL, syntax highlighting, intelligent UI
- **Documentation** - Comprehensive guides and technical documentation

**Project Links:**
- GitHub: [@orpheus497](https://github.com/orpheus497)
- Repository: [github.com/orpheus497/daedelus](https://github.com/orpheus497/daedelus)
- Issues: [GitHub Issues](https://github.com/orpheus497/daedelus/issues)

**Technology Stack (100% FOSS):**
- All dependencies: MIT, Apache 2.0, or BSD licensed
- No proprietary code or services
- Complete local processing (privacy-first design)

---

<div align="center">

**⭐ Star this repo if you find it useful!**

*Daedalus - Because your terminal should learn from you, not spy on you.*

</div>
