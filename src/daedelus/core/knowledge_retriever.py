"""
Knowledge Base Retrieval Module
Provides access to indexed knowledge (Redbook, etc.) for RAG pipeline
"""

import sqlite3
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

@dataclass
class KnowledgeResult:
    """A single knowledge base search result"""
    source: str
    chapter: str
    section: str
    title: str
    content: str
    rank: float
    commands: List[str]
    
    def get_context(self, max_length: int = 2000) -> str:
        """Get formatted context for LLM"""
        context = f"## {self.chapter}"
        if self.section:
            context += f" - Section {self.section}"
        context += f"\n### {self.title}\n\n"
        
        # Add content (truncated if needed)
        if len(self.content) > max_length:
            context += self.content[:max_length] + "...\n"
        else:
            context += self.content + "\n"
        
        # Add commands if available
        if self.commands:
            context += f"\n**Relevant commands:**\n"
            for cmd in self.commands[:10]:  # Limit to 10 commands
                context += f"- `{cmd}`\n"
        
        return context


class KnowledgeRetriever:
    """Retrieves relevant knowledge from database for RAG"""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".local/share/daedelus/history.db"
        self.db_path = db_path
        
    def search(self, query: str, limit: int = 5, 
               source: Optional[str] = None) -> List[KnowledgeResult]:
        """
        Search knowledge base using full-text search
        
        Args:
            query: Search query
            limit: Maximum number of results
            source: Filter by source (e.g., 'redbook')
        
        Returns:
            List of KnowledgeResult objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clean query for FTS (remove punctuation, split into OR terms)
        import re
        words = re.findall(r'\w+', query)
        clean_query = ' OR '.join(words) if words else query
        
        # Build query
        sql = """
            SELECT 
                kb.source,
                kb.chapter,
                kb.section,
                kb.title,
                kb.content,
                rank
            FROM knowledge_base kb
            JOIN knowledge_base_fts fts ON kb.id = fts.rowid
            WHERE knowledge_base_fts MATCH ?
        """
        
        params = [clean_query]
        
        if source:
            sql += " AND kb.source = ?"
            params.append(source)
        
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            source, chapter, section, title, content, rank = row
            
            # Get associated commands
            cursor.execute("""
                SELECT DISTINCT command
                FROM knowledge_commands
                WHERE knowledge_id IN (
                    SELECT id FROM knowledge_base
                    WHERE source = ? AND chapter = ? AND section = ?
                )
                LIMIT 20
            """, (source, chapter, section))
            
            commands = [cmd[0] for cmd in cursor.fetchall()]
            
            result = KnowledgeResult(
                source=source,
                chapter=chapter,
                section=section,
                title=title,
                content=content,
                rank=rank,
                commands=commands
            )
            results.append(result)
        
        conn.close()
        return results
    
    def search_commands(self, query: str, limit: int = 10) -> List[Tuple[str, str, str]]:
        """
        Search for specific commands in knowledge base
        
        Returns:
            List of (command, chapter, section) tuples
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT command, chapter, section
            FROM knowledge_commands
            WHERE command LIKE ?
            ORDER BY chapter, section
            LIMIT ?
        """, (f"%{query}%", limit))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_chapter_summary(self, chapter_num: int, source: str = 'redbook') -> Optional[str]:
        """Get summary of a specific chapter"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT title, content
            FROM knowledge_base
            WHERE source = ? AND chapter LIKE ?
            ORDER BY section
            LIMIT 1
        """, (source, f"%{chapter_num}%"))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            title, content = row
            # Return first paragraph as summary
            paragraphs = content.split('\n\n')
            return f"**{title}**\n\n{paragraphs[0] if paragraphs else content[:500]}"
        return None
    
    def get_rag_context(self, query: str, max_tokens: int = 3000) -> str:
        """
        Get formatted context for RAG (Retrieval Augmented Generation)
        
        Args:
            query: User's question/query
            max_tokens: Approximate max tokens (chars * 0.25)
        
        Returns:
            Formatted context string for LLM prompt
        """
        max_chars = max_tokens * 4  # Rough estimate: 1 token ≈ 4 chars
        
        # Search knowledge base
        results = self.search(query, limit=3)
        
        if not results:
            return ""
        
        # Build context
        context = "# Relevant Knowledge Base Information\n\n"
        context += f"The following information from the knowledge base is relevant to your query:\n\n"
        
        remaining_chars = max_chars - len(context)
        
        for i, result in enumerate(results, 1):
            section_context = result.get_context(max_length=remaining_chars // len(results))
            
            context += f"## Source {i}: {result.source}\n"
            context += section_context + "\n"
            context += "-" * 80 + "\n\n"
        
        # Truncate if too long
        if len(context) > max_chars:
            context = context[:max_chars] + "\n\n[Context truncated...]"
        
        return context
    
    def get_statistics(self) -> Dict[str, int]:
        """Get knowledge base statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total sections
        cursor.execute("SELECT COUNT(*) FROM knowledge_base")
        stats['total_sections'] = cursor.fetchone()[0]
        
        # Total commands
        cursor.execute("SELECT COUNT(*) FROM knowledge_commands")
        stats['total_commands'] = cursor.fetchone()[0]
        
        # By source
        cursor.execute("""
            SELECT source, COUNT(*) 
            FROM knowledge_base 
            GROUP BY source
        """)
        stats['by_source'] = dict(cursor.fetchall())
        
        # Chapters
        cursor.execute("SELECT COUNT(DISTINCT chapter) FROM knowledge_base")
        stats['total_chapters'] = cursor.fetchone()[0]
        
        conn.close()
        return stats


# Convenience function for quick access
def search_knowledge(query: str, limit: int = 5) -> List[KnowledgeResult]:
    """Quick search function"""
    retriever = KnowledgeRetriever()
    return retriever.search(query, limit=limit)


def get_rag_context(query: str) -> str:
    """Quick RAG context function"""
    retriever = KnowledgeRetriever()
    return retriever.get_rag_context(query)


if __name__ == "__main__":
    # Test the knowledge retriever
    print("🧪 Testing Knowledge Retriever\n")
    
    retriever = KnowledgeRetriever()
    
    # Test queries
    test_queries = [
        "how to check disk space",
        "SSH key setup",
        "compress with tar",
        "firewall configuration",
        "GPU nvidia"
    ]
    
    for query in test_queries:
        print(f"Query: '{query}'")
        print("-" * 80)
        
        results = retriever.search(query, limit=2)
        
        if results:
            for result in results:
                print(f"✓ {result.chapter} - {result.title}")
                print(f"  Commands: {len(result.commands)}")
                print(f"  Content preview: {result.content[:100]}...")
        else:
            print("  No results found")
        
        print()
    
    # Get RAG context example
    print("\n" + "=" * 80)
    print("RAG Context Example:")
    print("=" * 80)
    context = retriever.get_rag_context("how do I check disk space?", max_tokens=1000)
    print(context)
    
    # Statistics
    print("\n" + "=" * 80)
    print("Knowledge Base Statistics:")
    print("=" * 80)
    stats = retriever.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
