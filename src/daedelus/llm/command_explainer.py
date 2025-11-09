"""
Command explanation generator using LLM.

Provides natural language explanations of shell commands with context.

Created by: orpheus497
"""

import logging
from typing import Optional

from daedelus.llm.llm_manager import LLMManager
from daedelus.llm.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class CommandExplainer:
    """
    Generate natural language explanations of shell commands.

    Uses LLM with RAG to provide context-aware command explanations.

    Attributes:
        llm: LLM manager instance
        rag: RAG pipeline for context retrieval
        max_explanation_tokens: Maximum tokens for explanation
    """

    def __init__(
        self,
        llm: LLMManager,
        rag: Optional[RAGPipeline] = None,
        max_explanation_tokens: int = 150,
    ) -> None:
        """
        Initialize command explainer.

        Args:
            llm: LLM manager
            rag: Optional RAG pipeline for context
            max_explanation_tokens: Max tokens in explanation
        """
        self.llm = llm
        self.rag = rag
        self.max_explanation_tokens = max_explanation_tokens

        logger.info("CommandExplainer initialized")

    def explain_command(
        self,
        command: str,
        include_context: bool = True,
        cwd: Optional[str] = None,
        detailed: bool = False,
    ) -> str:
        """
        Generate explanation for a command.

        Args:
            command: Shell command to explain
            include_context: Whether to include context from RAG
            cwd: Current working directory
            detailed: Whether to provide detailed explanation

        Returns:
            Natural language explanation

        Example:
            >>> explainer = CommandExplainer(llm, rag)
            >>> explanation = explainer.explain_command("ls -la")
            >>> print(explanation)
            "Lists all files and directories in long format, including hidden files."
        """
        if not command.strip():
            return "No command provided."

        # Build prompt
        if include_context and self.rag:
            prompt = self.rag.build_prompt(
                query=command,
                task_type="explain",
                cwd=cwd,
            )
        else:
            # Direct prompt without context
            prompt = self._build_simple_prompt(command, detailed)

        logger.debug(f"Explaining command: {command}")

        try:
            # Generate explanation
            explanation = self.llm.generate(
                prompt,
                max_tokens=self.max_explanation_tokens,
                temperature=0.3,  # Lower temperature for more focused explanations
                stop=["Command:", "Next command:"],
            )

            return explanation.strip()

        except Exception as e:
            logger.error(f"Failed to generate explanation: {e}")
            return f"Error generating explanation: {str(e)}"

    def explain_with_examples(
        self,
        command: str,
        cwd: Optional[str] = None,
    ) -> dict:
        """
        Generate explanation with usage examples.

        Args:
            command: Shell command to explain
            cwd: Current working directory

        Returns:
            Dictionary with 'explanation' and 'examples' keys

        Example:
            >>> result = explainer.explain_with_examples("git add")
            >>> print(result['explanation'])
            >>> for example in result['examples']:
            ...     print(f"  - {example}")
        """
        # Get explanation
        explanation = self.explain_command(command, cwd=cwd, detailed=True)

        # Generate examples
        examples_prompt = f"""Based on this command: {command}

Provide 3 common usage examples. Format as a numbered list.

Examples:"""

        try:
            examples_text = self.llm.generate(
                examples_prompt,
                max_tokens=200,
                temperature=0.5,
            )

            # Parse examples
            examples = [
                line.strip().lstrip("1234567890.-) ")
                for line in examples_text.split("\n")
                if line.strip() and any(c.isdigit() for c in line[:5])
            ]

        except Exception as e:
            logger.warning(f"Failed to generate examples: {e}")
            examples = []

        return {
            "explanation": explanation,
            "examples": examples,
        }

    def explain_error(
        self,
        command: str,
        error_message: str,
        exit_code: int,
    ) -> str:
        """
        Explain why a command failed.

        Args:
            command: Command that failed
            error_message: Error message from command
            exit_code: Exit code

        Returns:
            Explanation of the error

        Example:
            >>> explanation = explainer.explain_error(
            ...     "cat nonexistent.txt",
            ...     "No such file or directory",
            ...     1
            ... )
        """
        prompt = f"""A shell command failed. Explain what went wrong and how to fix it.

Command: {command}
Exit code: {exit_code}
Error message: {error_message}

Explanation:"""

        try:
            explanation = self.llm.generate(
                prompt,
                max_tokens=self.max_explanation_tokens,
                temperature=0.4,
            )

            return explanation.strip()

        except Exception as e:
            logger.error(f"Failed to explain error: {e}")
            return "Unable to generate error explanation."

    def _build_simple_prompt(self, command: str, detailed: bool) -> str:
        """
        Build a simple prompt without RAG context.

        Args:
            command: Command to explain
            detailed: Whether to be detailed

        Returns:
            Prompt string
        """
        if detailed:
            return f"""Explain this shell command in detail, including:
1. What it does
2. Common use cases
3. Important flags/options

Command: {command}

Explanation:"""
        else:
            return f"""Explain this shell command in one clear sentence.

Command: {command}

Explanation:"""

    def __repr__(self) -> str:
        """String representation."""
        return f"CommandExplainer(max_tokens={self.max_explanation_tokens})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("CommandExplainer example - requires LLM to be loaded")

    # Example output format:
    example_explanations = {
        "ls -la": {
            "explanation": "Lists all files and directories in the current directory in long format, including hidden files (those starting with '.'), showing detailed information like permissions, owner, size, and modification date.",
            "examples": [
                "ls -la /home/user  # List all files in a specific directory",
                "ls -la | grep config  # Find config files",
                "ls -lat | head  # Show 10 most recently modified files",
            ],
        },
        "git commit -m": {
            "explanation": "Creates a new commit in the Git repository with the specified commit message, saving the changes that have been staged with 'git add'.",
            "examples": [
                "git commit -m 'Add new feature'",
                "git commit -m 'Fix bug in login'",
                "git commit -am 'Quick fix'  # Add and commit in one step",
            ],
        },
    }

    print("\nExample command explanations:")
    for cmd, result in example_explanations.items():
        print(f"\nCommand: {cmd}")
        print(f"Explanation: {result['explanation']}")
        print("Examples:")
        for ex in result['examples']:
            print(f"  {ex}")
