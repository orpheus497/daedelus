"""
Command templates and snippets system for Daedelus.

Allows users to create reusable command templates with variable substitution.

Created by: orpheus497
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Import with graceful degradation
try:
    from jinja2 import Environment, Template, TemplateSyntaxError
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    logger.warning("jinja2 not available - template rendering will use simple substitution")


@dataclass
class CommandTemplate:
    """A reusable command template."""

    name: str  # Template name (unique identifier)
    pattern: str  # Template pattern with variables (e.g., "git clone {{repo}}")
    description: str  # Human-readable description
    variables: List[str]  # List of variable names
    category: str  # Category (git, docker, system, etc.)
    examples: List[str]  # Example usage
    created: str  # Creation timestamp


class TemplateManager:
    """
    Manages command templates with variable substitution.

    Features:
    - Jinja2-style templates ({{variable}})
    - Variable detection and validation
    - Template storage and retrieval
    - Auto-discovery of templateable commands
    - Built-in template library
    """

    # Built-in templates
    BUILTIN_TEMPLATES = [
        CommandTemplate(
            name="git-clone",
            pattern="git clone {{repo}} {{dir}}",
            description="Clone a git repository",
            variables=["repo", "dir"],
            category="git",
            examples=["git clone https://github.com/user/repo.git myrepo"],
            created="",
        ),
        CommandTemplate(
            name="git-commit",
            pattern="git commit -m '{{message}}'",
            description="Commit with message",
            variables=["message"],
            category="git",
            examples=["git commit -m 'Add new feature'"],
            created="",
        ),
        CommandTemplate(
            name="docker-run",
            pattern="docker run {{flags}} {{image}} {{command}}",
            description="Run a docker container",
            variables=["flags", "image", "command"],
            category="docker",
            examples=["docker run -it --rm ubuntu /bin/bash"],
            created="",
        ),
        CommandTemplate(
            name="find-files",
            pattern="find {{path}} -name '{{pattern}}' {{action}}",
            description="Find files matching pattern",
            variables=["path", "pattern", "action"],
            category="system",
            examples=["find . -name '*.py' -type f"],
            created="",
        ),
        CommandTemplate(
            name="tar-create",
            pattern="tar -czf {{archive}}.tar.gz {{files}}",
            description="Create compressed tar archive",
            variables=["archive", "files"],
            category="system",
            examples=["tar -czf backup.tar.gz /path/to/files"],
            created="",
        ),
        CommandTemplate(
            name="ssh-tunnel",
            pattern="ssh -L {{local_port}}:localhost:{{remote_port}} {{user}}@{{host}}",
            description="Create SSH tunnel",
            variables=["local_port", "remote_port", "user", "host"],
            category="network",
            examples=["ssh -L 8080:localhost:80 user@server.com"],
            created="",
        ),
    ]

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        """
        Initialize template manager.

        Args:
            storage_path: Path to template storage file (JSON)
        """
        self.storage_path = storage_path
        self.templates: Dict[str, CommandTemplate] = {}

        # Load built-in templates
        for template in self.BUILTIN_TEMPLATES:
            self.templates[template.name] = template

        # Load user templates
        if storage_path and storage_path.exists():
            self._load_templates()

        logger.info(f"Template manager initialized with {len(self.templates)} templates")

    def _load_templates(self) -> None:
        """Load templates from storage file."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            for name, template_data in data.items():
                self.templates[name] = CommandTemplate(**template_data)

            logger.info(f"Loaded {len(data)} user templates")

        except Exception as e:
            logger.error(f"Failed to load templates: {e}")

    def _save_templates(self) -> None:
        """Save templates to storage file."""
        if not self.storage_path:
            return

        # Only save user templates (not built-ins)
        builtin_names = {t.name for t in self.BUILTIN_TEMPLATES}
        user_templates = {
            name: asdict(template)
            for name, template in self.templates.items()
            if name not in builtin_names
        }

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump(user_templates, f, indent=2)

            logger.debug(f"Saved {len(user_templates)} user templates")

        except Exception as e:
            logger.error(f"Failed to save templates: {e}")

    def add_template(
        self,
        name: str,
        pattern: str,
        description: str,
        category: str = "custom",
        examples: Optional[List[str]] = None,
    ) -> CommandTemplate:
        """
        Add a new template.

        Args:
            name: Template name (must be unique)
            pattern: Template pattern with {{variables}}
            description: Description of template
            category: Category name
            examples: Optional example commands

        Returns:
            Created CommandTemplate

        Raises:
            ValueError: If template name already exists
        """
        if name in self.templates:
            raise ValueError(f"Template '{name}' already exists")

        # Extract variables from pattern
        variables = self._extract_variables(pattern)

        template = CommandTemplate(
            name=name,
            pattern=pattern,
            description=description,
            variables=variables,
            category=category,
            examples=examples or [],
            created=str(datetime.now()),
        )

        self.templates[name] = template
        self._save_templates()

        logger.info(f"Added template: {name}")
        return template

    def _extract_variables(self, pattern: str) -> List[str]:
        """Extract variable names from template pattern."""
        # Match {{variable}} or {variable}
        matches = re.findall(r'\{\{?\s*(\w+)\s*\}\}?', pattern)
        return list(dict.fromkeys(matches))  # Remove duplicates, preserve order

    def render_template(
        self,
        name: str,
        variables: Dict[str, str],
        allow_missing: bool = False,
    ) -> str:
        """
        Render a template with variable substitution.

        Args:
            name: Template name
            variables: Dictionary of variable values
            allow_missing: If True, leave unsubstituted variables in output

        Returns:
            Rendered command string

        Raises:
            KeyError: If template not found
            ValueError: If required variables missing (and allow_missing=False)
        """
        if name not in self.templates:
            raise KeyError(f"Template '{name}' not found")

        template = self.templates[name]

        # Check for missing variables
        missing = set(template.variables) - set(variables.keys())
        if missing and not allow_missing:
            raise ValueError(f"Missing required variables: {', '.join(missing)}")

        # Render using Jinja2 if available, otherwise simple substitution
        if JINJA2_AVAILABLE:
            try:
                jinja_template = Template(template.pattern)
                return jinja_template.render(**variables)
            except TemplateSyntaxError as e:
                logger.error(f"Template syntax error: {e}")
                # Fall back to simple substitution

        # Simple substitution fallback
        result = template.pattern
        for var, value in variables.items():
            # Replace both {{var}} and {var}
            result = result.replace(f"{{{{{var}}}}}", value)
            result = result.replace(f"{{{var}}}", value)

        return result

    def list_templates(
        self,
        category: Optional[str] = None,
        include_builtin: bool = True,
    ) -> List[CommandTemplate]:
        """
        List available templates.

        Args:
            category: Optional category filter
            include_builtin: Whether to include built-in templates

        Returns:
            List of CommandTemplate objects
        """
        templates = list(self.templates.values())

        # Filter by category
        if category:
            templates = [t for t in templates if t.category == category]

        # Filter built-ins
        if not include_builtin:
            builtin_names = {t.name for t in self.BUILTIN_TEMPLATES}
            templates = [t for t in templates if t.name not in builtin_names]

        return sorted(templates, key=lambda t: (t.category, t.name))

    def get_template(self, name: str) -> Optional[CommandTemplate]:
        """
        Get a template by name.

        Args:
            name: Template name

        Returns:
            CommandTemplate if found, None otherwise
        """
        return self.templates.get(name)

    def delete_template(self, name: str) -> bool:
        """
        Delete a template.

        Args:
            name: Template name

        Returns:
            True if deleted, False if not found or is built-in

        Raises:
            ValueError: If trying to delete built-in template
        """
        # Prevent deletion of built-ins
        builtin_names = {t.name for t in self.BUILTIN_TEMPLATES}
        if name in builtin_names:
            raise ValueError(f"Cannot delete built-in template '{name}'")

        if name not in self.templates:
            return False

        del self.templates[name]
        self._save_templates()

        logger.info(f"Deleted template: {name}")
        return True

    def discover_templates(
        self,
        commands: List[str],
        min_frequency: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Discover potential templates from command history.

        Analyzes commands for repeated patterns with varying parts.

        Args:
            commands: List of command strings
            min_frequency: Minimum times a pattern must appear

        Returns:
            List of discovered template suggestions

        Example:
            commands = [
                "git commit -m 'Fix bug'",
                "git commit -m 'Add feature'",
                "git commit -m 'Update docs'",
            ]
            # Would suggest: git commit -m '{{message}}'
        """
        # Group commands by base command
        command_groups: Dict[str, List[str]] = {}

        for cmd in commands:
            parts = cmd.split()
            if not parts:
                continue

            base = parts[0]
            if base not in command_groups:
                command_groups[base] = []
            command_groups[base].append(cmd)

        suggestions = []

        # Analyze each group for patterns
        for base, group_commands in command_groups.items():
            if len(group_commands) < min_frequency:
                continue

            # Find common prefix and suffix
            if len(group_commands) >= 2:
                common_prefix = self._find_common_prefix(group_commands)
                if len(common_prefix.split()) >= 2:  # At least 2 words in common
                    # Extract variable part
                    variable_parts = []
                    for cmd in group_commands:
                        if cmd.startswith(common_prefix):
                            var_part = cmd[len(common_prefix):].strip()
                            if var_part:
                                variable_parts.append(var_part)

                    if variable_parts:
                        # Suggest template
                        suggested_pattern = f"{common_prefix}{{{{value}}}}"
                        suggestions.append({
                            "pattern": suggested_pattern,
                            "frequency": len(group_commands),
                            "examples": group_commands[:3],
                            "description": f"Auto-discovered {base} pattern",
                        })

        return sorted(suggestions, key=lambda x: x["frequency"], reverse=True)

    def _find_common_prefix(self, strings: List[str]) -> str:
        """Find common prefix of strings."""
        if not strings:
            return ""

        prefix = strings[0]
        for s in strings[1:]:
            while not s.startswith(prefix):
                prefix = prefix[:-1]
                if not prefix:
                    return ""

        return prefix.strip()

    def get_categories(self) -> List[str]:
        """Get list of all template categories."""
        categories = {t.category for t in self.templates.values()}
        return sorted(categories)


# Convenience functions
from datetime import datetime


if __name__ == "__main__":
    # Test template manager
    manager = TemplateManager()

    print("Command Template Manager Test")
    print("=" * 70)

    print("\nBuilt-in Templates:")
    for template in manager.list_templates():
        print(f"  {template.name} ({template.category})")
        print(f"    Pattern: {template.pattern}")
        print(f"    Variables: {', '.join(template.variables)}")
        print()

    print("\nRendering test:")
    rendered = manager.render_template(
        "git-clone",
        {"repo": "https://github.com/user/repo.git", "dir": "myproject"}
    )
    print(f"  {rendered}")
