"""
Comprehensive unit tests for CommandEmbedder.

Tests all major functionality:
- Model initialization
- Training from corpus
- Loading and saving models
- Command encoding
- Context encoding
- Tokenization
- Similarity search

Created by: orpheus497
"""

import numpy as np
import pytest

from daedelus.core.embeddings import CommandEmbedder


@pytest.fixture
def model_path(temp_dir):
    """Provide a temporary model path."""
    return temp_dir / "test_model.bin"


@pytest.fixture
def training_commands():
    """Provide a larger set of training commands."""
    return [
        "git status",
        "git add .",
        "git add -A",
        "git commit -m 'Update'",
        "git commit -m 'Fix bug'",
        "git push origin main",
        "git pull origin main",
        "git checkout -b feature",
        "git merge develop",
        "git log --oneline",
        "ls -la",
        "ls -lh /tmp",
        "cd projects",
        "cd /home/user",
        "pwd",
        "python train.py",
        "python test.py --verbose",
        "pip install numpy",
        "pip install pandas scikit-learn",
        "pip freeze > requirements.txt",
        "docker build -t myapp .",
        "docker run -p 8080:8080 myapp",
        "docker ps",
        "docker logs container_id",
        "docker-compose up -d",
        "kubectl get pods",
        "kubectl apply -f deployment.yaml",
        "kubectl describe pod mypod",
        "npm install",
        "npm run build",
        "npm test",
        "cargo build --release",
        "cargo test",
        "rustc main.rs",
        "make clean",
        "make install",
        "./configure --prefix=/usr/local",
        "grep -r 'pattern' .",
        "find . -name '*.py'",
        "sed -i 's/old/new/g' file.txt",
        "awk '{print $1}' data.txt",
        "cat file.txt | wc -l",
        "head -n 10 large.log",
        "tail -f application.log",
        "ssh user@host",
        "scp file.txt user@host:/path",
        "rsync -av source/ dest/",
        "tar -xzf archive.tar.gz",
        "zip -r archive.zip folder/",
        "chmod +x script.sh",
    ]


class TestEmbedderInit:
    """Test embedder initialization."""

    def test_init_default(self, model_path):
        """Test initialization with default parameters."""
        embedder = CommandEmbedder(model_path)

        assert embedder.model_path == model_path
        assert embedder.embedding_dim == 128
        assert embedder.model is None

    def test_init_custom_dim(self, model_path):
        """Test initialization with custom embedding dimension."""
        embedder = CommandEmbedder(model_path, embedding_dim=64)

        assert embedder.embedding_dim == 64

    def test_init_custom_params(self, model_path):
        """Test initialization with custom parameters."""
        embedder = CommandEmbedder(
            model_path,
            embedding_dim=256,
            vocab_size=100000,
            min_count=5,
            word_ngrams=5,
            epoch=10,
        )

        assert embedder.embedding_dim == 256
        assert embedder.vocab_size == 100000
        assert embedder.min_count == 5
        assert embedder.word_ngrams == 5
        assert embedder.epoch == 10


