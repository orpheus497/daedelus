"""
Annoy-based vector similarity search for Daedalus (Phase 1).

Provides fast approximate nearest neighbor search for command embeddings:
- Memory-mapped indexes for efficiency
- Fast queries (<10ms for 1M vectors)
- Persistent storage
- Incremental updates

Phase 2 will upgrade to sqlite-vss for better integration with the database.

Created by: orpheus497
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

try:
    from annoy import AnnoyIndex
except ImportError:
    AnnoyIndex = None  # type: ignore

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Fast vector similarity search using Annoy.

    Annoy (Approximate Nearest Neighbors Oh Yeah) provides:
    - Fast queries with low latency
    - Memory-mapped files (doesn't load entire index into RAM)
    - Good for read-heavy workloads
    - Simple to use

    Attributes:
        index_path: Path to Annoy index file
        dim: Dimensionality of vectors
        n_trees: Number of trees (more = better accuracy, slower build)
        index: Annoy index instance
        metadata: List of metadata dicts for each vector
    """

    def __init__(
        self,
        index_path: Path,
        dim: int = 128,
        n_trees: int = 10,
        metric: str = "angular",
    ) -> None:
        """
        Initialize vector store.

        Args:
            index_path: Path to save/load index files
            dim: Dimensionality of vectors (must match embeddings)
            n_trees: Number of trees to build (more = better quality)
            metric: Distance metric ('angular', 'euclidean', 'manhattan', 'hamming')
        """
        self.index_path = Path(index_path).expanduser()
        self.dim = dim
        self.n_trees = n_trees
        self.metric = metric

        # Create Annoy index
        if AnnoyIndex is None:
            raise ImportError("annoy is not installed. Install it with: pip install annoy==1.17.3")
        self.index = AnnoyIndex(self.dim, self.metric)

        # Metadata storage (parallel to index)
        self.metadata: list[dict[str, Any]] = []

        # Track if index is built
        self._built = False

        logger.info(f"VectorStore initialized (dim={dim}, metric={metric})")

    def add(
        self,
        embedding: npt.NDArray[np.float32],
        command: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Add a vector to the index.

        Args:
            embedding: Embedding vector
            command: Command string
            metadata: Additional metadata (timestamp, cwd, success_rate, etc.)

        Returns:
            Index of added vector

        Raises:
            ValueError: If vector dimension doesn't match
            RuntimeError: If index is already built
        """
        if self._built:
            raise RuntimeError("Cannot add to built index. Create new index or rebuild.")

        if len(embedding) != self.dim:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dim}, got {len(embedding)}"
            )

        # Get next index
        idx = len(self.metadata)

        # Add vector to Annoy index
        self.index.add_item(idx, embedding.tolist())

        # Store metadata
        meta = metadata or {}
        meta["command"] = command
        meta["index"] = idx
        self.metadata.append(meta)

        logger.debug(f"Added vector {idx}: {command[:30]}...")

        return idx

    def is_built(self) -> bool:
        """
        Check if the index has been built.

        Returns:
            True if index is built and ready for queries, False otherwise
        """
        return self._built

    def build(self) -> None:
        """
        Build the index.

        This must be called after adding all vectors and before searching.
        Building takes time but only needs to be done once.

        Raises:
            RuntimeError: If index is empty
        """
        if len(self.metadata) == 0:
            raise RuntimeError("Cannot build empty index")

        logger.info(f"Building index with {len(self.metadata)} vectors...")

        # Build Annoy index
        self.index.build(self.n_trees)
        self._built = True

        logger.info("Index built successfully")

    def search(
        self,
        query_embedding: npt.NDArray[np.float32],
        top_k: int = 10,
        include_distances: bool = True,
        search_k: int = -1,
    ) -> list[dict[str, Any]]:
        """
        Search for nearest neighbors.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            include_distances: Whether to include distances in results
            search_k: Search parameter (higher = more accurate, slower)
                     -1 means use n_trees * top_k

        Returns:
            List of result dictionaries with 'command', 'similarity', and metadata

        Raises:
            RuntimeError: If index hasn't been built
        """
        if not self._built:
            raise RuntimeError("Index not built. Call build() first.")

        # Get nearest neighbors
        if include_distances:
            indices, distances = self.index.get_nns_by_vector(
                query_embedding.tolist(),
                top_k,
                search_k=search_k,
                include_distances=True,
            )
        else:
            indices = self.index.get_nns_by_vector(
                query_embedding.tolist(),
                top_k,
                search_k=search_k,
                include_distances=False,
            )
            distances = [0.0] * len(indices)

        # Build result list
        results = []
        for idx, dist in zip(indices, distances, strict=False):
            if idx < len(self.metadata):
                result = self.metadata[idx].copy()

                # Convert distance to similarity
                # Angular distance is in [0, 2], convert to similarity in [0, 1]
                if self.metric == "angular":
                    similarity = 1.0 - (dist / 2.0)
                elif self.metric == "euclidean":
                    # Normalize euclidean distance to [0, 1] range (approximate)
                    similarity = 1.0 / (1.0 + dist)
                else:
                    similarity = 1.0 - dist  # Generic fallback

                result["similarity"] = float(similarity)
                result["distance"] = float(dist)

                results.append(result)

        return results

    def get_by_index(self, idx: int) -> dict[str, Any] | None:
        """
        Get metadata by index.

        Args:
            idx: Vector index

        Returns:
            Metadata dictionary or None if index invalid
        """
        if 0 <= idx < len(self.metadata):
            return self.metadata[idx].copy()
        return None

    def save(self) -> None:
        """
        Save index and metadata to disk.

        Raises:
            RuntimeError: If index hasn't been built
        """
        if not self._built:
            raise RuntimeError("Cannot save unbuilt index. Call build() first.")

        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Save Annoy index
        annoy_path = self.index_path.with_suffix(".ann")
        self.index.save(str(annoy_path))

        # Save metadata
        meta_path = self.index_path.with_suffix(".meta")
        with open(meta_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

        logger.info(f"Index saved to {self.index_path}")

    def load(self) -> None:
        """
        Load index and metadata from disk.

        Raises:
            FileNotFoundError: If index files don't exist
        """
        annoy_path = self.index_path.with_suffix(".ann")
        meta_path = self.index_path.with_suffix(".meta")

        if not annoy_path.exists():
            raise FileNotFoundError(f"Index not found: {annoy_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata not found: {meta_path}")

        # Load Annoy index
        self.index.load(str(annoy_path))
        self._built = True

        # Load metadata
        with open(meta_path) as f:
            self.metadata = json.load(f)

        logger.info(f"Index loaded from {self.index_path} " f"({len(self.metadata)} vectors)")

    def rebuild(
        self,
        embeddings: list[npt.NDArray[np.float32]],
        commands: list[str],
        metadata_list: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Rebuild index from scratch with new data.

        Useful for incremental updates or reindexing.

        Args:
            embeddings: List of embedding vectors
            commands: List of command strings
            metadata_list: Optional list of metadata dicts
        """
        if len(embeddings) != len(commands):
            raise ValueError("Embeddings and commands must have same length")

        # Create new index
        self.index = AnnoyIndex(self.dim, self.metric)
        self.metadata = []
        self._built = False

        # Add all vectors
        for i, (emb, cmd) in enumerate(zip(embeddings, commands, strict=False)):
            meta = metadata_list[i] if metadata_list else {}
            self.add(emb, cmd, meta)

        # Build index
        self.build()

        logger.info(f"Index rebuilt with {len(self.metadata)} vectors")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get index statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "total_vectors": len(self.metadata),
            "dimension": self.dim,
            "n_trees": self.n_trees,
            "metric": self.metric,
            "built": self._built,
            "index_file": str(self.index_path.with_suffix(".ann")),
            "metadata_file": str(self.index_path.with_suffix(".meta")),
        }

    def __len__(self) -> int:
        """Return number of vectors in index."""
        return len(self.metadata)

    def __repr__(self) -> str:
        """String representation."""
        status = "built" if self._built else "not built"
        return f"VectorStore(dim={self.dim}, vectors={len(self.metadata)}, " f"status={status})"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create test vectors
    dim = 128
    n_vectors = 1000

    # Initialize store
    store = VectorStore(
        index_path=Path("/tmp/daedelus_test_index"),
        dim=dim,
        n_trees=10,
    )

    # Add random vectors (in real use, these would be FastText embeddings)
    print(f"Adding {n_vectors} random vectors...")
    for i in range(n_vectors):
        vec = np.random.randn(dim).astype(np.float32)
        store.add(
            vec,
            f"command_{i}",
            {"timestamp": float(i), "success_rate": np.random.random()},
        )

    # Build index
    store.build()

    # Save to disk
    store.save()

    # Test search
    query_vec = np.random.randn(dim).astype(np.float32)
    results = store.search(query_vec, top_k=5)

    print("\nSearch results:")
    for r in results:
        print(f"  {r['similarity']:.3f} - {r['command']}")

    # Test load
    store2 = VectorStore(
        index_path=Path("/tmp/daedelus_test_index"),
        dim=dim,
    )
    store2.load()

    print(f"\nLoaded index: {len(store2)} vectors")
    print(f"Statistics: {store2.get_statistics()}")
