"""
Tests for Intent Classifier.

Created by: orpheus497
"""

import pytest

from daedelus.llm.intent_classifier import (
    Intent,
    IntentClassifier,
    IntentType,
    Urgency,
)


@pytest.fixture
def classifier():
    """Create an intent classifier instance."""
    return IntentClassifier()


def test_intent_classifier_initialization(classifier):
    """Test that intent classifier initializes correctly."""
    assert classifier is not None
    assert len(classifier.action_patterns) > 0
    assert len(classifier.question_patterns) > 0


def test_classify_file_action(classifier):
    """Test classification of file operation actions."""
    queries = [
        "create a new file called test.txt",
        "delete the old log files",
        "copy all Python files to backup/",
        "move the documents to archive",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.ACTION_FILE
        assert intent.confidence > 0.5


def test_classify_search_action(classifier):
    """Test classification of search actions."""
    queries = [
        "find all Python files",
        "search for files containing TODO",
        "locate the config.yaml file",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.ACTION_SEARCH
        assert intent.confidence > 0.5


def test_classify_git_action(classifier):
    """Test classification of Git actions."""
    queries = [
        "commit the changes",
        "push to origin main",
        "create a new branch",
        "merge feature into main",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.ACTION_GIT
        assert intent.confidence > 0.5


def test_classify_how_question(classifier):
    """Test classification of 'how to' questions."""
    queries = [
        "how do I compress a directory?",
        "how to list all processes",
        "how can I check disk space",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.QUESTION_HOW
        assert intent.confidence > 0.5


def test_classify_what_question(classifier):
    """Test classification of 'what is' questions."""
    queries = [
        "what is the chmod command",
        "what does grep do",
        "what are environment variables",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type in [IntentType.QUESTION_WHAT, IntentType.QUESTION_EXPLAIN]
        assert intent.confidence > 0.5


def test_classify_permission_fix(classifier):
    """Test classification of permission fix intents."""
    queries = [
        "permission denied when accessing file",
        "access denied error",
        "fix SSH key permissions",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.FIX_PERMISSION
        assert intent.confidence > 0.5


def test_classify_not_found_fix(classifier):
    """Test classification of not found fix intents."""
    queries = [
        "command not found: python",
        "no such file or directory",
        "file not found error",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.FIX_NOT_FOUND
        assert intent.confidence > 0.5


def test_urgency_detection_critical(classifier):
    """Test detection of critical urgency."""
    queries = [
        "URGENT: server is down",
        "emergency backup needed immediately",
        "critical error in production",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.urgency == Urgency.CRITICAL


def test_urgency_detection_high(classifier):
    """Test detection of high urgency."""
    queries = [
        "need to fix this quickly",
        "important security update",
        "server failing intermittently",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.urgency in [Urgency.HIGH, Urgency.CRITICAL]


def test_urgency_detection_low(classifier):
    """Test detection of low urgency."""
    queries = [
        "maybe clean up old logs sometime",
        "when you can, optimize the database",
        "eventually we should refactor this",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.urgency == Urgency.LOW


def test_entity_extraction_files(classifier):
    """Test extraction of file entities."""
    query = "copy test.py and config.yaml to backup/"
    intent = classifier.classify(query)

    assert "files" in intent.entities
    files = intent.entities["files"]
    assert any("test.py" in str(f) for f in files)


def test_entity_extraction_directories(classifier):
    """Test extraction of directory entities."""
    query = "list files in /home/user/projects"
    intent = classifier.classify(query)

    assert "directories" in intent.entities
    dirs = intent.entities["directories"]
    assert len(dirs) > 0


def test_entity_extraction_extensions(classifier):
    """Test extraction of file extension entities."""
    query = "find all Python files and JavaScript files"
    intent = classifier.classify(query)

    assert "extensions" in intent.entities
    extensions = intent.entities["extensions"]
    assert "Python" in extensions or "JavaScript" in extensions


def test_keyword_extraction(classifier):
    """Test keyword extraction."""
    query = "search through all configuration files for database settings"
    intent = classifier.classify(query)

    keywords = intent.keywords
    assert len(keywords) > 0
    assert any(kw in ["search", "configuration", "files", "database", "settings"] for kw in keywords)


def test_needs_decomposition_simple(classifier):
    """Test that simple queries don't need decomposition."""
    query = "list all files"
    intent = classifier.classify(query)

    assert intent.needs_decomposition is False


def test_needs_decomposition_complex(classifier):
    """Test that complex queries need decomposition."""
    queries = [
        "find all Python files and count the lines of code",
        "list directories and then sort by size",
        "search for TODO comments and create a report",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.needs_decomposition is True


def test_decompose_find_and_count(classifier):
    """Test decomposition of find and count query."""
    query = "find all Python files and count them"
    intent = classifier.classify(query)

    assert intent.needs_decomposition is True
    assert intent.decomposed_steps is not None
    assert len(intent.decomposed_steps) > 0


def test_generate_commands_file_operations(classifier):
    """Test command generation for file operations."""
    query = "create a new directory"
    intent = classifier.classify(query)

    assert len(intent.suggested_commands) > 0
    assert any("mkdir" in cmd for cmd in intent.suggested_commands)


def test_generate_commands_search(classifier):
    """Test command generation for search operations."""
    query = "find all Python files"
    intent = classifier.classify(query)

    assert len(intent.suggested_commands) > 0
    assert any("find" in cmd or "*.py" in cmd for cmd in intent.suggested_commands)


def test_generate_commands_git(classifier):
    """Test command generation for Git operations."""
    query = "commit my changes"
    intent = classifier.classify(query)

    assert len(intent.suggested_commands) > 0
    assert any("git" in cmd for cmd in intent.suggested_commands)


def test_generate_commands_compress(classifier):
    """Test command generation for compression."""
    query = "compress the logs directory"
    intent = classifier.classify(query)

    assert len(intent.suggested_commands) > 0
    assert any("tar" in cmd or "zip" in cmd for cmd in intent.suggested_commands)


def test_generate_commands_permission_fix(classifier):
    """Test command generation for permission fixes."""
    query = "permission denied on my SSH keys"
    intent = classifier.classify(query)

    assert len(intent.suggested_commands) > 0
    assert any("chmod" in cmd and "ssh" in cmd.lower() for cmd in intent.suggested_commands)


def test_classify_package_management(classifier):
    """Test classification of package management actions."""
    queries = [
        "install numpy using pip",
        "update all npm packages",
        "remove unused cargo dependencies",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.ACTION_PACKAGE
        assert intent.confidence > 0.5


def test_classify_text_processing(classifier):
    """Test classification of text processing actions."""
    queries = [
        "count lines in all Python files",
        "replace all tabs with spaces",
        "find and replace text in files",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.ACTION_TEXT
        assert intent.confidence > 0.5


def test_classify_status_check(classifier):
    """Test classification of status check intents."""
    queries = [
        "check if the server is running",
        "verify database connection",
        "test network connectivity",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.STATUS_CHECK
        assert intent.confidence > 0.5


def test_classify_list_status(classifier):
    """Test classification of list status intents."""
    queries = [
        "list all running processes",
        "show all environment variables",
        "display network interfaces",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert intent.type == IntentType.STATUS_LIST
        assert intent.confidence > 0.5


def test_confidence_scores(classifier):
    """Test that confidence scores are within valid range."""
    queries = [
        "find all files",
        "how do I use grep",
        "permission denied error",
        "list processes",
    ]

    for query in queries:
        intent = classifier.classify(query)
        assert 0.0 <= intent.confidence <= 1.0


def test_unknown_intent_low_confidence(classifier):
    """Test that unclear queries have lower confidence."""
    query = "something weird happened"
    intent = classifier.classify(query)

    # Should have lower confidence for unclear intent
    assert intent.confidence < 0.8 or intent.type == IntentType.UNKNOWN