class TestModelTraining:
    """Test model training functionality."""

    def test_train_from_corpus(self, model_path, training_commands):
        """Test training model from command corpus."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)

        embedder.train_from_corpus(training_commands)

        assert embedder.model is not None
        assert model_path.exists()

    def test_train_insufficient_data(self, model_path):
        """Test training with insufficient data raises error."""
        embedder = CommandEmbedder(model_path)

        with pytest.raises(ValueError, match="at least 10 commands"):
            embedder.train_from_corpus(["cmd1", "cmd2", "cmd3"])

    def test_train_creates_vocabulary(self, model_path, training_commands):
        """Test that training creates vocabulary."""
        embedder = CommandEmbedder(model_path, embedding_dim=32, epoch=1)
        embedder.train_from_corpus(training_commands)

        assert len(embedder.model.words) > 0

    def test_train_with_empty_commands(self, model_path):
        """Test training handles empty commands."""
        embedder = CommandEmbedder(model_path, embedding_dim=32, epoch=1)

        # Mix of valid and empty commands
        commands = ["git status", "", "ls -la", "   ", "pwd"] + ["cmd" for _ in range(10)]

        embedder.train_from_corpus(commands)
        assert embedder.model is not None


class TestModelPersistence:
    """Test model loading and saving."""

    def test_save_model(self, model_path, training_commands):
        """Test saving model to disk."""
        embedder = CommandEmbedder(model_path, embedding_dim=32, epoch=1)
        embedder.train_from_corpus(training_commands)

        # Model should already be saved during training
        assert model_path.exists()

    def test_save_without_model(self, model_path):
        """Test saving without trained model raises error."""
        embedder = CommandEmbedder(model_path)

        with pytest.raises(RuntimeError, match="No model to save"):
            embedder.save()

    def test_load_model(self, model_path, training_commands):
        """Test loading model from disk."""
        # Train and save model
        embedder1 = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder1.train_from_corpus(training_commands)

        # Load model in new embedder
        embedder2 = CommandEmbedder(model_path, embedding_dim=64)
        embedder2.load()

        assert embedder2.model is not None
        assert len(embedder2.model.words) > 0

    def test_load_nonexistent_model(self, model_path):
        """Test loading non-existent model raises error."""
        embedder = CommandEmbedder(model_path)

        with pytest.raises(FileNotFoundError):
            embedder.load()

    def test_load_preserves_embeddings(self, model_path, training_commands):
        """Test that loaded model produces same embeddings."""
        # Train model
        embedder1 = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder1.train_from_corpus(training_commands)
        vec1 = embedder1.encode_command("git status")

        # Load model
        embedder2 = CommandEmbedder(model_path, embedding_dim=64)
        embedder2.load()
        vec2 = embedder2.encode_command("git status")

        # Embeddings should be identical
        assert np.allclose(vec1, vec2, rtol=1e-5)


class TestCommandEncoding:
    """Test command encoding functionality."""

    def test_encode_command(self, model_path, training_commands):
        """Test encoding a command."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        vec = embedder.encode_command("git status")

        assert isinstance(vec, np.ndarray)
        assert vec.shape == (64,)
        assert vec.dtype == np.float32

    def test_encode_command_without_model(self, model_path):
        """Test encoding without loaded model raises error."""
        embedder = CommandEmbedder(model_path)

        with pytest.raises(RuntimeError, match="Model not loaded"):
            embedder.encode_command("git status")

    def test_encode_empty_command(self, model_path, training_commands):
        """Test encoding empty command returns zero vector."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        vec = embedder.encode_command("")

        assert np.allclose(vec, np.zeros(64))

    def test_encode_unknown_command(self, model_path, training_commands):
        """Test encoding command with unknown words."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        # Command with completely unknown words
        vec = embedder.encode_command("xyzabc qwerty asdfgh")

        # Should still produce non-zero vector due to subword embeddings
        assert vec.shape == (64,)
        assert not np.allclose(vec, np.zeros(64))

    def test_encode_similar_commands(self, model_path, training_commands):
        """Test that similar commands have similar embeddings."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        vec1 = embedder.encode_command("git status")
        vec2 = embedder.encode_command("git stat")
        vec3 = embedder.encode_command("ls -la")

        # git status and git stat should be more similar than git status and ls
        sim_12 = embedder._cosine_similarity(vec1, vec2)
        sim_13 = embedder._cosine_similarity(vec1, vec3)

        assert sim_12 > sim_13


class TestContextEncoding:
    """Test context encoding functionality."""

    def test_encode_context_with_cwd(self, model_path, training_commands):
        """Test encoding context with CWD."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        vec = embedder.encode_context(cwd="/home/user/projects")

        assert isinstance(vec, np.ndarray)
        assert vec.shape == (64,)
        assert not np.allclose(vec, np.zeros(64))

    def test_encode_context_with_history(self, model_path, training_commands):
        """Test encoding context with command history."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        history = ["git add .", "git commit -m 'test'", "git push"]
        vec = embedder.encode_context(history=history)

        assert vec.shape == (64,)
        assert not np.allclose(vec, np.zeros(64))

    def test_encode_context_with_partial(self, model_path, training_commands):
        """Test encoding context with partial command."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        vec = embedder.encode_context(partial="git st")

        assert vec.shape == (64,)
        assert not np.allclose(vec, np.zeros(64))

    def test_encode_context_combined(self, model_path, training_commands):
        """Test encoding context with all features."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        vec = embedder.encode_context(
            cwd="/home/user/project",
            history=["git add .", "git commit"],
            partial="git pu",
        )

        assert vec.shape == (64,)
        assert not np.allclose(vec, np.zeros(64))

    def test_encode_context_empty(self, model_path, training_commands):
        """Test encoding empty context."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        vec = embedder.encode_context()

        assert np.allclose(vec, np.zeros(64))

    def test_encode_context_without_model(self, model_path):
        """Test encoding context without model raises error."""
        embedder = CommandEmbedder(model_path)

        with pytest.raises(RuntimeError, match="Model not loaded"):
            embedder.encode_context(cwd="/tmp")


