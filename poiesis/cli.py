"""CLI entry point for Poiesis."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(package_name="poiesis")
def main() -> None:
    """Poiesis – autonomous long-form narrative generation engine."""


@main.command()
@click.option(
    "--config",
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml.",
)
@click.option(
    "--max-chapters",
    default=None,
    type=int,
    show_default=True,
    help="Override max chapters from config.",
)
@click.option(
    "--seed",
    default=None,
    type=click.Path(exists=True),
    help="Path to world_seed.yaml (overrides config).",
)
def run(config: str, max_chapters: int | None, seed: str | None) -> None:
    """Run the generation loop."""
    from poiesis.run_loop import RunLoop

    loop = RunLoop(config_path=config)
    loop.load_world_seed(seed_path=seed)
    loop.run(max_chapters=max_chapters)


@main.command()
@click.option(
    "--config",
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml.",
)
@click.option(
    "--seed",
    default=None,
    type=click.Path(exists=True),
    help="Path to world_seed.yaml.",
)
def init(config: str, seed: str | None) -> None:
    """Initialize a new world database from a seed file."""
    from poiesis.config import load_config
    from poiesis.db.database import Database

    cfg = load_config(config)
    db = Database(cfg.database.path)
    db.initialize_schema()
    console.print(f"[green]Database initialized at {cfg.database.path}[/green]")

    from poiesis.run_loop import RunLoop

    loop = RunLoop(config_path=config)
    loop.load_world_seed(seed_path=seed)
    console.print("[bold green]World initialized successfully.[/bold green]")


@main.command()
@click.option(
    "--config",
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml.",
)
def status(config: str) -> None:
    """Show current world state and generation progress."""
    from poiesis.config import load_config
    from poiesis.db.database import Database

    cfg = load_config(config)
    db = Database(cfg.database.path)
    db.initialize_schema()

    chapters = db.list_chapters()
    rules = db.list_world_rules()
    characters = db.list_characters()
    pending = db.list_staging_changes(status="pending")

    # Summary table
    table = Table(title="Poiesis World Status", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Chapters generated", str(len(chapters)))
    table.add_row("World rules", str(len(rules)))
    table.add_row("Characters", str(len(characters)))
    table.add_row("Pending staging changes", str(len(pending)))

    if chapters:
        last = chapters[-1]
        table.add_row("Last chapter", f"#{last['chapter_number']} – {last.get('title', '')}")
        table.add_row("Last chapter status", last.get("status", "unknown"))

    console.print(table)

    db.close()
