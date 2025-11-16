"""
Command-line interface for Daedelus.

Main CLI entry point with modular command group registration.

Created by: orpheus497
"""

import logging

import click

from daedelus import __version__
from daedelus.utils.config import Config
from daedelus.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(path_type=str),
    help="Path to config file",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v, -vv, -vvv)",
)
@click.pass_context
def cli(ctx: click.Context, config: str | None, verbose: int) -> None:
    """
    Daedelus - Self-Learning Terminal Assistant

    A privacy-first, offline AI assistant that learns from your command usage
    and builds its own intelligence locally.

    \b
    🧠 DEFAULT MODE - INTERACTIVE REPL:
      Just run 'daedelus' or 'deus' with no arguments to start the
      interactive shell with all features always active:
      • Real-time syntax highlighting
      • Auto-completion from history
      • AI-powered suggestions
      • Natural language understanding
      • Script creation and file operations
    
    \b
    🚀 QUICK START:
      daedelus              # Start interactive REPL (default)
      deus                  # Same as above (short alias)
      
      # Inside REPL, just type naturally:
      > ls -la
      > /generate find all large files
      > /write-script backup my documents
      > Tell me what's in this directory
    
    \b
    🔧 TRADITIONAL CLI COMMANDS (Optional):
      daedelus setup        # Configuration wizard
      daedelus start        # Start background daemon
      daedelus stop         # Stop daemon
      daedelus status       # Check system status
      daedelus dashboard    # Launch TUI dashboard
    
    \b
    📚 KEY FEATURES:
      • Interactive REPL shell (default interface)
      • Real-time syntax highlighting (always on)
      • Natural language command generation
      • Script writing from descriptions  
      • Document ingestion for training
      • File operations with AI analysis
      • Self-learning from usage patterns
      • 100% offline, privacy-first
    
    \b
    💡 WHY REPL MODE?
      Daedelus is designed as an AI assistant, not just a CLI tool.
      The REPL provides the best experience for:
      • Interactive exploration
      • Natural language interaction
      • Immediate feedback
      • Learning as you work
    
    \b
    📖 MORE HELP:
      daedelus --help            # This message
      daedelus <command> --help  # Command-specific help
      /help (in REPL)            # Interactive help
    
    Created by: orpheus497
    License: MIT | 100% FOSS | Privacy-First
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
    from pathlib import Path

    ctx.obj["config"] = Config(Path(config)) if config else Config()


# ========================================
# Register Command Groups
# ========================================

# Daemon management commands
from daedelus.cli.daemon_commands import register_daemon_commands

register_daemon_commands(cli)

# LLM-powered commands
from daedelus.cli.llm_commands import register_llm_commands

register_llm_commands(cli)

# Model and training commands
from daedelus.cli.model_commands import register_model_commands

register_model_commands(cli)

# Configuration commands
from daedelus.cli.config_commands import register_config_commands

register_config_commands(cli)

# Interactive mode and history commands
from daedelus.cli.interactive_commands import register_interactive_commands

register_interactive_commands(cli)

# Integration and diagnostics commands
from daedelus.cli.integration_commands import register_integration_commands

register_integration_commands(cli)

# Extended commands registration (files, tools, ingest, training, dashboard, settings, memory)
try:
    from daedelus.cli.extended_commands import register_extended_commands

    register_extended_commands(cli)
except ImportError:
    logger.warning("Extended commands not available")


def load_plugin_commands(cli_group: click.Group):
    """Dynamically loads CLI commands from plugins via a cache file."""
    import importlib
    import json
    import sys
    from pathlib import Path

    try:
        config = Config()
        cache_path = config.data_dir / "cli_commands.json"

        if not cache_path.exists():
            logger.debug("Plugin CLI command cache not found. Skipping.")
            return

        with open(cache_path) as f:
            commands_to_load = json.load(f)

        for name, info in commands_to_load.items():
            plugin_path_str = None
            try:
                module_name = info["module"]
                function_name = info["function"]
                plugin_path_str = info.get("path")

                if not plugin_path_str:
                    logger.warning(
                        f"Plugin command '{name}' is missing path information. Skipping."
                    )
                    continue

                plugin_path = Path(plugin_path_str)
                if not plugin_path.is_dir():
                    logger.warning(
                        f"Path for plugin command '{name}' does not exist: {plugin_path_str}. Skipping."
                    )
                    continue

                # Add to path and import
                sys.path.insert(0, str(plugin_path))

                module = importlib.import_module(module_name)
                command_func = getattr(module, function_name)
                cli_group.add_command(command_func, name)
                logger.debug(f"Loaded plugin command '{name}'")

            except Exception as e:
                logger.warning(f"Failed to load plugin command '{name}': {e}")
            finally:
                # Clean up sys.path
                if plugin_path_str and plugin_path_str in sys.path:
                    sys.path.remove(plugin_path_str)

    except Exception as e:
        logger.error(f"Failed to load plugin commands: {e}", exc_info=True)


# Register plugin commands
load_plugin_commands(cli)


def main() -> int:
    """Main entry point."""
    import sys

    try:
        # If no arguments provided, start REPL mode by default
        if len(sys.argv) == 1:
            sys.argv.append("repl")
        cli(obj={})
        return 0
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
