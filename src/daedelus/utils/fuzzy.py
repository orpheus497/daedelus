"""
Fuzzy search utilities for Daedelus.

Provides fuzzy matching for command search, history search, and suggestions.
Uses thefuzz library for fast fuzzy string matching.

Created by: orpheus497
"""

from typing import Any

from thefuzz import fuzz, process


class FuzzyMatcher:
    """
    Fuzzy string matching for commands and suggestions.

    Uses multiple scoring algorithms:
    - Simple ratio: Basic Levenshtein distance
    - Partial ratio: Best matching substring
    - Token sort: Ignores word order
    - Token set: Ignores duplicates and word order
    """

    def __init__(self, threshold: int = 60) -> None:
        """
        Initialize fuzzy matcher.

        Args:
            threshold: Minimum score (0-100) to consider a match
        """
        self.threshold = threshold

    def match(self, query: str, choice: str) -> int:
        """
        Get match score between query and choice.

        Args:
            query: Search query
            choice: String to match against

        Returns:
            Match score (0-100)
        """
        return fuzz.ratio(query.lower(), choice.lower())

    def partial_match(self, query: str, choice: str) -> int:
        """
        Get partial match score (best substring match).

        Args:
            query: Search query
            choice: String to match against

        Returns:
            Match score (0-100)
        """
        return fuzz.partial_ratio(query.lower(), choice.lower())

    def token_match(self, query: str, choice: str) -> int:
        """
        Get token-based match score (ignores word order).

        Args:
            query: Search query
            choice: String to match against

        Returns:
            Match score (0-100)
        """
        return fuzz.token_sort_ratio(query.lower(), choice.lower())

    def best_match(self, query: str, choices: list[str], limit: int = 5) -> list[tuple[str, int]]:
        """
        Find best matches from a list of choices.

        Args:
            query: Search query
            choices: List of strings to search
            limit: Maximum number of results

        Returns:
            List of (choice, score) tuples, sorted by score descending
        """
        if not query or not choices:
            return []

        # Use extractBests for efficient top-k matching
        results = process.extractBests(
            query.lower(),
            [c.lower() for c in choices],
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.threshold,
            limit=limit,
        )

        # Map back to original choices
        original_map = {c.lower(): c for c in choices}
        return [(original_map[match], score) for match, score in results]

    def search_commands(
        self, query: str, commands: list[str], limit: int = 5
    ) -> list[tuple[str, int]]:
        """
        Search command history with fuzzy matching.

        Args:
            query: Search query
            commands: List of command strings
            limit: Maximum number of results

        Returns:
            List of (command, score) tuples
        """
        return self.best_match(query, commands, limit=limit)

    def filter_commands(
        self, query: str, commands: list[dict[str, Any]], limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Filter command dictionaries by fuzzy matching on 'command' field.

        Args:
            query: Search query
            commands: List of command dictionaries with 'command' field
            limit: Maximum number of results

        Returns:
            Filtered list of command dictionaries
        """
        if not query:
            return commands[:limit]

        # Extract command strings
        command_strings = [cmd.get("command", "") for cmd in commands]

        # Get best matches
        matches = self.best_match(query, command_strings, limit=limit)

        # Return matching command dictionaries
        result = []
        for cmd_str, score in matches:
            for cmd in commands:
                if cmd.get("command") == cmd_str:
                    # Add score to command dict
                    cmd_copy = cmd.copy()
                    cmd_copy["fuzzy_score"] = score
                    result.append(cmd_copy)
                    break

        return result


# Global matcher instance
_matcher: FuzzyMatcher | None = None


def get_matcher(threshold: int = 60) -> FuzzyMatcher:
    """
    Get or create global fuzzy matcher instance.

    Args:
        threshold: Minimum match score (0-100)

    Returns:
        FuzzyMatcher instance
    """
    global _matcher
    if _matcher is None:
        _matcher = FuzzyMatcher(threshold=threshold)
    return _matcher
