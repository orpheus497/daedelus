"""
Intent Classifier for Daedelus.

Classifies user intent from natural language queries:
- Task decomposition for complex requests
- Command chaining suggestions
- Error-driven correction suggestions
- Action vs. question detection
- Priority and urgency detection

Enables intelligent understanding of:
- "Find all Python files and count lines of code" → decompose into find + wc
- "Show me files modified today" → ls/find with date filters
- "How do I compress a directory?" → provide tar command explanation
- "Fix the permissions on my SSH keys" → chmod 600 ~/.ssh/*

Created by: orpheus497
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of user intent."""

    # Action intents (user wants to DO something)
    ACTION_FILE = "action_file"  # File operations
    ACTION_PROCESS = "action_process"  # Process management
    ACTION_NETWORK = "action_network"  # Network operations
    ACTION_SYSTEM = "action_system"  # System administration
    ACTION_GIT = "action_git"  # Git operations
    ACTION_PACKAGE = "action_package"  # Package management
    ACTION_SEARCH = "action_search"  # Search/find operations
    ACTION_TEXT = "action_text"  # Text processing
    ACTION_PERMISSION = "action_permission"  # Permission changes
    ACTION_COMPRESS = "action_compress"  # Compression/archiving

    # Question intents (user wants to LEARN something)
    QUESTION_HOW = "question_how"  # How to do something
    QUESTION_WHAT = "question_what"  # What is something
    QUESTION_WHERE = "question_where"  # Where to find something
    QUESTION_WHY = "question_why"  # Why something happens
    QUESTION_EXPLAIN = "question_explain"  # Explain a command

    # Status intents (user wants to CHECK something)
    STATUS_CHECK = "status_check"  # Check status
    STATUS_LIST = "status_list"  # List items
    STATUS_COMPARE = "status_compare"  # Compare items

    # Fix intents (user encountered an ERROR)
    FIX_ERROR = "fix_error"  # Fix an error
    FIX_PERMISSION = "fix_permission"  # Permission denied
    FIX_NOT_FOUND = "fix_not_found"  # Command/file not found
    FIX_CONNECTION = "fix_connection"  # Connection error

    # Unknown
    UNKNOWN = "unknown"


class Urgency(Enum):
    """Urgency level of the request."""

    LOW = "low"  # Normal operation
    MEDIUM = "medium"  # Important but not critical
    HIGH = "high"  # Urgent
    CRITICAL = "critical"  # Emergency/disaster recovery


@dataclass
class Intent:
    """Classified intent with metadata."""

    type: IntentType
    confidence: float  # 0.0 - 1.0
    urgency: Urgency
    keywords: List[str]
    entities: Dict[str, str]  # Extracted entities (files, directories, etc.)
    suggested_commands: List[str]
    needs_decomposition: bool = False
    decomposed_steps: Optional[List[str]] = None


