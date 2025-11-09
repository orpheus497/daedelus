"""
Multi-tier suggestion engine for Daedalus.

Implements a 3-tier cascade for intelligent command suggestions:
1. Exact prefix match (fastest, most relevant)
2. Fuzzy semantic match (embeddings-based)
3. Contextual prediction (pattern-based)

Created by: orpheus497
"""

import logging
import math
from datetime import datetime
from typing import Any

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
        cwd: str | None = None,
        history: list[str] | None = None,
        context_window: int = 10,
    ) -> list[dict[str, Any]]:
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
        suggestions: list[dict[str, Any]] = []

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
        filtered = [s for s in unique_suggestions if s["confidence"] >= self.min_confidence]

        # Sort by confidence (descending)
        filtered.sort(key=lambda x: x["confidence"], reverse=True)

        # Limit to max suggestions
        result = filtered[: self.max_suggestions]

        logger.debug(f"Generated {len(result)} suggestions for '{partial}'")
        return result

    def _tier1_exact_prefix(
        self,
        partial: str,
        cwd: str | None = None,
    ) -> list[dict[str, Any]]:
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
            cwd_filter = "AND cwd LIKE ? || '%'" if cwd else ""
            query = f"""
                SELECT command, COUNT(*) as frequency, MAX(timestamp) as last_used
                FROM command_history
                WHERE command LIKE ? || '%'
                  AND exit_code = 0
                  {cwd_filter}
                GROUP BY command
                ORDER BY frequency DESC, last_used DESC
                LIMIT ?
            """

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

                suggestions.append(
                    {
                        "command": row["command"],
                        "confidence": confidence,
                        "source": "exact_prefix",
                        "frequency": frequency,
                    }
                )

            logger.debug(f"Tier 1: Found {len(suggestions)} exact matches")
            return suggestions

        except Exception as e:
            logger.error(f"Tier 1 error: {e}")
            return []

    def _tier2_semantic(
        self,
        partial: str,
        cwd: str | None = None,
        history: list[str] | None = None,
    ) -> list[dict[str, Any]]:
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

                suggestions.append(
                    {
                        "command": result["command"],
                        "confidence": confidence,
                        "source": "semantic",
                    }
                )

            logger.debug(f"Tier 2: Found {len(suggestions)} semantic matches")
            return suggestions

        except Exception as e:
            logger.error(f"Tier 2 error: {e}")
            return []

    def _tier3_contextual(
        self,
        partial: str,
        cwd: str | None = None,
        history: list[str] | None = None,
    ) -> list[dict[str, Any]]:
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
            """.format(
                "AND h2.command LIKE ? || '%'" if partial.strip() else ""
            )

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

                suggestions.append(
                    {
                        "command": row["command"],
                        "confidence": confidence,
                        "source": "contextual_pattern",
                        "frequency": frequency,
                    }
                )

            logger.debug(f"Tier 3: Found {len(suggestions)} pattern matches")
            return suggestions

        except Exception as e:
            logger.error(f"Tier 3 error: {e}")
            return []

    def rank_suggestions(
        self,
        suggestions: list[dict[str, Any]],
        boost_recent: bool = True,
        boost_cwd: bool = True,
        current_cwd: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Re-rank suggestions using advanced multi-factor scoring.

        Combines multiple signals to produce optimal suggestion ranking:
        - Recency weighting (exponential decay)
        - Directory-specific boosting (context awareness)
        - Success rate integration (learn from failures)
        - Frequency scoring (logarithmic diminishing returns)

        Args:
            suggestions: Initial suggestions
            boost_recent: Apply recency weighting
            boost_cwd: Apply directory-specific boosting
            current_cwd: Current working directory for context

        Returns:
            Re-ranked suggestions sorted by combined score
        """
        if not suggestions:
            return suggestions

        logger.debug(f"Re-ranking {len(suggestions)} suggestions...")

        # Enrich suggestions with additional metadata
        enriched = []
        for sug in suggestions:
            command = sug["command"]
            base_confidence = sug.get("confidence", 0.5)

            # Get command statistics from database
            stats = self._get_command_statistics(command)

            # Calculate individual factors
            recency_factor = self._calculate_recency_factor(stats) if boost_recent else 1.0
            directory_boost = (
                self._calculate_directory_boost(stats, current_cwd) if boost_cwd else 1.0
            )
            success_factor = self._calculate_success_factor(stats)
            frequency_factor = self._calculate_frequency_factor(stats)

            # Combined score: base confidence × all factors
            combined_score = (
                base_confidence
                * recency_factor
                * directory_boost
                * success_factor
                * frequency_factor
            )

            enriched_sug = {
                **sug,
                "recency_factor": recency_factor,
                "directory_boost": directory_boost,
                "success_factor": success_factor,
                "frequency_factor": frequency_factor,
                "combined_score": combined_score,
                "stats": stats,
            }

            enriched.append(enriched_sug)

        # Sort by combined score (descending)
        enriched.sort(key=lambda x: x["combined_score"], reverse=True)

        logger.debug(
            f"Re-ranked suggestions - top score: {enriched[0]['combined_score']:.4f}"
            if enriched
            else "No suggestions to rank"
        )

        return enriched

    def _get_command_statistics(self, command: str) -> dict[str, Any]:
        """
        Retrieve statistics for a command from the database.

        Args:
            command: Command string

        Returns:
            Statistics dictionary with:
            - total_executions: Total number of times executed
            - successful_executions: Number of successful (exit_code=0) executions
            - failed_executions: Number of failed executions
            - last_used_timestamp: Most recent execution timestamp
            - avg_duration: Average execution duration
            - directories: List of directories where command was used
            - total_frequency: Total frequency count
        """
        try:
            # Query for command statistics
            query = """
                SELECT
                    COUNT(*) as total_executions,
                    SUM(CASE WHEN exit_code = 0 THEN 1 ELSE 0 END) as successful_executions,
                    SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) as failed_executions,
                    MAX(timestamp) as last_used_timestamp,
                    AVG(duration) as avg_duration,
                    GROUP_CONCAT(DISTINCT cwd) as directories
                FROM command_history
                WHERE command = ?
            """

            cursor = self.db.conn.execute(query, (command,))
            row = cursor.fetchone()

            if row and row["total_executions"] > 0:
                return {
                    "total_executions": row["total_executions"],
                    "successful_executions": row["successful_executions"],
                    "failed_executions": row["failed_executions"],
                    "last_used_timestamp": row["last_used_timestamp"],
                    "avg_duration": row["avg_duration"] or 0.0,
                    "directories": row["directories"].split(",") if row["directories"] else [],
                    "total_frequency": row["total_executions"],
                }
            else:
                # No statistics available, return defaults
                return {
                    "total_executions": 0,
                    "successful_executions": 0,
                    "failed_executions": 0,
                    "last_used_timestamp": None,
                    "avg_duration": 0.0,
                    "directories": [],
                    "total_frequency": 0,
                }

        except Exception as e:
            logger.warning(f"Failed to get statistics for command '{command}': {e}")
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "last_used_timestamp": None,
                "avg_duration": 0.0,
                "directories": [],
                "total_frequency": 0,
            }

    def _calculate_recency_factor(self, stats: dict[str, Any]) -> float:
        """
        Calculate recency weighting using exponential decay.

        Formula: e^(-λ × days_since_last_use)
        where λ = 0.1 (decay constant)

        Args:
            stats: Command statistics

        Returns:
            Recency factor (0.0 to 1.0)
        """
        last_used = stats.get("last_used_timestamp")

        if last_used is None:
            # No usage history, return neutral
            return 0.5

        # Calculate days since last use
        now = datetime.now().timestamp()
        days_since_use = (now - last_used) / 86400.0  # 86400 seconds in a day

        # Exponential decay with λ = 0.1
        decay_constant = 0.1
        recency_factor = math.exp(-decay_constant * days_since_use)

        return recency_factor

    def _calculate_directory_boost(self, stats: dict[str, Any], current_cwd: str | None) -> float:
        """
        Calculate directory-specific boost for context awareness.

        Boost values:
        - 2.0x if command used in exact same directory
        - 1.5x if command used in parent or child directory
        - 1.0x otherwise (no boost)

        Args:
            stats: Command statistics
            current_cwd: Current working directory

        Returns:
            Directory boost factor (1.0 to 2.0)
        """
        if not current_cwd:
            return 1.0

        directories = stats.get("directories", [])

        if not directories:
            return 1.0

        # Check for exact match
        if current_cwd in directories:
            return 2.0

        # Check for parent/child relationship
        for directory in directories:
            if current_cwd.startswith(directory) or directory.startswith(current_cwd):
                return 1.5

        # No directory match
        return 1.0

    def _calculate_success_factor(self, stats: dict[str, Any]) -> float:
        """
        Calculate success rate factor to penalize frequently failing commands.

        Formula: (successful_executions / total_executions)^2
        Quadratic penalty ensures commands with low success rates are demoted.

        Args:
            stats: Command statistics

        Returns:
            Success factor (0.0 to 1.0)
        """
        total = stats.get("total_executions", 0)
        successful = stats.get("successful_executions", 0)

        if total == 0:
            # No execution history, assume neutral
            return 1.0

        success_rate = successful / total

        # Apply quadratic penalty
        success_factor = success_rate**2

        return success_factor

    def _calculate_frequency_factor(self, stats: dict[str, Any]) -> float:
        """
        Calculate frequency factor with logarithmic diminishing returns.

        Formula: log(frequency + 1)
        Ensures frequently used commands are boosted but with diminishing returns.

        Args:
            stats: Command statistics

        Returns:
            Frequency factor (>= 0.0)
        """
        frequency = stats.get("total_frequency", 0)

        # Logarithmic scaling to prevent over-boosting very frequent commands
        # log(1) = 0, log(2) = 0.69, log(10) = 2.30, log(100) = 4.61
        frequency_factor = math.log(frequency + 1)

        # Normalize to reasonable range (0.0 to ~2.0)
        # Commands used 1 time: ~0.69
        # Commands used 10 times: ~2.30
        # Commands used 100 times: ~4.61
        # We keep raw log value as higher frequency should still boost significantly
        return frequency_factor

    def explain_suggestion(self, suggestion: dict[str, Any]) -> str:
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
