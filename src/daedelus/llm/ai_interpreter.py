"""
AI Interpreter for Natural Language Understanding.

Interprets user's natural language and converts it to actionable commands,
scripts, or responses. This is the core AI brain that understands intent
and generates appropriate actions.

Created by: orpheus497
"""

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from daedelus.llm.command_generator import CommandGenerator
from daedelus.llm.intent_classifier import IntentClassifier, IntentType
from daedelus.llm.llm_manager import LLMManager
from daedelus.utils.os_detection import get_os_detector, get_update_command, get_install_command

logger = logging.getLogger(__name__)


@dataclass
class InterpretationResult:
    """Result of natural language interpretation."""

    intent: str
    action: str  # "execute", "inform", "create", "read", "write"
    commands: list[str]
    explanation: str
    confidence: float
    script_path: str | None = None
    script_content: str | None = None
    file_content: str | None = None


class AIInterpreter:
    """
    AI-powered natural language interpreter.

    Understands user intent from natural language and generates appropriate
    responses: commands, scripts, file operations, or informational responses.
    """

    def __init__(
        self,
        llm: LLMManager,
        intent_classifier: IntentClassifier | None = None,
        command_generator: CommandGenerator | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        """
        Initialize AI interpreter.

        Args:
            llm: LLM manager
            intent_classifier: Intent classifier (created if None)
            command_generator: Command generator (created if None)
            cache_dir: Directory for caching interpretations
        """
        self.llm = llm
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.command_generator = command_generator or CommandGenerator(llm)
        self.cache_dir = cache_dir
        self.os_detector = get_os_detector()
        
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
        logger.info(f"AIInterpreter initialized (OS: {self.os_detector.get_os_info().os_type.value})")

    def interpret(
        self,
        text: str,
        cwd: str | None = None,
        history: list[str] | None = None,
        session_id: str | None = None,
    ) -> InterpretationResult:
        """
        Interpret natural language input.

        Args:
            text: User's natural language input
            cwd: Current working directory
            history: Recent command history
            session_id: Session identifier

        Returns:
            InterpretationResult with action to take
        """
        if not text.strip():
            return InterpretationResult(
                intent="empty",
                action="inform",
                commands=[],
                explanation="Please provide input",
                confidence=0.0,
            )

        # Classify intent
        intent = self.intent_classifier.classify(text)
        
        logger.debug(f"Classified intent: {intent.type.value} (confidence: {intent.confidence})")

        # Handle based on intent type
        if intent.type in [IntentType.ACTION_FILE, IntentType.ACTION_SEARCH, 
                          IntentType.ACTION_SYSTEM, IntentType.ACTION_GIT]:
            return self._handle_action_intent(text, intent, cwd, history)
        
        elif intent.type in [IntentType.QUESTION_HOW, IntentType.QUESTION_WHAT,
                            IntentType.QUESTION_EXPLAIN]:
            return self._handle_question_intent(text, intent, cwd)
        
        elif intent.type in [IntentType.FIX_ERROR, IntentType.FIX_PERMISSION]:
            return self._handle_fix_intent(text, intent, cwd, history)
        
        else:
            # General interpretation
            return self._handle_general_intent(text, cwd, history)

    def _handle_action_intent(
        self, text: str, intent: Any, cwd: str | None, history: list[str] | None
    ) -> InterpretationResult:
        """Handle action-type intents."""
        # Check for system update commands
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in ["update", "upgrade"]) and any(
            phrase in text_lower for phrase in ["system", "os", "packages", "my os"]
        ):
            update_cmd = get_update_command()
            return InterpretationResult(
                intent="system_update",
                action="execute",
                commands=[update_cmd],
                explanation=f"To update your system packages, run: {update_cmd}",
                confidence=0.95,
            )
        
        # Check for package installation
        if "install" in text_lower and "package" in text_lower:
            # Extract package name if possible
            words = text_lower.split()
            if "install" in words:
                idx = words.index("install")
                if idx + 1 < len(words):
                    package = words[idx + 1]
                    install_cmd = get_install_command(package)
                    return InterpretationResult(
                        intent="package_install",
                        action="execute",
                        commands=[install_cmd],
                        explanation=f"To install {package}, run: {install_cmd}",
                        confidence=0.9,
                    )
        
        # Generate command(s)
        commands = []
        
        if intent.needs_decomposition and intent.decomposed_steps:
            # Multi-step action
            for step in intent.decomposed_steps:
                cmd = self.command_generator.generate_command(step, cwd=cwd, history=history)
                if cmd:
                    commands.append(cmd)
        else:
            # Single command
            cmd = self.command_generator.generate_command(text, cwd=cwd, history=history)
            if cmd:
                commands.append(cmd)
        
        # Fallback to intent-based commands if LLM fails
        if not commands and intent.suggested_commands:
            commands = intent.suggested_commands[:3]

        explanation = self._generate_explanation(text, commands, intent)

        return InterpretationResult(
            intent=intent.type.value,
            action="execute",
            commands=commands,
            explanation=explanation,
            confidence=intent.confidence,
        )

    def _handle_question_intent(
        self, text: str, intent: Any, cwd: str | None
    ) -> InterpretationResult:
        """Handle question-type intents."""
        # Generate explanation
        explanation = self._answer_question(text, intent)
        
        # Also suggest relevant commands if applicable
        commands = []
        if intent.suggested_commands:
            commands = intent.suggested_commands

        return InterpretationResult(
            intent=intent.type.value,
            action="inform",
            commands=commands,
            explanation=explanation,
            confidence=intent.confidence,
        )

    def _handle_fix_intent(
        self, text: str, intent: Any, cwd: str | None, history: list[str] | None
    ) -> InterpretationResult:
        """Handle fix/error intents."""
        # Analyze the error and suggest fixes
        commands = self._generate_fix_commands(text, intent, cwd, history)
        explanation = f"To fix this issue, try:\n" + "\n".join(f"- {cmd}" for cmd in commands)

        return InterpretationResult(
            intent=intent.type.value,
            action="execute",
            commands=commands,
            explanation=explanation,
            confidence=intent.confidence,
        )

    def _handle_general_intent(
        self, text: str, cwd: str | None, history: list[str] | None
    ) -> InterpretationResult:
        """Handle general/unknown intents."""
        # Try to generate a command anyway
        cmd = self.command_generator.generate_command(text, cwd=cwd, history=history)
        
        if cmd:
            return InterpretationResult(
                intent="general",
                action="execute",
                commands=[cmd],
                explanation=f"I interpreted this as: {cmd}",
                confidence=0.5,
            )
        else:
            return InterpretationResult(
                intent="unknown",
                action="inform",
                commands=[],
                explanation="I'm not sure how to help with that. Try rephrasing or use /help",
                confidence=0.0,
            )

    def write_script(
        self,
        description: str,
        cwd: str | None = None,
        output_name: str | None = None,
    ) -> InterpretationResult:
        """
        Generate a script from description.

        Args:
            description: What the script should do
            cwd: Current working directory
            output_name: Optional script name

        Returns:
            InterpretationResult with script details
        """
        # Determine script language
        language = self._detect_script_language(description)
        
        # Generate script content
        script_content = self._generate_script_content(description, language)
        
        # Determine output path
        if not output_name:
            import time
            timestamp = int(time.time())
            output_name = f"script_{timestamp}.{self._get_extension(language)}"
        
        script_path = Path(cwd or os.getcwd()) / output_name
        
        # Write script
        try:
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make executable
            os.chmod(script_path, 0o755)
            
            return InterpretationResult(
                intent="write_script",
                action="create",
                commands=[f"bash {script_path}"] if language == "bash" else [f"python {script_path}"],
                explanation=f"Created {language} script: {script_path}",
                confidence=0.8,
                script_path=str(script_path),
                script_content=script_content,
            )
        except Exception as e:
            logger.error(f"Error writing script: {e}")
            return InterpretationResult(
                intent="write_script",
                action="inform",
                commands=[],
                explanation=f"Error creating script: {e}",
                confidence=0.0,
            )

    def read_file(self, file_path: str, analyze: bool = True) -> InterpretationResult:
        """
        Read and optionally analyze a file.

        Args:
            file_path: Path to file
            analyze: Whether to provide AI analysis

        Returns:
            InterpretationResult with file content and analysis
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            analysis = ""
            if analyze:
                analysis = self._analyze_file_content(content, file_path)
            
            return InterpretationResult(
                intent="read_file",
                action="inform",
                commands=[],
                explanation=analysis if analyze else "File read successfully",
                confidence=1.0,
                file_content=content,
            )
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return InterpretationResult(
                intent="read_file",
                action="inform",
                commands=[],
                explanation=f"Error reading file: {e}",
                confidence=0.0,
            )

    def write_file(
        self, file_path: str, description: str, cwd: str | None = None
    ) -> InterpretationResult:
        """
        Write content to file based on description.

        Args:
            file_path: Path to file
            description: Description of what to write or content itself
            cwd: Current working directory

        Returns:
            InterpretationResult
        """
        # Determine if description is actual content or needs generation
        content = self._generate_file_content(description, file_path)
        
        full_path = Path(cwd or os.getcwd()) / file_path if not os.path.isabs(file_path) else Path(file_path)
        
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            
            return InterpretationResult(
                intent="write_file",
                action="create",
                commands=[],
                explanation=f"File written successfully: {full_path}",
                confidence=1.0,
            )
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return InterpretationResult(
                intent="write_file",
                action="inform",
                commands=[],
                explanation=f"Error writing file: {e}",
                confidence=0.0,
            )

    def _detect_script_language(self, description: str) -> str:
        """Detect script language from description."""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ["python", "py", "pip", "import"]):
            return "python"
        elif any(word in desc_lower for word in ["bash", "sh", "shell"]):
            return "bash"
        elif any(word in desc_lower for word in ["javascript", "js", "node"]):
            return "javascript"
        else:
            return "bash"  # Default

    def _get_extension(self, language: str) -> str:
        """Get file extension for language."""
        extensions = {
            "python": "py",
            "bash": "sh",
            "javascript": "js",
        }
        return extensions.get(language, "sh")

    def _generate_script_content(self, description: str, language: str) -> str:
        """Generate script content using LLM."""
        prompt = f"""Generate a {language} script that does the following:
{description}

