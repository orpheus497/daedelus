"""
Interactive mode and history commands for Daedelus CLI.

Provides REPL, search, highlighting, analytics, and tips commands.

Created by: orpheus497
"""

import logging

import click

from daedelus.daemon.ipc import IPCClient
from daedelus.utils.config import Config

logger = logging.getLogger(__name__)


def is_daemon_running(config: Config) -> bool:
    """Check if daemon is running (imported from daemon_commands)."""
    from daedelus.cli.daemon_commands import is_daemon_running as check_daemon
    return check_daemon(config)


def ensure_daemon_running(config: Config, silent: bool = False) -> bool:
    """Ensure daemon is running (imported from daemon_commands)."""
    from daedelus.cli.daemon_commands import ensure_daemon_running as ensure_daemon
    return ensure_daemon(config, silent)


@click.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """
    Start interactive REPL mode.

    An enhanced shell with all features always active:
    - Syntax highlighting
    - Fuzzy command search
    - AI-powered suggestions
    - Auto-completion from history
    - Command explanations and generation
    """
    config: Config = ctx.obj["config"]

    # Auto-start daemon if needed
    if not ensure_daemon_running(config):
        return

    try:
        from daedelus.cli.repl import start_repl

        client = IPCClient(config.get("daemon.socket_path"))
        start_repl(client)

    except ImportError as e:
        click.echo(f"❌ Missing dependencies for REPL mode: {e}")
        click.echo("Install with: pip install daedelus")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"REPL error: {e}", exc_info=True)


@click.command("i")
@click.pass_context
def interactive(ctx: click.Context) -> None:
    """Alias for 'repl' - start interactive mode."""
    ctx.invoke(repl)


@click.command()
@click.argument("query", nargs=-1, required=True)
@click.option("-n", "--limit", default=10, help="Number of results to show")
@click.pass_context
def search(ctx: click.Context, query: tuple[str, ...], limit: int) -> None:
    """
    Fuzzy search command history.

    Examples:
        daedelus search "git push"
        daedelus search docker -n 20
        daedelus search "file operations"
    """
    config: Config = ctx.obj["config"]
    query_str = " ".join(query)

    if not is_daemon_running(config):
        click.echo("⚠️  Daemon not running. Start with: daedelus start")
        return

    try:
        from daedelus.utils.fuzzy import get_matcher
        from daedelus.utils.highlighting import get_highlighter

        client = IPCClient(config.get("daemon.socket_path"))
        response = client.send_request("search", {"query": "", "limit": 500})

        if response.get("status") != "ok":
            click.echo(f"❌ Error: {response.get('error', 'Unknown error')}")
            return

        commands = response.get("results", [])
        matcher = get_matcher(threshold=40)
        matches = matcher.best_match(query_str, commands, limit=limit)

        if matches:
            highlighter = get_highlighter()
            click.echo(f"\n🔍 Search results for '{query_str}':\n")

            for cmd, score in matches:
                highlighted = highlighter.highlight_shell(cmd)
                click.echo(f"  [{score:3d}%] {highlighted}")
        else:
            click.echo(f"No matches found for '{query_str}'")

    except ImportError as e:
        click.echo(f"❌ Missing dependencies: {e}")
        click.echo("Install with: pip install --upgrade daedelus")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Search error: {e}", exc_info=True)


