# Deus.gguf Integration - Continuous Learning LLM System

## Overview

This document describes the integrated FOSS repository features for token compression, semantic comprehension, and continuous model training.

## Key Features

### 1. **Token Compression & Semantic Chunking**

100% FOSS semantic chunking system that intelligently compresses input tokens while maximizing semantic comprehension.

**Technology:**
- Custom implementation inspired by jparkerweb/semantic-chunking and chonkie-inc/chonkie
- Uses FastText embeddings for semantic similarity detection
- Preserves important context while reducing token usage

**How it works:**
- Splits text into semantic chunks based on embedding similarity
- Scores chunks by importance (information density, keywords, etc.)
- Compresses context to fit token limits while preserving meaning

**Configuration:**
```yaml
compression:
  enabled: true
  similarity_threshold: 0.75
  max_chunk_tokens: 512
  aggressive: false
```

**Usage:**
```python
from daedelus.llm.semantic_chunker import SemanticChunker, TokenCompressor

# Initialize
chunker = SemanticChunker(embedder, similarity_threshold=0.75)
compressor = TokenCompressor(chunker)

# Compress context
compressed = compressor.compress_context(text, max_tokens=512)
```

---

### 2. **Daedelus Embedding Model - Continuous Learning**

The embedding model that continuously grows and fine-tunes as you use the system.

**Features:**
- Incremental training on new commands
- Preserves existing knowledge while learning new patterns
- Automatic training triggers at command thresholds

**How it works:**
- Tracks new commands since last training
- When threshold reached (default: 100 commands), triggers incremental training
- Updates embeddings to improve semantic understanding

**Configuration:**
```yaml
continuous_learning:
  enabled: true
  embedding_training_threshold: 100
  periodic_updates: true
```

**Usage:**
```python
# Incremental training
embedder.incremental_train(new_commands, min_new_commands=100)

# Get training stats
stats = embedder.get_training_stats()
print(f"Vocabulary size: {stats['vocab_size']}")
```

---

### 3. **Deus.gguf Model System**

The main continuously trained and fine-tuned LLM that grows with your usage.

**Model Priority:**
1. **deus.gguf** (if exists) - Your personalized, continuously trained model
2. **daedelus_v*.gguf** - Versioned daedelus models (highest version)
3. **Other .gguf files** - Any other compatible models
4. **Download prompt** - If no models found, prompts for download

**How it works:**
- Auto-detects models in `~/.local/share/models/`
- Always uses deus.gguf if present
- Falls back to other models if deus.gguf not available
- Prompts for download if no models exist

**Configuration:**
```yaml
deus:
  enabled: true
  training_threshold: 500
  manual_training_enabled: true
  show_notifications: true
  show_status_bars: true
  auto_download_prompt: true
```

**Usage:**
```python
from daedelus.llm.deus_model_manager import DeusModelManager

# Initialize
manager = DeusModelManager(models_dir, training_threshold=500)

# Load model (auto-detects deus.gguf)
model = manager.load_model()

# Check if deus.gguf exists
if manager.has_deus_model():
    print("Using deus.gguf model")
else:
    print(f"Using fallback: {manager.fallback_model_path}")
```

---

### 4. **Threshold-Based & Command-Based Fine-Tuning**

Automatic and manual training triggers for continuous model improvement.

**Training Triggers:**

#### Automatic (Threshold-Based):
- Monitors command count since last training
- Automatically triggers when threshold reached (default: 500 commands)
- Sends notifications before training begins
- Locks program during training (10-30 minutes on consumer PC)

#### Manual (Command-Based):
```bash
# Trigger training manually
daedelus train

# Check training progress
daedelus status

# View training history
daedelus history
```

**Training Workflow:**
1. **Prepare data** - Fetch recent commands from database
2. **Train LoRA adapter** - Fine-tune using PEFT/LoRA (10-30 min)
3. **Merge adapter** - Merge with base model
4. **Convert to GGUF** - Create new GGUF file
5. **Update deus.gguf** - Replace with new trained model

