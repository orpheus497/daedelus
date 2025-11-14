"""
Tests for vector store module.

Tests Annoy approximate nearest neighbor search.

Created by: orpheus497
"""


import numpy as np
import pytest

from daedelus.core.vector_store import VectorStore


def test_vector_store_initialization(temp_dir):
    """Test vector store creation."""
    index_path = temp_dir / "test.ann"
    store = VectorStore(dim=128, index_path=index_path)

    assert store.dim == 128
    assert store.index_path == index_path


def test_add_vector(temp_dir):
    """Test single vector insertion."""
    store = VectorStore(dim=128, index_path=temp_dir / "test.ann")

    vector = np.random.randn(128).astype(np.float32)
    idx = store.add(vector, metadata={"command": "git status"})

    assert idx == 0


def test_build_index(temp_dir):
    """Test index building."""
    store = VectorStore(dim=128, index_path=temp_dir / "test.ann")

    for i in range(100):
        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, metadata={"command": f"cmd_{i}"})

    store.build()

    assert store.is_built()


def test_query_similar(temp_dir):
    """Test k-NN search."""
    store = VectorStore(dim=128, index_path=temp_dir / "test.ann")

    # Add vectors
    query_vec = np.random.randn(128).astype(np.float32)
    store.add(query_vec, metadata={"command": "target"})

    for i in range(10):
        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, metadata={"command": f"other_{i}"})

    store.build()

    # Query
    results = store.query(query_vec, k=5)

    assert len(results) <= 5
    # First result should be the query vector itself
    assert results[0]["metadata"]["command"] == "target"


def test_save_load_index(temp_dir):
    """Test index persistence."""
    index_path = temp_dir / "test.ann"
    store = VectorStore(dim=128, index_path=index_path)

    # Add and build
    for i in range(10):
        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, metadata={"command": f"cmd_{i}"})

    store.build()
    store.save()

    # Load in new instance
    store2 = VectorStore(dim=128, index_path=index_path)
    store2.load()

    # Should be able to query
    query = np.random.randn(128).astype(np.float32)
    results = store2.query(query, k=3)

    assert len(results) > 0


@pytest.mark.performance
def test_search_performance(temp_dir):
    """Test query time (<10ms)."""
    import time

    store = VectorStore(dim=128, index_path=temp_dir / "test.ann", n_trees=10)

    # Add 1000 vectors
    for i in range(1000):
        vec = np.random.randn(128).astype(np.float32)
        store.add(vec, metadata={"command": f"cmd_{i}"})

    store.build()

    query = np.random.randn(128).astype(np.float32)

    start = time.time()
    results = store.query(query, k=10)
    elapsed = time.time() - start

    assert elapsed < 0.01  # <10ms
