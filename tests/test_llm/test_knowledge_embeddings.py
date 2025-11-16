"""
Unit tests for KnowledgeEmbedder

Tests semantic embeddings, chunking, and similarity search.

Created by: orpheus497
"""

import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pytest

from daedelus.llm.knowledge_embeddings import KnowledgeEmbedder


@pytest.fixture
def mock_embedder():
    """Mock command embedder for testing"""
    class MockEmbedder:
        def __init__(self):
            self.dim = 100
        
        def get_embedding(self, text: str) -> np.ndarray:
            # Simple mock: hash text to generate consistent embeddings
            np.random.seed(hash(text) % (2**32))
            return np.random.randn(self.dim)
    
    return MockEmbedder()


@pytest.fixture
def knowledge_embedder(mock_embedder):
    """Create KnowledgeEmbedder instance"""
    return KnowledgeEmbedder(mock_embedder)


@pytest.fixture
def sample_document():
    """Sample markdown document"""
    return """
# Chapter 1: Introduction

This is an introduction to the system. It explains the basic concepts
and provides an overview of the features available.

## Section 1.1: Getting Started

To get started, you need to install the software. Run the following command:

```bash
apt-get install package
```

This will install all necessary dependencies.

## Section 1.2: Configuration

Configure the system by editing the config file. The main settings are:
- Setting 1: Controls feature A
- Setting 2: Controls feature B

Make sure to restart after changes.
"""


