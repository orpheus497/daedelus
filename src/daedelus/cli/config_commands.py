"""
Configuration management commands for Daedelus CLI.

Provides commands for viewing and modifying configuration settings.

Created by: orpheus497
"""

import click

from daedelus.utils.config import Config


@click.group()
def config_cmd() -> None:
    """Manage configuration."""
    pass


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


def register_config_commands(cli: click.Group) -> None:
    """Register all configuration commands."""
    cli.add_command(config_cmd, name="config")
