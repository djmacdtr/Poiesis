"""世界合并器，将已批准的暂存变更应用到 canon 层。"""

from __future__ import annotations

from typing import Any

from poiesis.db.database import Database
from poiesis.domain.world.model import WorldModel
from poiesis.vector_store.store import VectorStore


class WorldMerger:
    """Merges approved staging changes into canon and updates the vector store."""

    def merge(
        self,
        approved_changes: list[dict[str, Any]],
        world: WorldModel,
        db: Database,
        vector_store: VectorStore,
    ) -> int:
        merged = 0
        for change in approved_changes:
            try:
                self._persist(change, db)
                world._apply_to_canon(change)
                self._index(change, vector_store)
                merged += 1
            except Exception:
                import traceback

                traceback.print_exc()
        return merged

    def _persist(self, change: dict[str, Any], db: Database) -> None:
        entity_type: str = change["entity_type"]
        data: dict[str, Any] = change["proposed_data"]
        book_id = int(change.get("book_id") or 1)

        if entity_type == "character":
            db.upsert_character(
                name=data.get("name", change["entity_key"]),
                book_id=book_id,
                description=data.get("description"),
                core_motivation=data.get("core_motivation"),
                attributes=data.get("attributes", {}),
                status=data.get("status", "active"),
            )
        elif entity_type == "world_rule":
            db.upsert_world_rule(
                rule_key=data.get("rule_key", change["entity_key"]),
                description=data.get("description", ""),
                book_id=book_id,
                is_immutable=bool(data.get("is_immutable", False)),
                category=data.get("category"),
            )
        elif entity_type == "timeline_event":
            db.upsert_timeline_event(
                event_key=data.get("event_key", change["entity_key"]),
                description=data.get("description", ""),
                book_id=book_id,
                chapter_number=data.get("chapter_number"),
                characters_involved=data.get("characters_involved", []),
                timestamp_in_world=data.get("timestamp_in_world"),
            )
        elif entity_type == "foreshadowing":
            db.upsert_foreshadowing(
                hint_key=data.get("hint_key", change["entity_key"]),
                description=data.get("description", ""),
                book_id=book_id,
                introduced_in_chapter=data.get("introduced_in_chapter"),
                resolved_in_chapter=data.get("resolved_in_chapter"),
                status=data.get("status", "pending"),
            )

    def _index(self, change: dict[str, Any], vector_store: VectorStore) -> None:
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

