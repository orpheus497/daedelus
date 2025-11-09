# Daedalus API Reference

**Version**: 0.2.0
**Last Updated**: 2025-11-09

This document provides comprehensive API documentation for Daedalus components.

---

## Table of Contents

- [Core Components](#core-components)
  - [Database](#database)
  - [Embeddings](#embeddings)
  - [Vector Store](#vector-store)
  - [Suggestions](#suggestions)
  - [Safety](#safety)
  - [Templates](#templates)
- [Daemon](#daemon)
  - [Daemon](#daemon-1)
  - [IPC](#ipc)
- [LLM Components](#llm-components)
  - [LLM Manager](#llm-manager)
  - [RAG Pipeline](#rag-pipeline)
  - [Command Explainer](#command-explainer)
  - [Command Generator](#command-generator)
  - [PEFT Trainer](#peft-trainer)
  - [Model Manager](#model-manager)
- [Utilities](#utilities)
  - [Configuration](#configuration)
  - [Logging](#logging)
  - [Dependencies](#dependencies)
  - [Backup](#backup)
- [CLI](#cli)

---

## Core Components

### Database

**Module**: `daedelus.core.database`

#### Class: `Database`

SQLite database with FTS5 full-text search for command history storage.

**Constructor**:
```python
Database(db_path: Path | str, timeout: float = 30.0)
```

**Parameters**:
- `db_path`: Path to SQLite database file
- `timeout`: Connection timeout in seconds (default: 30.0)

**Methods**:

##### `log_command()`
```python
def log_command(
    self,
    command: str,
    cwd: str,
    timestamp: Optional[int] = None,
    exit_code: Optional[int] = None,
    duration: Optional[float] = None,
    session_id: Optional[int] = None
) -> int
```

Log a command execution to the database.

**Parameters**:
- `command`: The command string that was executed
- `cwd`: Current working directory when command was run
- `timestamp`: Unix timestamp (default: current time)
- `exit_code`: Command exit code (0 for success)
- `duration`: Execution time in seconds
- `session_id`: Shell session ID

**Returns**: Row ID of inserted command

**Example**:
```python
db = Database("~/.local/share/daedelus/history.db")
row_id = db.log_command(
    command="git status",
    cwd="/home/user/project",
    exit_code=0,
    duration=0.15
)
```

##### `get_recent_commands()`
```python
def get_recent_commands(
    self,
    n: int = 100,
    cwd: Optional[str] = None,
    successful_only: bool = False
) -> List[Dict[str, Any]]
```

Retrieve recent commands from database.

**Parameters**:
- `n`: Number of commands to return
- `cwd`: Filter by directory (None for all)
- `successful_only`: Only return commands with exit_code=0

**Returns**: List of command dictionaries with keys:
  - `id`: Command ID
  - `command`: Command string
  - `cwd`: Working directory
  - `timestamp`: Unix timestamp
  - `exit_code`: Exit code
  - `duration`: Execution time

##### `search_commands()`
```python
def search_commands(
    self,
    query: str,
    max_results: int = 50
) -> List[Dict[str, Any]]
```

Full-text search using FTS5.

**Parameters**:
- `query`: Search query string
- `max_results`: Maximum results to return

**Returns**: List of matching commands

---

### Embeddings

**Module**: `daedelus.core.embeddings`

#### Class: `CommandEmbedder`

FastText-based command embedding generation.

**Constructor**:
```python
CommandEmbedder(
    model_path: Optional[Path] = None,
    embedding_dim: int = 128,
    min_count: int = 2
)
```

**Methods**:

##### `train()`
```python
def train(
    self,
    commands: List[str],
    model_path: Path,
    epochs: int = 5
) -> None
```

Train FastText model on command corpus.

**Parameters**:
- `commands`: List of command strings
- `model_path`: Where to save trained model
- `epochs`: Training epochs (default: 5)

**Raises**:
- `RuntimeError`: If training fails
- `ValueError`: If commands list is empty

##### `encode()`
```python
def encode(
    self,
    text: str,
    context: Optional[Dict[str, Any]] = None
) -> np.ndarray
```

Generate embedding vector for text.

**Parameters**:
- `text`: Text to encode (command, partial, etc.)
- `context`: Optional context (cwd, history, etc.)

**Returns**: 128-dimensional numpy array

**Example**:
```python
embedder = CommandEmbedder()
embedder.train(commands, Path("model.bin"))

vector = embedder.encode("git status")
# Returns: array([0.123, -0.456, ...], shape=(128,))
```

---

### Vector Store

**Module**: `daedelus.core.vector_store`

#### Class: `VectorStore`

Annoy-based approximate nearest neighbor search.

**Constructor**:
```python
VectorStore(
    index_path: Path,
    dimension: int = 128,
    n_trees: int = 10
)
```

**Methods**:

##### `add_item()`
```python
def add_item(
    self,
    item_id: int,
    vector: np.ndarray,
    metadata: Optional[Dict[str, Any]] = None
) -> None
```

Add vector to index.

**Parameters**:
- `item_id`: Unique identifier
- `vector`: Embedding vector
- `metadata`: Optional metadata (stored separately as JSON)

##### `build()`
```python
def build(self) -> None
```

Build the Annoy index. Must be called after adding all items before querying.

##### `query()`
```python
def query(
    self,
    vector: np.ndarray,
    k: int = 10,
    search_k: int = -1
) -> List[Tuple[int, float]]
```

Find k nearest neighbors.

**Parameters**:
- `vector`: Query vector
- `k`: Number of neighbors to return
- `search_k`: Search parameter (default: k * n_trees)

**Returns**: List of (item_id, distance) tuples

##### `is_built()`
```python
def is_built(self) -> bool
```

Check if index has been built and is ready for queries.

**Returns**: True if built, False otherwise

---

### Suggestions

**Module**: `daedelus.core.suggestions`

#### Class: `SuggestionEngine`

3-tier cascade suggestion system with advanced ranking.

**Constructor**:
```python
SuggestionEngine(
    database: Database,
    embedder: CommandEmbedder,
    vector_store: VectorStore,
    max_suggestions: int = 5,
    min_confidence: float = 0.3
)
```

**Methods**:

##### `suggest()`
```python
def suggest(
    self,
    partial: str,
    cwd: Optional[str] = None,
    history: Optional[List[str]] = None
) -> List[Dict[str, Any]]
```

Get command suggestions using 3-tier cascade.

**Parameters**:
- `partial`: Partial command input
- `cwd`: Current working directory
- `history`: Recent command history

**Returns**: List of suggestions with:
  - `command`: Suggested command
  - `confidence`: Confidence score (0-1)
  - `source`: "exact", "semantic", or "contextual"
  - `metadata`: Additional ranking info

**Algorithm**:
1. **Tier 1**: Exact prefix match (SQL LIKE)
2. **Tier 2**: Semantic similarity (embeddings + Annoy)
3. **Tier 3**: Contextual patterns (sequence analysis)

**Ranking Factors**:
- Recency: e^(-0.1 × days_since_use)
- Directory: 2.0x (same), 1.5x (parent/child), 1.0x (other)
- Success: (success_rate)^2
- Frequency: log(count + 1)

**Example**:
```python
suggestions = engine.suggest(
    partial="git co",
    cwd="/home/user/project",
    history=["git add .", "git status"]
)

for sug in suggestions:
    print(f"{sug['command']} (confidence: {sug['confidence']:.2f})")
```

---

### Safety

**Module**: `daedelus.core.safety`

#### Class: `SafetyAnalyzer`

Dangerous command pattern detection.

**Constructor**:
```python
SafetyAnalyzer(
    config: Optional[Dict[str, Any]] = None
)
```

**Methods**:

##### `check_command()`
```python
def check_command(
    self,
    command: str
) -> Dict[str, Any]
```

Analyze command for safety issues.

**Returns**:
```python
{
    "safe": bool,
    "level": "safe" | "warning" | "danger",
    "patterns": List[str],  # Matched dangerous patterns
    "explanation": str
}
```

**Dangerous Patterns**:
- `rm -rf /`
- `dd if=/dev/zero of=/dev/sd*`
- `mkfs.*`
- Fork bombs: `:(){ :|:& };:`
- More...

---

### Templates

**Module**: `daedelus.core.templates`

#### Class: `TemplateManager`

Jinja2-style command templates.

**Methods**:

##### `render_template()`
```python
def render_template(
    self,
    template: str,
    variables: Dict[str, str]
) -> str
```

Render template with variables.

**Example**:
```python
template = "git commit -m '{{message}}'"
rendered = manager.render_template(
    template,
    {"message": "Fix bug"}
)
# Returns: "git commit -m 'Fix bug'"
```

---

## Daemon

### Daemon

**Module**: `daedelus.daemon.daemon`

#### Class: `DaedalusDaemon`

Main daemon orchestrator.

**Constructor**:
```python
DaedalusDaemon(
    config_path: Optional[Path] = None
)
```

**Methods**:

##### `start()`
```python
def start(
    self,
    foreground: bool = False
) -> None
```

Start daemon (background or foreground).

##### `stop()`
```python
def stop(self) -> None
```

Gracefully stop daemon, saving state and updating models.

##### `status()`
```python
def status(self) -> Dict[str, Any]
```

Get daemon status.

**Returns**:
```python
{
    "running": bool,
    "uptime": int,  # seconds
    "commands_logged": int,
    "suggestions_served": int,
    "model_version": str,
    "memory_usage_mb": float
}
```

---

### IPC

**Module**: `daedelus.daemon.ipc`

#### Functions

##### `send_request()`
```python
def send_request(
    socket_path: Path,
    request_type: str,
    data: Dict[str, Any],
    timeout: float = 5.0
) -> Dict[str, Any]
```

Send IPC request to daemon.

**Request Types**:
- `SUGGEST`: Get suggestions
- `LOG_COMMAND`: Log command execution
- `COMPLETE`: Command completion
- `SEARCH`: Search history
- `PING`: Health check
- `STATUS`: Get status

**Example**:
```python
response = send_request(
    socket_path=Path("~/.local/share/daedelus/runtime/daemon.sock"),
    request_type="SUGGEST",
    data={
        "partial": "git co",
        "cwd": "/home/user/project"
    }
)
```

---

## LLM Components

### LLM Manager

**Module**: `daedelus.llm.llm_manager`

#### Class: `LLMManager`

llama.cpp integration for local LLM inference.

**Constructor**:
```python
LLMManager(
    model_path: Path,
    context_length: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.9
)
```

**Methods**:

##### `generate()`
```python
def generate(
    self,
    prompt: str,
    max_tokens: int = 100
) -> str
```

Generate completion from prompt.

**Parameters**:
- `prompt`: Input prompt
- `max_tokens`: Maximum tokens to generate

**Returns**: Generated text

##### `chat()`
```python
def chat(
    self,
    messages: List[Dict[str, str]]
) -> str
```

Chat interface with conversation history.

**Parameters**:
- `messages`: List of `{"role": "user"|"assistant", "content": str}`

**Returns**: Assistant's response

---

### RAG Pipeline

**Module**: `daedelus.llm.rag_pipeline`

#### Class: `RAGPipeline`

Retrieval-Augmented Generation for context injection.

**Methods**:

##### `retrieve_context()`
```python
def retrieve_context(
    self,
    query: str,
    cwd: Optional[str] = None,
    max_context: int = 10
) -> Dict[str, Any]
```

Retrieve relevant context from command history.

**Returns**:
```python
{
    "recent_commands": List[str],
    "similar_commands": List[str],
    "successful_patterns": List[str],
    "directory_context": Dict[str, Any]
}
```

##### `format_prompt()`
```python
def format_prompt(
    self,
    query: str,
    context: Dict[str, Any],
    template: str = "default"
) -> str
```

Format prompt with context for LLM.

---

### Command Explainer

**Module**: `daedelus.llm.command_explainer`

#### Class: `CommandExplainer`

Natural language command explanations.

**Methods**:

##### `explain()`
```python
def explain(
    self,
    command: str,
    detailed: bool = False
) -> str
```

Explain what a command does.

**Example**:
```python
explainer = CommandExplainer(llm, rag)
explanation = explainer.explain("tar -xzf archive.tar.gz")
# Returns: "Extracts files from a gzip-compressed tar archive"
```

##### `explain_error()`
```python
def explain_error(
    self,
    command: str,
    error_message: str
) -> Dict[str, str]
```

Explain command error and suggest fixes.

**Returns**:
```python
{
    "explanation": str,
    "likely_cause": str,
    "suggested_fix": str
}
```

---

### Command Generator

**Module**: `daedelus.llm.command_generator`

#### Class: `CommandGenerator`

Generate shell commands from natural language descriptions.

**Methods**:

##### `generate()`
```python
def generate(
    self,
    description: str,
    return_multiple: bool = False
) -> Union[str, List[str]]
```

Generate command(s) from description.

**Example**:
```python
generator = CommandGenerator(llm, rag)
cmd = generator.generate("find all python files")
# Returns: "find . -name '*.py'"

alternatives = generator.generate(
    "compress folder",
    return_multiple=True
)
# Returns: ["tar -czf archive.tar.gz folder/", "zip -r archive.zip folder/", ...]
```

---

### PEFT Trainer

**Module**: `daedelus.llm.peft_trainer`

#### Class: `PEFTTrainer`

LoRA fine-tuning for model personalization.

**Methods**:

##### `train_adapter()`
```python
def train_adapter(
    self,
    training_data: List[str],
    adapter_path: Path,
    num_epochs: int = 3,
    batch_size: int = 4
) -> Dict[str, Any]
```

Train LoRA adapter on user's command patterns.

**Returns**: Training metrics (loss, global_step, etc.)

##### `export_adapter_to_gguf()`
```python
def export_adapter_to_gguf(
    self,
    adapter_path: Path,
    output_path: Path,
    quantization: str = "q4_k_m"
) -> Path
```

Export trained adapter to GGUF format for llama.cpp.

**Parameters**:
- `adapter_path`: Path to trained LoRA adapter
- `output_path`: Output GGUF file path
- `quantization`: Quantization level (q4_k_m, q8_0, f16, etc.)

**Returns**: Path to exported GGUF file

---

### Model Manager

**Module**: `daedelus.llm.model_manager`

#### Class: `ModelManager`

Model versioning and evolution.

**Methods**:

##### `download_model()`
```python
def download_model(
    self,
    model_id: str = "microsoft/Phi-3-mini-4k-instruct-gguf",
    filename: str = "Phi-3-mini-4k-instruct-q4.gguf"
) -> Path
```

Download model from HuggingFace.

##### `forge_new_version()`
```python
def forge_new_version(
    self,
    adapter_path: Path,
    quantization: str = "q4_k_m"
) -> Path
```

Create new model version by merging adapter.

**Process**:
1. Load base model
2. Load LoRA adapter
3. Merge weights using `PeftModel.merge_and_unload()`
4. Convert to GGUF
5. Quantize
6. Save as `daedelus_v{n+1}.gguf`

**Returns**: Path to new model version

##### `get_lineage()`
```python
def get_lineage(
    self,
    version: str
) -> List[Dict[str, Any]]
```

Get model version lineage.

**Returns**: List of version metadata showing evolution history

---

## Utilities

### Configuration

**Module**: `daedelus.utils.config`

#### Class: `Config`

YAML configuration management.

**Methods**:

##### `get()`
```python
def get(
    self,
    key: str,
    default: Any = None
) -> Any
```

Get config value using dot notation.

**Example**:
```python
config = Config()
max_suggestions = config.get("suggestions.max_suggestions", 5)
llm_enabled = config.get("llm.enabled", False)
```

##### `set()`
```python
def set(
    self,
    key: str,
    value: Any
) -> None
```

Set config value.

##### `save()`
```python
def save(self) -> None
```

Save config to YAML file.

---

### Logging

**Module**: `daedelus.utils.logging_config`

#### Functions

##### `setup_logging()`
```python
def setup_logging(
    log_path: Optional[Path] = None,
    level: str = "INFO",
    console: bool = True
) -> logging.Logger
```

Configure logging with colored output and file rotation.

**Parameters**:
- `log_path`: Path to log file (None for console only)
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `console`: Enable colored console output

---

### Dependencies

**Module**: `daedelus.utils.dependencies`

#### Functions

##### `check_dependencies()`
```python
def check_dependencies() -> Dict[str, bool]
```

Check which optional dependencies are available.

**Returns**:
```python
{
    "fasttext": bool,
    "annoy": bool,
    "llama_cpp": bool,
    "transformers": bool,
    "peft": bool
}
```

---

### Backup

**Module**: `daedelus.utils.backup`

#### Functions

##### `create_backup()`
```python
def create_backup(
    data_dir: Path,
    backup_dir: Path
) -> Path
```

Create compressed backup of data directory.

**Returns**: Path to backup file

##### `restore_backup()`
```python
def restore_backup(
    backup_path: Path,
    data_dir: Path,
    create_safety_backup: bool = True
) -> None
```

Restore from backup file.

---

## CLI

**Module**: `daedelus.cli.main`

### Commands

All commands are accessed via the `daedelus` command-line tool.

#### `setup`
```bash
daedelus setup
```

First-time setup (creates config, directories).

#### `start`
```bash
daedelus start [--foreground]
```

Start daemon (background or foreground mode).

#### `stop`
```bash
daedelus stop
```

Stop daemon gracefully.

#### `status`
```bash
daedelus status [--json]
```

Show daemon status.

#### `search`
```bash
daedelus search <query>
```

Search command history.

#### `explain` (Phase 2)
```bash
daedelus explain "<command>"
```

Explain what a command does.

#### `generate` (Phase 2)
```bash
daedelus generate "<description>"
```

Generate command from description.

#### `model` (Phase 2)
```bash
daedelus model download
daedelus model status
daedelus model versions
daedelus model rollback <version>
```

Model management commands.

---

## Type Definitions

### Common Types

```python
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import numpy as np

# Command record from database
CommandRecord = Dict[str, Any]  # {id, command, cwd, timestamp, exit_code, duration}

# Suggestion result
Suggestion = Dict[str, Any]  # {command, confidence, source, metadata}

# Safety check result
SafetyResult = Dict[str, Any]  # {safe, level, patterns, explanation}

# Model metadata
ModelMetadata = Dict[str, Any]  # {version, parent, base_model, training_sessions, sha256, created}
```

---

## Error Handling

### Common Exceptions

All Daedalus modules may raise:
- `RuntimeError`: For operational failures
- `ValueError`: For invalid parameters
- `FileNotFoundError`: For missing files
- `ConnectionError`: For IPC failures (daemon not running)

**Example Error Handling**:
```python
try:
    suggestions = engine.suggest("git co")
except RuntimeError as e:
    logger.error(f"Suggestion engine failed: {e}")
    # Fallback to basic completion
except ConnectionError:
    logger.error("Daemon not running")
    # Prompt user to start daemon
```

---

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Typical Time |
|-----------|------------|--------------|
| Database insert | O(1) | <1ms |
| Database query (recent) | O(n) | <5ms |
| FTS5 search | O(log n) | <10ms |
| Embedding encode | O(k) | <1ms |
| Vector search | O(log n) | <10ms |
| Suggestion (total) | O(n + log n) | <30ms |
| LLM inference | O(tokens) | 50-200ms |

Where:
- n = number of commands in database
- k = command length
- tokens = generated token count

### Memory Usage

| Component | Memory |
|-----------|--------|
| Database connection | ~10MB |
| Embeddings model | ~30MB |
| Vector index (1M items) | ~100MB |
| LLM model (Q4) | ~2.4GB |
| Total (Phase 1 only) | ~50MB |
| Total (Phase 1+2) | ~3GB |

---

## Thread Safety

- **Database**: Thread-safe (SQLite with timeout)
- **Embeddings**: Thread-safe after training
- **Vector Store**: Read-only after build (thread-safe)
- **LLM**: Not thread-safe (use locks for concurrent access)
- **Daemon**: Single-threaded event loop

---

## Version Compatibility

This API reference is for **Daedalus v0.2.0**.

**Breaking Changes**:
- v0.1.0 → v0.2.0: Added Phase 2 LLM components (backwards compatible)

**Deprecations**: None in v0.2.0

---

**For more information**:
- [Architecture Overview](ARCHITECTURE.md)
- [Development Guide](DEVELOPMENT.md)
- [Troubleshooting](TROUBLESHOOTING.md)

**Created by [orpheus497](https://github.com/orpheus497)**
