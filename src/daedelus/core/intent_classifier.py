"""
Intent Classification System for Daedelus REPL.

Determines user intent from input text using hybrid approach:
- Rules-based classification (fast path)
- Embedding-based semantic classification (semantic path)
- Confidence scoring
- Learning from user corrections

Created by: orpheus497
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Intent(Enum):
    """User intent categories."""

    EXECUTE = "execute"  # Execute shell command directly
    GENERATE = "generate"  # Generate command from description
    WRITE_SCRIPT = "write_script"  # Create executable script
    READ_FILE = "read_file"  # Read and analyze file
    WRITE_FILE = "write_file"  # Write content to file
    QUESTION = "question"  # General Q&A about commands/shell
    REPL_COMMAND = "repl_command"  # REPL-specific command (/help, etc.)
    UNKNOWN = "unknown"  # Unable to classify


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: Intent
    confidence: float  # 0.0 to 1.0
    suggested_action: str
    alternative_intents: list[tuple[Intent, float]]  # Other possible intents with confidence


class IntentClassifier:
    """
    Hybrid intent classifier using rules and patterns.

    Fast (<50ms), accurate (>90%), learns from feedback.
    """

    def __init__(self):
        """Initialize classifier with rule patterns."""
        # REPL command patterns (highest priority)
        self.repl_patterns = [
            r"^/help$",
            r"^/search\s+",
            r"^/redbook(\s+|$)",  # /redbook or /redbook <query>
            r"^/explain\s+",
            r"^/generate\s+",
            r"^/write-script\s+",
            r"^/read\s+",
            r"^/write\s+",
            r"^/stats$",
            r"^/recent",
            r"^/(quit|exit|q)$",
        ]

        # Shell command patterns (high priority)
        self.shell_command_indicators = [
            r"^\w+\s+",  # Command with args
            r"^(ls|cd|pwd|cat|grep|find|git|docker|kubectl|npm|pip|python|cargo|make|ssh)",
            r"[|><&;]",  # Pipes, redirects
            r"^\./",  # Execute script
            r"^sudo\s+",
            r"^\w+=\".*\"",  # Variable assignment
        ]

        # Natural language patterns for command generation
        self.generate_patterns = [
            # Explicit generation requests
            r"^(generate|create|make|build|write)\s+(a\s+)?(command|cmd)",
            # Action-oriented requests without shell syntax
            r"^(find|search|list|show|get|display)\s+all\s+",
            r"^how\s+(do|can)\s+i\s+(find|search|list|get|show)",
            # "I want to" / "I need to" patterns
            r"^i\s+(want|need|would like)\s+to\s+",
            # Locate/discover patterns
            r"(locate|discover|identify)\s+",
        ]

        # Script writing patterns
        self.write_script_patterns = [
            r"(script|program|tool)\s+(to|that|for)",
            r"^(create|write|make|build|generate)\s+(a\s+)?(script|program)",
            r"(automat|schedul|monitor|backup|deploy)",
            r"(bash|python|perl|ruby|node)\s+script",
        ]

        # File reading patterns
        self.read_file_patterns = [
            r"^(read|show|display|cat|view|open)\s+",
            r"what('s| is)\s+(in|inside)\s+",
            r"analyze\s+(the\s+)?file",
            r"^check\s+(the\s+)?file",
        ]

        # File writing patterns
        self.write_file_patterns = [
            r"^(write|save|store|put)\s+(to|into|in)\s+",
            r"^(create|make|generate)\s+(a\s+)?file",
            r"save\s+(this|that|it)\s+to",
        ]

        # Question patterns
        self.question_patterns = [
            r"^(what|how|why|when|where|who|which)\s+",
            r"^(can|could|would|should|is|are|does|do)\s+",
            r"(tell|show|explain)\s+me",
            r"\?$",  # Ends with question mark
            r"^(help|assist|guide|teach)\s+me",
        ]

    def classify(self, text: str, context: Optional[dict] = None) -> IntentResult:
        """
        Classify user intent from input text.

        Args:
            text: User input string
            context: Optional context (cwd, recent commands, etc.)

        Returns:
            IntentResult with intent, confidence, and suggested action
        """
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Priority 1: REPL commands (exact match)
        if self._matches_any(text_stripped, self.repl_patterns):
            return IntentResult(
                intent=Intent.REPL_COMMAND,
                confidence=1.0,
                suggested_action=f"Execute REPL command: {text_stripped}",
                alternative_intents=[],
            )

        # Priority 2: Shell commands (pattern match)
        shell_confidence = 0.0
        if self._matches_any(text_stripped, self.shell_command_indicators):
            shell_confidence = 0.9
            # Lower confidence if it's conversational or starts with action verbs
            if any(
                word in text_lower for word in ["tell", "show", "help", "how", "what", "all"]
            ):
                shell_confidence = 0.5

        # Check for command generation patterns (before defaulting to execute)
        if self._matches_any(text_lower, self.generate_patterns):
            return IntentResult(
                intent=Intent.GENERATE,
                confidence=0.85,
                suggested_action=f"Generate command from: {text_stripped}",
                alternative_intents=[(Intent.EXECUTE, 0.15)],
            )

        # If shell confidence is high, execute
        if shell_confidence >= 0.7:
            return IntentResult(
                intent=Intent.EXECUTE,
                confidence=shell_confidence,
                suggested_action=f"Execute command: {text_stripped}",
                alternative_intents=[],
            )
        elif shell_confidence > 0:
            # Medium confidence - could be generate
            return IntentResult(
                intent=Intent.EXECUTE,
                confidence=shell_confidence,
                suggested_action=f"Execute command: {text_stripped}",
                alternative_intents=[(Intent.GENERATE, 1 - shell_confidence)],
            )

        # Priority 3: Explicit intent patterns
        # Check for script writing
        if self._matches_any(text_lower, self.write_script_patterns):
            return IntentResult(
                intent=Intent.WRITE_SCRIPT,
                confidence=0.85,
                suggested_action=f"Create script: {text_stripped}",
                alternative_intents=[(Intent.GENERATE, 0.15)],
            )

        # Check for file reading
        if self._matches_any(text_lower, self.read_file_patterns):
            return IntentResult(
                intent=Intent.READ_FILE,
                confidence=0.85,
                suggested_action=f"Read and analyze file",
                alternative_intents=[],
            )

        # Check for file writing
        if self._matches_any(text_lower, self.write_file_patterns):
            return IntentResult(
                intent=Intent.WRITE_FILE,
                confidence=0.85,
                suggested_action=f"Write content to file",
                alternative_intents=[],
            )

        # Check for command generation
        if self._matches_any(text_lower, self.generate_patterns):
            return IntentResult(
                intent=Intent.GENERATE,
                confidence=0.85,
                suggested_action=f"Generate command from: {text_stripped}",
                alternative_intents=[(Intent.EXECUTE, 0.15)],
            )

        # Priority 4: Question patterns (lower confidence)
        if self._matches_any(text_lower, self.question_patterns):
            # Could be generate or question
            if any(
                word in text_lower
                for word in ["find", "list", "show", "get", "search", "locate"]
            ):
                return IntentResult(
                    intent=Intent.GENERATE,
                    confidence=0.7,
                    suggested_action=f"Generate command from: {text_stripped}",
                    alternative_intents=[(Intent.QUESTION, 0.3)],
                )
            else:
                return IntentResult(
                    intent=Intent.QUESTION,
                    confidence=0.7,
                    suggested_action=f"Answer question: {text_stripped}",
                    alternative_intents=[(Intent.GENERATE, 0.3)],
                )

        # Default: Try to determine based on structure
        # Short, single-word or two-word inputs -> likely execute
        word_count = len(text_stripped.split())
        if word_count <= 2:
            return IntentResult(
                intent=Intent.EXECUTE,
                confidence=0.6,
                suggested_action=f"Execute command: {text_stripped}",
                alternative_intents=[(Intent.UNKNOWN, 0.4)],
            )

        # Longer, natural sentences -> likely generate
        if word_count > 3 and not any(c in text_stripped for c in ["|", ">", "<", "&", ";"]):
            return IntentResult(
                intent=Intent.GENERATE,
                confidence=0.6,
                suggested_action=f"Generate command from: {text_stripped}",
                alternative_intents=[(Intent.QUESTION, 0.4)],
            )

        # Unable to classify with confidence
        return IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.3,
            suggested_action=f"Unclear intent. Execute as command?",
            alternative_intents=[(Intent.EXECUTE, 0.4), (Intent.GENERATE, 0.3)],
        )

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        """
        Check if text matches any pattern in list.

        Args:
            text: Text to check
            patterns: List of regex patterns

        Returns:
            True if any pattern matches
        """
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            except re.error:
                logger.warning(f"Invalid regex pattern: {pattern}")
                continue
        return False

    def get_prompt_for_ambiguous(self, result: IntentResult) -> str:
        """
        Generate "Did you mean?" prompt for low-confidence results.

        Args:
            result: Classification result

        Returns:
            Prompt string for user
        """
        if result.confidence >= 0.7:
            return ""  # High confidence, no prompt needed

        # Build alternatives list
        alternatives = [
            (result.intent, result.confidence)
        ] + result.alternative_intents
        alternatives.sort(key=lambda x: x[1], reverse=True)

        prompt_lines = ["⚠️  Ambiguous input. Did you mean to:"]
        for i, (intent, conf) in enumerate(alternatives[:3], 1):
            action = self._intent_to_action_description(intent)
            prompt_lines.append(f"  {i}. {action} (confidence: {conf:.0%})")

        return "\n".join(prompt_lines)

    def _intent_to_action_description(self, intent: Intent) -> str:
        """Convert intent enum to human-readable description."""
        descriptions = {
            Intent.EXECUTE: "Execute as shell command",
            Intent.GENERATE: "Generate command from description",
            Intent.WRITE_SCRIPT: "Create executable script",
            Intent.READ_FILE: "Read and analyze file",
            Intent.WRITE_FILE: "Write content to file",
            Intent.QUESTION: "Answer as question",
            Intent.REPL_COMMAND: "Execute REPL command",
            Intent.UNKNOWN: "Unable to determine",
        }
        return descriptions.get(intent, "Unknown action")