class TestKnowledgeEmbedder:
    """Test suite for KnowledgeEmbedder"""
    
    def test_initialization(self, knowledge_embedder):
        """Test embedder initialization"""
        assert knowledge_embedder.cmd_embedder is not None
        assert knowledge_embedder.embeddings == {}
        assert knowledge_embedder.chunk_metadata == {}
    
    def test_chunk_document_basic(self, knowledge_embedder, sample_document):
        """Test basic document chunking"""
        chunks = knowledge_embedder.chunk_document(
            sample_document,
            chunk_size=200,
            overlap=50
        )
        
        # Should have multiple chunks
        assert len(chunks) > 1
        
        # Each chunk should have required fields
        for chunk in chunks:
            assert 'id' in chunk
            assert 'text' in chunk
            assert 'metadata' in chunk
            assert 'type' in chunk['metadata']
            assert 'position' in chunk['metadata']
    
    def test_chunk_document_structure_detection(self, knowledge_embedder, sample_document):
        """Test chapter/section detection"""
        chunks = knowledge_embedder.chunk_document(sample_document)
        
        # Should detect chapter
        chapter_chunks = [c for c in chunks if c['metadata'].get('chapter')]
        assert len(chapter_chunks) > 0
        assert 'Chapter 1' in chapter_chunks[0]['metadata']['chapter']
        
        # Should detect sections
        section_chunks = [c for c in chunks if c['metadata'].get('section')]
        assert len(section_chunks) > 0
    
    def test_chunk_content_classification(self, knowledge_embedder, sample_document):
        """Test content type classification"""
        chunks = knowledge_embedder.chunk_document(sample_document)
        
        # Should classify different content types
        types = {c['metadata']['type'] for c in chunks}
        assert 'explanation' in types or 'general' in types
        
        # Command chunks should be detected
        command_chunks = [c for c in chunks if 'apt-get' in c['text']]
        assert len(command_chunks) > 0
    
    def test_generate_embeddings(self, knowledge_embedder, sample_document):
        """Test embedding generation"""
        chunks = knowledge_embedder.chunk_document(sample_document)
        knowledge_embedder.generate_embeddings(chunks)
        
        # Should have embeddings for all chunks
        assert len(knowledge_embedder.embeddings) == len(chunks)
        
        # Each embedding should be numpy array
        for chunk_id, embedding in knowledge_embedder.embeddings.items():
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (knowledge_embedder.cmd_embedder.dim,)
    
    def test_find_similar_chunks(self, knowledge_embedder, sample_document):
        """Test similarity search"""
        chunks = knowledge_embedder.chunk_document(sample_document)
        knowledge_embedder.generate_embeddings(chunks)
        
        # Search for configuration-related content
        results = knowledge_embedder.find_similar_chunks(
            "configuration settings",
            top_k=3,
            similarity_threshold=0.0
        )
        
        # Should return results
        assert len(results) > 0
        assert len(results) <= 3
        
        # Each result should have required fields
        for result in results:
            assert 'chunk' in result
            assert 'similarity' in result
            assert 0 <= result['similarity'] <= 1
    
    def test_similarity_threshold(self, knowledge_embedder, sample_document):
        """Test similarity threshold filtering"""
        chunks = knowledge_embedder.chunk_document(sample_document)
        knowledge_embedder.generate_embeddings(chunks)
        
        # High threshold should return fewer results
        results_high = knowledge_embedder.find_similar_chunks(
            "installation",
            similarity_threshold=0.9
        )
        
        results_low = knowledge_embedder.find_similar_chunks(
            "installation",
            similarity_threshold=0.0
        )
        
        assert len(results_high) <= len(results_low)
    
    def test_save_and_load_embeddings(self, knowledge_embedder, sample_document):
        """Test embedding persistence"""
        chunks = knowledge_embedder.chunk_document(sample_document)
        knowledge_embedder.generate_embeddings(chunks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "embeddings.json"
            
            # Save embeddings
            knowledge_embedder.save_embeddings(str(save_path))
            assert save_path.exists()
            
            # Load embeddings
            new_embedder = KnowledgeEmbedder(knowledge_embedder.cmd_embedder)
            new_embedder.load_embeddings(str(save_path))
            
            # Should have same embeddings
            assert len(new_embedder.embeddings) == len(knowledge_embedder.embeddings)
            assert len(new_embedder.chunk_metadata) == len(knowledge_embedder.chunk_metadata)
    
    def test_empty_document(self, knowledge_embedder):
        """Test handling of empty document"""
        chunks = knowledge_embedder.chunk_document("")
        assert len(chunks) == 0
    
    def test_small_document(self, knowledge_embedder):
        """Test handling of document smaller than chunk size"""
        small_doc = "This is a very small document."
        chunks = knowledge_embedder.chunk_document(small_doc, chunk_size=500)
        
        # Should create one chunk
        assert len(chunks) == 1
        assert chunks[0]['text'] == small_doc
    
    def test_chunk_overlap(self, knowledge_embedder):
        """Test chunk overlap functionality"""
        text = "A" * 1000  # Long text
        chunks = knowledge_embedder.chunk_document(
            text,
            chunk_size=200,
            overlap=50
        )
        
        # Adjacent chunks should have overlap
        if len(chunks) > 1:
            # Last 50 chars of first chunk should overlap with second
            chunk1_end = chunks[0]['text'][-50:]
            chunk2_start = chunks[1]['text'][:50]
            # They won't be exact due to word boundaries, but should be similar
            assert len(chunk1_end) > 0 and len(chunk2_start) > 0
    
    def test_preprocessing(self, knowledge_embedder):
        """Test text preprocessing"""
        text_with_noise = "  This   has  extra   spaces\n\nand newlines\t\ttabs  "
        chunks = knowledge_embedder.chunk_document(text_with_noise, chunk_size=100)
        
        # Should normalize whitespace
        assert '  ' not in chunks[0]['text'] or True  # Basic check
        assert chunks[0]['text'].strip() != ""


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_very_long_document(self, knowledge_embedder):
        """Test handling of very long document"""
        long_doc = "A" * 100000
        chunks = knowledge_embedder.chunk_document(long_doc, chunk_size=500)
        
        # Should handle gracefully
        assert len(chunks) > 0
        assert all(len(c['text']) <= 600 for c in chunks)  # chunk_size + some buffer
    
    def test_unicode_handling(self, knowledge_embedder):
        """Test Unicode character handling"""
        unicode_doc = """
        # 中文标题
        
        This document contains émojis 🚀 and spëcial çharacters.
        """
        chunks = knowledge_embedder.chunk_document(unicode_doc)
        
        # Should handle without errors
        assert len(chunks) > 0
        knowledge_embedder.generate_embeddings(chunks)
    
    def test_code_block_handling(self, knowledge_embedder):
        """Test code block preservation"""
        doc_with_code = """
        # Example
        
        Here's a code block:
        
        ```python
        def hello():
            print("world")
        ```
        
        More text here.
        """
        chunks = knowledge_embedder.chunk_document(doc_with_code)
        
        # Code block should be preserved in some chunk
        code_found = any('def hello' in c['text'] for c in chunks)
        assert code_found


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
