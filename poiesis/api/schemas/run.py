"""运行任务相关响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

TaskStatus = Literal["pending", "running", "completed", "failed", "interrupted"]


class RunRequest(BaseModel):
    """启动写作任务请求体。"""

    chapter_count: int = 1
    book_id: int = 1


class RunResponse(BaseModel):
    """启动任务响应，对应前端 RunResponse 类型。"""

    task_id: str
    status: TaskStatus
    message: str | None = None


class TaskDetail(BaseModel):
    """任务详情（轮询用），对应前端 TaskDetail 类型。"""

    task_id: str
    status: TaskStatus
    progress: float | None = None
    current_chapter: int | None = None
    total_chapters: int | None = None
    logs: list[str] = []
    error: str | None = None
    preview_text: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
