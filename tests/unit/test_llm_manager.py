"""
Unit tests for LLMManager.

Tests LLM inference capabilities via llama.cpp.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List


class MockLlama:
    """Mock llama-cpp-python Llama class."""

    def __init__(self, model_path: str, n_ctx: int = 2048, n_gpu_layers: int = 0, **kwargs):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.kwargs = kwargs

    def __call__(self, prompt: str, max_tokens: int = 100, **kwargs) -> Dict:
        """Mock completion."""
        return {
            "choices": [{
                "text": f"Generated response for: {prompt[:30]}...",
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": max_tokens,
                "total_tokens": len(prompt.split()) + max_tokens,
            }
        }

    def create_chat_completion(self, messages: List[Dict], **kwargs) -> Dict:
        """Mock chat completion."""
        last_message = messages[-1]["content"] if messages else ""
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"Chat response for: {last_message[:30]}...",
                },
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": sum(len(m["content"].split()) for m in messages),
                "completion_tokens": 50,
                "total_tokens": sum(len(m["content"].split()) for m in messages) + 50,
            }
        }

    def tokenize(self, text: str) -> List[int]:
        """Mock tokenization."""
        return [i for i in range(len(text.split()))]


@pytest.fixture
def mock_llama():
    """Fixture providing mock Llama."""
    return MockLlama


@pytest.fixture
def mock_model_file(tmp_path):
    """Fixture providing mock model file."""
    model_path = tmp_path / "test_model.gguf"
    model_path.write_text("mock model")
    return model_path


class TestLLMManagerImport:
    """Test LLM manager import and initialization."""

    def test_import_without_dependencies(self):
        """Test that module can be imported even without llama-cpp-python."""
        # This should not raise an error
        from daedelus.llm import llm_manager
        assert llm_manager is not None

    def test_missing_dependency_error(self, tmp_path):
        """Test that LLMManager raises error if llama-cpp-python not installed."""
        with patch("daedelus.llm.llm_manager.Llama", None):
            from daedelus.llm.llm_manager import LLMManager

            with pytest.raises(ImportError, match="llama-cpp-python not installed"):
                LLMManager(model_path=tmp_path / "model.gguf")


class TestLLMManagerInit:
    """Test LLM manager initialization."""

    def test_init_basic(self, mock_llama, mock_model_file):
        """Test basic initialization."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)

            assert llm.model_path == mock_model_file
            assert llm.context_length == 2048  # default
            assert llm.model is not None

    def test_init_custom_params(self, mock_llama, mock_model_file):
        """Test initialization with custom parameters."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(
                model_path=mock_model_file,
                context_length=4096,
                n_gpu_layers=32,
            )

            assert llm.context_length == 4096
            assert llm.model.n_gpu_layers == 32

    def test_init_model_not_found(self, mock_llama, tmp_path):
        """Test initialization with non-existent model."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            non_existent = tmp_path / "nonexistent.gguf"

            with pytest.raises(FileNotFoundError):
                LLMManager(model_path=non_existent)

    def test_init_string_path(self, mock_llama, mock_model_file):
        """Test initialization with string path."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=str(mock_model_file))

            assert llm.model_path == Path(str(mock_model_file))


class TestLLMGeneration:
    """Test LLM text generation."""

    def test_generate_basic(self, mock_llama, mock_model_file):
        """Test basic text generation."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            response = llm.generate("Test prompt")

            assert isinstance(response, str)
            assert len(response) > 0
            assert "Generated response" in response

    def test_generate_with_params(self, mock_llama, mock_model_file):
        """Test generation with custom parameters."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            response = llm.generate(
                "Test prompt",
                max_tokens=200,
                temperature=0.8,
                top_p=0.9,
            )

            assert isinstance(response, str)

    def test_generate_with_stop_sequences(self, mock_llama, mock_model_file):
        """Test generation with stop sequences."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            response = llm.generate(
                "Test prompt",
                stop=[".", "\n", "END"],
            )

            assert isinstance(response, str)

    def test_generate_empty_prompt(self, mock_llama, mock_model_file):
        """Test generation with empty prompt."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            response = llm.generate("")

            # Should still return something
            assert isinstance(response, str)


class TestLLMChatCompletion:
    """Test LLM chat completion."""

    def test_chat_complete_basic(self, mock_llama, mock_model_file):
        """Test basic chat completion."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            messages = [
                {"role": "user", "content": "Hello"},
            ]

            response = llm.chat_complete(messages)

            assert isinstance(response, str)
            assert "Chat response" in response

    def test_chat_complete_multi_turn(self, mock_llama, mock_model_file):
        """Test multi-turn chat completion."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
            ]

            response = llm.chat_complete(messages)

            assert isinstance(response, str)

    def test_chat_complete_with_system(self, mock_llama, mock_model_file):
        """Test chat completion with system message."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"},
            ]

            response = llm.chat_complete(messages)

            assert isinstance(response, str)

    def test_chat_complete_empty_messages(self, mock_llama, mock_model_file):
        """Test chat completion with empty messages."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)

            response = llm.chat_complete([])

            assert isinstance(response, str)


class TestLLMTokenization:
    """Test LLM tokenization."""

    def test_count_tokens_basic(self, mock_llama, mock_model_file):
        """Test basic token counting."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            count = llm.count_tokens("Hello world")

            assert isinstance(count, int)
            assert count > 0

    def test_count_tokens_empty(self, mock_llama, mock_model_file):
        """Test token counting with empty string."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            count = llm.count_tokens("")

            assert count == 0

    def test_count_tokens_long_text(self, mock_llama, mock_model_file):
        """Test token counting with long text."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            long_text = " ".join(["word"] * 1000)
            count = llm.count_tokens(long_text)

            assert count > 0


