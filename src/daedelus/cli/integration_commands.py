"""
System integration and diagnostics commands for Daedelus CLI.

Provides shell integration, diagnostics, and system information commands.

Created by: orpheus497
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import click

from daedelus.daemon.ipc import IPCClient
from daedelus.utils.config import Config

logger = logging.getLogger(__name__)


def is_daemon_running(config: Config) -> bool:
    """Check if daemon is running (imported from daemon_commands)."""
    from daedelus.cli.daemon_commands import is_daemon_running as check_daemon
    return check_daemon(config)


@click.command()
@click.argument("shell", type=click.Choice(["zsh", "bash", "fish"]))
def shell_integration(shell: str) -> None:
    """Print path to shell integration script."""
    import importlib.resources

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


@click.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """
    Show system information and identity.

    Displays Daedelus version, configuration paths, model status,
    and creator information.
    """
    config: Config = ctx.obj["config"]

    from daedelus import __version__, __formal_name__, __social_name__, __creator__, __purpose__

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


@click.command()
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


def register_integration_commands(cli: click.Group) -> None:
    """Register all integration and diagnostics commands."""
    cli.add_command(shell_integration, name="shell-integration")
    cli.add_command(info)
    cli.add_command(doctor)
