"""世界状态仓储与装载逻辑。"""

from __future__ import annotations

from typing import Any

if False:  # pragma: no cover
    from poiesis.db.database import Database


class WorldRepository:
    """负责从持久化层装载世界状态。"""

    def list_world_rules(self, db: Database, book_id: int = 1) -> list[dict[str, Any]]:
        """读取并标准化世界规则，避免上层重复处理 SQLite 字段差异。"""
        rows = db.list_world_rules(book_id=book_id)
        for row in rows:
            row["is_immutable"] = bool(row.get("is_immutable", 0))
            row.setdefault("created_at", "")
        return rows

    def list_characters(self, db: Database, book_id: int = 1) -> list[dict[str, Any]]:
        """读取并标准化角色快照。"""
        rows = db.list_characters(book_id=book_id)
        for row in rows:
            row.setdefault("description", "")
            row.setdefault("core_motivation", "")
            row.setdefault("attributes", {})
            row.setdefault("status", "active")
            row.setdefault("created_at", "")
            row.setdefault("updated_at", "")
        return rows

    def list_timeline_events(self, db: Database, book_id: int = 1) -> list[dict[str, Any]]:
        """读取并标准化时间线事件。"""
        rows = db.list_timeline_events(book_id=book_id)
        for row in rows:
            row.setdefault("characters_involved", [])
            row.setdefault("created_at", "")
        return rows

    def list_foreshadowing(self, db: Database, book_id: int = 1) -> list[dict[str, Any]]:
        """读取并标准化伏笔列表。"""
        rows = db.list_foreshadowing(book_id=book_id)
        for row in rows:
            row.setdefault("created_at", "")
        return rows

    def list_staging(
        self,
        db: Database,
        status: str | None = None,
        book_id: int = 1,
    ) -> list[dict[str, Any]]:
        """读取并标准化 staging 记录。"""
        rows = db.list_staging_changes(status=status, book_id=book_id)
        for row in rows:
            row.setdefault("rejection_reason", None)
            row.setdefault("source_chapter", None)
            row.setdefault("created_at", "")
        return rows

    def get_staging_change(self, db: Database, change_id: int) -> dict[str, Any] | None:
        """读取单条 staging 记录并补齐兼容字段。"""
        row = db.get_staging_change(change_id)
        if row is None:
            return None
        row.setdefault("rejection_reason", None)
        row.setdefault("source_chapter", None)
        row.setdefault("created_at", "")
        return row

    def mark_staging_approved(self, db: Database, change_id: int) -> dict[str, Any] | None:
        """把 staging 记录标记为 approved，并返回最新记录。"""
        change = self.get_staging_change(db, change_id)
        if change is None:
            return None
        db.update_staging_status(change_id, "approved")
        change["status"] = "approved"
        return change

    def mark_staging_rejected(
        self,
        db: Database,
        change_id: int,
        reason: str,
    ) -> dict[str, Any] | None:
        """把 staging 记录标记为 rejected，并带回 rejection_reason。"""
        change = self.get_staging_change(db, change_id)
        if change is None:
            return None
        db.update_staging_status(change_id, "rejected", rejection_reason=reason)
        change["status"] = "rejected"
        change["rejection_reason"] = reason
        return change

    def build_canon_snapshot(self, db: Database, book_id: int = 1) -> dict[str, Any]:
        """聚合 canon 四层快照，供 WorldModel 和 API 共用。"""
        return {
            "characters": {c["name"]: c for c in self.list_characters(db, book_id=book_id)},
            "world_rules": {r["rule_key"]: r for r in self.list_world_rules(db, book_id=book_id)},
            "timeline": {e["event_key"]: e for e in self.list_timeline_events(db, book_id=book_id)},
            "foreshadowing": {f["hint_key"]: f for f in self.list_foreshadowing(db, book_id=book_id)},
        }

    def load_world_state(self, db: Database, book_id: int = 1) -> dict[str, Any]:
        """读取某本书的 canon / staging / archive 快照。"""
        return {
            "canon": self.build_canon_snapshot(db, book_id=book_id),
            "staging": self.list_staging(db, status="pending", book_id=book_id),
            "archive": self.list_staging(db, status="rejected", book_id=book_id),
            "story_state": {},
            "loop_state": [],
        }