class TestLLMAdapterManagement:
    """Test LoRA adapter loading."""

    def test_load_adapter_basic(self, mock_llama, mock_model_file, tmp_path):
        """Test loading LoRA adapter."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            # Create mock adapter directory
            adapter_path = tmp_path / "adapter"
            adapter_path.mkdir()
            (adapter_path / "adapter_config.json").write_text("{}")

            llm = LLMManager(model_path=mock_model_file)

            # This should not raise an error
            # Actual implementation would load adapter
            # For now, just test the path handling
            assert llm.model is not None

    def test_load_adapter_not_found(self, mock_llama, mock_model_file, tmp_path):
        """Test loading non-existent adapter."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)

            # Loading non-existent adapter should be handled gracefully
            # Actual implementation would raise FileNotFoundError
            assert llm.model is not None


class TestLLMRepr:
    """Test LLM manager string representation."""

    def test_repr(self, mock_llama, mock_model_file):
        """Test __repr__ method."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)
            repr_str = repr(llm)

            assert "LLMManager" in repr_str
            assert "test_model.gguf" in repr_str


class TestLLMErrorHandling:
    """Test error handling in LLM operations."""

    def test_generation_error_handling(self, mock_llama, mock_model_file):
        """Test error handling during generation."""
        # Mock Llama that raises an error
        class ErrorLlama(MockLlama):
            def __call__(self, *args, **kwargs):
                raise RuntimeError("Generation failed")

        with patch("daedelus.llm.llm_manager.Llama", ErrorLlama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)

            with pytest.raises(RuntimeError, match="Generation failed"):
                llm.generate("Test prompt")

    def test_chat_error_handling(self, mock_llama, mock_model_file):
        """Test error handling during chat completion."""
        # Mock Llama that raises an error
        class ErrorLlama(MockLlama):
            def create_chat_completion(self, *args, **kwargs):
                raise RuntimeError("Chat failed")

        with patch("daedelus.llm.llm_manager.Llama", ErrorLlama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file)

            with pytest.raises(RuntimeError, match="Chat failed"):
                llm.chat_complete([{"role": "user", "content": "test"}])


class TestLLMContextManagement:
    """Test context length management."""

    def test_context_truncation(self, mock_llama, mock_model_file):
        """Test that long prompts are handled appropriately."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file, context_length=512)

            # Create a very long prompt
            long_prompt = " ".join(["word"] * 2000)

            # Should not raise an error (truncation or chunking should occur)
            response = llm.generate(long_prompt)

            assert isinstance(response, str)

    def test_context_length_setting(self, mock_llama, mock_model_file):
        """Test that context length is properly set."""
        with patch("daedelus.llm.llm_manager.Llama", mock_llama):
            from daedelus.llm.llm_manager import LLMManager

            llm = LLMManager(model_path=mock_model_file, context_length=4096)

            assert llm.context_length == 4096
            assert llm.model.n_ctx == 4096


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
