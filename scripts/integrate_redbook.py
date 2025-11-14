#!/usr/bin/env python3
"""
Redbook Integration Script
Parses the Redbook markdown and indexes it into Daedelus knowledge base
"""

import re
import sys
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

# Import daedelus modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from daedelus.utils.config import Config


@dataclass
class RedbookSection:
    """Represents a section of the Redbook"""
    chapter_num: int
    chapter_title: str
    section_num: Optional[str]
    section_title: str
    content: str
    part: str
    topics: List[str]
    commands: List[str]
    code_blocks: List[str]
    line_start: int
    line_end: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return asdict(self)
    
    def get_full_text(self) -> str:
        """Get full searchable text"""
        text = f"Part: {self.part}\n"
        text += f"Chapter {self.chapter_num}: {self.chapter_title}\n"
        if self.section_num:
            text += f"Section {self.section_num}: {self.section_title}\n"
        text += f"\n{self.content}\n"
        
        if self.commands:
            text += "\nCommands:\n" + "\n".join(f"  {cmd}" for cmd in self.commands)
        
        return text


class RedbookParser:
    """Parser for Redbook markdown format"""
    
    def __init__(self, redbook_path: str):
        self.redbook_path = Path(redbook_path)
        self.sections: List[RedbookSection] = []
        self.current_part = ""
        
    def parse(self) -> List[RedbookSection]:
        """Parse the entire Redbook"""
        print(f"📖 Parsing Redbook from {self.redbook_path}")
        
        with open(self.redbook_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"   Total lines: {len(lines):,}")
        
        # Parse structure
        self._parse_structure(lines)
        
        print(f"   Sections extracted: {len(self.sections)}")
        print(f"   Chapters covered: {len(set(s.chapter_num for s in self.sections))}")
        
        return self.sections
    
    def _parse_structure(self, lines: List[str]) -> None:
        """Parse the markdown structure into sections"""
        current_chapter = 0
        current_chapter_title = ""
        current_section = None
        current_section_num = None
        current_section_title = ""
        content_buffer = []
        line_start = 0
        
        for i, line in enumerate(lines, 1):
            # Check for PART markers
            if line.startswith('# PART'):
                self.current_part = line.strip('# \n')
                continue
            
            # Check for Chapter headers
            chapter_match = re.match(r'^## Chapter (\d+): (.+)$', line)
            if chapter_match:
                # Save previous section if exists
                if current_chapter > 0 and content_buffer:
                    self._save_section(
                        current_chapter, current_chapter_title,
                        current_section_num, current_section_title,
                        content_buffer, line_start, i-1
                    )
                    content_buffer = []
                
                current_chapter = int(chapter_match.group(1))
                current_chapter_title = chapter_match.group(2).strip()
                current_section_num = None
                current_section_title = ""
                line_start = i
                continue
            
            # Check for section headers (### with numbers)
            section_match = re.match(r'^### (\d+\.\d+) (.+)$', line)
            if section_match and current_chapter > 0:
                # Save previous section
                if content_buffer:
                    self._save_section(
                        current_chapter, current_chapter_title,
                        current_section_num, current_section_title,
                        content_buffer, line_start, i-1
                    )
                
                current_section_num = section_match.group(1)
                current_section_title = section_match.group(2).strip()
                content_buffer = []
                line_start = i
                continue
            
            # Accumulate content
            if current_chapter > 0:
                content_buffer.append(line)
        
        # Save final section
        if current_chapter > 0 and content_buffer:
            self._save_section(
                current_chapter, current_chapter_title,
                current_section_num, current_section_title,
                content_buffer, line_start, len(lines)
            )
    
    def _save_section(self, chapter_num: int, chapter_title: str,
                     section_num: Optional[str], section_title: str,
                     content_lines: List[str], line_start: int, line_end: int) -> None:
        """Save a parsed section"""
        content = ''.join(content_lines).strip()
        
        # Skip very short sections (likely just headers)
        if len(content) < 50:
            return
        
        # Extract commands and code blocks
        commands = self._extract_commands(content)
        code_blocks = self._extract_code_blocks(content)
        topics = self._extract_topics(chapter_title, section_title, content)
        
        section = RedbookSection(
            chapter_num=chapter_num,
            chapter_title=chapter_title,
            section_num=section_num,
            section_title=section_title or chapter_title,
            content=content,
            part=self.current_part,
            topics=topics,
            commands=commands,
            code_blocks=code_blocks,
            line_start=line_start,
            line_end=line_end
        )
        
        self.sections.append(section)
    
    def _extract_commands(self, content: str) -> List[str]:
        """Extract shell commands from content"""
        commands = []
        
        # Find code blocks with $ prefix or in command examples
        code_block_pattern = r'```(?:bash|sh|shell)?\n(.*?)```'
        for match in re.finditer(code_block_pattern, content, re.DOTALL):
            block = match.group(1)
            for line in block.split('\n'):
                line = line.strip()
                # Extract commands starting with $ or #
                if line.startswith('$ '):
                    commands.append(line[2:].split('#')[0].strip())
                elif line.startswith('# ') and ' ' in line[2:]:
                    # Skip pure comments
                    continue
                elif line and not line.startswith('#') and not line.startswith('//'):
                    # Treat as command
                    cmd = line.split('#')[0].strip()
                    if cmd:
                        commands.append(cmd)
        
        # Also find inline code with command patterns
        inline_code_pattern = r'`([^`]+)`'
        for match in re.finditer(inline_code_pattern, content):
            code = match.group(1)
            # If it looks like a command (has typical command words)
            if any(word in code for word in ['sudo', 'apt', 'dnf', 'systemctl', 'git', 'ssh', 'cd', 'ls', 'grep', 'find']):
                commands.append(code)
        
        return list(set(commands))[:50]  # Limit to 50 unique commands
    
    def _extract_code_blocks(self, content: str) -> List[str]:
        """Extract code blocks"""
        blocks = []
        code_block_pattern = r'```(?:bash|sh|shell|python|c|cpp|rust|go)?\n(.*?)```'
        for match in re.finditer(code_block_pattern, content, re.DOTALL):
            block = match.group(1).strip()
            if block:
                blocks.append(block)
        return blocks[:20]  # Limit to 20 blocks
    
    def _extract_topics(self, chapter_title: str, section_title: str, content: str) -> List[str]:
        """Extract key topics from section"""
        topics = []
        
        # Add chapter and section as topics
        topics.extend([
            word.lower() for word in chapter_title.split()
            if len(word) > 3 and word.lower() not in ['the', 'and', 'for', 'with', 'your']
        ])
        
        if section_title and section_title != chapter_title:
            topics.extend([
                word.lower() for word in section_title.split()
                if len(word) > 3 and word.lower() not in ['the', 'and', 'for', 'with', 'your']
            ])
        
        # Extract bold keywords (likely important terms)
        bold_pattern = r'\*\*([^*]+)\*\*'
        for match in re.finditer(bold_pattern, content):
            term = match.group(1).strip()
            if len(term) > 3 and len(term) < 30:
                topics.append(term.lower())
        
        return list(set(topics))[:30]  # Limit to 30 unique topics


