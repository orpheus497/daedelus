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
from daedelus.llm.script_templates import ScriptTemplates
from daedelus.llm.knowledge_base import get_knowledge_base
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
        self.knowledge_base = get_knowledge_base()  # Load Redbook knowledge
        
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
        template: str | None = None,
    ) -> InterpretationResult:
        """
        Generate a script from description or template.

        Args:
            description: What the script should do
            cwd: Current working directory
            output_name: Optional script name
            template: Optional template name (e.g., 'backup', 'monitor')

        Returns:
            InterpretationResult with script details
        """
        # Check if using template
        if template or self._is_template_request(description):
            return self._create_from_template(description, cwd, output_name, template)
        
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
                commands=[self._get_run_command(script_path, language)],
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

    def _get_run_command(self, script_path: Path, language: str) -> str:
        """Get command to run script based on language."""
        commands = {
            "bash": f"bash {script_path}",
            "python": f"python3 {script_path}",
            "perl": f"perl {script_path}",
            "ruby": f"ruby {script_path}",
            "php": f"php {script_path}",
            "javascript": f"node {script_path}",
            "go": f"go run {script_path}",
        }
        return commands.get(language, f"./{script_path}")

    def _is_template_request(self, description: str) -> bool:
        """Check if description requests a template."""
        template_keywords = ["backup", "monitor", "deploy", "api", "cron", "log analyzer"]
        desc_lower = description.lower()
        return any(keyword in desc_lower for keyword in template_keywords)

    def _create_from_template(
        self, description: str, cwd: str | None, output_name: str | None, template: str | None
    ) -> InterpretationResult:
        """Create script from template."""
        # Detect template if not specified
        if not template:
            template = self._detect_template(description)
        
        try:
            # Get template parameters from description
            params = self._extract_template_params(description, template)
            
            # Generate script from template
            script_content = ScriptTemplates.get_template(template, **params)
            
            # Determine output path
            if not output_name:
                output_name = f"{template}_script.sh"
            
            script_path = Path(cwd or os.getcwd()) / output_name
            
            # Write script
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make executable
            os.chmod(script_path, 0o755)
            
            return InterpretationResult(
                intent="write_script",
                action="create",
                commands=[f"./{script_path}"],
                explanation=f"Created {template} script: {script_path}",
                confidence=0.9,
                script_path=str(script_path),
                script_content=script_content,
            )
        except Exception as e:
            logger.error(f"Error creating template script: {e}")
            # Fallback to regular generation
            return self.write_script(description, cwd, output_name, template=None)

    def _detect_template(self, description: str) -> str:
        """Detect which template to use from description."""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ["backup", "archive"]):
            return "backup"
        elif any(word in desc_lower for word in ["monitor", "watch", "check system"]):
            return "monitor"
        elif any(word in desc_lower for word in ["deploy", "deployment"]):
            return "deploy"
        elif any(word in desc_lower for word in ["api", "server", "rest"]):
            return "api_server"
        elif any(word in desc_lower for word in ["process data", "csv", "json"]):
            return "data_processor"
        elif any(word in desc_lower for word in ["cron", "scheduled"]):
            return "cron_job"
        elif any(word in desc_lower for word in ["log", "analyze logs"]):
            return "log_analyzer"
        elif any(word in desc_lower for word in ["health", "system check"]):
            return "system_check"
        else:
            return "backup"  # Default

    def _extract_template_params(self, description: str, template: str) -> dict:
        """Extract parameters for template from description."""
        params = {}
        
        if template == "backup":
            # Try to extract source and destination
            if "from" in description.lower():
                parts = description.lower().split("from")[1].split("to")
                if len(parts) >= 2:
                    params["source"] = parts[0].strip()
                    params["dest"] = parts[1].strip()
        elif template == "monitor":
            # Extract interval if specified
            import re
            interval_match = re.search(r"every (\d+) (second|minute|hour)", description.lower())
            if interval_match:
                value = int(interval_match.group(1))
                unit = interval_match.group(2)
                if unit == "minute":
                    params["interval"] = value * 60
                elif unit == "hour":
                    params["interval"] = value * 3600
                else:
                    params["interval"] = value
        elif template == "api_server":
            # Extract language and port
            if "python" in description.lower():
                params["language"] = "python"
            elif "node" in description.lower() or "javascript" in description.lower():
                params["language"] = "node"
            
            port_match = re.search(r"port (\d+)", description.lower())
            if port_match:
                params["port"] = int(port_match.group(1))
        
        return params

    def list_templates(self) -> list[tuple[str, str]]:
        """List available script templates."""
        templates = ScriptTemplates.list_templates()
        return [(name, desc) for name, desc in templates.items()]

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
        
        # Python indicators
        if any(word in desc_lower for word in ["python", "py", "pip", "import", "django", "flask"]):
            return "python"
        # Bash/Shell indicators
        elif any(word in desc_lower for word in ["bash", "sh", "shell", "grep", "awk", "sed"]):
            return "bash"
        # JavaScript/Node.js indicators
        elif any(word in desc_lower for word in ["javascript", "js", "node", "npm", "express"]):
            return "javascript"
        # Perl indicators
        elif any(word in desc_lower for word in ["perl", "cpan"]):
            return "perl"
        # Ruby indicators
        elif any(word in desc_lower for word in ["ruby", "rb", "gem", "rails"]):
            return "ruby"
        # Go indicators
        elif any(word in desc_lower for word in ["go", "golang"]):
            return "go"
        # PHP indicators
        elif any(word in desc_lower for word in ["php"]):
            return "php"
        else:
            # Ask LLM to decide
            return self._llm_detect_language(description)

    def _llm_detect_language(self, description: str) -> str:
        """Use LLM to detect best language for task."""
        prompt = f"""What programming language is best suited for this task?
Task: {description}

Choose from: python, bash, javascript, perl, ruby, go, php

Respond with ONLY the language name, no explanation:"""
        
        try:
            response = self.llm.generate(prompt, max_tokens=10, temperature=0.1).strip().lower()
            # Extract language from response
            for lang in ["python", "bash", "javascript", "perl", "ruby", "go", "php"]:
                if lang in response:
                    return lang
            return "bash"  # Safe default
        except Exception:
            return "bash"  # Fallback

    def _get_extension(self, language: str) -> str:
        """Get file extension for language."""
        extensions = {
            "python": "py",
            "bash": "sh",
            "javascript": "js",
            "perl": "pl",
            "ruby": "rb",
            "go": "go",
            "php": "php",
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
- Follow best practices for {language}

Generate only the script code, no explanations:"""

        try:
            script = self.llm.generate(
                prompt,
                max_tokens=1000,
                temperature=0.2,
                stop=["```", "<|end|>"],
            )
            
            # Add shebang if not present
            script = self._add_shebang(script, language)
            
            # Validate syntax
            if self._validate_script_syntax(script, language):
                return script.strip()
            else:
                logger.warning(f"Script syntax validation failed for {language}")
                return script.strip()  # Still return it, user can fix
                
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return self._get_script_template(description, language)

    def _add_shebang(self, script: str, language: str) -> str:
        """Add appropriate shebang line to script."""
        shebangs = {
            "bash": "#!/bin/bash",
            "python": "#!/usr/bin/env python3",
            "perl": "#!/usr/bin/env perl",
            "ruby": "#!/usr/bin/env ruby",
            "php": "#!/usr/bin/env php",
            "javascript": "#!/usr/bin/env node",
        }
        
        shebang = shebangs.get(language, "#!/bin/bash")
        
        if not script.startswith("#!"):
            return f"{shebang}\n\n{script}"
        return script

    def _validate_script_syntax(self, script: str, language: str) -> bool:
        """Validate script syntax (basic checks)."""
        try:
            if language == "python":
                # Check Python syntax
                import ast
                ast.parse(script)
                return True
            elif language == "bash":
                # Basic bash checks - has shebang and no obvious errors
                return script.startswith("#!") and "#!/bin/" in script
            elif language == "javascript":
                # Check for node shebang or module syntax
                return "#!/usr/bin/env node" in script or "function" in script
            else:
                # Other languages - just check for shebang
                return script.startswith("#!")
        except SyntaxError:
            return False
        except Exception:
            return True  # If we can't validate, assume it's ok

    def _get_script_template(self, description: str, language: str) -> str:
        """Get basic script template for language."""
        templates = {
            "bash": f"""#!/bin/bash
# {description}

set -e  # Exit on error
set -u  # Exit on undefined variable

# TODO: Implement script logic
echo "TODO: Implement script"
""",
            "python": f"""#!/usr/bin/env python3
# {description}

import sys

def main():
    \"\"\"Main function.\"\"\"
    # TODO: Implement script logic
    print("TODO: Implement script")
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
            "javascript": f"""#!/usr/bin/env node
// {description}

'use strict';

function main() {{
    // TODO: Implement script logic
    console.log('TODO: Implement script');
    return 0;
}}

main();
""",
            "perl": f"""#!/usr/bin/env perl
# {description}

use strict;
use warnings;

# TODO: Implement script logic
print "TODO: Implement script\\n";
""",
            "ruby": f"""#!/usr/bin/env ruby
# {description}

# TODO: Implement script logic
puts 'TODO: Implement script'
""",
            "php": f"""#!/usr/bin/env php
<?php
// {description}

// TODO: Implement script logic
echo "TODO: Implement script\\n";
""",
            "go": f"""package main

import "fmt"

// {description}

func main() {{
    // TODO: Implement script logic
    fmt.Println("TODO: Implement script")
}}
""",
        }
        
        return templates.get(language, templates["bash"])

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

    # Enhanced file operations
    
    def batch_read_files(self, file_paths: list[str], analyze: bool = False) -> list[InterpretationResult]:
        """
        Read multiple files at once.
        
        Args:
            file_paths: List of file paths to read
            analyze: Whether to analyze each file
        
        Returns:
            List of InterpretationResults
        """
        results = []
        for file_path in file_paths:
            result = self.read_file(file_path, analyze)
            results.append(result)
        return results

    def batch_write_files(self, file_data: list[tuple[str, str]], cwd: str | None = None) -> list[InterpretationResult]:
        """
        Write multiple files at once.
        
        Args:
            file_data: List of (file_path, description) tuples
            cwd: Current working directory
        
        Returns:
            List of InterpretationResults
        """
        results = []
        for file_path, description in file_data:
            result = self.write_file(file_path, description, cwd)
            results.append(result)
        return results

    def summarize_file(self, file_path: str, max_words: int = 100) -> InterpretationResult:
        """
        Generate a summary of file contents.
        
        Args:
            file_path: Path to file
            max_words: Maximum words in summary
        
        Returns:
            InterpretationResult with summary
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Truncate if too long
            content_sample = content[:5000] if len(content) > 5000 else content
            
            prompt = f"""Summarize this file in {max_words} words or less:

