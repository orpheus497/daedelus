# Daedelus Enhanced Features Documentation

**Version**: 0.2.0+
**Author**: orpheus497
**License**: MIT (100% FOSS)

## Overview

This document describes the comprehensive enhancements added to Daedelus, transforming it into a fully-featured terminal assistant with file operations, command execution, tool development, document ingestion, and training data management capabilities.

---

## Table of Contents

1. [File Operations System](#file-operations-system)
2. [Command Execution System](#command-execution-system)
3. [Tool/Plugin Development System](#toolplugin-development-system)
4. [Document Ingestion System](#document-ingestion-system)
5. [Training Data Organization](#training-data-organization)
6. [User Interface Components](#user-interface-components)
7. [CLI Commands](#cli-commands)
8. [System Integration](#system-integration)
9. [Security & Permissions](#security--permissions)
10. [Examples & Use Cases](#examples--use-cases)

---

## File Operations System

### Overview

The File Operations System provides secure, permission-controlled access to files with full memory tracking for training data generation.

### Components

#### FileOperationsManager
Main interface for all file operations with built-in permission checks and logging.

**Key Features**:
- Read/write/list operations with permission validation
- Automatic logging for training data
- Support for multiple file types (text, binary, JSON, etc.)
- Metadata extraction (MIME type, size, timestamps)
- Size limits and safety checks

**Example Usage**:
```python
from daedelus.core.integration import get_integration

# Initialize integration
integration = get_integration()
integration.initialize()

# Read a file
content = integration.file_ops.read_file("/path/to/file.txt")

# Write a file
success = integration.file_ops.write_file("/path/to/output.txt", "content")

# List directory
files = integration.file_ops.list_directory("/path/to/dir", pattern="*.py")

# Get metadata
metadata = integration.file_ops.get_metadata("/path/to/file.txt")
```

#### FilePermissionManager
Manages file access permissions with configurable rules.

**Default Permissions**:
- `ALLOWED`: Read access to current directory
- `PROMPT`: Write/delete operations (require confirmation)
- `DENIED`: Sensitive directories (.ssh, .gnupg, etc.)

**Permission Levels**:
- `ALLOWED`: Operation proceeds without prompt
- `PROMPT`: User confirmation required
- `DENIED`: Operation blocked

**Customization**:
```python
# Grant permission
integration.file_ops.permission_manager.grant_permission(
    Path("/path/to/file"),
    AccessType.WRITE,
    session_only=True
)

# Deny permission
integration.file_ops.permission_manager.deny_permission(
    Path("/path/to/file"),
    AccessType.DELETE
)
```

#### FileMemoryTracker
Tracks all file operations for session memory and training data.

**Tracked Information**:
- Operation type (read, write, list, delete, metadata)
- File path and metadata
- Success/failure status
- Bytes read/written
- User approval status
- Session ID
- Timestamp

**Viewing History**:
```bash
# CLI command
daedelus files history --limit 50

# Programmatic access
from daedelus.core.file_operations import FileMemoryTracker

tracker = FileMemoryTracker(db_path)
recent = tracker.get_recent_accesses(limit=100)
stats = tracker.get_statistics()
```

---

## Command Execution System

### Overview

Secure command execution system with safety analysis, sandboxing support, and comprehensive logging.

### Components

#### CommandExecutor
Executes shell commands with safety checking and output capture.

**Execution Modes**:
- `DIRECT`: Execute directly in shell
- `SANDBOXED`: Execute in isolated environment (firejail/bwrap)
- `DRY_RUN`: Simulate execution without running

**Example Usage**:
```python
# Execute a command
result = integration.cmd_exec.execute(
    "git status",
    mode=ExecutionMode.DIRECT,
    timeout=30,
    capture_output=True
)

print(f"Exit code: {result.exit_code}")
print(f"Output: {result.stdout}")
print(f"Duration: {result.duration}s")

# Sandboxed execution
result = integration.cmd_exec.execute(
    "untrusted_command",
    mode=ExecutionMode.SANDBOXED
)
```

#### Safety Analysis
Built-in safety analyzer detects dangerous commands.

**Safety Levels**:
- `SAFE`: Command is safe to execute
- `WARNING`: Potentially dangerous, requires confirmation
- `DANGEROUS`: Very dangerous, strong warning
- `BLOCKED`: Automatically blocked

**Detected Patterns**:
- Destructive deletion (`rm -rf /`)
- Direct disk writes (`dd of=/dev/sd*`)
- Fork bombs
- World-writable permissions (chmod 777)

#### InteractiveShell
Maintains persistent shell session with state.

```python
shell = integration.interactive_shell

# Execute commands with persistent state
shell.execute_command("cd /tmp")
shell.execute_command("ls")  # Lists /tmp

# Get history
history = shell.get_history(limit=10)
```

---

## Tool/Plugin Development System

### Overview

Complete system for creating, managing, and executing custom tools and plugins with sandboxing and permission controls.

### Components

#### BaseTool
Abstract base class for all tools.

**Creating a Tool**:
```python
from daedelus.core.tool_system import BaseTool, ToolMetadata, ToolCategory, ToolPermission

class MyTool(BaseTool):
    def __init__(self, metadata: ToolMetadata):
        super().__init__(metadata or ToolMetadata(
            name="my_tool",
            version="1.0.0",
            description="My custom tool",
            author="Your Name",
            category=ToolCategory.UTILITY,
            permissions={ToolPermission.FILE_READ}
        ))

    def execute(self, **kwargs):
        # Tool implementation
        return {"status": "success", "data": kwargs}

    def validate_inputs(self, **kwargs):
        # Validate parameters
        return True
```

#### ToolRegistry
Manages tool discovery and registration.

```python
# Discover tools
count = integration.tool_registry.discover_tools()

# List tools
tools = integration.tool_registry.list_tools(category=ToolCategory.UTILITY)

# Register tool manually
integration.tool_registry.register_tool(MyTool, source_path=Path("my_tool.py"))
```

#### ToolExecutor
Executes tools with permission checking.

```python
# Execute a tool
result = integration.tool_executor.execute_tool(
    "my_tool",
    sandboxed=False,
    param1="value1",
    param2="value2"
)

print(f"Success: {result.success}")
print(f"Output: {result.output}")
```

### CLI Tool Management

```bash
# List installed tools
daedelus tools list

# Create new tool from template
daedelus tools create my_awesome_tool --category utility

# Discover tools
daedelus tools discover
```

---

## Document Ingestion System

### Overview

Ingest documents and files to automatically convert them into training data for the GGUF model.

### Supported Formats

- **Text**: .txt, .md
- **Code**: .py, .js, .ts, .java, .cpp, .c, .sh, .rs, .go, .rb, .php
- **PDF**: .pdf
- **HTML**: .html, .htm
- **Data**: .json, .xml, .yaml, .yml

### Components

#### DocumentParser
Parses various document formats and extracts content.

**Features**:
- Automatic type detection
- Structured data extraction
- Code analysis (functions, classes, imports)
- PDF text extraction
- HTML cleaning

#### DocumentChunker
Splits large documents into trainable chunks.

**Configuration**:
- Max chunk size (default: 512 tokens)
- Overlap between chunks (default: 50 tokens)
- Sentence-boundary aware splitting

#### TrainingDataFormatter
Converts documents into training data format.

**Training Formats**:
- Code explanation
- Function/class analysis
- Documentation summarization
- Q&A generation

### Usage

```bash
# Ingest single document
daedelus ingest document README.md --category docs --tags readme markdown

# Ingest entire directory
daedelus ingest directory ./docs --recursive --pattern "*.md"
```

**Programmatic**:
```python
# Ingest document
integration.doc_ingest.ingest_document(
    Path("README.md"),
    category="documentation",
    tags=["readme", "markdown"]
)

# Ingest directory
stats = integration.doc_ingest.ingest_directory(
    Path("./docs"),
    recursive=True,
    pattern="*.md"
)

# Export training data
integration.doc_ingest.export_training_data(
    Path("training.jsonl"),
    format='jsonl'
)
```

---

## Training Data Organization

### Overview

Comprehensive system for collecting, organizing, and exporting training data from all sources.

### Data Sources

1. **Command History**: Command patterns, usage, and contexts
2. **File Operations**: File access patterns and behaviors
3. **Tool Executions**: Tool usage patterns
4. **Ingested Documents**: Document content and knowledge

### Components

#### TrainingDataOrganizer
Aggregates and organizes training data from all sources.

**Example**:
```python
# Collect all training data
dataset = integration.training_organizer.collect_all_training_data(
    include_commands=True,
    include_file_ops=True,
    include_tools=True,
    include_documents=True,
    limit_per_source=1000
)

print(f"Collected {len(dataset.examples)} examples")

# Export dataset
output_path = integration.training_organizer.export_dataset(
    dataset,
    format='jsonl',
    min_quality='medium'
)
```

### Training Data Quality

**Quality Levels**:
- `HIGH`: Well-formed, successful operations
- `MEDIUM`: Acceptable but may need filtering
- `LOW`: Errors, failures - use with caution
- `EXCLUDED`: Should not be used for training

### CLI Commands

```bash
# Collect training data
daedelus training collect --limit 1000

# Export training data
daedelus training export --format jsonl --quality medium --output training.jsonl

# View statistics
daedelus training stats
```

---

## User Interface Components

### Settings Panel

Interactive UI for managing all Daedelus settings.

**Tabs**:
- File Permissions
- Command Execution
- Tool Permissions
- Training Data
- System Preferences

**Launch**:
```bash
daedelus settings
```

### Memory & Permissions Panel

View session memory, access history, and manage permissions in real-time.

**Tabs**:
- Overview (session statistics)
- Commands (command history)
- Files (file access history)
- Tools (tool execution history)
- Permissions (permission management)
- Tree View (hierarchical memory view)

**Launch**:
```bash
daedelus memory
```

### Enhanced Dashboard

Comprehensive dashboard with all features.

**Tabs**:
- Overview (system statistics)
- Commands (command analytics)
- Files (file operations monitoring)
- Tools (tool management)
- Training (training data management)
- System (system health)

**Launch**:
```bash
daedelus dashboard --enhanced
```

---

## CLI Commands

### File Operations

```bash
# View file operation history
daedelus files history --limit 50 --operation read

# View file operation statistics
daedelus files stats
```

### Tool Management

```bash
# List installed tools
daedelus tools list --category utility

# Create new tool
daedelus tools create my_tool --category custom

# Discover tools
daedelus tools discover
```

### Document Ingestion

```bash
# Ingest document
daedelus ingest document README.md --category docs --tags readme

# Ingest directory
daedelus ingest directory ./docs --recursive --pattern "*.md"
```

### Training Data

```bash
# Collect training data
daedelus training collect --commands --files --tools --documents --limit 1000

# Export training data
daedelus training export --format jsonl --output training.jsonl --quality medium

# View statistics
daedelus training stats
```

### User Interface

```bash
# Launch settings
daedelus settings

# Launch memory & permissions panel
daedelus memory

# Launch enhanced dashboard
daedelus dashboard --enhanced
```

---

## System Integration

### DaedelusIntegration Class

Unified API for all features.

```python
from daedelus.core.integration import DaedelusIntegration

# Initialize
integration = DaedelusIntegration()
integration.initialize(discover_tools=True)

# Access components
integration.file_ops           # File operations
integration.cmd_exec           # Command execution
integration.tool_executor      # Tool execution
integration.tool_registry      # Tool registry
integration.doc_ingest         # Document ingestion
integration.training_organizer # Training data
integration.interactive_shell  # Interactive shell

# Get statistics
stats = integration.get_comprehensive_statistics()

# Health check
health = integration.health_check()

# Shutdown
integration.shutdown()
```

### Global Singleton

```python
from daedelus.core.integration import get_integration, initialize_integration

# Get instance
integration = get_integration()

# Initialize
integration = initialize_integration(discover_tools=True)
```

---

## Security & Permissions

### Permission Model

All operations go through permission checks:

1. **Check**: Permission level determined (ALLOWED, PROMPT, DENIED)
2. **Prompt**: If required, user is prompted for approval
3. **Execute**: Operation proceeds if approved
4. **Log**: All operations logged with approval status

### Session vs Persistent Permissions

- **Session**: Granted for current session only
- **Persistent**: Stored in configuration for future sessions

### Sensitive Data Protection

**Automatically Excluded**:
- `.ssh` directory (SSH keys)
- `.gnupg` directory (GPG keys)
- `.password-store` (passwords)
- Files matching: `password`, `secret`, `token`, `api_key`, etc.

### Sandboxing

Tools and commands can be executed in sandboxed environments:

**Supported Sandboxes**:
- firejail (network isolation, filesystem restrictions)
- bubblewrap (namespace isolation)

**Fallback**: Direct execution if no sandbox available

---

## Examples & Use Cases

### Use Case 1: Automated Code Documentation

```python
# Ingest codebase
integration.doc_ingest.ingest_directory(
    Path("./src"),
    recursive=True,
    pattern="*.py"
)

# Collect training data
dataset = integration.training_organizer.collect_all_training_data(
    include_documents=True
)

# Export for fine-tuning
integration.training_organizer.export_dataset(dataset, format='alpaca')
```

### Use Case 2: Custom Tool Development

```bash
# Create tool template
daedelus tools create code_analyzer --category analysis

# Edit the tool (tools/code_analyzer.py)
# ... implement tool logic ...

# Discover and register
daedelus tools discover

# Execute tool
daedelus tools execute code_analyzer --file mycode.py
```

### Use Case 3: Interactive Shell Session

```python
shell = integration.interactive_shell

# Navigate and explore
shell.execute_command("cd /tmp")
shell.execute_command("ls -la")
shell.execute_command("cat file.txt")

# Get session history
history = shell.get_history()

# All operations are logged for training
```

### Use Case 4: Permission Management

```bash
# Launch memory panel
daedelus memory

# Navigate to Permissions tab
# View granted permissions
# Revoke or approve pending permissions
# Clear denied permissions
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Daedelus Integration                     │
│                      (Unified API)                          │
└────────────┬────────────────────────────────────────────────┘
             │
     ┌───────┴────────┬────────────┬──────────┬────────────┐
     │                │            │          │            │
┌────▼─────┐  ┌──────▼─────┐  ┌───▼────┐  ┌─▼──────┐  ┌──▼────────┐
│   File   │  │  Command   │  │  Tool  │  │Document│  │ Training  │
│Operations│  │ Execution  │  │ System │  │Ingest  │  │  Data     │
└────┬─────┘  └──────┬─────┘  └───┬────┘  └─┬──────┘  └──┬────────┘
     │               │            │          │            │
┌────▼─────┐  ┌──────▼─────┐  ┌───▼────┐  ┌─▼──────┐  ┌──▼────────┐
│Permission│  │   Safety   │  │Registry│  │ Parser │  │ Organizer │
│ Manager  │  │  Analyzer  │  │        │  │        │  │           │
└────┬─────┘  └──────┬─────┘  └───┬────┘  └─┬──────┘  └──┬────────┘
     │               │            │          │            │
┌────▼─────────────────▼────────────▼──────────▼────────────▼────┐
│                        SQLite Databases                         │
│  (file_ops.db, cmd_exec.db, tools.db, docs.db, history.db)    │
└─────────────────────────────────────────────────────────────────┘
                               │
                     ┌─────────▼──────────┐
                     │  Training Pipeline │
                     │    (GGUF Model)    │
                     └────────────────────┘
```

---

## Configuration

All features are configurable via `~/.config/daedelus/config.yaml`:

```yaml
file_operations:
  require_read_permission: false
  require_write_permission: true
  require_delete_permission: true
  max_file_size_mb: 10

command_execution:
  enable_safety_analysis: true
  block_dangerous_commands: true
  prompt_for_warnings: true
  default_timeout: 300
  capture_output: true
  log_all_executions: true

tools:
  require_permission_approval: true
  enable_sandboxing: false
  auto_discover: true

training:
  collect_command_history: true
  collect_file_operations: true
  collect_tool_executions: true
  collect_documents: true
  auto_train: true
  command_threshold: 500
  min_quality: medium
  exclude_sensitive: true
```

---

## Migration & Compatibility

### From v0.1.x to v0.2.0+

All existing functionality is preserved. New features are additive:

1. **Existing databases**: Continue to work unchanged
2. **CLI commands**: All previous commands still available
3. **Configuration**: New config options have sensible defaults
4. **Dependencies**: New dependencies installed automatically

**First-time initialization**:
```bash
# Re-run setup to create new directories
daedelus setup

# Initialize new features
python -c "from daedelus.core.integration import initialize_integration; initialize_integration()"
```

---

## Performance Considerations

### Resource Usage

- **Idle**: ~50-100MB RAM (depends on enabled features)
- **Active**: ~200-400MB RAM
- **With LLM**: ~3-4GB RAM (when training)

### Database Sizes

- **Command History**: ~100KB per 1000 commands
- **File Operations**: ~50KB per 1000 operations
- **Tool Executions**: ~20KB per 1000 executions
- **Ingested Documents**: Varies by document size

### Optimization Tips

1. **Limit history retention**: Configure in `config.yaml`
2. **Use quality filtering**: Export only high-quality training data
3. **Batch operations**: Process multiple files/commands together
4. **Lazy loading**: Components initialize on-demand

---

## Troubleshooting

### Common Issues

**Issue**: "Permission denied" when accessing files
**Solution**: Check `file_permissions.json` or grant permission via UI

**Issue**: Tools not discovered
**Solution**: Run `daedelus tools discover`

**Issue**: Training data export fails
**Solution**: Ensure sufficient disk space and check database paths

**Issue**: Sandboxed execution fails
**Solution**: Install firejail or bubblewrap, or use direct execution

### Logging

Enable debug logging:
```bash
daedelus -vvv [command]
```

### Support

- GitHub Issues: https://github.com/orpheus497/daedelus/issues
- Documentation: https://daedelus.readthedocs.io

---

## Future Enhancements

Planned for future releases:

- [ ] Cloud sync for training data (encrypted)
- [ ] Multi-device model synchronization
- [ ] Advanced analytics dashboard
- [ ] Plugin marketplace
- [ ] Real-time collaboration features
- [ ] GUI dashboard (web-based)

---

**Author**: orpheus497
**Created**: 2024-11-09
**License**: MIT (100% FOSS)
**Version**: 0.2.0+
