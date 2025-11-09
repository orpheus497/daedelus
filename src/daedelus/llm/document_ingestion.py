"""
Document Ingestion System
==========================
Provides comprehensive document ingestion for training data with:
- Multi-format document parsing (PDF, TXT, MD, Code, etc.)
- Intelligent text extraction and preprocessing
- Training data formatting for GGUF models
- Metadata extraction and organization
- Batch processing capabilities
- Integration with existing training pipeline

Author: orpheus497
License: MIT
"""

import hashlib
import json
import logging
import mimetypes
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Types of documents that can be ingested"""
    TEXT = "text"
    MARKDOWN = "markdown"
    CODE = "code"
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    UNKNOWN = "unknown"


class IngestionStatus(Enum):
    """Status of document ingestion"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DocumentMetadata:
    """Metadata about an ingested document"""
    file_path: str
    document_type: DocumentType
    file_size: int
    file_hash: str
    created: float
    modified: float
    ingested: float
    char_count: int
    token_count: Optional[int] = None
    language: Optional[str] = None
    encoding: str = "utf-8"
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None
    source: str = "manual"


@dataclass
class IngestedDocument:
    """Representation of an ingested document"""
    metadata: DocumentMetadata
    content: str
    extracted_text: str
    structured_data: Optional[Dict[str, Any]] = None
    chunks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TrainingDataFormat:
    """Formatted training data ready for model training"""
    instruction: str
    input: str
    output: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    """
    Parses various document formats and extracts text content.
    """

    def __init__(self):
        """Initialize document parser"""
        self.parsers = {
            DocumentType.TEXT: self._parse_text,
            DocumentType.MARKDOWN: self._parse_markdown,
            DocumentType.CODE: self._parse_code,
            DocumentType.PDF: self._parse_pdf,
            DocumentType.HTML: self._parse_html,
            DocumentType.JSON: self._parse_json,
            DocumentType.XML: self._parse_xml,
            DocumentType.YAML: self._parse_yaml,
        }

    def detect_document_type(self, file_path: Path) -> DocumentType:
        """
        Detect document type from file extension and content.

        Args:
            file_path: Path to document

        Returns:
            Detected document type
        """
        ext = file_path.suffix.lower()

        # Map extensions to types
        extension_map = {
            '.txt': DocumentType.TEXT,
            '.md': DocumentType.MARKDOWN,
            '.markdown': DocumentType.MARKDOWN,
            '.pdf': DocumentType.PDF,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML,
            '.json': DocumentType.JSON,
            '.xml': DocumentType.XML,
            '.yaml': DocumentType.YAML,
            '.yml': DocumentType.YAML,
            # Code files
            '.py': DocumentType.CODE,
            '.js': DocumentType.CODE,
            '.ts': DocumentType.CODE,
            '.java': DocumentType.CODE,
            '.cpp': DocumentType.CODE,
            '.c': DocumentType.CODE,
            '.h': DocumentType.CODE,
            '.sh': DocumentType.CODE,
            '.bash': DocumentType.CODE,
            '.zsh': DocumentType.CODE,
            '.fish': DocumentType.CODE,
            '.rs': DocumentType.CODE,
            '.go': DocumentType.CODE,
            '.rb': DocumentType.CODE,
            '.php': DocumentType.CODE,
        }

        return extension_map.get(ext, DocumentType.UNKNOWN)

    def parse_document(self, file_path: Path) -> Optional[IngestedDocument]:
        """
        Parse a document and extract content.

        Args:
            file_path: Path to document

        Returns:
            IngestedDocument or None if parsing failed
        """
        try:
            # Detect type
            doc_type = self.detect_document_type(file_path)

            # Get file metadata
            stat = file_path.stat()
            file_hash = self._compute_file_hash(file_path)

            # Parse content
            parser = self.parsers.get(doc_type)
            if not parser:
                logger.warning(f"No parser for document type {doc_type}: {file_path}")
                return None

            content, extracted_text, structured_data = parser(file_path)

            # Create metadata
            metadata = DocumentMetadata(
                file_path=str(file_path),
                document_type=doc_type,
                file_size=stat.st_size,
                file_hash=file_hash,
                created=stat.st_ctime,
                modified=stat.st_mtime,
                ingested=datetime.now().timestamp(),
                char_count=len(extracted_text),
                encoding='utf-8'
            )

            # Detect language for code files
            if doc_type == DocumentType.CODE:
                metadata.language = self._detect_code_language(file_path)

            return IngestedDocument(
                metadata=metadata,
                content=content,
                extracted_text=extracted_text,
                structured_data=structured_data
            )

        except Exception as e:
            logger.error(f"Failed to parse document {file_path}: {e}")
            return None

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _parse_text(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse plain text file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return content, content, None

    def _parse_markdown(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse markdown file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Extract structured information
        structured = {
            'headers': re.findall(r'^#+\s+(.+)$', content, re.MULTILINE),
            'code_blocks': re.findall(r'```[\w]*\n(.*?)\n```', content, re.DOTALL),
            'links': re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', content)
        }

        return content, content, structured

    def _parse_code(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse code file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Extract structured information
        structured = {
            'functions': self._extract_functions(content, file_path.suffix),
            'classes': self._extract_classes(content, file_path.suffix),
            'imports': self._extract_imports(content, file_path.suffix),
            'comments': self._extract_comments(content, file_path.suffix)
        }

        return content, content, structured

    def _parse_pdf(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse PDF file"""
        try:
            import PyPDF2

            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)

                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text())

                text = '\n\n'.join(text_parts)

                structured = {
                    'page_count': len(reader.pages),
                    'metadata': reader.metadata
                }

                return text, text, structured

        except ImportError:
            logger.warning("PyPDF2 not installed, falling back to text extraction")
            return self._parse_text(file_path)

    def _parse_html(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse HTML file"""
        try:
            from bs4 import BeautifulSoup

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')

            # Remove script and style elements
            for script in soup(['script', 'style']):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            structured = {
                'title': soup.title.string if soup.title else None,
                'headings': [h.get_text() for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])],
                'links': [{'text': a.get_text(), 'href': a.get('href')} for a in soup.find_all('a')]
            }

            return content, text, structured

        except ImportError:
            logger.warning("BeautifulSoup not installed, falling back to text extraction")
            return self._parse_text(file_path)

    def _parse_json(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        data = json.loads(content)

        # Convert to readable text
        text = json.dumps(data, indent=2)

        return content, text, data

    def _parse_xml(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse XML file"""
        import xml.etree.ElementTree as ET

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        try:
            tree = ET.fromstring(content)

            # Extract text
            text = ET.tostring(tree, encoding='unicode', method='text')

            structured = {
                'root_tag': tree.tag,
                'children': [child.tag for child in tree]
            }

            return content, text, structured

        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return content, content, None

    def _parse_yaml(self, file_path: Path) -> Tuple[str, str, Optional[Dict]]:
        """Parse YAML file"""
        try:
            import yaml

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            data = yaml.safe_load(content)

            # Convert to readable text
            text = yaml.dump(data, default_flow_style=False)

            return content, text, data

        except ImportError:
            logger.warning("PyYAML not installed, falling back to text extraction")
            return self._parse_text(file_path)

    def _detect_code_language(self, file_path: Path) -> str:
        """Detect programming language from file extension"""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'zsh',
            '.fish': 'fish',
            '.rs': 'rust',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
        }
        return ext_map.get(file_path.suffix.lower(), 'unknown')

    def _extract_functions(self, content: str, ext: str) -> List[str]:
        """Extract function definitions (basic pattern matching)"""
        patterns = {
            '.py': r'def\s+(\w+)\s*\(',
            '.js': r'function\s+(\w+)\s*\(',
            '.ts': r'function\s+(\w+)\s*\(',
            '.java': r'\w+\s+(\w+)\s*\([^)]*\)\s*\{',
        }

        pattern = patterns.get(ext)
        if pattern:
            return re.findall(pattern, content)
        return []

    def _extract_classes(self, content: str, ext: str) -> List[str]:
        """Extract class definitions"""
        patterns = {
            '.py': r'class\s+(\w+)[\s\(:]',
            '.js': r'class\s+(\w+)[\s\{]',
            '.ts': r'class\s+(\w+)[\s\{]',
            '.java': r'class\s+(\w+)[\s\{]',
        }

        pattern = patterns.get(ext)
        if pattern:
            return re.findall(pattern, content)
        return []

    def _extract_imports(self, content: str, ext: str) -> List[str]:
        """Extract import statements"""
        patterns = {
            '.py': r'(?:from\s+[\w.]+\s+)?import\s+([\w,\s.]+)',
            '.js': r'import\s+.*?from\s+["\'](.+?)["\']',
            '.ts': r'import\s+.*?from\s+["\'](.+?)["\']',
            '.java': r'import\s+([\w.]+);',
        }

        pattern = patterns.get(ext)
        if pattern:
            return re.findall(pattern, content)
        return []

    def _extract_comments(self, content: str, ext: str) -> List[str]:
        """Extract comments"""
        # Single-line comments
        if ext in ['.py', '.sh', '.bash', '.zsh', '.fish']:
            return re.findall(r'#\s*(.+)$', content, re.MULTILINE)
        elif ext in ['.js', '.ts', '.java', '.cpp', '.c']:
            return re.findall(r'//\s*(.+)$', content, re.MULTILINE)
        return []


class DocumentChunker:
    """
    Chunks documents into smaller pieces for training.
    """

    def __init__(self, max_chunk_size: int = 512, overlap: int = 50):
        """
        Initialize chunker.

        Args:
            max_chunk_size: Maximum tokens per chunk
            overlap: Token overlap between chunks
        """
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_document(self, document: IngestedDocument) -> List[Dict[str, Any]]:
        """
        Chunk document into smaller pieces.

        Args:
            document: Document to chunk

        Returns:
            List of chunks with metadata
        """
        text = document.extracted_text

        # Simple character-based chunking (approximate tokens)
        # Rough estimate: 1 token ≈ 4 characters
        char_chunk_size = self.max_chunk_size * 4
        char_overlap = self.overlap * 4

        chunks = []
        start = 0

        while start < len(text):
            end = start + char_chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                sentence_end = max(
                    text.rfind('. ', start, end),
                    text.rfind('! ', start, end),
                    text.rfind('? ', start, end),
                    text.rfind('\n', start, end)
                )

                if sentence_end > start:
                    end = sentence_end + 1

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    'text': chunk_text,
                    'start_char': start,
                    'end_char': end,
                    'chunk_index': len(chunks),
                    'source_file': document.metadata.file_path
                })

            start = end - char_overlap

        document.chunks = chunks
        return chunks


class TrainingDataFormatter:
    """
    Formats ingested documents into training data for the model.
    """

    def format_for_training(self, document: IngestedDocument) -> List[TrainingDataFormat]:
        """
        Format document into training data.

        Args:
            document: Ingested document

        Returns:
            List of training data entries
        """
        training_data = []

        # Create different training formats based on document type
        if document.metadata.document_type == DocumentType.CODE:
            training_data.extend(self._format_code_document(document))

        elif document.metadata.document_type == DocumentType.MARKDOWN:
            training_data.extend(self._format_markdown_document(document))

        else:
            training_data.extend(self._format_generic_document(document))

        return training_data

    def _format_code_document(self, document: IngestedDocument) -> List[TrainingDataFormat]:
        """Format code document for training"""
        entries = []

        # Code explanation task
        entries.append(TrainingDataFormat(
            instruction="Explain what this code does:",
            input=document.content[:2000],  # Limit size
            output=f"This is {document.metadata.language} code that implements various functions and classes.",
            metadata={
                'type': 'code_explanation',
                'language': document.metadata.language,
                'source': document.metadata.file_path
            }
        ))

        # Code-related Q&A from structured data
        if document.structured_data:
            functions = document.structured_data.get('functions', [])
            if functions:
                entries.append(TrainingDataFormat(
                    instruction="What functions are defined in this code?",
                    input=document.content[:2000],
                    output=f"The following functions are defined: {', '.join(functions)}",
                    metadata={'type': 'code_analysis', 'source': document.metadata.file_path}
                ))

            classes = document.structured_data.get('classes', [])
            if classes:
                entries.append(TrainingDataFormat(
                    instruction="What classes are defined in this code?",
                    input=document.content[:2000],
                    output=f"The following classes are defined: {', '.join(classes)}",
                    metadata={'type': 'code_analysis', 'source': document.metadata.file_path}
                ))

        return entries

    def _format_markdown_document(self, document: IngestedDocument) -> List[TrainingDataFormat]:
        """Format markdown document for training"""
        entries = []

        # Summarization task
        entries.append(TrainingDataFormat(
            instruction="Summarize this documentation:",
            input=document.content[:2000],
            output="This documentation covers various topics and provides detailed information.",
            metadata={'type': 'summarization', 'source': document.metadata.file_path}
        ))

        # Q&A from headers
        if document.structured_data and document.structured_data.get('headers'):
            headers = document.structured_data['headers']
            entries.append(TrainingDataFormat(
                instruction="What topics are covered in this documentation?",
                input=document.content[:2000],
                output=f"The documentation covers: {', '.join(headers[:10])}",
                metadata={'type': 'content_analysis', 'source': document.metadata.file_path}
            ))

        return entries

    def _format_generic_document(self, document: IngestedDocument) -> List[TrainingDataFormat]:
        """Format generic document for training"""
        entries = []

        # Generic comprehension task
        entries.append(TrainingDataFormat(
            instruction="What is this document about?",
            input=document.extracted_text[:2000],
            output="This document contains information and text content.",
            metadata={'type': 'comprehension', 'source': document.metadata.file_path}
        ))

        return entries


class DocumentIngestionManager:
    """
    Main manager for document ingestion pipeline.
    """

    def __init__(self, db_path: Path, storage_path: Path):
        """
        Initialize ingestion manager.

        Args:
            db_path: Path to database
            storage_path: Path to store processed documents
        """
        self.db_path = db_path
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.parser = DocumentParser()
        self.chunker = DocumentChunker()
        self.formatter = TrainingDataFormatter()

        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingested_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_hash TEXT NOT NULL,
                    document_type TEXT,
                    file_size INTEGER,
                    char_count INTEGER,
                    token_count INTEGER,
                    language TEXT,
                    category TEXT,
                    tags TEXT,
                    source TEXT,
                    created REAL,
                    modified REAL,
                    ingested REAL,
                    status TEXT,
                    error_message TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    instruction TEXT NOT NULL,
                    input TEXT NOT NULL,
                    output TEXT NOT NULL,
                    metadata TEXT,
                    created REAL,
                    FOREIGN KEY (document_id) REFERENCES ingested_documents(id)
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_hash ON ingested_documents(file_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_type ON ingested_documents(document_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_status ON ingested_documents(status)")

            conn.commit()

    def ingest_document(self, file_path: Path, category: Optional[str] = None, tags: Optional[List[str]] = None) -> bool:
        """
        Ingest a document into the system.

        Args:
            file_path: Path to document
            category: Optional category
            tags: Optional tags

        Returns:
            True if successful
        """
        try:
            # Check if already ingested
            file_hash = self.parser._compute_file_hash(file_path)

            with sqlite3.connect(self.db_path) as conn:
                existing = conn.execute(
                    "SELECT id FROM ingested_documents WHERE file_hash = ?",
                    (file_hash,)
                ).fetchone()

                if existing:
                    logger.info(f"Document already ingested: {file_path}")
                    return True

            # Parse document
            document = self.parser.parse_document(file_path)
            if not document:
                raise ValueError("Failed to parse document")

            # Add category and tags
            if category:
                document.metadata.category = category
            if tags:
                document.metadata.tags = tags

            # Chunk document
            self.chunker.chunk_document(document)

            # Format for training
            training_data = self.formatter.format_for_training(document)

            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO ingested_documents (
                        file_path, file_hash, document_type, file_size, char_count,
                        language, category, tags, source, created, modified, ingested, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document.metadata.file_path,
                    document.metadata.file_hash,
                    document.metadata.document_type.value,
                    document.metadata.file_size,
                    document.metadata.char_count,
                    document.metadata.language,
                    document.metadata.category,
                    json.dumps(document.metadata.tags),
                    document.metadata.source,
                    document.metadata.created,
                    document.metadata.modified,
                    document.metadata.ingested,
                    IngestionStatus.COMPLETED.value
                ))

                document_id = cursor.lastrowid

                # Store training data
                for entry in training_data:
                    conn.execute("""
                        INSERT INTO training_data (
                            document_id, instruction, input, output, metadata, created
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        document_id,
                        entry.instruction,
                        entry.input,
                        entry.output,
                        json.dumps(entry.metadata),
                        datetime.now().timestamp()
                    ))

                conn.commit()

            logger.info(f"Successfully ingested document: {file_path} ({len(training_data)} training entries)")
            return True

        except Exception as e:
            logger.error(f"Failed to ingest document {file_path}: {e}")

            # Record failure
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ingested_documents (
                        file_path, file_hash, status, error_message, ingested
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    str(file_path),
                    file_hash if 'file_hash' in locals() else '',
                    IngestionStatus.FAILED.value,
                    str(e),
                    datetime.now().timestamp()
                ))
                conn.commit()

            return False

    def ingest_directory(self, dir_path: Path, recursive: bool = True, pattern: str = "*") -> Dict[str, int]:
        """
        Ingest all documents in a directory.

        Args:
            dir_path: Path to directory
            recursive: If True, search recursively
            pattern: Glob pattern for files

        Returns:
            Dictionary with statistics
        """
        stats = {'success': 0, 'failed': 0, 'skipped': 0}

        if recursive:
            files = dir_path.rglob(pattern)
        else:
            files = dir_path.glob(pattern)

        for file_path in files:
            if file_path.is_file():
                if self.ingest_document(file_path):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

        return stats

    def export_training_data(self, output_path: Path, format: str = 'jsonl') -> bool:
        """
        Export training data to file.

        Args:
            output_path: Path to output file
            format: Export format ('jsonl', 'json', 'csv')

        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT instruction, input, output, metadata
                    FROM training_data
                    ORDER BY created
                """)

                if format == 'jsonl':
                    with open(output_path, 'w') as f:
                        for row in cursor:
                            entry = {
                                'instruction': row['instruction'],
                                'input': row['input'],
                                'output': row['output']
                            }
                            f.write(json.dumps(entry) + '\n')

                elif format == 'json':
                    entries = []
                    for row in cursor:
                        entries.append({
                            'instruction': row['instruction'],
                            'input': row['input'],
                            'output': row['output']
                        })

                    with open(output_path, 'w') as f:
                        json.dump(entries, f, indent=2)

                else:
                    raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Exported training data to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export training data: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        with sqlite3.connect(self.db_path) as conn:
            total_docs = conn.execute("SELECT COUNT(*) FROM ingested_documents").fetchone()[0]

            by_type = {}
            for row in conn.execute("SELECT document_type, COUNT(*) as count FROM ingested_documents GROUP BY document_type"):
                by_type[row[0]] = row[1]

            by_status = {}
            for row in conn.execute("SELECT status, COUNT(*) as count FROM ingested_documents GROUP BY status"):
                by_status[row[0]] = row[1]

            total_training = conn.execute("SELECT COUNT(*) FROM training_data").fetchone()[0]

            return {
                'total_documents': total_docs,
                'by_type': by_type,
                'by_status': by_status,
                'total_training_entries': total_training
            }
