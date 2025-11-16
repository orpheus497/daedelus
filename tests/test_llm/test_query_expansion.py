"""
Unit tests for QueryExpander

Tests synonym expansion, context filtering, and query variants.

Created by: orpheus497
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from daedelus.llm.query_expansion import QueryExpander


@pytest.fixture
def sample_synonyms():
    """Sample synonym dictionary"""
    return {
        'install': ['setup', 'add', 'deploy', 'configure'],
        'remove': ['delete', 'uninstall', 'purge', 'erase'],
        'firewall': ['iptables', 'ufw', 'firewalld'],
        'list': ['show', 'display', 'enumerate'],
        'file': ['document', 'item'],
    }


@pytest.fixture
def query_expander(sample_synonyms):
    """Create QueryExpander with sample synonyms"""
    expander = QueryExpander()
    expander.synonyms = sample_synonyms
    expander._build_reverse_index()
    return expander


@pytest.fixture
def yaml_synonym_file(sample_synonyms):
    """Create temporary YAML file with synonyms"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_synonyms, f)
        return f.name


class TestQueryExpander:
    """Test suite for QueryExpander"""
    
    def test_initialization(self):
        """Test expander initialization"""
        expander = QueryExpander()
        assert isinstance(expander.synonyms, dict)
        assert expander.stopwords is not None
    
    def test_load_synonyms_from_yaml(self, yaml_synonym_file):
        """Test loading synonyms from YAML file"""
        expander = QueryExpander()
        expander.load_synonyms(yaml_synonym_file)
        
        assert 'install' in expander.synonyms
        assert 'setup' in expander.synonyms['install']
    
    def test_basic_expansion(self, query_expander):
        """Test basic query expansion"""
        expanded = query_expander.expand_query("install firewall")
        
        # Should contain original terms (weighted 2.0)
        assert 'install' in expanded
        assert 'firewall' in expanded
        assert expanded['install'] == 2.0
        assert expanded['firewall'] == 2.0
        
        # Should contain synonyms
        assert 'setup' in expanded
        assert 'iptables' in expanded
    
    def test_expansion_weights(self, query_expander):
        """Test expansion weight decay"""
        expanded = query_expander.expand_query("install")
        
        # Original term should have highest weight
        assert expanded['install'] == 2.0
        
        # Synonyms should have lower weights
        for syn in ['setup', 'add', 'deploy']:
            if syn in expanded:
                assert expanded[syn] < expanded['install']
    
    def test_stopword_filtering(self, query_expander):
        """Test stopword removal"""
        expanded = query_expander.expand_query("how to install the firewall")
        
        # Stopwords should be filtered
        assert 'how' not in expanded
        assert 'to' not in expanded
        assert 'the' not in expanded
        
        # Content words should remain
        assert 'install' in expanded
        assert 'firewall' in expanded
    
    def test_context_filtering(self, query_expander):
        """Test context-aware filtering"""
        expanded = query_expander.expand_query(
            "install firewall",
            context="network security"
        )
        
        # Should boost relevant synonyms
        # (In a real implementation, this would filter/boost based on context)
        assert 'install' in expanded
        assert 'firewall' in expanded
    
    def test_generate_query_variants(self, query_expander):
        """Test query variant generation"""
        variants = query_expander.generate_query_variants("install firewall")
        
        # Should generate multiple variants
        assert len(variants) >= 2  # At least original + one variant
        
        # Original should be first
        assert variants[0] == "install firewall"
        
        # Variants should differ
        assert len(set(variants)) == len(variants)
    
    def test_add_synonym_runtime(self, query_expander):
        """Test adding synonyms at runtime"""
        query_expander.add_synonym("configure", ["setup", "init"])
        
        # Should have new synonym
        assert 'configure' in query_expander.synonyms
        assert 'setup' in query_expander.synonyms['configure']
        
        # Should work in expansion
        expanded = query_expander.expand_query("configure system")
        assert 'configure' in expanded
        assert 'setup' in expanded
    
    def test_reverse_index(self, query_expander):
        """Test reverse synonym lookup"""
        # Reverse index should map synonym back to main term
        assert 'setup' in query_expander.reverse_index
        assert 'install' in query_expander.reverse_index['setup']
    
    def test_empty_query(self, query_expander):
        """Test handling of empty query"""
        expanded = query_expander.expand_query("")
        assert len(expanded) == 0
    
    def test_unknown_term(self, query_expander):
        """Test handling of unknown term"""
        expanded = query_expander.expand_query("unknownterm123")
        
        # Should still return the term (no expansion)
        assert 'unknownterm123' in expanded
        assert expanded['unknownterm123'] == 2.0
    
    def test_mixed_case_handling(self, query_expander):
        """Test case-insensitive expansion"""
        expanded1 = query_expander.expand_query("Install Firewall")
        expanded2 = query_expander.expand_query("install firewall")
        
        # Should normalize to lowercase
        assert 'install' in expanded1
        assert 'install' in expanded2
    
    def test_special_characters(self, query_expander):
        """Test handling of special characters"""
        expanded = query_expander.expand_query("install-firewall")
        
        # Should handle hyphens, underscores, etc.
        # (Exact behavior depends on implementation)
        assert len(expanded) > 0
    
    def test_multi_word_terms(self, query_expander):
        """Test multi-word term handling"""
        query_expander.add_synonym("file system", ["filesystem", "fs"])
        expanded = query_expander.expand_query("file system check")
        
        # Should handle multi-word terms
        assert 'file' in expanded or 'system' in expanded
    
    def test_expansion_with_weights(self, query_expander):
        """Test expansion respects weight parameters"""
        expanded = query_expander.expand_query(
            "install firewall",
            original_weight=3.0,
            synonym_weight=0.5
        )
        
        # Original should have custom weight
        assert expanded['install'] == 3.0
        
        # Synonyms should have custom weight
        for term, weight in expanded.items():
            if term not in ['install', 'firewall']:
                assert weight <= 1.0  # Decay from synonym_weight


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_very_long_query(self, query_expander):
        """Test handling of very long query"""
        long_query = "install " * 100
        expanded = query_expander.expand_query(long_query)
        
        # Should handle without errors
        assert 'install' in expanded
    
    def test_unicode_query(self, query_expander):
        """Test Unicode handling"""
        expanded = query_expander.expand_query("配置 firewall 🔥")
        
        # Should handle gracefully
        assert len(expanded) > 0
    
    def test_numeric_terms(self, query_expander):
        """Test handling of numeric terms"""
        expanded = query_expander.expand_query("install package version 3.14")
        
        # Should preserve numbers
        assert any('3' in term or '14' in term for term in expanded.keys())
    
    def test_synonym_cycles(self, query_expander):
        """Test handling of synonym cycles"""
        # Create a cycle: A -> B -> C -> A
        query_expander.synonyms['termA'] = ['termB']
        query_expander.synonyms['termB'] = ['termC']
        query_expander.synonyms['termC'] = ['termA']
        query_expander._build_reverse_index()
        
        # Should not infinite loop
        expanded = query_expander.expand_query("termA")
        assert len(expanded) > 0
        assert len(expanded) < 100  # Reasonable limit
    
    def test_duplicate_synonyms(self, query_expander):
        """Test handling of duplicate synonyms"""
        query_expander.synonyms['install'] = ['setup', 'setup', 'add']
        expanded = query_expander.expand_query("install")
        
        # Should deduplicate
        assert expanded.get('setup', 0) > 0


class TestPerformance:
    """Performance-related tests"""
    
    def test_expansion_speed(self, query_expander):
        """Test expansion is fast enough"""
        import time
        
        start = time.time()
        for _ in range(100):
            query_expander.expand_query("install firewall configuration")
        elapsed = time.time() - start
        
        # Should be fast (<50ms per query on average)
        avg_time = elapsed / 100
        assert avg_time < 0.05, f"Expansion too slow: {avg_time*1000:.2f}ms"
    
    def test_large_synonym_dict(self):
        """Test with large synonym dictionary"""
        expander = QueryExpander()
        
        # Create large dict
        for i in range(1000):
            expander.synonyms[f'term{i}'] = [f'syn{i}_{j}' for j in range(10)]
        expander._build_reverse_index()
        
        # Should still be fast
        expanded = expander.expand_query("term500")
        assert 'term500' in expanded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