File: {file_path}
Content:
```
{content_sample}
```

Provide a concise summary:"""

            summary = self.llm.generate(
                prompt,
                max_tokens=max_words * 2,
                temperature=0.3,
            )
            
            return InterpretationResult(
                intent="summarize_file",
                action="inform",
                commands=[],
                explanation=summary.strip(),
                confidence=0.9,
                file_content=content,
            )
        except Exception as e:
            logger.error(f"Error summarizing file: {e}")
            return InterpretationResult(
                intent="summarize_file",
                action="inform",
                commands=[],
                explanation=f"Error summarizing file: {e}",
                confidence=0.0,
            )

    def backup_file(self, file_path: str) -> InterpretationResult:
        """
        Create a backup of file before modifying.
        
        Args:
            file_path: Path to file
        
        Returns:
            InterpretationResult with backup path
        """
        import shutil
        from datetime import datetime
        
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return InterpretationResult(
                    intent="backup_file",
                    action="inform",
                    commands=[],
                    explanation=f"File not found: {file_path}",
                    confidence=0.0,
                )
            
            # Create backup with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.parent / f"{file_path.stem}.backup_{timestamp}{file_path.suffix}"
            
            shutil.copy2(file_path, backup_path)
            
            return InterpretationResult(
                intent="backup_file",
                action="create",
                commands=[],
                explanation=f"Backup created: {backup_path}",
                confidence=1.0,
            )
        except Exception as e:
            logger.error(f"Error backing up file: {e}")
            return InterpretationResult(
                intent="backup_file",
                action="inform",
                commands=[],
                explanation=f"Error creating backup: {e}",
                confidence=0.0,
            )

    def detect_file_type(self, file_path: str) -> InterpretationResult:
        """
        Detect file type and provide information.
        
        Args:
            file_path: Path to file
        
        Returns:
            InterpretationResult with file type info
        """
        import mimetypes
        
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return InterpretationResult(
                    intent="detect_file_type",
                    action="inform",
                    commands=[],
                    explanation=f"File not found: {file_path}",
                    confidence=0.0,
                )
            
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            # Get file size
            size = file_path.stat().st_size
            size_str = self._format_file_size(size)
            
            # Get extension
            extension = file_path.suffix
            
            info = f"""File: {file_path.name}
