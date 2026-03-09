"""Poiesis 命令行入口。"""

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
@click.option(
    "--book-id",
    default=1,
    type=click.IntRange(1),
    show_default=True,
    help="目标书籍 ID。",
)
def run(config: str, max_chapters: int | None, seed: str | None, book_id: int) -> None:
    """运行新的 scene 驱动主链。"""
    from poiesis.api.services.scene_run_service import run_sync
    from poiesis.config import load_config

    chapter_count = max_chapters or load_config(config).generation.max_chapters
    run_id = run_sync(
        config_path=config,
        chapter_count=chapter_count,
        book_id=book_id,
        seed_path=seed,
        log=lambda message: console.print(f"[cyan]{message}[/cyan]"),
    )
    console.print(f"[green]同步运行完成，run_id={run_id}[/green]")


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
@click.option(
    "--book-id",
    default=1,
    type=click.IntRange(1),
    show_default=True,
    help="目标书籍 ID。",
)
def init(config: str, seed: str | None, book_id: int) -> None:
    """Initialize a new world database from a seed file."""
    from poiesis.api.services.scene_run_service import initialize_world
    from poiesis.config import load_config
    from poiesis.db.database import Database

    cfg = load_config(config)
    db = Database(cfg.database.path)
    db.initialize_schema()
    console.print(f"[green]Database initialized at {cfg.database.path}[/green]")
    db.close()
    initialize_world(config_path=config, book_id=book_id, seed_path=seed)
    console.print("[bold green]World initialized successfully.[/bold green]")


@main.command()
@click.option(
    "--config",
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml.",
)
@click.option("--host", default="0.0.0.0", show_default=True, help="监听地址。")
@click.option("--port", default=8000, show_default=True, type=int, help="监听端口。")
@click.option("--reload", is_flag=True, default=False, help="开启热重载（开发模式）。")
def serve(config: str, host: str, port: int, reload: bool) -> None:
    """启动 Poiesis HTTP API 服务（FastAPI + uvicorn）。"""
    import os

    import uvicorn

    os.environ["POIESIS_CONFIG"] = config
    console.print(f"[green]启动 API 服务：http://{host}:{port}[/green]")
    uvicorn.run(
        "poiesis.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@main.command()
@click.option(
    "--config",
    default="config.yaml",
    show_default=True,
    help="Path to config.yaml.",
)
@click.option(
    "--book-id",
    default=1,
    type=click.IntRange(1),
    show_default=True,
    help="目标书籍 ID。",
)
def status(config: str, book_id: int) -> None:
    """Show current world state and generation progress."""
    from poiesis.config import load_config
    from poiesis.db.database import Database

    cfg = load_config(config)
    db = Database(cfg.database.path)
    db.initialize_schema()

    if db.get_book(book_id) is None:
        db.close()
        raise click.ClickException(f"book_id={book_id} 不存在")

    chapters = db.list_chapters(book_id=book_id)
    rules = db.list_world_rules(book_id=book_id)
    characters = db.list_characters(book_id=book_id)
    pending = db.list_staging_changes(status="pending", book_id=book_id)

    # 构建并打印状态汇总表格
    table = Table(title="Poiesis World Status", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Book ID", str(book_id))
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
