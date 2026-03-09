"""CLI behavior tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from click.testing import CliRunner

from poiesis.cli import main
from poiesis.db.database import Database


@dataclass
class _DbCfg:
    path: str


@dataclass
class _Cfg:
    database: _DbCfg


def test_status_uses_book_id_scope(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli-status.db"
    db = Database(str(db_path))
    db.initialize_schema()

    second_book_id = db.create_book(name="第二本")

    db.upsert_chapter(chapter_number=1, content="book1", title="b1", book_id=1)
    db.upsert_chapter(chapter_number=1, content="book2", title="b2", book_id=second_book_id)

    db.upsert_world_rule("rule_a", "默认规则", book_id=1)
    db.upsert_world_rule("rule_a", "第二本规则", book_id=second_book_id)

    db.upsert_character(name="Alice", description="默认角色", book_id=1)
    db.upsert_character(name="Alice", description="第二本角色", book_id=second_book_id)

    db.add_staging_change(
        change_type="upsert",
        entity_type="character",
        entity_key="pending_book1",
        proposed_data={"name": "pending_book1"},
        book_id=1,
    )
    db.add_staging_change(
        change_type="upsert",
        entity_type="character",
        entity_key="pending_book2",
        proposed_data={"name": "pending_book2"},
        book_id=second_book_id,
    )
    db.close()

    monkeypatch.setattr(
        "poiesis.config.load_config", lambda _p: _Cfg(database=_DbCfg(path=str(db_path)))
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["status", "--config", "ignored.yaml", "--book-id", str(second_book_id)]
    )

    assert result.exit_code == 0
    assert "Book ID" in result.output
    assert str(second_book_id) in result.output
    assert "Chapters generated" in result.output


def test_run_passes_book_id_to_runloop(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeRunLoop:
        def __init__(self, config_path: str, book_id: int = 1) -> None:
            captured["config_path"] = config_path
            captured["book_id"] = book_id

        def load_world_seed(self, seed_path=None) -> None:
            captured["seed_path"] = seed_path

        def run(self, max_chapters=None) -> None:
            captured["max_chapters"] = max_chapters

    monkeypatch.setattr("poiesis.run_loop.RunLoop", _FakeRunLoop)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["run", "--config", "config.yaml", "--book-id", "7", "--max-chapters", "3"],
    )

    assert result.exit_code == 0
    assert captured["config_path"] == "config.yaml"
    assert captured["book_id"] == 7
    assert captured["seed_path"] is None
    assert captured["max_chapters"] == 3