Requirements:
- Include appropriate shebang line
- Add error handling
- Add comments explaining key sections
- Make it production-ready
- Follow best practices

Generate only the script code, no explanations:"""

        try:
            script = self.llm.generate(
                prompt,
                max_tokens=1000,
                temperature=0.2,
                stop=["```", "<|end|>"],
            )
            
            # Add shebang if not present
            if language == "bash" and not script.startswith("#!"):
                script = "#!/bin/bash\n\n" + script
            elif language == "python" and not script.startswith("#!"):
                script = "#!/usr/bin/env python3\n\n" + script
            
            return script.strip()
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            # Return basic template
            if language == "bash":
                return f"#!/bin/bash\n\n# {description}\n\necho 'TODO: Implement script'\n"
            else:
                return f"#!/usr/bin/env python3\n\n# {description}\n\nprint('TODO: Implement script')\n"

    def _generate_file_content(self, description: str, file_path: str) -> str:
        """Generate file content from description."""
        # If description looks like actual content, use it directly
        if len(description) > 100 or "\n" in description:
            return description
        
        # Otherwise generate content with LLM
        file_ext = Path(file_path).suffix
        
        prompt = f"""Generate content for a file ({file_path}) with the following purpose:
{description}

File type: {file_ext or 'text'}

Generate appropriate content. Do not include explanations, only the file content:"""

        try:
            content = self.llm.generate(
                prompt,
                max_tokens=800,
                temperature=0.3,
            )
            return content.strip()
        except Exception as e:
            logger.error(f"Error generating file content: {e}")
            return f"# {description}\n\n"

    def _analyze_file_content(self, content: str, file_path: str) -> str:
        """Analyze file content with AI."""
        file_ext = Path(file_path).suffix
        
        # Truncate content if too long
        content_sample = content[:2000] if len(content) > 2000 else content
        
        prompt = f"""Analyze this file ({file_path}):

