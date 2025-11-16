"""
LRU Cache for Search Results in Daedelus.

Provides caching for search results and embeddings to improve performance
and reduce redundant computations.

Phase 5 - Intelligence System Enhancement
Created by: orpheus497
"""

import hashlib
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class LRUCache:
    """
    Least Recently Used (LRU) cache with TTL support.
    
    Features:
    - LRU eviction when capacity is reached
    - Time-to-live (TTL) for automatic expiration
    - Hit/miss statistics tracking
    - Optional disk persistence
    
    Attributes:
        capacity: Maximum number of entries
        ttl: Time-to-live in seconds (None = no expiration)
        cache: OrderedDict storing (value, timestamp) tuples
        stats: Hit/miss statistics
    """
    
    def __init__(
        self,
        capacity: int = 1000,
        ttl: Optional[int] = 3600,  # 1 hour default
        name: str = "cache"
    ):
        """
        Initialize LRU cache.
        
        Args:
            capacity: Maximum number of cache entries
            ttl: Time-to-live in seconds (None = no expiration)
            name: Cache identifier for logging
        """
        self.capacity = capacity
        self.ttl = ttl
        self.name = name
        
        # OrderedDict maintains insertion order
        # Entries: key -> (value, timestamp)
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'sets': 0,
            'deletes': 0
        }
        
        logger.info(f"LRUCache '{name}' initialized (capacity={capacity}, ttl={ttl}s)")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            self.stats['misses'] += 1
            return None
        
        value, timestamp = self.cache[key]
        
        # Check TTL expiration
        if self.ttl is not None:
            age = time.time() - timestamp
            if age > self.ttl:
                # Expired
                del self.cache[key]
                self.stats['expirations'] += 1
                self.stats['misses'] += 1
                return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.stats['hits'] += 1
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Check if already exists
        if key in self.cache:
            # Update and move to end
            self.cache[key] = (value, time.time())
            self.cache.move_to_end(key)
        else:
            # Check capacity
            if len(self.cache) >= self.capacity:
                # Evict least recently used (first item)
                evicted_key, _ = self.cache.popitem(last=False)
                self.stats['evictions'] += 1
                logger.debug(f"Cache '{self.name}' evicted key: {evicted_key}")
            
            # Add new entry
            self.cache[key] = (value, time.time())
        
        self.stats['sets'] += 1
    
    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if not found
        """
        if key in self.cache:
            del self.cache[key]
            self.stats['deletes'] += 1
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cache '{self.name}' cleared ({count} entries)")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            'name': self.name,
            'size': len(self.cache),
            'capacity': self.capacity,
            'usage_pct': (len(self.cache) / self.capacity * 100) if self.capacity > 0 else 0.0,
            'ttl': self.ttl,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate_pct': round(hit_rate, 2),
            'evictions': self.stats['evictions'],
            'expirations': self.stats['expirations'],
            'sets': self.stats['sets'],
            'deletes': self.stats['deletes']
        }
    
    def contains(self, key: str) -> bool:
        """
        Check if key exists in cache (without accessing it).
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and not expired
        """
        if key not in self.cache:
            return False
        
        # Check TTL
        if self.ttl is not None:
            _, timestamp = self.cache[key]
            age = time.time() - timestamp
            if age > self.ttl:
                return False
        
        return True
    
    def prune_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        if self.ttl is None:
            return 0
        
        current_time = time.time()
        expired_keys = []
        
        for key, (value, timestamp) in self.cache.items():
            age = current_time - timestamp
            if age > self.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
            self.stats['expirations'] += 1
        
        if expired_keys:
            logger.debug(f"Cache '{self.name}' pruned {len(expired_keys)} expired entries")
        
        return len(expired_keys)
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'sets': 0,
            'deletes': 0
        }
        logger.info(f"Cache '{self.name}' statistics reset")


class SearchCache:
    """
    Specialized cache for search results with query normalization.
    
    Features:
    - Query normalization (lowercase, whitespace, etc.)
    - Separate caches for different search types
    - Automatic cache key generation from queries
    
    Attributes:
        keyword_cache: Cache for keyword search results
        semantic_cache: Cache for semantic search results
        rag_cache: Cache for RAG pipeline results
    """
    
    def __init__(
        self,
        capacity: int = 1000,
        ttl: int = 3600
    ):
        """
        Initialize search cache.
        
        Args:
            capacity: Maximum entries per cache
            ttl: Time-to-live in seconds
        """
        self.keyword_cache = LRUCache(capacity, ttl, "keyword_search")
        self.semantic_cache = LRUCache(capacity, ttl, "semantic_search")
        self.rag_cache = LRUCache(capacity, ttl, "rag_pipeline")
        
        logger.info("SearchCache initialized with 3 specialized caches")
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize query for consistent cache keys.
        
        Args:
            query: Raw query string
            
        Returns:
            Normalized query
        """
        # Lowercase
        normalized = query.lower()
        
        # Normalize whitespace
        normalized = ' '.join(normalized.split())
        
        # Trim
        normalized = normalized.strip()
        
        return normalized
    
    def _generate_key(
        self,
        query: str,
        **kwargs: Any
    ) -> str:
        """
        Generate cache key from query and parameters.
        
        Args:
            query: Search query
            **kwargs: Additional parameters (e.g., max_results, threshold)
            
        Returns:
            Cache key (hash)
        """
        # Normalize query
        norm_query = self._normalize_query(query)
        
        # Include kwargs in key
        key_parts = [norm_query]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        key_string = '|'.join(key_parts)
        
        # Generate hash
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return key_hash
    
    def get_keyword(
        self,
        query: str,
        **kwargs: Any
    ) -> Optional[Any]:
        """Get keyword search results from cache."""
        key = self._generate_key(query, **kwargs)
        return self.keyword_cache.get(key)
    
    def set_keyword(
        self,
        query: str,
        results: Any,
        **kwargs: Any
    ) -> None:
        """Set keyword search results in cache."""
        key = self._generate_key(query, **kwargs)
        self.keyword_cache.set(key, results)
    
    def get_semantic(
        self,
        query: str,
        **kwargs: Any
    ) -> Optional[Any]:
        """Get semantic search results from cache."""
        key = self._generate_key(query, **kwargs)
        return self.semantic_cache.get(key)
    
    def set_semantic(
        self,
        query: str,
        results: Any,
        **kwargs: Any
    ) -> None:
        """Set semantic search results in cache."""
        key = self._generate_key(query, **kwargs)
        self.semantic_cache.set(key, results)
    
    def get_rag(
        self,
        query: str,
        **kwargs: Any
    ) -> Optional[Any]:
        """Get RAG pipeline results from cache."""
        key = self._generate_key(query, **kwargs)
        return self.rag_cache.get(key)
    
    def set_rag(
        self,
        query: str,
        results: Any,
        **kwargs: Any
    ) -> None:
        """Set RAG pipeline results in cache."""
        key = self._generate_key(query, **kwargs)
        self.rag_cache.set(key, results)
    
    def clear_all(self) -> None:
        """Clear all caches."""
        self.keyword_cache.clear()
        self.semantic_cache.clear()
        self.rag_cache.clear()
    
    def get_combined_stats(self) -> Dict[str, Any]:
        """
        Get combined statistics from all caches.
        
        Returns:
            Dictionary with aggregated stats
        """
        keyword_stats = self.keyword_cache.get_stats()
        semantic_stats = self.semantic_cache.get_stats()
        rag_stats = self.rag_cache.get_stats()
        
        total_hits = keyword_stats['hits'] + semantic_stats['hits'] + rag_stats['hits']
        total_misses = keyword_stats['misses'] + semantic_stats['misses'] + rag_stats['misses']
        total_requests = total_hits + total_misses
        
        return {
            'total_hits': total_hits,
            'total_misses': total_misses,
            'total_requests': total_requests,
            'hit_rate_pct': round((total_hits / total_requests * 100) if total_requests > 0 else 0.0, 2),
            'total_size': keyword_stats['size'] + semantic_stats['size'] + rag_stats['size'],
            'keyword': keyword_stats,
            'semantic': semantic_stats,
            'rag': rag_stats
        }
    
    def prune_all_expired(self) -> int:
        """
        Prune expired entries from all caches.
        
        Returns:
            Total number of entries removed
        """
        total = 0
        total += self.keyword_cache.prune_expired()
        total += self.semantic_cache.prune_expired()
        total += self.rag_cache.prune_expired()
        return total
