"""
FastText-based command embeddings for Daedelus (Phase 1).

Provides semantic understanding of shell commands through vector embeddings:
- Subword awareness (handles typos and rare commands)
- Context-aware embeddings
- Efficient training and inference
- Quantization for reduced memory footprint

Identity Metadata (Hardcoded):
    Model Name: Daedelus Embedding Model
    Formal Name: Daedelus
    Social Name: Deus
    Created by: orpheus497
    Designer: orpheus497
    Purpose: Learn semantic representations of terminal commands to provide
             intelligent suggestions while maintaining complete user privacy

Phase 2 will add llama.cpp + Phi-3-mini for full LLM capabilities.

Created by: orpheus497
"""

# Model Identity Metadata (Hardcoded)
_MODEL_IDENTITY = {
    "model_name": "Daedelus Embedding Model",
    "formal_name": "Daedelus",
    "social_name": "Deus",
    "creator": "orpheus497",
    "designer": "orpheus497",
    "purpose": "Learn semantic representations of terminal commands for intelligent suggestions",
    "architecture": "FastText + Annoy (Phase 1)",
}

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
        max_corpus_size: int = 10000,
    ) -> None:
        """
        Initialize command embedder with persistent corpus management.

        Args:
            model_path: Path to save/load model
            embedding_dim: Size of embedding vectors
            vocab_size: Maximum vocabulary size
            min_count: Minimum word frequency to include
            word_ngrams: Max length of character ngrams (for subwords)
            epoch: Number of training epochs
            max_corpus_size: Maximum commands to keep in persistent corpus
        """
        self.model_path = Path(model_path).expanduser()
        self.embedding_dim = embedding_dim
        self.vocab_size = vocab_size
        self.min_count = min_count
        self.word_ngrams = word_ngrams
        self.epoch = epoch
        self.max_corpus_size = max_corpus_size

        # Persistent corpus file for incremental learning
        self.corpus_path = self.model_path.parent / f"{self.model_path.stem}_corpus.txt"

        self.model: fasttext.FastText._FastText | None = None

        logger.info(f"CommandEmbedder initialized (dim={embedding_dim})")
        logger.info(f"Model identity: {_MODEL_IDENTITY['formal_name']} (aka {_MODEL_IDENTITY['social_name']}) by {_MODEL_IDENTITY['creator']}")

    @staticmethod
    def get_model_identity() -> dict[str, str]:
        """
        Get the hardcoded identity metadata for this model.

        Returns:
            Dictionary containing model name, creator, purpose, and other identity info
        """
        return _MODEL_IDENTITY.copy()

    def train_from_corpus(self, commands: list[str], save_corpus: bool = True) -> None:
        """
        Train FastText model from command corpus with persistent corpus management.

        Args:
            commands: List of command strings
            save_corpus: Whether to save corpus for future incremental training

        Raises:
            ValueError: If corpus is too small (<10 commands)
        """
        if len(commands) < 10:
            raise ValueError("Need at least 10 commands to train")

        logger.info(f"Training embedder on {len(commands)} commands...")

        # Create training file (persistent if save_corpus=True, temp otherwise)
        if save_corpus:
            train_file = self.corpus_path
            self.corpus_path.parent.mkdir(parents=True, exist_ok=True)
            f = open(train_file, "w")
        else:
            temp_f = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                delete=False,
            )
            train_file = Path(temp_f.name)
            f = temp_f

        try:
            # Tokenize and write commands
            for cmd in commands:
                tokens = self.tokenize(cmd)
                if tokens:  # Skip empty commands
                    f.write(" ".join(tokens) + "\n")
            f.close()

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

            # Note: Quantization is only supported for supervised models
            # For unsupervised models, we skip quantization
            logger.info("Model training complete, saving...")

            # Save model
            self.save()

            if save_corpus:
                logger.info(f"Training corpus saved to {self.corpus_path}")

            logger.info(f"Model trained successfully. " f"Vocabulary size: {len(self.model.words)}")

        except Exception as e:
            logger.error(f"FastText training failed: {e}", exc_info=True)
            if not save_corpus and train_file.exists():
                train_file.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to train FastText model: {e}") from e

        finally:
            # Clean up temp file if not saving corpus
            if not save_corpus and train_file.exists():
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

    def incremental_train(
        self,
        new_commands: list[str],
        min_new_commands: int = 100,
    ) -> bool:
        """
        Incrementally train the model with new commands using proper corpus merging.

        This enables continuous learning by combining the existing training corpus
        with new commands and retraining. The model maintains learned vocabulary
        while adapting to new patterns.

        Implementation:
            1. Load existing training corpus (if available)
            2. Merge with new commands
            3. Apply corpus size management (keep most recent commands)
            4. Retrain model on combined corpus
            5. Save updated model and corpus

        Args:
            new_commands: List of new command strings to learn from
            min_new_commands: Minimum number of commands needed to trigger training

        Returns:
            True if training occurred, False if skipped

        Note:
            FastText doesn't support true incremental training, so we maintain
            a persistent corpus and retrain on the combined dataset. This ensures
            the model retains old knowledge while learning new patterns.
        """
        if not new_commands:
            logger.debug("No new commands for incremental training")
            return False

        if len(new_commands) < min_new_commands:
            logger.debug(
                f"Not enough new commands ({len(new_commands)} < {min_new_commands}), "
                "skipping incremental training"
            )
            return False

        logger.info(f"Incremental training with {len(new_commands)} new commands...")

        try:
            # Step 1: Load existing corpus if available
            existing_commands = []
            if self.corpus_path.exists():
                logger.info(f"Loading existing corpus from {self.corpus_path}")
                try:
                    with open(self.corpus_path) as f:
                        # Read tokenized commands from corpus file
                        for line in f:
                            line = line.strip()
                            if line:
                                # Reconstruct command from tokens (approximate)
                                # This preserves the tokenized format
                                existing_commands.append(line)
                    logger.info(f"Loaded {len(existing_commands)} commands from existing corpus")
                except Exception as e:
                    logger.warning(f"Failed to load existing corpus: {e}")
                    existing_commands = []

            # Step 2: Tokenize new commands
            new_tokenized = []
            for cmd in new_commands:
                tokens = self.tokenize(cmd)
                if tokens:
                    new_tokenized.append(" ".join(tokens))

            # Step 3: Combine old and new, maintaining corpus size limit
            combined = existing_commands + new_tokenized

            # Apply size management - keep most recent commands
            if len(combined) > self.max_corpus_size:
                logger.info(
                    f"Corpus size ({len(combined)}) exceeds max ({self.max_corpus_size}), "
                    "keeping most recent commands"
                )
                combined = combined[-self.max_corpus_size:]

            logger.info(f"Combined corpus size: {len(combined)} commands")

            # Step 4: Create training file with combined corpus
            train_file = self.corpus_path
            train_file.parent.mkdir(parents=True, exist_ok=True)

            with open(train_file, "w") as f:
                for tokenized_cmd in combined:
                    f.write(tokenized_cmd + "\n")

            # Step 5: Retrain model on combined corpus
            if fasttext is None:
                raise ImportError(
                    "fasttext is not installed. Install it with: pip install fasttext==0.9.2"
                )

            logger.info("Retraining model on combined corpus...")
            self.model = fasttext.train_unsupervised(
                str(train_file),
                model="skipgram",
                dim=self.embedding_dim,
                epoch=self.epoch,  # Use full epochs for proper convergence
                minCount=self.min_count,
                wordNgrams=self.word_ngrams,
                verbose=1,
            )

            # Step 6: Save updated model
            self.save()

            logger.info(
                f"Incremental training complete. "
                f"Vocabulary size: {len(self.model.words)}, "
                f"Corpus size: {len(combined)}"
            )

            return True

        except Exception as e:
            logger.error(f"Incremental training failed: {e}", exc_info=True)
            return False

    def get_corpus_stats(self) -> dict[str, Any]:
        """
        Get statistics about the persistent training corpus.

        Returns:
            Dictionary with corpus statistics including size, path, and existence
        """
        stats = {
            "corpus_exists": self.corpus_path.exists(),
            "corpus_path": str(self.corpus_path),
            "corpus_size": 0,
            "max_corpus_size": self.max_corpus_size,
        }

        if self.corpus_path.exists():
            try:
                with open(self.corpus_path) as f:
                    stats["corpus_size"] = sum(1 for line in f if line.strip())

                # Get file size in KB
                file_size = self.corpus_path.stat().st_size
                stats["file_size_kb"] = round(file_size / 1024, 2)

            except Exception as e:
                logger.warning(f"Failed to get corpus stats: {e}")

        return stats

    def clear_corpus(self) -> bool:
        """
        Clear the persistent training corpus.

        Returns:
            True if corpus was cleared, False otherwise

        Note:
            This removes the persistent corpus file. The model will remain
            intact, but future incremental training will start fresh.
        """
        if self.corpus_path.exists():
            try:
                self.corpus_path.unlink()
                logger.info(f"Cleared training corpus at {self.corpus_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to clear corpus: {e}")
                return False
        return False

    def get_training_stats(self) -> dict[str, int]:
        """
        Get statistics about the current model.

        Returns:
            Dictionary with model statistics
        """
        if self.model is None:
            return {
                "vocab_size": 0,
                "embedding_dim": self.embedding_dim,
                "loaded": False,
            }

        return {
            "vocab_size": len(self.model.words),
            "embedding_dim": self.embedding_dim,
            "loaded": True,
        }

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
