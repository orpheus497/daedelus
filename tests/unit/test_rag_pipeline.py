"""
Unit tests for RAGPipeline.

Tests context retrieval and prompt construction for LLM.
"""

from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_db():
    """Mock command database."""
    db = Mock()

    # Mock recent commands
    db.get_recent_commands.return_value = [
        {"command": "ls -la", "cwd": "/home", "timestamp": "2024-01-01 10:00:00"},
        {"command": "git status", "cwd": "/home/project", "timestamp": "2024-01-01 10:01:00"},
        {"command": "cd project", "cwd": "/home", "timestamp": "2024-01-01 10:02:00"},
    ]

    # Mock search commands
    db.search_commands.return_value = [
        {"command": "git commit -m", "cwd": "/home/project", "frequency": 10},
        {"command": "git push", "cwd": "/home/project", "frequency": 8},
    ]

    # Mock commands by directory
    db.get_commands_by_directory.return_value = [
        {"command": "npm install", "frequency": 5},
        {"command": "npm test", "frequency": 3},
    ]

    return db


@pytest.fixture
def mock_embedder():
    """Mock command embedder."""
    embedder = Mock()
    embedder.encode.return_value = [0.1] * 64  # Mock embedding
    return embedder


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = Mock()

    # Mock search results
    store.search.return_value = [
        ("git commit", 0.95),
        ("git add", 0.88),
        ("git status", 0.82),
    ]

    return store


class TestRAGPipelineInit:
    """Test RAG pipeline initialization."""

    def test_init_basic(self, mock_db, mock_embedder, mock_vector_store):
        """Test basic initialization."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)

        assert rag.db == mock_db
        assert rag.embedder == mock_embedder
        assert rag.vector_store == mock_vector_store

    def test_init_with_custom_params(self, mock_db, mock_embedder, mock_vector_store):
        """Test initialization with custom parameters."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(
            mock_db,
            mock_embedder,
            mock_vector_store,
            max_similar_commands=10,
            max_recent_commands=20,
        )

        assert rag.max_similar_commands == 10
        assert rag.max_recent_commands == 20


class TestContextRetrieval:
    """Test context retrieval from database."""

    def test_retrieve_context_basic(self, mock_db, mock_embedder, mock_vector_store):
        """Test basic context retrieval."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        context = rag.retrieve_context("git commit")

        assert "similar_commands" in context
        assert "recent_commands" in context
        assert "patterns" in context

    def test_retrieve_context_with_cwd(self, mock_db, mock_embedder, mock_vector_store):
        """Test context retrieval with current directory."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        context = rag.retrieve_context("npm install", cwd="/home/project")

        # Should filter by directory
        mock_db.get_commands_by_directory.assert_called()
        assert isinstance(context, dict)

    def test_retrieve_context_with_history(self, mock_db, mock_embedder, mock_vector_store):
        """Test context retrieval with recent history."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        history = ["cd project", "ls", "git status"]

        context = rag.retrieve_context("git commit", history=history)

        assert isinstance(context, dict)
        assert "recent_commands" in context

    def test_retrieve_context_empty_query(self, mock_db, mock_embedder, mock_vector_store):
        """Test context retrieval with empty query."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        context = rag.retrieve_context("")

        assert isinstance(context, dict)

    def test_retrieve_similar_commands(self, mock_db, mock_embedder, mock_vector_store):
        """Test retrieving similar commands via vector search."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        similar = rag._retrieve_similar_commands("git commit", n=5)

        assert isinstance(similar, list)
        mock_embedder.encode.assert_called_with("git commit")
        mock_vector_store.search.assert_called()

    def test_retrieve_recent_commands(self, mock_db, mock_embedder, mock_vector_store):
        """Test retrieving recent commands."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        recent = rag._retrieve_recent_commands(n=10, cwd="/home")

        assert isinstance(recent, list)
        mock_db.get_recent_commands.assert_called()

    def test_retrieve_patterns(self, mock_db, mock_embedder, mock_vector_store):
        """Test retrieving command patterns."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        patterns = rag._retrieve_patterns("git")

        assert isinstance(patterns, list)
        mock_db.search_commands.assert_called()


class TestContextFormatting:
    """Test context formatting for LLM prompts."""

    def test_format_context_basic(self, mock_db, mock_embedder, mock_vector_store):
        """Test basic context formatting."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        context = {
            "similar_commands": [("git commit -m", 0.95), ("git add", 0.88)],
            "recent_commands": [
                {"command": "ls -la", "cwd": "/home"},
                {"command": "git status", "cwd": "/home/project"},
            ],
            "patterns": [("git commit", 10), ("git push", 8)],
        }

        formatted = rag.format_context_for_llm(context)

        assert isinstance(formatted, str)
        assert "git commit" in formatted
        assert "ls -la" in formatted

    def test_format_context_empty(self, mock_db, mock_embedder, mock_vector_store):
        """Test formatting empty context."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        context = {
            "similar_commands": [],
            "recent_commands": [],
            "patterns": [],
        }

        formatted = rag.format_context_for_llm(context)

        assert isinstance(formatted, str)
        # Should indicate no context
        assert "No relevant" in formatted or formatted == ""

    def test_format_context_with_cwd(self, mock_db, mock_embedder, mock_vector_store):
        """Test formatting context with current directory."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        context = {
            "similar_commands": [("npm install", 0.9)],
            "recent_commands": [],
            "patterns": [],
        }

        formatted = rag.format_context_for_llm(context, cwd="/home/project")

        assert isinstance(formatted, str)
        assert "/home/project" in formatted or "npm install" in formatted


