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



def main() -> int:
    """Main entry point."""
    try:
        cli(obj={})
        return 0
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
