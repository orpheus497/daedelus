"""
Core components for Daedalus.

This module contains the core AI and data management components:
- Database: SQLite-based command history storage with FTS5
- Embeddings: FastText-based command embeddings (Phase 1)
- Vector Store: Annoy-based similarity search (Phase 1)
- Suggestions: Multi-tier suggestion engine

Phase 2 will add:
- LLM inference (llama.cpp + Phi-3-mini)
- RAG pipeline for context injection
- PEFT/LoRA fine-tuning
"""

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.vector_store import VectorStore

__all__ = ["CommandDatabase", "CommandEmbedder", "VectorStore"]