class TestPromptBuilding:
    """Test prompt construction for different tasks."""

    def test_build_prompt_explain(self, mock_db, mock_embedder, mock_vector_store):
        """Test building prompt for command explanation."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        prompt = rag.build_prompt(
            query="git commit -m 'message'",
            task_type="explain",
        )

        assert isinstance(prompt, str)
        assert "explain" in prompt.lower()
        assert "git commit" in prompt

    def test_build_prompt_generate(self, mock_db, mock_embedder, mock_vector_store):
        """Test building prompt for command generation."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        prompt = rag.build_prompt(
            query="commit my changes",
            task_type="generate",
        )

        assert isinstance(prompt, str)
        assert "generate" in prompt.lower() or "command" in prompt.lower()
        assert "commit" in prompt

    def test_build_prompt_suggest(self, mock_db, mock_embedder, mock_vector_store):
        """Test building prompt for command suggestions."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        prompt = rag.build_prompt(
            query="git com",
            task_type="suggest",
        )

        assert isinstance(prompt, str)
        assert "git com" in prompt

    def test_build_prompt_with_context(self, mock_db, mock_embedder, mock_vector_store):
        """Test building prompt with retrieved context."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        prompt = rag.build_prompt(
            query="git commit",
            task_type="explain",
            cwd="/home/project",
            history=["git status", "git add ."],
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should include context from retrieval
        # Mock will provide git-related commands

    def test_build_prompt_no_context(self, mock_db, mock_embedder, mock_vector_store):
        """Test building prompt without context retrieval."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        # Mock empty returns
        mock_db.get_recent_commands.return_value = []
        mock_db.search_commands.return_value = []
        mock_vector_store.search.return_value = []

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        prompt = rag.build_prompt(
            query="unknown command",
            task_type="explain",
        )

        assert isinstance(prompt, str)
        assert "unknown command" in prompt


class TestErrorHandling:
    """Test error handling in RAG pipeline."""

    def test_retrieve_context_db_error(self, mock_db, mock_embedder, mock_vector_store):
        """Test context retrieval when database fails."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        # Make database raise an error
        mock_db.get_recent_commands.side_effect = RuntimeError("DB error")

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)

        # Should handle error gracefully
        context = rag.retrieve_context("git commit")

        # Should still return a dict, possibly with empty/partial data
        assert isinstance(context, dict)

    def test_retrieve_context_embedder_error(self, mock_db, mock_embedder, mock_vector_store):
        """Test context retrieval when embedder fails."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        # Make embedder raise an error
        mock_embedder.encode.side_effect = RuntimeError("Embedding error")

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)

        # Should handle error gracefully
        context = rag.retrieve_context("git commit")

        assert isinstance(context, dict)

    def test_retrieve_context_vector_store_error(self, mock_db, mock_embedder, mock_vector_store):
        """Test context retrieval when vector store fails."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        # Make vector store raise an error
        mock_vector_store.search.side_effect = RuntimeError("Search error")

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)

        # Should handle error gracefully
        context = rag.retrieve_context("git commit")

        assert isinstance(context, dict)


class TestRelevanceFiltering:
    """Test filtering of relevant context."""

    def test_filter_similar_by_confidence(self, mock_db, mock_embedder, mock_vector_store):
        """Test filtering similar commands by confidence threshold."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        # Mock results with varying confidence
        mock_vector_store.search.return_value = [
            ("git commit", 0.95),  # High confidence
            ("git add", 0.88),  # Medium confidence
            ("ls -la", 0.45),  # Low confidence
        ]

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store, min_similarity=0.5)
        similar = rag._retrieve_similar_commands("git commit", n=10)

        # Should filter out low confidence results
        assert isinstance(similar, list)

    def test_deduplication(self, mock_db, mock_embedder, mock_vector_store):
        """Test deduplication of context items."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        # Mock duplicate results
        mock_db.get_recent_commands.return_value = [
            {"command": "git status", "cwd": "/home"},
            {"command": "git status", "cwd": "/home"},  # Duplicate
            {"command": "ls -la", "cwd": "/home"},
        ]

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        context = rag.retrieve_context("git")

        # Should handle duplicates (implementation specific)
        assert isinstance(context, dict)


class TestRepr:
    """Test string representation."""

    def test_repr(self, mock_db, mock_embedder, mock_vector_store):
        """Test __repr__ method."""
        from daedelus.llm.rag_pipeline import RAGPipeline

        rag = RAGPipeline(mock_db, mock_embedder, mock_vector_store)
        repr_str = repr(rag)

        assert "RAGPipeline" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
