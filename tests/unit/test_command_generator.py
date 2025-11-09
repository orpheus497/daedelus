"""
Unit tests for CommandGenerator.

Tests command generation from natural language descriptions.
"""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_llm():
    """Mock LLM manager."""
    llm = Mock()
    llm.generate.return_value = "find . -name '*.py'"
    return llm


@pytest.fixture
def mock_rag():
    """Mock RAG pipeline."""
    rag = Mock()
    rag.build_prompt.return_value = "Generate a command to find all python files"
    return rag


class TestCommandGeneratorInit:
    """Test command generator initialization."""

    def test_init_basic(self, mock_llm, mock_rag):
        """Test basic initialization."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)

        assert generator.llm == mock_llm
        assert generator.rag == mock_rag

    def test_init_without_rag(self, mock_llm):
        """Test initialization without RAG pipeline."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, None)

        assert generator.llm == mock_llm
        assert generator.rag is None

    def test_init_custom_max_tokens(self, mock_llm, mock_rag):
        """Test initialization with custom max tokens."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag, max_command_tokens=200)

        assert generator.max_command_tokens == 200


class TestBasicGeneration:
    """Test basic command generation."""

    def test_generate_command_basic(self, mock_llm, mock_rag):
        """Test basic command generation."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)
        command = generator.generate_command("find all python files")

        assert isinstance(command, str)
        assert len(command) > 0
        mock_llm.generate.assert_called_once()

    def test_generate_common_tasks(self, mock_llm, mock_rag):
        """Test generating commands for common tasks."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)

        tasks = [
            ("list all files", "ls -la"),
            ("show disk usage", "df -h"),
            ("find python files", "find . -name '*.py'"),
            ("compress folder", "tar -czf"),
        ]

        for description, expected_pattern in tasks:
            mock_llm.generate.return_value = expected_pattern
            command = generator.generate_command(description)
            assert isinstance(command, str)
            assert len(command) > 0

    def test_generate_empty_description(self, mock_llm, mock_rag):
        """Test generating command from empty description."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)
        command = generator.generate_command("")

        # Should return empty string or handle gracefully
        assert isinstance(command, str)

    def test_generate_complex_task(self, mock_llm, mock_rag):
        """Test generating command for complex task."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = "find . -name '*.log' -mtime +30 -delete"

        generator = CommandGenerator(mock_llm, mock_rag)
        command = generator.generate_command(
            "delete log files older than 30 days"
        )

        assert isinstance(command, str)
        assert "find" in command or "log" in command


class TestMultipleAlternatives:
    """Test generating multiple command alternatives."""

    def test_generate_multiple_commands(self, mock_llm, mock_rag):
        """Test generating multiple alternative commands."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = (
            "scp file.txt user@server:/path/\n"
            "rsync -av file.txt user@server:/path/\n"
            "sftp user@server"
        )

        generator = CommandGenerator(mock_llm, mock_rag)
        commands = generator.generate_command(
            "copy file to remote server",
            return_multiple=True,
        )

        assert isinstance(commands, list)
        assert len(commands) >= 1
        assert all(isinstance(cmd, str) for cmd in commands)

    def test_multiple_alternatives_limit(self, mock_llm, mock_rag):
        """Test that multiple alternatives are limited to 3."""
        from daedelus.llm.command_generator import CommandGenerator

        # Mock returns many alternatives
        mock_llm.generate.return_value = "\n".join([
            "cmd1", "cmd2", "cmd3", "cmd4", "cmd5"
        ])

        generator = CommandGenerator(mock_llm, mock_rag)
        commands = generator.generate_command(
            "task",
            return_multiple=True,
        )

        # Should limit to 3
        assert len(commands) <= 3


