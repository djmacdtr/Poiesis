"""World seed loading policy tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from poiesis.config import resolve_world_seed_path
from poiesis.run_loop import RunLoop


class _FakeDB:
    def __init__(self) -> None:
        self.rules: list[dict] = []
        self.chars: list[dict] = []
        self.events: list[dict] = []
        self.hints: list[dict] = []

    def list_world_rules(self, book_id: int = 1):
        return list(self.rules)

    def list_characters(self, book_id: int = 1):
        return list(self.chars)

    def list_timeline_events(self, book_id: int = 1):
        return list(self.events)

    def list_foreshadowing(self, book_id: int = 1):
        return list(self.hints)

    def upsert_world_rule(
        self, rule_key: str, description: str, book_id: int = 1, is_immutable: bool = True
    ):
        self.rules.append({"rule_key": rule_key, "description": description, "book_id": book_id})

    def upsert_character(
        self,
        name: str,
        book_id: int = 1,
        description: str | None = None,
        core_motivation: str | None = None,
        attributes=None,
    ):
        self.chars.append({"name": name, "description": description or "", "book_id": book_id})

    def upsert_timeline_event(
        self,
        event_key: str,
        description: str,
        book_id: int = 1,
        timestamp_in_world: str | None = None,
        chapter_number: int | None = None,
        characters_involved=None,
    ):
        self.events.append({"event_key": event_key, "description": description, "book_id": book_id})

    def upsert_foreshadowing(
        self, hint_key: str, description: str, book_id: int = 1, status: str = "pending"
    ):
        self.hints.append(
            {"hint_key": hint_key, "description": description, "book_id": book_id, "status": status}
        )


class _FakeWorld:
    def __init__(self) -> None:
        self.loaded = False

    def load_from_db(self, db: _FakeDB, book_id: int = 1) -> None:
        self.loaded = True


def _make_loop(language: str, db: _FakeDB) -> RunLoop:
    loop = RunLoop.__new__(RunLoop)
    loop._language = language
    loop._book_id = 1
    loop._db = db
    loop._world = _FakeWorld()
    loop._config = SimpleNamespace(world_seed="examples/world_seed.yaml")
    return loop


def _write_seed(path: Path, rule_desc: str) -> None:
    payload = {
        "immutable_rules": [
            {"key": "magic_costs_life", "description": rule_desc, "is_immutable": True}
        ],
        "characters": [{"name": "测试角色", "description": "角色描述"}],
        "timeline_events": [{"event_key": "e1", "description": "时间线事件"}],
        "foreshadowing": [{"hint_key": "h1", "description": "伏笔描述", "status": "pending"}],
    }
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, allow_unicode=True)


def test_load_world_seed_auto_selects_language_seed_when_empty(monkeypatch, tmp_path: Path) -> None:
    seed_zh = tmp_path / "world_seed_zh.yaml"
    _write_seed(seed_zh, "中文规则")

    db = _FakeDB()
    loop = _make_loop("zh-CN", db)

    monkeypatch.setattr(
        "poiesis.run_loop.resolve_world_seed_path", lambda language, default_seed: str(seed_zh)
    )

    loop.load_world_seed()

    assert any(item["description"] == "中文规则" for item in db.rules)
    assert loop._world.loaded is True


def test_load_world_seed_skips_auto_load_when_canon_exists(monkeypatch, tmp_path: Path) -> None:
    seed_zh = tmp_path / "world_seed_zh.yaml"
    _write_seed(seed_zh, "不应写入")

    db = _FakeDB()
    db.rules.append({"rule_key": "existing", "description": "已有规则", "book_id": 1})
    loop = _make_loop("zh-CN", db)

    monkeypatch.setattr(
        "poiesis.run_loop.resolve_world_seed_path", lambda language, default_seed: str(seed_zh)
    )

    loop.load_world_seed()

    assert len([r for r in db.rules if r.get("description") == "不应写入"]) == 0


def test_load_world_seed_with_explicit_seed_path_always_loads(tmp_path: Path) -> None:
    seed_custom = tmp_path / "custom_seed.yaml"
    _write_seed(seed_custom, "显式种子规则")

    db = _FakeDB()
    db.rules.append({"rule_key": "existing", "description": "已有规则", "book_id": 1})
    loop = _make_loop("zh-CN", db)

    loop.load_world_seed(seed_path=str(seed_custom))

    assert any(item["description"] == "显式种子规则" for item in db.rules)


def test_resolve_world_seed_path_supports_language_prefix_fallback() -> None:
    assert (
        resolve_world_seed_path("zh-TW", "examples/world_seed.yaml")
        == "examples/world_seed_zh.yaml"
    )
    assert (
        resolve_world_seed_path("en-GB", "examples/world_seed.yaml") == "examples/world_seed.yaml"
    )
