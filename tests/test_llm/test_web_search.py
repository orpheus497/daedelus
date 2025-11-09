"""Tests for web search."""
import pytest

def test_web_search_init():
    """Test web search initialization."""
    from daedelus.llm.web_search import WebSearch
    ws = WebSearch()
    assert ws is not None
