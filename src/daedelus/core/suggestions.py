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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from daedelus.core.database import CommandDatabase
from daedelus.core.embeddings import CommandEmbedder
from daedelus.core.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """
    User preferences for personalized suggestion scoring.

    Allows users to customize how suggestions are ranked based on their workflow preferences.
    """

    # Weighting factors (0.0 to 2.0, default 1.0 = neutral)
    recency_weight: float = 1.0  # How much to weight recent commands
    frequency_weight: float = 1.0  # How much to weight frequently-used commands
    success_weight: float = 1.0  # How much to weight successful commands
    directory_weight: float = 1.0  # How much to weight directory-specific commands

    # Boosting preferences
    prefer_short_commands: bool = False  # Boost commands with fewer tokens
    prefer_fast_commands: bool = False  # Boost commands with low avg duration
    avoid_dangerous_commands: bool = True  # Penalize commands with safety warnings

    # Personalization factors
    boost_user_favorites: list[str] = field(default_factory=list)  # Commands to always boost
    blacklist_commands: list[str] = field(default_factory=list)  # Commands to never suggest

    def apply_preferences_to_score(
        self,
        base_score: float,
        recency_factor: float,
        frequency_factor: float,
        success_factor: float,
        directory_boost: float,
        command: str,
        stats: dict[str, Any],
    ) -> float:
        """
        Apply user preferences to adjust the combined score.

        Args:
            base_score: Base combined score
            recency_factor: Recency factor
            frequency_factor: Frequency factor
            success_factor: Success factor
            directory_boost: Directory boost
            command: Command string
            stats: Command statistics

        Returns:
            Adjusted score with preferences applied
        """
        score = base_score

        # Apply weighting preferences
        # Recalculate with user weights
        adjusted_score = (
            base_score
            * (recency_factor ** self.recency_weight)
            * (frequency_factor ** self.frequency_weight)
            * (success_factor ** self.success_weight)
            * (directory_boost ** self.directory_weight)
        )

        # Short command preference (fewer tokens = faster to type)
        if self.prefer_short_commands:
            token_count = len(command.split())
            if token_count <= 3:
                adjusted_score *= 1.2  # Boost short commands
            elif token_count > 6:
                adjusted_score *= 0.8  # Penalize long commands

        # Fast command preference (low execution time)
        if self.prefer_fast_commands:
            avg_duration = stats.get("avg_duration", 0.0)
            if avg_duration > 0 and avg_duration < 1.0:
                adjusted_score *= 1.3  # Boost fast commands (<1s)
            elif avg_duration > 10.0:
                adjusted_score *= 0.7  # Penalize slow commands (>10s)

        # Boost user favorites
        if command in self.boost_user_favorites:
            adjusted_score *= 2.0  # Strong boost for favorites

        # Blacklist commands
        if command in self.blacklist_commands:
            adjusted_score *= 0.0  # Effectively remove from suggestions

        return adjusted_score


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
        preferences: UserPreferences | None = None,
    ) -> None:
        """
        Initialize suggestion engine with learning loop integration and personalization.

        Args:
            db: Command database
            embedder: Embedding model
            vector_store: Vector similarity search
            max_suggestions: Max suggestions to return
            min_confidence: Min confidence score (0-1)
            preferences: Optional user preferences for personalized scoring
        """
        self.db = db
        self.embedder = embedder
        self.vector_store = vector_store
        self.max_suggestions = max_suggestions
        self.min_confidence = min_confidence
        self.preferences = preferences or UserPreferences()

        # Learning loop tracking
        self._suggestion_feedback: dict[str, list[bool]] = {}  # command -> [accepted, rejected, ...]

        logger.info(
            f"SuggestionEngine initialized with learning loop "
            f"(personalization={'custom' if preferences else 'default'})"
        )

    def get_suggestions(
        self,
        partial: str,
        cwd: str | None = None,
        history: list[str] | None = None,
        context_window: int = 10,
        use_advanced_ranking: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get command suggestions using multi-tier cascade with advanced reranking.

        Args:
            partial: Partially typed command
            cwd: Current working directory
            history: Recent command history
            context_window: Number of recent commands to consider
            use_advanced_ranking: Apply multi-factor reranking (default True)

        Returns:
            List of suggestion dicts with 'command', 'confidence', 'source', and scoring factors
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

        # Apply advanced multi-factor reranking (integrates recency, success rate, directory, acceptance rate)
        if use_advanced_ranking and unique_suggestions:
            logger.debug("Applying advanced multi-factor reranking...")
            ranked_suggestions = self.rank_suggestions(
                unique_suggestions,
                boost_recent=True,
                boost_cwd=True,
                current_cwd=cwd,
            )
        else:
            # Legacy behavior: simple confidence sorting
            ranked_suggestions = unique_suggestions

        # Filter by confidence/combined_score
        if use_advanced_ranking:
            # Filter by combined_score when using advanced ranking
            filtered = [
                s
                for s in ranked_suggestions
                if s.get("combined_score", s.get("confidence", 0)) >= self.min_confidence
            ]
        else:
            # Filter by basic confidence
            filtered = [
                s for s in ranked_suggestions if s.get("confidence", 0) >= self.min_confidence
            ]

        # Sort by combined_score (if available) or confidence
        if use_advanced_ranking:
            filtered.sort(
                key=lambda x: x.get("combined_score", x.get("confidence", 0)), reverse=True
            )
        else:
            filtered.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        # Limit to max suggestions
        result = filtered[: self.max_suggestions]

        logger.debug(
            f"Generated {len(result)} suggestions for '{partial}' "
            f"(advanced_ranking={use_advanced_ranking})"
        )
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
            acceptance_factor = self._calculate_acceptance_factor(command)

            # Combined score: base confidence × all factors
            # Weighted formula balances all signals:
            # - Base confidence (from tier matching)
            # - Recency (decay over time)
            # - Directory context (2x boost for same dir)
            # - Success rate (quadratic penalty for failures)
            # - Frequency (logarithmic diminishing returns)
            # - Acceptance rate (user feedback learning)
            combined_score = (
                base_confidence
                * recency_factor
                * directory_boost
                * success_factor
                * frequency_factor
                * acceptance_factor
            )

            # Apply user preferences to personalize scoring
            if self.preferences:
                combined_score = self.preferences.apply_preferences_to_score(
                    base_score=combined_score,
                    recency_factor=recency_factor,
                    frequency_factor=frequency_factor,
                    success_factor=success_factor,
                    directory_boost=directory_boost,
                    command=command,
                    stats=stats,
                )

            enriched_sug = {
                **sug,
                "recency_factor": recency_factor,
                "directory_boost": directory_boost,
                "success_factor": success_factor,
                "frequency_factor": frequency_factor,
                "acceptance_factor": acceptance_factor,
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

    def _calculate_acceptance_factor(self, command: str) -> float:
        """
        Calculate acceptance rate factor from user feedback.

        This integrates the learning loop by boosting commands that
        users accept and penalizing those they reject.

        Formula:
        - acceptance_rate >= 0.7: 1.5x boost (user loves this suggestion)
        - acceptance_rate >= 0.5: 1.0x neutral (balanced)
        - acceptance_rate < 0.5: 0.5x penalty (user dislikes this suggestion)

        Args:
            command: Command to check

        Returns:
            Acceptance factor (0.5 to 1.5)
        """
        acceptance_rate = self.get_suggestion_acceptance_rate(command)

        # Map acceptance rate to boost/penalty
        if acceptance_rate >= 0.7:
            # High acceptance: boost by 1.5x
            return 1.5
        elif acceptance_rate >= 0.5:
            # Neutral acceptance: no change
            return 1.0
        elif acceptance_rate > 0.0:
            # Low acceptance: penalize by 0.5x
            return 0.5
        else:
            # No feedback data: neutral (assume OK)
            return 1.0

    def record_suggestion_feedback(
        self,
        command: str,
        accepted: bool,
        partial: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Record feedback on suggestion acceptance/rejection.

        This closes the learning loop by tracking which suggestions work.

        Args:
            command: The suggested command
            accepted: True if accepted, False if rejected
            partial: Original partial input (optional)
            context: Additional context (cwd, history, etc.)

        Learning Impact:
            - Accepted suggestions boost future scoring
            - Rejected suggestions reduce future scoring
            - Feedback used in multi-factor ranking
        """
        if command not in self._suggestion_feedback:
            self._suggestion_feedback[command] = []

        self._suggestion_feedback[command].append(accepted)

        logger.debug(
            f"Feedback recorded: '{command}' {'accepted' if accepted else 'rejected'}"
        )

        # Update pattern statistics if we have context
        if context and accepted:
            cwd = context.get("cwd")
            if cwd:
                # Update database pattern statistics
                try:
                    self.db.update_pattern_statistics(
                        context=cwd,
                        command=command,
                        success=True,
                        duration=None,
                    )
                except Exception as e:
                    logger.warning(f"Failed to update pattern statistics: {e}")

    def get_suggestion_acceptance_rate(self, command: str) -> float:
        """
        Get acceptance rate for a command based on feedback.

        Args:
            command: Command to check

        Returns:
            Acceptance rate (0.0 to 1.0), or 0.5 if no feedback
        """
        if command not in self._suggestion_feedback:
            return 0.5  # Neutral if no feedback

        feedback = self._suggestion_feedback[command]
        if not feedback:
            return 0.5

        acceptance_rate = sum(1 for f in feedback if f) / len(feedback)
        return acceptance_rate

    def close_learning_loop(
        self,
        command: str,
        exit_code: int,
        cwd: str,
        session_id: str,
        duration: float | None = None,
    ) -> None:
        """
        Close the learning loop by updating all subsystems after command execution.

        This ensures executed commands are:
        1. Stored in database (already done by caller)
        2. Embedded and indexed in vector store
        3. Pattern statistics updated

        Args:
            command: Executed command
            exit_code: Exit code (0 = success)
            cwd: Current working directory
            session_id: Session ID
            duration: Execution duration in seconds

        Learning Loop:
            execute → store → embed → index → retrieve → suggest → feedback → improve
        """
        success = exit_code == 0

        # 1. Update pattern statistics
        try:
            self.db.update_pattern_statistics(
                context=cwd,
                command=command,
                success=success,
                duration=duration,
            )
            logger.debug(f"Updated pattern statistics for '{command[:50]}...'")
        except Exception as e:
            logger.warning(f"Failed to update pattern statistics: {e}")

        # 2. Update embeddings and vector store (if command was successful)
        if success:
            try:
                # Encode command with context
                embedding = self.embedder.encode_command(command)

                # Add to vector store
                self.vector_store.add_item(
                    command=command,
                    embedding=embedding,
                    metadata={"cwd": cwd, "timestamp": datetime.now().timestamp()},
                )

                logger.debug(f"Added command to vector store: '{command[:50]}...'")
            except Exception as e:
                logger.warning(f"Failed to update vector store: {e}")

        # 3. If command was accepted from suggestion, record positive feedback
        acceptance_rate = self.get_suggestion_acceptance_rate(command)
        if acceptance_rate > 0.5:
            logger.debug(
                f"Command has {acceptance_rate:.0%} acceptance rate - high learning signal"
            )

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

        # Add acceptance rate if available
        command = suggestion.get("command", "")
        acceptance_rate = self.get_suggestion_acceptance_rate(command)

        if acceptance_rate != 0.5:  # Has feedback history
            return f"{base} (confidence: {confidence:.0%}, acceptance: {acceptance_rate:.0%})"
        else:
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
