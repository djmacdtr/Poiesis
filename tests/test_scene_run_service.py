"""Scene run service 基础测试。"""

from __future__ import annotations

from poiesis.api.services import scene_run_service
from poiesis.api.task_registry import TaskInfo


def test_start_run_passes_book_id_to_background_thread(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _DummyThread:
        def __init__(self, target, args, daemon: bool, name: str) -> None:
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon
            captured["name"] = name

        def start(self) -> None:
            captured["started"] = True

    def _fake_create(total_chapters: int) -> TaskInfo:
        return TaskInfo(task_id="t-book", total_chapters=total_chapters)

    monkeypatch.setattr(scene_run_service.threading, "Thread", _DummyThread)
    monkeypatch.setattr(scene_run_service.registry, "create", _fake_create)

    result = scene_run_service.start_run(config_path="config.yaml", chapter_count=2, book_id=7)

    assert result["task_id"] == "t-book"
    assert captured.get("started") is True
    assert captured.get("daemon") is True
    assert captured["args"][1:] == ("config.yaml", 2, 7)
