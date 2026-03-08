"""书籍路由：创建、查询、更新按书配置。"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from poiesis.api.deps import get_db, require_admin
from poiesis.api.schemas.book import BookCreateRequest, BookItem, BookUpdateRequest
from poiesis.db.database import Database

router = APIRouter(prefix="/api/books", tags=["书籍"])


@router.get("", response_model=list[BookItem])
def list_books(db: Database = Depends(get_db)) -> list[BookItem]:
    """返回所有书籍（默认书在前）。"""
    rows = db.list_books()
    return [BookItem(**row) for row in rows]


@router.post("", response_model=BookItem)
def create_book(
    body: BookCreateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookItem:
    """创建书籍并返回详情。"""
    try:
        book_id = db.create_book(
            name=body.name.strip(),
            language=body.language.strip(),
            style_preset=body.style_preset.strip(),
            style_prompt=body.style_prompt,
            naming_policy=body.naming_policy.strip(),
            is_default=body.is_default,
        )
    except sqlite3.IntegrityError as exc:
        if "books.name" in str(exc):
            raise HTTPException(status_code=409, detail="书名已存在，请更换后重试") from exc
        raise HTTPException(status_code=422, detail=f"创建书籍失败：{exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"创建书籍失败：{exc}") from exc

    row = db.get_book(book_id)
    if row is None:
        raise HTTPException(status_code=500, detail="书籍创建后读取失败")
    return BookItem(**row)


@router.put("/{book_id}", response_model=BookItem)
def update_book(
    book_id: int,
    body: BookUpdateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookItem:
    """更新书籍配置。"""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail=f"书籍 id={book_id} 不存在")

    try:
        db.update_book(
            book_id=book_id,
            name=body.name.strip(),
            language=body.language.strip(),
            style_preset=body.style_preset.strip(),
            style_prompt=body.style_prompt,
            naming_policy=body.naming_policy.strip(),
            is_default=body.is_default,
        )
    except sqlite3.IntegrityError as exc:
        if "books.name" in str(exc):
            raise HTTPException(status_code=409, detail="书名已存在，请更换后重试") from exc
        raise HTTPException(status_code=422, detail=f"更新书籍失败：{exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"更新书籍失败：{exc}") from exc

    row = db.get_book(book_id)
    if row is None:
        raise HTTPException(status_code=500, detail="书籍更新后读取失败")
    return BookItem(**row)
