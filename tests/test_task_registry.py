"""Task registry persistence tests."""

from __future__ import annotations

import json

from poiesis.api.task_registry import TaskRegistry


def test_registry_recovers_inflight_tasks_as_interrupted(tmp_path) -> None:
    storage = tmp_path / "task_registry.json"

    registry1 = TaskRegistry(storage_path=str(storage))
    task = registry1.create(total_chapters=3)
    task.status = "running"
    task.current_chapter = 1
    task.add_log("第 1 章完成")

    # Simulate process restart by building a new registry from the same file.
    registry2 = TaskRegistry(storage_path=str(storage))
    recovered = registry2.get(task.task_id)

    assert recovered is not None
    assert recovered.status == "interrupted"
    assert recovered.error is not None
    assert "重启" in recovered.error or "热重载" in recovered.error
    assert any("中断" in line for line in recovered.logs)


def test_registry_repairs_invalid_completed_zero_progress_task(tmp_path) -> None:
    storage = tmp_path / "task_registry.json"
    storage.write_text(
        json.dumps(
            [
                {
                    "task_id": "t-invalid",
                    "status": "completed",
                    "progress": 0.0,
                    "current_chapter": None,
                    "total_chapters": 1,
                    "logs": [],
                    "error": None,
                    "created_at": "2026-03-08T00:00:00+00:00",
                    "updated_at": "2026-03-08T00:00:00+00:00",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    registry = TaskRegistry(storage_path=str(storage))
    repaired = registry.get("t-invalid")

    assert repaired is not None
    assert repaired.status == "failed"
    assert repaired.error is not None
    assert "状态异常" in repaired.error
    assert any("状态异常" in line for line in repaired.logs)


def test_task_preview_is_persisted_and_reloaded(tmp_path) -> None:
    storage = tmp_path / "task_registry.json"

    registry1 = TaskRegistry(storage_path=str(storage))
    task = registry1.create(total_chapters=1)
    task.append_preview("第一段")
    task.append_preview("第二段")
    task.flush_preview()

    registry2 = TaskRegistry(storage_path=str(storage))
    restored = registry2.get(task.task_id)

    assert restored is not None
    assert "第一段" in restored.preview_text
    assert "第二段" in restored.preview_text
