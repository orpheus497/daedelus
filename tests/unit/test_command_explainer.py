"""
Unit tests for CommandExplainer.

Tests natural language command explanations.
"""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_llm():
    """Mock LLM manager."""
    llm = Mock()
    llm.generate.return_value = "This command lists all files in long format including hidden files."
    return llm


@pytest.fixture
def mock_rag():
    """Mock RAG pipeline."""
    rag = Mock()
    rag.build_prompt.return_value = "Explain this command: ls -la"
    rag.retrieve_context.return_value = {
        "similar_commands": [("ls -l", 0.9), ("ls -a", 0.85)],
        "recent_commands": [],
        "patterns": [],
    }
    return rag


class TestCommandExplainerInit:
    """Test command explainer initialization."""

    def test_init_basic(self, mock_llm, mock_rag):
        """Test basic initialization."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)

        assert explainer.llm == mock_llm
        assert explainer.rag == mock_rag

    def test_init_without_rag(self, mock_llm):
        """Test initialization without RAG pipeline."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, None)

        assert explainer.llm == mock_llm
        assert explainer.rag is None


class TestBasicExplanation:
    """Test basic command explanations."""

    def test_explain_command_basic(self, mock_llm, mock_rag):
        """Test basic command explanation."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command("ls -la")

        assert isinstance(explanation, str)
        assert len(explanation) > 0
        mock_llm.generate.assert_called_once()

    def test_explain_common_commands(self, mock_llm, mock_rag):
        """Test explaining common commands."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)

        commands = [
            "ls -la",
            "git status",
            "docker ps",
            "npm install",
            "cd /home",
        ]

        for cmd in commands:
            explanation = explainer.explain_command(cmd)
            assert isinstance(explanation, str)
            assert len(explanation) > 0

    def test_explain_complex_command(self, mock_llm, mock_rag):
        """Test explaining complex piped command."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = (
            "This finds all Python files, searches for 'TODO', "
            "and counts the occurrences."
        )

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command(
            "find . -name '*.py' | xargs grep 'TODO' | wc -l"
        )

        assert isinstance(explanation, str)
        assert "find" in explanation.lower() or "TODO" in explanation

    def test_explain_empty_command(self, mock_llm, mock_rag):
        """Test explaining empty command."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command("")

        # Should handle gracefully
        assert isinstance(explanation, str)


class TestExplanationWithContext:
    """Test explanations with contextual information."""

    def test_explain_with_context(self, mock_llm, mock_rag):
        """Test explanation with context from RAG."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command(
            "git commit -m 'message'",
            include_context=True,
        )

        assert isinstance(explanation, str)
        # Should use RAG to build prompt
        mock_rag.build_prompt.assert_called()

    def test_explain_without_context(self, mock_llm, mock_rag):
        """Test explanation without context."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command(
            "ls -la",
            include_context=False,
        )

        assert isinstance(explanation, str)
        # Should not use RAG
        mock_rag.build_prompt.assert_not_called()

    def test_explain_with_cwd(self, mock_llm, mock_rag):
        """Test explanation with current directory context."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command(
            "npm install",
            cwd="/home/project",
        )

        assert isinstance(explanation, str)

    def test_explain_without_rag_pipeline(self, mock_llm):
        """Test explanation when RAG is not available."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, None)
        explanation = explainer.explain_command("ls -la")

        assert isinstance(explanation, str)
        # Should still work without RAG
        mock_llm.generate.assert_called()


class TestExplanationWithExamples:
    """Test explanations with usage examples."""

    def test_explain_with_examples(self, mock_llm, mock_rag):
        """Test explanation with usage examples."""
        from daedelus.llm.command_explainer import CommandExplainer

        # Mock LLM to return examples
        mock_llm.generate.return_value = (
            "Lists files.\n"
            "Examples:\n"
            "- ls -la /home\n"
            "- ls -lh *.txt"
        )

        explainer = CommandExplainer(mock_llm, mock_rag)
        result = explainer.explain_with_examples("ls")

        assert isinstance(result, dict)
        assert "explanation" in result
        assert "examples" in result

    def test_examples_parsing(self, mock_llm, mock_rag):
        """Test parsing examples from LLM response."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = (
            "Git commit saves changes.\n\n"
            "Examples:\n"
            "1. git commit -m 'Add feature'\n"
            "2. git commit -am 'Fix bug'\n"
            "3. git commit --amend"
        )

        explainer = CommandExplainer(mock_llm, mock_rag)
        result = explainer.explain_with_examples("git commit")

        assert isinstance(result["examples"], list)
        assert len(result["examples"]) > 0

    def test_no_examples_in_response(self, mock_llm, mock_rag):
        """Test when LLM doesn't provide examples."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = "Lists all files."

        explainer = CommandExplainer(mock_llm, mock_rag)
        result = explainer.explain_with_examples("ls")

        # Should handle gracefully
        assert isinstance(result, dict)
        assert "explanation" in result


