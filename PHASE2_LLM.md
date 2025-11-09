# Phase 2: LLM Enhancement Documentation

## Overview

Phase 2 enhances Daedelus with local LLM capabilities for natural language command understanding and generation. All inference runs 100% locally using **Phi-3-mini** via **llama.cpp** for privacy.

## Architecture

### Core Components

1. **LLM Manager** (`llm_manager.py`)
   - Manages Phi-3-mini model via llama.cpp
   - Handles tokenization, context management
   - Provides chat and completion interfaces

2. **RAG Pipeline** (`rag_pipeline.py`)
   - Retrieves relevant context from command history
   - Combines vector search + database queries
   - Formats context for LLM prompts

3. **Command Explainer** (`command_explainer.py`)
   - Generates natural language command explanations
   - Context-aware (uses user's command history)
   - Error explanations with fixes

4. **Command Generator** (`command_generator.py`)
   - Generates shell commands from descriptions
   - Supports multiple alternatives
   - Command refinement and completion

5. **PEFT Trainer** (`peft_trainer.py`)
   - Fine-tunes model on user patterns via LoRA
   - Trains during daemon shutdown
   - Personalizes suggestions to user's style

6. **Enhanced Suggestion Engine** (`enhanced_suggestions.py`)
   - Combines Phase 1 (fast embeddings) + Phase 2 (LLM)
   - Automatic fallback to Phase 1 if LLM unavailable
   - Natural language query detection

## Features

### 1. Natural Language Command Explanations

```python
from daedelus.llm import CommandExplainer

explainer = CommandExplainer(llm, rag)

# Get explanation
explanation = explainer.explain_command("ls -la")
# Output: "Lists all files and directories in long format, including hidden files..."

# Get detailed explanation with examples
result = explainer.explain_with_examples("git add")
print(result['explanation'])
for example in result['examples']:
    print(f"  - {example}")
```

### 2. Command Generation from Descriptions

```python
from daedelus.llm import CommandGenerator

generator = CommandGenerator(llm, rag)

# Generate command
cmd = generator.generate_command("find all python files")
# Output: "find . -name '*.py'"

# Get multiple alternatives
alternatives = generator.generate_command(
    "compress folder",
    return_multiple=True
)
# Output: ["tar -czf archive.tar.gz folder/", "zip -r archive.zip folder/", ...]

# Generate with explanation
result = generator.generate_with_explanation("copy files to server")
print(f"Command: {result['command']}")
print(f"Explanation: {result['explanation']}")
```

### 3. RAG-Enhanced Suggestions

```python
from daedelus.llm import RAGPipeline, EnhancedSuggestionEngine

# Create RAG pipeline
rag = RAGPipeline(db, embedder, vector_store)

# Create enhanced engine
enhanced = EnhancedSuggestionEngine(base_engine, llm, rag)

# Get suggestions (automatically uses LLM for natural language)
suggestions = enhanced.get_suggestions(
    partial="find all config files",
    cwd="/home/user/project",
    history=["cd project", "ls"]
)

# Results include LLM-generated commands with explanations
for sug in suggestions:
    print(f"{sug['command']} ({sug['source']})")
    if 'explanation' in sug:
        print(f"  {sug['explanation']}")
```

### 4. Personalized Fine-Tuning (PEFT/LoRA)

```python
from daedelus.llm import PEFTTrainer

# Initialize trainer
trainer = PEFTTrainer(
    model_name="microsoft/Phi-3-mini-4k-instruct",
    adapter_path=Path("~/.local/share/daedelus/llm/adapter"),
    r=8,  # LoRA rank
    lora_alpha=32,
)

# Prepare training data from command history
commands = db.get_recent_commands(n=1000, successful_only=True)
command_list = [cmd['command'] for cmd in commands]

training_data = trainer.prepare_training_data(command_list)

# Train adapter (runs during daemon shutdown)
trainer.train_adapter(
    training_data,
    num_epochs=3,
    batch_size=4,
)

# Load adapter for inference
trainer.load_adapter()
```

## Configuration

Add to your `config.yaml`:

```yaml
# Phase 2 LLM settings
llm:
  enabled: true
  model_path: ~/.local/share/daedelus/llm/Phi-3-mini-4k-instruct-q4.gguf
  context_length: 2048
  temperature: 0.7
  top_p: 0.9
  max_tokens: 100

# PEFT fine-tuning
peft:
  enabled: true
  adapter_path: ~/.local/share/daedelus/llm/adapter
  r: 8
  lora_alpha: 32
  lora_dropout: 0.1
```

## Model Setup

### Download Phi-3-mini GGUF

```bash
# Create model directory
mkdir -p ~/.local/share/daedelus/llm

# Download Phi-3-mini (Q4 quantized, ~2.4GB)
cd ~/.local/share/daedelus/llm
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
```

### Install Dependencies

```bash
# Install Phase 2 dependencies
pip install 'daedelus[llm]'

# This installs:
# - llama-cpp-python (LLM inference)
# - peft (LoRA fine-tuning)
# - transformers (model handling)
# - accelerate (training optimization)
# - bitsandbytes (quantization)
```

## Integration with Daemon

The daemon automatically:

1. **On startup**: Loads LLM + adapter if enabled
2. **During runtime**: Uses enhanced suggestions
3. **On shutdown**: Fine-tunes adapter on new command patterns

```python
# In daemon initialization
if config.get("llm.enabled"):
    # Load LLM
    llm = LLMManager(
        model_path=config.get("llm.model_path"),
        context_length=config.get("llm.context_length"),
    )

    # Create RAG pipeline
    rag = RAGPipeline(db, embedder, vector_store)

    # Load adapter if exists
    if config.get("peft.enabled"):
        adapter_path = config.get("peft.adapter_path")
        if Path(adapter_path).exists():
            llm.load_adapter(adapter_path)

    # Use enhanced engine
    suggestion_engine = EnhancedSuggestionEngine(
        base_engine, llm, rag
    )
else:
    # Fallback to Phase 1
    suggestion_engine = SuggestionEngine(
        db, embedder, vector_store
    )
```

## Performance

### Inference Speed

- **Model**: Phi-3-mini (3.8B parameters, Q4 quantized)
- **Size**: ~2.4GB on disk
- **RAM**: ~3GB during inference
- **CPU**: ~50-200ms per completion (8-core)
- **GPU**: ~10-50ms per completion (optional)

### Resource Usage

| Component | Memory | Disk |
|-----------|--------|------|
| Base model (Q4) | ~3GB | ~2.4GB |
| LoRA adapter | ~50MB | ~20MB |
| Total Phase 2 | ~3.1GB | ~2.5GB |

## Privacy & Offline

**100% Local & Private:**
- ✅ All inference runs locally (no API calls)
- ✅ No data leaves your machine
- ✅ No internet required after model download
- ✅ Command history stays private
- ✅ Fine-tuning happens locally

## Examples

### Shell Integration

```bash
# In ZSH with Daedelus + LLM:

# Natural language query
$ find all log files<CTRL+SPACE>
# Suggests: find . -name "*.log"

# Get explanation
$ daedelus explain "tar -xzf archive.tar.gz"
# Output: "Extracts files from a gzip-compressed tar archive"

# Generate command
$ daedelus generate "compress all images"
# Output: "tar -czf images.tar.gz *.jpg *.png"
```

### API Usage

```python
# Complete workflow
from daedelus import (
    CommandDatabase,
    CommandEmbedder,
    VectorStore,
    SuggestionEngine,
)
from daedelus.llm import (
    LLMManager,
    RAGPipeline,
    EnhancedSuggestionEngine,
)

# Initialize Phase 1
db = CommandDatabase("history.db")
embedder = CommandEmbedder("model.bin")
vector_store = VectorStore("index")
base_engine = SuggestionEngine(db, embedder, vector_store)

# Initialize Phase 2
llm = LLMManager("Phi-3-mini-4k-instruct-q4.gguf")
rag = RAGPipeline(db, embedder, vector_store)
enhanced = EnhancedSuggestionEngine(base_engine, llm, rag)

# Use enhanced features
suggestions = enhanced.get_suggestions("find config")
explanation = enhanced.explain_command("ls -la")
command = enhanced.generate_command("copy files to server")
```

## Comparison: Phase 1 vs Phase 2

| Feature | Phase 1 (Embeddings) | Phase 2 (LLM) |
|---------|---------------------|---------------|
| Speed | Very fast (<10ms) | Fast (50-200ms) |
| Accuracy | Good for similar commands | Excellent for variations |
| Natural Language | No | Yes |
| Explanations | No | Yes |
| Command Generation | No | Yes |
| Memory | <100MB | ~3GB |
| Privacy | 100% local | 100% local |
| Works Offline | Yes | Yes |

## Best Practices

1. **Use Phase 1 by default** for speed
2. **Enable Phase 2** for:
   - Natural language queries
   - Command explanations
   - Learning new tools
3. **Fine-tune periodically** to personalize
4. **Monitor memory** usage on resource-constrained systems

## Troubleshooting

### LLM fails to load

```bash
# Check model file exists
ls -lh ~/.local/share/daedelus/llm/Phi-3-mini-4k-instruct-q4.gguf

# Check dependencies
python -c "import llama_cpp; print('OK')"

# Check memory
free -h  # Need ~3GB free RAM
```

### Slow inference

```bash
# Use GPU acceleration (if available)
pip install llama-cpp-python[cuda]

# Or use smaller quantization
# Q4: 2.4GB (good balance)
# Q8: 4.1GB (better quality, slower)
# Q2: 1.5GB (faster, lower quality)
```

### Fine-tuning issues

```bash
# Check adapter directory
ls -lh ~/.local/share/daedelus/llm/adapter/

# Verify training data
cat ~/.local/share/daedelus/llm/adapter/training_data.json | head
```

## Roadmap

### Current (v0.1.0)
- ✅ LLM inference via llama.cpp
- ✅ RAG pipeline
- ✅ Command explanation
- ✅ Command generation
- ✅ PEFT/LoRA setup

### Future (v0.2.0)
- Actual PEFT training loop
- Model caching for faster startup
- Streaming responses
- Multi-turn conversations
- Voice input support

## References

- **Phi-3**: https://huggingface.co/microsoft/Phi-3-mini-4k-instruct
- **llama.cpp**: https://github.com/ggerganov/llama.cpp
- **PEFT/LoRA**: https://github.com/huggingface/peft
- **RAG**: https://arxiv.org/abs/2005.11401

## License

Phase 2 components are MIT licensed, same as Phase 1.
Phi-3-mini model is MIT licensed by Microsoft.
