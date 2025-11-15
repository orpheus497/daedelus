"""
Interactive REPL mode for Daedelus.

Provides an enhanced REPL with:
- Real-time syntax highlighting
- AI-powered intent classification
- Command suggestions and history
- Natural language understanding

Created by: orpheus497
"""

import logging
import os
import subprocess
import time
import uuid
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from pygments.lexer import RegexLexer, bygroups, include
from pygments.lexers.shell import BashLexer
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Text
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from daedelus.core.intent_classifier import Intent, IntentClassifier, IntentResult
from daedelus.daemon.ipc import IPCClient
from daedelus.utils.fuzzy import get_matcher
from daedelus.utils.os_detection import get_os_detector

logger = logging.getLogger(__name__)


class DaedelusLexer(RegexLexer):
    """
    Custom lexer for Daedelus REPL with syntax highlighting for:
    - REPL commands (/help, /search, etc.)
    - Shell commands (bash/zsh/fish)
    - Natural language (detected)
    - File paths
    """

    name = "Daedelus"
    aliases = ["daedelus"]

    tokens = {
        "root": [
            # REPL commands (/, followed by command name)
            (
                r"^(/)(help|search|explain|generate|write-script|read|write|stats|recent|quit|exit|q)\b",
                bygroups(Operator, Keyword.Namespace),
            ),
            # Common shell commands
            (
                r"\b(ls|cd|pwd|cat|grep|find|git|docker|kubectl|npm|pip|python|cargo|make|ssh|scp|rsync|tar|curl|wget)\b",
                Keyword,
            ),
            # Pipes and redirects
            (r"[|><&;]", Operator),
            # Options/flags
            (r"--?[\w-]+", Name.Attribute),
            # Paths (starting with / or ./ or ~/)
            (r"(/|\.{1,2}/)[\w/.-]+", String),
            # Quoted strings
            (r'"[^"]*"', String.Double),
            (r"'[^']*'", String.Single),
            # Numbers
            (r"\b\d+\b", Number),
            # Everything else
            (r"\s+", Text),
            (r".", Text),
        ],
    }


class DaedelusCompleter(Completer):
    """
    Command completer using Daedelus history and fuzzy matching.
    """

    def __init__(self, ipc_client: IPCClient) -> None:
        """
        Initialize completer.

        Args:
            ipc_client: IPC client for communicating with daemon
        """
        self.ipc_client = ipc_client
        self.fuzzy = get_matcher(threshold=50)

    def get_completions(self, document: Any, complete_event: Any) -> Any:
        """
        Get command completions based on current input.

        Args:
            document: Current document
            complete_event: Completion event

        Yields:
            Completion objects
        """
        text = document.text_before_cursor.strip()

        if not text:
            # Show recent commands when no input
            try:
                response = self.ipc_client.send_request("search", {"query": "", "limit": 10})
                if response.get("status") == "ok":
                    commands = response.get("results", [])
                    for cmd in commands:
                        yield Completion(
                            cmd,
                            start_position=-len(text),
                            display_meta="recent",
                        )
            except Exception:
                pass
        else:
            # Use fuzzy matching for suggestions
            try:
                response = self.ipc_client.send_request("search", {"query": "", "limit": 100})
                if response.get("status") == "ok":
                    all_commands = response.get("results", [])
                    matches = self.fuzzy.best_match(text, all_commands, limit=10)

                    for cmd, score in matches:
                        yield Completion(
                            cmd,
                            start_position=-len(text),
                            display_meta=f"score: {score}",
                        )
            except Exception:
                pass


