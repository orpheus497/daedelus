"""
Integration tests for Phase 5 Intelligence System

Tests the complete workflow: semantic search, query expansion, 
caching, analytics, graph, and hybrid search.

Created by: orpheus497
"""

import tempfile
from pathlib import Path

import pytest

# Import Phase 5 components
from daedelus.core.analytics import SearchAnalytics
from daedelus.core.cache import SearchCache
from daedelus.llm.hybrid_search import HybridSearch
from daedelus.llm.knowledge_graph import KnowledgeGraph
from daedelus.llm.query_expansion import QueryExpander


class TestPhase5Integration:
    """Integration tests for Phase 5 components"""
    
    @pytest.fixture
    def temp_db(self):
        """Temporary database for analytics"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            return f.name
    
    @pytest.fixture
    def analytics(self, temp_db):
        """SearchAnalytics instance"""
        return SearchAnalytics(temp_db)
    
    @pytest.fixture
    def cache(self):
        """SearchCache instance"""
        return SearchCache()
    
    @pytest.fixture
    def query_expander(self):
        """QueryExpander with sample synonyms"""
        expander = QueryExpander()
        expander.synonyms = {
            'install': ['setup', 'add', 'deploy'],
            'firewall': ['iptables', 'ufw'],
            'configure': ['setup', 'config'],
        }
        expander._build_reverse_index()
        return expander
    
    @pytest.fixture
    def knowledge_graph(self):
        """KnowledgeGraph with sample data"""
        graph = KnowledgeGraph()
        
        # Add sample structure
        graph.add_chapter("ch1", "Chapter 1: Introduction", "Intro content")
        graph.add_chapter("ch2", "Chapter 2: Configuration", "Config content")
        
        graph.add_section("ch1", "sec1", "Getting Started", "GS content")
        graph.add_section("ch2", "sec2", "Firewall Setup", "FW content")
        
        graph.add_command("sec1", "install", "Install command", "apt-get install")
        graph.add_command("sec2", "iptables", "Firewall cmd", "iptables -A INPUT")
        
        return graph
    
    def test_query_expansion_workflow(self, query_expander):
        """Test query expansion workflow"""
        query = "install firewall"
        
        # Expand query
        expanded = query_expander.expand_query(query)
        
        # Should have original + synonyms
        assert 'install' in expanded
        assert 'firewall' in expanded
        assert 'setup' in expanded or 'iptables' in expanded
        
        # Original terms should have highest weight
        assert expanded['install'] == 2.0
        assert expanded['firewall'] == 2.0
    
    def test_caching_workflow(self, cache):
        """Test caching workflow"""
        query = "install firewall"
        results = [
            {"text": "result1", "score": 0.9},
            {"text": "result2", "score": 0.8}
        ]
        
        # First query - cache miss
        cached = cache.get_keyword(query)
        assert cached is None
        
        # Store results
        cache.set_keyword(query, results)
        
        # Second query - cache hit
        cached = cache.get_keyword(query)
        assert cached == results
        
        # Check stats
        stats = cache.get_stats()
        assert stats['keyword']['hits'] == 1
        assert stats['keyword']['misses'] == 1
    
    def test_analytics_workflow(self, analytics):
        """Test analytics tracking workflow"""
        query = "install firewall"
        results = [
            {"id": "r1", "text": "Result 1"},
            {"id": "r2", "text": "Result 2"}
        ]
        
        # Log search
        search_id = analytics.log_search(
            query=query,
            search_type="keyword",
            result_count=len(results),
            results=results
        )
        
        assert search_id is not None
        
        # Track interaction
        analytics.track_result_click(search_id, "r1", position=0)
        
        # Get stats
        stats = analytics.get_summary_stats(days=7)
        
        assert stats['total_searches'] == 1
        assert stats['total_results'] > 0
    
    def test_knowledge_graph_workflow(self, knowledge_graph):
        """Test knowledge graph workflow"""
        # Find related content
        related = knowledge_graph.find_related_content(
            "sec1",
            max_depth=2,
            max_results=5
        )
        
        # Should find related nodes
        assert len(related) > 0
        
        # Get node context
        context = knowledge_graph.get_node_context("sec1")
        
        assert 'node' in context
        assert 'ancestors' in context
        assert 'siblings' in context
        assert 'children' in context
    
    def test_hybrid_search_workflow(self, query_expander, knowledge_graph, cache):
        """Test hybrid search workflow"""
        # Mock search methods
        def mock_keyword_search(query):
            return [
                {"id": "k1", "text": "Keyword result 1", "score": 0.9},
                {"id": "k2", "text": "Keyword result 2", "score": 0.8}
            ]
        
        def mock_semantic_search(query):
            return [
                {"id": "s1", "text": "Semantic result 1", "score": 0.85},
                {"id": "k1", "text": "Keyword result 1", "score": 0.80}
            ]
        
        # Create hybrid search
        hybrid = HybridSearch(
            query_expander=query_expander,
            knowledge_graph=knowledge_graph,
            cache=cache
        )
        
        # Detect query type
        query_type = hybrid.detect_query_type("how to install firewall")
        assert query_type in ['factual', 'procedural', 'conceptual', 'command']
        
        # Get adaptive weights
        weights = hybrid.get_adaptive_weights(query_type)
        assert 'keyword' in weights
        assert 'semantic' in weights
        assert 'graph' in weights
        assert abs(sum(weights.values()) - 1.0) < 0.01  # Should sum to 1.0
    
    def test_end_to_end_search_workflow(self, analytics, cache, query_expander):
        """Test complete search workflow"""
        query = "install firewall configuration"
        
        # Step 1: Check cache
        cached = cache.get_keyword(query)
        
        if cached is None:
            # Step 2: Expand query
            expanded = query_expander.expand_query(query)
            assert len(expanded) > 2
            
            # Step 3: Perform search (mocked)
            results = [
                {"id": "r1", "text": "Firewall installation guide", "score": 0.9},
                {"id": "r2", "text": "Configure iptables", "score": 0.8}
            ]
            
            # Step 4: Store in cache
            cache.set_keyword(query, results)
            
            # Step 5: Log in analytics
            search_id = analytics.log_search(
                query=query,
                search_type="keyword",
                result_count=len(results),
                results=results,
                latency_ms=50
            )
            
            # Step 6: Track user interaction
            analytics.track_result_click(search_id, "r1", position=0)
            analytics.track_result_execution(search_id, "r1", success=True)
        else:
            results = cached
        
        # Verify results
        assert len(results) > 0
        
        # Verify cache worked
        cached2 = cache.get_keyword(query)
        assert cached2 == results
        
        # Verify analytics
        stats = analytics.get_summary_stats(days=7)
        assert stats['total_searches'] >= 1
    
    def test_rrf_fusion(self):
        """Test Reciprocal Rank Fusion"""
        from daedelus.llm.hybrid_search import HybridSearch
        
        # Sample ranked lists
        keyword_results = [
            {"id": "r1", "score": 0.9},
            {"id": "r2", "score": 0.8},
            {"id": "r3", "score": 0.7}
        ]
        
        semantic_results = [
            {"id": "r2", "score": 0.85},
            {"id": "r1", "score": 0.82},
            {"id": "r4", "score": 0.78}
        ]
        
        graph_results = [
            {"id": "r3", "score": 0.88},
            {"id": "r4", "score": 0.80}
        ]
        
        # Mock HybridSearch
        hybrid = HybridSearch(
            query_expander=QueryExpander(),
            knowledge_graph=KnowledgeGraph(),
            cache=SearchCache()
        )
        
        # Perform fusion
        fused = hybrid.reciprocal_rank_fusion(
            [keyword_results, semantic_results, graph_results],
            weights=[0.5, 0.3, 0.2]
        )
        
        # Should have unique results
        assert len(fused) <= 4  # r1, r2, r3, r4
        
        # Results should be scored
        for result in fused:
            assert 'rrf_score' in result
            assert result['rrf_score'] > 0


class TestPerformance:
    """Performance tests for Phase 5"""
    
    def test_cache_performance(self):
        """Test cache improves performance"""
        import time
        
        cache = SearchCache()
        query = "test query"
        results = [{"text": f"result{i}"} for i in range(100)]
        
        # First query (miss)
        start = time.time()
        cache.get_keyword(query)
        cache.set_keyword(query, results)
        miss_time = time.time() - start
        
        # Second query (hit)
        start = time.time()
        cached = cache.get_keyword(query)
        hit_time = time.time() - start
        
        # Cache hit should be much faster
        assert hit_time < miss_time
        assert hit_time < 0.001  # <1ms
    
    def test_query_expansion_performance(self):
        """Test query expansion is fast"""
        import time
        
        expander = QueryExpander()
        expander.synonyms = {f'term{i}': [f'syn{i}_{j}' for j in range(5)] 
                            for i in range(100)}
        expander._build_reverse_index()
        
        # Measure expansion time
        start = time.time()
        for _ in range(100):
            expander.expand_query("term50 term60 term70")
        elapsed = time.time() - start
        
        # Should be fast (<50ms per query)
        avg_time = elapsed / 100
        assert avg_time < 0.05
    
    def test_graph_traversal_performance(self):
        """Test graph traversal is fast"""
        import time
        
        graph = KnowledgeGraph()
        
        # Build large graph
        for i in range(50):
            graph.add_chapter(f"ch{i}", f"Chapter {i}", f"Content {i}")
            for j in range(5):
                graph.add_section(f"ch{i}", f"sec{i}_{j}", f"Section {j}", f"Content")
        
        # Measure traversal time
        start = time.time()
        related = graph.find_related_content("sec0_0", max_depth=2)
        elapsed = time.time() - start
        
        # Should be fast (<100ms)
        assert elapsed < 0.1


class TestEdgeCases:
    """Edge case testing"""
    
    def test_empty_query(self, query_expander):
        """Test empty query handling"""
        expanded = query_expander.expand_query("")
        assert len(expanded) == 0
    
    def test_no_results(self, analytics):
        """Test handling of searches with no results"""
        search_id = analytics.log_search(
            query="nonexistent query",
            search_type="keyword",
            result_count=0,
            results=[]
        )
        
        assert search_id is not None
        
        stats = analytics.get_summary_stats(days=7)
        assert stats['total_searches'] == 1
    
    def test_cache_with_ttl_expiration(self):
        """Test cache TTL expiration"""
        import time
        
        cache = SearchCache(ttl=1)  # 1 second TTL
        query = "test"
        results = ["result"]
        
        cache.set_keyword(query, results)
        assert cache.get_keyword(query) is not None
        
        # Wait for expiration
        time.sleep(1.1)
        
        assert cache.get_keyword(query) is None
    
    def test_graph_with_no_connections(self):
        """Test graph with isolated nodes"""
        graph = KnowledgeGraph()
        graph.add_chapter("ch1", "Isolated", "Content")
        
        related = graph.find_related_content("ch1", max_depth=3)
        
        # Should handle gracefully
        assert isinstance(related, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
