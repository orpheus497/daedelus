# DAEDELUS IMPLEMENTATION GUIDE
## Quick Start for Developers

**Project:** Daedelus - Self-Learning Terminal Assistant  
**Architecture:** Unified System Design  
**Timeline:** 17 weeks to MVP

---

## PHASE 1: FOUNDATION (Weeks 1-2)

### Week 1: Project Setup

**Day 1-2: Repository & Infrastructure**
```bash
# Initialize project
mkdir daedelus && cd daedelus
git init
python -m venv venv
source venv/bin/activate

# Project structure
mkdir -p daedelus/{daemon,model,vector,ipc,cli}
mkdir -p tests/{unit,integration,performance}
mkdir -p plugins/{zsh,bash,fish}
mkdir -p docs
```

**Create pyproject.toml:**
```toml
[project]
name = "daedelus"
version = "0.1.0"
description = "Self-learning terminal assistant"
authors = [{name = "Your Name", email = "your@email.com"}]
license = {text = "MIT"}
requires-python = ">=3.11"
dependencies = [
    "fasttext-wheel>=0.9.2",
    "numpy>=1.24.0",
    "annoy>=1.17.0",
    "click>=8.1.0",
    "pyyaml>=6.0",
    "ptyprocess>=0.7.0",
    "python-daemon>=3.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]

[project.scripts]
daedelus = "daedelus.cli:main"

[build-system]
requires = ["setuptools>=65.0", "wheel"]
build-backend = "setuptools.build_meta"
```

**Day 3-4: Core Module Structure**
```python
# daedelus/__init__.py
"""
Daedelus: Self-learning terminal assistant
"""
__version__ = "0.1.0"

from .daemon import DaedelusDaemon
from .model import CommandEmbedder
from .vector import VectorStore

__all__ = ["DaedelusDaemon", "CommandEmbedder", "VectorStore"]
```

**Day 5-7: Configuration System**
```python
# daedelus/config.py
from pathlib import Path
import yaml

DEFAULT_CONFIG = {
    'daemon': {
        'socket_path': '~/.daedelus/daemon.sock',
        'log_path': '~/.daedelus/daemon.log',
        'pid_path': '~/.daedelus/daemon.pid',
    },
    'model': {
        'embedding_dim': 128,
        'vocab_size': 50000,
        'model_path': '~/.daedelus/model.bin',
    },
    'vector_store': {
        'index_type': 'annoy',
        'index_path': '~/.daedelus/index',
        'n_trees': 10,
    },
    'database': {
        'path': '~/.daedelus/history.db',
    },
    'privacy': {
        'excluded_paths': ['~/.ssh', '~/.gnupg'],
        'excluded_patterns': ['password', 'token', 'secret'],
        'history_retention_days': 90,
    }
}

class Config:
    def __init__(self, config_path='~/.daedelus/config.yaml'):
        self.config_path = Path(config_path).expanduser()
        self.config = self._load_config()
    
    def _load_config(self):
        if self.config_path.exists():
            with open(self.config_path) as f:
                user_config = yaml.safe_load(f)
            return {**DEFAULT_CONFIG, **user_config}
        return DEFAULT_CONFIG
    
    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f)
```

### Week 2: Database & Logging

**Day 1-3: SQLite Schema**
```python
# daedelus/database.py
import sqlite3
from pathlib import Path
from datetime import datetime

class CommandDatabase:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        command TEXT NOT NULL,
        cwd TEXT NOT NULL,
        exit_code INTEGER NOT NULL,
        duration REAL,
        output_length INTEGER,
        session_id TEXT NOT NULL
    );
    
    CREATE INDEX IF NOT EXISTS idx_timestamp ON commands(timestamp);
    CREATE INDEX IF NOT EXISTS idx_command ON commands(command);
    CREATE INDEX IF NOT EXISTS idx_session ON commands(session_id);
    
    CREATE VIRTUAL TABLE IF NOT EXISTS command_fts USING fts5(
        command,
        content='commands',
        content_rowid='id'
    );
    """
    
    def __init__(self, db_path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._init_schema()
    
    def _init_schema(self):
        self.conn.executescript(self.SCHEMA)
        self.conn.commit()
    
    def insert_command(self, command, cwd, exit_code, duration, session_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO commands 
            (timestamp, command, cwd, exit_code, duration, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().timestamp(),
            command,
            cwd,
            exit_code,
            duration,
            session_id
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_recent_commands(self, n=100):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM commands 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (n,))
        return cursor.fetchall()
    
    def search_commands(self, query):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.* FROM commands c
            JOIN command_fts fts ON c.id = fts.rowid
            WHERE command_fts MATCH ?
            ORDER BY rank
            LIMIT 20
        """, (query,))
        return cursor.fetchall()
```

