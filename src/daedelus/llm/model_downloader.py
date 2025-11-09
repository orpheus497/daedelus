"""
Interactive model downloader with user prompts.

Provides user-friendly interface for:
- Model selection and download
- Progress tracking
- Fallback suggestions
- Model recommendations

Created by: orpheus497
"""

import logging
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

logger = logging.getLogger(__name__)


class ModelDownloader:
    """
    Interactive model downloader.

    Features:
    - User-friendly model selection
    - Download progress tracking
    - Automatic fallback handling
    - Model recommendations based on hardware
    """

    def __init__(
        self,
        model_manager: Any,
        console: Console | None = None,
    ) -> None:
        """
        Initialize model downloader.

        Args:
            model_manager: ModelManager instance
            console: Rich Console (creates new if None)
        """
        self.model_manager = model_manager
        self.console = console or Console()

        logger.info("ModelDownloader initialized")

    def prompt_for_download(self) -> Path | None:
        """
        Prompt user to download a model.

        Returns:
            Path to downloaded model, or None if cancelled
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold yellow]No Models Found[/bold yellow]\n\n"
                "No LLM models were detected in your models directory.\n"
                "Would you like to download a model now?",
                border_style="yellow",
                title="[bold]Setup Required[/bold]",
            )
        )
        self.console.print()

        # Ask if user wants to download
        should_download = Confirm.ask(
            "Download a model now?",
            default=True,
        )

        if not should_download:
            self.console.print(
                "[dim]You can download a model later using: daedelus download-model[/dim]"
            )
            return None

        # Show model options
        model_name = self.show_model_selection()

        if not model_name:
            return None

        # Download the model
        return self.download_with_progress(model_name)

    def show_model_selection(self) -> str | None:
        """
        Show interactive model selection menu.

        Returns:
            Selected model name, or None if cancelled
        """
        self.console.print()
        self.console.print("[bold]Available Models:[/bold]")
        self.console.print()

        # Create table of available models
        table = Table(show_header=True)
        table.add_column("#", style="cyan", width=3)
        table.add_column("Model", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Description", style="white")
        table.add_column("Recommended", style="magenta")

        registry = self.model_manager.MODEL_REGISTRY

        model_list = list(registry.items())

        for idx, (name, info) in enumerate(model_list, 1):
            # Determine recommendation
            recommended = ""
            if name == "tinyllama":
                recommended = "✓ Best for most users"
            elif name == "phi-3-mini":
                recommended = "Better quality"

            table.add_row(
                str(idx),
                name,
                f"{info['size_mb']} MB",
                info["description"],
                recommended,
            )

        self.console.print(table)
        self.console.print()

        # Get user selection
        max_choice = len(model_list)

        choice = Prompt.ask(
            f"Select model [1-{max_choice}] (or 'cancel')",
            default="1",
        )

        if choice.lower() in ["cancel", "c", "q", "quit"]:
            return None

        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(model_list):
                return model_list[choice_idx][0]
            else:
                self.console.print("[red]Invalid choice[/red]")
                return None
        except ValueError:
            self.console.print("[red]Invalid input[/red]")
            return None

    def download_with_progress(self, model_name: str) -> Path | None:
        """
        Download model with progress tracking.

        Args:
            model_name: Name of model to download

        Returns:
            Path to downloaded model, or None if failed
        """
        registry = self.model_manager.MODEL_REGISTRY

        if model_name not in registry:
            self.console.print(f"[red]Unknown model: {model_name}[/red]")
            return None

        model_info = registry[model_name]

        self.console.print()
        self.console.print(
            Panel.fit(
                f"[bold cyan]Downloading {model_name}[/bold cyan]\n\n"
                f"Size: {model_info['size_mb']} MB\n"
                f"Repository: {model_info['repo']}\n\n"
                "[dim]This may take several minutes...[/dim]",
                border_style="cyan",
                title="[bold]Download[/bold]",
            )
        )
        self.console.print()

        try:
            with self.console.status(
                f"[bold green]Downloading {model_name}...",
                spinner="dots",
            ):
                model_path = self.model_manager.download_model(
                    model_name=model_name,
                    force=False,
                )

            self.console.print()
            self.console.print(
                f"[bold green]✓ Download complete![/bold green] {model_path}"
            )
            self.console.print()

            return model_path

        except Exception as e:
            self.console.print()
            self.console.print(
                Panel.fit(
                    f"[bold red]Download Failed[/bold red]\n\n"
                    f"Error: {e}\n\n"
                    "[dim]Please check your internet connection and try again.[/dim]",
                    border_style="red",
                    title="[bold]Error[/bold]",
                )
            )
            self.console.print()
            logger.error(f"Download failed: {e}")
            return None

    def suggest_fallback(self) -> str | None:
        """
        Suggest fallback model if preferred model unavailable.

        Returns:
            Suggested model name, or None
        """
        self.console.print()
        self.console.print(
            "[yellow]The deus.gguf model is not available.[/yellow]"
        )
        self.console.print(
            "[dim]Would you like to download a base model to get started?[/dim]"
        )
        self.console.print()

        should_download = Confirm.ask(
            "Download base model (TinyLlama)?",
            default=True,
        )

        if should_download:
            return "tinyllama"
        else:
            return None

    def __repr__(self) -> str:
        """String representation."""
        return "ModelDownloader(interactive)"


# Utility functions for CLI integration
def prompt_and_download_model(models_dir: Path) -> Path | None:
    """
    Prompt user and download a model (CLI utility).

    Args:
        models_dir: Models directory

    Returns:
        Path to downloaded model, or None if cancelled
    """
    from daedelus.llm.model_manager import ModelManager

    console = Console()

    manager = ModelManager(models_dir)
    downloader = ModelDownloader(manager, console)

    return downloader.prompt_for_download()


def auto_download_if_missing(models_dir: Path) -> bool:
    """
    Automatically download default model if no models exist.

    Args:
        models_dir: Models directory

    Returns:
        True if model available, False otherwise
    """
    from daedelus.llm.model_manager import ModelManager

    manager = ModelManager(models_dir)

    # Check if any models exist
    existing_models = list(models_dir.glob("*.gguf"))

    if existing_models:
        return True

    # No models - prompt for download
    console = Console()
    downloader = ModelDownloader(manager, console)

    model_path = downloader.prompt_for_download()

    return model_path is not None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Model Downloader Test")
    print("=" * 70)

    console = Console()

    # Simulate no models scenario
    console.print()
    console.print("[bold]Scenario: No models found[/bold]")
    console.print()

    # Show what the prompts look like
    console.print(
        Panel.fit(
            "[bold yellow]No Models Found[/bold yellow]\n\n"
            "No LLM models were detected in your models directory.\n"
            "Would you like to download a model now?",
            border_style="yellow",
            title="[bold]Setup Required[/bold]",
        )
    )

    console.print()
    console.print("[dim]User would be prompted to select and download a model...[/dim]")
