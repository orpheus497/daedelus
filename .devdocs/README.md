# Daedalus Development Documentation

This directory contains technical documentation and design specifications for the Daedalus project.

## Contents

### Planning Documents (`planning/`)

- **daedelus_complete_blueprint.md** - Complete technical architecture and design
- **daedelus_executive_summary.md** - High-level project overview
- **daedelus_implementation_guide.md** - Implementation roadmap and guidelines
- **daedelus_master_index.md** - Documentation index and navigation
- **daedelus_research_database.md** - Technology research and comparisons

## Project Overview

Daedalus is a privacy-first terminal assistant that learns from your command history to provide intelligent suggestions. It uses FastText embeddings and Annoy vector search to build a personalized model completely offline.

### Key Features

- **100% Local** - No cloud services, no telemetry, no external API calls
- **Privacy-First** - Configurable filtering of sensitive commands and directories
- **Self-Learning** - Builds its own AI model from your usage patterns
- **Lightweight** - <100MB RAM, <500MB disk, <50ms suggestions
- **FOSS** - MIT licensed with only permissive dependencies

### Architecture

**Phase 1 (Current):** Embedding-based system
- FastText word embeddings (MIT)
- Annoy vector similarity search (Apache 2.0)
- SQLite with FTS5 for command history
- 3-tier suggestion cascade (prefix → semantic → contextual)

**Phase 2 (Planned Q2 2025):** LLM enhancement
- llama.cpp integration for local LLM inference
- Phi-3-mini model (MIT)
- RAG pipeline for context injection
- PEFT/LoRA fine-tuning for personalization

## Development

For contribution guidelines, see `CONTRIBUTING.md` in the project root.

For quick start and usage, see `QUICKSTART.md` in the project root.

## License

All documentation and code: MIT License

---

*For more information, see the planning documents in this directory.*