class DaedelusREPL:
    """
    Enhanced REPL for Daedelus with syntax highlighting and fuzzy search.
    """

    def __init__(self, ipc_client: IPCClient) -> None:
        """
        Initialize REPL.

        Args:
            ipc_client: IPC client for communicating with daemon
        """
        self.ipc_client = ipc_client
        self.console = Console()
        self.fuzzy = get_matcher()
        self.session_id = str(uuid.uuid4())
        self.current_dir = os.getcwd()  # Track current directory
        self.os_detector = get_os_detector()  # OS detection for system-specific commands
        self.intent_classifier = IntentClassifier()  # AI intent classification

        # Create custom key bindings
        self.kb = KeyBindings()

        @self.kb.add("c-d")  # Ctrl+D to exit
        def _(event: Any) -> None:
            # Raise EOFError to exit gracefully
            raise EOFError()

        @self.kb.add("c-c")  # Ctrl+C to clear input
        def _(event: Any) -> None:
            event.current_buffer.reset()

        # Create prompt session with auto-suggestions and real-time syntax highlighting
        self.session: PromptSession[str] = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            completer=DaedelusCompleter(ipc_client),
            complete_style=CompleteStyle.MULTI_COLUMN,
            key_bindings=self.kb,
            lexer=PygmentsLexer(DaedelusLexer),  # Real-time syntax highlighting
            style=Style.from_dict(
                {
                    "prompt": "ansicyan bold",
                    # Syntax highlighting colors (Pygments tokens)
                    "pygments.keyword": "ansibrightgreen bold",  # Shell commands
                    "pygments.keyword.namespace": "ansibrightmagenta bold",  # REPL commands
                    "pygments.operator": "ansibrightcyan",  # Pipes, redirects
                    "pygments.name.attribute": "ansiyellow",  # Flags/options
                    "pygments.string": "ansibrightblue",  # Paths and strings
                    "pygments.number": "ansimagenta",  # Numbers
                    "pygments.comment": "ansibrightblack italic",  # Comments
                    # Completion menu
                    "completion-menu.completion": "bg:#008888 #ffffff",
                    "completion-menu.completion.current": "bg:#00aaaa #000000",
                    "scrollbar.background": "bg:#88aaaa",
                    "scrollbar.button": "bg:#222222",
                    # Auto-suggestions
                    "auto-suggestion": "#666666",
                }
            ),
        )

    def print_welcome(self) -> None:
        """Print welcome message."""
        welcome = """
# 🧠 Daedelus Interactive Shell

**Welcome to Daedelus** - Your self-learning AI terminal assistant
*Type `daedelus` or `deus` to start | 100% offline & privacy-first*

## 🎨 Features Always Active
- ✅ **Real-time syntax highlighting** - Commands colored as you type
- ✅ **Auto-completion** - Tab to complete from history
- ✅ **Fuzzy search** - Find commands with partial matches
- ✅ **AI suggestions** - Intelligent command recommendations
- ✅ **History navigation** - ↑/↓ arrows through your history
- ✅ **The Redbook** - Complete terminal mastery guide built-in

## 📋 REPL Commands
- `/help` - Show this help message
- `/search <query>` - Fuzzy search command history
- `/redbook <query>` - Search The Redbook knowledge base
- `/redbook` - Show Redbook information
- `/explain <command>` - AI explanation of any command
- `/generate <description>` - Generate command from natural language
- `/write-script <description>` - Create executable script from description
- `/read <file>` - Read and analyze file contents
- `/write <file>` - Write content to file with AI assistance
- `/stats` - Usage statistics and analytics
- `/recent [n]` - Show recent commands (default: 20)
- `/quit`, `/exit`, `/q` - Exit REPL

## 📖 The Redbook Integration
Daedelus includes **The Redbook** - a comprehensive terminal mastery guide by orpheus497
covering Linux commands, system administration, security, and more.

**Search examples:**
```bash
/redbook package management      # Find package management chapters
/redbook how to configure SSH    # Search for SSH configuration
/redbook systemd services        # Learn about service management
```

## 🤖 AI Capabilities
The AI can interpret natural language and:
- **Generate commands** from plain English descriptions
- **Write scripts** (7 languages: bash, python, js, perl, ruby, go, php)
- **Read/analyze documents** and provide insights
- **Execute complex workflows** by chaining commands
- **Build tools** dynamically as needed (8 templates available)
- **Learn continuously** from your usage patterns
- **Access The Redbook** for authoritative Linux guidance

**Examples:**
```bash
/generate find all python files larger than 1MB
/write-script backup my home directory to external drive
/explain tar -xzf archive.tar.gz
/redbook how to set up firewall
Tell me what's in the config file  # Natural language
Create a script to monitor CPU usage  # Natural language
```

## ⌨️ Keyboard Shortcuts
- `Tab` - Auto-complete from history
- `↑/↓` - Navigate command history  
- `Ctrl+C` - Clear current line
- `Ctrl+D` - Exit REPL

## 🚀 External Commands
Run from your regular terminal:
- `daedelus` or `deus` - Start REPL (default)
- `daedelus start` - Start background daemon
- `daedelus stop` - Stop daemon
- `daedelus status` - Check system status
- `daedelus ingest document <file>` - Add training data
- `daedelus training stats` - View training data statistics
- `daedelus dashboard` - Launch TUI dashboard
- `daedelus setup` - Configuration wizard

*Note: Full command reference: `daedelus --help` | Quick: `deus --help`*
        """
        self.console.print(
            Panel(Markdown(welcome), title="🧠 Daedelus Interactive REPL", border_style="cyan")
        )

    def handle_command(self, text: str | None) -> bool:
        """
        Handle REPL command with AI-powered intent classification.

        Args:
            text: Command text (can be None if prompt was interrupted)

        Returns:
            True to continue, False to exit
        """
        if text is None:
            return True

        text = text.strip()

        if not text:
            return True

        # Classify intent using AI
        intent_result = self.intent_classifier.classify(
            text, context={"cwd": self.current_dir}
        )

        # Handle based on classified intent
        if intent_result.intent == Intent.REPL_COMMAND:
            # REPL commands always get priority
            return self._handle_repl_command(text)

        elif intent_result.intent == Intent.EXECUTE:
            # High confidence - execute as shell command
            if intent_result.confidence >= 0.7:
                self._execute_command(text)
            else:
                # Low confidence - ask for confirmation
                prompt = self.intent_classifier.get_prompt_for_ambiguous(intent_result)
                if prompt:
                    self.console.print(prompt)
                    self.console.print(
                        f"\n[dim]Press Enter to execute, or type a different command:[/dim]"
                    )
                self._execute_command(text)

        elif intent_result.intent == Intent.GENERATE:
            # Generate command from natural language
            self._generate_command(text)

        elif intent_result.intent == Intent.WRITE_SCRIPT:
            # Create executable script
            self._write_script(text)

        elif intent_result.intent == Intent.READ_FILE:
            # Extract file path and read
            file_path = text.split()[-1]  # Simplistic - get last word
            self._read_file(file_path)

        elif intent_result.intent == Intent.WRITE_FILE:
            # Extract file path and write
            file_path = text.split()[-1]
            self._write_file(file_path)

        elif intent_result.intent == Intent.QUESTION:
            # Answer as Q&A
            self._handle_natural_language(text)

        elif intent_result.intent == Intent.UNKNOWN:
            # Low confidence - show options and default to execute
            prompt = self.intent_classifier.get_prompt_for_ambiguous(intent_result)
            if prompt:
                self.console.print(f"[yellow]{prompt}[/yellow]")
                self.console.print(
                    f"\n[dim]Defaulting to execution. Type /help for REPL commands.[/dim]"
                )
            self._execute_command(text)

        else:
            # Fallback - execute as command
            self._execute_command(text)

        return True

    def _handle_repl_command(self, text: str) -> bool:
        """
        Handle REPL-specific commands.

        Args:
            text: REPL command text

        Returns:
            True to continue, False to exit
        """
        # Handle special commands
        if text in ["/quit", "/exit", "/q"]:
            self.console.print("[cyan]Goodbye! 👋[/cyan]")
            return False

        elif text == "/help":
            self.print_welcome()

        elif text == "/stats":
            self._show_stats()

        elif text == "/recent":
            self._show_recent()

        elif text.startswith("/search "):
            query = text[8:].strip()
            self._fuzzy_search(query)

        elif text.startswith("/redbook "):
            query = text[9:].strip()
            self._search_redbook(query)

        elif text == "/redbook":
            self._show_redbook_info()

        elif text.startswith("/explain "):
            command = text[9:].strip()
            self._explain_command(command)

        elif text.startswith("/generate "):
            description = text[10:].strip()
            self._generate_command(description)

        elif text.startswith("/write-script "):
            description = text[14:].strip()
            self._write_script(description)

        elif text.startswith("/read "):
            file_path = text[6:].strip()
            self._read_file(file_path)

        elif text.startswith("/write "):
            file_path = text[7:].strip()
            self._write_file(file_path)

        else:
            self.console.print(f"[yellow]Unknown REPL command: {text}[/yellow]")
            self.console.print("[dim]Type /help for available commands[/dim]")

        return True

    def _execute_command(self, command: str) -> None:
        """
        Execute shell command and log to daemon.

        Args:
            command: Shell command to execute
        """
        # Handle cd command specially to change REPL's working directory
        stripped_cmd = command.strip()
        if stripped_cmd == "cd" or stripped_cmd.startswith("cd "):
            self._handle_cd_command(command)
            return

        # Display the command with syntax highlighting
        self.console.print("[dim]→[/dim] ", end="")
        self.console.print(Syntax(command, "bash", theme="monokai", background_color="default"))

        # Execute the command
        start_time = time.time()
        try:
            # Use shell=True to handle pipes, redirects, etc.
            result = subprocess.run(
                command,
                shell=True,
                capture_output=False,  # Show output in real-time
                text=True,
                cwd=self.current_dir,  # Use tracked directory
            )
            exit_code = result.returncode
            duration = time.time() - start_time

            # Log to daemon
            try:
                self.ipc_client.log_command(
                    command=command,
                    exit_code=exit_code,
                    duration=duration,
                    cwd=self.current_dir,
                    session_id=self.session_id,
                )
            except Exception as e:
                logger.debug(f"Failed to log command: {e}")

            # Show status
            if exit_code == 0:
                self.console.print(f"[dim green]✓ Exit code: {exit_code}[/dim green]")
            else:
                self.console.print(f"[dim red]✗ Exit code: {exit_code}[/dim red]")

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Command interrupted[/yellow]")
            duration = time.time() - start_time
            # Log interrupted command
            try:
                self.ipc_client.log_command(
                    command=command,
                    exit_code=130,  # Standard exit code for SIGINT
                    duration=duration,
                    cwd=self.current_dir,
                    session_id=self.session_id,
                )
            except Exception as e:
                logger.debug(f"Failed to log interrupted command: {e}")

        except Exception as e:
            self.console.print(f"[red]Error executing command: {e}[/red]")
            duration = time.time() - start_time
            # Log failed command
            try:
                self.ipc_client.log_command(
                    command=command,
                    exit_code=1,
                    duration=duration,
                    cwd=self.current_dir,
                    session_id=self.session_id,
                )
            except Exception as e:
                logger.debug(f"Failed to log failed command: {e}")

        # Show suggestions after command execution
        self._show_suggestion(command)

    def _handle_cd_command(self, command: str) -> None:
        """
        Handle cd command to change working directory.

        Args:
            command: cd command to execute
        """
        # Parse the cd command
        parts = command.strip().split(maxsplit=1)
        if len(parts) == 1:
            # cd with no argument goes to home
            target_dir = os.path.expanduser("~")
        else:
            target_dir = os.path.expanduser(parts[1])

        # Change directory
        try:
            # Resolve relative to current directory
            if not os.path.isabs(target_dir):
                target_dir = os.path.join(self.current_dir, target_dir)
            
            # Normalize the path
            target_dir = os.path.normpath(target_dir)
            
            # Change directory
            os.chdir(target_dir)
            self.current_dir = target_dir
            
            self.console.print(f"[dim green]→ {self.current_dir}[/dim green]")
            
            # Log to daemon
            try:
                self.ipc_client.log_command(
                    command=command,
                    exit_code=0,
                    duration=0.0,
                    cwd=self.current_dir,
                    session_id=self.session_id,
                )
            except Exception as e:
                logger.debug(f"Failed to log cd command: {e}")
                
        except FileNotFoundError:
            self.console.print(f"[red]cd: {parts[1] if len(parts) > 1 else '~'}: No such file or directory[/red]")
        except PermissionError:
            self.console.print(f"[red]cd: {parts[1] if len(parts) > 1 else '~'}: Permission denied[/red]")
        except Exception as e:
            self.console.print(f"[red]cd: {e}[/red]")

    def _show_stats(self) -> None:
        """Show command usage statistics."""
        try:
            response = self.ipc_client.send_request("get_stats", {})
            if response.get("status") == "ok":
                # Stats are at top level of response
                stats = response

                table = Table(title="Daedelus Statistics", show_header=False)
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("Total Commands", str(stats.get("total_commands", 0)))
                table.add_row("Unique Commands", str(stats.get("unique_commands", 0)))
                table.add_row("Success Rate", f"{stats.get('success_rate', 0):.1f}%")
                table.add_row("Most Used", stats.get("most_used", "N/A"))

                self.console.print(table)
        except Exception as e:
            self.console.print(f"[red]Error getting stats: {e}[/red]")

    def _show_recent(self) -> None:
        """Show recent commands."""
        try:
            response = self.ipc_client.send_request("search", {"query": "", "limit": 20})
            if response.get("status") == "ok":
                commands = response.get("results", [])

                if commands:
                    self.console.print("\n[cyan]Recent Commands:[/cyan]")
                    for i, cmd in enumerate(commands, 1):
                        self.console.print(f"{i:2d}. [green]{cmd}[/green]")
                else:
                    self.console.print("[dim]No recent commands[/dim]")
        except Exception as e:
            self.console.print(f"[red]Error getting recent commands: {e}[/red]")

    def _fuzzy_search(self, query: str) -> None:
        """
        Fuzzy search command history.

        Args:
            query: Search query
        """
        try:
            response = self.ipc_client.send_request("search", {"query": "", "limit": 500})
            if response.get("status") == "ok":
                commands = response.get("results", [])
                matches = self.fuzzy.best_match(query, commands, limit=10)

                if matches:
                    self.console.print(f"\n[cyan]Search results for '{query}':[/cyan]")
                    for cmd, score in matches:
                        self.console.print(f"[dim]{score:3d}%[/dim] [green]{cmd}[/green]")
                else:
                    self.console.print(f"[dim]No matches for '{query}'[/dim]")
        except Exception as e:
            self.console.print(f"[red]Error searching: {e}[/red]")

    def _explain_command(self, command: str) -> None:
        """
        Explain a command using LLM.

        Args:
            command: Command to explain
        """
        try:
            response = self.ipc_client.send_request("explain_command", {"command": command})
            if response.get("status") == "ok":
                explanation = response.get("explanation", "")
                self.console.print(
                    Panel(Markdown(explanation), title="Explanation", border_style="green")
                )
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[red]Error: {error}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error explaining command: {e}[/red]")

    def _generate_command(self, description: str) -> None:
        """
        Generate command from description.

        Args:
            description: Natural language description
        """
        try:
            response = self.ipc_client.send_request(
                "generate_command", {"description": description}
            )
            if response.get("status") == "ok":
                command = response.get("command", "")
                self.console.print("\n[cyan]Generated command:[/cyan]")
                self.console.print(f"[green]{command}[/green]\n")
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[red]Error: {error}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error generating command: {e}[/red]")

    def _show_suggestion(self, command: str) -> None:
        """
        Show AI suggestion for command.

        Args:
            command: Command to get suggestion for
        """
        try:
            response = self.ipc_client.send_request("suggest", {"partial": command})
            if response.get("status") == "ok":
                suggestions = response.get("suggestions", [])
                if suggestions:
                    self.console.print("\n[cyan]Suggestions:[/cyan]")
                    for i, sugg in enumerate(suggestions[:5], 1):
                        cmd = sugg.get("command", "")
                        score = sugg.get("score", 0)
                        self.console.print(f"{i}. [dim]{score:.2f}[/dim] [green]{cmd}[/green]")
        except Exception:
            pass  # Silently ignore suggestion errors

    def _write_script(self, description: str) -> None:
        """
        Write a script based on natural language description.

        Args:
            description: What the script should do
        """
        try:
            self.console.print(f"[cyan]🔧 Creating script:[/cyan] {description}")
            response = self.ipc_client.send_request(
                "write_script", {"description": description, "cwd": self.current_dir}
            )
            if response.get("status") == "ok":
                script_path = response.get("script_path", "")
                script_content = response.get("script_content", "")
                language = response.get("language", "bash")
                
                self.console.print(f"\n[green]✅ Script created:[/green] {script_path}")
                self.console.print(f"\n[cyan]Script content:[/cyan]")
                self.console.print(Syntax(script_content, language, theme="monokai", line_numbers=True))
                
                # Ask if user wants to execute
                self.console.print("\n[yellow]Execute this script? (y/N):[/yellow]", end=" ")
                import sys
                response_input = sys.stdin.readline().strip().lower()
                if response_input == 'y':
                    self._execute_command(f"bash {script_path}")
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[red]Error: {error}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error writing script: {e}[/red]")

    def _read_file(self, file_path: str) -> None:
        """
        Read and analyze file with AI.

        Args:
            file_path: Path to file to read
        """
        try:
            import os
            full_path = os.path.join(self.current_dir, file_path) if not os.path.isabs(file_path) else file_path
            
            if not os.path.exists(full_path):
                self.console.print(f"[red]File not found:[/red] {file_path}")
                return
                
            self.console.print(f"[cyan]📖 Reading file:[/cyan] {file_path}")
            response = self.ipc_client.send_request(
                "read_file", {"file_path": full_path, "analyze": True}
            )
            if response.get("status") == "ok":
                content = response.get("content", "")
                analysis = response.get("analysis", "")
                file_type = response.get("file_type", "text")
                
                # Show file content
                self.console.print(f"\n[cyan]Content:[/cyan]")
                self.console.print(Syntax(content[:2000], file_type, theme="monokai", line_numbers=True))
                if len(content) > 2000:
                    self.console.print("[dim]... (content truncated)[/dim]")
                
                # Show AI analysis
                if analysis:
                    self.console.print(f"\n[cyan]AI Analysis:[/cyan]")
                    self.console.print(Panel(Markdown(analysis), border_style="green"))
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[red]Error: {error}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error reading file: {e}[/red]")

    def _write_file(self, file_path: str) -> None:
        """
        Write content to file with AI assistance.

        Args:
            file_path: Path to file to write
        """
        try:
            self.console.print(f"[cyan]📝 What should I write to {file_path}?[/cyan]")
            self.console.print("[dim]Describe the content or paste it directly:[/dim]")
            
            import sys
            content_description = sys.stdin.readline().strip()
            
            if not content_description:
                self.console.print("[yellow]Cancelled[/yellow]")
                return
                
            response = self.ipc_client.send_request(
                "write_file", 
                {
                    "file_path": file_path, 
                    "description": content_description,
                    "cwd": self.current_dir
                }
            )
            if response.get("status") == "ok":
                written_path = response.get("file_path", file_path)
                self.console.print(f"[green]✅ File written:[/green] {written_path}")
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[red]Error: {error}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error writing file: {e}[/red]")

    def _is_natural_language(self, text: str) -> bool:
        """
        Detect if input is natural language vs shell command.

        Args:
            text: User input

        Returns:
            True if likely natural language
        """
        # Natural language indicators
        nl_indicators = [
            "tell me", "show me", "what is", "how do i", "how to",
            "can you", "could you", "would you", "please",
            "i want", "i need", "help me", "explain",
            "create a", "make a", "write a", "build a",
            "find out", "check if", "list all",
            "i am using", "i'm using", "i have", "i'm",
            "what's the", "whats the", "which command"
        ]
        
        text_lower = text.lower()
        
        # Check for natural language indicators
        if any(indicator in text_lower for indicator in nl_indicators):
            return True
            
        # Check if it starts with common question words or conversational starters
        first_words = text_lower.split()
        if first_words and first_words[0] in ["what", "how", "why", "when", "where", "who", "which", "i"]:
            return True
            
        # If it contains only words and spaces (no shell syntax)
        import re
        if re.match(r'^[a-zA-Z\s,\']+$', text) and len(text.split()) > 3:
            return True
            
        return False

    def _handle_natural_language(self, text: str) -> None:
        """
        Handle natural language input with AI interpretation.

        Args:
            text: Natural language input
        """
        try:
            # Check for OS-specific package manager questions
            text_lower = text.lower()
            if any(word in text_lower for word in ["update", "upgrade", "install", "package"]):
                if any(word in text_lower for word in ["fedora", "debian", "ubuntu", "command", "what", "which"]):
                    self._handle_os_package_question(text)
                    return
            
            self.console.print(f"[dim]🤖 Interpreting:[/dim] {text}")
            response = self.ipc_client.send_request(
                "interpret_natural_language",
                {
                    "text": text,
                    "cwd": self.current_dir,
                    "session_id": self.session_id
                }
            )
            
            if response.get("status") == "ok":
                intent = response.get("intent", "")
                action = response.get("action", "")
                commands = response.get("commands", [])
                explanation = response.get("explanation", "")
                
                if explanation:
                    self.console.print(f"\n[cyan]Understanding:[/cyan] {explanation}")
                
                if commands:
                    self.console.print(f"\n[cyan]Suggested commands:[/cyan]")
                    for i, cmd in enumerate(commands, 1):
                        self.console.print(f"{i}. [green]{cmd}[/green]")
                    
                    # Execute first command automatically if high confidence
                    if action == "execute" and len(commands) > 0:
                        self.console.print(f"\n[yellow]Execute command 1? (Y/n):[/yellow]", end=" ")
                        import sys
                        response_input = sys.stdin.readline().strip().lower()
                        if response_input in ['', 'y', 'yes']:
                            self._execute_command(commands[0])
                elif action:
                    self.console.print(f"[yellow]Action:[/yellow] {action}")
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[yellow]I'm not sure how to help with that. Try a command or /help[/yellow]")
                logger.debug(f"Natural language interpretation error: {error}")
                
        except Exception as e:
            self.console.print(f"[yellow]I'm not sure how to help with that. Try a command or /help[/yellow]")
            logger.debug(f"Error handling natural language: {e}")
    
    def _handle_os_package_question(self, text: str) -> None:
        """
        Handle OS-specific package manager questions.

        Args:
            text: Natural language question about package management
        """
        os_info = self.os_detector.get_os_info()
        text_lower = text.lower()
        
        self.console.print(f"\n[cyan]System Information:[/cyan]")
        self.console.print(f"  OS: [green]{os_info.distribution or os_info.os_type.value}[/green]")
        self.console.print(f"  Package Manager: [green]{os_info.package_manager.value}[/green]")
        self.console.print()
        
        if "update" in text_lower or "upgrade" in text_lower:
            cmd = self.os_detector.get_update_command()
            self.console.print(f"[cyan]To update your system:[/cyan]")
            self.console.print(f"  [green]{cmd}[/green]")
            self.console.print()
            
            self.console.print(f"[yellow]Execute this command? (y/N):[/yellow]", end=" ")
            import sys
            response_input = sys.stdin.readline().strip().lower()
            if response_input == 'y':
                self._execute_command(cmd)
        
        elif "install" in text_lower:
            # Extract package name if mentioned
            words = text.split()
            package = None
            for i, word in enumerate(words):
                if word.lower() == "install" and i + 1 < len(words):
                    package = words[i + 1]
                    break
            
            if package:
                cmd = self.os_detector.get_install_command(package)
                self.console.print(f"[cyan]To install {package}:[/cyan]")
                self.console.print(f"  [green]{cmd}[/green]")
            else:
                self.console.print(f"[cyan]Package install command format:[/cyan]")
                self.console.print(f"  [green]{self.os_detector.get_install_command('<package_name>')}[/green]")
                self.console.print()
                self.console.print(f"[dim]Example: {self.os_detector.get_install_command('python3-pip')}[/dim]")
        
        else:
            self.console.print(f"[cyan]Common commands for {os_info.package_manager.value}:[/cyan]")
            self.console.print(f"  Update system: [green]{self.os_detector.get_update_command()}[/green]")
            self.console.print(f"  Install package: [green]{self.os_detector.get_install_command('<package>')}[/green]")
            self.console.print(f"  Search packages: [green]{self.os_detector.get_search_command('<query>')}[/green]")

    def get_status_bar(self) -> str:
        """Get status bar text with system info."""
        try:
            # Get daemon status
            response = self.ipc_client.call_with_timeout("daemon_status", timeout=1.0)
            if response and response.get("success"):
                status = response.get("status", {})
                commands_logged = status.get("total_commands", 0)
                uptime_seconds = status.get("uptime_seconds", 0)
                uptime_str = self._format_uptime(uptime_seconds)
                
                return f"✓ Daemon: UP | Uptime: {uptime_str} | Commands: {commands_logged}"
            else:
                return "✗ Daemon: DOWN"
        except Exception:
            return "✗ Daemon: UNREACHABLE"

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human-readable format."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d {hours}h"

    def print_status_bar(self) -> None:
        """Print status bar at top of terminal."""
        status = self.get_status_bar()
        self.console.print(f"[dim]{status}[/dim]")

    def run(self) -> None:
        """Run the REPL loop."""
        self.print_welcome()
        
        # Print initial status bar
        self.print_status_bar()
        self.console.print()  # Empty line

        while True:
            try:
                # Enhanced prompt with current directory and emoji
                cwd_short = self._shorten_path(self.current_dir)
                prompt_text = HTML(f"<ansicyan><b>💡 deus</b></ansicyan>:<ansigreen>{cwd_short}</ansigreen>❯ ")
                text = self.session.prompt(prompt_text)

                # Handle command
                if not self.handle_command(text):
                    break

            except KeyboardInterrupt:
                continue
            except EOFError:
                self.console.print("\n[cyan]Goodbye! 👋[/cyan]")
                break
            except Exception as e:
                logger.error(f"REPL error: {e}", exc_info=True)
                self.console.print(f"[red]Error: {e}[/red]")

    def _shorten_path(self, path: str, max_len: int = 40) -> str:
        """Shorten path for display."""
        if len(path) <= max_len:
            return path
        
        # Replace home with ~
        home = os.path.expanduser("~")
        if path.startswith(home):
            path = "~" + path[len(home):]
        
        # If still too long, show ...
        if len(path) > max_len:
            parts = path.split(os.sep)
            if len(parts) > 3:
                return os.sep.join([parts[0], "...", parts[-1]])
        
        return path

    def _search_redbook(self, query: str) -> None:
        """
        Search The Redbook knowledge base.
        
        Args:
            query: Search query
        """
        try:
            response = self.ipc_client.send_request("search_knowledge_base", {"query": query})
            
            if response and response.get("status") == "ok":
                explanation = response.get("explanation", "No results found")
                self.console.print(f"\n[cyan]The Redbook Search Results:[/cyan]\n")
                self.console.print(Markdown(explanation))
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[yellow]Unable to search knowledge base: {error}[/yellow]")
        except Exception as e:
            logger.error(f"Error searching redbook: {e}")
            self.console.print(f"[red]Error: {e}[/red]")

    def _show_redbook_info(self) -> None:
        """Show information about The Redbook knowledge base."""
        try:
            response = self.ipc_client.send_request("knowledge_summary", {})
            
            if response and response.get("status") == "ok":
                explanation = response.get("explanation", "Knowledge base info not available")
                self.console.print(f"\n[cyan]The Redbook Knowledge Base:[/cyan]\n")
                self.console.print(Markdown(explanation))
            else:
                error = response.get("error", "Unknown error")
                self.console.print(f"[yellow]Unable to get knowledge base info: {error}[/yellow]")
        except Exception as e:
            logger.error(f"Error getting redbook info: {e}")
            self.console.print(f"[red]Error: {e}[/red]")


def start_repl(ipc_client: IPCClient) -> None:
    """
    Start interactive REPL.

    Args:
        ipc_client: IPC client for daemon communication
    """
    repl = DaedelusREPL(ipc_client)
    repl.run()