Type: {mime_type or 'Unknown'}
Extension: {extension or 'None'}
Size: {size_str}
Path: {file_path.absolute()}"""
            
            return InterpretationResult(
                intent="detect_file_type",
                action="inform",
                commands=[],
                explanation=info,
                confidence=1.0,
            )
        except Exception as e:
            logger.error(f"Error detecting file type: {e}")
            return InterpretationResult(
                intent="detect_file_type",
                action="inform",
                commands=[],
                explanation=f"Error detecting file type: {e}",
                confidence=0.0,
            )

    def _format_file_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    # Knowledge Base Integration (Redbook)

    def search_knowledge_base(self, query: str) -> InterpretationResult:
        """
        Search The Redbook knowledge base for information.
        
        Args:
            query: Search query
            
        Returns:
            InterpretationResult with search results
        """
        try:
            # Get relevant context from Redbook
            results = self.knowledge_base.get_relevant_context(query, max_results=10)
            
            # Search for specific commands
            command_match = re.search(r'\b([a-z-]+)\b', query.lower())
            if command_match:
                command = command_match.group(1)
                cmd_results = self.knowledge_base.search_command(command)
                if cmd_results:
                    results.extend([r['match'] for r in cmd_results[:3]])
            
            if results:
                explanation = f"Found in The Redbook:\n\n" + "\n".join(f"• {r}" for r in results)
            else:
                explanation = f"No specific results found in The Redbook for '{query}'. Try rephrasing or use /help for available commands."
            
            return InterpretationResult(
                intent="search_knowledge",
                action="inform",
                commands=[],
                explanation=explanation,
                confidence=0.8 if results else 0.3,
            )
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return InterpretationResult(
                intent="search_knowledge",
                action="inform",
                commands=[],
                explanation=f"Error searching knowledge base: {e}",
                confidence=0.0,
            )

    def get_knowledge_summary(self) -> InterpretationResult:
        """
        Get summary of loaded knowledge base.
        
        Returns:
            InterpretationResult with knowledge base info
        """
        try:
            summary = self.knowledge_base.get_summary()
            
            if not summary['loaded']:
                explanation = "The Redbook knowledge base is not loaded."
            else:
                explanation = f"""The Redbook is loaded and available!