**Configuration:**
```yaml
deus:
  training_threshold: 500        # Commands before auto-training
  manual_training_enabled: true  # Allow manual training
```

**Usage:**
```python
from daedelus.llm.training_coordinator import TrainingCoordinator

# Initialize
coordinator = TrainingCoordinator(deus_manager, peft_trainer, db)

# Check if training should trigger
if coordinator.check_and_trigger_training():
    print("Training started")

# Manual trigger
coordinator.check_and_trigger_training(force=True)

# Get progress
progress = coordinator.get_progress()
print(f"Status: {progress.status}")
print(f"Progress: {progress.progress_percentage}%")
```

---

### 5. **Training UI with Status Bars & Notifications**

Rich terminal UI for training feedback.

**Features:**
- Real-time progress bars
- Status updates for each training step
- Time elapsed and estimated remaining
- Program lock warning
- Success/failure notifications

**Training Steps:**
1. ⏳ **Preparing** - Fetching and preparing training data
2. 🔄 **Training** - Fine-tuning LoRA adapter (10-30 min)
3. 🔧 **Converting** - Converting to GGUF format
4. ✨ **Finalizing** - Updating deus.gguf
5. ✓ **Completed** - Training complete!

**Notifications:**
- Training threshold reached
- Training started (with time estimate)
- Progress updates
- Completion or failure

**Configuration:**
```yaml
deus:
  show_notifications: true
  show_status_bars: true
```

**Example Output:**
```
┌─────────────────────────────────────────────┐
│ ⚠ Training In Progress ⚠                   │
│                                             │
│ The program is currently training the      │
│ deus.gguf model. Please wait for          │
│ training to complete.                       │
│                                             │
│ Estimated time: 10-30 minutes              │
│ on consumer PC                              │
└─────────────────────────────────────────────┘

Overall Training Progress ████████░░░░ 60%
Step 2/5: Training LoRA adapter...
Elapsed: 0:12:34  Remaining: ~0:08:00
```

---

### 6. **Model Fallback Logic & Download Prompts**

Smart model detection with automatic fallback and user-friendly download.

**Fallback Logic:**
```
deus.gguf exists? → Use deus.gguf
    ↓ No
daedelus_v*.gguf exists? → Use highest version
    ↓ No
Other .gguf exists? → Use first found
    ↓ No
Prompt user to download
```

**Download Prompt:**
```
┌─────────────────────────────────────────────┐
│ No Models Found                             │
│                                             │
│ No LLM models were detected in your        │
│ models directory. Would you like to        │
│ download a model now?                       │
└─────────────────────────────────────────────┘

Available Models:
# Model         Size     Description
1 tinyllama     669 MB   TinyLlama 1.1B ✓ Best for most
2 phi-3-mini    2400 MB  Phi-3-mini 3.8B (Better quality)

Select model [1-2] (or 'cancel'): _
```

**Usage:**
```python
from daedelus.llm.model_downloader import ModelDownloader, prompt_and_download_model

# Prompt user for download
model_path = prompt_and_download_model(models_dir)

# Auto-download if missing
success = auto_download_if_missing(models_dir)
```

---

## Time Estimates (Consumer PC)

**Training Time Estimates:**
- 100 commands: ~5 minutes
- 500 commands: ~15 minutes
- 1000 commands: ~25 minutes

**Factors affecting time:**
- CPU speed
- Available RAM
- Number of training samples
- Model size

**Note:** During training, the program is locked and unavailable for use.

---

## Configuration Example

Complete configuration for all features:

```yaml
# Enable LLM
llm:
  enabled: true
  model_path: null  # Auto-detects deus.gguf
  context_length: 2048
  n_gpu_layers: 0

# Enable PEFT training
peft:
  enabled: true
  r: 8
  lora_alpha: 32

# Deus model settings
deus:
  enabled: true
  training_threshold: 500
  manual_training_enabled: true
  show_notifications: true
  show_status_bars: true
  auto_download_prompt: true

# Token compression
compression:
  enabled: true
  similarity_threshold: 0.75
  max_chunk_tokens: 512
  aggressive: false

# Continuous learning
continuous_learning:
  enabled: true
  embedding_training_threshold: 100
  periodic_updates: true
```

