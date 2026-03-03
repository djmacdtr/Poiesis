"""世界合并器，将已批准的暂存变更应用到 canon 层。"""

from __future__ import annotations

from typing import Any

from poiesis.db.database import Database
from poiesis.vector_store.store import VectorStore
from poiesis.world import WorldModel


class WorldMerger:
    """Merges approved staging changes into canon and updates the vector store."""

    def merge(
        self,
        approved_changes: list[dict[str, Any]],
        world: WorldModel,
        db: Database,
        vector_store: VectorStore,
    ) -> int:
        """Apply a list of approved changes to the canon.

        For each change:
        1. Persist to the appropriate DB table.
        2. Apply to the in-memory canon.
        3. Upsert in the vector store for future retrieval.

        Args:
            approved_changes: List of staging-change dicts that have been
                approved (each must have ``change_type``, ``entity_type``,
                ``entity_key``, ``proposed_data``).
            world: :class:`~poiesis.world.WorldModel` whose canon will be
                updated in-memory.
            db: :class:`~poiesis.db.database.Database` for persistence.
            vector_store: :class:`~poiesis.vector_store.store.VectorStore`
                for semantic indexing.

        Returns:
            Number of changes successfully merged.
        """
        merged = 0
        for change in approved_changes:
            try:
                self._persist(change, db)
                world._apply_to_canon(change)
                self._index(change, vector_store)
                merged += 1
            except Exception:
                # 单个变更失败不应阻断其他变更的处理，记录错误后继续执行
                import traceback

                traceback.print_exc()
        return merged

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _persist(self, change: dict[str, Any], db: Database) -> None:
        """Write the change to the appropriate database table."""
        entity_type: str = change["entity_type"]
        data: dict[str, Any] = change["proposed_data"]

        if entity_type == "character":
            db.upsert_character(
                name=data.get("name", change["entity_key"]),
                description=data.get("description"),
                core_motivation=data.get("core_motivation"),
                attributes=data.get("attributes", {}),
                status=data.get("status", "active"),
            )
        elif entity_type == "world_rule":
            db.upsert_world_rule(
                rule_key=data.get("rule_key", change["entity_key"]),
                description=data.get("description", ""),
                is_immutable=bool(data.get("is_immutable", False)),
                category=data.get("category"),
            )
        elif entity_type == "timeline_event":
            db.upsert_timeline_event(
                event_key=data.get("event_key", change["entity_key"]),
                description=data.get("description", ""),
                chapter_number=data.get("chapter_number"),
                characters_involved=data.get("characters_involved", []),
                timestamp_in_world=data.get("timestamp_in_world"),
            )
        elif entity_type == "foreshadowing":
            db.upsert_foreshadowing(
                hint_key=data.get("hint_key", change["entity_key"]),
                description=data.get("description", ""),
                introduced_in_chapter=data.get("introduced_in_chapter"),
                resolved_in_chapter=data.get("resolved_in_chapter"),
                status=data.get("status", "pending"),
            )

    def _index(self, change: dict[str, Any], vector_store: VectorStore) -> None:
        """Add or update the change in the vector store."""
        if change["change_type"] == "delete":
            vector_store.remove(change["entity_key"])
            return

        data: dict[str, Any] = change["proposed_data"]
        description = data.get("description", "")
        if not description:
            return

        vector_store.add(
            key=f"{change['entity_type']}:{change['entity_key']}",
            text=description,
            metadata={
                "entity_type": change["entity_type"],
                "entity_key": change["entity_key"],
            },
        )
