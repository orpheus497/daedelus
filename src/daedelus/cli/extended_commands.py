"""
Extended CLI Commands
=====================
Additional CLI commands for the enhanced features:
- File operations management
- Tool/plugin management
- Document ingestion
- Training data management
- Enhanced dashboard and settings

Author: orpheus497
License: MIT
"""

import json
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table as RichTable
from rich import print as rprint

from ..utils.config import Config

logger = logging.getLogger(__name__)
console = Console()


@click.group(name="files")
def files_group():
    """
    File operations management commands.

    Manage file access permissions, view file operation history,
    and configure file operation settings.
    """
    pass


@files_group.command(name="history")
@click.option("--limit", "-n", type=int, default=20, help="Number of records to show")
@click.option("--operation", "-o", type=str, help="Filter by operation type (read/write/list)")
@click.pass_context
def files_history(ctx: click.Context, limit: int, operation: Optional[str]):
    """
    View file operation history.

    Shows a log of all file operations performed by Daedelus,
    including read, write, list, and metadata operations.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    file_ops_db = data_dir / "file_operations.db"

    if not file_ops_db.exists():
        click.echo("No file operations history found.")
        return

    try:
        import sqlite3

        with sqlite3.connect(file_ops_db) as conn:
            query = "SELECT timestamp, operation, file_path, success, bytes_read, bytes_written FROM file_access_log"

            if operation:
                query += f" WHERE operation = '{operation.upper()}'"

            query += f" ORDER BY timestamp DESC LIMIT {limit}"

            cursor = conn.execute(query)

            table = RichTable(title="File Operation History")
            table.add_column("Time", style="cyan")
            table.add_column("Operation", style="yellow")
            table.add_column("File Path", style="green")
            table.add_column("Status", style="magenta")
            table.add_column("Size", style="blue")

            for row in cursor:
                timestamp, op, path, success, bytes_read, bytes_written = row

                from datetime import datetime
                time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                status = "✓ Success" if success else "✗ Failed"

                if bytes_read:
                    size = f"{bytes_read} bytes"
                elif bytes_written:
                    size = f"{bytes_written} bytes"
                else:
                    size = "-"

                table.add_row(time_str, op, path, status, size)

            console.print(table)

    except Exception as e:
        click.echo(f"Error reading file operations history: {e}", err=True)


@files_group.command(name="stats")
@click.pass_context
def files_stats(ctx: click.Context):
    """
    Show file operations statistics.

    Displays aggregate statistics about file operations including
    total operations, success rates, and bytes transferred.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    file_ops_db = data_dir / "file_operations.db"

    if not file_ops_db.exists():
        click.echo("No file operations data found.")
        return

    try:
        from ..core.file_operations import FileMemoryTracker

        tracker = FileMemoryTracker(file_ops_db)
        stats = tracker.get_statistics()

        rprint("\n[bold cyan]File Operations Statistics[/bold cyan]\n")
        rprint(f"[bold]Total Operations:[/bold] {stats['total_operations']:,}")
        rprint(f"[bold]Success Rate:[/bold] {stats['success_rate']:.1f}%")
        rprint(f"[bold]Total Bytes Read:[/bold] {stats['total_bytes_read']:,}")
        rprint(f"[bold]Total Bytes Written:[/bold] {stats['total_bytes_written']:,}")

        rprint("\n[bold]Operations by Type:[/bold]")
        for op_type, count in stats['operations_by_type'].items():
            rprint(f"  • {op_type}: {count:,}")

        rprint("\n[bold]Most Accessed Files:[/bold]")
        for i, file_stat in enumerate(stats['most_accessed_files'][:10], 1):
            rprint(f"  {i}. {file_stat['file_path']} ({file_stat['count']} times)")

    except Exception as e:
        click.echo(f"Error getting file statistics: {e}", err=True)


@click.group(name="tools")
def tools_group():
    """
    Tool and plugin management commands.

    Manage installed tools, create new tools, and view tool execution history.
    """
    pass


