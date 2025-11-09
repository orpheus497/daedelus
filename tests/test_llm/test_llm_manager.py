"""Tests for LLM manager."""
import pytest

def test_llm_manager_init(temp_dir, mock_llm):
    """Test LLM manager initialization."""
    from daedelus.llm.llm_manager import LLMManager
    mgr = LLMManager(model_path=temp_dir / "model.gguf")
    assert mgr.model_path.name == "model.gguf"

def test_generate_text(temp_dir, mock_llm):
    """Test text generation."""
    from daedelus.llm.llm_manager import LLMManager
    mgr = LLMManager(model_path=temp_dir / "model.gguf")
    result = mgr.generate("test prompt")
    assert isinstance(result, str)
    assert len(result) > 0
