"""
Unit tests for EnhancedSuggestionEngine.

Tests integration of Phase 1 (embeddings) and Phase 2 (LLM).
"""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_base_engine():
    """Mock Phase 1 suggestion engine."""
    engine = Mock()
    engine.max_suggestions = 5
    engine.get_suggestions.return_value = [
        {"command": "ls -la", "confidence": 0.95, "source": "exact_prefix"},
        {"command": "ls -lh", "confidence": 0.88, "source": "semantic"},
        {"command": "ls -lt", "confidence": 0.82, "source": "contextual"},
    ]
    return engine


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
    rag.build_prompt.return_value = "Test prompt"
    return rag


@pytest.fixture
def mock_command_generator():
    """Mock command generator."""
    generator = Mock()
    generator.generate_command.return_value = "find . -name '*.py'"
    generator.generate_with_explanation.return_value = {
        "command": "find . -name '*.py'",
        "explanation": "Finds all Python files",
    }
    return generator


@pytest.fixture
def mock_command_explainer():
    """Mock command explainer."""
    explainer = Mock()
    explainer.explain_command.return_value = "Lists files in long format"
    return explainer


class TestEnhancedSuggestionEngineInit:
    """Test enhanced suggestion engine initialization."""

    def test_init_with_llm(self, mock_base_engine, mock_llm, mock_rag):
        """Test initialization with LLM enabled."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"), \
             patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
            engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)

            assert engine.base_engine == mock_base_engine
            assert engine.llm == mock_llm
            assert engine.rag == mock_rag
            assert engine.llm_enabled is True

    def test_init_without_llm(self, mock_base_engine):
        """Test initialization without LLM (Phase 1 only)."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        engine = EnhancedSuggestionEngine(mock_base_engine, None, None)

        assert engine.base_engine == mock_base_engine
        assert engine.llm is None
        assert engine.rag is None
        assert engine.llm_enabled is False
        assert engine.command_generator is None
        assert engine.command_explainer is None


class TestBasicSuggestions:
    """Test basic suggestion retrieval."""

    def test_get_suggestions_phase1_only(self, mock_base_engine):
        """Test suggestions with Phase 1 only (no LLM)."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        engine = EnhancedSuggestionEngine(mock_base_engine, None, None)
        suggestions = engine.get_suggestions("ls")

        assert isinstance(suggestions, list)
        assert len(suggestions) == 3
        mock_base_engine.get_suggestions.assert_called_once()

    def test_get_suggestions_llm_disabled(self, mock_base_engine, mock_llm, mock_rag):
        """Test suggestions with LLM disabled via parameter."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"), \
             patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
            engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
            suggestions = engine.get_suggestions("ls", use_llm=False)

            assert isinstance(suggestions, list)
            # Should use Phase 1 only
            mock_base_engine.get_suggestions.assert_called()

    def test_get_suggestions_with_context(self, mock_base_engine):
        """Test suggestions with context (cwd, history)."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        engine = EnhancedSuggestionEngine(mock_base_engine, None, None)
        suggestions = engine.get_suggestions(
            "git",
            cwd="/home/project",
            history=["ls", "cd project"],
            context_window=10,
        )

        assert isinstance(suggestions, list)
        # Check that context was passed to base engine
        call_args = mock_base_engine.get_suggestions.call_args
        assert call_args[0][1] == "/home/project"  # cwd
        assert call_args[0][2] == ["ls", "cd project"]  # history


class TestNaturalLanguageDetection:
    """Test natural language query detection."""

    def test_is_natural_language_true_cases(self, mock_base_engine, mock_llm, mock_rag):
        """Test detection of natural language queries."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"), \
             patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
            engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)

            natural_language_queries = [
                "find all python files",
                "show me log files",
                "list all directories with images",
                "how to compress a folder",
                "find all files containing error",
            ]

            for query in natural_language_queries:
                assert engine._is_natural_language(query) is True

    def test_is_natural_language_false_cases(self, mock_base_engine, mock_llm, mock_rag):
        """Test detection of command-like inputs."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"), \
             patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
            engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)

            command_like_inputs = [
                "ls -la",
                "git status",
                "docker ps",
                "npm install",
                "cd /home",
            ]

            for query in command_like_inputs:
                assert engine._is_natural_language(query) is False

    def test_is_natural_language_edge_cases(self, mock_base_engine, mock_llm, mock_rag):
        """Test edge cases in natural language detection."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"), \
             patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
            engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)

            # Short queries (less than 3 words)
            assert engine._is_natural_language("ls") is False
            assert engine._is_natural_language("git com") is False

            # Empty or single word
            assert engine._is_natural_language("") is False
            assert engine._is_natural_language("hello") is False


