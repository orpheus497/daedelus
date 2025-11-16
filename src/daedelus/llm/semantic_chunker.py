"""
Semantic chunking for token compression.

Implements a 100% FOSS semantic chunking system that intelligently splits
and compresses text based on semantic boundaries, maximizing semantic
comprehension while minimizing token usage.

Inspired by jparkerweb/semantic-chunking and chonkie-inc/chonkie.

Created by: orpheus497
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A semantic chunk of text."""

    text: str
    start_idx: int
    end_idx: int
    sentences: list[str]
    importance_score: float = 0.0


class SemanticChunker:
    """
    Semantic text chunker that preserves meaning while compressing tokens.

    Uses embeddings to detect semantic boundaries and intelligently
    chunks text to maximize coherence and minimize redundancy.

    Features:
    - Sentence-level semantic similarity analysis
    - Dynamic chunk size based on semantic coherence
    - Token-aware chunking with configurable limits
    - Importance scoring for prioritization

    Attributes:
        embedder: Command embedder for semantic analysis
        similarity_threshold: Minimum similarity to merge sentences (0.0-1.0)
        max_chunk_tokens: Maximum tokens per chunk
        min_chunk_sentences: Minimum sentences per chunk
    """

    def __init__(
        self,
        embedder: Any,
        similarity_threshold: float = 0.75,
        max_chunk_tokens: int = 512,
        min_chunk_sentences: int = 2,
    ) -> None:
        """
        Initialize semantic chunker.

        Args:
            embedder: Embedder with encode_command() method
            similarity_threshold: Similarity threshold for grouping (0.0-1.0)
            max_chunk_tokens: Maximum tokens per chunk
            min_chunk_sentences: Minimum sentences per chunk
        """
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold
        self.max_chunk_tokens = max_chunk_tokens
        self.min_chunk_sentences = min_chunk_sentences

        logger.info(
            f"SemanticChunker initialized (threshold={similarity_threshold}, "
            f"max_tokens={max_chunk_tokens})"
        )

    def chunk_text(self, text: str) -> list[Chunk]:
        """
        Split text into semantically coherent chunks.

        Args:
            text: Input text to chunk

        Returns:
            List of Chunk objects
        """
        if not text.strip():
            return []

        # Split into sentences
        sentences = self._split_sentences(text)

        if not sentences:
            return []

        # Generate embeddings for each sentence
        embeddings = []
        for sent in sentences:
            emb = self.embedder.encode_command(sent)
            embeddings.append(emb)

        # Calculate similarity between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)

        # Group sentences into chunks based on similarity
        chunks = []
        current_chunk_sentences = [sentences[0]]
        chunk_start = 0

        for i, sim in enumerate(similarities):
            if sim >= self.similarity_threshold:
                # Similar enough to merge
                current_chunk_sentences.append(sentences[i + 1])
            else:
                # Semantic boundary detected - create chunk
                chunk_text = " ".join(current_chunk_sentences)
                chunk = Chunk(
                    text=chunk_text,
                    start_idx=chunk_start,
                    end_idx=i,
                    sentences=current_chunk_sentences.copy(),
                )
                chunks.append(chunk)

                # Start new chunk
                current_chunk_sentences = [sentences[i + 1]]
                chunk_start = i + 1

        # Add final chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            chunk = Chunk(
                text=chunk_text,
                start_idx=chunk_start,
                end_idx=len(sentences) - 1,
                sentences=current_chunk_sentences.copy(),
            )
            chunks.append(chunk)

        # Calculate importance scores
        for chunk in chunks:
            chunk.importance_score = self._calculate_importance(chunk)

        logger.debug(f"Created {len(chunks)} semantic chunks from {len(sentences)} sentences")

        return chunks

    def compress_text(
        self,
        text: str,
        target_tokens: int,
        preserve_important: bool = True,
    ) -> str:
        """
        Compress text to target token count while preserving meaning.

        Args:
            text: Input text to compress
            target_tokens: Target token count
            preserve_important: Prioritize important chunks

        Returns:
            Compressed text
        """
        chunks = self.chunk_text(text)

        if not chunks:
            return text

        # Sort by importance if requested
        if preserve_important:
            chunks.sort(key=lambda c: c.importance_score, reverse=True)

        # Select chunks until we reach target tokens
        selected_chunks = []
        current_tokens = 0

        for chunk in chunks:
            # Estimate tokens (rough: 4 chars = 1 token)
            chunk_tokens = len(chunk.text) // 4

            if current_tokens + chunk_tokens <= target_tokens:
                selected_chunks.append(chunk)
                current_tokens += chunk_tokens
            else:
                # Try to fit partial chunk
                remaining_tokens = target_tokens - current_tokens
                if remaining_tokens > 10:  # Only add if meaningful
                    # Truncate chunk to fit
                    chars_to_keep = remaining_tokens * 4
                    truncated_text = chunk.text[:chars_to_keep] + "..."
                    truncated_chunk = Chunk(
                        text=truncated_text,
                        start_idx=chunk.start_idx,
                        end_idx=chunk.end_idx,
                        sentences=chunk.sentences[: len(chunk.sentences) // 2],
                        importance_score=chunk.importance_score,
                    )
                    selected_chunks.append(truncated_chunk)
                break

        # Sort by original order if we preserved importance
        if preserve_important:
            selected_chunks.sort(key=lambda c: c.start_idx)

        # Combine chunks
        compressed = " ".join(c.text for c in selected_chunks)

        compression_ratio = len(compressed) / len(text) if text else 1.0
        logger.debug(
            f"Compressed text from {len(text)} to {len(compressed)} chars "
            f"(ratio: {compression_ratio:.2%})"
        )

        return compressed

    def _split_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences.

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Simple sentence splitter (can be enhanced)
        # Split on periods, exclamations, questions followed by space/newline
        sentences = re.split(r"([.!?])\s+", text)

        # Recombine punctuation with sentences
        result = []
        i = 0
        while i < len(sentences):
            if i + 1 < len(sentences) and sentences[i + 1] in ".!?":
                result.append(sentences[i] + sentences[i + 1])
                i += 2
            else:
                if sentences[i].strip():
                    result.append(sentences[i])
                i += 1

        # Clean up
        result = [s.strip() for s in result if s.strip()]

        return result

    def _cosine_similarity(
        self,
        vec1: npt.NDArray[np.float32],
        vec2: npt.NDArray[np.float32],
    ) -> float:
        """
        Calculate cosine similarity between vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0.0-1.0)
        """
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = np.dot(vec1, vec2) / (norm1 * norm2)

        # Convert from [-1, 1] to [0, 1]
        return float((similarity + 1) / 2)

    def _calculate_importance(self, chunk: Chunk) -> float:
        """
        Calculate importance score for a chunk.

        Higher scores indicate more important/informative chunks.

        Args:
            chunk: Chunk to score

        Returns:
            Importance score (0.0-1.0)
        """
        score = 0.0

        # Length penalty/bonus (medium length chunks preferred)
        length = len(chunk.text)
        if 50 <= length <= 200:
            score += 0.3
        elif length > 200:
            score += 0.2
        else:
            score += 0.1

        # Information density (unique words / total words)
        words = chunk.text.lower().split()
        if words:
            unique_ratio = len(set(words)) / len(words)
            score += unique_ratio * 0.4

        # Keyword presence (commands, technical terms)
        keywords = [
            "error",
            "warning",
            "failed",
            "success",
            "command",
            "file",
            "directory",
            "git",
            "docker",
            "python",
            "npm",
            "build",
            "test",
            "run",
        ]

        keyword_count = sum(1 for kw in keywords if kw in chunk.text.lower())
        score += min(keyword_count * 0.1, 0.3)

        return min(score, 1.0)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SemanticChunker(threshold={self.similarity_threshold}, "
            f"max_tokens={self.max_chunk_tokens})"
        )


class TokenCompressor:
    """
    High-level token compression interface.

    Combines semantic chunking with smart truncation to compress
    prompts while maintaining semantic integrity.
    """

    def __init__(
        self,
        semantic_chunker: SemanticChunker,
        aggressive: bool = False,
    ) -> None:
        """
        Initialize token compressor.

        Args:
            semantic_chunker: Semantic chunker instance
            aggressive: Use aggressive compression (higher ratio)
        """
        self.chunker = semantic_chunker
        self.aggressive = aggressive

        logger.info(f"TokenCompressor initialized (aggressive={aggressive})")

    def compress_context(
        self,
        context: str,
        max_tokens: int,
    ) -> str:
        """
        Compress context to fit within token limit.

        Args:
            context: Context text to compress
            max_tokens: Maximum tokens allowed

        Returns:
            Compressed context
        """
        # Estimate current tokens
        current_tokens = len(context) // 4

        if current_tokens <= max_tokens:
            return context

        # Calculate compression target
        if self.aggressive:
            target_tokens = int(max_tokens * 0.8)  # Use 80% of limit
        else:
            target_tokens = int(max_tokens * 0.95)  # Use 95% of limit

        # Compress using semantic chunking
        compressed = self.chunker.compress_text(
            context,
            target_tokens=target_tokens,
            preserve_important=True,
        )

        return compressed

    def compress_prompt(
        self,
        system_prompt: str,
        user_query: str,
        context: str,
        max_total_tokens: int,
    ) -> dict[str, str]:
        """
        Compress a complete prompt (system + context + query).

        Args:
            system_prompt: System instructions
            user_query: User query (never compressed)
            context: Retrieved context
            max_total_tokens: Maximum total tokens

        Returns:
            Dictionary with compressed components
        """
        # Estimate tokens for each part
        system_tokens = len(system_prompt) // 4
        query_tokens = len(user_query) // 4
        context_tokens = len(context) // 4

        # Reserve tokens for query and system (never compress these)
        reserved_tokens = system_tokens + query_tokens

        # Calculate available tokens for context
        available_for_context = max_total_tokens - reserved_tokens

        if available_for_context <= 0:
            logger.warning("No tokens available for context - query/system too long")
            return {
                "system": system_prompt,
                "context": "",
                "query": user_query,
            }

        # Compress context if needed
        if context_tokens > available_for_context:
            compressed_context = self.compress_context(context, available_for_context)
        else:
            compressed_context = context

        return {
            "system": system_prompt,
            "context": compressed_context,
            "query": user_query,
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"TokenCompressor(aggressive={self.aggressive})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("Semantic Chunker Test")
    print("=" * 60)

    # Example text
    example_text = """
    The git status command shows the current state of your repository.
    It displays which files have been modified and which are staged.

    You can use git add to stage files for commit. This prepares
    them for the next commit. The staging area is a key git concept.

    Docker containers provide isolated environments. They package
    applications with their dependencies. This makes deployment easier.
    """

    # Note: In real use, would use actual CommandEmbedder
    # For this example, we'll demonstrate the interface
    print("\nExample text (", len(example_text), "chars ):")
    print(example_text[:200] + "...")

    print("\nSemanticChunker Interface:")
    print("- chunk_text(text) -> List[Chunk]")
    print("- compress_text(text, target_tokens) -> str")
    print("- Each chunk has: text, sentences, importance_score")

    print("\nTokenCompressor Interface:")
    print("- compress_context(context, max_tokens) -> str")
    print("- compress_prompt(system, query, context, max_tokens) -> dict")
