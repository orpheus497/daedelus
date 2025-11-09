"""Tests for command explainer."""
import pytest

def test_explainer_init(test_db):
    """Test explainer initialization."""
    from daedelus.llm.command_explainer import CommandExplainer
    explainer = CommandExplainer(test_db)
    assert explainer is not None

def test_explain_simple_command(test_db):
    """Test command explanation."""
    from daedelus.llm.command_explainer import CommandExplainer
    explainer = CommandExplainer(test_db)
    result = explainer.explain("ls -la")
    assert isinstance(result, str)
