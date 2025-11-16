"""
Tests for suggestion engine.

Tests the 3-tier cascade suggestion system with ranking.

Created by: orpheus497
"""

import pytest

from daedelus.core.suggestions import SuggestionEngine


def test_suggestion_engine_init(test_db):
    """Test engine initialization."""
    engine = SuggestionEngine(test_db)
    assert engine.db is test_db


def test_tier1_exact_match(test_db):
    """Test exact prefix matching."""
    # Log commands
    for i in range(5):
        test_db.log_command("git status", "/home/user/project", 0, 0.05)
    test_db.log_command("git add .", "/home/user/project", 0, 0.12)

    engine = SuggestionEngine(test_db)
    suggestions = engine.suggest("git st", cwd="/home/user/project")

    assert len(suggestions) > 0
    assert any("git status" in s["command"] for s in suggestions)


def test_max_suggestions_limit(test_db):
    """Test result count limiting."""
    # Log many commands
    for i in range(20):
        test_db.log_command(f"git status{i}", "/home/user", 0, 0.05)

    engine = SuggestionEngine(test_db, max_suggestions=5)
    suggestions = engine.suggest("git", cwd="/home/user")

    assert len(suggestions) <= 5


def test_confidence_threshold(test_db):
    """Test minimum confidence filtering."""
    test_db.log_command("git status", "/home/user", 0, 0.05)

    engine = SuggestionEngine(test_db, min_confidence=0.9)
    suggestions = engine.suggest("py", cwd="/home/user")

    # Should filter out low confidence
    assert all(s["confidence"] >= 0.9 for s in suggestions)


def test_empty_partial(test_db):
    """Test empty input handling."""
    engine = SuggestionEngine(test_db)
    suggestions = engine.suggest("", cwd="/home/user")

    assert suggestions == []


def test_deduplication(test_db):
    """Test duplicate removal."""
    # Log same command multiple times
    for _ in range(5):
        test_db.log_command("git status", "/home/user", 0, 0.05)

    engine = SuggestionEngine(test_db)
    suggestions = engine.suggest("git", cwd="/home/user")

    # Should not have duplicates
    commands = [s["command"] for s in suggestions]
    assert len(commands) == len(set(commands))


@pytest.mark.performance
def test_suggest_performance(test_db):
    """Test suggestion latency (<30ms)."""
    import time

    # Log many commands
    for i in range(1000):
        test_db.log_command(f"command_{i}", "/home/user", 0, 0.01)

    engine = SuggestionEngine(test_db)

    start = time.time()
    suggestions = engine.suggest("com", cwd="/home/user")
    elapsed = time.time() - start

    assert elapsed < 0.03  # <30ms
