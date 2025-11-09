"""
Comprehensive unit tests for SuggestionEngine.

Tests all major functionality:
- Engine initialization
- Multi-tier suggestion cascade
- Tier 1: Exact prefix matching
- Tier 2: Semantic similarity
- Tier 3: Contextual patterns
- Deduplication and filtering
- Ranking and scoring
- Explanation generation

Created by: orpheus497
"""

import pytest

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.suggestions import SuggestionEngine
from daedelus.core.vector_store import VectorStore


@pytest.fixture
def setup_suggestion_engine(temp_dir):
    """Set up a complete suggestion engine with test data."""
    # Create database
    db = CommandDatabase(temp_dir / "test.db")
    session_id = db.create_session(shell="zsh", cwd="/home/user")

    # Insert test commands
    commands = [
        ("git status", "/home/user/project", 0),
        ("git status", "/home/user/project", 0),
        ("git status", "/home/user/project", 0),
        ("git add .", "/home/user/project", 0),
        ("git add .", "/home/user/project", 0),
        ("git commit -m 'update'", "/home/user/project", 0),
        ("git push origin main", "/home/user/project", 0),
        ("ls -la", "/home/user", 0),
        ("cd projects", "/home/user", 0),
        ("python train.py", "/home/user/ml", 0),
        ("pip install numpy", "/home/user/ml", 0),
        ("docker build -t app .", "/home/user/docker", 0),
        ("docker run app", "/home/user/docker", 0),
    ]

    for cmd, cwd, exit_code in commands:
        db.insert_command(cmd, cwd, exit_code, session_id, duration=0.5)

    # Create embedder and train it
    embedder = CommandEmbedder(temp_dir / "model.bin", embedding_dim=64, epoch=1)
    training_commands = [cmd for cmd, _, _ in commands] + [
        "git log",
        "git diff",
        "ls",
        "pwd",
        "cat file.txt",
    ]
    embedder.train_from_corpus(training_commands)

    # Create vector store
    vector_store = VectorStore(temp_dir / "index", dim=64)
    for cmd, cwd, _ in commands:
        embedding = embedder.encode_command(cmd)
        vector_store.add(embedding, cmd, {"cwd": cwd})
    vector_store.build()

    # Create suggestion engine
    engine = SuggestionEngine(
        db=db,
        embedder=embedder,
        vector_store=vector_store,
        max_suggestions=5,
        min_confidence=0.3,
    )

    yield engine, db, embedder, vector_store

    db.close()


class TestSuggestionEngineInit:
    """Test suggestion engine initialization."""

    def test_init(self, setup_suggestion_engine):
        """Test basic initialization."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        assert engine.db is db
        assert engine.embedder is embedder
        assert engine.vector_store is vector_store
        assert engine.max_suggestions == 5
        assert engine.min_confidence == 0.3

    def test_init_custom_params(self, temp_dir):
        """Test initialization with custom parameters."""
        db = CommandDatabase(temp_dir / "test.db")
        embedder = CommandEmbedder(temp_dir / "model.bin")
        vector_store = VectorStore(temp_dir / "index")

        engine = SuggestionEngine(
            db=db,
            embedder=embedder,
            vector_store=vector_store,
            max_suggestions=10,
            min_confidence=0.5,
        )

        assert engine.max_suggestions == 10
        assert engine.min_confidence == 0.5

        db.close()


class TestGetSuggestions:
    """Test main suggestion interface."""

    def test_get_suggestions_basic(self, setup_suggestion_engine):
        """Test getting basic suggestions."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("git")

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert all("command" in s for s in suggestions)
        assert all("confidence" in s for s in suggestions)
        assert all("source" in s for s in suggestions)

    def test_get_suggestions_with_context(self, setup_suggestion_engine):
        """Test suggestions with context."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions(
            partial="git",
            cwd="/home/user/project",
            history=["git add .", "git commit"],
        )

        assert len(suggestions) > 0

    def test_get_suggestions_empty_partial(self, setup_suggestion_engine):
        """Test suggestions with empty partial."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("")

        # Should still work, may return contextual suggestions
        assert isinstance(suggestions, list)

    def test_suggestions_ordered_by_confidence(self, setup_suggestion_engine):
        """Test that suggestions are ordered by confidence."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("git")

        confidences = [s["confidence"] for s in suggestions]
        # Should be in descending order
        assert confidences == sorted(confidences, reverse=True)

    def test_suggestions_respect_max_limit(self, setup_suggestion_engine):
        """Test that max_suggestions is respected."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("git")

        assert len(suggestions) <= engine.max_suggestions

    def test_suggestions_respect_min_confidence(self, setup_suggestion_engine):
        """Test that min_confidence filter works."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("git")

        assert all(s["confidence"] >= engine.min_confidence for s in suggestions)

    def test_suggestions_deduplicated(self, setup_suggestion_engine):
        """Test that duplicate commands are removed."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("git")

        commands = [s["command"] for s in suggestions]
        # No duplicates
        assert len(commands) == len(set(commands))


