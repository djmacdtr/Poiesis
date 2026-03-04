"""内存任务注册表（TaskRegistry）。

注意：进程重启后任务状态将丢失，MVP 允许此限制。
如需持久化，可将任务状态写入 SQLite 或 Redis。
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from threading import Lock
from typing import Any

# 日志环形缓冲区最大行数
_MAX_LOG_LINES = 200


class TaskInfo:
    """单个任务的状态与日志信息。"""

    def __init__(self, task_id: str, total_chapters: int) -> None:
        self.task_id = task_id
        self.status: str = "pending"  # pending / running / completed / failed
        self.total_chapters: int = total_chapters
        self.current_chapter: int = 0
        self.error: str | None = None
        self.created_at: str = datetime.now(UTC).isoformat()
        self.updated_at: str = self.created_at
        # 最近 N 行日志（环形缓冲）
        self._logs: deque[str] = deque(maxlen=_MAX_LOG_LINES)

    def add_log(self, message: str) -> None:
        """追加一条日志，并更新 updated_at。"""
        self._logs.append(message)
        self.updated_at = datetime.now(UTC).isoformat()

    @property
    def logs(self) -> list[str]:
        """返回当前日志列表（最新的在末尾）。"""
        return list(self._logs)

    @property
    def progress(self) -> float | None:
        """返回进度百分比（0~1），未开始时返回 None。"""
        if self.total_chapters <= 0:
            return None
        return self.current_chapter / self.total_chapters

    def to_dict(self) -> dict[str, Any]:
        """导出为字典，供 Pydantic schema 使用。"""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "current_chapter": self.current_chapter if self.current_chapter > 0 else None,
            "total_chapters": self.total_chapters,
            "logs": self.logs,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TaskRegistry:
    """全局内存任务注册表，线程安全。"""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = Lock()

    def create(self, total_chapters: int) -> TaskInfo:
        """创建一个新任务并返回 TaskInfo 对象。"""
        task_id = str(uuid.uuid4())
        task = TaskInfo(task_id=task_id, total_chapters=total_chapters)
        with self._lock:
            self._tasks[task_id] = task
        return task

    def get(self, task_id: str) -> TaskInfo | None:
        """按 task_id 查询任务，不存在时返回 None。"""
        with self._lock:
            return self._tasks.get(task_id)

    def all_tasks(self) -> list[TaskInfo]:
        """返回全部任务列表。"""
        with self._lock:
            return list(self._tasks.values())


# 应用级单例注册表
registry = TaskRegistry()
