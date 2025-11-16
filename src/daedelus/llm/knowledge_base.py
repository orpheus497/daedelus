"""
Knowledge Base Integration for Daedelus.

Integrates external knowledge sources (like The Redbook) into Daedelus's
AI intelligence, making them available for embeddings and LLM context.

Created by: orpheus497
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy.typing as npt

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Manages external knowledge sources for Daedelus.
    
    Processes and indexes documents like The Redbook to make them
    available for AI-powered command generation and assistance.
    """

    def __init__(self, knowledge_dir: Path | None = None, embedder=None):
        """
        Initialize knowledge base.
        
        Args:
            knowledge_dir: Directory containing knowledge base files
            embedder: Optional KnowledgeEmbedder for semantic search
        """
        if knowledge_dir is None:
            # Default to data/knowledge_base in project root
            knowledge_dir = Path.home() / ".local/share/daedelus/knowledge_base"
        
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        self.documents: Dict[str, Dict] = {}
        self.chunks: List[Dict] = []
        
        # Semantic search support (Phase 5)
        self.embedder = embedder
        self.semantic_enabled = embedder is not None
        
        logger.info(f"KnowledgeBase initialized at {self.knowledge_dir} (semantic={'enabled' if self.semantic_enabled else 'disabled'})")

    def load_redbook(self) -> bool:
        """
        Load The Redbook into knowledge base.
        
        Returns:
            True if loaded successfully
        """
        redbook_path = self.knowledge_dir / "REDBOOK.md"
        
        if not redbook_path.exists():
            logger.warning(f"Redbook not found at {redbook_path}")
            return False
        
        try:
            with open(redbook_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the redbook
            doc_info = self._parse_redbook(content)
            
            self.documents['redbook'] = doc_info
            
            logger.info(f"Redbook loaded: {len(doc_info['chapters'])} chapters, {len(doc_info['sections'])} sections")
            return True
            
        except Exception as e:
            logger.error(f"Error loading Redbook: {e}")
            return False

    def _parse_redbook(self, content: str) -> Dict:
        """
        Parse The Redbook into structured sections.
        
        Args:
            content: Redbook content
            
        Returns:
            Parsed document structure
        """
        lines = content.split('\n')
        
        doc_info = {
            'title': 'The Redbook',
            'author': 'orpheus497',
            'chapters': [],
            'sections': [],
            'content': content,
            'size': len(content)
        }
        
        current_chapter = None
        current_section = None
        
        for i, line in enumerate(lines):
            # Detect chapters - can be ## Chapter N: or # **Chapter N:**
            chapter_match = re.match(r'^##? \*{0,2}Chapter (\d+):\s*(.+?)[\*]*$', line)
            if chapter_match:
                chapter_num = int(chapter_match.group(1))
                chapter_title = chapter_match.group(2).strip('*').strip()
                current_chapter = {
                    'number': chapter_num,
                    'title': chapter_title,
                    'line': i,
                    'sections': []
                }
                doc_info['chapters'].append(current_chapter)
                continue
            
            # Detect sections (### or ####)
            section_match = re.match(r'^(#{3,4})\s+(.+)$', line)
            if section_match and current_chapter:
                level = len(section_match.group(1))
                section_title = section_match.group(2)
                current_section = {
                    'title': section_title,
                    'level': level,
                    'line': i,
                    'chapter': current_chapter['number']
                }
                current_chapter['sections'].append(current_section)
                doc_info['sections'].append(current_section)
        
        return doc_info

    def get_relevant_context(self, query: str, max_results: int = 5) -> List[str]:
        """
        Get relevant context from knowledge base for a query with improved ranking.
        
        Args:
            query: User query
            max_results: Maximum number of results
            
        Returns:
            List of relevant text snippets with scores
        """
        if 'redbook' not in self.documents:
            return []
        
        query_lower = query.lower()
        query_words = [w for w in re.findall(r'\w+', query_lower) if len(w) > 2]
        
        # Score-based results
        scored_results = []
        
        # Search chapter titles with scoring
        for chapter in self.documents['redbook']['chapters']:
            title_lower = chapter['title'].lower()
            score = 0
            
            # Exact phrase match (highest priority)
            if query_lower in title_lower:
                score += 100
            
            # Multi-word matches
            matching_words = sum(1 for word in query_words if word in title_lower)
            score += matching_words * 10
            
            # Partial word matches
            for word in query_words:
                if any(word in title_word for title_word in title_lower.split()):
                    score += 3
            
            if score > 0:
                content_preview = self.get_chapter_content(chapter['number'])
                if content_preview:
                    # Extract first meaningful paragraph
                    lines = content_preview.split('\n')
                    preview_text = ""
                    for line in lines[1:]:  # Skip header
                        if line.strip() and not line.strip().startswith('#'):
                            preview_text = line.strip()[:200]
                            break
                    
                    result = f"**Chapter {chapter['number']}: {chapter['title']}**\n{preview_text}..."
                    scored_results.append((score, result, 'chapter'))
        
        # Search section titles with scoring
        for section in self.documents['redbook']['sections']:
            title_lower = section['title'].lower()
            score = 0
            
            # Exact phrase match
            if query_lower in title_lower:
                score += 50
            
            # Multi-word matches
            matching_words = sum(1 for word in query_words if word in title_lower)
            score += matching_words * 5
            
            # Partial word matches
            for word in query_words:
                if any(word in title_word for title_word in title_lower.split()):
                    score += 2
            
            if score > 0:
                result = f"  → {section['title']} (Chapter {section['chapter']})"
                scored_results.append((score, result, 'section'))
        
        # Search content for keyword matches
        content = self.documents['redbook']['content']
        content_lower = content.lower()
        
        # Find contextual matches in content
        for word in query_words:
            pattern = re.compile(r'.{0,100}\b' + re.escape(word) + r'\b.{0,100}', re.IGNORECASE)
            matches = pattern.findall(content)[:3]  # Limit to 3 per word
            for match in matches:
                score = 2
                # Boost if multiple query words appear
                score += sum(1 for w in query_words if w in match.lower())
                
                result = f"  • ...{match.strip()}..."
                scored_results.append((score, result, 'content'))
        
        # Sort by score (highest first) and type priority
        type_priority = {'chapter': 0, 'section': 1, 'content': 2}
        scored_results.sort(key=lambda x: (-x[0], type_priority.get(x[2], 3)))
        
        # Return top results
        return [result for score, result, _ in scored_results[:max_results]]

    def get_chapter_content(self, chapter_num: int) -> Optional[str]:
        """
        Get content of a specific chapter.
        
        Args:
            chapter_num: Chapter number
            
        Returns:
            Chapter content or None
        """
        if 'redbook' not in self.documents:
            return None
        
        doc = self.documents['redbook']
        content_lines = doc['content'].split('\n')
        
        # Find chapter
        chapter = None
        for ch in doc['chapters']:
            if ch['number'] == chapter_num:
                chapter = ch
                break
        
        if not chapter:
            return None
        
        # Find next chapter or end
        start_line = chapter['line']
        end_line = len(content_lines)
        
        for ch in doc['chapters']:
            if ch['number'] > chapter_num:
                end_line = ch['line']
                break
        
        return '\n'.join(content_lines[start_line:end_line])

    def search_command(self, command: str) -> List[Dict]:
        """
        Search for command references in knowledge base.
        
        Args:
            command: Command to search for
            
        Returns:
            List of relevant sections mentioning the command
        """
        if 'redbook' not in self.documents:
            return []
        
        results = []
        content = self.documents['redbook']['content']
        lines = content.split('\n')
        
        # Search for command mentions
        for i, line in enumerate(lines):
            if f'`{command}`' in line or f'$ {command}' in line:
                # Get context (5 lines before and after)
                context_start = max(0, i - 5)
                context_end = min(len(lines), i + 6)
                context = '\n'.join(lines[context_start:context_end])
                
                results.append({
                    'line': i,
                    'context': context,
                    'match': line.strip()
                })
        
        return results[:10]  # Return top 10 matches

    def get_summary(self) -> Dict:
        """
        Get summary of loaded knowledge base.
        
        Returns:
            Summary information
        """
        if 'redbook' not in self.documents:
            return {'loaded': False}
        
        doc = self.documents['redbook']
        return {
            'loaded': True,
            'title': doc['title'],
            'author': doc['author'],
            'chapters': len(doc['chapters']),
            'sections': len(doc['sections']),
            'size_kb': doc['size'] // 1024,
            'path': str(self.knowledge_dir / 'REDBOOK.md')
        }

    def initialize_for_training(self) -> Tuple[List[str], List[Dict]]:
        """
        Prepare knowledge base content for training embeddings and fine-tuning.
        
        Returns:
            Tuple of (text_chunks, metadata)
        """
        if 'redbook' not in self.documents:
            return [], []
        
        text_chunks = []
        metadata = []
        
        doc = self.documents['redbook']
        
        # Create chunks from chapters
        for chapter in doc['chapters']:
            content = self.get_chapter_content(chapter['number'])
            if content:
                # Split into smaller chunks (1000 chars each)
                chunk_size = 1000
                for i in range(0, len(content), chunk_size):
                    chunk = content[i:i + chunk_size]
                    text_chunks.append(chunk)
                    metadata.append({
                        'source': 'redbook',
                        'chapter': chapter['number'],
                        'title': chapter['title'],
                        'chunk_id': i // chunk_size
                    })
        
        logger.info(f"Prepared {len(text_chunks)} chunks from Redbook for training")
        return text_chunks, metadata
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Dict]:
        """
        Perform semantic search on knowledge base using embeddings.
        
        Args:
            query: Search query
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (0-1)
            
        Returns:
            List of results with chunks and similarity scores
        """
        if not self.semantic_enabled or not self.embedder:
            logger.warning("Semantic search not enabled - embedder not initialized")
            return []
        
        # Generate query embedding
        query_text = self.embedder._preprocess_for_embedding(query)
        query_embedding = self.embedder.embedder.embed(query_text)
        
        # Find similar chunks
        similar_chunks = self.embedder.find_similar_chunks(
            query_embedding,
            top_k=top_k,
            min_similarity=min_similarity
        )
        
        # Format results
        results = []
        for chunk, similarity in similar_chunks:
            result = {
                'text': chunk['text'],
                'similarity': similarity,
                'chapter': chunk.get('chapter'),
                'section': chunk.get('section'),
                'type': chunk.get('type', 'general'),
                'preview': chunk['text'][:200] + '...' if len(chunk['text']) > 200 else chunk['text']
            }
            results.append(result)
        
        return results
    
    def hybrid_search(
        self,
        query: str,
        max_results: int = 5,
        keyword_weight: float = 0.4,
        semantic_weight: float = 0.6
    ) -> List[str]:
        """
        Perform hybrid search combining keyword and semantic approaches.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            keyword_weight: Weight for keyword results (0-1)
            semantic_weight: Weight for semantic results (0-1)
            
        Returns:
            List of formatted result strings
        """
        # Normalize weights
        total_weight = keyword_weight + semantic_weight
        keyword_weight /= total_weight
        semantic_weight /= total_weight
        
        # Get keyword results
        keyword_results = self.get_relevant_context(query, max_results=max_results * 2)
        
        # Get semantic results if available
        semantic_results = []
        if self.semantic_enabled:
            semantic_results = self.semantic_search(query, top_k=max_results * 2)
        
        # Combine and re-rank results
        combined_results = []
        
        # Add keyword results with weighted scores
        for i, result in enumerate(keyword_results):
            score = keyword_weight * (1.0 - i / max(len(keyword_results), 1))
            combined_results.append({
                'text': result,
                'score': score,
                'source': 'keyword'
            })
        
        # Add semantic results with weighted scores
        for result in semantic_results:
            score = semantic_weight * result['similarity']
            
            # Format semantic result
            text = f"**{result['chapter']['title'] if result.get('chapter') else 'Content'}**\n{result['preview']}"
            if result.get('section'):
                text = f"**{result['section']['title']}** (Chapter {result['chapter']['number']})\n{result['preview']}"
            
            combined_results.append({
                'text': text,
                'score': score,
                'source': 'semantic'
            })
        
        # De-duplicate and sort by score
        seen_texts = set()
        unique_results = []
        for result in sorted(combined_results, key=lambda x: x['score'], reverse=True):
            # Simple deduplication by first 100 chars
            text_key = result['text'][:100]
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique_results.append(result['text'])
        
        return unique_results[:max_results]
    
    def initialize_semantic_search(self) -> bool:
        """
        Initialize semantic search capabilities.
        
        Creates embeddings for all knowledge base content if not already present.
        
        Returns:
            True if initialization successful
        """
        if not self.semantic_enabled:
            logger.warning("Cannot initialize semantic search - no embedder provided")
            return False
        
        if 'redbook' not in self.documents:
            logger.warning("Cannot initialize semantic search - no documents loaded")
            return False
        
        embeddings_path = self.knowledge_dir / 'embeddings' / 'redbook_embeddings'
        
        # Try to load existing embeddings
        if embeddings_path.with_suffix('.json').exists():
            logger.info("Loading existing embeddings...")
            if self.embedder.load_embeddings(embeddings_path):
                return True
        
        # Generate new embeddings
        logger.info("Generating knowledge base embeddings...")
        
        content = self.documents['redbook']['content']
        chunks = self.embedder.chunk_document(content, 'redbook')
        self.embedder.chunks = chunks
        
        embeddings = self.embedder.generate_embeddings(chunks)
        
        # Save for future use
        self.embedder.save_embeddings(embeddings_path)
        
        logger.info(f"Semantic search initialized with {len(chunks)} chunks")
        return True


# Global instance
_knowledge_base = None


def get_knowledge_base() -> KnowledgeBase:
    """Get global knowledge base instance."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
        _knowledge_base.load_redbook()
    return _knowledge_base
