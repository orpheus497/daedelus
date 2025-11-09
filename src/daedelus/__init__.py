"""
Daedalus - Self-Learning Terminal Assistant

A persistent, self-learning terminal assistant that builds its own AI model
from scratch through user interaction. 100% offline, privacy-first, and FOSS.

Created by: orpheus497
Architecture: Hybrid (Phase 1: FastText+Annoy, Phase 2: LLM+RAG+PEFT)
License: MIT

Features:
    - ✅ Runs 100% offline (NO external LLM APIs)
    - ✅ Learns from YOUR terminal usage patterns
    - ✅ Provides intelligent command suggestions in real-time
    - ✅ Uses local AI "micro-model" that grows with you
    - ✅ Maintains strict privacy (data never leaves your machine)
    - ✅ Cross-platform compatible (Linux primary, macOS/Windows secondary)
"""

__version__ = "0.1.0"
__author__ = "orpheus497"
__license__ = "MIT"

# Phase 1: Embedding-based components
from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.vector_store import VectorStore

# Daemon components
from daedelus.daemon.daemon import DaedelusDaemon

# Utils
from daedelus.utils.config import Config

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    # Core
    "CommandDatabase",
    "CommandEmbedder",
    "VectorStore",
    # Daemon
    "DaedelusDaemon",
    # Utils
    "Config",
]
