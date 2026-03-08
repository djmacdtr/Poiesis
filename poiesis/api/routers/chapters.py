"""章节路由：GET /api/chapters, GET /api/chapters/{id}。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from poiesis.api.deps import get_db
from poiesis.api.schemas.chapter import Chapter, ChapterSummaryItem
from poiesis.api.services import chapter_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/chapters", tags=["章节"])


@router.get("", response_model=list[ChapterSummaryItem])
def list_chapters(
    book_id: int = Query(default=1, ge=1),
    db: Database = Depends(get_db),
) -> list[ChapterSummaryItem]:
    """获取所有章节的摘要列表（不含正文）。"""
    rows = chapter_service.list_chapters(db, book_id=book_id)
    return [ChapterSummaryItem(**r) for r in rows]


@router.get("/{chapter_id}", response_model=Chapter)
def get_chapter(
    chapter_id: int,
    book_id: int = Query(default=1, ge=1),
    db: Database = Depends(get_db),
) -> Chapter:
    """按章节行 id 获取章节详情（含正文与计划）。"""
    row = chapter_service.get_chapter(db, chapter_id, book_id=book_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"章节 id={chapter_id} 不存在")
    return Chapter(**row)