@tools_group.command(name="list")
@click.option("--category", "-c", type=str, help="Filter by category")
@click.option("--enabled-only", is_flag=True, help="Show only enabled tools")
@click.pass_context
def tools_list(ctx: click.Context, category: Optional[str], enabled_only: bool):
    """
    List installed tools.

    Shows all tools and plugins currently installed in Daedelus.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    tools_db = data_dir / "tools.db"
    tools_dir = data_dir / "tools"

    if not tools_db.exists():
        click.echo("No tools database found. Run 'daedelus tools discover' first.")
        return

    try:
        from ..core.tool_system import ToolRegistry, ToolCategory

        registry = ToolRegistry(tools_db, tools_dir)

        cat_filter = ToolCategory(category) if category else None
        tools = registry.list_tools(category=cat_filter, enabled_only=enabled_only)

        if not tools:
            click.echo("No tools found.")
            return

        table = RichTable(title="Installed Tools")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="yellow")
        table.add_column("Category", style="green")
        table.add_column("Author", style="magenta")
        table.add_column("Status", style="blue")
        table.add_column("Usage", style="white")

        for tool in tools:
            status = "✓ Enabled" if tool.enabled else "✗ Disabled"
            table.add_row(
                tool.name,
                tool.version,
                tool.category.value,
                tool.author,
                status,
                str(tool.usage_count)
            )

        console.print(table)

    except Exception as e:
        click.echo(f"Error listing tools: {e}", err=True)


@tools_group.command(name="discover")
@click.pass_context
def tools_discover(ctx: click.Context):
    """
    Discover and register tools from the tools directory.

    Scans the tools directory for new or updated tools and registers them.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    tools_db = data_dir / "tools.db"
    tools_dir = data_dir / "tools"

    try:
        from ..core.tool_system import ToolRegistry

        registry = ToolRegistry(tools_db, tools_dir)
        count = registry.discover_tools()

        click.echo(f"✓ Discovered and registered {count} tools")

    except Exception as e:
        click.echo(f"Error discovering tools: {e}", err=True)


@tools_group.command(name="create")
@click.argument("name")
@click.option("--category", "-c", type=str, default="custom", help="Tool category")
@click.pass_context
def tools_create(ctx: click.Context, name: str, category: str):
    """
    Create a new tool from template.

    Creates a new tool file with boilerplate code that you can customize.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir
    tools_dir = data_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    output_path = tools_dir / f"{name}.py"

    if output_path.exists():
        click.echo(f"Error: Tool '{name}' already exists at {output_path}", err=True)
        return

    try:
        from ..core.tool_system import ToolDeveloper, ToolCategory, ToolPermission

        # Create tool template
        ToolDeveloper.create_tool_template(
            name=name,
            category=ToolCategory(category.upper()),
            permissions=[ToolPermission.FILE_READ],  # Default permission
            output_path=output_path
        )

        click.echo(f"✓ Created tool template: {output_path}")
        click.echo(f"\nNext steps:")
        click.echo(f"  1. Edit {output_path} to implement your tool")
        click.echo(f"  2. Run 'daedelus tools discover' to register it")
        click.echo(f"  3. Test with 'daedelus tools execute {name}'")

    except Exception as e:
        click.echo(f"Error creating tool: {e}", err=True)


@click.group(name="ingest")
def ingest_group():
    """
    Document ingestion commands.

    Ingest documents and files to add them to the training data.
    """
    pass


@ingest_group.command(name="document")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--category", "-c", type=str, help="Category for the document")
@click.option("--tags", "-t", multiple=True, help="Tags for the document")
@click.pass_context
def ingest_document(ctx: click.Context, file_path: Path, category: Optional[str], tags: tuple):
    """
    Ingest a document into the training data.

    Processes the document, extracts content, and adds it to the
    training data for model fine-tuning.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    doc_ingest_db = data_dir / "document_ingestion.db"
    storage_path = data_dir / "ingested_documents"

    try:
        from ..llm.document_ingestion import DocumentIngestionManager

        manager = DocumentIngestionManager(doc_ingest_db, storage_path)

        click.echo(f"Ingesting document: {file_path}")

        success = manager.ingest_document(
            file_path,
            category=category,
            tags=list(tags) if tags else None
        )

        if success:
            click.echo("✓ Document ingested successfully")

            # Show statistics
            stats = manager.get_statistics()
            click.echo(f"\nTotal documents: {stats['total_documents']}")
            click.echo(f"Training entries: {stats['total_training_entries']}")
        else:
            click.echo("✗ Failed to ingest document", err=True)

    except Exception as e:
        click.echo(f"Error ingesting document: {e}", err=True)