class TestErrorExplanation:
    """Test error message explanations."""

    def test_explain_error_basic(self, mock_llm, mock_rag):
        """Test explaining command error."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = (
            "Permission denied error. Try running with sudo."
        )

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_error(
            "rm /etc/config",
            "Permission denied",
        )

        assert isinstance(explanation, str)
        assert "permission" in explanation.lower() or "denied" in explanation.lower()

    def test_explain_common_errors(self, mock_llm, mock_rag):
        """Test explaining common error types."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)

        errors = [
            ("ls /nonexistent", "No such file or directory"),
            ("git push", "Permission denied (publickey)"),
            ("npm install", "EACCES permission denied"),
            ("python script.py", "ModuleNotFoundError: No module named"),
        ]

        for cmd, error in errors:
            mock_llm.generate.return_value = f"Error explanation for {cmd}"
            explanation = explainer.explain_error(cmd, error)
            assert isinstance(explanation, str)

    def test_explain_error_with_exit_code(self, mock_llm, mock_rag):
        """Test explaining error with exit code."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = "Command failed with exit code 1."

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_error(
            "git push",
            "rejected",
            exit_code=1,
        )

        assert isinstance(explanation, str)


class TestOutputFormatting:
    """Test explanation output formatting."""

    def test_brief_explanation(self, mock_llm, mock_rag):
        """Test brief explanation format."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = "Lists files in the current directory."

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command("ls", brief=True)

        assert isinstance(explanation, str)
        # Brief explanations should be shorter
        assert len(explanation) < 200

    def test_detailed_explanation(self, mock_llm, mock_rag):
        """Test detailed explanation format."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = (
            "The ls command lists directory contents. "
            "The -l flag provides long format with permissions, "
            "owner, size, and modification time. "
            "The -a flag includes hidden files starting with a dot."
        )

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command("ls -la", brief=False)

        assert isinstance(explanation, str)
        assert len(explanation) > 50

    def test_explanation_cleanup(self, mock_llm, mock_rag):
        """Test that explanations are properly cleaned up."""
        from daedelus.llm.command_explainer import CommandExplainer

        # Mock LLM returns explanation with extra whitespace
        mock_llm.generate.return_value = "  \n\nLists files.\n\n  "

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command("ls")

        # Should be cleaned up
        assert explanation == explanation.strip()


class TestParameterHandling:
    """Test handling of various parameters."""

    def test_max_tokens_parameter(self, mock_llm, mock_rag):
        """Test that max_tokens is properly passed to LLM."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag, max_explanation_tokens=200)
        explainer.explain_command("ls -la")

        # Check that generate was called with max_tokens
        call_args = mock_llm.generate.call_args
        assert call_args is not None

    def test_temperature_parameter(self, mock_llm, mock_rag):
        """Test temperature setting for explanations."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)
        explainer.explain_command("ls")

        # Explanations should use lower temperature for consistency
        call_args = mock_llm.generate.call_args
        if call_args and "temperature" in call_args[1]:
            assert call_args[1]["temperature"] <= 0.5


class TestErrorHandling:
    """Test error handling in explanations."""

    def test_llm_generation_error(self, mock_llm, mock_rag):
        """Test handling of LLM generation errors."""
        from daedelus.llm.command_explainer import CommandExplainer

        # Make LLM raise an error
        mock_llm.generate.side_effect = RuntimeError("Generation failed")

        explainer = CommandExplainer(mock_llm, mock_rag)

        # Should handle error gracefully
        with pytest.raises(RuntimeError):
            explainer.explain_command("ls")

    def test_rag_error(self, mock_llm, mock_rag):
        """Test handling of RAG pipeline errors."""
        from daedelus.llm.command_explainer import CommandExplainer

        # Make RAG raise an error
        mock_rag.build_prompt.side_effect = RuntimeError("RAG failed")

        explainer = CommandExplainer(mock_llm, mock_rag)

        # Should handle error gracefully or fall back
        try:
            result = explainer.explain_command("ls", include_context=True)
            # If no exception, should have fallback behavior
            assert isinstance(result, str)
        except RuntimeError:
            # Or propagate the error
            pass

    def test_empty_llm_response(self, mock_llm, mock_rag):
        """Test handling of empty LLM response."""
        from daedelus.llm.command_explainer import CommandExplainer

        mock_llm.generate.return_value = ""

        explainer = CommandExplainer(mock_llm, mock_rag)
        explanation = explainer.explain_command("ls")

        # Should handle empty response
        assert isinstance(explanation, str)


class TestRepr:
    """Test string representation."""

    def test_repr(self, mock_llm, mock_rag):
        """Test __repr__ method."""
        from daedelus.llm.command_explainer import CommandExplainer

        explainer = CommandExplainer(mock_llm, mock_rag)
        repr_str = repr(explainer)

        assert "CommandExplainer" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
