# LLM Model Setup Guide

This guide covers everything you need to know about downloading, configuring, and using different LLM models with Daedalus.

## Overview

Daedalus uses GGUF-format models compatible with llama.cpp for its LLM features. These models power:
- Command explanations (`daedelus explain`)
- Command generation (`daedelus generate`)
- Question answering (`daedelus ask`)
- Web search summarization (`daedelus websearch`)

## Quick Start

```bash
# Create models directory
mkdir -p ~/.local/share/models

# Download recommended model (Phi-3-mini)
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf

# Move to expected location
mv Phi-3-mini-4k-instruct-q4.gguf ~/.local/share/models/model.gguf

# Restart Daedalus
daedelus restart

# Test it
daedelus explain "ls -la"
```

## Available Models

### Recommended Models

#### 1. Phi-3-mini (Recommended)
- **Size**: ~2.4GB
- **RAM Required**: 4GB
- **Speed**: Fast
- **Quality**: High
- **Best for**: General use, balanced performance

```bash
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
mv Phi-3-mini-4k-instruct-q4.gguf ~/.local/share/models/model.gguf
```

#### 2. TinyLlama-1.1B
- **Size**: ~600MB
- **RAM Required**: 2GB
- **Speed**: Very fast
- **Quality**: Good
- **Best for**: Low-end systems, quick responses

```bash
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
mv tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf ~/.local/share/models/model.gguf
```

#### 3. Mistral-7B
- **Size**: ~4GB
- **RAM Required**: 8GB
- **Speed**: Moderate
- **Quality**: Very high
- **Best for**: High-end systems, complex queries

```bash
wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf
mv mistral-7b-instruct-v0.2.Q4_K_M.gguf ~/.local/share/models/model.gguf
```

#### 4. Qwen2.5-3B
- **Size**: ~3GB
- **RAM Required**: 6GB
- **Speed**: Fast
- **Quality**: High
- **Best for**: Multilingual support, code generation

```bash
wget https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf
mv qwen2.5-3b-instruct-q4_k_m.gguf ~/.local/share/models/model.gguf
```

### Model Comparison

| Model | Size | RAM | CPU Usage | Response Time | Quality | Use Case |
|-------|------|-----|-----------|---------------|---------|----------|
| TinyLlama-1.1B | 600MB | 2GB | Low | <1s | ⭐⭐⭐ | Lightweight systems |
| Phi-3-mini | 2.4GB | 4GB | Medium | 1-2s | ⭐⭐⭐⭐ | **Recommended** |
| Qwen2.5-3B | 3GB | 6GB | Medium | 2-3s | ⭐⭐⭐⭐ | Multilingual |
| Mistral-7B | 4GB | 8GB | High | 3-5s | ⭐⭐⭐⭐⭐ | High performance |

## Configuration

### Default Configuration

Daedalus looks for models at: `~/.local/share/models/model.gguf`

Default settings in `~/.config/daedelus/config.yaml`:

```yaml
llm:
  enabled: true
  model_path: ~/.local/share/models/model.gguf
  context_length: 2048
  temperature: 0.7
```

### Changing the Model Path

#### Option 1: Edit Config File

```bash
# Open config
nano ~/.config/daedelus/config.yaml

# Modify the llm section:
llm:
  enabled: true
  model_path: /path/to/your/custom-model.gguf  # Change this
  context_length: 2048
  temperature: 0.7
```

#### Option 2: Use CLI

```bash
# Set model path
daedelus config set llm.model_path /path/to/your/model.gguf

# Verify
daedelus config get llm.model_path

# Restart to load new model
daedelus restart
```

### Configuration Parameters

#### `llm.enabled`
- **Type**: boolean
- **Default**: `true`
- **Description**: Enable/disable LLM features

```bash
daedelus config set llm.enabled true
```

#### `llm.model_path`
- **Type**: string (file path)
- **Default**: `~/.local/share/models/model.gguf`
- **Description**: Path to GGUF model file

```bash
daedelus config set llm.model_path ~/.local/share/models/my-model.gguf
```

#### `llm.context_length`
- **Type**: integer
- **Default**: `2048`
- **Range**: 512 - 8192
- **Description**: Maximum context window size (higher = more RAM usage)

```bash
# For small models
daedelus config set llm.context_length 1024

# For large models with lots of RAM
daedelus config set llm.context_length 4096
```

#### `llm.temperature`
- **Type**: float
- **Default**: `0.7`
- **Range**: 0.0 - 2.0
- **Description**: Creativity level (0.0 = deterministic, 1.0 = creative)

```bash
# More deterministic (for technical commands)
daedelus config set llm.temperature 0.3

# More creative (for general questions)
daedelus config set llm.temperature 0.9
```

### Advanced Settings

#### Using Multiple Models

Keep multiple models and switch between them:

```bash
# Download multiple models
wget <model1-url> -O ~/.local/share/models/phi-3-mini.gguf
wget <model2-url> -O ~/.local/share/models/mistral-7b.gguf
wget <model3-url> -O ~/.local/share/models/tinyllama.gguf

# Switch to different model
daedelus config set llm.model_path ~/.local/share/models/mistral-7b.gguf
daedelus restart

# Switch back
daedelus config set llm.model_path ~/.local/share/models/phi-3-mini.gguf
daedelus restart
```

#### Performance Tuning

For low-end systems:
```yaml
llm:
  enabled: true
  model_path: ~/.local/share/models/tinyllama.gguf
  context_length: 1024
  temperature: 0.5
```

