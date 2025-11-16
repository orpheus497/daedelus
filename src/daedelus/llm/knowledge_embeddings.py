"""
Knowledge Base Semantic Embeddings for Daedelus.

Generates and manages vector embeddings for knowledge base content,
enabling semantic search capabilities for improved context retrieval.

Phase 5 - Intelligence System Enhancement
Created by: orpheus497
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from daedelus.core.embeddings import CommandEmbedder

logger = logging.getLogger(__name__)


class KnowledgeEmbedder:
    """
    Generates and manages semantic embeddings for knowledge base chunks.
    
    Uses FastText embeddings to create vector representations of knowledge
    base content (chapters, sections, paragraphs) for semantic similarity search.
    
    Attributes:
        embedder: CommandEmbedder instance for generating embeddings
        chunk_size: Target size for content chunks (characters)
        overlap: Overlap between chunks (characters)
        chunks: List of chunked content with metadata
        embeddings_cache: Cache of chunk_id -> embedding mapping
    """
    
    def __init__(
        self,
        embedder: CommandEmbedder,
        chunk_size: int = 500,
        overlap: int = 100,
    ):
        """
        Initialize knowledge embedder.
        
        Args:
            embedder: CommandEmbedder instance to use
            chunk_size: Target characters per chunk
            overlap: Overlap between chunks for context preservation
        """
        self.embedder = embedder
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        self.chunks: List[Dict] = []
        self.embeddings_cache: Dict[str, npt.NDArray[np.float32]] = {}
        
        logger.info(f"KnowledgeEmbedder initialized (chunk_size={chunk_size}, overlap={overlap})")
    
    def chunk_document(
        self,
        content: str,
        doc_name: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Chunk document into semantic units for embedding.
        
        Strategy:
        1. Split by chapters/sections (structural boundaries)
        2. Further split large sections into paragraph chunks
        3. Maintain overlap for context continuity
        4. Preserve metadata (chapter, section, line numbers)
        
        Args:
            content: Document content (markdown)
            doc_name: Document identifier (e.g., 'redbook')
            metadata: Optional document-level metadata
            
        Returns:
            List of chunk dictionaries with metadata
        """
        chunks = []
        lines = content.split('\n')
        
        current_chapter = None
        current_section = None
        current_chunk = []
        current_chunk_start = 0
        
        for line_num, line in enumerate(lines):
            # Detect chapters
            chapter_match = re.match(r'^##? \*{0,2}Chapter (\d+):\s*(.+?)[\*]*$', line)
            if chapter_match:
                # Flush previous chunk
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    if len(chunk_text.strip()) > 50:  # Minimum chunk size
                        chunks.append(self._create_chunk(
                            chunk_text,
                            doc_name,
                            current_chapter,
                            current_section,
                            current_chunk_start,
                            line_num
                        ))
                
                current_chapter = {
                    'number': int(chapter_match.group(1)),
                    'title': chapter_match.group(2).strip('*').strip()
                }
                current_section = None
                current_chunk = [line]
                current_chunk_start = line_num
                continue
            
            # Detect sections
            section_match = re.match(r'^(#{3,4})\s+(.+)$', line)
            if section_match and current_chapter:
                # Flush previous chunk
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    if len(chunk_text.strip()) > 50:
                        chunks.append(self._create_chunk(
                            chunk_text,
                            doc_name,
                            current_chapter,
                            current_section,
                            current_chunk_start,
                            line_num
                        ))
                
                current_section = {
                    'title': section_match.group(2),
                    'level': len(section_match.group(1))
                }
                current_chunk = [line]
                current_chunk_start = line_num
                continue
            
            # Add line to current chunk
            current_chunk.append(line)
            
            # Check if chunk is getting too large
            chunk_text = '\n'.join(current_chunk)
            if len(chunk_text) >= self.chunk_size:
                # Split into smaller chunks with overlap
                sub_chunks = self._split_large_chunk(
                    chunk_text,
                    doc_name,
                    current_chapter,
                    current_section,
                    current_chunk_start,
                    line_num
                )
                chunks.extend(sub_chunks)
                
                # Keep overlap for next chunk
                overlap_lines = current_chunk[-(self.overlap // 50):]  # ~50 chars per line
                current_chunk = overlap_lines
                current_chunk_start = line_num - len(overlap_lines)
        
        # Flush final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            if len(chunk_text.strip()) > 50:
                chunks.append(self._create_chunk(
                    chunk_text,
                    doc_name,
                    current_chapter,
                    current_section,
                    current_chunk_start,
                    len(lines)
                ))
        
        logger.info(f"Chunked {doc_name}: {len(chunks)} chunks created")
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        doc_name: str,
        chapter: Optional[Dict],
        section: Optional[Dict],
        start_line: int,
        end_line: int
    ) -> Dict:
        """Create a chunk dictionary with metadata."""
        chunk_id = hashlib.md5(text.encode()).hexdigest()[:16]
        
        return {
            'id': chunk_id,
            'text': text.strip(),
            'doc_name': doc_name,
            'chapter': chapter.copy() if chapter else None,
            'section': section.copy() if section else None,
            'start_line': start_line,
            'end_line': end_line,
            'size': len(text),
            'type': self._classify_chunk_type(text)
        }
    
    def _classify_chunk_type(self, text: str) -> str:
        """Classify chunk type based on content."""
        text_lower = text.lower()
        
        # Command-heavy chunks
        if text.count('$') >= 3 or text.count('```') >= 2:
            return 'command_reference'
        
        # Conceptual/explanatory chunks
        if any(word in text_lower for word in ['what', 'why', 'how', 'explain', 'understand']):
            return 'explanation'
        
        # Procedure/tutorial chunks
        if any(word in text_lower for word in ['step', 'first', 'next', 'then', 'finally']):
            return 'procedure'
        
        # General content
        return 'general'
    
    def _split_large_chunk(
        self,
        text: str,
        doc_name: str,
        chapter: Optional[Dict],
        section: Optional[Dict],
        start_line: int,
        end_line: int
    ) -> List[Dict]:
        """Split a large chunk into smaller overlapping chunks."""
        chunks = []
        paragraphs = text.split('\n\n')
        
        current = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            if current_size + para_size > self.chunk_size and current:
                # Create chunk from accumulated paragraphs
                chunk_text = '\n\n'.join(current)
                chunks.append(self._create_chunk(
                    chunk_text,
                    doc_name,
                    chapter,
                    section,
                    start_line,
                    end_line
                ))
                
                # Keep last paragraph for overlap
                current = [current[-1], para] if current else [para]
                current_size = len(current[-1]) + para_size
            else:
                current.append(para)
                current_size += para_size
        
        # Add final chunk
        if current:
            chunk_text = '\n\n'.join(current)
            chunks.append(self._create_chunk(
                chunk_text,
                doc_name,
                chapter,
                section,
                start_line,
                end_line
            ))
        
        return chunks
    
    def generate_embeddings(self, chunks: List[Dict]) -> Dict[str, npt.NDArray[np.float32]]:
        """
        Generate embeddings for all chunks.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            Dictionary mapping chunk_id to embedding vector
        """
        embeddings = {}
        
        for chunk in chunks:
            chunk_id = chunk['id']
            
            # Skip if already cached
            if chunk_id in self.embeddings_cache:
                embeddings[chunk_id] = self.embeddings_cache[chunk_id]
                continue
            
            # Generate embedding for chunk text
            text = chunk['text']
            
            # Preprocess text for embedding
            processed_text = self._preprocess_for_embedding(text)
            
            # Generate embedding using command embedder
            embedding = self.embedder.embed(processed_text)
            
            # Cache and store
            self.embeddings_cache[chunk_id] = embedding
            embeddings[chunk_id] = embedding
        
        logger.info(f"Generated {len(embeddings)} embeddings ({len(self.embeddings_cache)} cached)")
        return embeddings
    
    def _preprocess_for_embedding(self, text: str) -> str:
        """
        Preprocess text for better embedding quality.
        
        Strategies:
        - Remove markdown formatting
        - Extract key terms
        - Normalize whitespace
        - Keep commands and technical terms
        """
        # Remove markdown headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Remove markdown formatting (**, *, `, etc.)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        
        # Remove code block markers but keep content
        text = re.sub(r'```[\w]*\n', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def save_embeddings(self, output_path: Path) -> None:
        """
        Save embeddings and chunks to disk.
        
        Args:
            output_path: Path to save embeddings (JSON + NPY)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save chunks metadata as JSON
        chunks_data = {
            'chunks': self.chunks,
            'count': len(self.chunks),
            'chunk_size': self.chunk_size,
            'overlap': self.overlap
        }
        
        with open(output_path.with_suffix('.json'), 'w') as f:
            json.dump(chunks_data, f, indent=2)
        
        # Save embeddings as numpy array
        if self.embeddings_cache:
            # Create ordered array
            chunk_ids = [chunk['id'] for chunk in self.chunks]
            embeddings_array = np.array([
                self.embeddings_cache[chunk_id] 
                for chunk_id in chunk_ids
            ])
            
            np.save(output_path.with_suffix('.npy'), embeddings_array)
            
            logger.info(f"Saved {len(self.chunks)} chunks and embeddings to {output_path}")
    
    def load_embeddings(self, input_path: Path) -> bool:
        """
        Load embeddings and chunks from disk.
        
        Args:
            input_path: Path to load from
            
        Returns:
            True if loaded successfully
        """
        input_path = Path(input_path)
        
        try:
            # Load chunks metadata
            with open(input_path.with_suffix('.json'), 'r') as f:
                data = json.load(f)
                self.chunks = data['chunks']
                self.chunk_size = data.get('chunk_size', self.chunk_size)
                self.overlap = data.get('overlap', self.overlap)
            
            # Load embeddings
            embeddings_array = np.load(input_path.with_suffix('.npy'))
            
            # Rebuild cache
            self.embeddings_cache = {
                chunk['id']: embeddings_array[i]
                for i, chunk in enumerate(self.chunks)
            }
            
            logger.info(f"Loaded {len(self.chunks)} chunks and embeddings from {input_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading embeddings: {e}")
            return False
    
    def find_similar_chunks(
        self,
        query_embedding: npt.NDArray[np.float32],
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Tuple[Dict, float]]:
        """
        Find chunks most similar to query embedding.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity threshold
            
        Returns:
            List of (chunk, similarity_score) tuples
        """
        if not self.embeddings_cache:
            return []
        
        results = []
        
        for chunk in self.chunks:
            chunk_id = chunk['id']
            if chunk_id not in self.embeddings_cache:
                continue
            
            chunk_embedding = self.embeddings_cache[chunk_id]
            
            # Compute cosine similarity
            similarity = self._cosine_similarity(query_embedding, chunk_embedding)
            
            if similarity >= min_similarity:
                results.append((chunk, float(similarity)))
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def _cosine_similarity(
        self,
        vec1: npt.NDArray[np.float32],
        vec2: npt.NDArray[np.float32]
    ) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