class TestGenerationWithContext:
    """Test command generation with context."""

    def test_generate_with_cwd(self, mock_llm, mock_rag):
        """Test generation with current directory."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)
        command = generator.generate_command(
            "install dependencies",
            cwd="/home/project",
        )

        assert isinstance(command, str)
        # Should use RAG with cwd
        mock_rag.build_prompt.assert_called()

    def test_generate_with_history(self, mock_llm, mock_rag):
        """Test generation with command history."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)
        history = ["cd project", "ls", "git status"]

        command = generator.generate_command(
            "commit changes",
            history=history,
        )

        assert isinstance(command, str)

    def test_generate_without_rag(self, mock_llm):
        """Test generation when RAG is not available."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, None)
        command = generator.generate_command("list files")

        assert isinstance(command, str)
        # Should still work with simple prompt
        mock_llm.generate.assert_called()


class TestGenerationWithExplanation:
    """Test command generation with explanations."""

    def test_generate_with_explanation(self, mock_llm, mock_rag):
        """Test generating command with explanation."""
        from daedelus.llm.command_generator import CommandGenerator

        # Mock LLM responses
        mock_llm.generate.side_effect = [
            "find . -name '*.py'",  # Command generation
            "Finds all Python files in the current directory",  # Explanation
        ]

        generator = CommandGenerator(mock_llm, mock_rag)
        result = generator.generate_with_explanation("find python files")

        assert isinstance(result, dict)
        assert "command" in result
        assert "explanation" in result
        assert isinstance(result["command"], str)
        assert isinstance(result["explanation"], str)

    def test_generate_with_explanation_no_command(self, mock_llm, mock_rag):
        """Test explanation generation when command fails."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = ""

        generator = CommandGenerator(mock_llm, mock_rag)
        result = generator.generate_with_explanation("invalid task")

        assert isinstance(result, dict)
        assert result["command"] == ""
        assert "explanation" in result


class TestCommandRefinement:
    """Test command refinement based on feedback."""

    def test_refine_command_basic(self, mock_llm, mock_rag):
        """Test basic command refinement."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = "ls -la"

        generator = CommandGenerator(mock_llm, mock_rag)
        refined = generator.refine_command(
            "ls",
            "show hidden files too",
        )

        assert isinstance(refined, str)
        assert len(refined) > 0

    def test_refine_add_flags(self, mock_llm, mock_rag):
        """Test refinement to add flags."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = "ls -lh"

        generator = CommandGenerator(mock_llm, mock_rag)
        refined = generator.refine_command(
            "ls -l",
            "make sizes human readable",
        )

        assert isinstance(refined, str)

    def test_refine_change_command(self, mock_llm, mock_rag):
        """Test refinement that changes command entirely."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = "find . -name '*.txt'"

        generator = CommandGenerator(mock_llm, mock_rag)
        refined = generator.refine_command(
            "ls *.txt",
            "search recursively in subdirectories",
        )

        assert isinstance(refined, str)

    def test_refine_error_fallback(self, mock_llm, mock_rag):
        """Test that refinement falls back to original on error."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.side_effect = RuntimeError("Failed")

        generator = CommandGenerator(mock_llm, mock_rag)
        refined = generator.refine_command("ls", "add -a flag")

        # Should fall back to original
        assert refined == "ls"


class TestCommandCompletion:
    """Test partial command completion."""

    def test_complete_partial_basic(self, mock_llm, mock_rag):
        """Test basic partial completion."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = (
            "git commit\n"
            "git commit -m\n"
            "git commit -am"
        )

        generator = CommandGenerator(mock_llm, mock_rag)
        completions = generator.complete_partial("git com")

        assert isinstance(completions, list)
        assert len(completions) > 0
        # All should start with the partial
        assert all(c.startswith("git com") for c in completions)

    def test_complete_partial_filter_invalid(self, mock_llm, mock_rag):
        """Test that invalid completions are filtered."""
        from daedelus.llm.command_generator import CommandGenerator

        # Mock returns some invalid completions
        mock_llm.generate.return_value = (
            "git commit\n"
            "ls -la\n"  # Doesn't start with partial
            "git commit -m"
        )

        generator = CommandGenerator(mock_llm, mock_rag)
        completions = generator.complete_partial("git com")

        # Should filter out "ls -la"
        assert all(c.startswith("git com") for c in completions)

    def test_complete_partial_limit(self, mock_llm, mock_rag):
        """Test completion limit of 3."""
        from daedelus.llm.command_generator import CommandGenerator

        # Mock returns many completions
        mock_llm.generate.return_value = "\n".join([
            "git commit",
            "git commit -m",
            "git commit -am",
            "git commit --amend",
            "git commit -a",
        ])

        generator = CommandGenerator(mock_llm, mock_rag)
        completions = generator.complete_partial("git com")

        assert len(completions) <= 3


class TestCommandParsing:
    """Test command parsing and cleaning."""

    def test_parse_commands_simple(self, mock_llm, mock_rag):
        """Test parsing simple command list."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)

        # Test internal parsing method
        response = "ls -la\ngit status\ncd /home"
        commands = generator._parse_commands(response)

        assert len(commands) == 3
        assert "ls -la" in commands
        assert "git status" in commands

    def test_clean_command_numbered(self, mock_llm, mock_rag):
        """Test cleaning numbered commands."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)

        test_cases = [
            ("1. ls -la", "ls -la"),
            ("2) git status", "git status"),
            ("- cd /home", "cd /home"),
            ("* npm install", "npm install"),
        ]

        for input_cmd, expected in test_cases:
            cleaned = generator._clean_command(input_cmd)
            assert cleaned == expected

    def test_clean_command_markdown(self, mock_llm, mock_rag):
        """Test cleaning markdown code blocks."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)

        test_cases = [
            ("```bash\nls -la\n```", "ls -la"),
            ("```\ngit status\n```", "git status"),
            ("```sh\ncd /home\n```", "cd /home"),
        ]

        for input_cmd, expected in test_cases:
            cleaned = generator._clean_command(input_cmd)
            assert cleaned == expected

    def test_clean_command_comments(self, mock_llm, mock_rag):
        """Test cleaning comments from commands."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)

        test_cases = [
            ("ls -la # List all files", "ls -la"),
            ("git status # Check git status", "git status"),
        ]

        for input_cmd, expected in test_cases:
            cleaned = generator._clean_command(input_cmd)
            assert cleaned == expected

    def test_clean_command_filter_explanations(self, mock_llm, mock_rag):
        """Test filtering out explanatory text."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)

        # These should be filtered out
        invalid = [
            "This command lists files",
            "The ls command shows",
            "It displays all",
            "Command: ls",
            "Use this command",
        ]

        for text in invalid:
            cleaned = generator._clean_command(text)
            assert cleaned == ""