For high-end systems:
```yaml
llm:
  enabled: true
  model_path: ~/.local/share/models/mistral-7b.gguf
  context_length: 4096
  temperature: 0.7
```

## Finding More Models

### Hugging Face

Search for GGUF models on Hugging Face:
- https://huggingface.co/models?search=gguf

Popular model creators:
- **TheBloke** - High-quality GGUF conversions
- **bartowski** - Recent model quantizations
- **QuantFactory** - Various quantizations

### Model Requirements

A model must be:
- ✅ In GGUF format
- ✅ Compatible with llama.cpp
- ✅ Instruction-tuned (chat/instruct variants)
- ✅ Quantized (Q4_K_M or Q4_0 recommended)

### Quantization Levels

| Quantization | Size | Quality | Speed | Recommended |
|--------------|------|---------|-------|-------------|
| Q2_K | Smallest | Low | Fastest | ❌ Too low quality |
| Q3_K_M | Small | Medium | Very Fast | ⚠️ Acceptable |
| Q4_K_M | Medium | Good | Fast | ✅ **Recommended** |
| Q5_K_M | Large | Very Good | Moderate | ✅ If RAM available |
| Q6_K | Larger | Excellent | Slower | ⚠️ For large systems |
| Q8_0 | Largest | Best | Slowest | ❌ Usually overkill |

**Recommendation**: Use Q4_K_M quantization for best balance.

## Troubleshooting

### Model Not Found

```bash
# Check what Daedalus is looking for
daedelus info

# Check if file exists
ls -lh ~/.local/share/models/

# Verify config
daedelus config get llm.model_path

# Create directory if missing
mkdir -p ~/.local/share/models
```

### Out of Memory

**Symptoms**: Daemon crashes, system freezes, "allocation failed" errors

**Solutions**:
1. Use a smaller model (TinyLlama instead of Mistral)
2. Use lower quantization (Q4 instead of Q6)
3. Reduce context length:
   ```bash
   daedelus config set llm.context_length 1024
   ```
4. Close other applications
5. Add swap space

### Slow Performance

**Symptoms**: Long response times, high CPU usage

**Solutions**:
1. Use a smaller model
2. Reduce context length
3. Lower temperature (slightly faster):
   ```bash
   daedelus config set llm.temperature 0.5
   ```
4. Ensure model is on SSD, not HDD
5. Check system resources: `htop`

### Model Loads Slowly on First Use

This is normal! The model needs to be loaded into RAM.

- First load: 5-30 seconds (depending on model size)
- Subsequent uses: Instant (model stays in RAM)

To keep model in memory, keep the daemon running:
```bash
daedelus start  # Starts daemon in background
```

### Wrong/Unexpected Responses

**Solutions**:
1. Adjust temperature:
   ```bash
   # More consistent
   daedelus config set llm.temperature 0.3

   # More varied
   daedelus config set llm.temperature 0.9
   ```

2. Try a different model (Phi-3-mini usually best for commands)

3. Check model is correct type (needs to be instruct/chat variant)

## Privacy & Security

### Where Models Are Stored

- **Models**: `~/.local/share/models/` (you download these)
- **User data**: `~/.local/share/daedelus/` (your command history)
- **Config**: `~/.config/daedelus/config.yaml`

### Privacy Guarantees

✅ Models run 100% locally on your machine
✅ No internet connection required after download
✅ No telemetry or data collection
✅ Your commands never leave your computer

### .gitignore Protection

The `.gitignore` file ensures that if you fork or upload Daedalus:
- ❌ Your models are NOT uploaded (too large)
- ❌ Your command history is NOT uploaded (private data)
- ❌ Your config is NOT uploaded (personal paths)
- ✅ Only the program code is included

## Best Practices

1. **Start with Phi-3-mini** - Best balance for most users
2. **Use Q4_K_M quantization** - Good quality, reasonable size
3. **Keep daemon running** - Faster responses (model stays in RAM)
4. **Adjust temperature** - Lower (0.3-0.5) for technical tasks, higher (0.7-0.9) for creative tasks
5. **Monitor RAM usage** - Use `htop` or `daedelus status`
6. **Update models occasionally** - New models release frequently

## Examples

### Example 1: Switch to TinyLlama for Speed

```bash
# Download TinyLlama
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf -O ~/.local/share/models/tinyllama.gguf

# Configure Daedalus to use it
daedelus config set llm.model_path ~/.local/share/models/tinyllama.gguf
daedelus config set llm.context_length 1024

# Restart
daedelus restart

# Test
daedelus explain "grep -r 'pattern' ."
```

### Example 2: Use Mistral for Better Quality

```bash
# Download Mistral 7B
wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf -O ~/.local/share/models/mistral.gguf

# Configure
daedelus config set llm.model_path ~/.local/share/models/mistral.gguf
daedelus config set llm.context_length 4096
daedelus config set llm.temperature 0.7

# Restart
daedelus restart

# Test complex query
daedelus websearch "advanced git branching strategies"
```

### Example 3: Optimize for Low RAM

```bash
# Use TinyLlama with minimal settings
daedelus config set llm.model_path ~/.local/share/models/tinyllama.gguf
daedelus config set llm.context_length 512
daedelus config set llm.temperature 0.5
daedelus restart
```

## Support

For issues or questions:
- Check [Troubleshooting Guide](TROUBLESHOOTING.md)
- See [README.md](../README.md) for general info
- Report issues: https://github.com/orpheus497/daedelus/issues

---

**Created by orpheus497**
