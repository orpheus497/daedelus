"""
Command-line interface for Daedalus.

Provides user commands for managing the daemon and querying history.

Created by: orpheus497
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import click

from daedelus import __version__
from daedelus.daemon.daemon import DaedelusDaemon
from daedelus.daemon.ipc import IPCClient
from daedelus.utils.config import Config
from daedelus.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    help="Path to config file",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v, -vv, -vvv)",
)
@click.pass_context
def cli(ctx: click.Context, config: Path | None, verbose: int) -> None:
    """
    Daedelus - Self-Learning Terminal Assistant

    A privacy-first, offline AI assistant that learns from your command usage
    and builds its own intelligence locally. Formal name: Daedelus, Nickname: Deus

    Features:
      • 🧠 Self-learning AI that builds from your usage patterns
      • ⚡ Ultra-fast suggestions (<50ms)
      • 🔒 100% offline, privacy-first (no data ever leaves your machine)
      • 🎯 Context-aware command completion
      • 🤖 LLM-powered explanations and command generation
      • 🔄 Continuous learning and model fine-tuning

    Quick Start:
      daedelus setup    # Initialize configuration
      daedelus start    # Start the daemon
      daedelus repl     # Launch interactive mode (all features active)

    Quick alias: deus (works exactly the same as daedelus)
      Example: deus start, deus repl, deus status

    Created and Designed by: orpheus497
    License: MIT | 100% FOSS
    """
    # Set up logging
    log_level = logging.WARNING
    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG

    setup_logging(console=True, level=log_level)

    # Load configuration
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config(config) if config else Config()


@cli.command()
@click.pass_context
def setup(ctx: click.Context) -> None:
    """
    Set up Daedelus for first-time use.

    This command initializes Daedelus by creating:
      • Configuration file at ~/.config/daedelus/config.yaml
      • Data directory at ~/.local/share/daedelus/
      • Models directory at ~/.local/share/models/

    After setup, you'll need to:
      1. Start the daemon: daedelus start
      2. Add shell integration to your shell RC file
      3. (Optional) Download LLM model for advanced features

    Daedelus is designed and created by orpheus497.
    """
    config: Config = ctx.obj["config"]

    click.echo("🚀 Setting up Daedalus...")

    # Create directories
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.config_dir.mkdir(parents=True, exist_ok=True)

    # Save default config
    if not config.config_path.exists():
        config.save()
        click.echo(f"✅ Created config: {config.config_path}")
    else:
        click.echo(f"ℹ️  Config already exists: {config.config_path}")

    click.echo(f"✅ Data directory: {config.data_dir}")

    # Shell integration instructions
    click.echo("\n📝 To enable shell integration, add to your shell RC file:")
    click.echo("\n  # For ZSH (~/.zshrc):")
    click.echo("  source $(daedelus shell-integration zsh)")
    click.echo("\n  # For Bash (~/.bashrc):")
    click.echo("  source $(daedelus shell-integration bash)")

    click.echo("\n✨ Setup complete! Run 'daedelus start' to begin.")


@cli.command()
@click.option(
    "--foreground",
    is_flag=True,
    help="Run in foreground (don't daemonize)",
)
@click.pass_context
def start(ctx: click.Context, foreground: bool) -> None:
    """
    Start the Daedelus daemon.

    The daemon runs in the background and:
      • Monitors your terminal commands
      • Learns from your usage patterns
      • Provides intelligent suggestions via shell integration
      • Builds local AI models from your interactions
      • Maintains complete privacy (no data leaves your machine)

    Use --foreground to run in the current terminal (useful for debugging).
    For automatic startup on boot, use: ./scripts/install-systemd-service.sh
    """
    config: Config = ctx.obj["config"]

    # Check if already running
    if is_daemon_running(config):
        click.echo("⚠️  Daemon is already running")
        click.echo(f"PID file: {config.get('daemon.pid_path')}")
        return

    if foreground:
        # Run in foreground
        click.echo("🚀 Starting daemon in foreground...")
        click.echo("Press Ctrl+C to stop")

        daemon = DaedelusDaemon(config)
        try:
            daemon.start()
        except KeyboardInterrupt:
            click.echo("\n⏹️  Stopped by user")

    else:
        # Run in background
        click.echo("🚀 Starting daemon in background...")

        # Use subprocess to daemonize
        cmd = [sys.executable, "-m", "daedelus.daemon.daemon"]

        # Redirect output to log file
        log_path = Path(config.get("daemon.log_path"))
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as log_file:
            subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,  # Detach from terminal
            )

        # Wait a moment and check if it started
        time.sleep(1)

        if is_daemon_running(config):
            click.echo("✅ Daemon started successfully")
            click.echo(f"Log file: {log_path}")
        else:
            click.echo("❌ Failed to start daemon")
            click.echo(f"Check logs: {log_path}")


@cli.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """
    Stop the Daedelus daemon.

    Gracefully shuts down the daemon and saves all learned data.
    Your command history and AI models are preserved for the next session.
    """
    config: Config = ctx.obj["config"]

    if not is_daemon_running(config):
        click.echo("ℹ️  Daemon is not running")
        return

    click.echo("⏹️  Stopping daemon...")

    # Get PID
    pid_path = Path(config.get("daemon.pid_path"))
    try:
        pid = int(pid_path.read_text().strip())

        # Send SIGTERM
        os.kill(pid, signal.SIGTERM)

        # Wait for shutdown
        for _ in range(10):
            time.sleep(0.5)
            if not is_daemon_running(config):
                click.echo("✅ Daemon stopped")
                return

        # Force kill if still running
        click.echo("⚠️  Daemon didn't stop gracefully, forcing...")
        os.kill(pid, signal.SIGKILL)
        pid_path.unlink(missing_ok=True)
        click.echo("✅ Daemon stopped (forced)")

    except (ProcessLookupError, ValueError) as e:
        click.echo(f"❌ Error stopping daemon: {e}")
        pid_path.unlink(missing_ok=True)


@cli.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """Restart the Daedalus daemon."""
    ctx.invoke(stop)
    time.sleep(1)
    ctx.invoke(start)


@cli.command()
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output in JSON format",
)
@click.pass_context
def status(ctx: click.Context, output_json: bool) -> None:
    """
    Show daemon status and statistics.

    Displays:
      • Daemon running state and uptime
      • Number of commands logged and learned
      • Suggestions generated
      • Database statistics and success rates
      • Overall learning progress

    Use --json for machine-readable output.
    """
    config: Config = ctx.obj["config"]

    if not is_daemon_running(config):
        if output_json:
            import json

            click.echo(json.dumps({"status": "stopped"}))
        else:
            click.echo("⚫ Daemon is not running")
        return

    # Query daemon via IPC
    try:
        client = IPCClient(config.get("daemon.socket_path"))
        status_data = client.status()

        if output_json:
            import json

            click.echo(json.dumps(status_data, indent=2))
        else:
            click.echo("🟢 Daemon is running")
            click.echo(f"\nUptime: {status_data.get('uptime_seconds', 0):.1f}s")
            click.echo(f"Requests handled: {status_data.get('requests_handled', 0)}")
            click.echo(f"Commands logged: {status_data.get('commands_logged', 0)}")
            click.echo(f"Suggestions generated: {status_data.get('suggestions_generated', 0)}")

            if "database" in status_data:
                db = status_data["database"]
                click.echo("\nDatabase:")
                click.echo(f"  Total commands: {db.get('total_commands', 0)}")
                click.echo(f"  Success rate: {db.get('success_rate', 0):.1f}%")

    except Exception as e:
        click.echo(f"❌ Error querying daemon: {e}")


@cli.command()
@click.argument("query")
@click.option(
    "-n",
    "--limit",
    default=20,
    help="Number of results",
)
@click.pass_context
def search(ctx: click.Context, query: str, limit: int) -> None:
    """
    Search command history with fuzzy matching.

    Uses intelligent fuzzy matching to find commands even with typos
    or partial matches. Searches through your entire command history.

    Examples:
      daedelus search "git push"      # Find all git push commands
      daedelus search docker -n 50    # Show 50 Docker commands
      daedelus search "file operations"  # Semantic search

    Quick alias: ds "query" (with shell integration)
    """
    config: Config = ctx.obj["config"]

    if not is_daemon_running(config):
        click.echo("❌ Daemon is not running. Start it with 'daedelus start'")
        return

    try:
        client = IPCClient(config.get("daemon.socket_path"))
        from daedelus.daemon.ipc import IPCMessage, MessageType

        msg = IPCMessage(MessageType.SEARCH, {"query": query, "limit": limit})
        response = client.send_message(msg)

        if response.type == MessageType.ERROR:
            click.echo(f"❌ {response.data.get('error')}")
            return

        results = response.data.get("results", [])

        if not results:
            click.echo("No results found")
            return

        click.echo(f"Found {len(results)} results:\n")
        for result in results:
            cmd = result.get("command", "")
            timestamp = result.get("timestamp", 0)
            cwd = result.get("cwd", "")

            from datetime import datetime

            time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

            click.echo(f"  {time_str} | {cwd}")
            click.echo(f"    {cmd}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@cli.command()
@click.argument("shell", type=click.Choice(["zsh", "bash", "fish"]))
def shell_integration(shell: str) -> None:
    """Print path to shell integration script."""
    import importlib.resources
    import sys

    # Map shell to integration file
    integration_files = {
        "zsh": "zsh/daedelus.plugin.zsh",
        "bash": "bash/daedelus.bash",
        "fish": "fish/daedelus.fish",
    }

    # Try to find the integration file using importlib.resources
    try:
        # For Python 3.9+, use files() API
        if sys.version_info >= (3, 9):
            from importlib.resources import files

            shell_clients_dir = files('daedelus').joinpath('shell_clients')
            integration_path = shell_clients_dir / integration_files[shell]

            # Get the actual file system path
            if hasattr(integration_path, '__fspath__'):
                actual_path = Path(integration_path.__fspath__())
            else:
                # For traversable objects, we need to extract to temp location
                import tempfile
                import shutil
                with importlib.resources.as_file(integration_path) as path:
                    actual_path = path

            if actual_path.exists():
                click.echo(str(actual_path))
            else:
                raise FileNotFoundError(f"Integration file not found: {actual_path}")
        else:
            # Fallback for Python 3.8 and earlier
            import pkg_resources
            package_name = 'daedelus'
            resource_path = f'shell_clients/{integration_files[shell]}'

            if pkg_resources.resource_exists(package_name, resource_path):
                actual_path = pkg_resources.resource_filename(package_name, resource_path)
                click.echo(actual_path)
            else:
                raise FileNotFoundError(f"Integration file not found: {resource_path}")

    except Exception as e:
        click.echo(f"Error: Integration file not found", err=True)
        click.echo(f"Details: {e}", err=True)

        # Provide helpful fallback information
        import daedelus
        package_dir = Path(daedelus.__file__).parent.parent.parent
        fallback_path = package_dir / "shell_clients" / integration_files[shell]

        click.echo(f"\nTrying fallback location: {fallback_path}", err=True)
        if fallback_path.exists():
            click.echo(str(fallback_path))
        else:
            click.echo(f"\nFallback also failed. Please check your installation.", err=True)
            sys.exit(1)


@cli.command()
@click.argument("command_text", nargs=-1, required=True)
@click.option(
    "--detailed",
    is_flag=True,
    help="Provide detailed explanation",
)
@click.option(
    "--examples",
    is_flag=True,
    help="Include usage examples",
)
@click.pass_context
def explain(ctx: click.Context, command_text: tuple, detailed: bool, examples: bool) -> None:
    """Explain what a command does using LLM."""
    command = " ".join(command_text)
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.command_explainer import CommandExplainer
        from daedelus.llm.llm_manager import LLMManager

        click.echo("Loading LLM (this may take a moment)...")

        # Get model path from config
        model_path = Path(config.get("llm.model_path"))

        # Initialize LLM
        llm = LLMManager(
            model_path=model_path,
            context_length=config.get("llm.context_length"),
            temperature=config.get("llm.temperature"),
        )
        explainer = CommandExplainer(llm)

        if examples:
            # Get explanation with examples
            result = explainer.explain_with_examples(command)
            click.echo(f"\nCommand: {command}")
            click.echo(f"\nExplanation:\n{result['explanation']}")

            if result.get("examples"):
                click.echo("\nExamples:")
                for example in result["examples"]:
                    click.echo(f"  • {example}")
        else:
            # Get simple explanation
            explanation = explainer.explain_command(command, include_context=False, detailed=detailed)
            click.echo(f"\nCommand: {command}")
            click.echo(f"\nExplanation:\n{explanation}")

    except ImportError as e:
        click.echo(f"❌ LLM dependencies not found: {e}")
        click.echo("Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus")
    except FileNotFoundError:
        click.echo(f"❌ LLM model not found at: {model_path}")
        click.echo(f"\nTo use LLM features, download a model (e.g., Phi-3-mini GGUF) and place it at:")
        click.echo(f"  {model_path}")
        click.echo(f"\nOr create the directory first:")
        click.echo(f"  mkdir -p {model_path.parent}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Failed to explain command: {e}", exc_info=True)


@cli.command()
@click.argument("description", nargs=-1, required=True)
@click.option(
    "--alternatives",
    "-a",
    is_flag=True,
    help="Show multiple alternative commands",
)
@click.option(
    "--explain",
    "-e",
    is_flag=True,
    help="Include explanation of generated command",
)
@click.pass_context
def generate(
    ctx: click.Context, description: tuple, alternatives: bool, explain: bool
) -> None:
    """Generate a command from natural language description."""
    desc_text = " ".join(description)
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.command_generator import CommandGenerator
        from daedelus.llm.llm_manager import LLMManager

        click.echo("Loading LLM (this may take a moment)...")

        # Get model path from config
        model_path = Path(config.get("llm.model_path"))

        # Initialize LLM
        llm = LLMManager(
            model_path=model_path,
            context_length=config.get("llm.context_length"),
            temperature=config.get("llm.temperature"),
        )
        generator = CommandGenerator(llm)

        if explain:
            # Generate with explanation
            result = generator.generate_with_explanation(desc_text)
            click.echo(f"\nTask: {desc_text}")
            click.echo(f"\nGenerated command:\n  {result['command']}")
            click.echo(f"\nExplanation:\n{result['explanation']}")

        elif alternatives:
            # Generate multiple alternatives
            commands = generator.generate_command(desc_text, return_multiple=True)
            click.echo(f"\nTask: {desc_text}")
            click.echo("\nAlternative commands:")
            for i, cmd in enumerate(commands, 1):
                click.echo(f"  {i}. {cmd}")

        else:
            # Generate single command
            command = generator.generate_command(desc_text)
            click.echo(f"\nTask: {desc_text}")
            click.echo(f"\nGenerated command:\n  {command}")

    except ImportError as e:
        click.echo(f"❌ LLM dependencies not found: {e}")
        click.echo("Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus")
    except FileNotFoundError:
        click.echo(f"❌ LLM model not found at: {model_path}")
        click.echo(f"\nTo use LLM features, download a model (e.g., Phi-3-mini GGUF) and place it at:")
        click.echo(f"  {model_path}")
        click.echo(f"\nOr create the directory first:")
        click.echo(f"  mkdir -p {model_path.parent}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Failed to generate command: {e}", exc_info=True)


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.pass_context
def ask(ctx: click.Context, query: tuple) -> None:
    """Ask a question about shell commands or system administration."""
    query_text = " ".join(query)
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.llm_manager import LLMManager

        click.echo("Loading LLM (this may take a moment)...")

        # Get model path from config
        model_path = Path(config.get("llm.model_path"))

        # Initialize LLM
        llm = LLMManager(
            model_path=model_path,
            context_length=config.get("llm.context_length"),
            temperature=config.get("llm.temperature"),
        )

        # Use Phi-3 chat format for better results
        prompt = f"""<|system|>
