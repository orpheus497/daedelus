"""
Training Data Organization System
==================================
Comprehensive system for organizing all interactions, commands, file operations,
and ingested documents into structured training data for GGUF model fine-tuning.

Integrates with:
- Command history database
- File operations log
- Tool execution log
- Document ingestion system
- Existing PEFT training pipeline

Author: orpheus497
License: MIT
"""

import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TrainingDataSource(Enum):
    """Sources of training data"""
    COMMAND_HISTORY = "command_history"
    FILE_OPERATIONS = "file_operations"
    TOOL_EXECUTIONS = "tool_executions"
    DOCUMENT_INGESTION = "document_ingestion"
    USER_INTERACTIONS = "user_interactions"
    MANUAL_ENTRY = "manual_entry"


class TrainingDataQuality(Enum):
    """Quality ratings for training data"""
    HIGH = "high"  # Well-formed, successful operations
    MEDIUM = "medium"  # Acceptable but may need filtering
    LOW = "low"  # Errors, failures - use with caution
    EXCLUDED = "excluded"  # Should not be used for training


@dataclass
class TrainingExample:
    """A single training example"""
    source: TrainingDataSource
    instruction: str
    input: str
    output: str
    context: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality: TrainingDataQuality = TrainingDataQuality.MEDIUM
    timestamp: float = 0.0
    session_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class TrainingDataset:
    """Collection of training examples organized for fine-tuning"""
    name: str
    description: str
    examples: List[TrainingExample]
    created: float
    updated: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def split(self, train_ratio: float = 0.8) -> Tuple[List[TrainingExample], List[TrainingExample]]:
        """Split dataset into train/validation sets"""
        split_idx = int(len(self.examples) * train_ratio)
        return self.examples[:split_idx], self.examples[split_idx:]

    def filter_by_quality(self, min_quality: TrainingDataQuality = TrainingDataQuality.MEDIUM) -> List[TrainingExample]:
        """Filter examples by quality threshold"""
        quality_order = [TrainingDataQuality.HIGH, TrainingDataQuality.MEDIUM, TrainingDataQuality.LOW, TrainingDataQuality.EXCLUDED]
        min_idx = quality_order.index(min_quality)

        return [ex for ex in self.examples if quality_order.index(ex.quality) <= min_idx]


