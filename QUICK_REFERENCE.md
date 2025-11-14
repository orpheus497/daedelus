# Daedelus Quick Reference

*Your AI-Powered Terminal Assistant*

## 🚀 Quick Start

```bash
# Start Daedelus (either command works)
daedelus
deus

# Setup for first time
daedelus setup

# Start background daemon
daedelus start

# Check status
daedelus status
```

## 🎯 Command Structure

```
daedelus [command] [options]  # Full command name
deus [command] [options]      # Quick alias (identical)
```

**Key Point:** `deus` is an alias for `daedelus` - they work exactly the same!

## 🧠 REPL Mode (Default)

Just run `daedelus` or `deus` to enter interactive mode.

### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show help | `/help` |
| `/quit` | Exit REPL | `/quit` or Ctrl+D |
| `/search <query>` | Search history | `/search git commit` |
| `/recent [n]` | Recent commands | `/recent 20` |
| `/stats` | Usage statistics | `/stats` |

### AI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/generate <desc>` | Generate command | `/generate find large files` |
| `/explain <cmd>` | Explain command | `/explain tar -xzf file.tar.gz` |
| `/write-script <desc>` | Create script | `/write-script backup documents` |
| `/read <file>` | Read & analyze | `/read config.yaml` |
| `/write <file>` | Write file | `/write notes.txt meeting agenda` |

### Natural Language

Just type naturally - Daedelus understands:

```bash
> Tell me what's in this directory
> Create a backup script for my home folder
> Show me all Python files modified today
> Find files larger than 100MB
> How do I compress a directory?
```

### Shell Commands

Any command not starting with `/` is executed as a shell command:

```bash
> ls -la
> cd ~/projects
> git status
> docker ps
> python script.py
```

## 📋 External Commands

Run from your regular terminal (not in REPL):

### Daemon Management

```bash
daedelus start         # Start background daemon
daedelus stop          # Stop daemon
daedelus status        # Check daemon status
daedelus restart       # Restart daemon
```

### Configuration

```bash
daedelus setup         # Interactive setup wizard
daedelus config list   # View configuration
daedelus config set <key> <value>  # Set config
```

### Document Ingestion

```bash
# Add documents for AI training
daedelus ingest document ./guide.md
daedelus ingest document ./script.py -c code
daedelus ingest directory ./docs -r -p "*.md"
```

### Training Data

```bash
daedelus training stats              # View statistics
daedelus training collect            # Collect training data
daedelus training export -f jsonl    # Export for fine-tuning
```

### Model Management

```bash
daedelus model status        # Check model status
daedelus model download      # Download AI model
daedelus model setup         # Setup LLM
```

### File Operations

```bash
daedelus files history       # File operation history
daedelus files stats         # File statistics
```

### Tools & Plugins

```bash
daedelus tools list          # List installed tools
daedelus tools discover      # Discover new tools
daedelus tools create mytool # Create new tool
```

### Dashboard & UI

```bash
daedelus dashboard    # Launch TUI dashboard
daedelus settings     # Settings panel
daedelus memory       # Memory & permissions panel
```

### Analytics

```bash
daedelus analytics           # Detailed analytics
daedelus history --limit 50  # Command history
```

## ⌨️ Keyboard Shortcuts (in REPL)

| Shortcut | Action |
|----------|--------|
| `Tab` | Auto-complete from history |
| `↑` / `↓` | Navigate command history |
| `Ctrl+C` | Clear current line |
| `Ctrl+D` | Exit REPL |
| `Ctrl+R` | Reverse search (coming soon) |

## 💡 Tips & Tricks

### 1. Use Natural Language
```bash
> Tell me the disk usage
# Instead of remembering: df -h
```

### 2. Generate Scripts
```bash
> /write-script monitor CPU and send alert if over 80%
# Creates ready-to-use script with error handling
```

### 3. Analyze Files
```bash
> /read error.log
# Gets AI analysis of what's wrong
```

### 4. Quick Alias
```bash
# Add to ~/.bashrc or ~/.zshrc
alias d='deus'

# Now just type:
d  # Starts Daedelus REPL
```

### 5. Project Context
```bash
# Daedelus remembers your current directory
> cd ~/projects/myapp
> generate a Dockerfile for Python app
# AI knows you're in a Python project
```

## 🔒 Privacy

- **100% Offline** - No data ever leaves your machine
- **No Telemetry** - No tracking, no analytics, no calls home
- **Local Storage** - All data in `~/.local/share/daedelus/`
- **Privacy Config** - Edit `privacy.yaml` for custom exclusions

### Clear All Data
```bash
rm -rf ~/.local/share/daedelus
```

## 🆘 Help & Support

### In REPL
```bash
> /help
```

### Command Help
```bash
daedelus --help
daedelus <command> --help
```

### Documentation
```bash
# In project directory
cat docs/README.md
cat QUICKSTART.md
```

### Troubleshooting
```bash
# Check daemon logs
daedelus logs

# Verbose mode
daedelus -vvv status

# Test connection
daedelus ping
```

## 📊 Common Workflows

### Daily Usage
```bash
# Morning: Start daemon
daedelus start

# Work: Use REPL for commands
daedelus
> /generate backup script
> Tell me the system load
> /read todo.txt

# Evening: Stop daemon
daedelus stop
```

### Development
```bash
# Add documentation to training
daedelus ingest directory ./docs -r

# Generate code
daedelus
> /write-script parse CSV and extract emails
> /generate test the API endpoint

# Review history
> /search git push
```

### System Administration
```bash
daedelus
> Show me disk usage by directory
> Find files not accessed in 6 months
> /write-script cleanup old logs
> Monitor system resources
```

## 🎯 Pro Tips

1. **Tab Completion** - Press Tab to see suggestions from your history
2. **Context Matters** - AI uses your current directory and recent commands
3. **Be Specific** - More detail in natural language = better results
4. **Review Scripts** - Always check generated scripts before executing
5. **Build Gradually** - Start with simple commands, let AI learn your style

## 🌟 Examples Gallery

### File Management
```bash
> Find all duplicate files in current directory
> /write-script organize downloads by file type
> /read .gitignore and explain what's excluded
```

### Development
```bash
> Generate a Python script to scrape website data
> /write-script run tests and email results
> Explain this error: permission denied
```

### DevOps
```bash
> /write-script deploy to production with rollback
> Show me all Docker containers using more than 1GB RAM
> /generate kubernetes deployment yaml
```

### Data Processing
```bash
> /write-script merge CSV files and remove duplicates
> Parse JSON and extract all email addresses
> /generate convert YAML to JSON
```

## 📚 Learn More

- **README.md** - Project overview
- **QUICKSTART.md** - Detailed getting started guide
- **docs/API.md** - API reference
- **docs/NEW_FEATURES.md** - Latest features

## 🎓 Version Info

```bash
daedelus --version
```

---

**Remember:** Daedelus learns from YOU. The more you use it, the better it becomes at predicting what you need!

Happy commanding! 🚀
