"""章节服务层，封装章节数据的读取逻辑。"""

from __future__ import annotations

from typing import Any

from poiesis.db.database import Database

# 数据库章节状态 → 前端期望状态的映射
_STATUS_MAP: dict[str, str] = {
    "final": "completed",
    "flagged": "draft",
    "draft": "draft",
    "needs_review": "needs_review",
    "ready_to_publish": "ready_to_publish",
    "published": "published",
}


def _map_status(raw: str | None) -> str:
    """将数据库 status 值映射为前端可识别的值。"""
    return _STATUS_MAP.get(raw or "draft", raw or "draft")


def _normalize_chapter(row: dict[str, Any]) -> dict[str, Any]:
    """标准化章节记录，统一处理空值与状态映射。"""
    row = dict(row)
    row["title"] = row.get("title") or ""
    row["status"] = _map_status(row.get("status"))
    # 确保时间字段存在
    row.setdefault("created_at", "")
    row.setdefault("updated_at", "")
    return row


def list_chapters(db: Database, book_id: int = 1) -> list[dict[str, Any]]:
    """返回所有章节的摘要列表（不含正文）。"""
    rows = db.list_chapters(book_id=book_id)
    return [_normalize_chapter(r) for r in rows]


def get_chapter(db: Database, chapter_id: int, book_id: int = 1) -> dict[str, Any] | None:
    """按章节行 id（primary key）查询章节详情，不存在时返回 None。"""
    row = db.get_chapter_by_id(chapter_id, book_id=book_id)
    if row is None:
        return None
    return _normalize_chapter(row)