**Day 4-5: Logging Setup**
```python
# daedelus/logging_config.py
import logging
from pathlib import Path

def setup_logging(log_path, level=logging.INFO):
    log_path = Path(log_path).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('daedelus')
```

**Day 6-7: Testing Foundation**
```python
# tests/conftest.py
import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def test_config(temp_dir):
    return {
        'daemon': {'socket_path': str(temp_dir / 'daemon.sock')},
        'model': {'model_path': str(temp_dir / 'model.bin')},
        'database': {'path': str(temp_dir / 'test.db')},
    }

@pytest.fixture
def test_db(temp_dir):
    from daedelus.database import CommandDatabase
    return CommandDatabase(temp_dir / 'test.db')
```

---

## PHASE 2: CORE FUNCTIONALITY (Weeks 3-7)

### Week 3: PTY Monitoring

**Basic daemon structure:**
```python
# daedelus/daemon.py
import os
import signal
import socket
from pathlib import Path
import daemon
import logging

class DaedelusDaemon:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.socket_path = Path(config['daemon']['socket_path']).expanduser()
        self.running = False
    
    def start(self):
        """Start daemon in background"""
        context = daemon.DaemonContext(
            pidfile=daemon.pidfile.PIDLockFile(
                self.config['daemon']['pid_path']
            ),
            signal_map={
                signal.SIGTERM: self._shutdown_handler,
                signal.SIGINT: self._shutdown_handler,
            }
        )
        
        with context:
            self.run()
    
    def run(self):
        """Main event loop"""
        self.running = True
        self._create_socket()
        
        while self.running:
            try:
                # Accept connections
                conn, addr = self.socket.accept()
                self._handle_connection(conn)
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
    
    def _create_socket(self):
        """Create Unix domain socket"""
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.socket_path))
        self.socket.listen(5)
        
        # Restrict permissions
        os.chmod(self.socket_path, 0o600)
    
    def _handle_connection(self, conn):
        """Handle IPC connection"""
        # Implementation in week 4
        pass
    
    def _shutdown_handler(self, signum, frame):
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        self.running = False
        
        if hasattr(self, 'socket'):
            self.socket.close()
        
        if self.socket_path.exists():
            self.socket_path.unlink()
```

### Week 4: IPC Protocol

**Message format:**
```python
# daedelus/ipc.py
import json
from enum import Enum

class MessageType(Enum):
    SUGGEST = "suggest"
    LOG_COMMAND = "log_command"
    EXPLAIN_ERROR = "explain_error"
    COMPLETE = "complete"
    SHUTDOWN = "shutdown"

class IPCMessage:
    def __init__(self, msg_type, data):
        self.type = msg_type
        self.data = data
    
    def to_json(self):
        return json.dumps({
            'type': self.type.value,
            'data': self.data
        })
    
    @classmethod
    def from_json(cls, json_str):
        obj = json.loads(json_str)
        return cls(
            MessageType(obj['type']),
            obj['data']
        )

class IPCServer:
    def __init__(self, daemon):
        self.daemon = daemon
    
    def handle_message(self, conn):
        # Read message
        data = conn.recv(4096)
        if not data:
            return
        
        msg = IPCMessage.from_json(data.decode())
        
        # Route to handler
        if msg.type == MessageType.SUGGEST:
            response = self.daemon.get_suggestions(msg.data)
        elif msg.type == MessageType.LOG_COMMAND:
            self.daemon.log_command(msg.data)
            response = {'status': 'ok'}
        elif msg.type == MessageType.EXPLAIN_ERROR:
            response = self.daemon.explain_error(msg.data)
        else:
            response = {'error': 'Unknown message type'}
        
        # Send response
        conn.sendall(json.dumps(response).encode())
```

### Week 5-6: Embedding Model