```
{content_sample}
```

Provide a concise analysis:
- What is this file?
- Key components or sections
- Any notable patterns or issues
- Suggestions (if applicable)

Keep response under 200 words:"""

        try:
            analysis = self.llm.generate(
                prompt,
                max_tokens=300,
                temperature=0.4,
            )
            return analysis.strip()
        except Exception as e:
            logger.error(f"Error analyzing file: {e}")
            return "Unable to analyze file content"

    def _generate_explanation(self, text: str, commands: list[str], intent: Any) -> str:
        """Generate explanation for interpreted action."""
        if not commands:
            return "No commands generated"
        
        if len(commands) == 1:
            return f"I'll execute: {commands[0]}"
        else:
            steps = "\n".join(f"{i}. {cmd}" for i, cmd in enumerate(commands, 1))
            return f"I'll execute these steps:\n{steps}"

    def _answer_question(self, text: str, intent: Any) -> str:
        """Answer a question using LLM."""
        prompt = f"""Answer this question concisely (under 150 words):

{text}

Provide a helpful answer focusing on practical usage:"""

        try:
            answer = self.llm.generate(
                prompt,
                max_tokens=250,
                temperature=0.5,
            )
            return answer.strip()
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return "I don't have enough information to answer that question."

    def _generate_fix_commands(
        self, text: str, intent: Any, cwd: str | None, history: list[str] | None
    ) -> list[str]:
        """Generate commands to fix an issue."""
        if intent.suggested_commands:
            return intent.suggested_commands
        
        # Use LLM to suggest fixes
        prompt = f"""Suggest commands to fix this issue:

{text}

Provide 1-3 shell commands that could solve this. One per line, no explanations:"""

        try:
            response = self.llm.generate(
                prompt,
                max_tokens=150,
                temperature=0.3,
            )
            # Parse commands
            commands = [line.strip() for line in response.strip().split('\n') if line.strip()]
            return commands[:3]  # Max 3 commands
        except Exception as e:
            logger.error(f"Error generating fix commands: {e}")
            return []
