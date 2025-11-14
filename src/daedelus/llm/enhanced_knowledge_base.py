"""
Enhanced Knowledge Base with Deep Learning and User Correction.

Provides comprehensive Redbook parsing, recursive learning from user corrections,
and intelligent pruning for continuous improvement.

Created by: orpheus497
"""

import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class UserCorrection:
    """Record of user correction for learning."""
    timestamp: str
    query: str
    ai_response: str
    user_correction: str
    context: Dict
    applied: bool = False
    
    
@dataclass
class RedBookSection:
    """Detailed section information."""
    type: str  # 'part', 'chapter', 'section', 'subsection', 'code', 'example'
    level: int
    number: str  # e.g., "1", "1.1", "1.1.1"
    title: str
    content: str
    line_start: int
    line_end: int
    parent: Optional[str] = None  # Parent section number
    keywords: List[str] = None
    commands: List[str] = None


class EnhancedKnowledgeBase:
    """
    Advanced knowledge base with deep parsing and learning.
    """

    def __init__(self, knowledge_dir: Path | None = None, learning_dir: Path | None = None):
        """
        Initialize enhanced knowledge base.
        
        Args:
            knowledge_dir: Directory containing knowledge base files
            learning_dir: Directory for storing learning data
        """
        if knowledge_dir is None:
            knowledge_dir = Path.home() / ".local/share/daedelus/knowledge_base"
        if learning_dir is None:
            learning_dir = Path.home() / ".local/share/daedelus/learning"
        
        self.knowledge_dir = Path(knowledge_dir)
        self.learning_dir = Path(learning_dir)
        
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        
        self.sections: List[RedBookSection] = []
        self.corrections: List[UserCorrection] = []
        self.section_index: Dict[str, RedBookSection] = {}  # number -> section
        self.keyword_index: Dict[str, List[str]] = {}  # keyword -> section numbers
        self.command_index: Dict[str, List[str]] = {}  # command -> section numbers
        
        # Learning statistics
        self.stats = {
            'total_queries': 0,
            'corrections_received': 0,
            'corrections_applied': 0,
            'accuracy_score': 1.0
        }
        
        self._load_learning_data()
        logger.info(f"EnhancedKnowledgeBase initialized at {self.knowledge_dir}")

    def load_redbook_deep(self) -> bool:
        """
        Load and deeply parse The Redbook with full structure.
        
        Returns:
            True if loaded successfully
        """
        redbook_path = self.knowledge_dir / "REDBOOK.md"
        
        if not redbook_path.exists():
            logger.warning(f"Redbook not found at {redbook_path}")
            return False
        
        try:
            with open(redbook_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            self.sections = self._deep_parse_redbook(lines)
            self._build_indices()
            
            logger.info(f"Redbook deeply parsed: {len(self.sections)} sections indexed")
            return True
            
        except Exception as e:
            logger.error(f"Error loading Redbook: {e}")
            return False

    def _deep_parse_redbook(self, lines: List[str]) -> List[RedBookSection]:
        """
        Deep parse Redbook with full hierarchical structure.
        
        Args:
            lines: Redbook lines
            
        Returns:
            List of parsed sections
        """
        sections = []
        current_part = None
        current_chapter = None
        current_section = None
        current_content = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # PART headers (# PART N:)
            part_match = re.match(r'^# PART (\d+):\s*(.+)$', stripped)
            if part_match:
                # Save previous section
                if current_section:
                    current_section.content = '\n'.join(current_content)
                    current_section.line_end = i - 1
                    sections.append(current_section)
                    current_content = []
                
                part_num = part_match.group(1)
                part_title = part_match.group(2)
                current_part = part_num
                
                section = RedBookSection(
                    type='part',
                    level=0,
                    number=part_num,
                    title=part_title,
                    content='',
                    line_start=i,
                    line_end=i
                )
                sections.append(section)
                current_section = None
                continue
            
            # Chapter headers (## Chapter N: or # **Chapter N:**)
            chapter_match = re.match(r'^##?\s*\*{0,2}Chapter (\d+):\s*(.+?)[\*]*$', stripped)
            if chapter_match:
                # Save previous section
                if current_section:
                    current_section.content = '\n'.join(current_content)
                    current_section.line_end = i - 1
                    sections.append(current_section)
                    current_content = []
                
                chapter_num = chapter_match.group(1)
                chapter_title = chapter_match.group(2).strip('*').strip()
                current_chapter = chapter_num
                
                section = RedBookSection(
                    type='chapter',
                    level=1,
                    number=chapter_num,
                    title=chapter_title,
                    content='',
                    line_start=i,
                    line_end=i,
                    parent=current_part
                )
                sections.append(section)
                current_section = section
                continue
            
            # Numbered sections (### 1.1 Title or ### 1.1: Title)
            numbered_match = re.match(r'^###\s+(\d+\.\d+(?:\.\d+)?):?\s*(.+)$', stripped)
            if numbered_match:
                # Save previous section
                if current_section:
                    current_section.content = '\n'.join(current_content)
                    current_section.line_end = i - 1
                    sections.append(current_section)
                    current_content = []
                
                section_num = numbered_match.group(1)
                section_title = numbered_match.group(2)
                
                # Determine level by dots
                level = section_num.count('.') + 2
                
                section = RedBookSection(
                    type='section',
                    level=level,
                    number=section_num,
                    title=section_title,
                    content='',
                    line_start=i,
                    line_end=i,
                    parent=current_chapter
                )
                current_section = section
                continue
            
            # Regular section headers (###, ####)
            header_match = re.match(r'^(#{3,6})\s+(.+)$', stripped)
            if header_match and current_chapter:
                # Save previous section
                if current_section and current_section.type != 'chapter':
                    current_section.content = '\n'.join(current_content)
                    current_section.line_end = i - 1
                    sections.append(current_section)
                    current_content = []
                
                level = len(header_match.group(1))
                title = header_match.group(2)
                
                # Generate pseudo-number
                section_num = f"{current_chapter}.{len([s for s in sections if s.parent == current_chapter])}"
                
                section = RedBookSection(
                    type='subsection',
                    level=level,
                    number=section_num,
                    title=title,
                    content='',
                    line_start=i,
                    line_end=i,
                    parent=current_chapter
                )
                current_section = section
                continue
            
            # Code blocks or examples
            if stripped.startswith('```'):
                if current_section:
                    current_content.append(line.rstrip())
                continue
            
            # Regular content
            if current_section:
                current_content.append(line.rstrip())
        
        # Save last section
        if current_section:
            current_section.content = '\n'.join(current_content)
            current_section.line_end = len(lines) - 1
            sections.append(current_section)
        
        return sections

    def _build_indices(self):
        """Build search indices from parsed sections."""
        self.section_index = {}
        self.keyword_index = {}
        self.command_index = {}
        
        for section in self.sections:
            # Section number index
            self.section_index[section.number] = section
            
            # Extract keywords from title
            keywords = self._extract_keywords(section.title)
            section.keywords = keywords
            
            for keyword in keywords:
                if keyword not in self.keyword_index:
                    self.keyword_index[keyword] = []
                self.keyword_index[keyword].append(section.number)
            
            # Extract commands from content
            commands = self._extract_commands(section.content)
            section.commands = commands
            
            for cmd in commands:
                if cmd not in self.command_index:
                    self.command_index[cmd] = []
                self.command_index[cmd].append(section.number)

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Remove common words
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were'}
        
        words = re.findall(r'\b[a-z]+\b', text.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return list(set(keywords))

    def _extract_commands(self, content: str) -> List[str]:
        """Extract shell commands from content."""
        commands = []
        
        # Find commands in code blocks
        code_blocks = re.findall(r'```(?:bash|shell)?\n(.*?)```', content, re.DOTALL)
        for block in code_blocks:
            lines = block.split('\n')
            for line in lines:
                # Skip comments and empty lines
                if line.strip().startswith('#') or not line.strip():
                    continue
                # Extract command (first word)
                match = re.match(r'^(?:\$\s+)?([a-z-]+)', line.strip())
                if match:
                    commands.append(match.group(1))
        
        # Find inline code commands
        inline_cmds = re.findall(r'`([a-z-]+)`', content)
        commands.extend(inline_cmds)
        
        return list(set(commands))

    def search_deep(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Deep search across all indexed content.
        
        Args:
            query: Search query
            max_results: Maximum results
            
        Returns:
            List of matching sections with relevance scores
        """
        self.stats['total_queries'] += 1
        query_lower = query.lower()
        query_words = self._extract_keywords(query_lower)
        
        results = []
        
        for section in self.sections:
            score = 0.0
            
            # Title match (highest weight)
            if any(word in section.title.lower() for word in query_words):
                score += 10.0
            
            # Keyword match
            if section.keywords:
                matching_keywords = set(query_words) & set(section.keywords)
                score += len(matching_keywords) * 3.0
            
            # Command match
            query_cmds = re.findall(r'\b([a-z-]+)\b', query_lower)
            if section.commands:
                matching_cmds = set(query_cmds) & set(section.commands)
                score += len(matching_cmds) * 5.0
            
            # Content match (lower weight)
            if section.content and query_lower in section.content.lower():
                score += 1.0
            
            if score > 0:
                results.append({
                    'section': section,
                    'score': score,
                    'number': section.number,
                    'title': section.title,
                    'type': section.type,
                    'excerpt': self._get_excerpt(section, query_words)
                })
        
        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results[:max_results]

    def _get_excerpt(self, section: RedBookSection, keywords: List[str]) -> str:
        """Get relevant excerpt from section."""
        if not section.content:
            return section.title
        
        lines = section.content.split('\n')
        for line in lines:
            if any(kw in line.lower() for kw in keywords):
                return line.strip()[:200]
        
        # Return first non-empty line
        for line in lines:
            if line.strip():
                return line.strip()[:200]
        
        return section.title

    def get_section_full(self, section_number: str) -> Optional[RedBookSection]:
        """Get full section by number."""
        return self.section_index.get(section_number)

    def get_section_tree(self, section_number: str) -> List[RedBookSection]:
        """
        Get section with parent context (breadcrumb).
        
        Args:
            section_number: Section number
            
        Returns:
            List of sections from root to target
        """
        section = self.section_index.get(section_number)
        if not section:
            return []
        
        tree = [section]
        
        # Walk up to parents
        current = section
        while current.parent:
            parent = self.section_index.get(current.parent)
            if parent:
                tree.insert(0, parent)
                current = parent
            else:
                break
        
        return tree

    def add_user_correction(self, query: str, ai_response: str, user_correction: str, 
                           context: Dict = None) -> None:
        """
        Record user correction for learning.
        
        Args:
            query: Original query
            ai_response: AI's response
            user_correction: User's correction
            context: Additional context
        """
        correction = UserCorrection(
            timestamp=datetime.now().isoformat(),
            query=query,
            ai_response=ai_response,
            user_correction=user_correction,
            context=context or {},
            applied=False
        )
        
        self.corrections.append(correction)
        self.stats['corrections_received'] += 1
        
        # Save correction
        self._save_correction(correction)
        
        # Apply correction immediately
        self._apply_correction(correction)
        
        logger.info(f"User correction recorded: {query[:50]}...")

    def _apply_correction(self, correction: UserCorrection):
        """
        Apply user correction to improve future responses.
        
        This creates a correction mapping that influences future searches.
        """
        # Simple learning: boost sections mentioned in correction
        query_words = self._extract_keywords(correction.user_correction)
        
        # Find sections matching correction
        for section in self.sections:
            if any(word in section.title.lower() for word in query_words):
                # Add correction keywords to section
                if section.keywords:
                    section.keywords.extend(query_words)
                    section.keywords = list(set(section.keywords))
                
                # Rebuild keyword index for this section
                for keyword in query_words:
                    if keyword not in self.keyword_index:
                        self.keyword_index[keyword] = []
                    if section.number not in self.keyword_index[keyword]:
                        self.keyword_index[keyword].append(section.number)
        
        correction.applied = True
        self.stats['corrections_applied'] += 1
        
        # Update accuracy score
        self._update_accuracy()

    def _update_accuracy(self):
        """Update accuracy score based on corrections."""
        if self.stats['total_queries'] > 0:
            error_rate = self.stats['corrections_received'] / self.stats['total_queries']
            self.stats['accuracy_score'] = max(0.0, 1.0 - error_rate)

    def ask_for_confirmation(self, query: str, response: str) -> str:
        """
        Format a confirmation request to the user.
        
        Args:
            query: Original query
            response: AI response
            
        Returns:
            Formatted confirmation message
        """
        return f"""
**AI Response:**
{response}

**Was this helpful?**
- Type 'y' if correct
- Type 'n' and provide correction: "n: <your correction>"
- Press Enter to continue
"""

    def _save_correction(self, correction: UserCorrection):
        """Save correction to disk."""
        corrections_file = self.learning_dir / "corrections.jsonl"
        
        with open(corrections_file, 'a') as f:
            f.write(json.dumps(asdict(correction)) + '\n')

    def _load_learning_data(self):
        """Load previous corrections and learning data."""
        corrections_file = self.learning_dir / "corrections.jsonl"
        
        if not corrections_file.exists():
            return
        
        try:
            with open(corrections_file, 'r') as f:
                for line in f:
                    data = json.loads(line.strip())
                    correction = UserCorrection(**data)
                    self.corrections.append(correction)
                    
                    # Reapply corrections
                    if not correction.applied:
                        self._apply_correction(correction)
            
            logger.info(f"Loaded {len(self.corrections)} previous corrections")
        except Exception as e:
            logger.error(f"Error loading corrections: {e}")

    def get_stats(self) -> Dict:
        """Get learning statistics."""
        return {
            **self.stats,
            'total_sections': len(self.sections),
            'indexed_keywords': len(self.keyword_index),
            'indexed_commands': len(self.command_index),
            'corrections_stored': len(self.corrections)
        }

    def export_learning_summary(self) -> str:
        """Export learning summary as markdown."""
        stats = self.get_stats()
        
        summary = f"""# Daedelus Learning Summary

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Statistics
- **Total Queries**: {stats['total_queries']}
- **Corrections Received**: {stats['corrections_received']}
- **Corrections Applied**: {stats['corrections_applied']}
- **Accuracy Score**: {stats['accuracy_score']:.1%}

## Knowledge Base
- **Sections Indexed**: {stats['total_sections']}
- **Keywords Indexed**: {stats['indexed_keywords']}
- **Commands Indexed**: {stats['indexed_commands']}

## Recent Corrections
"""
        
        # Add recent corrections
        for correction in self.corrections[-10:]:
            summary += f"\n### {correction.timestamp}\n"
            summary += f"**Query**: {correction.query}\n"
            summary += f"**Correction**: {correction.user_correction}\n"
        
        return summary