---

## CLI Commands

New commands for deus.gguf system:

```bash
# Download a model
daedelus download-model

# Manually trigger training
daedelus train

# Check training status
daedelus status

# View training progress
daedelus progress

# List available models
daedelus models list

# Show model info
daedelus models info
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Commands                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────┐
│              Command Counter                            │
│  (Tracks commands since last training)                  │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ↓ Threshold Reached?
┌─────────────────────────────────────────────────────────┐
│          Training Coordinator                           │
│  • Threshold-based triggers                             │
│  • Manual training triggers                             │
│  • Progress tracking                                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────┐
│            Training Workflow                            │
│  1. Prepare data from command history                   │
│  2. Train LoRA adapter (PEFT)                          │
│  3. Merge adapter with base model                       │
│  4. Convert to GGUF                                     │
│  5. Update deus.gguf                                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────┐
│             Deus Model Manager                          │
│  • Auto-detect deus.gguf                                │
│  • Fallback to other models                             │
│  • Model prioritization                                 │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────┐
│                 LLM Inference                           │
│  • RAG with token compression                           │
│  • Semantic chunking                                    │
│  • Context optimization                                 │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Files

| File | Description |
|------|-------------|
| `semantic_chunker.py` | Token compression & semantic chunking |
| `deus_model_manager.py` | deus.gguf detection & prioritization |
| `training_coordinator.py` | Training triggers & workflow |
| `training_ui.py` | Status bars & notifications |
| `model_downloader.py` | Interactive model download |
| `rag_pipeline.py` | Enhanced with token compression |
| `embeddings.py` | Enhanced with continuous learning |

---

## Getting Started

1. **Install daedelus:**
   ```bash
   pip install daedelus
   ```

2. **Start the daemon:**
   ```bash
   daedelus start
   ```

3. **Download a model (if prompted):**
   - Select TinyLlama (recommended) or Phi-3-mini
   - Wait for download to complete

4. **Use normally:**
   - Commands are tracked automatically
   - Training triggers at threshold (default: 500 commands)
   - deus.gguf is created after first training

5. **Manual training (optional):**
   ```bash
   daedelus train
   ```

---

## Troubleshooting

### No models detected
- Run `daedelus download-model` to download a model
- Or manually place a .gguf file in `~/.local/share/models/`

### Training fails
- Check logs: `~/.local/share/daedelus/daemon.log`
- Ensure enough disk space (models can be 2-5 GB)
- Verify llama.cpp is installed for GGUF conversion

### Training too slow
- Reduce `training_threshold` to train on fewer commands
- Use smaller model (TinyLlama instead of Phi-3)
- Training time is normal for consumer PCs (10-30 min)

### Token compression not working
- Check `compression.enabled: true` in config
- Verify embeddings are loaded
- Check logs for compression errors

---

## FAQ

**Q: What is deus.gguf?**
A: deus.gguf is your personalized LLM that continuously learns from your command usage. It's created after the first training session and grows with each subsequent training.

**Q: How often should I train?**
A: The default threshold (500 commands) balances learning frequency with training time. You can adjust this in the config.

**Q: Can I use the program during training?**
A: No, the program is locked during training to ensure model integrity. Training takes 10-30 minutes on consumer hardware.

**Q: What happens to my old models?**
A: Old versions are backed up automatically. You can rollback if needed using `daedelus models rollback`.

**Q: Is this 100% FOSS?**
A: Yes! All components use FOSS technologies:
- FastText (Facebook Research, MIT)
- llama.cpp (ggerganov, MIT)
- TinyLlama (Apache 2.0)
- Transformers (HuggingFace, Apache 2.0)
- PEFT (HuggingFace, Apache 2.0)

---

## License

All new components are licensed under the same license as the Daedelus project.

100% FOSS - No proprietary dependencies.
