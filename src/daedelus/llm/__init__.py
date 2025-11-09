"""
LLM enhancement module for Daedelus Phase 2.

Provides local LLM capabilities for:
- Natural language command explanations
- Command generation from descriptions
- Context-aware suggestions
- Fine-tuning via PEFT/LoRA
- RAG (Retrieval-Augmented Generation)

Created by: orpheus497
"""

from daedelus.llm.llm_manager import LLMManager
from daedelus.llm.command_explainer import CommandExplainer
from daedelus.llm.command_generator import CommandGenerator
from daedelus.llm.rag_pipeline import RAGPipeline
from daedelus.llm.peft_trainer import PEFTTrainer
from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

__all__ = [
    "LLMManager",
    "CommandExplainer",
    "CommandGenerator",
    "RAGPipeline",
    "PEFTTrainer",
    "EnhancedSuggestionEngine",
]
