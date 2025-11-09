# Daedalus Troubleshooting Guide

**Version**: 0.2.0
**Last Updated**: 2025-11-09

This guide helps you diagnose and fix common issues with Daedalus.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Daemon Issues](#daemon-issues)
- [Shell Integration Issues](#shell-integration-issues)
- [Suggestion Issues](#suggestion-issues)
- [LLM Issues (Phase 2)](#llm-issues-phase-2)
- [Performance Issues](#performance-issues)
- [Database Issues](#database-issues)
- [Configuration Issues](#configuration-issues)
- [Log Analysis](#log-analysis)
- [Emergency Procedures](#emergency-procedures)

---

## Installation Issues

### FastText Won't Compile

**Symptom**: `pip install fasttext` fails with compilation errors

**Causes**:
1. Missing C++ compiler
2. Missing Python development headers
3. Incompatible Python version

**Solutions**:

#### Ubuntu/Debian
```bash
# Install build tools
sudo apt update
sudo apt install build-essential python3-dev

# Retry installation
pip install fasttext==0.9.2
```

#### macOS
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Or use Homebrew
brew install gcc

# Retry installation
pip install fasttext==0.9.2
```

#### Fedora
```bash
# Install development tools
sudo dnf install gcc-c++ python3-devel

# Retry installation
pip install fasttext==0.9.2
```

#### Alternative: Install from Source
```bash
git clone https://github.com/facebookresearch/fastText.git
cd fastText
pip install .
```

#### Last Resort: Use Python 3.10 or 3.11
FastText compiles more reliably on Python 3.10-3.11:
```bash
# Create new virtualenv with Python 3.10
python3.10 -m venv venv
source venv/bin/activate
pip install fasttext==0.9.2
```

---

### llama-cpp-python Installation Fails

**Symptom**: Phase 2 dependencies won't install

**Solution 1: Basic CPU Installation**
```bash
pip install llama-cpp-python --no-cache-dir
```

**Solution 2: With GPU Support (CUDA)**
```bash
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python --no-cache-dir
```

**Solution 3: With GPU Support (Metal/macOS)**
```bash
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python --no-cache-dir
```

**Solution 4: Pre-built Wheels**
Check [llama-cpp-python releases](https://github.com/abetlen/llama-cpp-python/releases) for pre-built wheels.

---

### Permission Denied Errors

**Symptom**: Cannot create directories or files

**Solution 1: Check Permissions**
```bash
# Check directories
ls -la ~/.local/share/daedelus
ls -la ~/.config/daedelus

# Fix permissions
chmod 755 ~/.local/share/daedelus
chmod 755 ~/.config/daedelus
```

**Solution 2: Run Setup Again**
```bash
daedelus setup
```

---

## Daemon Issues

### Daemon Won't Start

**Symptom**: `daedelus start` fails or hangs

**Diagnosis**:
```bash
# Check if already running
daedelus status

# Check logs for errors
tail -50 ~/.local/share/daedelus/daemon.log

# Try foreground mode for detailed output
daedelus start --foreground
```

**Common Causes & Solutions**:

#### 1. Socket Already Exists
```bash
# Remove stale socket
rm ~/.local/share/daedelus/runtime/daemon.sock

# Try starting again
daedelus start
```

#### 2. Port/Socket in Use
```bash
# Kill any existing daemon
pkill -f daedelus

# Clean up socket
rm ~/.local/share/daedelus/runtime/daemon.sock

# Start fresh
daedelus start
```

#### 3. Missing Dependencies
```bash
# Check dependencies
python -c "import fasttext, annoy; print('OK')"

# If fails, reinstall
pip install -r requirements.txt
```

#### 4. Corrupted Database
```bash
# Backup current database
cp ~/.local/share/daedelus/history.db ~/.local/share/daedelus/history.db.backup

# Try to repair
sqlite3 ~/.local/share/daedelus/history.db "PRAGMA integrity_check;"

# If corrupted, restore from backup or start fresh
daedelus setup --reset
```

---

### Daemon Crashes Repeatedly

**Diagnosis**:
```bash
# Check daemon log
tail -100 ~/.local/share/daedelus/daemon.log

# Look for stack traces or error patterns
grep -i "error\|exception\|traceback" ~/.local/share/daedelus/daemon.log
```

**Common Causes**:

#### 1. Out of Memory
```bash
# Check memory usage
free -h

# If Phase 2 (LLM) is enabled and you're low on RAM:
# Disable LLM temporarily
vi ~/.config/daedelus/config.yaml
# Set: llm.enabled = false

daedelus restart
```

#### 2. Corrupted Model Files
```bash
# Remove and retrain Phase 1 models
rm ~/.local/share/daedelus/embeddings.bin
rm ~/.local/share/daedelus/commands.ann

# Restart (will retrain on next shutdown)
daedelus restart
```

#### 3. Bad Configuration
```bash
# Reset to defaults
mv ~/.config/daedelus/config.yaml ~/.config/daedelus/config.yaml.backup
daedelus setup

# Compare and merge
diff ~/.config/daedelus/config.yaml ~/.config/daedelus/config.yaml.backup
```

---

### Daemon Won't Stop

**Symptom**: `daedelus stop` hangs or doesn't work

**Solution 1: Force Kill**
```bash
# Find daemon process
ps aux | grep daedelus

# Kill it
pkill -9 -f daedelus

# Clean up socket
rm ~/.local/share/daedelus/runtime/daemon.sock
```

**Solution 2: Check Systemd (if using systemd)**
```bash
# Stop via systemd
systemctl --user stop daedelus

# Check status
systemctl --user status daedelus
```

---

## Shell Integration Issues

### Ctrl+Space Doesn't Work

**Diagnosis**:
```bash
# 1. Check daemon is running
daedelus status

# 2. Check shell integration loaded
type daedelus_suggest  # Should show function definition

# 3. Test IPC manually
daedelus search "git"  # Should return results
```

**Solutions**:

#### 1. Daemon Not Running
```bash
daedelus start
```

#### 2. Shell Integration Not Loaded
```bash
# ZSH
echo "source $(daedelus shell-integration zsh)" >> ~/.zshrc
source ~/.zshrc

# Bash
echo "source $(daedelus shell-integration bash)" >> ~/.bashrc
source ~/.bashrc

# Fish
echo "source (daedelus shell-integration fish)" >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

#### 3. Keybinding Conflict
```bash
# Check if Ctrl+Space is already bound
# ZSH: bindkey | grep '^\"\^@ '
# Bash: bind -p | grep '\"\\C-@ '

# Use alternative keybinding
export DAEDELUS_KEYBIND="^X"  # Ctrl+X instead
```

---

### Commands Not Being Logged

**Diagnosis**:
```bash
# Check recent commands
daedelus search "."  # Search for anything

# Check database directly
sqlite3 ~/.local/share/daedelus/history.db "SELECT COUNT(*) FROM commands;"
```

**Solutions**:

#### 1. Hook Not Installed
Verify hooks are active:

**ZSH**:
```bash
# Check preexec hook
typeset -f preexec | grep daedelus

# If missing, reload integration
source $(daedelus shell-integration zsh)
```

**Bash**:
```bash
# Check PROMPT_COMMAND
echo $PROMPT_COMMAND | grep daedelus

# If missing, reload integration
source $(daedelus shell-integration bash)
```

#### 2. Privacy Filter Blocking
```bash
# Check if your commands match excluded patterns
grep -E "password|token|secret" ~/.local/share/daedelus/daemon.log

# Adjust filters in config if needed
vi ~/.config/daedelus/config.yaml
# Edit privacy.excluded_patterns
```

#### 3. Permission Issues
```bash
# Check database permissions
ls -l ~/.local/share/daedelus/history.db

# Should be writable by user
chmod 644 ~/.local/share/daedelus/history.db
```

---

## Suggestion Issues

### No Suggestions Appearing

**Diagnosis**:
```bash
# 1. Check if daemon has data
daedelus status
# Look for "commands_logged" > 0

# 2. Test suggestion engine
daedelus search "git"
# Should return matching commands

# 3. Check models exist
ls -lh ~/.local/share/daedelus/*.{bin,ann}
```

**Solutions**:

#### 1. Insufficient Data
Daedalus needs data to learn from:
```bash
# Use your shell normally for a while (>50 commands)
# Then check:
daedelus status
```

#### 2. Models Not Trained
```bash
# Force model update
daedelus stop  # Triggers training
daedelus start

# Check if models were created
ls -lh ~/.local/share/daedelus/
```

#### 3. Embedding Model Missing
```bash
# Check if FastText model exists
ls ~/.local/share/daedelus/embeddings.bin

# If missing, stop/start daemon to trigger training
daedelus restart
```

---

### Suggestions Are Poor Quality

**Diagnosis**:
```bash
# Check suggestion settings
grep -A 5 "suggestions:" ~/.config/daedelus/config.yaml

# Check if enough data
daedelus status | grep "commands_logged"
```

**Solutions**:

#### 1. Lower Confidence Threshold
```yaml
# Edit config
suggestions:
  min_confidence: 0.2  # Lower from 0.3
  max_suggestions: 10  # Show more options
```

#### 2. Build More History
```bash
# Daedalus learns from patterns
# Use shell more, especially in varied directories
```

#### 3. Retrain Models
```bash
# Force retrain with current data
daedelus stop  # Triggers training
daedelus start
```

---

## LLM Issues (Phase 2)

### LLM Features Not Working

**Diagnosis**:
```bash
# 1. Check if LLM is enabled
grep "llm:" ~/.config/daedelus/config.yaml

# 2. Check if dependencies installed
python -c "import llama_cpp; print('OK')"

# 3. Check if model exists
ls -lh ~/.local/share/daedelus/llm/*.gguf
```

**Solutions**:

#### 1. LLM Disabled in Config
```yaml
# Edit config
llm:
  enabled: true
```

#### 2. Dependencies Missing
```bash
pip install -r requirements-llm.txt
```

#### 3. Model Not Downloaded
```bash
# Download Phi-3-mini
daedelus model download

# This downloads ~2.4GB, may take time
```

---

### Model Download Fails

**Symptom**: `daedelus model download` fails or hangs

**Solutions**:

#### 1. Network Issues
```bash
# Check internet connection
ping huggingface.co

# Use proxy if needed
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port

daedelus model download
```

#### 2. Disk Space
```bash
# Check available space (need ~3GB)
df -h ~/.local/share/daedelus

# Clean old backups if needed
rm ~/.local/share/daedelus/backups/daedelus_backup_*.tar.gz
```

#### 3. Manual Download
```bash
# Download manually from HuggingFace
cd ~/.local/share/daedelus/llm
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
```

---

### LLM Inference Too Slow

**Symptom**: Suggestions take >5 seconds

**Solutions**:

#### 1. Use Smaller Context
```yaml
llm:
  context_length: 1024  # Reduce from 2048
  max_tokens: 50        # Reduce from 100
```

#### 2. Enable GPU Acceleration
```bash
# Reinstall with GPU support
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python --force-reinstall

# Or for macOS (Metal)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python --force-reinstall
```

#### 3. Use More Quantization
```bash
# Download more quantized model (smaller, faster)
# Q4_K_M (current): ~2.4GB, good quality
# Q3_K_M: ~1.9GB, faster, slightly lower quality
```

---

### High Memory Usage

**Symptom**: Daemon using >4GB RAM

**Diagnosis**:
```bash
# Check memory usage
ps aux | grep daedelus
# Or
top -p $(pgrep daedelus)
```

**Solutions**:

#### 1. Disable LLM
```yaml
llm:
  enabled: false
```

#### 2. Restart Daemon
```bash
# Memory leak possible (rare)
daedelus restart
```

#### 3. Use Resource Limits (systemd)
```ini
# /etc/systemd/user/daedelus.service
[Service]
MemoryMax=3G
```

---

## Performance Issues

### Slow Suggestions (>1 second)

**Diagnosis**:
```bash
# Enable debug logging
vi ~/.config/daedelus/config.yaml
# Set: daemon.log_level = DEBUG

# Restart and check logs
daedelus restart
tail -f ~/.local/share/daedelus/daemon.log | grep "latency"
```

**Solutions**:

#### 1. Database Too Large
```bash
# Check database size
ls -lh ~/.local/share/daedelus/history.db

# If >1GB, clean old data
sqlite3 ~/.local/share/daedelus/history.db <<EOF
DELETE FROM commands WHERE timestamp < strftime('%s', 'now', '-90 days');
VACUUM;
EOF
```

#### 2. Index Not Built
```bash
# Rebuild indexes
daedelus stop
rm ~/.local/share/daedelus/commands.ann
daedelus start  # Will rebuild
```

#### 3. Reduce Max Suggestions
```yaml
suggestions:
  max_suggestions: 3  # Reduce from 5
```

---

### High CPU Usage

**Symptom**: Daemon using >50% CPU when idle

**Diagnosis**:
```bash
# Check what's consuming CPU
top -p $(pgrep daedelus)

# Check if in training loop
grep "training" ~/.local/share/daedelus/daemon.log
```

**Solutions**:

#### 1. Stuck in Training
```bash
# Kill and restart
pkill -9 daedelus
daedelus start
```

#### 2. Disable Auto-Training
```yaml
peft:
  enabled: false  # Disable fine-tuning
```

---

## Database Issues

### Database Locked

**Symptom**: "Database is locked" errors in logs

**Solutions**:

#### 1. Wait and Retry
SQLite locks are usually brief. Wait 30s and retry.

#### 2. Increase Timeout
```yaml
database:
  timeout: 60.0  # Increase from 30.0
```

#### 3. Close Other Connections
```bash
# Check for other processes accessing DB
lsof ~/.local/share/daedelus/history.db

# Kill if needed
```

---

### Database Corrupted

**Symptom**: Daemon crashes with SQLite errors

**Diagnosis**:
```bash
sqlite3 ~/.local/share/daedelus/history.db "PRAGMA integrity_check;"
```

**Solutions**:

#### 1. Repair Database
```bash
# Dump and reimport
sqlite3 ~/.local/share/daedelus/history.db ".dump" > dump.sql
mv ~/.local/share/daedelus/history.db ~/.local/share/daedelus/history.db.corrupt
sqlite3 ~/.local/share/daedelus/history.db < dump.sql
```

#### 2. Restore from Backup
```bash
# Find latest backup
ls -lt ~/.local/share/daedelus/backups/

# Restore
tar -xzf ~/.local/share/daedelus/backups/daedelus_backup_*.tar.gz -C ~/.local/share/daedelus/
```

#### 3. Start Fresh (Last Resort)
```bash
# Backup everything first!
cp -r ~/.local/share/daedelus ~/.local/share/daedelus.backup

# Reset
rm ~/.local/share/daedelus/history.db
daedelus setup
```

---

## Configuration Issues

### Config Not Loading

**Symptom**: Changes to `config.yaml` not taking effect

**Solution**:
```bash
# 1. Verify config syntax
python -c "import yaml; yaml.safe_load(open('~/.config/daedelus/config.yaml'))"

# 2. Restart daemon
daedelus restart

# 3. Check if config file is in correct location
ls -l ~/.config/daedelus/config.yaml
```

---

### Invalid Configuration

**Symptom**: Daemon fails to start with config error

**Solution**:
```bash
# Check logs for specific error
tail -50 ~/.local/share/daedelus/daemon.log | grep -i "config"

# Common issues:
# - Indentation (YAML requires spaces, not tabs)
# - Missing quotes around strings with special chars
# - Invalid boolean (use: true/false, not: yes/no)

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('$HOME/.config/daedelus/config.yaml'))"
```

---

## Log Analysis

### Finding Errors

```bash
# Recent errors
grep -i "error" ~/.local/share/daedelus/daemon.log | tail -20

# Exceptions with context
grep -A 5 -i "exception\|traceback" ~/.local/share/daedelus/daemon.log

# Warnings
grep -i "warning" ~/.local/share/daedelus/daemon.log
```

### Understanding Log Levels

- **DEBUG**: Verbose, for development
- **INFO**: Normal operations
- **WARNING**: Potential issues
- **ERROR**: Failures (but recoverable)
- **CRITICAL**: Severe failures

### Enable Debug Logging

```yaml
# config.yaml
daemon:
  log_level: DEBUG
```

```bash
daedelus restart
tail -f ~/.local/share/daedelus/daemon.log
```

---

## Emergency Procedures

### Complete Reset

**Warning**: This deletes all data!

```bash
# 1. Stop daemon
daedelus stop

# 2. Backup (optional but recommended)
tar -czf ~/daedelus-backup-$(date +%Y%m%d).tar.gz \
    ~/.local/share/daedelus \
    ~/.config/daedelus

# 3. Remove all data
rm -rf ~/.local/share/daedelus
rm -rf ~/.config/daedelus

# 4. Reinstall
pip uninstall daedelus
pip install daedelus

# 5. Setup fresh
daedelus setup
daedelus start
```

---

### Recover from Backup

```bash
# 1. Find backup
ls -lt ~/.local/share/daedelus/backups/

# 2. Stop daemon
daedelus stop

# 3. Backup current state
mv ~/.local/share/daedelus ~/.local/share/daedelus.old

# 4. Extract backup
tar -xzf ~/.local/share/daedelus/backups/daedelus_backup_YYYYMMDD_HHMMSS.tar.gz \
    -C ~/.local/share/

# 5. Restart
daedelus start
```

---

### Debug Mode

For comprehensive debugging:

```bash
# 1. Stop daemon
daedelus stop

# 2. Enable debug logging
vi ~/.config/daedelus/config.yaml
# Set: daemon.log_level = DEBUG

# 3. Start in foreground with verbose output
daedelus start --foreground 2>&1 | tee debug.log

# 4. In another terminal, test functionality
daedelus status
daedelus search "test"

# 5. Analyze debug.log
less debug.log
```

---

## Getting Help

If you're still stuck:

1. **Check logs**: `~/.local/share/daedelus/daemon.log`
2. **Check GitHub Issues**: https://github.com/orpheus497/daedelus/issues
3. **Create new issue** with:
   - Daedalus version: `daedelus --version`
   - Python version: `python --version`
   - OS/distro: `uname -a`
   - Relevant log excerpts
   - Steps to reproduce

---

## Common Error Messages

### "ConnectionRefusedError"
**Meaning**: Daemon not running
**Solution**: `daedelus start`

### "FileNotFoundError: daemon.sock"
**Meaning**: Daemon not started or socket removed
**Solution**: `daedelus start`

### "RuntimeError: Failed to load model"
**Meaning**: Model file corrupted or missing
**Solution**: Remove and retrain (`rm ~/.local/share/daedelus/embeddings.bin && daedelus restart`)

### "MemoryError"
**Meaning**: Out of RAM (likely Phase 2 LLM)
**Solution**: Disable LLM or add more RAM

### "sqlite3.OperationalError: database is locked"
**Meaning**: Database in use by another process
**Solution**: Wait or increase timeout in config

---

**For more information**:
- [API Reference](API.md)
- [Architecture Overview](ARCHITECTURE.md)
- [Development Guide](DEVELOPMENT.md)

**Created by [orpheus497](https://github.com/orpheus497)**