class CommandHistoryFormatter:
    """
    Formats command history into training data.
    Teaches the model about command patterns, usage, and context.
    """

    def __init__(self, history_db_path: Path):
        """
        Initialize formatter.

        Args:
            history_db_path: Path to command history database
        """
        self.history_db_path = history_db_path

    def format_command_examples(
        self,
        limit: Optional[int] = None,
        min_success_rate: float = 0.7,
        exclude_sensitive: bool = True
    ) -> List[TrainingExample]:
        """
        Format command history into training examples.

        Args:
            limit: Maximum number of examples
            min_success_rate: Minimum success rate for commands
            exclude_sensitive: Exclude sensitive commands

        Returns:
            List of training examples
        """
        examples = []

        with sqlite3.connect(self.history_db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get successful commands with context
            query = """
                SELECT
                    command,
                    cwd,
                    exit_code,
                    duration,
                    timestamp,
                    session_id
                FROM command_history
                WHERE exit_code = 0
                ORDER BY timestamp DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            for row in conn.execute(query):
                command = row['command']

                # Skip sensitive commands
                if exclude_sensitive and self._is_sensitive_command(command):
                    continue

                # Create training examples for different tasks

                # 1. Command suggestion
                examples.append(TrainingExample(
                    source=TrainingDataSource.COMMAND_HISTORY,
                    instruction="Suggest a command to accomplish this task",
                    input=self._infer_task_description(command),
                    output=command,
                    context=f"Working directory: {row['cwd']}",
                    metadata={
                        'exit_code': row['exit_code'],
                        'duration': row['duration'],
                        'cwd': row['cwd']
                    },
                    quality=TrainingDataQuality.HIGH,
                    timestamp=row['timestamp'],
                    session_id=row['session_id'],
                    tags=['command_suggestion', 'shell']
                ))

                # 2. Command explanation
                examples.append(TrainingExample(
                    source=TrainingDataSource.COMMAND_HISTORY,
                    instruction="Explain what this command does",
                    input=command,
                    output=self._generate_explanation(command),
                    context=f"Working directory: {row['cwd']}",
                    metadata={
                        'exit_code': row['exit_code'],
                        'duration': row['duration']
                    },
                    quality=TrainingDataQuality.MEDIUM,
                    timestamp=row['timestamp'],
                    session_id=row['session_id'],
                    tags=['command_explanation', 'shell']
                ))

        return examples

    def format_command_sequences(self, window_size: int = 5) -> List[TrainingExample]:
        """
        Format command sequences to teach workflow patterns.

        Args:
            window_size: Number of commands in sequence

        Returns:
            List of training examples
        """
        examples = []

        with sqlite3.connect(self.history_db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get command sequences by session
            cursor = conn.execute("""
                SELECT command, cwd, session_id, timestamp
                FROM command_history
                WHERE exit_code = 0
                ORDER BY session_id, timestamp
            """)

            sequences_by_session = defaultdict(list)
            for row in cursor:
                sequences_by_session[row['session_id']].append(row)

            # Create sequence examples
            for session_id, commands in sequences_by_session.items():
                for i in range(len(commands) - window_size + 1):
                    window = commands[i:i + window_size]

                    # Sequence prediction task
                    context_commands = [cmd['command'] for cmd in window[:-1]]
                    next_command = window[-1]['command']

                    examples.append(TrainingExample(
                        source=TrainingDataSource.COMMAND_HISTORY,
                        instruction="Given this sequence of commands, what would be the next logical command?",
                        input="\n".join(context_commands),
                        output=next_command,
                        context=f"Session: {session_id}",
                        metadata={'sequence_length': window_size},
                        quality=TrainingDataQuality.MEDIUM,
                        timestamp=window[-1]['timestamp'],
                        session_id=session_id,
                        tags=['command_sequence', 'workflow']
                    ))

        return examples

    def _is_sensitive_command(self, command: str) -> bool:
        """Check if command contains sensitive data"""
        sensitive_patterns = [
            'password', 'secret', 'token', 'api_key', 'aws_access',
            'ssh-keygen', 'gpg', '.env'
        ]
        return any(pattern in command.lower() for pattern in sensitive_patterns)

    def _infer_task_description(self, command: str) -> str:
        """Infer task description from command"""
        # Simple heuristics - could be improved with ML
        if command.startswith('git'):
            if 'commit' in command:
                return "Commit changes to git repository"
            elif 'push' in command:
                return "Push changes to remote repository"
            elif 'pull' in command:
                return "Pull changes from remote repository"
            elif 'status' in command:
                return "Check git repository status"

        elif command.startswith('ls'):
            return "List files in directory"

        elif command.startswith('cd'):
            return "Change to a directory"

        elif command.startswith('cat') or command.startswith('less'):
            return "View file contents"

        elif command.startswith('grep'):
            return "Search for text pattern in files"

        elif command.startswith('find'):
            return "Find files or directories"

        return f"Execute: {command}"

    def _generate_explanation(self, command: str) -> str:
        """Generate explanation for command"""
        parts = command.split()
        if not parts:
            return "Empty command"

        base_cmd = parts[0]

        explanations = {
            'ls': "Lists files and directories",
            'cd': "Changes the current working directory",
            'pwd': "Prints the current working directory",
            'cat': "Displays file contents",
            'grep': "Searches for text patterns in files",
            'find': "Searches for files and directories",
            'git': "Version control system command",
            'python': "Executes Python script or interpreter",
            'pip': "Python package manager",
            'npm': "Node.js package manager",
            'docker': "Container management command",
        }

        base_explanation = explanations.get(base_cmd, f"Executes {base_cmd} command")

        if len(parts) > 1:
            return f"{base_explanation} with arguments: {' '.join(parts[1:])}"

        return base_explanation


class FileOperationsFormatter:
    """
    Formats file operations into training data.
    Teaches the model about file manipulation patterns.
    """

    def __init__(self, file_ops_db_path: Path):
        """Initialize formatter"""
        self.file_ops_db_path = file_ops_db_path

    def format_file_operation_examples(self, limit: Optional[int] = None) -> List[TrainingExample]:
        """Format file operations into training examples"""
        examples = []

        with sqlite3.connect(self.file_ops_db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT
                    operation,
                    file_path,
                    success,
                    file_type,
                    bytes_read,
                    bytes_written,
                    timestamp,
                    session_id
                FROM file_access_log
                WHERE success = 1
                ORDER BY timestamp DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            for row in conn.execute(query):
                operation = row['operation']
                file_path = row['file_path']

                # File operation task
                examples.append(TrainingExample(
                    source=TrainingDataSource.FILE_OPERATIONS,
                    instruction=f"How do I {operation} a file?",
                    input=f"File: {file_path}",
                    output=self._generate_file_operation_advice(operation, row),
                    metadata={
                        'operation': operation,
                        'file_type': row['file_type'],
                        'bytes_read': row['bytes_read'],
                        'bytes_written': row['bytes_written']
                    },
                    quality=TrainingDataQuality.HIGH,
                    timestamp=row['timestamp'],
                    session_id=row['session_id'],
                    tags=['file_operations', operation]
                ))

        return examples

    def _generate_file_operation_advice(self, operation: str, row: sqlite3.Row) -> str:
        """Generate advice for file operation"""
        if operation == 'read':
            return f"To read a file, use file reading functions. The file was successfully read ({row['bytes_read']} bytes)."
        elif operation == 'write':
            return f"To write a file, use file writing functions with appropriate permissions. Successfully wrote {row['bytes_written']} bytes."
        elif operation == 'list':
            return "To list files in a directory, use directory listing functions."
        else:
            return f"The {operation} operation was performed successfully on the file."


class ToolExecutionFormatter:
    """
    Formats tool executions into training data.
    Teaches the model about tool usage patterns.
    """

    def __init__(self, tool_db_path: Path):
        """Initialize formatter"""
        self.tool_db_path = tool_db_path

    def format_tool_execution_examples(self, limit: Optional[int] = None) -> List[TrainingExample]:
        """Format tool executions into training examples"""
        examples = []

        with sqlite3.connect(self.tool_db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT
                    tool_name,
                    success,
                    duration,
                    timestamp,
                    session_id
                FROM tool_executions
                WHERE success = 1
                ORDER BY timestamp DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            for row in conn.execute(query):
                examples.append(TrainingExample(
                    source=TrainingDataSource.TOOL_EXECUTIONS,
                    instruction="How do I use this tool?",
                    input=f"Tool: {row['tool_name']}",
                    output=f"The {row['tool_name']} tool can be executed to perform its designated function. Execution typically takes {row['duration']:.2f} seconds.",
                    metadata={
                        'tool_name': row['tool_name'],
                        'duration': row['duration']
                    },
                    quality=TrainingDataQuality.MEDIUM,
                    timestamp=row['timestamp'],
                    session_id=row['session_id'],
                    tags=['tool_usage', row['tool_name']]
                ))

        return examples


class TrainingDataOrganizer:
    """
    Main organizer that aggregates all training data sources.
    """

    def __init__(
        self,
        history_db: Path,
        file_ops_db: Path,
        tool_db: Path,
        doc_ingest_db: Path,
        output_dir: Path
    ):
        """
        Initialize organizer.

        Args:
            history_db: Command history database path
            file_ops_db: File operations database path
            tool_db: Tool execution database path
            doc_ingest_db: Document ingestion database path
            output_dir: Directory for organized training data
        """
        self.history_db = history_db
        self.file_ops_db = file_ops_db
        self.tool_db = tool_db
        self.doc_ingest_db = doc_ingest_db
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize formatters
        self.cmd_formatter = CommandHistoryFormatter(history_db)
        self.file_formatter = FileOperationsFormatter(file_ops_db)
        self.tool_formatter = ToolExecutionFormatter(tool_db)

        self._init_database()

    def _init_database(self):
        """Initialize organizer database"""
        db_path = self.output_dir / "training_data_index.db"

        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created REAL,
                    updated REAL,
                    example_count INTEGER,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_examples_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER,
                    source TEXT,
                    quality TEXT,
                    timestamp REAL,
                    session_id TEXT,
                    tags TEXT,
                    FOREIGN KEY (dataset_id) REFERENCES training_datasets(id)
                )
            """)

            conn.commit()

    def collect_all_training_data(
        self,
        include_commands: bool = True,
        include_file_ops: bool = True,
        include_tools: bool = True,
        include_documents: bool = True,
        limit_per_source: Optional[int] = 1000
    ) -> TrainingDataset:
        """
        Collect training data from all sources.

        Args:
            include_commands: Include command history
            include_file_ops: Include file operations
            include_tools: Include tool executions
            include_documents: Include ingested documents
            limit_per_source: Limit per source

        Returns:
            TrainingDataset with all collected examples
        """
        all_examples = []

        # Collect from command history
        if include_commands and self.history_db.exists():
            logger.info("Collecting command history examples...")
            cmd_examples = self.cmd_formatter.format_command_examples(limit=limit_per_source)
            all_examples.extend(cmd_examples)
            logger.info(f"Collected {len(cmd_examples)} command examples")

            # Also collect command sequences
            seq_examples = self.cmd_formatter.format_command_sequences()
            all_examples.extend(seq_examples[:limit_per_source] if limit_per_source else seq_examples)
            logger.info(f"Collected {len(seq_examples)} command sequence examples")

        # Collect from file operations
        if include_file_ops and self.file_ops_db.exists():
            logger.info("Collecting file operation examples...")
            file_examples = self.file_formatter.format_file_operation_examples(limit=limit_per_source)
            all_examples.extend(file_examples)
            logger.info(f"Collected {len(file_examples)} file operation examples")

        # Collect from tool executions
        if include_tools and self.tool_db.exists():
            logger.info("Collecting tool execution examples...")
            tool_examples = self.tool_formatter.format_tool_execution_examples(limit=limit_per_source)
            all_examples.extend(tool_examples)
            logger.info(f"Collected {len(tool_examples)} tool execution examples")

        # Collect from document ingestion
        if include_documents and self.doc_ingest_db.exists():
            logger.info("Collecting document ingestion examples...")
            doc_examples = self._collect_document_examples(limit=limit_per_source)
            all_examples.extend(doc_examples)
            logger.info(f"Collected {len(doc_examples)} document examples")

        # Create dataset
        dataset = TrainingDataset(
            name=f"daedelus_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description="Comprehensive training dataset from all sources",
            examples=all_examples,
            created=datetime.now().timestamp(),
            updated=datetime.now().timestamp(),
            metadata={
                'total_examples': len(all_examples),
                'sources': {
                    'commands': include_commands,
                    'file_ops': include_file_ops,
                    'tools': include_tools,
                    'documents': include_documents
                }
            }
        )

        logger.info(f"Created dataset with {len(all_examples)} total examples")
        return dataset

    def _collect_document_examples(self, limit: Optional[int] = None) -> List[TrainingExample]:
        """Collect examples from document ingestion"""
        examples = []

        with sqlite3.connect(self.doc_ingest_db) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT
                    instruction,
                    input,
                    output,
                    metadata,
                    created
                FROM training_data
                ORDER BY created DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            for row in conn.execute(query):
                metadata = json.loads(row['metadata']) if row['metadata'] else {}

                examples.append(TrainingExample(
                    source=TrainingDataSource.DOCUMENT_INGESTION,
                    instruction=row['instruction'],
                    input=row['input'],
                    output=row['output'],
                    metadata=metadata,
                    quality=TrainingDataQuality.HIGH,
                    timestamp=row['created'],
                    tags=['document', metadata.get('type', 'unknown')]
                ))

        return examples

    def export_dataset(
        self,
        dataset: TrainingDataset,
        format: str = 'jsonl',
        min_quality: TrainingDataQuality = TrainingDataQuality.MEDIUM
    ) -> Path:
        """
        Export dataset to file for training.

        Args:
            dataset: Dataset to export
            format: Export format ('jsonl', 'json', 'alpaca')
            min_quality: Minimum quality threshold

        Returns:
            Path to exported file
        """
        # Filter by quality
        filtered_examples = dataset.filter_by_quality(min_quality)

        # Generate filename
        filename = f"{dataset.name}.{format}"
        output_path = self.output_dir / filename

        if format == 'jsonl':
            with open(output_path, 'w') as f:
                for example in filtered_examples:
                    entry = {
                        'instruction': example.instruction,
                        'input': example.input,
                        'output': example.output
                    }
                    if example.context:
                        entry['context'] = example.context

                    f.write(json.dumps(entry) + '\n')

        elif format == 'json':
            entries = []
            for example in filtered_examples:
                entry = {
                    'instruction': example.instruction,
                    'input': example.input,
                    'output': example.output
                }
                if example.context:
                    entry['context'] = example.context

                entries.append(entry)

            with open(output_path, 'w') as f:
                json.dump(entries, f, indent=2)

        elif format == 'alpaca':
            # Alpaca instruction format
            entries = []
            for example in filtered_examples:
                entry = {
                    'instruction': example.instruction,
                    'input': example.input,
                    'output': example.output,
                    'text': f"### Instruction:\n{example.instruction}\n\n### Input:\n{example.input}\n\n### Response:\n{example.output}"
                }
                entries.append(entry)

            with open(output_path, 'w') as f:
                json.dump(entries, f, indent=2)

        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported {len(filtered_examples)} examples to {output_path}")
        return output_path

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about available training data"""
        stats = {
            'sources': {}
        }

        # Command history stats
        if self.history_db.exists():
            with sqlite3.connect(self.history_db) as conn:
                total_commands = conn.execute("SELECT COUNT(*) FROM command_history").fetchone()[0]
                successful_commands = conn.execute("SELECT COUNT(*) FROM command_history WHERE exit_code = 0").fetchone()[0]

                stats['sources']['commands'] = {
                    'total': total_commands,
                    'successful': successful_commands,
                    'success_rate': (successful_commands / total_commands * 100) if total_commands > 0 else 0
                }

        # File operations stats
        if self.file_ops_db.exists():
            with sqlite3.connect(self.file_ops_db) as conn:
                total_ops = conn.execute("SELECT COUNT(*) FROM file_access_log").fetchone()[0]
                successful_ops = conn.execute("SELECT COUNT(*) FROM file_access_log WHERE success = 1").fetchone()[0]

                stats['sources']['file_operations'] = {
                    'total': total_ops,
                    'successful': successful_ops
                }

        # Tool executions stats
        if self.tool_db.exists():
            with sqlite3.connect(self.tool_db) as conn:
                total_execs = conn.execute("SELECT COUNT(*) FROM tool_executions").fetchone()[0]
                successful_execs = conn.execute("SELECT COUNT(*) FROM tool_executions WHERE success = 1").fetchone()[0]

                stats['sources']['tools'] = {
                    'total': total_execs,
                    'successful': successful_execs
                }

        # Document ingestion stats
        if self.doc_ingest_db.exists():
            with sqlite3.connect(self.doc_ingest_db) as conn:
                total_docs = conn.execute("SELECT COUNT(*) FROM ingested_documents").fetchone()[0]
                total_training = conn.execute("SELECT COUNT(*) FROM training_data").fetchone()[0]

                stats['sources']['documents'] = {
                    'total_documents': total_docs,
                    'training_entries': total_training
                }

        return stats