**FastText implementation:**
```python
# daedelus/model.py
import fasttext
import numpy as np
from pathlib import Path
import shlex
import re

class CommandEmbedder:
    def __init__(self, config):
        self.config = config
        self.model_path = Path(config['model']['model_path']).expanduser()
        self.embedding_dim = config['model']['embedding_dim']
        self.model = None
    
    def train_from_corpus(self, commands):
        """Train embedding model from command corpus"""
        # Create temporary training file
        train_file = self.model_path.parent / 'train.txt'
        with open(train_file, 'w') as f:
            for cmd in commands:
                tokens = self.tokenize(cmd)
                f.write(' '.join(tokens) + '\n')
        
        # Train FastText model
        self.model = fasttext.train_unsupervised(
            str(train_file),
            model='skipgram',
            dim=self.embedding_dim,
            epoch=5,
            minCount=2,
            wordNgrams=3  # Subword support
        )
        
        # Quantize to reduce size
        self.model.quantize(retrain=True)
        
        # Save
        self.model.save_model(str(self.model_path))
        
        # Clean up
        train_file.unlink()
    
    def load(self):
        """Load existing model"""
        if self.model_path.exists():
            self.model = fasttext.load_model(str(self.model_path))
        else:
            raise FileNotFoundError(f"Model not found: {self.model_path}")
    
    def encode_command(self, command):
        """Convert command to embedding vector"""
        if not self.model:
            raise RuntimeError("Model not loaded")
        
        tokens = self.tokenize(command)
        
        # Get word vectors
        word_vecs = [self.model.get_word_vector(token) for token in tokens]
        
        # Average pooling
        if word_vecs:
            return np.mean(word_vecs, axis=0)
        else:
            return np.zeros(self.embedding_dim)
    
    def tokenize(self, command):
        """Tokenize command into meaningful units"""
        # Use shlex for proper shell parsing
        try:
            parts = shlex.split(command)
        except:
            # Fallback to simple split
            parts = command.split()
        
        tokens = []
        for part in parts:
            if part.startswith('-'):
                # Keep flags whole
                tokens.append(part)
            else:
                # Split on special chars but keep them
                tokens.extend(re.findall(r'\w+|[^\w\s]', part))
        
        return tokens
```

### Week 7: Vector Store

**Annoy implementation:**
```python
# daedelus/vector.py
from annoy import AnnoyIndex
import pickle
from pathlib import Path
import numpy as np

class VectorStore:
    def __init__(self, config):
        self.config = config
        self.dim = config['model']['embedding_dim']
        self.index_path = Path(config['vector_store']['index_path']).expanduser()
        self.n_trees = config['vector_store']['n_trees']
        
        self.index = AnnoyIndex(self.dim, 'angular')
        self.metadata = []
    
    def add(self, embedding, command, metadata):
        """Add command embedding to index"""
        idx = len(self.metadata)
        self.index.add_item(idx, embedding)
        self.metadata.append({
            'command': command,
            'metadata': metadata
        })
    
    def build(self):
        """Finalize index"""
        self.index.build(self.n_trees)
    
    def search(self, query_embedding, top_k=10):
        """Find nearest neighbors"""
        indices, distances = self.index.get_nns_by_vector(
            query_embedding,
            top_k,
            include_distances=True
        )
        
        results = []
        for idx, dist in zip(indices, distances):
            if idx < len(self.metadata):
                results.append({
                    'command': self.metadata[idx]['command'],
                    'similarity': 1.0 - dist,  # Convert distance to similarity
                    'metadata': self.metadata[idx]['metadata']
                })
        
        return results
    
    def save(self):
        """Persist to disk"""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index.save(str(self.index_path) + '.ann')
        
        with open(str(self.index_path) + '.meta', 'wb') as f:
            pickle.dump(self.metadata, f)
    
    def load(self):
        """Load from disk"""
        self.index.load(str(self.index_path) + '.ann')
        
        with open(str(self.index_path) + '.meta', 'rb') as f:
            self.metadata = pickle.load(f)
```

---

## PHASE 3: SHELL INTEGRATION (Weeks 8-10)

### Week 8: ZSH Plugin