class IntentClassifier:
    """
    Natural language intent classifier.

    Analyzes user queries to understand intent and provide appropriate responses:
    - Classifies intent type (action, question, status, fix)
    - Extracts entities (files, directories, commands)
    - Suggests command sequences
    - Decomposes complex requests
    - Detects urgency level

    Example usage:
        classifier = IntentClassifier()

        # Simple action
        intent = classifier.classify("list all Python files")
        # → ACTION_SEARCH, commands: ["find . -name '*.py'", "ls *.py"]

        # Complex decomposition
        intent = classifier.classify("find Python files and count lines")
        # → ACTION_SEARCH + ACTION_TEXT, decompose into steps

        # Question
        intent = classifier.classify("how do I compress a directory?")
        # → QUESTION_HOW, provide tar/zip explanation

        # Fix error
        intent = classifier.classify("permission denied when accessing /etc/hosts")
        # → FIX_PERMISSION, suggest sudo or chmod
    """

    def __init__(self) -> None:
        """Initialize the intent classifier."""
        self._build_patterns()

    def _build_patterns(self) -> None:
        """Build regex patterns for intent classification."""
        # Action patterns
        self.action_patterns = {
            IntentType.ACTION_FILE: [
                r"\b(?:create|make|touch|remove|delete|rm|move|mv|copy|cp|rename)\b.*\b(?:file|directory|folder)\b",
                r"\b(?:file|directory|folder)\b.*\b(?:create|make|remove|delete|move|copy|rename)\b",
            ],
            IntentType.ACTION_PROCESS: [
                r"\b(?:kill|stop|start|restart|terminate)\b.*\b(?:process|service|daemon)\b",
                r"\b(?:process|service|daemon)\b.*\b(?:kill|stop|start|restart)\b",
            ],
            IntentType.ACTION_NETWORK: [
                r"\b(?:ping|curl|wget|download|upload|fetch|connect|ssh|scp)\b",
                r"\b(?:network|connection|port|socket|http|https|ftp)\b",
            ],
            IntentType.ACTION_GIT: [
                r"\b(?:git|commit|push|pull|clone|branch|merge|rebase|checkout)\b",
                r"\b(?:repository|repo|remote|origin)\b.*\b(?:git|version\s+control)\b",
            ],
            IntentType.ACTION_PACKAGE: [
                r"\b(?:install|uninstall|update|upgrade|remove)\b.*\b(?:package|library|module|dependency)\b",
                r"\b(?:pip|npm|yarn|cargo|apt|yum|brew|pacman)\b",
            ],
            IntentType.ACTION_SEARCH: [
                r"\b(?:find|search|locate|grep|look\s+for|filter)\b",
                r"\b(?:all|every)\b.*\b(?:file|directory|folder)\b.*\b(?:with|containing|matching)\b",
            ],
            IntentType.ACTION_TEXT: [
                r"\b(?:count|wc|lines|words|characters)\b",
                r"\b(?:replace|substitute|sed|awk|change)\b.*\b(?:text|string|word)\b",
            ],
            IntentType.ACTION_PERMISSION: [
                r"\b(?:chmod|chown|permission|owner|group)\b",
                r"\b(?:change|set|fix)\b.*\b(?:permission|owner)\b",
            ],
            IntentType.ACTION_COMPRESS: [
                r"\b(?:compress|zip|tar|gzip|archive|extract|unzip|decompress)\b",
                r"\b(?:create|make)\b.*\b(?:archive|tarball|zip)\b",
            ],
        }

        # Question patterns
        self.question_patterns = {
            IntentType.QUESTION_HOW: [
                r"^how\s+(?:do\s+i|to|can\s+i)",
                r"\bhow\b.*\b(?:do|use|run|execute)\b",
            ],
            IntentType.QUESTION_WHAT: [
                r"^what\s+(?:is|are|does)",
                r"\bwhat\b.*\b(?:command|tool|program)\b",
            ],
            IntentType.QUESTION_WHERE: [
                r"^where\s+(?:is|are|can\s+i\s+find)",
                r"\bwhere\b.*\b(?:located|stored|saved)\b",
            ],
            IntentType.QUESTION_EXPLAIN: [
                r"\b(?:explain|describe|tell\s+me\s+about|what\s+does)\b",
                r"\bmean(?:ing)?\s+of\b",
            ],
        }

        # Status patterns
        self.status_patterns = {
            IntentType.STATUS_CHECK: [
                r"\b(?:check|verify|test|status|state)\b",
                r"\bis\b.*\b(?:running|working|active|enabled)\b",
            ],
            IntentType.STATUS_LIST: [
                r"\b(?:list|show|display|print)\s+(?:all|every|the)?\b",
                r"\bwhat\s+(?:are|is)\s+(?:all|the)?\b",
            ],
        }

        # Fix patterns
        self.fix_patterns = {
            IntentType.FIX_ERROR: [
                r"\b(?:fix|solve|resolve|repair)\b.*\b(?:error|issue|problem)\b",
                r"\b(?:error|issue|problem)\b.*\b(?:fix|solve|resolve)\b",
            ],
            IntentType.FIX_PERMISSION: [
                r"\bpermission\s+denied\b",
                r"\baccess\s+denied\b",
                r"\bforbidden\b.*\b(?:access|permission)\b",
            ],
            IntentType.FIX_NOT_FOUND: [
                r"\b(?:command|file|directory)\s+not\s+found\b",
                r"\bno\s+such\s+(?:file|directory|command)\b",
            ],
            IntentType.FIX_CONNECTION: [
                r"\bconnection\s+(?:refused|failed|timeout|reset)\b",
                r"\bcannot\s+connect\b",
            ],
        }

        # Urgency keywords
        self.urgency_keywords = {
            Urgency.CRITICAL: ["emergency", "urgent", "critical", "immediately", "asap", "disaster", "broken", "down"],
            Urgency.HIGH: ["important", "soon", "quick", "quickly", "fast", "now", "failing"],
            Urgency.MEDIUM: ["should", "need", "want", "would like"],
            Urgency.LOW: ["maybe", "possibly", "eventually", "sometime", "when you can"],
        }

    def classify(self, query: str) -> Intent:
        """
        Classify user intent from natural language query.

        Args:
            query: Natural language query string

        Returns:
            Intent object with classification and metadata
        """
        query_lower = query.lower().strip()

        # Extract entities
        entities = self._extract_entities(query)

        # Classify intent type
        intent_type, confidence = self._classify_type(query_lower)

        # Detect urgency
        urgency = self._detect_urgency(query_lower)

        # Extract keywords
        keywords = self._extract_keywords(query_lower)

        # Check if needs decomposition
        needs_decomposition = self._needs_decomposition(query_lower)

        # Generate suggested commands
        suggested_commands = self._generate_commands(intent_type, query, entities)

        # Decompose if needed
        decomposed_steps = None
        if needs_decomposition:
            decomposed_steps = self._decompose_query(query, entities)

        return Intent(
            type=intent_type,
            confidence=confidence,
            urgency=urgency,
            keywords=keywords,
            entities=entities,
            suggested_commands=suggested_commands,
            needs_decomposition=needs_decomposition,
            decomposed_steps=decomposed_steps,
        )

    def _classify_type(self, query: str) -> Tuple[IntentType, float]:
        """
        Classify the intent type.

        Args:
            query: Query string (lowercase)

        Returns:
            Tuple of (IntentType, confidence)
        """
        max_confidence = 0.0
        best_intent = IntentType.UNKNOWN

        # Check all pattern categories
        all_patterns = [
            (self.action_patterns, 0.9),
            (self.question_patterns, 0.85),
            (self.status_patterns, 0.8),
            (self.fix_patterns, 0.95),  # High confidence for fix intents
        ]

        for patterns, base_confidence in all_patterns:
            for intent_type, pattern_list in patterns.items():
                for pattern in pattern_list:
                    if re.search(pattern, query, re.IGNORECASE):
                        # Calculate confidence based on pattern match
                        confidence = base_confidence

                        # Boost confidence if multiple patterns match
                        matches = sum(
                            1
                            for p in pattern_list
                            if re.search(p, query, re.IGNORECASE)
                        )
                        confidence = min(1.0, confidence + (matches - 1) * 0.05)

                        if confidence > max_confidence:
                            max_confidence = confidence
                            best_intent = intent_type

        # Default to ACTION_SEARCH if no clear pattern matches
        if best_intent == IntentType.UNKNOWN and max_confidence < 0.3:
            # Check for common action words
            action_words = ["show", "get", "give", "tell"]
            if any(word in query for word in action_words):
                return (IntentType.STATUS_LIST, 0.5)

        return (best_intent, max_confidence)

    def _extract_entities(self, query: str) -> Dict[str, str]:
        """
        Extract entities from query (files, directories, commands, etc.).

        Args:
            query: Query string

        Returns:
            Dictionary of extracted entities
        """
        entities = {}

        # Extract file patterns
        file_patterns = re.findall(r'\b\w+\.\w+\b|["\']([^"\']+\.\w+)["\']', query)
        if file_patterns:
            entities["files"] = [f for f in file_patterns if f]

        # Extract directory paths
        dir_patterns = re.findall(r'(?:/[\w\-./]+|~/[\w\-./]*|\./[\w\-./]+)', query)
        if dir_patterns:
            entities["directories"] = dir_patterns

        # Extract commands (words after specific verbs)
        command_pattern = re.findall(r'(?:run|execute|use)\s+(\w+)', query, re.IGNORECASE)
        if command_pattern:
            entities["commands"] = command_pattern

        # Extract file extensions
        ext_pattern = re.findall(r'\b(\w+)\s+files?\b', query, re.IGNORECASE)
        if ext_pattern:
            entities["extensions"] = ext_pattern

        # Extract numbers (could be PIDs, ports, counts, etc.)
        numbers = re.findall(r'\b\d+\b', query)
        if numbers:
            entities["numbers"] = numbers

        return entities

    def _detect_urgency(self, query: str) -> Urgency:
        """
        Detect urgency level from query.

        Args:
            query: Query string (lowercase)

        Returns:
            Urgency level
        """
        for urgency_level, keywords in self.urgency_keywords.items():
            if any(keyword in query for keyword in keywords):
                return urgency_level

        # Default to LOW urgency
        return Urgency.LOW

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from query.

        Args:
            query: Query string (lowercase)

        Returns:
            List of keywords
        """
        # Remove common stop words
        stop_words = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "i", "you", "he", "she", "it",
            "we", "they", "to", "of", "in", "on", "at", "for", "with", "from", "by",
        }

        # Extract words
        words = re.findall(r'\b\w+\b', query)

        # Filter stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords[:10]  # Limit to 10 keywords

    def _needs_decomposition(self, query: str) -> bool:
        """
        Check if query needs decomposition into multiple steps.

        Args:
            query: Query string (lowercase)

        Returns:
            True if needs decomposition
        """
        # Patterns indicating complex multi-step operations
        decomposition_indicators = [
            r'\band\s+(?:then|also|additionally)\b',
            r'\b(?:first|then|next|after\s+that|finally)\b',
            r'\bpipe\b|\|\|?',
            r'\b(?:count|filter|sort|group)\b.*\b(?:and|then)\b',
        ]

        for pattern in decomposition_indicators:
            if re.search(pattern, query, re.IGNORECASE):
                return True

        # Check for multiple action verbs
        action_verbs = ["find", "list", "count", "show", "filter", "sort", "group", "delete", "copy", "move"]
        verb_count = sum(1 for verb in action_verbs if verb in query)

        return verb_count >= 2

    def _decompose_query(self, query: str, entities: Dict[str, str]) -> List[str]:
        """
        Decompose complex query into steps.

        Args:
            query: Original query string
            entities: Extracted entities

        Returns:
            List of decomposed steps
        """
        steps = []
        query_lower = query.lower()

        # Common decomposition patterns
        if "find" in query_lower and "count" in query_lower:
            steps.append("Find matching files")
            steps.append("Count the results")

        elif "search" in query_lower and "delete" in query_lower:
            steps.append("Search for matching items")
            steps.append("Review the results")
            steps.append("Delete the items")

        elif "list" in query_lower and "sort" in query_lower:
            steps.append("List the items")
            steps.append("Sort the results")

        # Generic decomposition based on conjunctions
        elif " and " in query_lower or " then " in query_lower:
            parts = re.split(r'\s+(?:and|then)\s+', query_lower)
            steps = [part.strip().capitalize() for part in parts if part.strip()]

        # Fallback: split on common conjunctions
        if not steps:
            conjunctions = [" and then ", " and ", " then "]
            for conj in conjunctions:
                if conj in query_lower:
                    steps = [part.strip().capitalize() for part in query_lower.split(conj)]
                    break

        return steps if steps else ["Execute the operation"]

    def _generate_commands(
        self, intent_type: IntentType, query: str, entities: Dict[str, str]
    ) -> List[str]:
        """
        Generate suggested commands based on intent.

        Args:
            intent_type: Classified intent type
            query: Original query
            entities: Extracted entities

        Returns:
            List of suggested commands
        """
        commands = []

        # File operations
        if intent_type == IntentType.ACTION_FILE:
            if "create" in query.lower() or "make" in query.lower():
                if "directory" in query.lower() or "folder" in query.lower():
                    commands.append("mkdir directory_name")
                else:
                    commands.append("touch file_name")
            elif "delete" in query.lower() or "remove" in query.lower():
                commands.append("rm file_name")
                commands.append("rm -r directory_name")
            elif "copy" in query.lower():
                commands.append("cp source destination")

        # Search operations
        elif intent_type == IntentType.ACTION_SEARCH:
            extensions = entities.get("extensions", [])
            if extensions:
                ext = extensions[0]
                commands.append(f"find . -name '*.{ext}'")
                commands.append(f"ls **/*.{ext}")
                commands.append(f"grep -r 'pattern' --include='*.{ext}'")
            else:
                commands.append("find . -name 'pattern'")
                commands.append("grep -r 'pattern' .")

        # Git operations
        elif intent_type == IntentType.ACTION_GIT:
            if "commit" in query.lower():
                commands.append("git add .")
                commands.append("git commit -m 'message'")
            elif "push" in query.lower():
                commands.append("git push")
                commands.append("git push origin branch_name")
            elif "clone" in query.lower():
                commands.append("git clone <repository-url>")

        # Permission fixes
        elif intent_type == IntentType.FIX_PERMISSION:
            if "ssh" in query.lower():
                commands.append("chmod 600 ~/.ssh/id_rsa")
                commands.append("chmod 644 ~/.ssh/id_rsa.pub")
                commands.append("chmod 700 ~/.ssh")
            else:
                commands.append("sudo command")
                commands.append("chmod +x file_name")

        # Text processing
        elif intent_type == IntentType.ACTION_TEXT:
            if "count" in query.lower():
                if "lines" in query.lower():
                    commands.append("wc -l file")
                elif "words" in query.lower():
                    commands.append("wc -w file")
                else:
                    commands.append("wc file")

        # Compression
        elif intent_type == IntentType.ACTION_COMPRESS:
            if "compress" in query.lower() or "create" in query.lower():
                commands.append("tar -czf archive.tar.gz directory/")
                commands.append("zip -r archive.zip directory/")
            elif "extract" in query.lower() or "decompress" in query.lower():
                commands.append("tar -xzf archive.tar.gz")
                commands.append("unzip archive.zip")

        return commands[:5]  # Limit to 5 suggestions
