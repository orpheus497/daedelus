"""
Command generation from natural language descriptions.

Uses LLM to generate appropriate shell commands from user intent.

Created by: orpheus497
"""

import logging
import re

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
        rag: RAGPipeline | None = None,
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
        cwd: str | None = None,
        history: list[str] | None = None,
        return_multiple: bool = False,
    ) -> str | list[str]:
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
                stop=["<|end|>", "<|user|>", "\n\n"],  # Phi-3 chat format stop sequences
            )

            # Log raw response for debugging
            logger.debug(f"Raw LLM response: {repr(response)}")

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
        cwd: str | None = None,
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

        # Then generate explanation (using Phi-3 chat format)
        explain_prompt = f"""<|system|>
You are a helpful Linux command expert. Explain commands briefly in one sentence.<|end|>
<|user|>
Briefly explain what this command does:

Command: {command}<|end|>
<|assistant|>
"""

        try:
            explanation = self.llm.generate(
                explain_prompt,
                max_tokens=80,
                temperature=0.3,
                stop=["<|end|>", "<|user|>"],
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
        cwd: str | None = None,
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
        # Format in Phi-3 chat format
        prompt = f"""<|system|>
You are a helpful Linux command expert. Modify shell commands as requested. Output only the modified command.<|end|>
<|user|>
Modify this shell command according to the user's request.

Current command: {current_command}
User request: {refinement}

Modified command:<|end|>
<|assistant|>
"""

        try:
            refined = self.llm.generate(
                prompt,
                max_tokens=self.max_command_tokens,
                temperature=0.2,  # Very low temperature for precise modifications
                stop=["<|end|>", "<|user|>", "\n"],
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
        cwd: str | None = None,
        history: list[str] | None = None,
    ) -> list[str]:
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
        # Format in Phi-3 chat format
        prompt = f"""<|system|>
You are a helpful Linux command expert. Complete partial commands. Output only completed commands, one per line.<|end|>
<|user|>
Complete this partial shell command with the most likely completions.

Partial command: {partial_command}

Provide 3 possible completions, one per line:<|end|>
<|assistant|>
"""

        try:
            response = self.llm.generate(
                prompt,
                max_tokens=100,
                temperature=0.4,
                stop=["<|end|>", "<|user|>"],
            )

            # Parse completions
            completions = self._parse_commands(response)

            # Filter to ensure they start with the partial
            valid_completions = [
                cmd for cmd in completions if cmd.startswith(partial_command.strip())
            ]

            return valid_completions[:3]

        except Exception as e:
            logger.error(f"Failed to complete command: {e}")
            return []

    def _build_simple_prompt(self, description: str, multiple: bool) -> str:
        """
        Build a simple prompt without RAG context.
        Uses Phi-3 chat format for proper model interaction.

        Args:
            description: Task description
            multiple: Whether to request multiple alternatives

        Returns:
            Prompt string in Phi-3 format
        """
        if multiple:
            user_message = f"Generate shell commands for this task. Provide 3 alternative approaches, one per line.\n\nTask: {description}"
        else:
            user_message = f"Generate a shell command for this task. Output only the command, no explanation or extra text.\n\nTask: {description}"

        # Format in Phi-3 chat format
        return f"""<|system|>
You are a helpful Linux command expert. Generate only valid shell commands, nothing else.<|end|>
<|user|>
{user_message}<|end|>
<|assistant|>
"""

    def _parse_commands(self, response: str) -> list[str]:
        """
        Parse commands from LLM response.

        Args:
            response: Raw LLM response

        Returns:
            List of cleaned commands
        """
        if not response or not response.strip():
            logger.warning("Empty response from LLM")
            return []

        # Split by newlines
        lines = response.strip().split("\n")

        commands = []
        for i, line in enumerate(lines):
            # Clean up line
            cleaned = self._clean_command(line)
            if cleaned:
                logger.debug(f"Parsed command {i+1}: {cleaned}")
                commands.append(cleaned)
            elif line.strip():
                # Log filtered lines for debugging
                logger.debug(f"Filtered line {i+1}: {repr(line)}")

        if not commands:
            logger.warning(f"No valid commands extracted from response: {repr(response)}")

        return commands

    def _clean_command(self, text: str) -> str:
        """
        Clean up a command string.

        Removes:
        - Numbering (1., 2., etc.)
        - Markdown code blocks (```)
        - Extra whitespace
        - Explanatory text after #
        - Common LLM prefixes

        Args:
            text: Raw command text

        Returns:
            Cleaned command
        """
        if not text:
            return ""

        # Extract commands from inline backticks (e.g., "use the `ls` command" -> "ls")
        backtick_match = re.search(r"`([^`]+)`", text)
        if backtick_match:
            # Found a command in backticks, use that
            text = backtick_match.group(1)

        # Remove markdown code blocks
        text = re.sub(r"```(?:bash|sh|shell)?\n?", "", text)

        # Remove numbering
        text = re.sub(r"^\d+[\.\)]\s*", "", text.strip())

        # Remove bullet points
        text = re.sub(r"^[-*]\s*", "", text.strip())

        # Remove common LLM prefixes like "Command:", "Use:", "Try:", etc.
        prefixes = [
            r"^command:\s*",
            r"^generated command:\s*",
            r"^the command is:\s*",
            r"^you can use:\s*",
            r"^use:\s*",
            r"^try:\s*",
            r"^run:\s*",
            r"^execute:\s*",
        ]
        for prefix in prefixes:
            text = re.sub(prefix, "", text.strip(), flags=re.IGNORECASE)

        # Extract command (before any # comment that's clearly explanatory)
        # But preserve inline comments that are part of the command
        if " #" in text and len(text.split(" #")[0]) > 3:
            text = text.split(" #")[0]

        # Clean up whitespace
        text = text.strip()

        # Validate it looks like a command (must have some content)
        if not text or len(text) < 2:
            return ""

        # Filter out explanatory text and natural language
        first_word = text.split()[0] if text.split() else ""

        # Filter obvious non-command text
        if first_word.lower() in ["this", "the", "it", "that", "these", "here", "a", "an"]:
            # Check if there's more after these words that looks like a command
            remaining = " ".join(text.split()[1:]) if len(text.split()) > 1 else ""
            if remaining and len(remaining) > 2:
                # Check if the remaining text starts with a typical command word
                remaining_first = remaining.split()[0].lower() if remaining.split() else ""
                # If it's still explanatory (like "command lists..."), filter it
                if remaining_first in ["command", "will", "can", "should", "would", "lists", "shows", "displays"]:
                    return ""
                text = remaining.strip()
            else:
                return ""

        # Additional check: if text looks like natural language explanation, filter it
        # Commands typically don't have common English words like "lists", "shows", "displays" as the command name
        if first_word.lower() in ["lists", "shows", "displays", "prints", "creates", "removes", "deletes",
                                  "will", "can", "should", "would", "could", "might", "may"]:
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
    for alt in multi_example["alternatives"]:
        print(f"  - {alt}")
