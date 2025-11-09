"""
FastText-based command embeddings for Daedalus (Phase 1).

Provides semantic understanding of shell commands through vector embeddings:
- Subword awareness (handles typos and rare commands)
- Context-aware embeddings
- Efficient training and inference
- Quantization for reduced memory footprint

Phase 2 will add llama.cpp + Phi-3-mini for full LLM capabilities.

Created by: orpheus497
"""

import logging
import re
import shlex
import tempfile
from pathlib import Path

import numpy as np
import numpy.typing as npt

try:
    import fasttext
except ImportError:
    fasttext = None  # type: ignore

logger = logging.getLogger(__name__)


class CommandEmbedder:
    """
    FastText-based command embedding model.

    Uses unsupervised learning (skipgram) to create vector representations
    of commands that capture semantic similarity.

    Features:
    - Subword embeddings (handles typos and OOV words)
    - Context-aware encoding (CWD, history, environment)
    - Efficient training on command corpus
    - Model quantization for <50MB footprint

    Attributes:
        model_path: Path to saved FastText model
        embedding_dim: Dimensionality of embeddings
        model: FastText model instance
    """

    def __init__(
        self,
        model_path: Path,
        embedding_dim: int = 128,
        vocab_size: int = 50000,
        min_count: int = 2,
        word_ngrams: int = 3,
        epoch: int = 5,
    ) -> None:
        """
        Initialize command embedder.

        Args:
            model_path: Path to save/load model
            embedding_dim: Size of embedding vectors
            vocab_size: Maximum vocabulary size
            min_count: Minimum word frequency to include
            word_ngrams: Max length of character ngrams (for subwords)
            epoch: Number of training epochs
        """
        self.model_path = Path(model_path).expanduser()
        self.embedding_dim = embedding_dim
        self.vocab_size = vocab_size
        self.min_count = min_count
        self.word_ngrams = word_ngrams
        self.epoch = epoch

        self.model: fasttext.FastText._FastText | None = None

        logger.info(f"CommandEmbedder initialized (dim={embedding_dim})")

    def train_from_corpus(self, commands: list[str]) -> None:
        """
        Train FastText model from command corpus.

        Args:
            commands: List of command strings

        Raises:
            ValueError: If corpus is too small (<10 commands)
        """
        if len(commands) < 10:
            raise ValueError("Need at least 10 commands to train")

        logger.info(f"Training embedder on {len(commands)} commands...")

        # Create temporary training file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            train_file = Path(f.name)

            # Tokenize and write commands
            for cmd in commands:
                tokens = self.tokenize(cmd)
                if tokens:  # Skip empty commands
                    f.write(" ".join(tokens) + "\n")

        try:
            # Train unsupervised FastText model
            if fasttext is None:
                raise ImportError(
                    "fasttext is not installed. Install it with: pip install fasttext==0.9.2"
                )
            logger.info(f"Training FastText model on {len(commands)} commands...")
            self.model = fasttext.train_unsupervised(
                str(train_file),
                model="skipgram",  # Skip-gram is better for rare words
                dim=self.embedding_dim,
                epoch=self.epoch,
                minCount=self.min_count,
                wordNgrams=self.word_ngrams,  # Subword support
                verbose=2,
            )

            # Quantize model to reduce size
            logger.info("Quantizing model...")
            self.model.quantize(
                input=str(train_file),
                retrain=True,
                cutoff=self.vocab_size,
            )

            # Save model
            self.save()

            logger.info(f"Model trained successfully. " f"Vocabulary size: {len(self.model.words)}")

        except Exception as e:
            logger.error(f"FastText training failed: {e}", exc_info=True)
            if train_file.exists():
                train_file.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to train FastText model: {e}") from e

        finally:
            # Clean up temp file
            if train_file.exists():
                train_file.unlink()

    def load(self) -> None:
        """
        Load existing FastText model.

        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        if fasttext is None:
            raise ImportError(
                "fasttext is not installed. Install it with: pip install fasttext==0.9.2"
            )

        logger.info(f"Loading model from {self.model_path}")
        self.model = fasttext.load_model(str(self.model_path))

        logger.info(f"Model loaded. Vocab size: {len(self.model.words)}")

    def save(self) -> None:
        """
        Save model to disk.

        Raises:
            RuntimeError: If model hasn't been trained
        """
        if self.model is None:
            raise RuntimeError("No model to save. Train or load first.")

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(self.model_path))

        logger.info(f"Model saved to {self.model_path}")

    def encode_command(self, command: str) -> npt.NDArray[np.float32]:
        """
        Convert command string to embedding vector.

        Args:
            command: Command string to encode

        Returns:
            Embedding vector (shape: [embedding_dim])

        Raises:
            RuntimeError: If model hasn't been loaded
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        tokens = self.tokenize(command)

        if not tokens:
            # Return zero vector for empty command
            return np.zeros(self.embedding_dim, dtype=np.float32)

        # Get word vectors
        word_vecs = [self.model.get_word_vector(token) for token in tokens]

        # Mean pooling
        embedding = np.mean(word_vecs, axis=0).astype(np.float32)

        return embedding

    def encode_context(
        self,
        cwd: str | None = None,
        history: list[str] | None = None,
        partial: str | None = None,
    ) -> npt.NDArray[np.float32]:
        """
        Encode context information into a vector.

        Context includes:
        - Current working directory
        - Recent command history
        - Partial command being typed

        Args:
            cwd: Current working directory
            history: List of recent commands
            partial: Partially typed command

        Returns:
            Context embedding vector
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        features = []

        # CWD features (directory name)
        if cwd:
            dir_name = Path(cwd).name
            if dir_name:
                dir_vec = self.model.get_word_vector(dir_name)
                features.append(dir_vec)

        # History features (average of recent commands)
        if history:
            hist_vecs = [self.encode_command(cmd) for cmd in history[-5:]]
            if hist_vecs:
                hist_mean = np.mean(hist_vecs, axis=0)
                features.append(hist_mean)

        # Partial command features
        if partial:
            partial_vec = self.encode_command(partial)
            features.append(partial_vec)

        # Combine features
        if features:
            return np.mean(features, axis=0).astype(np.float32)
        else:
            return np.zeros(self.embedding_dim, dtype=np.float32)

    def tokenize(self, command: str) -> list[str]:
        """
        Tokenize shell command into meaningful tokens.

        Handles:
        - Shell quoting
        - Flags and options
        - Special characters
        - Pipes and redirects

        Args:
            command: Command string

        Returns:
            List of tokens

        Example:
            >>> embedder.tokenize("git commit -m 'Initial commit'")
            ['git', 'commit', '-m', 'Initial', 'commit']
        """
        # Remove leading/trailing whitespace
        command = command.strip()

        if not command:
            return []

        # Try proper shell parsing first
        try:
            parts = shlex.split(command)
        except ValueError:
            # Fallback to simple split if shell parsing fails
            parts = command.split()

        tokens = []

        for part in parts:
            # Keep flags whole
            if part.startswith("-"):
                tokens.append(part)
            # Handle paths (keep basename)
            elif "/" in part:
                # Split path and keep both full path and basename
                tokens.append(part)
                basename = Path(part).name
                if basename != part:
                    tokens.append(basename)
            # Regular words: split on special chars but keep them
            else:
                # Extract alphanumeric sequences and special chars separately
                sub_tokens = re.findall(r"\w+|[^\w\s]", part)
                tokens.extend(sub_tokens)

        return tokens

    def get_similar_commands(
        self,
        command: str,
        candidates: list[str],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """
        Find most similar commands from a list of candidates.

        Args:
            command: Query command
            candidates: List of candidate commands
            top_k: Number of results to return

        Returns:
            List of (command, similarity_score) tuples, sorted by similarity
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        query_vec = self.encode_command(command)

        # Compute similarities
        similarities = []
        for candidate in candidates:
            candidate_vec = self.encode_command(candidate)
            similarity = self._cosine_similarity(query_vec, candidate_vec)
            similarities.append((candidate, float(similarity)))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    @staticmethod
    def _cosine_similarity(
        vec1: npt.NDArray[np.float32],
        vec2: npt.NDArray[np.float32],
    ) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score in [0, 1]
        """
        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Cosine similarity
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)

        # Convert from [-1, 1] to [0, 1]
        return float((similarity + 1) / 2)

    def __repr__(self) -> str:
        """String representation."""
        status = "loaded" if self.model is not None else "not loaded"
        return f"CommandEmbedder(dim={self.embedding_dim}, status={status})"


# Example usage and testing
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Example commands for testing
    example_commands = [
        "git status",
        "git add .",
        "git commit -m 'update'",
        "git push origin main",
        "ls -la",
        "cd projects",
        "python train.py",
        "pip install numpy",
        "docker build -t myapp .",
        "docker run -p 8080:8080 myapp",
        "kubectl get pods",
        "kubectl apply -f deployment.yaml",
        "npm install",
        "npm run build",
        "cargo build --release",
        "rustc main.rs",
    ]

    # Initialize embedder
    model_path = Path("/tmp/daedelus_test_model.bin")
    embedder = CommandEmbedder(model_path)

    # Train model
    embedder.train_from_corpus(example_commands)

    # Test encoding
    vec = embedder.encode_command("git status")
    print(f"Embedding shape: {vec.shape}")
    print(f"Embedding: {vec[:10]}...")  # Show first 10 dims

    # Test similarity
    similar = embedder.get_similar_commands("git stat", example_commands)
    print("\nMost similar to 'git stat':")
    for cmd, sim in similar:
        print(f"  {sim:.3f} - {cmd}")
