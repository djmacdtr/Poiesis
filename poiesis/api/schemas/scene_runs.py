"""Scene 驱动运行 API 的请求与响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from poiesis.application.scene_contracts import (
    ChapterOutput,
    ChapterTrace,
    LoopState,
    ReviewQueueItem,
    RunSummary,
    SceneTrace,
)


class StartRunRequest(BaseModel):
    """启动新 run。"""

    book_id: int = Field(default=1, ge=1)
    chapter_count: int = Field(default=1, ge=1, le=50)


class StartRunResponse(BaseModel):
    """启动 run 的返回。"""

    task_id: str
    status: str
    run_id: int | None = None


class RunDetailResponse(BaseModel):
    """run 详情。"""

    run: RunSummary
    chapters: list[dict[str, Any]]


class ChapterDetailResponse(BaseModel):
    """章节详情。"""

    trace: ChapterTrace
    output: ChapterOutput | None = None


class SceneDetailResponse(BaseModel):
    """scene 详情。"""

    scene: SceneTrace
    patches: list[dict[str, Any]] = Field(default_factory=list)


class ReviewListResponse(BaseModel):
    """审阅队列。"""

    items: list[ReviewQueueItem]


class ReviewActionRequest(BaseModel):
    """审阅动作请求。"""

    patch_text: str = ""


class LoopListResponse(BaseModel):
    """loop 列表。"""

    items: list[LoopState]
