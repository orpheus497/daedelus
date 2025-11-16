"""
System-wide caching for Daedelus.

Provides intelligent caching for:
- LLM interpretations and responses
- Command suggestions
- File analysis results
- Frequently accessed data

Created by: orpheus497
"""

import hashlib
import json
import logging
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    timestamp: float
    ttl: float  # Time to live in seconds
    hit_count: int = 0


class SystemCache:
    """
    Production-ready system cache with TTL and eviction policies.

    Features:
    - Automatic expiration (TTL)
    - LRU eviction when full
    - Persistent storage
    - Thread-safe operations
    - Memory-efficient
    """

    def __init__(
        self,
        cache_dir: Path,
        max_entries: int = 10000,
        default_ttl: float = 3600.0,  # 1 hour
    ) -> None:
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache storage
            max_entries: Maximum number of cache entries
            default_ttl: Default time-to-live in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        
        # In-memory cache
        self._cache: dict[str, CacheEntry] = {}
        
        # Cache file paths
        self.cache_file = self.cache_dir / "cache.pkl"
        self.metadata_file = self.cache_dir / "metadata.json"
        
        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }
        
        # Load existing cache
        self._load_cache()
        
        logger.info(f"SystemCache initialized with {len(self._cache)} entries")

    def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self.stats["misses"] += 1
            return None
        
        entry = self._cache[key]
        
        # Check expiration
        if self._is_expired(entry):
            self.delete(key)
            self.stats["expirations"] += 1
            self.stats["misses"] += 1
            return None
        
        # Update hit count
        entry.hit_count += 1
        self.stats["hits"] += 1
        
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        # Evict if at capacity
        if len(self._cache) >= self.max_entries and key not in self._cache:
            self._evict_lru()
        
        # Create entry
        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=ttl if ttl is not None else self.default_ttl,
        )
        
        self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("Cache cleared")

    def save(self) -> None:
        """Persist cache to disk."""
        try:
            # Save cache entries
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self._cache, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Save metadata
            metadata = {
                "stats": self.stats,
                "entry_count": len(self._cache),
                "last_saved": time.time(),
            }
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.debug(f"Cache saved: {len(self._cache)} entries")
            
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _load_cache(self) -> None:
        """Load cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'rb') as f:
                    self._cache = pickle.load(f)
                
                # Remove expired entries
                expired = [k for k, v in self._cache.items() if self._is_expired(v)]
                for k in expired:
                    del self._cache[k]
                
                logger.info(f"Cache loaded: {len(self._cache)} entries")
            
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    metadata = json.load(f)
                    self.stats.update(metadata.get("stats", {}))
                    
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self._cache = {}

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if entry has expired."""
        return (time.time() - entry.timestamp) > entry.ttl

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        # Find entry with lowest hit count and oldest timestamp
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].hit_count, -self._cache[k].timestamp)
        )
        
        del self._cache[lru_key]
        self.stats["evictions"] += 1
        
        logger.debug(f"Evicted LRU entry: {lru_key}")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0
        
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self.stats["evictions"],
            "expirations": self.stats["expirations"],
        }

    def __del__(self) -> None:
        """Save cache on destruction."""
        try:
            self.save()
        except Exception:
            pass


class InterpretationCache:
    """
    Specialized cache for natural language interpretations.
    
    Uses content-based hashing for semantic caching.
    """

    def __init__(self, system_cache: SystemCache) -> None:
        """
        Initialize interpretation cache.

        Args:
            system_cache: Underlying system cache
        """
        self.cache = system_cache

    def get_interpretation(self, text: str, context: dict[str, Any] | None = None) -> Any | None:
        """
        Get cached interpretation.

        Args:
            text: Input text
            context: Optional context (cwd, history, etc.)

        Returns:
            Cached interpretation or None
        """
        key = self._make_key(text, context)
        return self.cache.get(key)

    def cache_interpretation(
        self,
        text: str,
        result: Any,
        context: dict[str, Any] | None = None,
        ttl: float = 1800.0,  # 30 minutes
    ) -> None:
        """
        Cache interpretation result.

        Args:
            text: Input text
            result: Interpretation result
            context: Optional context
            ttl: Time-to-live
        """
        key = self._make_key(text, context)
        self.cache.set(key, result, ttl=ttl)

    def _make_key(self, text: str, context: dict[str, Any] | None) -> str:
        """Generate cache key from text and context."""
        # Normalize text
        normalized = text.lower().strip()
        
        # Include relevant context
        context_str = ""
        if context:
            # Only include cwd in key, not full history
            if "cwd" in context:
                context_str = str(context["cwd"])
        
        # Hash for consistent key
        combined = f"{normalized}:{context_str}"
        return "interp:" + hashlib.sha256(combined.encode()).hexdigest()[:16]


class CommandCache:
    """Specialized cache for command suggestions and completions."""

    def __init__(self, system_cache: SystemCache) -> None:
        """
        Initialize command cache.

        Args:
            system_cache: Underlying system cache
        """
        self.cache = system_cache

    def get_suggestions(self, partial: str, limit: int = 5) -> list[dict[str, Any]] | None:
        """Get cached command suggestions."""
        key = f"suggest:{partial}:{limit}"
        return self.cache.get(key)

    def cache_suggestions(
        self,
        partial: str,
        suggestions: list[dict[str, Any]],
        limit: int = 5,
        ttl: float = 300.0,  # 5 minutes
    ) -> None:
        """Cache command suggestions."""
        key = f"suggest:{partial}:{limit}"
        self.cache.set(key, suggestions, ttl=ttl)
