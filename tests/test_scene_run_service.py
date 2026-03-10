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

    class _DummyDb:
        def initialize_schema(self) -> None:
            return None

        def get_active_blueprint_revision(self, book_id: int) -> dict[str, int]:
            return {"id": 1, "book_id": book_id}

        def close(self) -> None:
            return None

    monkeypatch.setattr(scene_run_service, "Database", lambda _path: _DummyDb())

    result = scene_run_service.start_run(config_path="config.yaml", chapter_count=2, book_id=7)

    assert result["task_id"] == "t-book"
    assert captured.get("started") is True
    assert captured.get("daemon") is True
    assert captured["args"][1:] == ("config.yaml", 2, 7)


def test_get_run_detail_falls_back_to_scene_traces_when_chapter_trace_missing(tmp_db) -> None:
    """历史 run 若只有 scene trace，详情接口也应展示章节摘要。"""
    run_id = tmp_db.create_run_trace(
        task_id="fallback-task",
        book_id=1,
        status="running",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    tmp_db.upsert_run_scene_trace(
        run_id,
        {
            "chapter_number": 1,
            "scene_number": 1,
            "status": "needs_review",
            "scene_plan": {
                "chapter_number": 1,
                "scene_number": 1,
                "title": "场景1",
                "goal": "建立冲突",
            },
            "draft": None,
            "final_text": "旧正文",
            "changeset": {"loop_updates": []},
            "verifier_issues": [],
            "review_required": True,
            "review_reason": "仍需人工审核",
            "review_status": "pending",
            "metrics": {"issue_count": 1},
        },
    )
    tmp_db.create_scene_review(run_id, 1, 1, "仍需人工审核")
    tmp_db.update_run_trace_status(run_id, "failed", error_message="章节 trace 不存在", finished=True)

    payload = scene_run_service.get_run_detail(tmp_db, run_id)

    assert payload is not None
    assert payload["run"].current_chapter == 1
    assert payload["run"].status == "failed"
    assert payload["chapters"][0]["chapter_number"] == 1
    assert payload["chapters"][0]["status"] == "needs_review"
    assert payload["chapters"][0]["review_required"] is True
