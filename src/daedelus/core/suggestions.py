"""
Multi-tier suggestion engine for Daedalus.

Implements a 3-tier cascade for intelligent command suggestions:
1. Exact prefix match (fastest, most relevant)
2. Fuzzy semantic match (embeddings-based)
3. Contextual prediction (pattern-based)

Created by: orpheus497
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.vector_store import VectorStore

logger = logging.getLogger(__name__)


class SuggestionEngine:
    """
    Multi-tier command suggestion engine.

    Combines multiple strategies for intelligent suggestions:
    - Tier 1: Exact prefix matching (very fast, high precision)
    - Tier 2: Semantic similarity (embedding-based)
    - Tier 3: Context-aware patterns (Markov chains, sequences)

    Attributes:
        db: Command history database
        embedder: FastText embedding model
        vector_store: Annoy similarity search
        max_suggestions: Maximum number of suggestions to return
        min_confidence: Minimum confidence threshold
    """

    def __init__(
        self,
        db: CommandDatabase,
        embedder: CommandEmbedder,
        vector_store: VectorStore,
        max_suggestions: int = 5,
        min_confidence: float = 0.3,
    ) -> None:
        """
        Initialize suggestion engine.

        Args:
            db: Command database
            embedder: Embedding model
            vector_store: Vector similarity search
            max_suggestions: Max suggestions to return
            min_confidence: Min confidence score (0-1)
        """
        self.db = db
        self.embedder = embedder
        self.vector_store = vector_store
        self.max_suggestions = max_suggestions
        self.min_confidence = min_confidence

        logger.info("SuggestionEngine initialized")

    def get_suggestions(
        self,
        partial: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
        context_window: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get command suggestions using multi-tier cascade.

        Args:
            partial: Partially typed command
            cwd: Current working directory
            history: Recent command history
            context_window: Number of recent commands to consider

        Returns:
            List of suggestion dicts with 'command', 'confidence', 'source'
        """
        suggestions: List[Dict[str, Any]] = []

        # Tier 1: Exact prefix match
        tier1 = self._tier1_exact_prefix(partial, cwd)
        suggestions.extend(tier1)

        # Tier 2: Semantic similarity (if not enough from tier 1)
        if len(suggestions) < self.max_suggestions:
            tier2 = self._tier2_semantic(partial, cwd, history)
            suggestions.extend(tier2)

        # Tier 3: Contextual patterns (if still not enough)
        if len(suggestions) < self.max_suggestions:
            tier3 = self._tier3_contextual(partial, cwd, history)
            suggestions.extend(tier3)

        # Deduplicate by command
        seen = set()
        unique_suggestions = []
        for sug in suggestions:
            if sug["command"] not in seen:
                seen.add(sug["command"])
                unique_suggestions.append(sug)

        # Filter by confidence
        filtered = [
            s for s in unique_suggestions
            if s["confidence"] >= self.min_confidence
        ]

        # Sort by confidence (descending)
        filtered.sort(key=lambda x: x["confidence"], reverse=True)

        # Limit to max suggestions
        result = filtered[:self.max_suggestions]

        logger.debug(f"Generated {len(result)} suggestions for '{partial}'")
        return result

    def _tier1_exact_prefix(
        self,
        partial: str,
        cwd: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Tier 1: Exact prefix matching.

        Fast SQL query for commands starting with the partial string.
        Prioritizes recent and frequently used commands.

        Args:
            partial: Partial command string
            cwd: Current working directory (for filtering)

        Returns:
            List of suggestions
        """
        if not partial.strip():
            return []

        try:
            # Query database for prefix matches
            query = f"""
                SELECT command, COUNT(*) as frequency, MAX(timestamp) as last_used
                FROM command_history
                WHERE command LIKE ? || '%'
                  AND exit_code = 0
                  {}
                GROUP BY command
                ORDER BY frequency DESC, last_used DESC
                LIMIT ?
            """.format("AND cwd LIKE ? || '%'" if cwd else "")

            params = [partial]
            if cwd:
                params.append(cwd)
            params.append(self.max_suggestions)

            cursor = self.db.conn.execute(query, tuple(params))
            rows = cursor.fetchall()

            suggestions = []
            for row in rows:
                # Calculate confidence based on frequency and recency
                frequency = row["frequency"]

                # Simple confidence: normalized frequency
                # In production, could use more sophisticated scoring
                confidence = min(1.0, frequency / 10.0)

                suggestions.append({
                    "command": row["command"],
                    "confidence": confidence,
                    "source": "exact_prefix",
                    "frequency": frequency,
                })

            logger.debug(f"Tier 1: Found {len(suggestions)} exact matches")
            return suggestions

        except Exception as e:
            logger.error(f"Tier 1 error: {e}")
            return []

    def _tier2_semantic(
        self,
        partial: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Tier 2: Semantic similarity using embeddings.

        Uses FastText embeddings + Annoy vector search to find
        semantically similar commands.

        Args:
            partial: Partial command
            cwd: Current directory
            history: Recent commands

        Returns:
            List of suggestions
        """
        if not partial.strip():
            return []

        try:
            # Encode query with context
            query_embedding = self.embedder.encode_context(
                cwd=cwd,
                history=history,
                partial=partial,
            )

            # Search vector store
            results = self.vector_store.search(
                query_embedding,
                top_k=self.max_suggestions * 2,  # Get more, filter later
            )

            suggestions = []
            for result in results:
                # Use similarity as confidence
                confidence = result["similarity"]

                suggestions.append({
                    "command": result["command"],
                    "confidence": confidence,
                    "source": "semantic",
                })

            logger.debug(f"Tier 2: Found {len(suggestions)} semantic matches")
            return suggestions

        except Exception as e:
            logger.error(f"Tier 2 error: {e}")
            return []

    def _tier3_contextual(
        self,
        partial: str,
        cwd: Optional[str] = None,
        history: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Tier 3: Contextual predictions using patterns.

        Uses command sequences and patterns to predict next command
        based on current context.

        Args:
            partial: Partial command
            cwd: Current directory
            history: Recent command history

        Returns:
            List of suggestions
        """
        if not history:
            return []

        try:
            # Get last command from history
            last_command = history[-1] if history else None
            if not last_command:
                return []

            # Query for commands that frequently follow the last command
            query = """
                SELECT h2.command, COUNT(*) as frequency
                FROM command_history h1
                JOIN command_history h2 ON h1.session_id = h2.session_id
                WHERE h1.command = ?
                  AND h2.timestamp > h1.timestamp
                  AND h2.timestamp - h1.timestamp < 300
                  AND h2.exit_code = 0
                  {}
                GROUP BY h2.command
                ORDER BY frequency DESC
                LIMIT ?
            """.format("AND h2.command LIKE ? || '%'" if partial.strip() else "")

            params = [last_command]
            if partial.strip():
                params.append(partial)
            params.append(self.max_suggestions)

            cursor = self.db.conn.execute(query, tuple(params))
            rows = cursor.fetchall()

            suggestions = []
            for row in rows:
                frequency = row["frequency"]

                # Confidence based on how often this sequence occurs
                confidence = min(0.8, frequency / 5.0)  # Cap at 0.8 for patterns

                suggestions.append({
                    "command": row["command"],
                    "confidence": confidence,
                    "source": "contextual_pattern",
                    "frequency": frequency,
                })

            logger.debug(f"Tier 3: Found {len(suggestions)} pattern matches")
            return suggestions

        except Exception as e:
            logger.error(f"Tier 3 error: {e}")
            return []

    def rank_suggestions(
        self,
        suggestions: List[Dict[str, Any]],
        boost_recent: bool = True,
        boost_cwd: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Re-rank suggestions using additional signals.

        Args:
            suggestions: Initial suggestions
            boost_recent: Boost recently used commands
            boost_cwd: Boost commands from current directory

        Returns:
            Re-ranked suggestions
        """
        # TODO: Implement advanced ranking
        # - Recency weighting
        # - Directory-specific boosting
        # - Success rate integration
        # - User feedback learning

        return suggestions

    def explain_suggestion(self, suggestion: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation for a suggestion.

        Args:
            suggestion: Suggestion dictionary

        Returns:
            Explanation string
        """
        source = suggestion.get("source", "unknown")
        confidence = suggestion.get("confidence", 0.0)

        explanations = {
            "exact_prefix": "Exact match from your history",
            "semantic": "Similar command based on meaning",
            "contextual_pattern": "Often used after previous command",
        }

        base = explanations.get(source, "Suggested command")
        return f"{base} (confidence: {confidence:.0%})"


# Example usage
if __name__ == "__main__":
    from pathlib import Path

    logging.basicConfig(level=logging.DEBUG)

    # This would normally be initialized with real components
    print("SuggestionEngine example - requires initialized components")

    # Example suggestion result:
    example_suggestions = [
        {
            "command": "git commit -m 'update'",
            "confidence": 0.95,
            "source": "exact_prefix",
            "frequency": 42,
        },
        {
            "command": "git commit --amend",
            "confidence": 0.75,
            "source": "semantic",
        },
        {
            "command": "git push",
            "confidence": 0.65,
            "source": "contextual_pattern",
            "frequency": 15,
        },
    ]

    for sug in example_suggestions:
        print(f"  {sug['confidence']:.2f} - {sug['command']} ({sug['source']})")
