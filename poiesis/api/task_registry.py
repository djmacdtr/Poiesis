"""任务注册表（TaskRegistry）。

默认将任务状态持久化到本地 JSON 文件，避免开发模式热重载后任务直接丢失。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Callable

# 日志环形缓冲区最大行数
_MAX_LOG_LINES = 200
_MAX_PREVIEW_CHARS = 12000
_INVALID_COMPLETED_MSG = (
    "任务状态异常：记录显示已完成，但未记录任何章节进度。"
    "可能是服务重载或测试数据残留导致，请重新发起生成。"
)


class TaskInfo:
    """单个任务的状态与日志信息。"""

    def __init__(
        self,
        task_id: str,
        total_chapters: int,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.task_id = task_id
        self._status: str = "pending"  # pending / running / completed / failed / interrupted
        self.total_chapters: int = total_chapters
        self._current_chapter: int = 0
        self._error: str | None = None
        self._preview_text: str = ""
        self._preview_last_touch: float = 0.0
        self.created_at: str = datetime.now(UTC).isoformat()
        self.updated_at: str = self.created_at
        # 最近 N 行日志（环形缓冲）
        self._logs: deque[str] = deque(maxlen=_MAX_LOG_LINES)
        self._on_change = on_change

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        self._status = value
        self._touch()

    @property
    def current_chapter(self) -> int:
        return self._current_chapter

    @current_chapter.setter
    def current_chapter(self, value: int) -> None:
        self._current_chapter = value
        self._touch()

    @property
    def error(self) -> str | None:
        return self._error

    @error.setter
    def error(self, value: str | None) -> None:
        self._error = value
        self._touch()

    @property
    def preview_text(self) -> str:
        return self._preview_text

    def reset_preview(self) -> None:
        self._preview_text = ""
        self._touch()

    def append_preview(self, chunk: str) -> None:
        """Append preview text with a bounded buffer and throttled disk persistence."""
        if not chunk:
            return

        self._preview_text += chunk
        if len(self._preview_text) > _MAX_PREVIEW_CHARS:
            self._preview_text = self._preview_text[-_MAX_PREVIEW_CHARS:]

        now = time.monotonic()
        if now - self._preview_last_touch >= 0.8:
            self._preview_last_touch = now
            self._touch()

    def flush_preview(self) -> None:
        """Force-persist preview updates before task state transitions."""
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()
        if self._on_change:
            self._on_change()

    def add_log(self, message: str) -> None:
        """追加一条日志，并更新 updated_at。"""
        self._logs.append(message)
        self._touch()

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
            "preview_text": self.preview_text if self.preview_text else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        on_change: Callable[[], None] | None = None,
    ) -> "TaskInfo":
        task = cls(
            task_id=payload.get("task_id", str(uuid.uuid4())),
            total_chapters=int(payload.get("total_chapters", 0)),
            on_change=on_change,
        )
        task._status = str(payload.get("status", "pending"))
        task._current_chapter = int(payload.get("current_chapter") or 0)
        task._error = payload.get("error")
        task._preview_text = str(payload.get("preview_text") or "")
        task.created_at = payload.get("created_at") or datetime.now(UTC).isoformat()
        task.updated_at = payload.get("updated_at") or task.created_at
        logs = payload.get("logs") or []
        task._logs.extend([str(line) for line in logs])
        return task


class TaskRegistry:
    """全局内存任务注册表，线程安全。"""

    def __init__(self, storage_path: str | None = None) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = Lock()
        self._storage_path = storage_path or os.environ.get(
            "POIESIS_TASK_REGISTRY_PATH", "data/task_registry.json"
        )
        self._load_from_storage()

    def _storage_file(self) -> Path:
        return Path(self._storage_path)

    def _persist(self) -> None:
        with self._lock:
            snapshot = [task.to_dict() for task in self._tasks.values()]

        storage_file = self._storage_file()
        storage_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = storage_file.with_suffix(storage_file.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(storage_file)

    def _load_from_storage(self) -> None:
        storage_file = self._storage_file()
        if not storage_file.exists():
            return

        try:
            raw = json.loads(storage_file.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(raw, list):
            return

        recovered = False
        for item in raw:
            if not isinstance(item, dict):
                continue
            task = TaskInfo.from_dict(item, on_change=self._persist)
            if task.status in ("pending", "running"):
                recovered = True
                task.status = "interrupted"
                task.error = "服务发生热重载或重启，原任务已中断，请重新发起生成。"
                task.add_log(task.error)
            # 防御性修复：历史数据中出现“已完成但 0 进度”时，标记为异常终态，避免误导前端。
            elif (
                task.status == "completed"
                and task.total_chapters > 0
                and task.current_chapter <= 0
            ):
                recovered = True
                task.status = "failed"
                task.error = _INVALID_COMPLETED_MSG
                if not task.logs:
                    task.add_log(_INVALID_COMPLETED_MSG)
            self._tasks[task.task_id] = task

        if recovered:
            self._persist()

    def create(self, total_chapters: int) -> TaskInfo:
        """创建一个新任务并返回 TaskInfo 对象。"""
        task_id = str(uuid.uuid4())
        task = TaskInfo(task_id=task_id, total_chapters=total_chapters, on_change=self._persist)
        with self._lock:
            self._tasks[task_id] = task
        self._persist()
        return task

    def get(self, task_id: str) -> TaskInfo | None:
        """按 task_id 查询任务，不存在时返回 None。"""
        with self._lock:
            return self._tasks.get(task_id)

    def all_tasks(self) -> list[TaskInfo]:
        """返回全部任务列表。"""
        with self._lock:
            return list(self._tasks.values())

    def prune_history(self, keep_recent: int) -> int:
        """清理历史任务，保留运行中任务与最近 N 条已结束任务。"""
        keep_recent = max(0, keep_recent)
        active_statuses = {"pending", "running"}

        with self._lock:
            tasks = list(self._tasks.values())
            active_tasks = [task for task in tasks if task.status in active_statuses]
            terminal_tasks = [task for task in tasks if task.status not in active_statuses]
            terminal_tasks.sort(key=lambda task: task.updated_at, reverse=True)

            keep_ids = {task.task_id for task in active_tasks}
            keep_ids.update(task.task_id for task in terminal_tasks[:keep_recent])

            before = len(self._tasks)
            self._tasks = {task_id: task for task_id, task in self._tasks.items() if task_id in keep_ids}
            removed = before - len(self._tasks)

        if removed > 0:
            self._persist()
        return removed


# 应用级单例注册表
registry = TaskRegistry()
