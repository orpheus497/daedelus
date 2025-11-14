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

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Manages external knowledge sources for Daedelus.
    
    Processes and indexes documents like The Redbook to make them
    available for AI-powered command generation and assistance.
    """

    def __init__(self, knowledge_dir: Path | None = None):
        """
        Initialize knowledge base.
        
        Args:
            knowledge_dir: Directory containing knowledge base files
        """
        if knowledge_dir is None:
            # Default to data/knowledge_base in project root
            knowledge_dir = Path.home() / ".local/share/daedelus/knowledge_base"
        
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        self.documents: Dict[str, Dict] = {}
        self.chunks: List[Dict] = []
        
        logger.info(f"KnowledgeBase initialized at {self.knowledge_dir}")

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
        Get relevant context from knowledge base for a query.
        
        Args:
            query: User query
            max_results: Maximum number of results
            
        Returns:
            List of relevant text snippets
        """
        if 'redbook' not in self.documents:
            return []
        
        query_lower = query.lower()
        relevant = []
        
        # Search chapter titles
        for chapter in self.documents['redbook']['chapters']:
            if any(word in chapter['title'].lower() for word in query_lower.split()):
                relevant.append(f"Chapter {chapter['number']}: {chapter['title']}")
        
        # Search section titles
        for section in self.documents['redbook']['sections']:
            if any(word in section['title'].lower() for word in query_lower.split()):
                relevant.append(f"  {section['title']}")
        
        return relevant[:max_results]

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


# Global instance
_knowledge_base = None


def get_knowledge_base() -> KnowledgeBase:
    """Get global knowledge base instance."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
        _knowledge_base.load_redbook()
    return _knowledge_base
