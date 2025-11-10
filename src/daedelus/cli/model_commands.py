"""
Model and training management commands for Daedelus CLI.

Provides commands for model download, initialization, fine-tuning, and version management.

Created by: orpheus497
"""

import logging
from pathlib import Path

import click

from daedelus.utils.config import Config

logger = logging.getLogger(__name__)


@click.command()
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


@click.group()
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


def register_model_commands(cli: click.Group) -> None:
    """Register all model and training commands."""
    cli.add_command(train)
    cli.add_command(model)
