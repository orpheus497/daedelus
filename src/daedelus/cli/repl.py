"""
Interactive REPL mode for Daedelus.

Provides a ptpython-like REPL for exploring command history,
getting suggestions, and interacting with the AI assistant.

Created by: orpheus497
"""

import logging
import sys
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from daedelus.daemon.ipc import IPCClient
from daedelus.utils.fuzzy import get_matcher
from daedelus.utils.highlighting import get_highlighter

logger = logging.getLogger(__name__)


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
                response = self.ipc_client.send_request("get_recent_commands", {"n": 10})
                if response.get("status") == "ok":
                    commands = response.get("commands", [])
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
                response = self.ipc_client.send_request("get_recent_commands", {"n": 100})
                if response.get("status") == "ok":
                    all_commands = response.get("commands", [])
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
        self.highlighter = get_highlighter()
        self.fuzzy = get_matcher()

        # Create custom key bindings
        self.kb = KeyBindings()

        @self.kb.add("c-d")  # Ctrl+D to exit
        def _(event: Any) -> None:
            event.app.exit()

        @self.kb.add("c-c")  # Ctrl+C to clear input
        def _(event: Any) -> None:
            event.current_buffer.reset()

        # Create prompt session with auto-suggestions
        self.session: PromptSession[str] = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            completer=DaedelusCompleter(ipc_client),
            complete_style=CompleteStyle.MULTI_COLUMN,
            key_bindings=self.kb,
            style=Style.from_dict(
                {
                    "prompt": "ansicyan bold",
                    "completion-menu.completion": "bg:#008888 #ffffff",
                    "completion-menu.completion.current": "bg:#00aaaa #000000",
                    "scrollbar.background": "bg:#88aaaa",
                    "scrollbar.button": "bg:#222222",
                    "auto-suggestion": "#666666",
                }
            ),
        )

    def print_welcome(self) -> None:
        """Print welcome message."""
        welcome = """
# Daedelus Interactive REPL

Welcome to the Daedelus interactive shell!

**Commands:**
- Type any shell command to see suggestions
- Use Tab for auto-completion
- Use ↑/↓ arrows to navigate history
- `/help` - Show this help
- `/search <query>` - Fuzzy search command history
- `/explain <command>` - Explain a command
- `/generate <description>` - Generate command from description
- `/stats` - Show usage statistics
- `/recent` - Show recent commands
- `/quit` or Ctrl+D - Exit REPL

**Features:**
✨ Syntax highlighting
🔍 Fuzzy search
🤖 AI-powered suggestions
📊 Command analytics
        """
        self.console.print(Panel(Markdown(welcome), title="Welcome", border_style="cyan"))

    def handle_command(self, text: str) -> bool:
        """
        Handle REPL command.

        Args:
            text: Command text

        Returns:
            True to continue, False to exit
        """
        text = text.strip()

        if not text:
            return True

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

        elif text.startswith("/explain "):
            command = text[9:].strip()
            self._explain_command(command)

        elif text.startswith("/generate "):
            description = text[10:].strip()
            self._generate_command(description)

        else:
            # Highlight the command
            highlighted = self.highlighter.highlight_shell(text)
            self.console.print(f"[dim]→[/dim] {highlighted}")

            # Show suggestion
            self._show_suggestion(text)

        return True

    def _show_stats(self) -> None:
        """Show command usage statistics."""
        try:
            response = self.ipc_client.send_request("get_stats", {})
            if response.get("status") == "ok":
                stats = response.get("stats", {})

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
            response = self.ipc_client.send_request("get_recent_commands", {"n": 20})
            if response.get("status") == "ok":
                commands = response.get("commands", [])

                if commands:
                    self.console.print("\n[cyan]Recent Commands:[/cyan]")
                    for i, cmd in enumerate(commands, 1):
                        highlighted = self.highlighter.highlight_shell(cmd)
                        self.console.print(f"{i:2d}. {highlighted}")
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
            response = self.ipc_client.send_request("get_recent_commands", {"n": 500})
            if response.get("status") == "ok":
                commands = response.get("commands", [])
                matches = self.fuzzy.best_match(query, commands, limit=10)

                if matches:
                    self.console.print(f"\n[cyan]Search results for '{query}':[/cyan]")
                    for cmd, score in matches:
                        highlighted = self.highlighter.highlight_shell(cmd)
                        self.console.print(f"[dim]{score:3d}%[/dim] {highlighted}")
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
                self.console.print(Panel(Markdown(explanation), title="Explanation", border_style="green"))
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
            response = self.ipc_client.send_request("generate_command", {"description": description})
            if response.get("status") == "ok":
                command = response.get("command", "")
                highlighted = self.highlighter.highlight_shell(command)
                self.console.print(f"\n[cyan]Generated command:[/cyan]\n{highlighted}")
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
                        highlighted = self.highlighter.highlight_shell(cmd)
                        self.console.print(f"{i}. [dim]{score:.2f}[/dim] {highlighted}")
        except Exception:
            pass  # Silently ignore suggestion errors

    def run(self) -> None:
        """Run the REPL loop."""
        self.print_welcome()

        while True:
            try:
                # Show prompt
                text = self.session.prompt(
                    HTML("<ansicyan><b>daedelus></b></ansicyan> "),
                )

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


def start_repl(ipc_client: IPCClient) -> None:
    """
    Start interactive REPL.

    Args:
        ipc_client: IPC client for daemon communication
    """
    repl = DaedelusREPL(ipc_client)
    repl.run()
