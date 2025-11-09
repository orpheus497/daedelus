"""
LLM Manager for Daedelus Phase 2.

Manages the local LLM (Phi-3-mini via llama.cpp) for command understanding
and generation.

Created by: orpheus497
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None  # type: ignore


class LLMManager:
    """
    Manager for local LLM inference using llama.cpp.

    Handles:
    - Model loading (Phi-3-mini GGUF)
    - Context management
    - Generation with proper parameters
    - Token counting and optimization

    Attributes:
        model_path: Path to GGUF model file
        model: Loaded llama.cpp model instance
        context_length: Maximum context window
        temperature: Sampling temperature
        top_p: Nucleus sampling parameter
    """

    def __init__(
        self,
        model_path: Path,
        context_length: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        n_gpu_layers: int = 0,
        verbose: bool = False,
    ) -> None:
        """
        Initialize LLM manager.

        Args:
            model_path: Path to GGUF model file (e.g., Phi-3-mini-4k-instruct-q4.gguf)
            context_length: Context window size (tokens)
            temperature: Sampling temperature (0.0-1.0)
            top_p: Nucleus sampling parameter (0.0-1.0)
            n_gpu_layers: Number of layers to offload to GPU (0 = CPU only)
            verbose: Enable verbose logging from llama.cpp
        """
        if Llama is None:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus"
            )

        self.model_path = Path(model_path).expanduser()
        self.context_length = context_length
        self.temperature = temperature
        self.top_p = top_p
        self.n_gpu_layers = n_gpu_layers

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        logger.info(f"Loading LLM from {self.model_path}...")

        # Load model
        self.model = Llama(
            model_path=str(self.model_path),
            n_ctx=context_length,
            n_gpu_layers=n_gpu_layers,
            verbose=verbose,
        )

        logger.info("LLM loaded successfully")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 100,
        temperature: float | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
    ) -> str:
        """
        Generate text from prompt.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (uses default if None)
            top_p: Nucleus sampling (uses default if None)
            stop: List of stop sequences

        Returns:
            Generated text
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # Use instance defaults if not specified
        temp = temperature if temperature is not None else self.temperature
        top_p_val = top_p if top_p is not None else self.top_p

        logger.debug(f"Generating with prompt: {prompt[:50]}...")

        # Generate
        response = self.model(
            prompt,
            max_tokens=max_tokens,
            temperature=temp,
            top_p=top_p_val,
            stop=stop or [],
            echo=False,
        )

        # Extract generated text
        if isinstance(response, dict):
            text = response.get("choices", [{}])[0].get("text", "")
        else:
            text = str(response)

        return text.strip()

    def chat_complete(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 100,
        temperature: float | None = None,
    ) -> str:
        """
        Chat completion with message history.

        Args:
            messages: List of messages with 'role' and 'content' keys
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Assistant response

        Example:
            >>> messages = [
            ...     {"role": "system", "content": "You are a helpful assistant."},
            ...     {"role": "user", "content": "What does 'ls -la' do?"},
            ... ]
            >>> response = llm.chat_complete(messages)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # Format messages into prompt (Phi-3 format)
        prompt = self._format_chat_prompt(messages)

        # Generate response
        return self.generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["<|end|>", "<|user|>"],
        )

    def _format_chat_prompt(self, messages: list[dict[str, str]]) -> str:
        """
        Format messages into Phi-3 chat format.

        Phi-3 uses this format:
        <|system|>
        {system_message}<|end|>
        <|user|>
        {user_message}<|end|>
        <|assistant|>

        Args:
            messages: List of message dicts

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                prompt_parts.append(f"<|system|>\n{content}<|end|>")
            elif role == "user":
                prompt_parts.append(f"<|user|>\n{content}<|end|>")
            elif role == "assistant":
                prompt_parts.append(f"<|assistant|>\n{content}<|end|>")

        # Add assistant prompt at the end
        prompt_parts.append("<|assistant|>")

        return "\n".join(prompt_parts)

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to tokenize

        Returns:
            Number of tokens
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        tokens = self.model.tokenize(text.encode("utf-8"))
        return len(tokens)

    def truncate_to_context(self, text: str, reserve_tokens: int = 100) -> str:
        """
        Truncate text to fit in context window.

        Args:
            text: Text to truncate
            reserve_tokens: Tokens to reserve for generation

        Returns:
            Truncated text
        """
        max_tokens = self.context_length - reserve_tokens

        # Count current tokens
        current_tokens = self.count_tokens(text)

        if current_tokens <= max_tokens:
            return text

        # Truncate by characters (approximate)
        # Rough estimate: 1 token ≈ 4 characters
        target_chars = max_tokens * 4
        return text[:target_chars]

    def __repr__(self) -> str:
        """String representation."""
        return f"LLMManager(model_path={self.model_path}, " f"context_length={self.context_length})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # This requires a downloaded Phi-3-mini GGUF model
    # Download from: https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf

    try:
        llm = LLMManager(
            model_path=Path("~/.local/share/daedelus/llm/Phi-3-mini-4k-instruct-q4.gguf"),
            context_length=2048,
        )

        # Test generation
        messages = [
            {"role": "system", "content": "You are a helpful Linux command expert."},
            {"role": "user", "content": "Explain what 'ls -la' does in one sentence."},
        ]

        response = llm.chat_complete(messages, max_tokens=50)
        print(f"Response: {response}")

    except FileNotFoundError:
        print("Model file not found. Please download Phi-3-mini GGUF model first.")
    except ImportError:
        print("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
