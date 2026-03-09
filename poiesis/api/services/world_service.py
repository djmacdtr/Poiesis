"""世界设定服务层，封装 Canon / Staging 数据的读写逻辑。"""

from __future__ import annotations

from typing import Any

from poiesis.db.database import Database
from poiesis.domain.world.repository import WorldRepository


def get_canon(db: Database, book_id: int | None = None) -> dict[str, Any]:
    """读取完整的 Canon 快照（世界规则、角色、时间线、伏笔）。"""
    repo = WorldRepository()
    book = book_id or 1
    world_rules = repo.list_world_rules(db, book_id=book)
    characters = repo.list_characters(db, book_id=book)
    timeline = repo.list_timeline_events(db, book_id=book)
    foreshadowing = repo.list_foreshadowing(db, book_id=book)

    return {
        "world_rules": world_rules,
        "characters": characters,
        "timeline": timeline,
        "foreshadowing": foreshadowing,
    }


def list_staging(
    db: Database,
    status: str | None = None,
    book_id: int | None = None,
) -> list[dict[str, Any]]:
    """返回 staging 变更列表。status 为 None 时返回全部。"""
    repo = WorldRepository()
    return repo.list_staging(db, status=status, book_id=book_id or 1)


def approve_staging(db: Database, change_id: int) -> dict[str, Any] | None:
    """批准指定 staging 变更，返回更新后的记录。"""
    repo = WorldRepository()
    return repo.mark_staging_approved(db, change_id)


def reject_staging(db: Database, change_id: int, reason: str) -> dict[str, Any] | None:
    """拒绝指定 staging 变更并记录原因，返回更新后的记录。"""
    repo = WorldRepository()
    return repo.mark_staging_rejected(db, change_id, reason)