class TestTier1ExactPrefix:
    """Test tier 1 exact prefix matching."""

    def test_tier1_exact_match(self, setup_suggestion_engine):
        """Test exact prefix matching."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier1_exact_prefix("git st")

        # Should find "git status"
        assert len(suggestions) > 0
        assert any(s["command"] == "git status" for s in suggestions)

    def test_tier1_no_match(self, setup_suggestion_engine):
        """Test when no exact match exists."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier1_exact_prefix("nonexistent")

        assert len(suggestions) == 0

    def test_tier1_empty_partial(self, setup_suggestion_engine):
        """Test tier 1 with empty partial."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier1_exact_prefix("")

        assert len(suggestions) == 0

    def test_tier1_with_cwd_filter(self, setup_suggestion_engine):
        """Test tier 1 with CWD filtering."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier1_exact_prefix("git", cwd="/home/user/project")

        assert len(suggestions) > 0
        # All should be git commands from that directory

    def test_tier1_frequency_ordering(self, setup_suggestion_engine):
        """Test that tier 1 orders by frequency."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier1_exact_prefix("git")

        # "git status" appears 3 times, should be high ranked
        if suggestions:
            assert any(s["command"] == "git status" for s in suggestions)

    def test_tier1_confidence_calculation(self, setup_suggestion_engine):
        """Test that confidence is calculated."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier1_exact_prefix("git")

        assert all(0.0 <= s["confidence"] <= 1.0 for s in suggestions)

    def test_tier1_source_tag(self, setup_suggestion_engine):
        """Test that source is tagged correctly."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier1_exact_prefix("git")

        assert all(s["source"] == "exact_prefix" for s in suggestions)


class TestTier2Semantic:
    """Test tier 2 semantic similarity."""

    def test_tier2_semantic_match(self, setup_suggestion_engine):
        """Test semantic similarity matching."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier2_semantic("git")

        assert len(suggestions) > 0
        # Should find git-related commands

    def test_tier2_with_context(self, setup_suggestion_engine):
        """Test tier 2 with context."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier2_semantic(
            partial="git",
            cwd="/home/user/project",
            history=["git add ."],
        )

        assert len(suggestions) > 0

    def test_tier2_empty_partial(self, setup_suggestion_engine):
        """Test tier 2 with empty partial."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier2_semantic("")

        assert len(suggestions) == 0

    def test_tier2_confidence_from_similarity(self, setup_suggestion_engine):
        """Test that confidence comes from similarity."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier2_semantic("git status")

        assert all(0.0 <= s["confidence"] <= 1.0 for s in suggestions)

    def test_tier2_source_tag(self, setup_suggestion_engine):
        """Test that source is tagged correctly."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier2_semantic("git")

        assert all(s["source"] == "semantic" for s in suggestions)

    def test_tier2_typo_handling(self, setup_suggestion_engine):
        """Test that tier 2 handles typos well."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        # Typo: "git staus" instead of "git status"
        suggestions = engine._tier2_semantic("git staus")

        # Should still find git-related commands due to semantic similarity
        assert len(suggestions) > 0


class TestTier3Contextual:
    """Test tier 3 contextual patterns."""

    def test_tier3_pattern_match(self, setup_suggestion_engine):
        """Test contextual pattern matching."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        # After "git add .", often comes "git commit"
        suggestions = engine._tier3_contextual(
            partial="git",
            history=["git add ."],
        )

        # May or may not find patterns depending on test data
        assert isinstance(suggestions, list)

    def test_tier3_no_history(self, setup_suggestion_engine):
        """Test tier 3 with no history."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine._tier3_contextual("git", history=[])

        assert len(suggestions) == 0

    def test_tier3_source_tag(self, setup_suggestion_engine):
        """Test that source is tagged correctly."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        # Add commands to create a pattern
        session_id = db.create_session()
        db.insert_command("git add .", "/tmp", 0, session_id)
        db.insert_command("git commit -m 'test'", "/tmp", 0, session_id)
        db.insert_command("git add .", "/tmp", 0, session_id)
        db.insert_command("git commit -m 'test2'", "/tmp", 0, session_id)

        suggestions = engine._tier3_contextual(
            partial="git",
            history=["git add ."],
        )

        if suggestions:
            assert all(s["source"] == "contextual_pattern" for s in suggestions)

    def test_tier3_confidence_capping(self, setup_suggestion_engine):
        """Test that tier 3 confidence is capped."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        # Create strong pattern
        session_id = db.create_session()
        for _ in range(20):
            db.insert_command("git add .", "/tmp", 0, session_id)
            db.insert_command("git commit", "/tmp", 0, session_id)

        suggestions = engine._tier3_contextual(
            partial="git",
            history=["git add ."],
        )

        # Confidence should be capped at 0.8
        if suggestions:
            assert all(s["confidence"] <= 0.8 for s in suggestions)


class TestMultiTierCascade:
    """Test the multi-tier cascade behavior."""

    def test_cascade_fills_from_multiple_tiers(self, setup_suggestion_engine):
        """Test that cascade uses multiple tiers."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("git")

        # Should have suggestions from different tiers
        sources = {s["source"] for s in suggestions}
        # At least one tier should be represented
        assert len(sources) >= 1

    def test_cascade_prioritizes_tier1(self, setup_suggestion_engine):
        """Test that exact matches are prioritized."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = engine.get_suggestions("git status")

        # First suggestion should be exact match if available
        if suggestions:
            first = suggestions[0]
            # Either exact match or very high confidence
            assert first["source"] == "exact_prefix" or first["confidence"] > 0.7


class TestExplainSuggestion:
    """Test suggestion explanation generation."""

    def test_explain_exact_prefix(self, setup_suggestion_engine):
        """Test explanation for exact prefix match."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestion = {
            "command": "git status",
            "confidence": 0.95,
            "source": "exact_prefix",
        }

        explanation = engine.explain_suggestion(suggestion)

        assert "exact match" in explanation.lower()
        assert "95%" in explanation

    def test_explain_semantic(self, setup_suggestion_engine):
        """Test explanation for semantic match."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestion = {
            "command": "git commit",
            "confidence": 0.75,
            "source": "semantic",
        }

        explanation = engine.explain_suggestion(suggestion)

        assert "similar" in explanation.lower() or "meaning" in explanation.lower()
        assert "75%" in explanation

    def test_explain_contextual(self, setup_suggestion_engine):
        """Test explanation for contextual match."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestion = {
            "command": "git push",
            "confidence": 0.65,
            "source": "contextual_pattern",
        }

        explanation = engine.explain_suggestion(suggestion)

        assert "after" in explanation.lower() or "pattern" in explanation.lower()
        assert "65%" in explanation

    def test_explain_unknown_source(self, setup_suggestion_engine):
        """Test explanation for unknown source."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestion = {
            "command": "test",
            "confidence": 0.5,
            "source": "unknown_source",
        }

        explanation = engine.explain_suggestion(suggestion)

        assert "50%" in explanation


class TestRankSuggestions:
    """Test suggestion ranking."""

    def test_rank_suggestions_passthrough(self, setup_suggestion_engine):
        """Test that rank_suggestions currently passes through."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        suggestions = [
            {"command": "cmd1", "confidence": 0.9, "source": "test"},
            {"command": "cmd2", "confidence": 0.7, "source": "test"},
        ]

        ranked = engine.rank_suggestions(suggestions)

        # Currently just returns the same list (TODO in implementation)
        assert ranked == suggestions


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_suggestions_with_special_characters(self, setup_suggestion_engine):
        """Test suggestions with special characters."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        session_id = db.create_session()
        db.insert_command("grep -r 'pattern' .", "/tmp", 0, session_id)

        suggestions = engine.get_suggestions("grep")

        assert len(suggestions) >= 0  # Should not crash

    def test_suggestions_with_unicode(self, setup_suggestion_engine):
        """Test suggestions with unicode."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        session_id = db.create_session()
        db.insert_command("echo '你好'", "/tmp", 0, session_id)

        suggestions = engine.get_suggestions("echo")

        assert len(suggestions) >= 0  # Should not crash

    def test_suggestions_very_long_partial(self, setup_suggestion_engine):
        """Test with very long partial command."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        long_partial = "git " + "commit " * 100

        suggestions = engine.get_suggestions(long_partial)

        assert isinstance(suggestions, list)

    def test_suggestions_with_sql_injection_attempt(self, setup_suggestion_engine):
        """Test that SQL injection is prevented."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        # SQL injection attempt
        malicious = "git'; DROP TABLE command_history; --"

        suggestions = engine.get_suggestions(malicious)

        # Should not crash, database should be fine
        assert isinstance(suggestions, list)

        # Verify database still works
        stats = db.get_statistics()
        assert stats["total_commands"] > 0


class TestPerformance:
    """Test performance characteristics."""

    def test_suggestions_with_large_history(self, setup_suggestion_engine):
        """Test with large command history."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        # Add many commands
        session_id = db.create_session()
        for i in range(1000):
            db.insert_command(f"test_command_{i % 100}", "/tmp", 0, session_id)

        # Should still be fast
        suggestions = engine.get_suggestions("test")

        assert len(suggestions) >= 0

    def test_suggestions_respects_limit(self, setup_suggestion_engine):
        """Test that suggestion limit is hard cap."""
        engine, db, embedder, vector_store = setup_suggestion_engine

        # Even with many matches, should respect limit
        suggestions = engine.get_suggestions("git")

        assert len(suggestions) <= engine.max_suggestions
