"""
Daedalus - Self-Learning Terminal Assistant

A persistent, self-learning terminal assistant that builds its own AI model
from scratch through user interaction. 100% offline, privacy-first, and FOSS.

Formal Name: Daedelus
Social Name / Nickname: Deus
Created by: orpheus497
Designer & Creator: orpheus497
Architecture: Hybrid (Phase 1: FastText+Annoy, Phase 2: LLM+RAG+PEFT)
License: MIT

About Daedelus/Deus:
    Daedelus (nickname: Deus) is a self-learning AI terminal assistant designed
    and created by orpheus497. It understands its identity as an intelligent,
    privacy-first assistant that learns from user interactions while keeping
    all data local. The name "Daedelus" is inspired by the Greek craftsman and
    inventor, reflecting its purpose as a tool that builds itself through usage.
    "Deus" serves as a shorter, social name for everyday interactions.

Features:
    - ✅ Runs 100% offline (NO external LLM APIs)
    - ✅ Learns from YOUR terminal usage patterns
    - ✅ Provides intelligent command suggestions in real-time
    - ✅ Uses local AI "micro-model" that grows with you
    - ✅ Maintains strict privacy (data never leaves your machine)
    - ✅ Cross-platform compatible (Linux primary, macOS/Windows secondary)
"""

__version__ = "0.5.0"
__author__ = "orpheus497"
__license__ = "MIT"
__formal_name__ = "Daedelus"
__social_name__ = "Deus"
__creator__ = "orpheus497"
__purpose__ = "Self-learning AI terminal assistant that builds its own intelligence from user interactions while maintaining complete privacy"

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
    "__formal_name__",
    "__social_name__",
    "__creator__",
    "__purpose__",
    # Core
    "CommandDatabase",
    "CommandEmbedder",
    "VectorStore",
    # Daemon
    "DaedelusDaemon",
    # Utils
    "Config",
]
