"""
RAG (Retrieval-Augmented Generation) pipeline for Daedelus.

Retrieves relevant context from command history and embeddings to enhance
LLM responses.

Now includes token compression for efficient semantic comprehension.

Created by: orpheus497
"""

import logging
from typing import Any

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Import token compression (optional)
try:
    from daedelus.llm.semantic_chunker import SemanticChunker, TokenCompressor

    COMPRESSION_AVAILABLE = True
except ImportError:
    COMPRESSION_AVAILABLE = False
    logger.debug("Token compression not available")


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
        enable_compression: bool = True,
        compression_aggressive: bool = False,
        max_context_tokens: int = 1024,
    ) -> None:
        """
        Initialize RAG pipeline with token counting and management.

        Args:
            db: Command database
            embedder: Command embedder
            vector_store: Vector store for similarity search
            max_context_commands: Maximum commands in context
            enable_compression: Enable token compression
            compression_aggressive: Use aggressive compression
            max_context_tokens: Maximum tokens for context (default 1024)
        """
        self.db = db
        self.embedder = embedder
        self.vector_store = vector_store
        self.max_context_commands = max_context_commands
        self.max_context_tokens = max_context_tokens

        # Initialize token compression if available
        self.compressor = None
        if enable_compression and COMPRESSION_AVAILABLE:
            try:
                chunker = SemanticChunker(
                    embedder=embedder,
                    similarity_threshold=0.75,
                    max_chunk_tokens=512,
                )
                self.compressor = TokenCompressor(
                    semantic_chunker=chunker,
                    aggressive=compression_aggressive,
                )
                logger.info("Token compression enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize token compression: {e}")
                self.compressor = None

        logger.info(f"RAG pipeline initialized (max_context_tokens={max_context_tokens})")

    def retrieve_context(
        self,
        query: str,
        cwd: str | None = None,
        history: list[str] | None = None,
        include_similar: bool = True,
        include_recent: bool = True,
        include_patterns: bool = True,
    ) -> dict[str, Any]:
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

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses simple heuristic: ~4 characters per token.
        For precise counting, would need actual tokenizer.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Simple heuristic: average 4 chars per token
        # This is approximate but works well for English text
        return len(text) // 4

    def score_relevance(
        self,
        item: dict[str, Any],
        query: str,
        cwd: str | None = None,
    ) -> float:
        """
        Score relevance of a retrieved item.

        Considers multiple factors:
        - Similarity score (if available)
        - Recency (timestamp)
        - Directory match (cwd)
        - Command success rate

        Args:
            item: Retrieved item (command, similarity, etc.)
            query: Original query
            cwd: Current working directory

        Returns:
            Relevance score (0.0-1.0)
        """
        score = 0.5  # Base score

        # Factor 1: Similarity score (if available)
        if "similarity" in item:
            score += item["similarity"] * 0.3

        # Factor 2: Recency (if timestamp available)
        if "timestamp" in item:
            import time
            age_hours = (time.time() - item["timestamp"]) / 3600
            # Decay over time: recent = higher score
            recency_score = max(0, 1.0 - (age_hours / (24 * 30)))  # Decay over 30 days
            score += recency_score * 0.2

        # Factor 3: Directory match
        if cwd and "cwd" in item:
            if item["cwd"] == cwd:
                score += 0.2  # Exact match
            elif item["cwd"].startswith(cwd) or cwd.startswith(item["cwd"]):
                score += 0.1  # Parent/child directory

        # Factor 4: Success rate (if available)
        if "success" in item and item["success"]:
            score += 0.1

        return min(1.0, score)

    def prioritize_and_truncate(
        self,
        items: list[dict[str, Any]],
        query: str,
        cwd: str | None,
        max_tokens: int,
    ) -> list[dict[str, Any]]:
        """
        Prioritize items by relevance and truncate to fit token budget.

        Args:
            items: List of retrieved items
            query: Original query
            cwd: Current working directory
            max_tokens: Maximum tokens allowed

        Returns:
            Prioritized and truncated list of items
        """
        if not items:
            return []

        # Score all items
        scored_items = []
        for item in items:
            score = self.score_relevance(item, query, cwd)
            scored_items.append((score, item))

        # Sort by relevance (highest first)
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # Truncate to fit token budget
        result = []
        tokens_used = 0

        for score, item in scored_items:
            # Estimate tokens for this item
            item_str = str(item.get("command", ""))
            item_tokens = self.count_tokens(item_str)

            if tokens_used + item_tokens <= max_tokens:
                result.append(item)
                tokens_used += item_tokens
            else:
                # No more room
                break

        logger.debug(f"Prioritized {len(result)}/{len(items)} items ({tokens_used} tokens)")
        return result

    def format_context_for_llm(self, context: dict[str, Any], max_tokens: int | None = None) -> str:
        """
        Format retrieved context into a string for LLM prompt with token management.

        Args:
            context: Context dictionary from retrieve_context()
            max_tokens: Maximum tokens for context (uses self.max_context_tokens if None)

        Returns:
            Formatted context string (truncated if needed)

        Features:
            - Token counting to prevent context overflow
            - Relevance-based prioritization
            - Graceful truncation with fallback
        """
        max_tokens = max_tokens or self.max_context_tokens
        parts = []

        # Add current directory (small, always include)
        if context.get("cwd"):
            parts.append(f"Current directory: {context['cwd']}")

        # Calculate remaining token budget
        base_tokens = self.count_tokens("\n".join(parts))
        remaining_tokens = max(0, max_tokens - base_tokens - 50)  # Reserve 50 for safety

        # Prioritize and truncate similar commands
        if context.get("similar_commands"):
            prioritized = self.prioritize_and_truncate(
                context["similar_commands"],
                context.get("query", ""),
                context.get("cwd"),
                remaining_tokens // 3,  # Allocate 1/3 of budget
            )

            if prioritized:
                parts.append("\nSimilar commands used before:")
                for item in prioritized:
                    parts.append(f"  - {item['command']} (similarity: {item['similarity']:.2f})")

        # Add recent history (fixed size for consistency)
        if context.get("recent_history"):
            parts.append("\nRecent commands:")
            for cmd in context["recent_history"][-5:]:  # Last 5
                parts.append(f"  - {cmd}")

        # Add directory patterns
        if context.get("patterns"):
            prioritized_patterns = self.prioritize_and_truncate(
                context["patterns"],
                context.get("query", ""),
                context.get("cwd"),
                remaining_tokens // 3,  # Allocate 1/3 of budget
            )

            if prioritized_patterns:
                parts.append("\nCommands used in this directory:")
                for item in prioritized_patterns:
                    parts.append(f"  - {item['command']}")

        formatted = "\n".join(parts)

        # Final token check and truncation
        total_tokens = self.count_tokens(formatted)
        if total_tokens > max_tokens:
            logger.warning(f"Context exceeded budget ({total_tokens} > {max_tokens}), truncating...")
            # Simple truncation: cut to max_tokens * 4 characters
            formatted = formatted[: max_tokens * 4]
            formatted += "\n[... context truncated ...]"

        logger.debug(f"Formatted context: {self.count_tokens(formatted)} tokens")
        return formatted

    def build_prompt(
        self,
        query: str,
        task_type: str = "explain",
        cwd: str | None = None,
        history: list[str] | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Build a complete prompt with retrieved context.

        Args:
            query: User query (command or description)
            task_type: Type of task ('explain', 'generate', 'suggest')
            cwd: Current working directory
            history: Recent command history
            max_tokens: Maximum tokens for prompt (enables compression)

        Returns:
            Complete prompt with system instructions and context
        """
        # Retrieve context
        context = self.retrieve_context(query, cwd, history)

        # Format context
        context_str = self.format_context_for_llm(context)

        # Build prompt based on task type
        if task_type == "explain":
            system_prompt = "You are a helpful Linux command expert. Explain commands clearly and concisely."
            prompt_template = f"""Context:
{{context}}

Command to explain: {query}

Provide a clear, concise explanation of what this command does."""

        elif task_type == "generate":
            system_prompt = "You are a helpful Linux command expert. Generate appropriate shell commands based on descriptions."
            prompt_template = f"""Context:
{{context}}

Task: {query}

Generate the appropriate shell command to accomplish this task. Provide only the command, no explanation."""

        elif task_type == "suggest":
            system_prompt = "You are a helpful Linux command expert. Suggest the best command to use."
            prompt_template = f"""Context:
{{context}}

Partial command or task: {query}

Suggest the most appropriate command to use. Provide only the command."""

        else:
            # Generic prompt
            system_prompt = "You are a helpful Linux command expert."
            prompt_template = f"""Context:
{{context}}

Query: {query}

Response:"""

        # Apply token compression if enabled and max_tokens specified
        if self.compressor and max_tokens:
            try:
                compressed = self.compressor.compress_prompt(
                    system_prompt=system_prompt,
                    user_query=query,
                    context=context_str,
                    max_total_tokens=max_tokens,
                )

                context_str = compressed["context"]
                logger.debug(f"Context compressed for token limit: {max_tokens}")

            except Exception as e:
                logger.warning(f"Token compression failed: {e}")
                # Continue with uncompressed context

        # Build final prompt
        prompt = f"""{system_prompt}

{prompt_template.format(context=context_str)}"""

        return prompt

    def __repr__(self) -> str:
        """String representation."""
        return f"RAGPipeline(max_context_commands={self.max_context_commands})"


# Example usage
if __name__ == "__main__":

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