You are a helpful assistant for shell commands and system administration. Answer questions concisely and accurately.<|end|>
<|user|>
{query_text}<|end|>
<|assistant|>
"""

        # Generate response
        response = llm.generate(prompt, max_tokens=300, temperature=0.5, stop=["<|end|>", "<|user|>"])

        click.echo(f"\nQuestion: {query_text}")
        click.echo(f"\nAnswer:\n{response}")

    except ImportError as e:
        click.echo(f"❌ LLM dependencies not found: {e}")
        click.echo("Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus")
    except FileNotFoundError:
        click.echo(f"❌ LLM model not found at: {model_path}")
        click.echo(f"\nTo use LLM features, download a model (e.g., Phi-3-mini GGUF) and place it at:")
        click.echo(f"  {model_path}")
        click.echo(f"\nOr create the directory first:")
        click.echo(f"  mkdir -p {model_path.parent}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Failed to answer question: {e}", exc_info=True)


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Provide detailed summary",
)
@click.option(
    "--results",
    "-n",
    default=5,
    help="Number of search results to use",
)
@click.pass_context
def websearch(ctx: click.Context, query: tuple, detailed: bool, results: int) -> None:
    """Search the web and get AI-summarized results."""
    query_text = " ".join(query)
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.llm_manager import LLMManager
        from daedelus.llm.web_search import WebSearcher

        click.echo(f"🔍 Searching the web for: {query_text}")

        # Get model path from config
        model_path = Path(config.get("llm.model_path"))

        # Initialize LLM
        llm = LLMManager(
            model_path=model_path,
            context_length=config.get("llm.context_length"),
            temperature=config.get("llm.temperature"),
        )

        # Perform search and summarize
        searcher = WebSearcher(llm)
        result = searcher.search_and_summarize(query_text, max_results=results, detailed=detailed)

        # Display results
        click.echo(f"\n{'='*70}")
        click.echo(f"Query: {result['query']}")
        click.echo(f"{'='*70}\n")
        click.echo(result["summary"])

        if result["sources"]:
            click.echo(f"\n{'='*70}")
            click.echo("Sources:")
            for i, source in enumerate(result["sources"], 1):
                click.echo(f"  {i}. {source}")

        click.echo(f"{'='*70}")

    except ImportError as e:
        click.echo(f"❌ Dependencies not found: {e}")
        click.echo("Ensure 'requests' is installed: pip install requests")
    except FileNotFoundError:
        click.echo(f"❌ LLM model not found at: {model_path}")
        click.echo(f"\nTo use web search with AI summarization:")
        click.echo(f"1. Download a GGUF model (see docs for instructions)")
        click.echo(f"2. Place it at: {model_path}")
        click.echo(f"\nSee README.md for model download instructions.")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Web search failed: {e}", exc_info=True)


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """
    Show system information and identity.

    Displays Daedelus version, configuration paths, model status,
    and creator information.
    """
    config: Config = ctx.obj["config"]

    from daedelus import __formal_name__, __social_name__, __creator__, __purpose__

    click.echo("=" * 60)
    click.echo("  Daedelus System Information")
    click.echo("=" * 60)
    click.echo(f"\n📋 Identity:")
    click.echo(f"  Formal Name: {__formal_name__}")
    click.echo(f"  Social Name: {__social_name__}")
    click.echo(f"  Creator: {__creator__}")
    click.echo(f"  Designer: {__creator__}")
    click.echo(f"  Purpose: {__purpose__}")
    click.echo(f"\n📦 Version: {__version__}")
    click.echo(f"📄 License: MIT (100% FOSS)")
    click.echo(f"\n🗂️  Configuration:")
    click.echo(f"  Config: {config.config_path}")
    click.echo(f"  Data dir: {config.data_dir}")
    click.echo(f"  Socket: {config.get('daemon.socket_path')}")
    click.echo(f"  Log: {config.get('daemon.log_path')}")
    click.echo(f"  Database: {config.get('database.path')}")

    db_path = Path(config.get("database.path"))
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        click.echo(f"  Database size: {size_mb:.2f} MB")

    click.echo(f"\n🧠 Phase 1 (Embedding Model):")
    click.echo(f"  Model Type: FastText + Annoy")
    click.echo(f"  Model Path: {config.get('model.model_path')}")
    click.echo(f"  Purpose: Fast semantic command similarity")

    click.echo(f"\n🤖 Phase 2 (LLM - Deus Model):")
    click.echo(f"  Enabled: {config.get('llm.enabled')}")
    click.echo(f"  Model Path: {config.get('llm.model_path')}")
    click.echo(f"  Purpose: Command explanation, generation, Q&A")

    # Check model existence
    llm_model_path = Path(config.get('llm.model_path'))
    if llm_model_path.exists():
        size_mb = llm_model_path.stat().st_size / (1024 * 1024)
        click.echo(f"  Status: ✅ Found ({size_mb:.1f} MB)")
    else:
        click.echo(f"  Status: ❌ Not found")
        click.echo(f"  Hint: Download a GGUF model with: daedelus model download")

    click.echo(f"\n💡 The AI models understand their identity and were designed by {__creator__}")
    click.echo("=" * 60)


@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """
    Run diagnostics and troubleshooting checks.

    Checks the health of your Daedelus installation, including:
    • Dependencies and environment
    • Configuration files
    • Daemon status and connectivity
    • Shell integration
    • Database integrity
    • File permissions

    Use this command to diagnose installation or runtime issues.
    """
    config: Config = ctx.obj["config"]
    issues = []
    warnings = []

    click.echo("=" * 60)
    click.echo("  Daedelus Doctor - System Diagnostics")
    click.echo("=" * 60)
    click.echo()

    # Check 1: Python version
    click.echo("[1/10] Checking Python version...")
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        click.echo(f"  ✅ Python {python_version} (OK)")
    else:
        click.echo(f"  ❌ Python {python_version} (Need 3.10+)")
        issues.append(f"Python version {python_version} is too old (need 3.10+)")

    # Check 2: Installation
    click.echo("\n[2/10] Checking daedelus installation...")
    try:
        import daedelus
        click.echo(f"  ✅ Package installed: v{daedelus.__version__}")
    except ImportError as e:
        click.echo(f"  ❌ Package not properly installed: {e}")
        issues.append("daedelus package not properly installed")

    # Check 3: Shell integration files
    click.echo("\n[3/10] Checking shell integration files...")
    for shell in ['bash', 'zsh', 'fish']:
        try:
            result = subprocess.run(
                ['daedelus', 'shell-integration', shell],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and Path(result.stdout.strip()).exists():
                click.echo(f"  ✅ {shell}: {result.stdout.strip()}")
            else:
                click.echo(f"  ⚠️  {shell}: Not found")
                warnings.append(f"{shell} integration file not found")
        except Exception as e:
            click.echo(f"  ❌ {shell}: Error - {e}")
            issues.append(f"{shell} integration check failed: {e}")

    # Check 4: Configuration
    click.echo("\n[4/10] Checking configuration...")
    if config.config_path.exists():
        click.echo(f"  ✅ Config file: {config.config_path}")
    else:
        click.echo(f"  ⚠️  Config file not found: {config.config_path}")
        warnings.append("Config file not found (will use defaults)")

    # Check 5: Data directory
    click.echo("\n[5/10] Checking data directory...")
    if config.data_dir.exists():
        click.echo(f"  ✅ Data directory: {config.data_dir}")
        # Check permissions
        if os.access(config.data_dir, os.W_OK):
            click.echo(f"  ✅ Writable: Yes")
        else:
            click.echo(f"  ❌ Writable: No")
            issues.append(f"Data directory not writable: {config.data_dir}")
    else:
        click.echo(f"  ⚠️  Data directory not found: {config.data_dir}")
        warnings.append("Data directory not initialized (run 'daedelus setup')")

    # Check 6: Daemon status
    click.echo("\n[6/10] Checking daemon status...")
    if is_daemon_running(config):
        click.echo(f"  ✅ Daemon: Running")
        try:
            client = IPCClient(config.get("daemon.socket_path"))
            status_data = client.status()
            click.echo(f"  ✅ IPC: Connected")
            click.echo(f"  ℹ️  Uptime: {status_data.get('uptime_seconds', 0):.1f}s")
        except Exception as e:
            click.echo(f"  ❌ IPC: Cannot communicate - {e}")
            issues.append(f"Daemon running but IPC failed: {e}")
    else:
        click.echo(f"  ⚠️  Daemon: Not running")
        warnings.append("Daemon not running (start with 'daedelus start')")

    # Check 7: Database
    click.echo("\n[7/10] Checking database...")
    db_path = Path(config.get("database.path"))
    if db_path.exists():
        try:
            from daedelus.core.database import CommandDatabase
            db = CommandDatabase(db_path)
            stats = db.get_statistics()
            click.echo(f"  ✅ Database: {db_path}")
            click.echo(f"  ℹ️  Commands: {stats.get('total_commands', 0)}")
            db.close()
        except Exception as e:
            click.echo(f"  ❌ Database error: {e}")
            issues.append(f"Database corrupted or inaccessible: {e}")
    else:
        click.echo(f"  ⚠️  Database not found (will be created on first use)")

    # Check 8: Socket
    click.echo("\n[8/10] Checking IPC socket...")
    socket_path = Path(config.get("daemon.socket_path"))
    if socket_path.exists():
        click.echo(f"  ✅ Socket: {socket_path}")
    else:
        click.echo(f"  ⚠️  Socket not found (daemon not running)")

    # Check 9: Dependencies
    click.echo("\n[9/10] Checking key dependencies...")
    deps = {
        'fasttext': 'FastText embeddings',
        'annoy': 'Vector search',
        'click': 'CLI framework',
        'rich': 'Terminal UI',
    }
    for dep, desc in deps.items():
        try:
            __import__(dep)
            click.echo(f"  ✅ {dep}: OK ({desc})")
        except ImportError:
            click.echo(f"  ❌ {dep}: Missing ({desc})")
            issues.append(f"Missing dependency: {dep}")

    # Check 10: Shell integration active
    click.echo("\n[10/10] Checking shell integration status...")
    shell_rc_files = {
        'bash': Path.home() / '.bashrc',
        'zsh': Path.home() / '.zshrc',
        'fish': Path.home() / '.config/fish/config.fish',
    }
    integrated = False
    for shell, rc_file in shell_rc_files.items():
        if rc_file.exists():
            with open(rc_file, 'r') as f:
                content = f.read()
                if 'daedelus shell-integration' in content:
                    click.echo(f"  ✅ {shell}: Integrated in {rc_file}")
                    integrated = True

    if not integrated:
        click.echo(f"  ⚠️  No shell integration found in RC files")
        warnings.append("Shell integration not added to any RC file")

    # Summary
    click.echo()
    click.echo("=" * 60)
    click.echo("  Diagnostic Summary")
    click.echo("=" * 60)
    click.echo()

    if not issues and not warnings:
        click.echo("✅ All checks passed! Your Daedelus installation is healthy.")
    else:
        if issues:
            click.echo(f"❌ Found {len(issues)} critical issue(s):")
            for i, issue in enumerate(issues, 1):
                click.echo(f"   {i}. {issue}")
            click.echo()

        if warnings:
            click.echo(f"⚠️  Found {len(warnings)} warning(s):")
            for i, warning in enumerate(warnings, 1):
                click.echo(f"   {i}. {warning}")
            click.echo()

        if issues:
            click.echo("Recommendations:")
            click.echo("  • Reinstall daedelus: pip install -e .")
            click.echo("  • Run setup: daedelus setup")
            click.echo("  • Check installation guide: README.md")
        elif warnings:
            click.echo("Recommendations:")
            if not integrated:
                click.echo("  • Add shell integration: See install output")
            if not is_daemon_running(config):
                click.echo("  • Start daemon: daedelus start")

    click.echo()


@cli.command()
@click.option(
    "--force",
    is_flag=True,
    help="Force re-training even if recently trained",
)
@click.option(
    "--epochs",
    default=3,
    help="Number of training epochs",
)
@click.option(
    "--min-commands",
    default=100,
    help="Minimum number of new commands required",
)
@click.pass_context
def train(ctx: click.Context, force: bool, epochs: int, min_commands: int) -> None:
    """Manually trigger fine-tuning of the LLM."""
    config: Config = ctx.obj["config"]

    if not config.get("llm.enabled"):
        click.echo("❌ LLM is not enabled in config")
        click.echo("Enable it with: daedelus config set llm.enabled true")
        return

    try:
        from daedelus.core.database import CommandDatabase
        from daedelus.llm.model_manager import ModelManager
        from daedelus.llm.peft_trainer import PEFTTrainer

        click.echo("🎓 Starting manual training session...")

        # Initialize components
        db = CommandDatabase(config.get("database.path"))
        models_dir = Path(config.get("llm.model_path")).parent
        model_manager = ModelManager(models_dir)

        # Check if we have commands to train on
        recent_commands = db.get_recent_commands(n=1000, successful_only=True)

        if len(recent_commands) < min_commands and not force:
            click.echo(f"⚠️  Only {len(recent_commands)} commands in history")
            click.echo(f"Minimum required: {min_commands}")
            click.echo("Use --force to train anyway, or wait for more commands")
            return

        click.echo(f"Found {len(recent_commands)} commands for training")

        # Initialize trainer
        adapter_path = models_dir / "adapter_latest"
        trainer = PEFTTrainer(
            model_name="microsoft/Phi-3-mini-4k-instruct",
            adapter_path=adapter_path,
            r=config.get("peft.r", 8),
            lora_alpha=config.get("peft.lora_alpha", 32),
            lora_dropout=config.get("peft.lora_dropout", 0.1),
        )

        # Prepare training data
        click.echo("Preparing training data...")
        training_data = trainer.prepare_training_data(
            commands=[cmd["command"] for cmd in recent_commands],
            max_samples=1000,
        )

        # Train
        click.echo(f"Training for {epochs} epochs (this may take 5-10 minutes)...")
        trainer.train_adapter(
            training_data=training_data,
            output_dir=adapter_path,
            num_epochs=epochs,
            batch_size=4,
            learning_rate=1e-4,
        )

        click.echo("✅ Training complete!")

        # Ask if user wants to forge new model version
        if click.confirm("\nForge new model version from adapter?"):
            click.echo("🔨 Forging new model version...")

            current_model = model_manager.get_current_model()
            if current_model:
                click.echo(f"Current model: {current_model.name} (v{current_model.version})")

            new_model_path = model_manager.forge_next_version(
                adapter_path=adapter_path,
                training_commands=len(training_data),
                notes=f"Manual training session with {len(training_data)} commands",
            )

            click.echo(f"✅ New model forged: {new_model_path}")
            click.echo("Restart daemon to use new model: daedelus restart")
        else:
            click.echo("Adapter saved but not merged into model")
            click.echo(f"Adapter path: {adapter_path}")

    except ImportError as e:
        click.echo(f"❌ PEFT dependencies not found: {e}")
        click.echo("Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Training failed: {e}", exc_info=True)


@cli.group()
def model() -> None:
    """Manage LLM models."""
    pass


@model.command("download")
@click.option(
    "--model",
    default="tinyllama",
    help="Model name to download",
)
@click.pass_context
def model_download(ctx: click.Context, model: str) -> None:
    """Download base model from HuggingFace."""
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.model_manager import ModelManager

        models_dir = Path(config.get("llm.model_path")).parent
        manager = ModelManager(models_dir)

        click.echo(f"📥 Downloading {model}...")
        click.echo(f"This may take a while (model is ~669MB for TinyLlama)")

        path = manager.download_model(model)

        click.echo(f"✅ Downloaded: {path}")
        click.echo(f"\nTo initialize Daedelus model, run:")
        click.echo(f"  daedelus model init")

    except ImportError as e:
        click.echo(f"❌ Dependencies not found: {e}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Download failed: {e}", exc_info=True)


@model.command("init")
@click.option(
    "--base-model",
    default="tinyllama",
    help="Base model to use",
)
@click.pass_context
def model_init(ctx: click.Context, base_model: str) -> None:
    """Initialize Daedelus model from base."""
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.model_manager import ModelManager

        models_dir = Path(config.get("llm.model_path")).parent
        manager = ModelManager(models_dir)

        click.echo(f"🔧 Initializing Daedelus from {base_model}...")

        path = manager.initialize_daedelus(base_model)

        click.echo(f"✅ Initialized: {path}")
        click.echo(f"\nDaedelus is ready to learn from your commands!")
        click.echo(f"Start the daemon: daedelus start")

    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Initialization failed: {e}", exc_info=True)


@model.command("status")
@click.pass_context
def model_status(ctx: click.Context) -> None:
    """Show current model status."""
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.model_manager import ModelManager

        models_dir = Path(config.get("llm.model_path")).parent
        manager = ModelManager(models_dir)

        current = manager.get_current_model()

        if current:
            click.echo("Current Model")
            click.echo("=" * 40)
            click.echo(f"Name: {current.name}")
            click.echo(f"Version: v{current.version}")
            click.echo(f"Size: {current.size_bytes / (1024**3):.2f} GB")
            click.echo(f"Created: {current.created.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"Training commands: {current.training_commands}")
            click.echo(f"Parent: {current.parent or 'None (base model)'}")

            # Show lineage
            lineage = manager.get_lineage(current.name)
            if len(lineage) > 1:
                click.echo(f"\nLineage: {' → '.join(lineage)}")
        else:
            click.echo("No active model")
            click.echo("Initialize with: daedelus model init")

    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Status check failed: {e}", exc_info=True)


@model.command("versions")
@click.pass_context
def model_versions(ctx: click.Context) -> None:
    """List all model versions."""
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.model_manager import ModelManager

        models_dir = Path(config.get("llm.model_path")).parent
        manager = ModelManager(models_dir)

        models = manager.list_models()

        if not models:
            click.echo("No models found")
            return

        click.echo("Available Models")
        click.echo("=" * 60)

        for m in models:
            size_gb = m.size_bytes / (1024**3)
            marker = "→" if m == manager.get_current_model() else " "
            click.echo(f"{marker} {m.name:20s} v{m.version:2d}  {size_gb:5.2f}GB  {m.training_commands:5d} cmds")

    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Version list failed: {e}", exc_info=True)


@model.command("rollback")
@click.argument("version", type=int)
@click.pass_context
def model_rollback(ctx: click.Context, version: int) -> None:
    """Rollback to a previous model version."""
    config: Config = ctx.obj["config"]

    try:
        from daedelus.llm.model_manager import ModelManager

        models_dir = Path(config.get("llm.model_path")).parent
        manager = ModelManager(models_dir)

        current = manager.get_current_model()
        if current:
            click.echo(f"Current: {current.name} (v{current.version})")

        click.echo(f"Rolling back to v{version}...")

        path = manager.rollback(version)

        click.echo(f"✅ Rolled back to: {path}")
        click.echo("\nRestart daemon to use rolled-back model:")
        click.echo("  daedelus restart")

    except ValueError as e:
        click.echo(f"❌ {e}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Rollback failed: {e}", exc_info=True)


@cli.group()
def config_cmd() -> None:
    """Manage configuration."""
    pass


cli.add_command(config_cmd, name="config")


@config_cmd.command("get")
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Get configuration value."""
    config: Config = ctx.obj["config"]

    try:
        value = config.get(key)
        click.echo(f"{key} = {value}")
    except KeyError:
        click.echo(f"❌ Key not found: {key}")


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set configuration value."""
    config: Config = ctx.obj["config"]

    # Parse value type
    parsed_value = value
    if value.lower() in ("true", "false"):
        parsed_value = value.lower() == "true"
    elif value.isdigit():
        parsed_value = int(value)
    elif value.replace(".", "", 1).isdigit():
        parsed_value = float(value)

    config.set(key, parsed_value)
    config.save()

    click.echo(f"✅ Set {key} = {parsed_value}")
    click.echo(f"Config saved to: {config.config_path}")


@config_cmd.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show all configuration."""
    config: Config = ctx.obj["config"]

    import json

    click.echo("Current Configuration")
    click.echo("=" * 60)
    click.echo(json.dumps(config.config, indent=2, sort_keys=True))


