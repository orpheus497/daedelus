"""
LLM Manager for Daedelus Phase 2.

Manages the local LLM (Phi-3-mini via llama.cpp) for command understanding
and generation.

The LLM understands its identity as Deus (Daedelus) and its purpose
as a terminal assistant created by orpheus497.

Created by: orpheus497
"""

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None  # type: ignore


class LLMCache:
    """
    Simple semantic cache for LLM queries.

    Caches responses based on prompt hash to avoid redundant LLM calls.
    Includes TTL (time-to-live) for cache entries.
    """

    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of cached entries
            default_ttl: Default time-to-live in seconds (1 hour)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: dict[str, dict[str, Any]] = {}
        self.access_times: dict[str, float] = {}
        self._lock = threading.Lock()

    def _get_key(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate cache key from prompt and parameters."""
        key_str = f"{prompt}|{max_tokens}|{temperature:.2f}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str | None:
        """Get cached response if available and not expired."""
        with self._lock:
            key = self._get_key(prompt, max_tokens, temperature)

            if key not in self.cache:
                return None

            entry = self.cache[key]
            age = time.time() - entry["timestamp"]

            # Check if expired
            if age > entry["ttl"]:
                del self.cache[key]
                del self.access_times[key]
                return None

            # Update access time
            self.access_times[key] = time.time()
            return entry["response"]

    def set(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response: str,
        ttl: int | None = None,
    ) -> None:
        """Cache a response."""
        with self._lock:
            key = self._get_key(prompt, max_tokens, temperature)

            # Evict oldest if at capacity
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.access_times, key=self.access_times.get)  # type: ignore
                del self.cache[oldest_key]
                del self.access_times[oldest_key]

            self.cache[key] = {
                "response": response,
                "timestamp": time.time(),
                "ttl": ttl or self.default_ttl,
            }
            self.access_times[key] = time.time()

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hit_rate": 0.0,  # Would need counters to track this
            }


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
        enable_cache: bool = True,
        cache_size: int = 100,
        default_timeout: float = 30.0,
    ) -> None:
        """
        Initialize LLM manager with caching and timeout support.

        Args:
            model_path: Path to GGUF model file (e.g., Phi-3-mini-4k-instruct-q4.gguf)
            context_length: Context window size (tokens)
            temperature: Sampling temperature (0.0-1.0)
            top_p: Nucleus sampling parameter (0.0-1.0)
            n_gpu_layers: Number of layers to offload to GPU (0 = CPU only)
            verbose: Enable verbose logging from llama.cpp
            enable_cache: Enable response caching
            cache_size: Maximum cache entries
            default_timeout: Default generation timeout in seconds

        Raises:
            ImportError: If llama-cpp-python not installed
            FileNotFoundError: If model file not found
            RuntimeError: If model loading fails
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
        self.default_timeout = default_timeout
        self.model: Any = None
        self._model_loaded = False

        # Initialize cache
        self.cache = LLMCache(max_size=cache_size) if enable_cache else None

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        logger.info(f"Loading LLM from {self.model_path}...")

        try:
            # Load model with error handling
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=context_length,
                n_gpu_layers=n_gpu_layers,
                verbose=verbose,
            )
            self._model_loaded = True
            logger.info("LLM loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e

    def generate(
        self,
        prompt: str,
        max_tokens: int = 100,
        temperature: float | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        timeout: float | None = None,
        use_cache: bool = True,
    ) -> str:
        """
        Generate text from prompt with caching and timeout support.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (uses default if None)
            top_p: Nucleus sampling (uses default if None)
            stop: List of stop sequences
            timeout: Generation timeout in seconds (uses default if None)
            use_cache: Whether to use cache for this request

        Returns:
            Generated text

        Raises:
            RuntimeError: If model not loaded or generation fails
            TimeoutError: If generation exceeds timeout

        Performance:
            - Caching provides instant responses for repeated queries
            - Timeout prevents hanging on complex prompts
        """
        if not self._model_loaded or self.model is None:
            raise RuntimeError("Model not loaded or failed to load")

        # Use instance defaults if not specified
        temp = temperature if temperature is not None else self.temperature
        top_p_val = top_p if top_p is not None else self.top_p
        timeout_val = timeout if timeout is not None else self.default_timeout

        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get(prompt, max_tokens, temp)
            if cached:
                logger.debug(f"Cache hit for prompt: {prompt[:50]}...")
                return cached

        logger.debug(f"Generating with prompt: {prompt[:50]}...")

        # Generate with timeout
        result_container: list[Any] = [None]
        exception_container: list[Exception] = []

        def _generate() -> None:
            try:
                response = self.model(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temp,
                    top_p=top_p_val,
                    stop=stop or [],
                    echo=False,
                )
                result_container[0] = response
            except Exception as e:
                exception_container.append(e)

        # Run generation in thread with timeout
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()
        thread.join(timeout=timeout_val)

        # Check if thread finished
        if thread.is_alive():
            logger.warning(f"Generation timed out after {timeout_val}s")
            raise TimeoutError(f"LLM generation exceeded {timeout_val}s timeout")

        # Check for exceptions
        if exception_container:
            raise RuntimeError(f"Generation failed: {exception_container[0]}") from exception_container[0]

        # Extract generated text
        response = result_container[0]
        if isinstance(response, dict):
            text = response.get("choices", [{}])[0].get("text", "")
        else:
            text = str(response) if response else ""

        text = text.strip()

        # Cache the result
        if use_cache and self.cache and text:
            self.cache.set(prompt, max_tokens, temp, text)

        return text

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

    def health_check(self) -> dict[str, Any]:
        """
        Check model health and readiness.

        Returns:
            Dictionary with health status information

        Health checks:
            - Model loaded successfully
            - Model file exists and is readable
            - Test generation works
            - Cache statistics
        """
        health = {
            "model_loaded": self._model_loaded,
            "model_exists": self.model_path.exists(),
            "model_size_mb": 0.0,
            "model_readable": False,
            "test_generation": False,
            "cache_enabled": self.cache is not None,
            "cache_stats": {},
        }

        # Check model file
        if self.model_path.exists():
            try:
                health["model_size_mb"] = self.model_path.stat().st_size / (1024 * 1024)
                health["model_readable"] = self.model_path.is_file()
            except Exception as e:
                logger.warning(f"Failed to read model file: {e}")

        # Test generation if model loaded
        if self._model_loaded and self.model:
            try:
                test_prompt = "Test"
                result = self.generate(
                    test_prompt,
                    max_tokens=5,
                    temperature=0.1,
                    timeout=5.0,
                    use_cache=False,
                )
                health["test_generation"] = bool(result)
            except Exception as e:
                logger.warning(f"Health check generation failed: {e}")
                health["test_generation_error"] = str(e)

        # Cache statistics
        if self.cache:
            health["cache_stats"] = self.cache.get_stats()

        return health

    def is_healthy(self) -> bool:
        """
        Quick health check.

        Returns:
            True if model is loaded and operational
        """
        return self._model_loaded and self.model is not None

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics dictionary
        """
        if self.cache:
            return self.cache.get_stats()
        return {"cache_enabled": False}

    def clear_cache(self) -> None:
        """Clear the response cache."""
        if self.cache:
            self.cache.clear()
            logger.info("LLM cache cleared")

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