class RedbookIndexer:
    """Indexes Redbook sections into Daedelus database"""
    
    def __init__(self):
        self.config = Config()
        self.data_dir = Path(self.config.data_dir)
        self.db_path = self.data_dir / "history.db"
        
    def index_sections(self, sections: List[RedbookSection]) -> None:
        """Index all sections into database"""
        print(f"\n💾 Indexing {len(sections)} sections into database")
        print(f"   Database: {self.db_path}")
        
        # Create knowledge base tables if they don't exist
        self._create_tables()
        
        # Insert sections
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing Redbook data
        cursor.execute("DELETE FROM knowledge_base WHERE source = 'redbook'")
        cursor.execute("DELETE FROM knowledge_commands WHERE source = 'redbook'")
        
        for i, section in enumerate(sections, 1):
            # Insert section
            cursor.execute("""
                INSERT INTO knowledge_base (
                    source, chapter, section, title, content,
                    part, topics, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                'redbook',
                f"Chapter {section.chapter_num}",
                section.section_num or "",
                f"{section.chapter_title} - {section.section_title}",
                section.get_full_text(),
                section.part,
                json.dumps(section.topics),
                json.dumps({
                    'line_start': section.line_start,
                    'line_end': section.line_end,
                    'command_count': len(section.commands),
                    'code_block_count': len(section.code_blocks)
                })
            ))
            
            section_id = cursor.lastrowid
            
            # Insert commands
            for cmd in section.commands:
                cursor.execute("""
                    INSERT INTO knowledge_commands (
                        knowledge_id, source, command, chapter, section
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    section_id,
                    'redbook',
                    cmd,
                    f"Chapter {section.chapter_num}",
                    section.section_num or ""
                ))
            
            if i % 10 == 0:
                print(f"   Indexed {i}/{len(sections)} sections...")
        
        conn.commit()
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM knowledge_base WHERE source = 'redbook'")
        section_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM knowledge_commands WHERE source = 'redbook'")
        command_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n✅ Indexing complete!")
        print(f"   Sections indexed: {section_count}")
        print(f"   Commands indexed: {command_count}")
    
    def _create_tables(self) -> None:
        """Create knowledge base tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Knowledge base table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                chapter TEXT,
                section TEXT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                part TEXT,
                topics TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, chapter, section)
            )
        """)
        
        # Create FTS index for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_base_fts USING fts5(
                title, content, chapter, section, part, topics,
                content='knowledge_base',
                content_rowid='id'
            )
        """)
        
        # Commands table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_id INTEGER,
                source TEXT NOT NULL,
                command TEXT NOT NULL,
                chapter TEXT,
                section TEXT,
                FOREIGN KEY(knowledge_id) REFERENCES knowledge_base(id)
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kb_source ON knowledge_base(source)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kb_chapter ON knowledge_base(chapter)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kc_command ON knowledge_commands(command)
        """)
        
        conn.commit()
        conn.close()


