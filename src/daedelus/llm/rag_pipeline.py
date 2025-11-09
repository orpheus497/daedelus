"""
RAG (Retrieval-Augmented Generation) pipeline for Daedelus.

Retrieves relevant context from command history and embeddings to enhance
LLM responses.

Created by: orpheus497
"""

import logging
from typing import Any, Dict, List, Optional

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline.

    Combines vector similarity search with command history to provide
    relevant context for LLM generation.

    Attributes:
        db: Command history database
        embedder: Command embedder for semantic search
        vector_store: Vector similarity search index
        max_context_commands: Maximum commands to include in context
    """

    def __init__(
        self,
        db: CommandDatabase,
        embedder: CommandEmbedder,
        vector_store: VectorStore,
        max_context_commands: int = 10,
    ) -> None:
        """
        Initialize RAG pipeline.

        Args:
            db: Command database
            embedder: Command embedder
            vector_store: Vector store for similarity search
            max_context_commands: Maximum commands in context
        """
        self.db = db
        self.embedder = embedder
        self.vector_store = vector_store
        self.max_context_commands = max_context_commands

        logger.info("RAG pipeline initialized")

    def retrieve_context(
        self,
        query: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
        include_similar: bool = True,
        include_recent: bool = True,
        include_patterns: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context for a query.

        Args:
            query: Query text (command or description)
            cwd: Current working directory
            history: Recent command history
            include_similar: Include semantically similar commands
            include_recent: Include recent commands from history
            include_patterns: Include common patterns

        Returns:
            Context dictionary with retrieved information
        """
        context = {
            "query": query,
            "cwd": cwd,
            "recent_history": history or [],
            "similar_commands": [],
            "recent_commands": [],
            "patterns": [],
        }

        # 1. Get semantically similar commands
        if include_similar:
            try:
                # Encode query
                query_embedding = self.embedder.encode_command(query)

                # Search vector store
                similar_results = self.vector_store.search(
                    query_embedding,
                    top_k=self.max_context_commands,
                )

                context["similar_commands"] = [
                    {
                        "command": r["command"],
                        "similarity": r["similarity"],
                    }
                    for r in similar_results
                ]

                logger.debug(f"Found {len(similar_results)} similar commands")

            except Exception as e:
                logger.warning(f"Failed to retrieve similar commands: {e}")

        # 2. Get recent successful commands
        if include_recent:
            try:
                recent = self.db.get_recent_commands(
                    n=self.max_context_commands,
                    successful_only=True,
                )

                context["recent_commands"] = [
                    {
                        "command": cmd["command"],
                        "cwd": cmd["cwd"],
                        "timestamp": cmd["timestamp"],
                    }
                    for cmd in recent
                ]

                logger.debug(f"Retrieved {len(recent)} recent commands")

            except Exception as e:
                logger.warning(f"Failed to retrieve recent commands: {e}")

        # 3. Get command patterns from current directory
        if include_patterns and cwd:
            try:
                # Search for commands used in this directory
                cwd_commands = self.db.search_commands("", cwd_filter=cwd, limit=5)

                context["patterns"] = [
                    {
                        "command": cmd["command"],
                        "cwd": cmd["cwd"],
                    }
                    for cmd in cwd_commands
                ]

                logger.debug(f"Found {len(cwd_commands)} directory patterns")

            except Exception as e:
                logger.warning(f"Failed to retrieve patterns: {e}")

        return context

    def format_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format retrieved context into a string for LLM prompt.

        Args:
            context: Context dictionary from retrieve_context()

        Returns:
            Formatted context string
        """
        parts = []

        # Add current directory
        if context.get("cwd"):
            parts.append(f"Current directory: {context['cwd']}")

        # Add recent history
        if context.get("recent_history"):
            parts.append("\nRecent commands:")
            for cmd in context["recent_history"][-5:]:  # Last 5
                parts.append(f"  - {cmd}")

        # Add similar commands
        if context.get("similar_commands"):
            parts.append("\nSimilar commands used before:")
            for item in context["similar_commands"][:5]:  # Top 5
                parts.append(f"  - {item['command']} (similarity: {item['similarity']:.2f})")

        # Add directory patterns
        if context.get("patterns"):
            parts.append("\nCommands used in this directory:")
            for item in context["patterns"][:3]:  # Top 3
                parts.append(f"  - {item['command']}")

        return "\n".join(parts)

    def build_prompt(
        self,
        query: str,
        task_type: str = "explain",
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> str:
        """
        Build a complete prompt with retrieved context.

        Args:
            query: User query (command or description)
            task_type: Type of task ('explain', 'generate', 'suggest')
            cwd: Current working directory
            history: Recent command history

        Returns:
            Complete prompt with system instructions and context
        """
        # Retrieve context
        context = self.retrieve_context(query, cwd, history)

        # Format context
        context_str = self.format_context_for_llm(context)

        # Build prompt based on task type
        if task_type == "explain":
            prompt = f"""You are a helpful Linux command expert. Explain commands clearly and concisely.

Context:
{context_str}

Command to explain: {query}

Provide a clear, concise explanation of what this command does."""

        elif task_type == "generate":
            prompt = f"""You are a helpful Linux command expert. Generate appropriate shell commands based on descriptions.

Context:
{context_str}

Task: {query}

Generate the appropriate shell command to accomplish this task. Provide only the command, no explanation."""

        elif task_type == "suggest":
            prompt = f"""You are a helpful Linux command expert. Suggest the best command to use.

Context:
{context_str}

Partial command or task: {query}

Suggest the most appropriate command to use. Provide only the command."""

        else:
            # Generic prompt
            prompt = f"""You are a helpful Linux command expert.

Context:
{context_str}

Query: {query}

Response:"""

        return prompt

    def __repr__(self) -> str:
        """String representation."""
        return f"RAGPipeline(max_context_commands={self.max_context_commands})"


# Example usage
if __name__ == "__main__":
    from pathlib import Path

    logging.basicConfig(level=logging.DEBUG)

    print("RAG Pipeline example - requires initialized components")

    # Example context result:
    example_context = {
        "query": "list files",
        "cwd": "/home/user/projects",
        "recent_history": ["cd projects", "git status"],
        "similar_commands": [
            {"command": "ls -la", "similarity": 0.85},
            {"command": "ls -lh", "similarity": 0.78},
        ],
        "recent_commands": [
            {"command": "git status", "cwd": "/home/user/projects"},
        ],
        "patterns": [
            {"command": "git status"},
            {"command": "git add ."},
        ],
    }

    # Create RAG pipeline (mock)
    # In real use, would be:
    # rag = RAGPipeline(db, embedder, vector_store)
    # prompt = rag.build_prompt("ls", task_type="explain")

    print("\nExample formatted context:")
    # Mock pipeline for demonstration
    class MockRAG(RAGPipeline):
        def __init__(self):
            self.max_context_commands = 10

    mock_rag = MockRAG()
    formatted = mock_rag.format_context_for_llm(example_context)
    print(formatted)