@click.command()
@click.argument("command_text", nargs=-1)
@click.option("-s", "--syntax", default="bash", help="Syntax highlighting language")
@click.pass_context
def highlight(ctx: click.Context, command_text: tuple[str, ...], syntax: str) -> None:
    """
    Highlight command with syntax coloring.

    Examples:
        daedelus highlight "git log --oneline --graph"
        daedelus highlight "SELECT * FROM users" --syntax sql
    """
    if not command_text:
        click.echo("❌ No command provided")
        return

    try:
        from daedelus.utils.highlighting import get_highlighter

        command = " ".join(command_text)
        highlighter = get_highlighter()
        highlighted = highlighter.highlight_auto(command, language=syntax)

        click.echo(highlighted)

    except ImportError as e:
        click.echo(f"❌ Missing dependencies: {e}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@click.command()
@click.option("--detailed", is_flag=True, help="Show detailed statistics")
@click.pass_context
def analytics(ctx: click.Context, detailed: bool) -> None:
    """
    Show command usage analytics.

    Displays:
    - Most frequently used commands
    - Command success rates
    - Usage patterns by time
    - Directory-based statistics
    """
    config: Config = ctx.obj["config"]

    if not is_daemon_running(config):
        click.echo("⚠️  Daemon not running. Start with: daedelus start")
        return

    try:
        from rich.console import Console
        from rich.table import Table

        client = IPCClient(config.get("daemon.socket_path"))
        response = client.send_request("get_stats", {})

        if response.get("status") != "ok":
            click.echo(f"❌ Error: {response.get('error', 'Unknown error')}")
            return

        # Stats are at top level of response
        stats = response
        console = Console()

        # Create statistics table
        table = Table(title="📊 Daedelus Analytics", show_header=True)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Total Commands", str(stats.get("total_commands", 0)))
        table.add_row("Unique Commands", str(stats.get("unique_commands", 0)))
        table.add_row("Success Rate", f"{stats.get('success_rate', 0):.1f}%")
        table.add_row("Most Used", stats.get("most_used", "N/A"))

        console.print(table)

        if detailed:
            # Show top commands
            top_commands = stats.get("top_commands", [])
            if top_commands:
                click.echo("\n📈 Top 10 Commands:")
                for i, (cmd, count) in enumerate(top_commands[:10], 1):
                    click.echo(f"  {i:2d}. {cmd:40s} ({count} times)")

    except ImportError as e:
        click.echo(f"❌ Missing dependencies: {e}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@click.command()
@click.pass_context
def tips(ctx: click.Context) -> None:
    """
    Show helpful tips and tricks for using Daedelus.
    """
    from rich.console import Console
    from rich.markdown import Markdown

    tips_text = """
# 🎯 Daedelus Tips & Tricks

## Quick Start
- `daedelus repl` or `daedelus i` - Start interactive mode
- `daedelus search <query>` - Fuzzy search your command history
- `daedelus explain <command>` - Get AI explanation
- `daedelus generate <description>` - Generate command from description

## Interactive REPL Commands
- `/search <query>` - Fuzzy search history
- `/explain <cmd>` - Explain a command
- `/generate <desc>` - Generate command
- `/recent` - Show recent commands
- `/stats` - Usage statistics
- `/help` - REPL help

## Keyboard Shortcuts (in REPL)
- `Tab` - Auto-complete from history
- `↑/↓` - Navigate history
- `Ctrl+D` - Exit REPL
- `Ctrl+C` - Clear current line

## Advanced Usage
- `daedelus analytics --detailed` - Detailed usage statistics
- `daedelus highlight "command" --syntax python` - Syntax highlighting
- `daedelus search "git" -n 20` - Show 20 search results

## Shell Integration
Add to your shell RC file for auto-suggestions:
```bash
# For ZSH
source $(daedelus shell-integration zsh)

# For Bash
source $(daedelus shell-integration bash)
```

## Model Management
- `daedelus model download` - Download TinyLlama model
- `daedelus model init` - Initialize Daedelus model
- `daedelus model status` - Check model status
- `daedelus model versions` - List all versions

## Privacy
- All data stays local (100% offline)
- No telemetry or tracking
- Commands in sensitive directories are excluded
- See config for privacy settings
    """

    console = Console()
    console.print(Markdown(tips_text))


def register_interactive_commands(cli: click.Group) -> None:
    """Register all interactive and history commands."""
    cli.add_command(repl)
    cli.add_command(interactive)
    cli.add_command(search)
    cli.add_command(highlight)
    cli.add_command(analytics)
    cli.add_command(tips)
