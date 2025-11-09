"""Tests for model manager."""
import pytest

def test_model_manager_init(temp_dir):
    """Test model manager initialization."""
    from daedelus.llm.model_manager import ModelManager
    mgr = ModelManager(temp_dir)
    assert mgr.models_dir == temp_dir

def test_get_lineage(temp_dir):
    """Test model lineage tracking."""
    from daedelus.llm.model_manager import ModelManager
    mgr = ModelManager(temp_dir)
    lineage = mgr.get_lineage("test_model")
    assert isinstance(lineage, list)
