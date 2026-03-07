"""Task registry persistence tests."""

from __future__ import annotations

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
