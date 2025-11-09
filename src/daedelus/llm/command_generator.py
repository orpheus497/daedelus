"""
Command generation from natural language descriptions.

Uses LLM to generate appropriate shell commands from user intent.

Created by: orpheus497
"""

import logging
import re
from typing import List, Optional

from daedelus.llm.llm_manager import LLMManager
from daedelus.llm.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class CommandGenerator:
    """
    Generate shell commands from natural language descriptions.

    Uses LLM with RAG to generate contextually appropriate commands.

    Attributes:
        llm: LLM manager instance
        rag: RAG pipeline for context retrieval
        max_command_tokens: Maximum tokens for generated command
    """

    def __init__(
        self,
        llm: LLMManager,
        rag: Optional[RAGPipeline] = None,
        max_command_tokens: int = 100,
    ) -> None:
        """
        Initialize command generator.

        Args:
            llm: LLM manager
            rag: Optional RAG pipeline for context
            max_command_tokens: Max tokens in generated command
        """
        self.llm = llm
        self.rag = rag
        self.max_command_tokens = max_command_tokens

        logger.info("CommandGenerator initialized")

    def generate_command(
        self,
        description: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
        return_multiple: bool = False,
    ) -> str | List[str]:
        """
        Generate command from natural language description.

        Args:
            description: Natural language description of desired action
            cwd: Current working directory
            history: Recent command history for context
            return_multiple: Return multiple alternatives if True

        Returns:
            Generated command string, or list of alternatives

        Example:
            >>> generator = CommandGenerator(llm, rag)
            >>> cmd = generator.generate_command("find all python files")
            >>> print(cmd)
            "find . -name '*.py'"
        """
        if not description.strip():
            return [] if return_multiple else ""

        # Build prompt with context
        if self.rag:
            prompt = self.rag.build_prompt(
                query=description,
                task_type="generate",
                cwd=cwd,
                history=history,
            )

            if return_multiple:
                prompt += "\n\nProvide 3 alternative commands, one per line."
        else:
            prompt = self._build_simple_prompt(description, return_multiple)

        logger.debug(f"Generating command for: {description}")

        try:
            # Generate command(s)
            response = self.llm.generate(
                prompt,
                max_tokens=self.max_command_tokens,
                temperature=0.3,  # Lower temperature for precise commands
                stop=["Explanation:", "\n\n", "User:"],
            )

            # Parse response
            commands = self._parse_commands(response)

            if return_multiple:
                return commands[:3]  # Return up to 3 alternatives
            else:
                return commands[0] if commands else ""

        except Exception as e:
            logger.error(f"Failed to generate command: {e}")
            return [] if return_multiple else ""

    def generate_with_explanation(
        self,
        description: str,
        cwd: Optional[str] = None,
    ) -> dict:
        """
        Generate command with explanation.

        Args:
            description: Natural language description
            cwd: Current working directory

        Returns:
            Dictionary with 'command' and 'explanation' keys

        Example:
            >>> result = generator.generate_with_explanation("compress all logs")
            >>> print(f"Command: {result['command']}")
            >>> print(f"Explanation: {result['explanation']}")
        """
        # First generate command
        command = self.generate_command(description, cwd=cwd)

        if not command:
            return {"command": "", "explanation": "Could not generate command."}

        # Then generate explanation
        explain_prompt = f"""Briefly explain what this command does:

Command: {command}

Explanation (one sentence):"""

        try:
            explanation = self.llm.generate(
                explain_prompt,
                max_tokens=80,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(f"Failed to generate explanation: {e}")
            explanation = "No explanation available."

        return {
            "command": command,
            "explanation": explanation.strip(),
        }

    def refine_command(
        self,
        current_command: str,
        refinement: str,
        cwd: Optional[str] = None,
    ) -> str:
        """
        Refine an existing command based on feedback.

        Args:
            current_command: Current command
            refinement: Description of how to modify it
            cwd: Current working directory

        Returns:
            Refined command

        Example:
            >>> refined = generator.refine_command(
            ...     "ls",
            ...     "show hidden files too"
            ... )
            >>> print(refined)
            "ls -la"
        """
        prompt = f"""Modify this shell command according to the user's request.

Current command: {current_command}
User request: {refinement}

Modified command (only the command, no explanation):"""

        try:
            refined = self.llm.generate(
                prompt,
                max_tokens=self.max_command_tokens,
                temperature=0.2,  # Very low temperature for precise modifications
                stop=["\n", "Explanation:"],
            )

            # Clean up response
            refined = self._clean_command(refined)

            return refined if refined else current_command

        except Exception as e:
            logger.error(f"Failed to refine command: {e}")
            return current_command

    def complete_partial(
        self,
        partial_command: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Complete a partially typed command.

        Args:
            partial_command: Partially typed command
            cwd: Current working directory
            history: Recent command history

        Returns:
            List of possible completions

        Example:
            >>> completions = generator.complete_partial("git com")
            >>> print(completions)
            ["git commit", "git commit -m", "git commit -am"]
        """
        prompt = f"""Complete this partial shell command with the most likely completions.

Partial command: {partial_command}

Provide 3 possible completions, one per line (commands only, no explanations):"""

        try:
            response = self.llm.generate(
                prompt,
                max_tokens=100,
                temperature=0.4,
                stop=["\n\n"],
            )

            # Parse completions
            completions = self._parse_commands(response)

            # Filter to ensure they start with the partial
            valid_completions = [
                cmd for cmd in completions
                if cmd.startswith(partial_command.strip())
            ]

            return valid_completions[:3]

        except Exception as e:
            logger.error(f"Failed to complete command: {e}")
            return []

    def _build_simple_prompt(self, description: str, multiple: bool) -> str:
        """
        Build a simple prompt without RAG context.

        Args:
            description: Task description
            multiple: Whether to request multiple alternatives

        Returns:
            Prompt string
        """
        if multiple:
            return f"""Generate shell commands for this task. Provide 3 alternative approaches.

Task: {description}

Commands (one per line):"""
        else:
            return f"""Generate a shell command for this task.

Task: {description}

Command (only the command, no explanation):"""

    def _parse_commands(self, response: str) -> List[str]:
        """
        Parse commands from LLM response.

        Args:
            response: Raw LLM response

        Returns:
            List of cleaned commands
        """
        # Split by newlines
        lines = response.strip().split("\n")

        commands = []
        for line in lines:
            # Clean up line
            cleaned = self._clean_command(line)
            if cleaned:
                commands.append(cleaned)

        return commands

    def _clean_command(self, text: str) -> str:
        """
        Clean up a command string.

        Removes:
        - Numbering (1., 2., etc.)
        - Markdown code blocks (```)
        - Extra whitespace
        - Explanatory text after #

        Args:
            text: Raw command text

        Returns:
            Cleaned command
        """
        # Remove markdown code blocks
        text = re.sub(r'```(?:bash|sh|shell)?\n?', '', text)

        # Remove numbering
        text = re.sub(r'^\d+[\.\)]\s*', '', text.strip())

        # Remove bullet points
        text = re.sub(r'^[-*]\s*', '', text.strip())

        # Extract command (before any # comment that's clearly explanatory)
        # But preserve inline comments that are part of the command
        if ' #' in text and len(text.split(' #')[0]) > 3:
            text = text.split(' #')[0]

        # Clean up whitespace
        text = text.strip()

        # Validate it looks like a command
        if not text or len(text) < 2:
            return ""

        # Check it starts with a command-like word (not explanation)
        first_word = text.split()[0] if text.split() else ""
        if first_word.lower() in ["this", "the", "it", "command", "use", "try"]:
            return ""

        return text

    def __repr__(self) -> str:
        """String representation."""
        return f"CommandGenerator(max_tokens={self.max_command_tokens})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("CommandGenerator example - requires LLM to be loaded")

    # Example generation scenarios:
    examples = {
        "find all python files": "find . -name '*.py'",
        "show disk usage": "df -h",
        "compress folder into tar": "tar -czf archive.tar.gz folder/",
        "show running processes": "ps aux",
        "find files larger than 100MB": "find . -type f -size +100M",
    }

    print("\nExample command generations:")
    for description, expected_cmd in examples.items():
        print(f"\nDescription: {description}")
        print(f"Expected command: {expected_cmd}")

    print("\n\nExample with alternatives:")
    multi_example = {
        "description": "copy files to remote server",
        "alternatives": [
            "scp file.txt user@server:/path/",
            "rsync -av file.txt user@server:/path/",
            "sftp user@server",
        ],
    }
    print(f"Description: {multi_example['description']}")
    print("Alternatives:")
    for alt in multi_example['alternatives']:
        print(f"  - {alt}")