**File: plugins/zsh/daedelus.plugin.zsh**
```zsh
# Daedelus ZSH Plugin
# Version: 0.1.0

# Configuration
DAEDELUS_SOCKET="${HOME}/.daedelus/daemon.sock"
DAEDELUS_KEYBIND="^ "  # Ctrl+Space

# Initialize
daedelus_init() {
    # Check daemon
    if [[ ! -S "$DAEDELUS_SOCKET" ]]; then
        echo "Starting Daedelus daemon..."
        daedelus start-daemon &
        sleep 1
    fi
    
    # Set up hooks
    autoload -U add-zsh-hook
    add-zsh-hook preexec daedelus_preexec
    add-zsh-hook precmd daedelus_precmd
    
    # Key bindings
    zle -N daedelus-suggest
    bindkey "$DAEDELUS_KEYBIND" daedelus-suggest
}

# Before command execution
daedelus_preexec() {
    DAEDELUS_CMD="$1"
    DAEDELUS_START=$(date +%s.%N)
}

# After command execution
daedelus_precmd() {
    local exit_code=$?
    
    if [[ -n "$DAEDELUS_CMD" ]]; then
        local duration=$(echo "$(date +%s.%N) - $DAEDELUS_START" | bc)
        
        # Send to daemon
        echo "{
            \"type\": \"log_command\",
            \"data\": {
                \"command\": \"$DAEDELUS_CMD\",
                \"exit_code\": $exit_code,
                \"duration\": $duration,
                \"cwd\": \"$PWD\"
            }
        }" | nc -U "$DAEDELUS_SOCKET" &>/dev/null &
        
        unset DAEDELUS_CMD DAEDELUS_START
    fi
}

# Suggestion widget
daedelus-suggest() {
    local buffer="$BUFFER"
    local cursor="$CURSOR"
    
    # Get suggestions
    local suggestions=$(echo "{
        \"type\": \"suggest\",
        \"data\": {
            \"partial\": \"$buffer\",
            \"cwd\": \"$PWD\",
            \"history\": $(fc -ln -10 | jq -Rs 'split("\n")')
        }
    }" | nc -U "$DAEDELUS_SOCKET" 2>/dev/null)
    
    if [[ -n "$suggestions" ]]; then
        # Display suggestions
        echo ""
        echo "$suggestions" | jq -r '.suggestions[] | "  \(.command)"'
        zle reset-prompt
    fi
}

# Auto-start
daedelus_init
```

### Week 9: Bash Integration

### Week 10: Testing Shell Integration

---

## PHASE 4: LEARNING & OPTIMIZATION (Weeks 11-14)

### Week 11: Pattern Recognition

**Session analysis:**
```python
# daedelus/learning.py
from collections import Counter, defaultdict
import numpy as np

class PatternRecognizer:
    def __init__(self, db):
        self.db = db
    
    def analyze_session(self, session_id):
        """Analyze command patterns in session"""
        commands = self.db.get_session_commands(session_id)
        
        # Extract patterns
        patterns = {
            'frequent_commands': self._find_frequent(commands),
            'command_sequences': self._find_sequences(commands),
            'error_corrections': self._find_corrections(commands),
            'directory_patterns': self._find_directory_patterns(commands)
        }
        
        return patterns
    
    def _find_frequent(self, commands, threshold=3):
        """Find frequently used commands"""
        cmd_counter = Counter(cmd['command'] for cmd in commands)
        return {cmd: count for cmd, count in cmd_counter.items() 
                if count >= threshold}
    
    def _find_sequences(self, commands, window=3):
        """Find common command sequences"""
        sequences = []
        for i in range(len(commands) - window + 1):
            seq = tuple(cmd['command'] for cmd in commands[i:i+window])
            sequences.append(seq)
        
        return Counter(sequences).most_common(10)
    
    def _find_corrections(self, commands):
        """Identify error -> correction pairs"""
        corrections = []
        
        for i in range(len(commands) - 1):
            if commands[i]['exit_code'] != 0:
                if commands[i+1]['exit_code'] == 0:
                    # Potential correction
                    corrections.append({
                        'error': commands[i]['command'],
                        'correction': commands[i+1]['command'],
                        'similarity': self._command_similarity(
                            commands[i]['command'],
                            commands[i+1]['command']
                        )
                    })
        
        return [c for c in corrections if c['similarity'] > 0.5]
```

### Week 12: Fine-tuning

**Incremental learning:**
```python
# daedelus/fine_tuning.py
class ModelUpdater:
    def __init__(self, embedder, vector_store, db):
        self.embedder = embedder
        self.vector_store = vector_store
        self.db = db
    
    def update_from_session(self, session_id):
        """Update model from session data"""
        # Get session commands
        commands = self.db.get_session_commands(session_id)
        
        # Filter successful commands
        successful = [c for c in commands if c['exit_code'] == 0]
        
        # Add to vector store
        for cmd in successful:
            embedding = self.embedder.encode_command(cmd['command'])
            self.vector_store.add(embedding, cmd['command'], {
                'timestamp': cmd['timestamp'],
                'cwd': cmd['cwd'],
                'success_rate': 1.0
            })
        
        # Rebuild index
        self.vector_store.build()
        self.vector_store.save()
    
    def retrain_embedder(self):
        """Retrain embedding model on all history"""
        # Get all successful commands
        all_commands = self.db.get_all_successful_commands()
        
        # Retrain
        self.embedder.train_from_corpus(all_commands)
        self.embedder.save()
```

### Week 13-14: Performance Optimization

