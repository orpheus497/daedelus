"""
LLM-powered commands for Daedelus CLI.

Provides AI-powered command explanation, generation, and question answering.

Created by: orpheus497
"""

import logging
from pathlib import Path

import click

from daedelus.utils.config import Config

logger = logging.getLogger(__name__)


@click.command()
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
            explanation = explainer.explain_command(
                command, include_context=False, detailed=detailed
            )
            click.echo(f"\nCommand: {command}")
            click.echo(f"\nExplanation:\n{explanation}")

    except ImportError as e:
        click.echo(f"❌ LLM dependencies not found: {e}")
        click.echo("Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus")
    except FileNotFoundError:
        click.echo(f"❌ LLM model not found at: {model_path}")
        click.echo(
            "\nTo use LLM features, download a model (e.g., Phi-3-mini GGUF) and place it at:"
        )
        click.echo(f"  {model_path}")
        click.echo("\nOr create the directory first:")
        click.echo(f"  mkdir -p {model_path.parent}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Failed to explain command: {e}", exc_info=True)


@click.command()
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
def generate(ctx: click.Context, description: tuple, alternatives: bool, explain: bool) -> None:
    """Generate a command from natural language description."""
    desc_text = " ".join(description)
    config: Config = ctx.obj["config"]

    # Try daemon first for generation/explanation
    try:
        from daedelus.daemon.ipc import IPCClient

        client = IPCClient(config.get("daemon.socket_path"), timeout=60.0)
        resp = client.send_request(
            "generate_command",
            {"description": desc_text, "return_multiple": alternatives},
        )
        if resp.get("status") == "ok" and ("command" in resp or "commands" in resp):
            click.echo(f"\nTask: {desc_text}")
            if explain:
                cmd = (
                    resp.get("command")
                    if not alternatives
                    else ", ".join(resp.get("commands", [])[:1])
                )
                exp = client.send_request("explain_command", {"command": cmd})
                click.echo(f"\nGenerated command:\n  {cmd}")
                if exp.get("status") == "ok" and exp.get("explanation"):
                    click.echo(f"\nExplanation:\n{exp['explanation']}")
                return
            if alternatives:
                click.echo("\nAlternative commands:")
                for i, cmd in enumerate(resp.get("commands", []), 1):
                    click.echo(f"  {i}. {cmd}")
            else:
                click.echo(f"\nGenerated command:\n  {resp.get('command','')}")
            return
    except Exception:
        pass

    try:
        from daedelus.llm.command_generator import CommandGenerator
        from daedelus.llm.llm_manager import LLMManager

        click.echo("Loading LLM (this may take a moment)...")

        # Get model path from config
        model_path = Path(config.get("llm.model_path")).expanduser()

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
        click.echo(
            "\nTo use LLM features, download a model (e.g., Phi-3-mini GGUF) and place it at:"
        )
        click.echo(f"  {model_path}")
        click.echo("\nOr create the directory first:")
        click.echo(f"  mkdir -p {model_path.parent}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Failed to generate command: {e}", exc_info=True)


@click.command()
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
        response = llm.generate(
            prompt, max_tokens=300, temperature=0.5, stop=["<|end|>", "<|user|>"]
        )

        click.echo(f"\nQuestion: {query_text}")
        click.echo(f"\nAnswer:\n{response}")

    except ImportError as e:
        click.echo(f"❌ LLM dependencies not found: {e}")
        click.echo("Try reinstalling daedelus: pip install --upgrade --force-reinstall daedelus")
    except FileNotFoundError:
        click.echo(f"❌ LLM model not found at: {model_path}")
        click.echo(
            "\nTo use LLM features, download a model (e.g., Phi-3-mini GGUF) and place it at:"
        )
        click.echo(f"  {model_path}")
        click.echo("\nOr create the directory first:")
        click.echo(f"  mkdir -p {model_path.parent}")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Failed to answer question: {e}", exc_info=True)


@click.command()
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
        click.echo("\nTo use web search with AI summarization:")
        click.echo("1. Download a GGUF model (see docs for instructions)")
        click.echo(f"2. Place it at: {model_path}")
        click.echo("\nSee README.md for model download instructions.")
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        logger.error(f"Web search failed: {e}", exc_info=True)


def register_llm_commands(cli: click.Group) -> None:
    """Register all LLM-powered commands."""
    cli.add_command(explain)
    cli.add_command(generate)
    cli.add_command(ask)
    cli.add_command(websearch)
