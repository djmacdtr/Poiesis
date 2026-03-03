"""运行任务服务层，在后台线程中执行 RunLoop 并记录日志。"""

from __future__ import annotations

import threading
from typing import Any

from poiesis.api.task_registry import TaskInfo, registry


def _run_in_background(task: TaskInfo, config_path: str, chapter_count: int) -> None:
    """后台线程函数：初始化 RunLoop 并逐章生成，将进度写入任务日志。

    注意：此函数在独立线程中运行，若进程重启任务状态将丢失（MVP 已知限制）。
    如需可靠性，建议引入任务队列（如 Celery / RQ）并将状态持久化到 DB。
    """
    # 延迟导入，避免启动时加载 LLM 依赖
    from poiesis.run_loop import RunLoop

    task.status = "running"
    task.add_log("任务开始：初始化生成器…")

    try:
        loop = RunLoop(config_path=config_path)
        task.add_log("加载世界种子…")
        loop.load_world_seed()

        existing = loop._db.list_chapters()
        start_chapter = len(existing) + 1
        end_chapter = start_chapter + chapter_count - 1

        task.add_log(f"准备生成第 {start_chapter} 至第 {end_chapter} 章…")

        for i, chapter_number in enumerate(range(start_chapter, end_chapter + 1), start=1):
            task.add_log(f"开始规划第 {chapter_number} 章…")
            loop._generate_chapter(chapter_number)
            task.current_chapter = i
            task.add_log(f"第 {chapter_number} 章完成 ({i}/{chapter_count})")

        task.status = "completed"
        task.add_log(f"全部 {chapter_count} 章生成完毕。")

    except Exception as exc:  # noqa: BLE001
        task.status = "failed"
        task.error = str(exc)
        task.add_log(f"生成失败：{exc}")


def start_run(config_path: str, chapter_count: int) -> dict[str, Any]:
    """创建后台生成任务，立即返回任务信息。"""
    task = registry.create(total_chapters=chapter_count)
    thread = threading.Thread(
        target=_run_in_background,
        args=(task, config_path, chapter_count),
        daemon=True,
        name=f"poiesis-run-{task.task_id[:8]}",
    )
    thread.start()
    return task.to_dict()


def get_task(task_id: str) -> dict[str, Any] | None:
    """查询任务状态，不存在时返回 None。"""
    task = registry.get(task_id)
    return task.to_dict() if task else None