@cli.command()
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


@cli.command("i")
@click.pass_context
def interactive(ctx: click.Context) -> None:
    """Alias for 'repl' - start interactive mode."""
    ctx.invoke(repl)


@cli.command()
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
        response = client.send_request("get_recent_commands", {"n": 500})

        if response.get("status") != "ok":
            click.echo(f"❌ Error: {response.get('error', 'Unknown error')}")
            return

        commands = response.get("commands", [])
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


@cli.command()
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


@cli.command()
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

        stats = response.get("stats", {})
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


@cli.command()
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


# Helper functions


def is_daemon_running(config: Config) -> bool:
    """Check if daemon is running."""
    pid_path = Path(config.get("daemon.pid_path"))

    if not pid_path.exists():
        return False

    try:
        pid = int(pid_path.read_text().strip())

        # Check if process exists
        os.kill(pid, 0)  # Doesn't actually kill, just checks
        return True

    except (ProcessLookupError, ValueError):
        # Stale PID file
        pid_path.unlink(missing_ok=True)
        return False


def ensure_daemon_running(config: Config, silent: bool = False) -> bool:
    """
    Ensure daemon is running, auto-start if needed.

    Args:
        config: Configuration object
        silent: If True, don't print messages

    Returns:
        True if daemon is running (or was started), False otherwise
    """
    if is_daemon_running(config):
        return True

    if not silent:
        click.echo("🚀 Auto-starting Daedelus daemon...")

    # Start daemon in background
    cmd = [sys.executable, "-m", "daedelus.daemon.daemon"]

    # Redirect output to log file
    log_path = Path(config.get("daemon.log_path"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(log_path, "a") as log_file:
            subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )

        # Wait a moment and check if it started
        time.sleep(1)

        if is_daemon_running(config):
            if not silent:
                click.echo("✅ Daemon started successfully")
            return True
        else:
            if not silent:
                click.echo(f"❌ Failed to start daemon. Check logs: {log_path}")
            return False

    except Exception as e:
        if not silent:
            click.echo(f"❌ Error starting daemon: {e}")
        return False


def main() -> int:
    """Main entry point."""
    try:
        cli(obj={})
        return 0
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