**Profiling and optimization:**
```python
# Performance benchmarks
import time
from memory_profiler import profile

@profile
def benchmark_suggestion():
    daemon = DaedelusDaemon(config)
    context = {
        'partial': 'git com',
        'cwd': '/home/user/project',
        'history': ['git status', 'git add .']
    }
    
    times = []
    for _ in range(100):
        start = time.perf_counter()
        suggestions = daemon.get_suggestions(context)
        end = time.perf_counter()
        times.append(end - start)
    
    print(f"Mean: {np.mean(times)*1000:.2f}ms")
    print(f"P95: {np.percentile(times, 95)*1000:.2f}ms")
    print(f"P99: {np.percentile(times, 99)*1000:.2f}ms")
```

---

## PHASE 5: DOCUMENTATION & RELEASE (Weeks 15-17)

### Week 15: Documentation

**README.md:**
```markdown
# Daedelus

A self-learning terminal assistant that gets smarter the more you use it.

## Features

- 🧠 **Self-Teaching AI** - Builds its own model from your command history
- ⚡ **Ultra-Lightweight** - <100MB RAM, <500MB disk
- 🔒 **Privacy-First** - Everything stays on your machine
- 🚀 **Fast** - <50ms suggestion latency
- 🎯 **Context-Aware** - Understands your workflow

## Installation

```bash
pip install daedelus
daedelus setup
```

## Usage

Type commands as normal. Press `Ctrl+Space` for suggestions.

## License

MIT
```

### Week 16: CI/CD Setup

**GitHub Actions workflow:**
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python }}
      
      - name: Install dependencies
        run: |
          pip install -e .[dev]
      
      - name: Run tests
        run: |
          pytest --cov=daedelus tests/
      
      - name: Run linters
        run: |
          ruff check daedelus/
          mypy daedelus/
```

### Week 17: Release

**Checklist:**
- [ ] All tests passing
- [ ] Documentation complete
- [ ] License files in place
- [ ] PyPI package ready
- [ ] GitHub release created
- [ ] Announcement prepared

---

## RECOMMENDED TECHNOLOGY STACK

### Core Libraries (Confirmed)
1. **FastText** - Embedding model (MIT)
2. **Annoy** - Vector search (Apache 2.0)
3. **SQLite** - Database (Public Domain)
4. **ptyprocess** - PTY handling (ISC)
5. **Click** - CLI framework (BSD)
6. **pytest** - Testing (MIT)

### Development Tools
1. **Black** - Code formatting
2. **Ruff** - Linting
3. **mypy** - Type checking
4. **pytest-cov** - Coverage

---

## KEY METRICS TO TRACK

### Performance
- Suggestion latency (target: <50ms)
- Memory usage (target: <100MB)
- Startup time (target: <500ms)
- Database query time (target: <10ms)

### Quality
- Test coverage (target: >80%)
- Type coverage (target: >90%)
- Documentation coverage (target: 100%)

### User Experience
- Time to first suggestion
- Suggestion accuracy
- False positive rate

---

## TROUBLESHOOTING GUIDE

### Common Issues

**Daemon won't start:**
```bash
# Check logs
tail -f ~/.daedelus/daemon.log

# Remove stale PID
rm ~/.daedelus/daemon.pid

# Restart
daedelus restart-daemon
```

**No suggestions appearing:**
```bash
# Check socket connection
ls -la ~/.daedelus/daemon.sock

# Test IPC
echo '{"type":"suggest","data":{"partial":"git"}}' | nc -U ~/.daedelus/daemon.sock
```

**High memory usage:**
```bash
# Check index size
du -sh ~/.daedelus/

# Rebuild with pruning
daedelus rebuild-index --prune
```

---

## CONTRIBUTION WORKFLOW

1. Fork repository
2. Create feature branch
3. Write tests first (TDD)
4. Implement feature
5. Run full test suite
6. Submit pull request

**Code Style:**
- Black formatting
- Type hints required
- Docstrings for public APIs
- Test coverage >80%

---

## NEXT STEPS

1. ✅ Complete foundation (Weeks 1-2)
2. ⏳ Build core functionality (Weeks 3-7)
3. ⏳ Shell integration (Weeks 8-10)
4. ⏳ Learning & optimization (Weeks 11-14)
5. ⏳ Documentation & release (Weeks 15-17)

**Get started now:**
```bash
git clone https://github.com/yourusername/daedelus
cd daedelus
pip install -e .[dev]
pytest tests/
```

---

**Implementation Guide Complete**
**Ready to Build!**
