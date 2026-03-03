"""世界设定服务层，封装 Canon / Staging 数据的读写逻辑。"""

from __future__ import annotations

from poiesis.db.database import Database


def get_canon(db: Database) -> dict:
    """读取完整的 Canon 快照（世界规则、角色、时间线、伏笔）。"""
    world_rules = db.list_world_rules()
    characters = db.list_characters()
    timeline = db.list_timeline_events()
    foreshadowing = db.list_foreshadowing()

    # 标准化 is_immutable：SQLite 存储为 0/1，转换为 bool
    for rule in world_rules:
        rule["is_immutable"] = bool(rule.get("is_immutable", 0))
        rule.setdefault("created_at", "")

    for char in characters:
        char.setdefault("description", "")
        char.setdefault("core_motivation", "")
        char.setdefault("attributes", {})
        char.setdefault("status", "active")
        char.setdefault("created_at", "")
        char.setdefault("updated_at", "")

    for event in timeline:
        event.setdefault("characters_involved", [])
        event.setdefault("created_at", "")

    for hint in foreshadowing:
        hint.setdefault("created_at", "")

    return {
        "world_rules": world_rules,
        "characters": characters,
        "timeline": timeline,
        "foreshadowing": foreshadowing,
    }


def list_staging(db: Database, status: str | None = None) -> list[dict]:
    """返回 staging 变更列表。status 为 None 时返回全部。"""
    rows = db.list_staging_changes(status=status)
    for row in rows:
        row.setdefault("rejection_reason", None)
        row.setdefault("source_chapter", None)
        row.setdefault("created_at", "")
    return rows


def approve_staging(db: Database, change_id: int) -> dict | None:
    """批准指定 staging 变更，返回更新后的记录。"""
    change = db.get_staging_change(change_id)
    if change is None:
        return None
    db.update_staging_status(change_id, "approved")
    change["status"] = "approved"
    change.setdefault("rejection_reason", None)
    change.setdefault("source_chapter", None)
    change.setdefault("created_at", "")
    return change


def reject_staging(db: Database, change_id: int, reason: str) -> dict | None:
    """拒绝指定 staging 变更并记录原因，返回更新后的记录。"""
    change = db.get_staging_change(change_id)
    if change is None:
        return None
    db.update_staging_status(change_id, "rejected", rejection_reason=reason)
    change["status"] = "rejected"
    change["rejection_reason"] = reason
    change.setdefault("source_chapter", None)
    change.setdefault("created_at", "")
    return change