**Title**: {summary['title']}
**Author**: {summary['author']}
**Chapters**: {summary['chapters']}
**Sections**: {summary['sections']}
**Size**: {summary['size_kb']} KB
**Path**: {summary['path']}

Use natural language queries to search the Redbook for terminal commands,
system administration tips, and Linux expertise.

Examples:
  - "how to manage services"
  - "show me package management commands"
  - "what's the best way to configure SSH"
"""
            
            return InterpretationResult(
                intent="knowledge_summary",
                action="inform",
                commands=[],
                explanation=explanation,
                confidence=1.0 if summary['loaded'] else 0.5,
            )
        except Exception as e:
            logger.error(f"Error getting knowledge summary: {e}")
            return InterpretationResult(
                intent="knowledge_summary",
                action="inform",
                commands=[],
                explanation=f"Error getting knowledge summary: {e}",
                confidence=0.0,
            )

    def enhance_prompt_with_knowledge(self, user_query: str, base_prompt: str) -> str:
        """
        Enhance LLM prompt with relevant knowledge base context.
        
        Args:
            user_query: User's query
            base_prompt: Base LLM prompt
            
        Returns:
            Enhanced prompt with Redbook context
        """
        # Get relevant context
        context = self.knowledge_base.get_relevant_context(user_query, max_results=3)
        
        if context:
            context_str = "\n".join(f"- {c}" for c in context)
            enhanced = f"""{base_prompt}

Relevant information from The Redbook:
{context_str}

User query: {user_query}

Provide a helpful answer using this context:"""
            return enhanced
        
        return base_prompt
