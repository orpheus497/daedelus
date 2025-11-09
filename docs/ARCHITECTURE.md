# Daedalus Architecture

**Version**: 0.2.0
**Last Updated**: 2025-11-09

This document provides a comprehensive architectural overview of Daedalus.

---

## Table of Contents

- [System Overview](#system-overview)
- [Design Principles](#design-principles)
- [High-Level Architecture](#high-level-architecture)
- [Phase 1: Embedding-Based System](#phase-1-embedding-based-system)
- [Phase 2: LLM Enhancement](#phase-2-llm-enhancement)
- [Data Flow](#data-flow)
- [Component Interactions](#component-interactions)
- [Storage Architecture](#storage-architecture)
- [Deployment Architecture](#deployment-architecture)
- [Security Architecture](#security-architecture)
- [Performance Architecture](#performance-architecture)

---

## System Overview

Daedalus is a **self-learning terminal assistant** that combines fast embedding-based suggestions with optional LLM enhancement for natural language understanding.

### Key Characteristics

- **Hybrid Intelligence**: Fast Phase 1 (<30ms) + powerful Phase 2 (50-200ms)
- **Privacy-First**: 100% local processing, no external APIs
- **Self-Learning**: Continuously improves from user patterns
- **FOSS**: All dependencies use permissive licenses
- **Production-Ready**: 179+ tests, 80%+ coverage, CI/CD

---

## Design Principles

### 1. Privacy is Non-Negotiable

**All processing must be local. Zero external API calls.**

- No telemetry
- No cloud services
- No data leaves the machine
- Configurable privacy filters

**Implementation**:
- Unix domain sockets (not TCP)
- Local SQLite database
- Local model inference
- Encrypted storage for sensitive patterns

### 2. Performance First

**Response time must feel instant.**

**Targets** (all exceeded):
- Suggestions: <50ms (achieved: 10-30ms)
- Memory: <100MB Phase 1 (achieved: ~50MB)
- Startup: <500ms (achieved: ~200ms)

**Strategies**:
- Memory-mapped indexes
- Lazy loading
- Caching
- Efficient data structures (Annoy, SQLite indexes)

### 3. Graceful Degradation

**System must work even if components fail.**

- Phase 2 unavailable → fallback to Phase 1
- LLM dependencies missing → Phase 1 only
- Model training fails → continue with existing model
- Network down → always works (local-first)

### 4. Type Safety

**All code uses comprehensive type hints.**

- Catch bugs at development time
- Better IDE support
- Self-documenting code
- mypy strict mode compliance

### 5. FOSS Compliance

**Only permissive licenses (MIT/Apache/BSD).**

- Enables commercial use
- No GPL restrictions
- Community-friendly
- Long-term sustainability

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     User Shell                          │
│              (ZSH / Bash / Fish)                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Unix Socket IPC
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 Daedalus Daemon                         │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │         Privacy Filtering Layer                   │ │
│  │  (Excluded paths, patterns, ReDoS protection)     │ │
│  └───────────────────────────────────────────────────┘ │
│                     │                                   │
│  ┌──────────────────┴────────────────┐                 │
│  │                                   │                 │
│  ▼                                   ▼                 │
│ ┌──────────────┐           ┌────────────────┐          │
│ │  Phase 1     │           │   Phase 2      │          │
│ │  (Always On) │           │  (Optional)    │          │
│ └──────────────┘           └────────────────┘          │
│                                                         │
│  Phase 1 Components:        Phase 2 Components:        │
│  • SQLite + FTS5           • llama.cpp                 │
│  • FastText Embeddings     • Phi-3-mini                │
│  • Annoy Vector Store      • RAG Pipeline              │
│  • 3-Tier Suggestions      • PEFT/LoRA                 │
│  • Safety Analysis         • Model Manager             │
│                                                         │
└─────────────────────────────────────────────────────────┘
                     │
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               Persistent Storage                        │
│                                                         │
│  ~/.local/share/daedelus/                              │
│  ├── history.db (SQLite)                               │
│  ├── embeddings.bin (FastText model)                   │
│  ├── commands.ann (Annoy index)                        │
│  ├── commands.meta (JSON metadata)                     │
│  └── llm/ (Phase 2)                                    │
│      ├── Phi-3-mini-*.gguf (base model)                │
│      ├── daedelus_v1.gguf (initial)                    │
│      ├── daedelus_v2.gguf (fine-tuned)                 │
│      └── adapter/ (LoRA weights)                       │
│                                                         │
│  ~/.config/daedelus/                                   │
│  └── config.yaml (user configuration)                  │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 1: Embedding-Based System

### Architecture

```
                      Suggestion Request
                            │
                            ▼
                    ┌───────────────┐
                    │  Suggestion   │
                    │    Engine     │
                    │  (3 Tiers)    │
                    └───────┬───────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
    ┌───────┐         ┌──────────┐       ┌──────────┐
    │ Tier 1│         │  Tier 2  │       │  Tier 3  │
    │ Exact │         │ Semantic │       │Contextual│
    └───┬───┘         └────┬─────┘       └────┬─────┘
        │                  │                   │
        ▼                  ▼                   ▼
    ┌───────┐      ┌──────────────┐    ┌──────────┐
    │SQLite │      │FastText      │    │ Pattern  │
    │  FTS5 │      │+ Annoy       │    │ Analysis │
    │       │      │Vector Search │    │          │
    └───────┘      └──────────────┘    └──────────┘
        │                  │                   │
        └─────────┬────────┴──────────┬────────┘
                  │                   │
                  ▼                   ▼
            ┌──────────┐        ┌──────────┐
            │ Ranking  │        │ Metadata │
            │ Algorithm│        │ Enriching│
            └────┬─────┘        └────┬─────┘
                 │                   │
                 └─────────┬─────────┘
                           ▼
                    Ranked Suggestions
```

### Components

#### 1. Database Layer

**Technology**: SQLite with FTS5

**Schema**:
```sql
-- Command history
CREATE TABLE commands (
    id INTEGER PRIMARY KEY,
    command TEXT NOT NULL,
    cwd TEXT,
    timestamp INTEGER,
    exit_code INTEGER,
    duration REAL,
    session_id INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Full-text search
CREATE VIRTUAL TABLE commands_fts USING fts5(
    command,
    content=commands,
    content_rowid=id
);

-- Sessions
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    start_time INTEGER,
    end_time INTEGER,
    command_count INTEGER
);

-- Pattern statistics
CREATE TABLE pattern_stats (
    pattern TEXT PRIMARY KEY,
    count INTEGER,
    last_used INTEGER,
    success_rate REAL
);

-- Indexes
CREATE INDEX idx_commands_cwd ON commands(cwd);
CREATE INDEX idx_commands_timestamp ON commands(timestamp);
CREATE INDEX idx_commands_session ON commands(session_id);
```

**Performance**:
- Inserts: <1ms
- FTS5 queries: <10ms
- Index scans: <5ms

#### 2. Embedding Layer

**Technology**: FastText (subword-aware)

**Architecture**:
```
Input Command → Tokenization → Subword Vectors → Aggregation → 128D Vector
                                                                      │
                                                                      ▼
                                                            Memory-Mapped Model
                                                                 (~30MB)
```

**Training**:
- Model: Skipgram (better for rare words)
- Dimension: 128 (balance quality/size)
- Min count: 2 (filters noise)
- Epochs: 5
- Training time: <30s for 10K commands

**Advantages**:
- Handles typos (subword-aware)
- Small model size
- Fast inference (~1ms)
- Doesn't require large corpus

#### 3. Vector Store

**Technology**: Spotify Annoy (Approximate Nearest Neighbors)

**Architecture**:
```
Vectors → Build Index → N Trees → Memory-Mapped File
          (10 trees)              (~100MB for 1M items)
                                           │
                                           ▼
                                  Query: <10ms for k=10
```

**Configuration**:
- Trees: 10 (balanced build/query time)
- Metric: Angular distance
- Search k: k * n_trees (quality/speed tradeoff)

**Trade-offs**:
- Build time: O(n log n) ~ 1 min for 100K
- Query time: O(log n) ~ <10ms for 1M
- Memory: Memory-mapped (minimal RAM)
- Accuracy: ~95% recall vs brute force

#### 4. Suggestion Engine

**3-Tier Cascade**:

**Tier 1: Exact Prefix Match**
```sql
SELECT command, COUNT(*) as freq
FROM commands
WHERE command LIKE ?||'%'
GROUP BY command
ORDER BY freq DESC, timestamp DESC
LIMIT ?;
```
- Time: <5ms
- Recall: ~20% (only exact prefixes)
- Precision: 100% (exact matches)

**Tier 2: Semantic Similarity**
```python
# Encode partial input
vector = embedder.encode(partial)

# Query vector store
neighbors = vector_store.query(vector, k=20)

# Fetch commands from database
commands = [db.get_command(id) for id, dist in neighbors]
```
- Time: <20ms
- Recall: ~70% (semantic similarity)
- Precision: ~80% (may include false positives)

**Tier 3: Contextual Patterns**
```python
# Analyze command sequences
recent = history[-10:]
patterns = find_sequences(recent, partial)

# Score by co-occurrence
scores = score_by_context(patterns, cwd)
```
- Time: <30ms
- Recall: ~10% (rare patterns)
- Precision: ~90% (context-specific)

**Ranking Algorithm**:
```python
def rank_suggestion(cmd, context):
    # Base confidence from tier
    base = tier_confidence(cmd.tier)

    # Recency factor (exponential decay)
    days_since = (now - cmd.last_used) / 86400
    recency = exp(-0.1 * days_since)

    # Directory relevance
    if cmd.cwd == context.cwd:
        directory = 2.0  # Same directory
    elif is_parent_child(cmd.cwd, context.cwd):
        directory = 1.5  # Parent/child
    else:
        directory = 1.0  # Other

    # Success rate (quadratic penalty for failures)
    success = cmd.success_rate ** 2

    # Frequency (logarithmic diminishing returns)
    frequency = log(cmd.count + 1)

    # Combined score
    return base * recency * directory * success * frequency
```

---

## Phase 2: LLM Enhancement

### Architecture

```
                Natural Language Query
                         │
                         ▼
                ┌────────────────┐
                │  NL Detection  │
                │   (heuristic)  │
                └────────┬───────┘
                         │
                 ┌───────┴──────┐
                 │              │
                 ▼              ▼
         ┌──────────┐    ┌──────────┐
         │ Phase 1  │    │ Phase 2  │
         │  (Fast)  │    │  (LLM)   │
         └──────────┘    └────┬─────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
            ┌──────────────┐    ┌─────────────┐
            │ RAG Pipeline │    │ LLM Manager │
            │(Context Retr)│    │ (llama.cpp) │
            └──────┬───────┘    └──────┬──────┘
                   │                   │
                   │   ┌───────────────┘
                   │   │
                   ▼   ▼
            ┌──────────────┐
            │   Phi-3-mini │
            │  (Q4 Quant)  │
            │   ~2.4GB     │
            └──────────────┘
```

### Components

#### 1. LLM Manager

**Technology**: llama.cpp (CPU inference)

**Architecture**:
```
┌─────────────────────────────────────┐
│ llama.cpp Python bindings           │
├─────────────────────────────────────┤
│ Model Loading                       │
│ • Memory mapping (mmap)             │
│ • Quantization support (Q4_K_M)     │
│ • Context management (2048 tokens)  │
├─────────────────────────────────────┤
│ Inference Engine                    │
│ • Tokenization                      │
│ • Attention computation             │
│ • Sampling (top_p, temperature)     │
├─────────────────────────────────────┤
│ Output                              │
│ • Generated text                    │
│ • Token probabilities               │
└─────────────────────────────────────┘
```

**Performance**:
- Model: Phi-3-mini (3.8B params)
- Quantization: Q4_K_M (~2.4GB)
- Context: 2048 tokens
- Inference: 50-200ms on CPU, 10-50ms on GPU

#### 2. RAG Pipeline

**Retrieval Strategy**:
```
Query → [Recent Commands] + [Similar Commands] + [Successful Patterns]
           (last 5 in CWD)   (embedding search)    (high success rate)
                                      │
                                      ▼
                              Context Assembly
                                      │
                                      ▼
                              Prompt Formatting
                                      │
                                      ▼
                                   LLM Input
```

**Prompt Template**:
```
You are Daedalus, a terminal command assistant.

User's Environment:
- Current directory: {cwd}
- Recent commands: {recent_commands}
- Command style: {user_patterns}

User's Query: {query}

Provide a shell command that accomplishes this task.
Command:
```

#### 3. PEFT/LoRA Training

**Architecture**:
```
┌──────────────────────────────┐
│  Base Model (Phi-3-mini)     │
│  (Frozen Weights)            │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  LoRA Adapters               │
│  • q_proj: r=8, α=32         │
│  • k_proj: r=8, α=32         │
│  • v_proj: r=8, α=32         │
│  (~20MB trainable params)    │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Training Loop               │
│  • HuggingFace Trainer       │
│  • AdamW optimizer           │
│  • Gradient accumulation     │
│  • Mixed precision (fp16)    │
│  • 3 epochs, batch_size=4    │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Adapter Export              │
│  • merge_and_unload()        │
│  • Convert to GGUF           │
│  • Quantize (Q4_K_M)         │
└──────────────────────────────┘
```

**Training Trigger**: Daemon shutdown + minimum 100 new commands

#### 4. Model Evolution

**Version Lineage**:
```
Phi-3-mini-4k-instruct (base)
        │
        ▼
    daedelus_v1.gguf (initial conversion)
        │
        │ + User's 1st batch (1000 commands)
        ▼
    daedelus_v2.gguf (fine-tuned)
        │
        │ + User's 2nd batch (500 commands)
        ▼
    daedelus_v3.gguf (further fine-tuned)
        │
        ▼
       ...
```

**Metadata Tracking**:
```json
{
  "version": "daedelus_v3",
  "parent": "daedelus_v2",
  "base_model": "microsoft/Phi-3-mini-4k-instruct",
  "training_sessions": [
    {"session": 1, "commands": 1000, "date": "2025-11-10"},
    {"session": 2, "commands": 500, "date": "2025-11-15"}
  ],
  "sha256": "abc123...",
  "created": "2025-11-15T14:30:00Z"
}
```

---

## Data Flow

### Command Execution Flow

```
1. User Types Command
   │
   ▼
2. Shell Hook Captures
   │
   ▼
3. IPC Message → Daemon
   │
   ▼
4. Privacy Filter Check
   │
   ├─ Excluded? → Skip logging
   │
   └─ Safe? → Continue
      │
      ▼
5. Log to SQLite
   │
   ▼
6. Update Statistics
   │
   ▼
7. Queue for Embedding
   (batch update)
```

### Suggestion Flow

```
1. User Presses Ctrl+Space
   │
   ▼
2. Shell Sends IPC Request
   │
   ▼
3. Daemon Receives
   │
   ├─ NL Query? → Phase 2 Path
   │   │
   │   ├─ RAG: Retrieve Context
   │   ├─ LLM: Generate Command
   │   └─ Fallback to Phase 1 if fails
   │
   └─ Command Partial? → Phase 1 Path
       │
       ├─ Tier 1: Exact Match (SQL)
       ├─ Tier 2: Semantic (Embeddings)
       ├─ Tier 3: Contextual (Patterns)
       │
       └─ Rank & Merge
           │
           ▼
4. Return Suggestions
   │
   ▼
5. Shell Displays
```

### Training Flow

```
1. Daemon Shutdown Signal
   │
   ▼
2. Check: New Commands >= Threshold?
   │
   ├─ No → Skip training
   │
   └─ Yes → Continue
       │
       ▼
3. Phase 1 Training
   │
   ├─ Retrain FastText
   ├─ Rebuild Annoy Index
   └─ Update Statistics
       │
       ▼
4. Phase 2 Training (if enabled)
   │
   ├─ Prepare Training Data
   ├─ Fine-Tune LoRA Adapter
   ├─ Merge Adapter
   ├─ Export to GGUF
   └─ Update Version Metadata
       │
       ▼
5. Save All Models
   │
   ▼
6. Shutdown Complete
```

---

## Component Interactions

### Startup Sequence

```
1. Load Configuration
   │
   ▼
2. Initialize Logging
   │
   ▼
3. Check Dependencies
   │
   ├─ FastText available?
   ├─ Annoy available?
   └─ llama-cpp-python available? (Phase 2)
       │
       ▼
4. Load Database
   │
   ├─ Open SQLite connection
   └─ Initialize schema if needed
       │
       ▼
5. Load Phase 1 Models
   │
   ├─ Load FastText embeddings
   └─ Load Annoy index
       │
       ▼
6. Load Phase 2 Models (if enabled)
   │
   ├─ Load Phi-3-mini GGUF
   ├─ Initialize RAG pipeline
   └─ Load latest daedelus_vN model
       │
       ▼
7. Start IPC Server
   │
   ├─ Create Unix socket
   └─ Listen for connections
       │
       ▼
8. Enter Event Loop
```

**Total Startup Time**: ~200ms (Phase 1 only), ~3-5s (Phase 1+2)

### Shutdown Sequence

```
1. Receive SIGTERM/SIGINT
   │
   ▼
2. Set running=False
   │
   ▼
3. Wait for Current Requests
   │
   ▼
4. Close IPC Socket
   │
   ▼
5. Update Models (if threshold met)
   │
   ├─ Phase 1: Retrain embeddings
   └─ Phase 2: Fine-tune LLM
       │
       ▼
6. Save State
   │
   ├─ Flush database
   └─ Close connections
       │
       ▼
7. Exit Gracefully
```

**Total Shutdown Time**: ~100ms (no training), ~5-10min (with training)

---

## Storage Architecture

### File Layout

```
~/.local/share/daedelus/
├── runtime/
│   └── daemon.sock              # Unix socket (ephemeral)
├── history.db                   # SQLite database
├── history.db-wal               # Write-ahead log
├── history.db-shm               # Shared memory
├── embeddings.bin               # FastText model (~30MB)
├── commands.ann                 # Annoy index (~100MB for 1M)
├── commands.meta                # JSON metadata
├── daemon.log                   # Rotating log files
├── daemon.log.1
├── daemon.log.2
├── backups/
│   ├── daedelus_backup_20251109_143000.tar.gz
│   └── ...
└── llm/                         # Phase 2 only
    ├── Phi-3-mini-4k-instruct-q4.gguf  # Base model (~2.4GB)
    ├── daedelus_v1.gguf         # Initial version (~2.4GB)
    ├── daedelus_v2.gguf         # After training (~2.4GB)
    ├── daedelus_v3.gguf         # After more training (~2.4GB)
    ├── adapter_v2/              # LoRA weights (~20MB)
    │   ├── adapter_config.json
    │   ├── adapter_model.bin
    │   └── training_metrics.json
    └── metadata/
        ├── v1.json
        ├── v2.json
        └── v3.json

~/.config/daedelus/
└── config.yaml                  # User configuration
```

### Disk Usage

| Component | Size |
|-----------|------|
| SQLite DB (1M commands) | ~500MB |
| FastText model | ~30MB |
| Annoy index (1M vectors) | ~100MB |
| Logs (with rotation) | ~50MB |
| **Phase 1 Total** | **~680MB** |
| Phi-3-mini base | ~2.4GB |
| Daedelus models (3 versions) | ~7.2GB |
| LoRA adapters | ~60MB |
| **Phase 2 Total** | **~9.7GB** |
| **Overall Max** | **~10.4GB** |

### Backup Strategy

- **Frequency**: Daily (configurable)
- **Retention**: Keep last 7 backups
- **Compression**: gzip (~80% reduction)
- **Scope**: Database, embeddings, config (not LLM models)

---

## Deployment Architecture

### Systemd Integration

```
daedelus.service
    ├── Type: simple
    ├── User: %u (current user)
    ├── ExecStart: /path/to/daedelus start --foreground
    ├── Restart: on-failure
    ├── RestartSec: 10s
    └── Security Hardening:
        ├── PrivateTmp=true
        ├── ProtectSystem=strict
        ├── ProtectHome=read-only
        ├── NoNewPrivileges=true
        └── MemoryMax=4G (with LLM)
```

### Resource Limits

**Phase 1 Only**:
- CPU: <5% idle, <50% active
- Memory: ~50MB idle, ~200MB active
- Disk I/O: Minimal (mostly reads)
- Network: None

**Phase 1+2**:
- CPU: <5% idle, 30-80% during LLM inference
- Memory: ~3GB idle, ~4GB active
- Disk I/O: Moderate (model loading)
- Network: None (all local)

---

## Security Architecture

### Threat Model

**In Scope**:
- Local privilege escalation
- Code injection via commands
- Data exfiltration
- Denial of service

**Out of Scope**:
- Physical access attacks
- Kernel exploits
- Hardware attacks

### Security Measures

#### 1. Privacy Filtering

```python
# Excluded paths
EXCLUDED_PATHS = [
    "~/.ssh", "~/.gnupg", "~/.password-store",
    "~/.aws", "~/.kube", ...
]

# Excluded patterns (regex)
EXCLUDED_PATTERNS = [
    r"password", r"token", r"secret",
    r"api[_-]?key", r"[A-Z0-9]{32,}", ...  # Likely keys
]
```

#### 2. ReDoS Protection

```python
def validate_regex(pattern: str) -> bool:
    # Max length check
    if len(pattern) > 1000:
        return False

    # Count repetition operators
    repetitions = pattern.count('*') + pattern.count('+')
    if repetitions > 10:
        return False

    return True
```

#### 3. Command Safety Analysis

Detects dangerous patterns:
- Destructive commands (`rm -rf /`, `mkfs.*`)
- Fork bombs (`:(){ :|:& };:`)
- Overwrite devices (`dd of=/dev/sd*`)

#### 4. IPC Security

- Unix domain sockets (no network exposure)
- File permissions: 0600 (owner only)
- Timeout protection (5s max)
- Message size limits (1MB)

#### 5. Data Security

- SQLite with timeout (prevents locks)
- JSON metadata (no pickle - code execution risk)
- Encrypted storage for sensitive patterns (future)

---

## Performance Architecture

### Optimization Strategies

#### 1. Lazy Loading

```python
class Daemon:
    def __init__(self):
        self.db = Database()  # Load immediately
        self._embedder = None  # Lazy
        self._vector_store = None  # Lazy
        self._llm = None  # Lazy

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = load_embedder()
        return self._embedder
```

#### 2. Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def encode_command(command: str) -> np.ndarray:
    return embedder.encode(command)
```

#### 3. Memory Mapping

- Annoy index: mmap (100MB on disk, <10MB RAM)
- FastText model: mmap (30MB on disk, minimal RAM)
- SQLite: OS page cache

#### 4. Batch Processing

```python
# Don't update index after every command
command_queue = []

def log_command(cmd):
    db.insert(cmd)
    command_queue.append(cmd)

    if len(command_queue) >= BATCH_SIZE:
        update_models(command_queue)
        command_queue.clear()
```

#### 5. Parallel Processing

```python
with ThreadPoolExecutor() as executor:
    # Run tiers in parallel
    tier1 = executor.submit(exact_match, partial)
    tier2 = executor.submit(semantic_search, partial)
    tier3 = executor.submit(contextual_patterns, partial)

    results = tier1.result() + tier2.result() + tier3.result()
```

### Performance Monitoring

**Metrics Tracked**:
- Suggestion latency (p50, p95, p99)
- Database query time
- Embedding encoding time
- Vector search time
- LLM inference time
- Memory usage
- Disk I/O

**Logging**:
```python
logger.info(
    "Suggestion served",
    extra={
        "latency_ms": 15.3,
        "tier": "semantic",
        "result_count": 5
    }
)
```

---

## Architectural Decisions

For detailed rationale behind architectural choices, see:

- [ADR-001: Hybrid Phase 1 + Phase 2](.devdocs/DECISIONS_LOG.md#adr-001)
- [ADR-002: Privacy-First Design](.devdocs/DECISIONS_LOG.md#adr-002)
- [ADR-011: Daemon Architecture](.devdocs/DECISIONS_LOG.md#adr-011)
- [ADR-012: 3-Tier Suggestion Cascade](.devdocs/DECISIONS_LOG.md#adr-012)

All 25 ADRs are documented in `.devdocs/DECISIONS_LOG.md`.

---

## Future Architecture (Phase 3)

### Planned Enhancements

1. **Plugin System**:
   - Sandboxed execution
   - Plugin API
   - Dynamic loading

2. **Distributed Mode**:
   - Optional cloud sync (E2E encrypted)
   - Team sharing
   - Multi-device support

3. **Advanced Analytics**:
   - Command flow analysis
   - Productivity metrics
   - Anomaly detection

---

**For more information**:
- [API Reference](API.md)
- [Development Guide](DEVELOPMENT.md)
- [Troubleshooting](TROUBLESHOOTING.md)

**Created by [orpheus497](https://github.com/orpheus497)**
