"""章节相关响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChapterSummaryItem(BaseModel):
    """章节列表项（不含正文），对应前端 ChapterSummaryItem 类型。"""

    id: int
    chapter_number: int
    title: str | None
    word_count: int
    # 状态映射：数据库的 'final' → 'completed'，'flagged' → 'draft'
    status: str
    created_at: str
    updated_at: str


class ChapterPlan(BaseModel):
    """章节写作计划（JSON 对象）。"""

    outline: str | None = None
    key_events: list[str] | None = None
    characters: list[str] | None = None

    model_config = {"extra": "allow"}


class Chapter(ChapterSummaryItem):
    """章节详情（含正文与计划），对应前端 Chapter 类型。"""

    content: str
    plan: dict[str, Any] | None = None
