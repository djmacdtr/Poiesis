"""世界设定服务层，封装 Canon / Staging 数据的读写逻辑。"""

from __future__ import annotations

from typing import Any

from poiesis.db.database import Database
from poiesis.domain.world.repository import WorldRepository


def get_canon(db: Database, book_id: int | None = None) -> dict[str, Any]:
    """读取完整的 Canon 快照（世界规则、角色、时间线、伏笔）。"""
    repo = WorldRepository()
    book = book_id or 1
    snapshot = repo.load_world_state(db, book_id=book)
    canon = snapshot["canon"]

    return {
        "world_rules": list(canon["world_rules"].values()),
        "characters": list(canon["characters"].values()),
        "timeline": list(canon["timeline"].values()),
        "foreshadowing": list(canon["foreshadowing"].values()),
        "story_state": snapshot["story_state"],
        "world_blueprint_summary": snapshot.get("world_blueprint_summary") or None,
        "relationship_graph": snapshot.get("relationship_graph") or [],
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