class TestTokenization:
    """Test command tokenization."""

    def test_tokenize_simple_command(self, model_path):
        """Test tokenizing simple command."""
        embedder = CommandEmbedder(model_path)

        tokens = embedder.tokenize("git status")

        assert "git" in tokens
        assert "status" in tokens

    def test_tokenize_command_with_flags(self, model_path):
        """Test tokenizing command with flags."""
        embedder = CommandEmbedder(model_path)

        tokens = embedder.tokenize("ls -la /tmp")

        assert "ls" in tokens
        assert "-la" in tokens

    def test_tokenize_command_with_quotes(self, model_path):
        """Test tokenizing command with quoted arguments."""
        embedder = CommandEmbedder(model_path)

        tokens = embedder.tokenize("git commit -m 'Initial commit'")

        assert "git" in tokens
        assert "commit" in tokens
        assert "-m" in tokens
        assert "Initial" in tokens
        assert "commit" in tokens

    def test_tokenize_command_with_path(self, model_path):
        """Test tokenizing command with path."""
        embedder = CommandEmbedder(model_path)

        tokens = embedder.tokenize("cat /home/user/file.txt")

        assert "cat" in tokens
        # Both full path and basename should be included
        assert any("/home/user/file.txt" in t for t in tokens)
        assert any("file.txt" in t or "file" in t for t in tokens)

    def test_tokenize_empty_command(self, model_path):
        """Test tokenizing empty command."""
        embedder = CommandEmbedder(model_path)

        tokens = embedder.tokenize("")

        assert tokens == []

    def test_tokenize_whitespace_only(self, model_path):
        """Test tokenizing whitespace-only command."""
        embedder = CommandEmbedder(model_path)

        tokens = embedder.tokenize("   \t\n   ")

        assert tokens == []

    def test_tokenize_complex_command(self, model_path):
        """Test tokenizing complex command with pipes and redirects."""
        embedder = CommandEmbedder(model_path)

        tokens = embedder.tokenize("cat file.txt | grep pattern > output.txt")

        assert "cat" in tokens
        assert "grep" in tokens

    def test_tokenize_invalid_shell_syntax(self, model_path):
        """Test tokenizing command with invalid shell syntax."""
        embedder = CommandEmbedder(model_path)

        # Should fall back to simple split
        tokens = embedder.tokenize("incomplete 'quote")

        assert len(tokens) > 0


class TestSimilaritySearch:
    """Test similarity search functionality."""

    def test_get_similar_commands(self, model_path, training_commands):
        """Test finding similar commands."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        similar = embedder.get_similar_commands("git stat", training_commands, top_k=3)

        assert len(similar) == 3
        assert all(isinstance(item, tuple) for item in similar)
        assert all(isinstance(item[0], str) and isinstance(item[1], float) for item in similar)

        # Most similar should be "git status"
        assert "git status" in [cmd for cmd, _ in similar]

    def test_get_similar_commands_ordering(self, model_path, training_commands):
        """Test that results are ordered by similarity."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        similar = embedder.get_similar_commands("docker", training_commands, top_k=5)

        # Similarities should be in descending order
        similarities = [sim for _, sim in similar]
        assert similarities == sorted(similarities, reverse=True)

    def test_get_similar_commands_top_k(self, model_path, training_commands):
        """Test that top_k parameter works."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        similar = embedder.get_similar_commands("git", training_commands, top_k=10)

        assert len(similar) == 10

    def test_get_similar_commands_without_model(self, model_path):
        """Test similarity search without model raises error."""
        embedder = CommandEmbedder(model_path)

        with pytest.raises(RuntimeError, match="Model not loaded"):
            embedder.get_similar_commands("git status", ["cmd1", "cmd2"])


class TestCosineSimilarity:
    """Test cosine similarity computation."""

    def test_cosine_similarity_identical(self):
        """Test similarity of identical vectors."""
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)

        sim = CommandEmbedder._cosine_similarity(vec, vec)

        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        """Test similarity of orthogonal vectors."""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        sim = CommandEmbedder._cosine_similarity(vec1, vec2)

        # Orthogonal vectors should have similarity around 0.5 (midpoint of [0,1])
        assert abs(sim - 0.5) < 0.1

    def test_cosine_similarity_opposite(self):
        """Test similarity of opposite vectors."""
        vec1 = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        vec2 = np.array([-1.0, -1.0, -1.0], dtype=np.float32)

        sim = CommandEmbedder._cosine_similarity(vec1, vec2)

        # Opposite vectors should have low similarity
        assert sim < 0.1

    def test_cosine_similarity_zero_vector(self):
        """Test similarity with zero vector."""
        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.zeros(3, dtype=np.float32)

        sim = CommandEmbedder._cosine_similarity(vec1, vec2)

        assert sim == 0.0


class TestRepr:
    """Test string representation."""

    def test_repr_not_loaded(self, model_path):
        """Test repr when model not loaded."""
        embedder = CommandEmbedder(model_path, embedding_dim=128)

        repr_str = repr(embedder)

        assert "CommandEmbedder" in repr_str
        assert "dim=128" in repr_str
        assert "not loaded" in repr_str

    def test_repr_loaded(self, model_path, training_commands):
        """Test repr when model is loaded."""
        embedder = CommandEmbedder(model_path, embedding_dim=64, epoch=1)
        embedder.train_from_corpus(training_commands)

        repr_str = repr(embedder)

        assert "CommandEmbedder" in repr_str
        assert "dim=64" in repr_str
        assert "loaded" in repr_str
