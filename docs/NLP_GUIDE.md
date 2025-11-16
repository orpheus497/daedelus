# Daedelus Natural Language Processing - Quick Guide

## Using Natural Language Commands

Daedelus now understands natural language and generates accurate, OS-specific commands.

### Basic Usage

Simply type what you want to do in plain English:

```bash
daedelus
> update my system packages
→ sudo dnf update -y

> find all python files
→ find . -name '*.py'

> show disk usage
→ df -h
```

### Supported Command Types

1. **System Operations**
   - "update my system"
   - "install package X"
   - "search for package Y"

2. **File Operations**
   - "find all python files"
   - "create a directory called projects"
   - "delete old log files"

3. **Git Operations**
   - "commit my changes"
   - "push to remote"
   - "show git status"

4. **System Information**
   - "show disk usage"
   - "list running processes"
   - "check memory usage"

5. **Script Generation**
   - "/write-script create a backup script for my documents"
   - "generate a script to process CSV files"

### Command Feedback

When Daedelus suggests a command:

1. **Accept** - Press `Y` or `Enter` to execute
2. **Reject** - Press `n` to skip
3. **Modify** - Type your own command

Your feedback helps Daedelus learn and improve!

### Dashboard - NLP Prompts Tab

View all your natural language interactions:

```bash
daedelus dashboard
```

Navigate to the "NLP Prompts" tab to see:
- All prompts you've entered
- Commands generated
- Your feedback (accepted/rejected)
- Overall accuracy metrics

### Training Data

Your interactions are collected as training data to improve the AI:

**What's Collected:**
- Your natural language prompt
- Detected intent
- Generated commands
- Which command you executed
- Whether it succeeded

**Export Training Data:**
```bash
# Via dashboard: Click "Export Training Data"
# Data saved to: ~/.local/share/daedelus/training_data_YYYYMMDD_HHMMSS.json
```

**Privacy:**
- All data stays on your system
- No external API calls
- You control what's collected
- Can clear history anytime

### Advanced Features

**Explain Commands:**
```bash
> /explain tar -xzf archive.tar.gz
```

**Generate Multiple Options:**
```bash
> /generate find large files
# Returns 3 alternative commands
```

**Write Scripts:**
```bash
> /write-script backup my documents folder
# Creates executable script
```

### OS-Specific Commands

Daedelus automatically detects your OS and generates appropriate commands:

| Your OS | Update Command |
|---------|----------------|
| Fedora/RHEL 8+ | `sudo dnf update -y` |
| RHEL 7/CentOS 7 | `sudo yum update -y` |
| Debian/Ubuntu | `sudo apt update && sudo apt upgrade -y` |
| Arch Linux | `sudo pacman -Syu --noconfirm` |
| macOS (Homebrew) | `brew update && brew upgrade` |

### Tips for Best Results

1. **Be Specific**
   - ✓ "find python files modified today"
   - ✗ "find stuff"

2. **Use Action Words**
   - ✓ "create", "find", "delete", "update"
   - ✗ "I need", "maybe"

3. **Provide Context**
   - ✓ "install python development tools"
   - ✗ "install dev"

4. **Review Before Executing**
   - Always check suggested commands
   - Especially for system modifications
   - Can reject and try again

### Troubleshooting

**"I'm not sure how to help with that"**
- Try rephrasing your request
- Be more specific
- Use action verbs
- Check `/help` for examples

**Commands Don't Match Your OS**
- Report as bug (OS detection may need update)
- Use explicit commands as fallback

**Want to Disable NLP**
- Use `/` prefix for explicit commands
- Or just type shell commands directly

### Privacy Settings

Control what data is collected:

```bash
daedelus settings
# Navigate to Privacy section
```

Options:
- Disable NLP prompt logging
- Auto-clear prompts after N days
- Exclude specific directories
- Filter sensitive commands

### Examples

**System Maintenance:**
```bash
> update my system packages
→ sudo dnf update -y
Execute? (Y/n): y
✓ System updated successfully

> clean up old packages
→ sudo dnf autoremove -y
Execute? (Y/n): y
```

**Development Workflow:**
```bash
> find all python files and count lines
Understanding: I'll execute these steps:
1. Find matching files
2. Count the results

Suggested commands:
1. find . -name '*.py' -exec wc -l {} + | tail -1
2. find . -name '*.py' | xargs wc -l

Execute command 1? (Y/n): y
```

**Script Creation:**
```bash
> /write-script backup my home directory to external drive
Understanding: Created bash script: /tmp/backup_script_1699999999.sh

Script content:
#!/bin/bash
# Backup home directory to external drive
...

Execute? (Y/n): y
→ bash /tmp/backup_script_1699999999.sh
```

## Learning Cycle

1. **You** enter natural language
2. **Daedelus** interprets and generates commands
3. **You** accept, reject, or modify
4. **System** learns from your feedback
5. **Model** improves with each interaction

Over time, Daedelus becomes more accurate and personalized to your workflow!

## Getting Help

- `/help` - Show all REPL commands
- `daedelus --help` - Show all CLI commands
- `daedelus dashboard` - Visual interface
- Check logs: `~/.local/share/daedelus/daemon.log`

## Feedback

Your feedback makes Daedelus better:
- Accept good suggestions
- Reject bad ones
- Report bugs and issues
- Suggest new features

The more you use it, the smarter it gets! 🧠✨
