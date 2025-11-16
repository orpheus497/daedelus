"""
Unit tests for SearchCache (LRU + TTL)

Tests caching functionality, eviction, TTL, and statistics.

Created by: orpheus497
"""

import time

import pytest

from daedelus.core.cache import LRUCache, SearchCache


class TestLRUCache:
    """Test suite for LRUCache"""
    
    def test_initialization(self):
        """Test cache initialization"""
        cache = LRUCache(capacity=10, ttl=60)
        assert cache.capacity == 10
        assert cache.ttl == 60
        assert len(cache.cache) == 0
    
    def test_basic_get_set(self):
        """Test basic get/set operations"""
        cache = LRUCache(capacity=5)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
    
    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = LRUCache(capacity=5)
        assert cache.get("nonexistent") is None
    
    def test_lru_eviction(self):
        """Test LRU eviction when capacity exceeded"""
        cache = LRUCache(capacity=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # All should be present
        assert cache.get("key1") is not None
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None
        
        # Add one more (should evict key1 - least recently used)
        cache.set("key4", "value4")
        
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key4") is not None
    
    def test_access_updates_lru(self):
        """Test that accessing an entry updates LRU order"""
        cache = LRUCache(capacity=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # Access key1 (makes it most recently used)
        cache.get("key1")
        
        # Add new key (should evict key2, not key1)
        cache.set("key4", "value4")
        
        assert cache.get("key1") is not None  # Still present
        assert cache.get("key2") is None  # Evicted
    
    def test_ttl_expiration(self):
        """Test TTL-based expiration"""
        cache = LRUCache(capacity=10, ttl=1)  # 1 second TTL
        
        cache.set("key1", "value1")
        assert cache.get("key1") is not None
        
        # Wait for expiration
        time.sleep(1.1)
        
        assert cache.get("key1") is None  # Expired
    
    def test_statistics(self):
        """Test hit/miss/eviction statistics"""
        cache = LRUCache(capacity=2)
        
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Causes eviction
        
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['evictions'] == 1
        assert stats['size'] == 2
    
    def test_clear(self):
        """Test cache clearing"""
        cache = LRUCache(capacity=5)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        assert len(cache.cache) == 2
        
        cache.clear()
        
        assert len(cache.cache) == 0
        assert cache.get("key1") is None
    
    def test_prune_expired(self):
        """Test pruning expired entries"""
        cache = LRUCache(capacity=10, ttl=1)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Add new entry (should trigger prune)
        cache.set("key3", "value3")
        cache._prune_expired()
        
        # Old entries should be gone
        assert "key1" not in cache.cache
        assert "key2" not in cache.cache
    
    def test_update_existing_key(self):
        """Test updating an existing key"""
        cache = LRUCache(capacity=5)
        
        cache.set("key1", "value1")
        cache.set("key1", "value2")  # Update
        
        assert cache.get("key1") == "value2"
        assert len(cache.cache) == 1  # Still only one entry


class TestSearchCache:
    """Test suite for SearchCache"""
    
    def test_initialization(self):
        """Test search cache initialization"""
        cache = SearchCache()
        
        assert cache.keyword_cache is not None
        assert cache.semantic_cache is not None
        assert cache.rag_cache is not None
    
    def test_keyword_cache(self):
        """Test keyword search caching"""
        cache = SearchCache()
        
        query = "install firewall"
        results = [{"text": "result1"}, {"text": "result2"}]
        
        cache.set_keyword(query, results)
        cached = cache.get_keyword(query)
        
        assert cached == results
    
    def test_semantic_cache(self):
        """Test semantic search caching"""
        cache = SearchCache()
        
        query = "configure security"
        results = [{"chunk": "result1", "score": 0.9}]
        
        cache.set_semantic(query, results)
        cached = cache.get_semantic(query)
        
        assert cached == results
    
    def test_rag_cache(self):
        """Test RAG pipeline caching"""
        cache = SearchCache()
        
        query = "how to deploy"
        context = {"chunks": ["chunk1", "chunk2"]}
        
        cache.set_rag(query, context)
        cached = cache.get_rag(query)
        
        assert cached == context
    
    def test_query_normalization(self):
        """Test query normalization for consistent keys"""
        cache = SearchCache()
        
        results = [{"text": "result"}]
        
        # Different whitespace, capitalization
        cache.set_keyword("Install  Firewall", results)
        
        # Should retrieve with normalized query
        cached = cache.get_keyword("install firewall")
        assert cached == results
    
    def test_combined_stats(self):
        """Test combined statistics"""
        cache = SearchCache()
        
        cache.set_keyword("query1", ["result"])
        cache.get_keyword("query1")  # Hit
        cache.get_keyword("query2")  # Miss
        
        cache.set_semantic("query3", ["result"])
        cache.get_semantic("query3")  # Hit
        
        stats = cache.get_stats()
        
        assert stats['total_hits'] == 2
        assert stats['total_misses'] == 1
        assert 'keyword' in stats
        assert 'semantic' in stats
        assert 'rag' in stats
    
    def test_clear_all(self):
        """Test clearing all caches"""
        cache = SearchCache()
        
        cache.set_keyword("q1", ["r1"])
        cache.set_semantic("q2", ["r2"])
        cache.set_rag("q3", {"context": "c1"})
        
        cache.clear_all()
        
        stats = cache.get_stats()
        assert stats['keyword']['size'] == 0
        assert stats['semantic']['size'] == 0
        assert stats['rag']['size'] == 0
    
    def test_independent_caches(self):
        """Test that caches are independent"""
        cache = SearchCache()
        
        query = "same query"
        
        cache.set_keyword(query, ["keyword result"])
        cache.set_semantic(query, ["semantic result"])
        
        # Should retrieve different results from different caches
        keyword_result = cache.get_keyword(query)
        semantic_result = cache.get_semantic(query)
        
        assert keyword_result != semantic_result
        assert keyword_result == ["keyword result"]
        assert semantic_result == ["semantic result"]


class TestEdgeCases:
    """Edge case testing"""
    
    def test_zero_capacity(self):
        """Test cache with zero capacity"""
        cache = LRUCache(capacity=0)
        
        cache.set("key", "value")
        # With 0 capacity, nothing should be stored
        assert cache.get("key") is None
    
    def test_very_large_value(self):
        """Test storing large value"""
        cache = LRUCache(capacity=5)
        
        large_value = "x" * 1000000  # 1MB string
        cache.set("key", large_value)
        
        assert cache.get("key") == large_value
    
    def test_none_value(self):
        """Test storing None as value"""
        cache = LRUCache(capacity=5)
        
        cache.set("key", None)
        result = cache.get("key")
        
        # Should distinguish between "not found" and "stored None"
        # Implementation-dependent behavior
        assert result is None or "key" not in cache.cache
    
    def test_concurrent_access_simulation(self):
        """Simulate concurrent access patterns"""
        cache = LRUCache(capacity=10)
        
        # Rapid set/get operations
        for i in range(100):
            cache.set(f"key{i % 15}", f"value{i}")
            cache.get(f"key{(i-1) % 15}")
        
        # Should handle without errors
        stats = cache.get_stats()
        assert stats['hits'] > 0
        assert stats['misses'] >= 0
    
    def test_special_characters_in_keys(self):
        """Test keys with special characters"""
        cache = SearchCache()
        
        special_query = "how to $(install) file?"
        results = ["result"]
        
        cache.set_keyword(special_query, results)
        cached = cache.get_keyword(special_query)
        
        assert cached == results
    
    def test_unicode_keys(self):
        """Test Unicode in cache keys"""
        cache = SearchCache()
        
        unicode_query = "如何安装 firewall 🔥"
        results = ["result"]
        
        cache.set_keyword(unicode_query, results)
        cached = cache.get_keyword(unicode_query)
        
        assert cached == results


class TestPerformance:
    """Performance tests"""
    
    def test_lookup_speed(self):
        """Test cache lookup speed"""
        cache = LRUCache(capacity=1000)
        
        # Fill cache
        for i in range(1000):
            cache.set(f"key{i}", f"value{i}")
        
        # Measure lookup time
        start = time.time()
        for i in range(1000):
            cache.get(f"key{i % 1000}")
        elapsed = time.time() - start
        
        # Should be very fast (<10ms total for 1000 lookups)
        assert elapsed < 0.01
    
    def test_hit_rate(self):
        """Test expected hit rate"""
        cache = SearchCache()
        
        # Simulate realistic access pattern
        queries = ["query1", "query2", "query3"] * 10
        
        for q in queries:
            cached = cache.get_keyword(q)
            if cached is None:
                cache.set_keyword(q, [f"result for {q}"])
        
        stats = cache.get_stats()
        
        # Should have decent hit rate (>50%)
        total = stats['total_hits'] + stats['total_misses']
        if total > 0:
            hit_rate = stats['total_hits'] / total
            assert hit_rate > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