class TestLLMEnhancedSuggestions:
    """Test LLM-enhanced suggestions."""

    def test_suggestions_with_natural_language(self, mock_base_engine, mock_llm, mock_rag):
        """Test suggestions for natural language query."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine
        from daedelus.llm.command_generator import CommandGenerator

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator") as MockGen:
            mock_gen_instance = Mock()
            mock_gen_instance.generate_command.return_value = "find . -name '*.py'"
            MockGen.return_value = mock_gen_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                suggestions = engine.get_suggestions("find all python files")

                assert isinstance(suggestions, list)
                assert len(suggestions) > 0

                # Should have LLM-generated command first
                assert suggestions[0]["source"] == "llm_generation"
                assert suggestions[0]["confidence"] == 0.9

    def test_suggestions_deduplication(self, mock_base_engine, mock_llm, mock_rag):
        """Test deduplication of LLM and Phase 1 suggestions."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        # Base engine returns "ls -la"
        mock_base_engine.get_suggestions.return_value = [
            {"command": "ls -la", "confidence": 0.95, "source": "exact"},
            {"command": "ls -lh", "confidence": 0.88, "source": "semantic"},
        ]

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator") as MockGen:
            # LLM also generates "ls -la" (duplicate)
            mock_gen_instance = Mock()
            mock_gen_instance.generate_command.return_value = "ls -la"
            MockGen.return_value = mock_gen_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                suggestions = engine.get_suggestions("list all files")

                # Should deduplicate
                commands = [s["command"] for s in suggestions]
                assert commands.count("ls -la") == 1


class TestCommandGeneration:
    """Test command generation via LLM."""

    def test_generate_command_basic(self, mock_base_engine, mock_llm, mock_rag):
        """Test basic command generation."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator") as MockGen:
            mock_gen_instance = Mock()
            mock_gen_instance.generate_with_explanation.return_value = {
                "command": "tar -czf archive.tar.gz folder/",
                "explanation": "Compresses folder into tar.gz",
            }
            MockGen.return_value = mock_gen_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                result = engine.generate_command("compress folder")

                assert isinstance(result, dict)
                assert result["command"] == "tar -czf archive.tar.gz folder/"
                assert "explanation" in result
                assert result["source"] == "llm_generation"

    def test_generate_command_without_llm(self, mock_base_engine):
        """Test command generation when LLM is not available."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        engine = EnhancedSuggestionEngine(mock_base_engine, None, None)
        result = engine.generate_command("compress folder")

        assert result is None

    def test_generate_command_with_context(self, mock_base_engine, mock_llm, mock_rag):
        """Test command generation with context."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator") as MockGen:
            mock_gen_instance = Mock()
            mock_gen_instance.generate_with_explanation.return_value = {
                "command": "npm install",
                "explanation": "Installs dependencies",
            }
            MockGen.return_value = mock_gen_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                result = engine.generate_command(
                    "install dependencies",
                    cwd="/home/project",
                    history=["cd project"],
                )

                assert isinstance(result, dict)


class TestCommandExplanation:
    """Test command explanation via LLM."""

    def test_explain_command_basic(self, mock_base_engine, mock_llm, mock_rag):
        """Test basic command explanation."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandExplainer") as MockExp:
            mock_exp_instance = Mock()
            mock_exp_instance.explain_command.return_value = "Lists all files in long format"
            MockExp.return_value = mock_exp_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                explanation = engine.explain_command("ls -la")

                assert isinstance(explanation, str)
                assert "Lists all files" in explanation

    def test_explain_command_without_llm(self, mock_base_engine):
        """Test command explanation when LLM is not available."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        engine = EnhancedSuggestionEngine(mock_base_engine, None, None)
        explanation = engine.explain_command("ls -la")

        assert "not available" in explanation or "disabled" in explanation

    def test_explain_command_with_cwd(self, mock_base_engine, mock_llm, mock_rag):
        """Test command explanation with current directory."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandExplainer") as MockExp:
            mock_exp_instance = Mock()
            mock_exp_instance.explain_command.return_value = "Explanation"
            MockExp.return_value = mock_exp_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                explanation = engine.explain_command("npm install", cwd="/home/project")

                assert isinstance(explanation, str)
                # Should pass cwd to explainer
                mock_exp_instance.explain_command.assert_called_with(
                    "npm install", cwd="/home/project"
                )