def test_search(db_path: Path, query: str) -> None:
    """Test searching the indexed Redbook"""
    print(f"\n🔍 Testing search: '{query}'")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Search using FTS5
    cursor.execute("""
        SELECT kb.chapter, kb.section, kb.title, 
               snippet(knowledge_base_fts, 1, '<b>', '</b>', '...', 40) as snippet
        FROM knowledge_base kb
        JOIN knowledge_base_fts fts ON kb.id = fts.rowid
        WHERE knowledge_base_fts MATCH ?
        ORDER BY rank
        LIMIT 5
    """, (query,))
    
    results = cursor.fetchall()
    
    if results:
        print(f"   Found {len(results)} results:")
        for chapter, section, title, snippet in results:
            print(f"\n   📌 {chapter} {section}: {title}")
            print(f"      {snippet[:200]}...")
    else:
        print("   No results found")
    
    conn.close()


def main():
    """Main integration script"""
    print("=" * 80)
    print("🚀 REDBOOK INTEGRATION SCRIPT")
    print("=" * 80)
    
    # Path to Redbook
    redbook_path = Path("/home/orpheus497/Projects/redbook/README.md")
    
    if not redbook_path.exists():
        print(f"❌ Error: Redbook not found at {redbook_path}")
        sys.exit(1)
    
    # Parse Redbook
    parser = RedbookParser(redbook_path)
    sections = parser.parse()
    
    if not sections:
        print("❌ Error: No sections parsed from Redbook")
        sys.exit(1)
    
    # Show statistics
    print(f"\n📊 Parsing Statistics:")
    print(f"   Total sections: {len(sections)}")
    print(f"   Chapters: {len(set(s.chapter_num for s in sections))}")
    print(f"   Total commands: {sum(len(s.commands) for s in sections)}")
    print(f"   Total code blocks: {sum(len(s.code_blocks) for s in sections)}")
    print(f"   Parts covered: {len(set(s.part for s in sections))}")
    
    # Show sample
    print(f"\n📄 Sample Section:")
    sample = sections[10]  # Show a middle section
    print(f"   Chapter {sample.chapter_num}: {sample.chapter_title}")
    print(f"   Section {sample.section_num}: {sample.section_title}")
    print(f"   Topics: {', '.join(sample.topics[:10])}")
    print(f"   Commands: {len(sample.commands)}")
    print(f"   Content length: {len(sample.content)} chars")
    
    # Index into database
    indexer = RedbookIndexer()
    indexer.index_sections(sections)
    
    # Test searches
    test_queries = [
        "disk space",
        "SSH setup",
        "compress directory",
        "firewall",
        "GPU CUDA"
    ]
    
    for query in test_queries:
        test_search(indexer.db_path, query)
    
    print("\n" + "=" * 80)
    print("✅ REDBOOK INTEGRATION COMPLETE")
    print("=" * 80)
    print("\n💡 The Redbook knowledge is now available to Daedelus!")
    print("   Query examples:")
    print("     daedelus ask 'how do I check disk space?'")
    print("     daedelus ask 'how to set up SSH keys?'")
    print("     daedelus generate 'compress a directory with tar'")


if __name__ == "__main__":
    main()
