"""
Comprehensive unit tests for VectorStore.

Tests all major functionality:
- Store initialization
- Adding vectors
- Building index
- Searching
- Persistence (save/load)
- Rebuilding
- Statistics

Created by: orpheus497
"""

import pickle
from pathlib import Path

import numpy as np
import pytest

from daedelus.core.vector_store import VectorStore


@pytest.fixture
def index_path(temp_dir):
    """Provide a temporary index path."""
    return temp_dir / "test_index"


@pytest.fixture
def sample_vectors():
    """Provide sample vectors for testing."""
    np.random.seed(42)
    return [np.random.randn(128).astype(np.float32) for _ in range(100)]


@pytest.fixture
def sample_commands():
    """Provide sample command strings."""
    return [f"command_{i}" for i in range(100)]


class TestVectorStoreInit:
    """Test vector store initialization."""

    def test_init_default(self, index_path):
        """Test initialization with default parameters."""
        store = VectorStore(index_path)

        assert store.index_path == index_path
        assert store.dim == 128
        assert store.n_trees == 10
        assert store.metric == "angular"
        assert len(store.metadata) == 0
        assert not store._built

    def test_init_custom_dim(self, index_path):
        """Test initialization with custom dimension."""
        store = VectorStore(index_path, dim=64)

        assert store.dim == 64

    def test_init_custom_trees(self, index_path):
        """Test initialization with custom number of trees."""
        store = VectorStore(index_path, n_trees=20)

        assert store.n_trees == 20

    def test_init_custom_metric(self, index_path):
        """Test initialization with custom metric."""
        store = VectorStore(index_path, metric="euclidean")

        assert store.metric == "euclidean"


class TestAddingVectors:
    """Test adding vectors to the store."""

    def test_add_vector(self, index_path):
        """Test adding a single vector."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(128).astype(np.float32)

        idx = store.add(vec, "test command", {"cwd": "/tmp"})

        assert idx == 0
        assert len(store.metadata) == 1
        assert store.metadata[0]["command"] == "test command"
        assert store.metadata[0]["cwd"] == "/tmp"

    def test_add_multiple_vectors(self, index_path):
        """Test adding multiple vectors."""
        store = VectorStore(index_path, dim=128)

        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            idx = store.add(vec, f"command {i}")
            assert idx == i

        assert len(store.metadata) == 10

    def test_add_wrong_dimension(self, index_path):
        """Test adding vector with wrong dimension raises error."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(64).astype(np.float32)

        with pytest.raises(ValueError, match="dimension mismatch"):
            store.add(vec, "test")

    def test_add_after_build(self, index_path):
        """Test that adding after build raises error."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(128).astype(np.float32)

        store.add(vec, "cmd1")
        store.build()

        with pytest.raises(RuntimeError, match="Cannot add to built index"):
            store.add(vec, "cmd2")

    def test_add_with_metadata(self, index_path):
        """Test adding vector with metadata."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(128).astype(np.float32)

        metadata = {
            "timestamp": 1234567890.0,
            "cwd": "/home/user",
            "success_rate": 0.95,
        }

        idx = store.add(vec, "git status", metadata)

        assert store.metadata[idx]["command"] == "git status"
        assert store.metadata[idx]["timestamp"] == 1234567890.0
        assert store.metadata[idx]["success_rate"] == 0.95

    def test_add_without_metadata(self, index_path):
        """Test adding vector without metadata."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(128).astype(np.float32)

        idx = store.add(vec, "test command")

        assert "command" in store.metadata[idx]
        assert store.metadata[idx]["command"] == "test command"


class TestBuildingIndex:
    """Test index building."""

    def test_build_index(self, index_path):
        """Test building index."""
        store = VectorStore(index_path, dim=128)

        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")

        store.build()

        assert store._built

    def test_build_empty_index(self, index_path):
        """Test building empty index raises error."""
        store = VectorStore(index_path)

        with pytest.raises(RuntimeError, match="Cannot build empty index"):
            store.build()

    def test_build_enables_search(self, index_path):
        """Test that building enables search."""
        store = VectorStore(index_path, dim=128)

        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")

        store.build()

        # Should be able to search now
        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=3)

        assert len(results) > 0


class TestSearching:
    """Test vector search functionality."""

    def test_search_basic(self, index_path):
        """Test basic search."""
        store = VectorStore(index_path, dim=128)

        # Add and build
        vectors = [np.random.randn(128).astype(np.float32) for _ in range(50)]
        for i, vec in enumerate(vectors):
            store.add(vec, f"cmd{i}")
        store.build()

        # Search
        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=5)

        assert len(results) == 5
        assert all("command" in r for r in results)
        assert all("similarity" in r for r in results)
        assert all("distance" in r for r in results)

    def test_search_before_build(self, index_path):
        """Test searching before build raises error."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, "cmd")

        query = np.random.randn(128).astype(np.float32)

        with pytest.raises(RuntimeError, match="Index not built"):
            store.search(query)

    def test_search_top_k(self, index_path):
        """Test that top_k parameter works."""
        store = VectorStore(index_path, dim=128)

        for i in range(100):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        query = np.random.randn(128).astype(np.float32)

        results = store.search(query, top_k=10)
        assert len(results) == 10

        results = store.search(query, top_k=3)
        assert len(results) == 3

    def test_search_includes_metadata(self, index_path):
        """Test that search results include metadata."""
        store = VectorStore(index_path, dim=128)

        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            metadata = {"cwd": f"/path{i}", "freq": i * 10}
            store.add(vec, f"cmd{i}", metadata)
        store.build()

        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=3)

        for r in results:
            assert "cwd" in r
            assert "freq" in r

    def test_search_similarity_range(self, index_path):
        """Test that similarity scores are in valid range."""
        store = VectorStore(index_path, dim=128)

        for i in range(50):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=10)

        for r in results:
            assert 0.0 <= r["similarity"] <= 1.0

    def test_search_ordering(self, index_path):
        """Test that results are ordered by similarity."""
        store = VectorStore(index_path, dim=128)

        for i in range(50):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=10)

        similarities = [r["similarity"] for r in results]
        # Should be in descending order
        assert similarities == sorted(similarities, reverse=True)

    def test_search_without_distances(self, index_path):
        """Test search without distance computation."""
        store = VectorStore(index_path, dim=128)

        for i in range(20):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=5, include_distances=False)

        assert len(results) == 5