class TestErrorHandling:
    """Test error handling in enhanced suggestions."""

    def test_llm_error_fallback_to_phase1(self, mock_base_engine, mock_llm, mock_rag):
        """Test fallback to Phase 1 when LLM fails."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator") as MockGen:
            # Make generator raise an error
            mock_gen_instance = Mock()
            mock_gen_instance.generate_command.side_effect = RuntimeError("LLM failed")
            MockGen.return_value = mock_gen_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                suggestions = engine.get_suggestions("find all files")

                # Should fall back to Phase 1
                assert isinstance(suggestions, list)
                assert len(suggestions) > 0

    def test_generation_error_returns_none(self, mock_base_engine, mock_llm, mock_rag):
        """Test that generation errors return None."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator") as MockGen:
            mock_gen_instance = Mock()
            mock_gen_instance.generate_with_explanation.side_effect = RuntimeError("Failed")
            MockGen.return_value = mock_gen_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                result = engine.generate_command("task")

                assert result is None

    def test_explanation_error_returns_error_message(self, mock_base_engine, mock_llm, mock_rag):
        """Test that explanation errors return error message."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandExplainer") as MockExp:
            mock_exp_instance = Mock()
            mock_exp_instance.explain_command.side_effect = RuntimeError("Explain failed")
            MockExp.return_value = mock_exp_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                explanation = engine.explain_command("ls")

                assert isinstance(explanation, str)
                assert "Error" in explanation


class TestSuggestionLimits:
    """Test suggestion limits and ranking."""

    def test_max_suggestions_limit(self, mock_base_engine, mock_llm, mock_rag):
        """Test that suggestions are limited to max_suggestions."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        # Base engine has max_suggestions = 5
        mock_base_engine.max_suggestions = 5

        # Return many suggestions from Phase 1
        mock_base_engine.get_suggestions.return_value = [
            {"command": f"cmd{i}", "confidence": 0.9 - i*0.1, "source": "test"}
            for i in range(10)
        ]

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator") as MockGen:
            mock_gen_instance = Mock()
            mock_gen_instance.generate_command.return_value = "llm_cmd"
            MockGen.return_value = mock_gen_instance

            with patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
                engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
                suggestions = engine.get_suggestions("find all files")

                # Should limit to max_suggestions
                assert len(suggestions) <= 5


class TestRepr:
    """Test string representation."""

    def test_repr_with_llm(self, mock_base_engine, mock_llm, mock_rag):
        """Test __repr__ with LLM enabled."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        with patch("daedelus.llm.enhanced_suggestions.CommandGenerator"), \
             patch("daedelus.llm.enhanced_suggestions.CommandExplainer"):
            engine = EnhancedSuggestionEngine(mock_base_engine, mock_llm, mock_rag)
            repr_str = repr(engine)

            assert "EnhancedSuggestionEngine" in repr_str
            assert "enabled" in repr_str

    def test_repr_without_llm(self, mock_base_engine):
        """Test __repr__ with LLM disabled."""
        from daedelus.llm.enhanced_suggestions import EnhancedSuggestionEngine

        engine = EnhancedSuggestionEngine(mock_base_engine, None, None)
        repr_str = repr(engine)

        assert "EnhancedSuggestionEngine" in repr_str
        assert "disabled" in repr_str


# Import patch for the tests that need it
from unittest.mock import patch


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