@ingest_group.command(name="directory")
@click.argument("dir_path", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive", "-r", is_flag=True, help="Process directory recursively")
@click.option("--pattern", "-p", type=str, default="*", help="File pattern to match")
@click.pass_context
def ingest_directory(ctx: click.Context, dir_path: Path, recursive: bool, pattern: str):
    """
    Ingest all documents from a directory.

    Recursively processes all documents in a directory and adds them
    to the training data.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    doc_ingest_db = data_dir / "document_ingestion.db"
    storage_path = data_dir / "ingested_documents"

    try:
        from ..llm.document_ingestion import DocumentIngestionManager

        manager = DocumentIngestionManager(doc_ingest_db, storage_path)

        click.echo(f"Ingesting documents from: {dir_path}")
        click.echo(f"Pattern: {pattern}, Recursive: {recursive}")

        stats = manager.ingest_directory(dir_path, recursive=recursive, pattern=pattern)

        click.echo(f"\n✓ Ingestion complete:")
        click.echo(f"  • Successful: {stats['success']}")
        click.echo(f"  • Failed: {stats['failed']}")
        click.echo(f"  • Skipped: {stats['skipped']}")

    except Exception as e:
        click.echo(f"Error ingesting directory: {e}", err=True)


@click.group(name="training")
def training_group():
    """
    Training data management commands.

    Collect, organize, and export training data for model fine-tuning.
    """
    pass


@training_group.command(name="collect")
@click.option("--commands/--no-commands", default=True, help="Include command history")
@click.option("--files/--no-files", default=True, help="Include file operations")
@click.option("--tools/--no-tools", default=True, help="Include tool executions")
@click.option("--documents/--no-documents", default=True, help="Include ingested documents")
@click.option("--limit", "-l", type=int, default=1000, help="Limit per source")
@click.pass_context
def training_collect(
    ctx: click.Context,
    commands: bool,
    files: bool,
    tools: bool,
    documents: bool,
    limit: int
):
    """
    Collect training data from all sources.

    Aggregates data from command history, file operations, tool executions,
    and ingested documents into a unified training dataset.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    try:
        from ..llm.training_data_organizer import TrainingDataOrganizer

        organizer = TrainingDataOrganizer(
            history_db=data_dir / "history.db",
            file_ops_db=data_dir / "file_operations.db",
            tool_db=data_dir / "tools.db",
            doc_ingest_db=data_dir / "document_ingestion.db",
            output_dir=data_dir / "training_data"
        )

        click.echo("Collecting training data from all sources...")

        dataset = organizer.collect_all_training_data(
            include_commands=commands,
            include_file_ops=files,
            include_tools=tools,
            include_documents=documents,
            limit_per_source=limit
        )

        click.echo(f"\n✓ Collected {len(dataset.examples)} training examples")

        # Show breakdown
        rprint("\n[bold]Examples by Source:[/bold]")
        from collections import Counter
        source_counts = Counter(ex.source.value for ex in dataset.examples)
        for source, count in source_counts.items():
            rprint(f"  • {source}: {count:,}")

    except Exception as e:
        click.echo(f"Error collecting training data: {e}", err=True)


@training_group.command(name="export")
@click.option("--format", "-f", type=click.Choice(["jsonl", "json", "alpaca"]), default="jsonl", help="Export format")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option("--quality", "-q", type=click.Choice(["high", "medium", "low"]), default="medium", help="Minimum quality")
@click.pass_context
def training_export(ctx: click.Context, format: str, output: Optional[Path], quality: str):
    """
    Export training data to file.

    Exports collected training data in various formats suitable for
    model fine-tuning (JSONL, JSON, Alpaca format).
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    try:
        from ..llm.training_data_organizer import TrainingDataOrganizer, TrainingDataQuality

        organizer = TrainingDataOrganizer(
            history_db=data_dir / "history.db",
            file_ops_db=data_dir / "file_operations.db",
            tool_db=data_dir / "tools.db",
            doc_ingest_db=data_dir / "document_ingestion.db",
            output_dir=data_dir / "training_data"
        )

        # Collect data
        click.echo("Collecting training data...")
        dataset = organizer.collect_all_training_data()

        # Export
        min_quality = TrainingDataQuality(quality.upper())

        if not output:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = data_dir / "training_data" / f"training_export_{timestamp}.{format}"

        output_path = organizer.export_dataset(dataset, format=format, min_quality=min_quality)

        click.echo(f"✓ Exported {len(dataset.examples)} examples to {output_path}")

    except Exception as e:
        click.echo(f"Error exporting training data: {e}", err=True)


@training_group.command(name="stats")
@click.pass_context
def training_stats(ctx: click.Context):
    """
    Show training data statistics.

    Displays statistics about available training data from all sources.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    try:
        from ..llm.training_data_organizer import TrainingDataOrganizer

        organizer = TrainingDataOrganizer(
            history_db=data_dir / "history.db",
            file_ops_db=data_dir / "file_operations.db",
            tool_db=data_dir / "tools.db",
            doc_ingest_db=data_dir / "document_ingestion.db",
            output_dir=data_dir / "training_data"
        )

        stats = organizer.get_statistics()

        rprint("\n[bold cyan]Training Data Statistics[/bold cyan]\n")

        for source, source_stats in stats.get('sources', {}).items():
            rprint(f"[bold]{source.title()}:[/bold]")
            for key, value in source_stats.items():
                rprint(f"  • {key}: {value}")
            rprint()

    except Exception as e:
        click.echo(f"Error getting training statistics: {e}", err=True)


@click.command(name="dashboard")
@click.option("--enhanced", is_flag=True, help="Use enhanced dashboard with all features")
@click.pass_context
def dashboard_command(ctx: click.Context, enhanced: bool):
    """
    Launch the Daedelus dashboard.

    Interactive TUI dashboard for viewing statistics, managing settings,
    and controlling all Daedelus features.
    """
    config: Config = ctx.obj["config"]
    data_dir = config.data_dir

    try:
        if enhanced:
            from ..ui.enhanced_dashboard import run_enhanced_dashboard
            run_enhanced_dashboard(data_dir, config)
        else:
            from ..ui.dashboard import run_dashboard

            # Get stats from database
            # TODO: Implement actual stats gathering
            stats = {
                "total_commands": 0,
                "successful_commands": 0,
                "success_rate": 0.0,
                "total_sessions": 0,
                "database_size_bytes": 0
            }

            run_dashboard(stats)

    except Exception as e:
        click.echo(f"Error launching dashboard: {e}", err=True)


@click.command(name="settings")
@click.pass_context
def settings_command(ctx: click.Context):
    """
    Launch the settings panel.

    Interactive UI for managing all Daedelus settings including
    file permissions, command execution, tools, and training data.
    """
    config: Config = ctx.obj["config"]

    try:
        from textual.app import App
        from ..ui.settings_panel import SettingsPanel

        class SettingsApp(App):
            def compose(self):
                yield SettingsPanel(config)

        app = SettingsApp()
        app.run()

    except Exception as e:
        click.echo(f"Error launching settings: {e}", err=True)


@click.command(name="memory")
@click.pass_context
def memory_command(ctx: click.Context):
    """
    Launch memory and permissions panel.

    Interactive UI for viewing session memory, access history,
    and managing permissions.
    """
    try:
        from textual.app import App
        from ..ui.memory_and_permissions import MemoryAndPermissionsPanel

        class MemoryApp(App):
            def compose(self):
                yield MemoryAndPermissionsPanel()

        app = MemoryApp()
        app.run()

    except Exception as e:
        click.echo(f"Error launching memory panel: {e}", err=True)


# Export all command groups
def register_extended_commands(cli_group):
    """
    Register all extended commands with the main CLI group.

    Args:
        cli_group: Main Click CLI group
    """
    cli_group.add_command(files_group)
    cli_group.add_command(tools_group)
    cli_group.add_command(ingest_group)
    cli_group.add_command(training_group)
    cli_group.add_command(dashboard_command)
    cli_group.add_command(settings_command)
    cli_group.add_command(memory_command)