class TestPersistence:
    """Test saving and loading index."""

    def test_save_index(self, index_path):
        """Test saving index to disk."""
        store = VectorStore(index_path, dim=128)

        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}", {"value": i})
        store.build()

        store.save()

        # Check files exist
        assert index_path.with_suffix(".ann").exists()
        assert index_path.with_suffix(".meta").exists()

    def test_save_unbuilt_index(self, index_path):
        """Test saving unbuilt index raises error."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, "cmd")

        with pytest.raises(RuntimeError, match="Cannot save unbuilt index"):
            store.save()

    def test_load_index(self, index_path):
        """Test loading index from disk."""
        # Create and save index
        store1 = VectorStore(index_path, dim=128)
        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            store1.add(vec, f"cmd{i}", {"value": i})
        store1.build()
        store1.save()

        # Load index
        store2 = VectorStore(index_path, dim=128)
        store2.load()

        assert store2._built
        assert len(store2.metadata) == 10
        assert store2.metadata[5]["command"] == "cmd5"
        assert store2.metadata[5]["value"] == 5

    def test_load_nonexistent_index(self, index_path):
        """Test loading non-existent index raises error."""
        store = VectorStore(index_path)

        with pytest.raises(FileNotFoundError):
            store.load()

    def test_load_preserves_search_capability(self, index_path):
        """Test that loaded index can search."""
        # Create and save
        store1 = VectorStore(index_path, dim=128)
        np.random.seed(42)
        vectors = [np.random.randn(128).astype(np.float32) for _ in range(50)]
        for i, vec in enumerate(vectors):
            store1.add(vec, f"cmd{i}")
        store1.build()
        store1.save()

        # Load and search
        store2 = VectorStore(index_path, dim=128)
        store2.load()

        query = np.random.randn(128).astype(np.float32)
        results = store2.search(query, top_k=5)

        assert len(results) == 5


class TestRebuild:
    """Test index rebuilding."""

    def test_rebuild_index(self, index_path):
        """Test rebuilding index with new data."""
        store = VectorStore(index_path, dim=128)

        # Initial build
        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        # Rebuild with new data
        new_vectors = [np.random.randn(128).astype(np.float32) for _ in range(20)]
        new_commands = [f"new_cmd{i}" for i in range(20)]

        store.rebuild(new_vectors, new_commands)

        assert len(store.metadata) == 20
        assert store._built
        assert store.metadata[0]["command"] == "new_cmd0"

    def test_rebuild_with_metadata(self, index_path):
        """Test rebuilding with metadata."""
        store = VectorStore(index_path, dim=128)

        vectors = [np.random.randn(128).astype(np.float32) for _ in range(10)]
        commands = [f"cmd{i}" for i in range(10)]
        metadata = [{"value": i * 2} for i in range(10)]

        store.rebuild(vectors, commands, metadata)

        assert store.metadata[5]["value"] == 10

    def test_rebuild_mismatched_lengths(self, index_path):
        """Test rebuild with mismatched lengths raises error."""
        store = VectorStore(index_path, dim=128)

        vectors = [np.random.randn(128).astype(np.float32) for _ in range(10)]
        commands = ["cmd1", "cmd2"]  # Too few

        with pytest.raises(ValueError, match="same length"):
            store.rebuild(vectors, commands)


class TestGetByIndex:
    """Test retrieving metadata by index."""

    def test_get_by_index(self, index_path):
        """Test getting metadata by index."""
        store = VectorStore(index_path, dim=128)

        for i in range(10):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}", {"value": i})

        meta = store.get_by_index(5)

        assert meta is not None
        assert meta["command"] == "cmd5"
        assert meta["value"] == 5

    def test_get_by_index_invalid(self, index_path):
        """Test getting invalid index returns None."""
        store = VectorStore(index_path, dim=128)

        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, "cmd")

        assert store.get_by_index(999) is None
        assert store.get_by_index(-1) is None

    def test_get_by_index_returns_copy(self, index_path):
        """Test that get_by_index returns a copy."""
        store = VectorStore(index_path, dim=128)
        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, "cmd", {"value": 10})

        meta1 = store.get_by_index(0)
        meta1["value"] = 999

        meta2 = store.get_by_index(0)

        # Original should be unchanged
        assert meta2["value"] == 10


class TestStatistics:
    """Test statistics retrieval."""

    def test_get_statistics(self, index_path):
        """Test getting index statistics."""
        store = VectorStore(index_path, dim=128, n_trees=15, metric="euclidean")

        for i in range(25):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        stats = store.get_statistics()

        assert stats["total_vectors"] == 25
        assert stats["dimension"] == 128
        assert stats["n_trees"] == 15
        assert stats["metric"] == "euclidean"
        assert stats["built"] is True
        assert "index_file" in stats
        assert "metadata_file" in stats

    def test_get_statistics_unbuilt(self, index_path):
        """Test statistics for unbuilt index."""
        store = VectorStore(index_path, dim=64)

        vec = np.random.randn(64).astype(np.float32)
        store.add(vec, "cmd")

        stats = store.get_statistics()

        assert stats["built"] is False


class TestLen:
    """Test __len__ method."""

    def test_len(self, index_path):
        """Test length of vector store."""
        store = VectorStore(index_path, dim=128)

        assert len(store) == 0

        for i in range(15):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")

        assert len(store) == 15


class TestRepr:
    """Test string representation."""

    def test_repr_unbuilt(self, index_path):
        """Test repr for unbuilt index."""
        store = VectorStore(index_path, dim=128)

        repr_str = repr(store)

        assert "VectorStore" in repr_str
        assert "dim=128" in repr_str
        assert "vectors=0" in repr_str
        assert "not built" in repr_str

    def test_repr_built(self, index_path):
        """Test repr for built index."""
        store = VectorStore(index_path, dim=64)

        for i in range(10):
            vec = np.random.randn(64).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        repr_str = repr(store)

        assert "VectorStore" in repr_str
        assert "dim=64" in repr_str
        assert "vectors=10" in repr_str
        assert "built" in repr_str


class TestDifferentMetrics:
    """Test using different distance metrics."""

    def test_angular_metric(self, index_path):
        """Test using angular distance."""
        store = VectorStore(index_path, dim=128, metric="angular")

        for i in range(20):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=5)

        assert len(results) == 5
        assert all(0 <= r["similarity"] <= 1 for r in results)

    def test_euclidean_metric(self, index_path):
        """Test using euclidean distance."""
        store = VectorStore(index_path, dim=128, metric="euclidean")

        for i in range(20):
            vec = np.random.randn(128).astype(np.float32)
            store.add(vec, f"cmd{i}")
        store.build()

        query = np.random.randn(128).astype(np.float32)
        results = store.search(query, top_k=5)

        assert len(results) == 5
        # Similarity should still be in reasonable range
        assert all(r["similarity"] >= 0 for r in results)
