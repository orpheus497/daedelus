"""
Enhanced suggestion engine with LLM integration.

Combines Phase 1 (embedding-based) and Phase 2 (LLM-based) suggestion
strategies for best results.

Created by: orpheus497
"""

import logging
from typing import Any, Dict, List, Optional

from daedelus.core.suggestions import SuggestionEngine
from daedelus.llm.command_generator import CommandGenerator
from daedelus.llm.command_explainer import CommandExplainer
from daedelus.llm.llm_manager import LLMManager
from daedelus.llm.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class EnhancedSuggestionEngine:
    """
    Enhanced suggestion engine with LLM capabilities.

    Combines:
    - Phase 1: Fast embedding-based suggestions
    - Phase 2: LLM-powered command generation and explanations

    Falls back to Phase 1 if LLM is disabled or unavailable.

    Attributes:
        base_engine: Phase 1 suggestion engine
        llm: Optional LLM manager
        rag: Optional RAG pipeline
        command_generator: Optional command generator
        command_explainer: Optional command explainer
        llm_enabled: Whether LLM features are enabled
    """

    def __init__(
        self,
        base_engine: SuggestionEngine,
        llm: Optional[LLMManager] = None,
        rag: Optional[RAGPipeline] = None,
    ) -> None:
        """
        Initialize enhanced suggestion engine.

        Args:
            base_engine: Phase 1 suggestion engine
            llm: Optional LLM manager (Phase 2)
            rag: Optional RAG pipeline (Phase 2)
        """
        self.base_engine = base_engine
        self.llm = llm
        self.rag = rag

        # Initialize Phase 2 components if LLM is available
        self.llm_enabled = llm is not None

        if self.llm_enabled:
            self.command_generator = CommandGenerator(llm, rag)
            self.command_explainer = CommandExplainer(llm, rag)
            logger.info("Enhanced suggestion engine initialized with LLM support")
        else:
            self.command_generator = None
            self.command_explainer = None
            logger.info("Enhanced suggestion engine initialized (LLM disabled)")

    def get_suggestions(
        self,
        partial: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
        context_window: int = 10,
        use_llm: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get command suggestions with optional LLM enhancement.

        Args:
            partial: Partially typed command
            cwd: Current working directory
            history: Recent command history
            context_window: Number of recent commands to consider
            use_llm: Whether to use LLM features (if available)

        Returns:
            List of suggestion dicts with 'command', 'confidence', 'source'
        """
        # Get Phase 1 suggestions (fast, always available)
        base_suggestions = self.base_engine.get_suggestions(
            partial, cwd, history, context_window
        )

        # If LLM is disabled or not requested, return Phase 1 only
        if not use_llm or not self.llm_enabled:
            return base_suggestions

        # Try to enhance with LLM
        try:
            # If partial looks like natural language, try generating command
            if self._is_natural_language(partial):
                llm_suggestion = self._generate_from_description(partial, cwd, history)

                if llm_suggestion:
                    # Prepend LLM suggestion with high confidence
                    llm_suggestion["source"] = "llm_generation"
                    llm_suggestion["confidence"] = 0.9

                    # Combine with base suggestions (deduplicate)
                    combined = [llm_suggestion]
                    seen = {llm_suggestion["command"]}

                    for sug in base_suggestions:
                        if sug["command"] not in seen:
                            combined.append(sug)
                            seen.add(sug["command"])

                    return combined[:self.base_engine.max_suggestions]

            # Otherwise, enhance existing suggestions with explanations
            return self._add_explanations(base_suggestions[:3])

        except Exception as e:
            logger.warning(f"LLM enhancement failed, falling back to base: {e}")
            return base_suggestions

    def generate_command(
        self,
        description: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate command from natural language description.

        Args:
            description: Natural language description
            cwd: Current working directory
            history: Recent command history

        Returns:
            Suggestion dict or None if generation fails
        """
        if not self.llm_enabled or not self.command_generator:
            logger.warning("LLM not available for command generation")
            return None

        try:
            result = self.command_generator.generate_with_explanation(
                description, cwd
            )

            if result.get("command"):
                return {
                    "command": result["command"],
                    "confidence": 0.85,
                    "source": "llm_generation",
                    "explanation": result.get("explanation", ""),
                }

        except Exception as e:
            logger.error(f"Command generation failed: {e}")

        return None

    def explain_command(
        self,
        command: str,
        cwd: Optional[str] = None,
    ) -> str:
        """
        Get explanation for a command.

        Args:
            command: Shell command to explain
            cwd: Current working directory

        Returns:
            Natural language explanation
        """
        if not self.llm_enabled or not self.command_explainer:
            return "Explanation not available (LLM disabled)"

        try:
            return self.command_explainer.explain_command(command, cwd=cwd)
        except Exception as e:
            logger.error(f"Explanation failed: {e}")
            return f"Error: {str(e)}"

    def _is_natural_language(self, text: str) -> bool:
        """
        Check if text looks like natural language vs a command.

        Args:
            text: Input text

        Returns:
            True if text appears to be natural language
        """
        # Heuristics for detecting natural language:
        # - Contains spaces between words
        # - Contains common English words
        # - Doesn't start with common commands
        # - Contains question words or action verbs

        text = text.strip().lower()

        # Check for command-like patterns
        common_commands = {
            "ls", "cd", "git", "docker", "npm", "python", "cat", "grep",
            "find", "rm", "cp", "mv", "curl", "wget", "ssh", "sudo"
        }

        first_word = text.split()[0] if text.split() else ""

        if first_word in common_commands:
            return False

        # Check for natural language indicators
        nl_indicators = [
            "find", "show", "list", "display", "get", "search", "create",
            "delete", "remove", "copy", "move", "what", "how", "where",
            "all", "files", "directories", "with", "that", "containing"
        ]

        word_count = len(text.split())

        # If has 3+ words and contains NL indicators, likely natural language
        if word_count >= 3 and any(word in text for word in nl_indicators):
            return True

        # Check for specific patterns
        if any(text.startswith(prefix) for prefix in ["how to", "find all", "show me", "list all"]):
            return True

        return False

    def _generate_from_description(
        self,
        description: str,
        cwd: Optional[str],
        history: Optional[List[str]],
    ) -> Optional[Dict[str, Any]]:
        """
        Generate command suggestion from description.

        Args:
            description: Natural language description
            cwd: Current working directory
            history: Recent history

        Returns:
            Suggestion dict or None
        """
        if not self.command_generator:
            return None

        try:
            command = self.command_generator.generate_command(
                description, cwd, history
            )

            if command:
                return {
                    "command": command,
                    "confidence": 0.9,
                    "source": "llm_generation",
                }

        except Exception as e:
            logger.debug(f"Generation failed: {e}")

        return None

    def _add_explanations(
        self,
        suggestions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Add explanations to suggestions.

        Args:
            suggestions: List of suggestions

        Returns:
            Suggestions with explanations added
        """
        if not self.command_explainer:
            return suggestions

        enhanced = []

        for sug in suggestions:
            try:
                # Get brief explanation
                explanation = self.command_explainer.explain_command(
                    sug["command"],
                    include_context=False,
                )

                # Add to suggestion
                sug_copy = sug.copy()
                sug_copy["explanation"] = explanation

                enhanced.append(sug_copy)

            except Exception as e:
                logger.debug(f"Failed to explain {sug['command']}: {e}")
                enhanced.append(sug)

        return enhanced

    def __repr__(self) -> str:
        """String representation."""
        llm_status = "enabled" if self.llm_enabled else "disabled"
        return f"EnhancedSuggestionEngine(llm={llm_status})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("EnhancedSuggestionEngine example - requires components to be initialized")

    # Example usage pattern:
    print("\nUsage pattern:")
    print("1. Create Phase 1 components (database, embedder, vector store)")
    print("2. Create base suggestion engine")
    print("3. Optionally create Phase 2 components (LLM, RAG)")
    print("4. Create enhanced engine")
    print("5. Get suggestions with automatic Phase 1/2 combination")

    # Example suggestions with different sources:
    example_suggestions = [
        {
            "command": "ls -la",
            "confidence": 0.95,
            "source": "exact_prefix",
            "explanation": "Lists all files in long format including hidden files.",
        },
        {
            "command": "find . -name '*.py'",
            "confidence": 0.90,
            "source": "llm_generation",
            "explanation": "Recursively finds all Python files in the current directory.",
        },
        {
            "command": "ls -lh",
            "confidence": 0.78,
            "source": "semantic",
            "explanation": "Lists files in long format with human-readable sizes.",
        },
    ]

    print("\nExample enhanced suggestions:")
    for sug in example_suggestions:
        print(f"\n{sug['confidence']:.2f} - {sug['command']}")
        print(f"  Source: {sug['source']}")
        print(f"  {sug['explanation']}")
