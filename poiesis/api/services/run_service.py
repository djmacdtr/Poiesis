"""运行任务服务层，在后台线程中执行 RunLoop 并记录日志。"""

from __future__ import annotations

import os
import threading
from typing import Any

from poiesis.api.task_registry import TaskInfo, registry

_PROVIDER_TO_KEY = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
}


def _validate_llm_key_prerequisites(loop: Any) -> None:
    """Validate that effective writer/planner providers have corresponding API keys."""

    missing: list[str] = []
    checks = [
        ("写作模型", loop._config.llm.provider, loop._config.llm.model),
        ("规划模型", loop._config.planner_llm.provider, loop._config.planner_llm.model),
    ]

    for role, provider, model in checks:
        key_name = _PROVIDER_TO_KEY.get(provider)
        if not key_name:
            continue

        key_from_db = loop._load_key_from_db(key_name)
        key_from_env = os.environ.get(key_name)
        if not (key_from_db or key_from_env):
            missing.append(f"{role}（{provider} / {model}）缺少 {key_name}")

    if missing:
        details = "；".join(missing)
        raise ValueError(
            "模型配置校验失败："
            f"{details}。"
            "请在【系统设置 -> API Key 配置】补齐后重试。"
        )


def _run_in_background(task: TaskInfo, config_path: str, chapter_count: int) -> None:
    """后台线程函数：初始化 RunLoop 并逐章生成，将进度写入任务日志。

    此函数在独立线程中运行。若服务热重载/重启，运行中的任务会被标记为中断，
    并提示用户重新发起生成。
    """
    # 延迟导入，避免启动时加载 LLM 依赖
    from poiesis.run_loop import RunLoop

    task.status = "running"
    task.add_log("任务开始：初始化生成器…")

    try:
        loop = RunLoop(config_path=config_path)
        task.add_log(f"配置来源：{config_path}")
        task.add_log(f"数据库路径：{loop._config.database.path}")
        task.add_log(
            "生效模型："
            f"写作={loop._config.llm.provider}/{loop._config.llm.model}；"
            f"规划={loop._config.planner_llm.provider}/{loop._config.planner_llm.model}"
        )
        task.add_log("检查模型配置…")
        _validate_llm_key_prerequisites(loop)
        task.add_log("模型配置检查通过。")

        task.add_log("加载世界种子…")
        loop.load_world_seed()

        existing = loop._db.list_chapters()
        start_chapter = len(existing) + 1
        end_chapter = start_chapter + chapter_count - 1

        task.add_log(f"准备生成第 {start_chapter} 至第 {end_chapter} 章…")

        for i, chapter_number in enumerate(range(start_chapter, end_chapter + 1), start=1):
            task.add_log(f"开始规划第 {chapter_number} 章…")
            task.reset_preview()
            loop._generate_chapter(chapter_number, on_writer_delta=task.append_preview)
            task.flush_preview()
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


def list_tasks() -> list[dict[str, Any]]:
    """返回全部任务（按最近更新时间倒序）。"""
    tasks = [task.to_dict() for task in registry.all_tasks()]
    return sorted(tasks, key=lambda item: item.get("updated_at") or "", reverse=True)


def prune_task_history(keep_recent: int) -> dict[str, int]:
    """清理历史任务，返回删除数量与剩余任务数量。"""
    removed = registry.prune_history(keep_recent=keep_recent)
    remaining = len(registry.all_tasks())
    return {"removed": removed, "remaining": remaining}