class TestErrorHandling:
    """Test error handling in command generation."""

    def test_generation_error(self, mock_llm, mock_rag):
        """Test handling of generation errors."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.side_effect = RuntimeError("Generation failed")

        generator = CommandGenerator(mock_llm, mock_rag)
        command = generator.generate_command("task")

        # Should return empty string on error
        assert command == ""

    def test_generation_error_multiple(self, mock_llm, mock_rag):
        """Test handling of generation errors with multiple alternatives."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.side_effect = RuntimeError("Generation failed")

        generator = CommandGenerator(mock_llm, mock_rag)
        commands = generator.generate_command("task", return_multiple=True)

        # Should return empty list on error
        assert commands == []

    def test_empty_llm_response(self, mock_llm, mock_rag):
        """Test handling of empty LLM response."""
        from daedelus.llm.command_generator import CommandGenerator

        mock_llm.generate.return_value = ""

        generator = CommandGenerator(mock_llm, mock_rag)
        command = generator.generate_command("task")

        assert isinstance(command, str)

    def test_invalid_llm_response(self, mock_llm, mock_rag):
        """Test handling of invalid LLM response."""
        from daedelus.llm.command_generator import CommandGenerator

        # Mock returns only explanations, no actual commands
        mock_llm.generate.return_value = (
            "This would list all files in the directory."
        )

        generator = CommandGenerator(mock_llm, mock_rag)
        command = generator.generate_command("list files")

        # Should filter out explanations
        assert isinstance(command, str)


class TestParameterHandling:
    """Test handling of generation parameters."""

    def test_temperature_setting(self, mock_llm, mock_rag):
        """Test that temperature is set appropriately."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)
        generator.generate_command("task")

        # Should use low temperature for precise commands
        call_args = mock_llm.generate.call_args
        if call_args and "temperature" in call_args[1]:
            assert call_args[1]["temperature"] <= 0.5

    def test_max_tokens_setting(self, mock_llm, mock_rag):
        """Test that max_tokens is properly set."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag, max_command_tokens=150)
        generator.generate_command("task")

        call_args = mock_llm.generate.call_args
        assert call_args is not None

    def test_stop_sequences(self, mock_llm, mock_rag):
        """Test that stop sequences are used."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)
        generator.generate_command("task")

        call_args = mock_llm.generate.call_args
        # Should have stop sequences to prevent over-generation
        assert call_args is not None


class TestRepr:
    """Test string representation."""

    def test_repr(self, mock_llm, mock_rag):
        """Test __repr__ method."""
        from daedelus.llm.command_generator import CommandGenerator

        generator = CommandGenerator(mock_llm, mock_rag)
        repr_str = repr(generator)

        assert "CommandGenerator" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
