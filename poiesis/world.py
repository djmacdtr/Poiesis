"""Three-layer world knowledge model for Poiesis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from poiesis.db.database import Database


class WorldModel:
    """Manages the three-layer world knowledge model.

    Layers
    ------
    canon
        Approved, immutable-from-generation-perspective world facts.
    staging
        Proposed changes extracted from generated chapters, awaiting review.
    archive
        Rejected staging changes, kept for audit purposes.
    """

    def __init__(self) -> None:
        """Initialise an empty WorldModel."""
        self.canon: dict[str, Any] = {
            "characters": {},
            "world_rules": {},
            "timeline": {},
            "foreshadowing": {},
        }
        self.staging: list[dict[str, Any]] = []
        self.archive: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_from_db(self, db: Database) -> None:
        """Populate the canon layer from the database.

        Args:
            db: Initialised :class:`~poiesis.db.database.Database` instance.
        """
        self.canon["characters"] = {c["name"]: c for c in db.list_characters()}
        self.canon["world_rules"] = {r["rule_key"]: r for r in db.list_world_rules()}
        self.canon["timeline"] = {e["event_key"]: e for e in db.list_timeline_events()}
        self.canon["foreshadowing"] = {f["hint_key"]: f for f in db.list_foreshadowing()}

        # Load pending staging changes
        self.staging = db.list_staging_changes(status="pending")

        # Load rejected archive changes
        self.archive = db.list_staging_changes(status="rejected")

    # ------------------------------------------------------------------
    # Staging operations
    # ------------------------------------------------------------------

    def propose_change(self, change: dict[str, Any]) -> None:
        """Add a proposed change to the staging layer.

        The change dict must contain at least: ``change_type``,
        ``entity_type``, ``entity_key``, ``proposed_data``.

        Args:
            change: Change descriptor dictionary.
        """
        required = {"change_type", "entity_type", "entity_key", "proposed_data"}
        missing = required - change.keys()
        if missing:
            raise ValueError(f"Change dict missing required keys: {missing}")
        self.staging.append(change)

    def approve_change(self, change_id: int, db: Database) -> None:
        """Move a staging change into the canon layer.

        Args:
            change_id: Database ``id`` of the staging change to approve.
            db: Initialised :class:`~poiesis.db.database.Database` instance.
        """
        change = db.get_staging_change(change_id)
        if change is None:
            raise ValueError(f"Staging change {change_id} not found")
        if change["status"] != "pending":
            raise ValueError(
                f"Cannot approve change {change_id}: status is '{change['status']}'"
            )

        db.update_staging_status(change_id, "approved")
        self._apply_to_canon(change)

        # Sync staging list
        self.staging = [s for s in self.staging if s.get("id") != change_id]

    def reject_change(self, change_id: int, reason: str, db: Database) -> None:
        """Move a staging change into the archive layer.

        Args:
            change_id: Database ``id`` of the staging change to reject.
            reason: Human-readable rejection reason.
            db: Initialised :class:`~poiesis.db.database.Database` instance.
        """
        change = db.get_staging_change(change_id)
        if change is None:
            raise ValueError(f"Staging change {change_id} not found")
        if change["status"] != "pending":
            raise ValueError(
                f"Cannot reject change {change_id}: status is '{change['status']}'"
            )

        db.update_staging_status(change_id, "rejected", rejection_reason=reason)
        change["rejection_reason"] = reason
        self.archive.append(change)

        self.staging = [s for s in self.staging if s.get("id") != change_id]

    # ------------------------------------------------------------------
    # Canon helpers
    # ------------------------------------------------------------------

    def _apply_to_canon(self, change: dict[str, Any]) -> None:
        """Apply an approved change to the in-memory canon."""
        entity_type: str = change["entity_type"]
        entity_key: str = change["entity_key"]
        data: dict[str, Any] = change["proposed_data"]

        layer_map = {
            "character": "characters",
            "world_rule": "world_rules",
            "timeline_event": "timeline",
            "foreshadowing": "foreshadowing",
        }
        layer = layer_map.get(entity_type)
        if layer is None:
            return

        if change["change_type"] == "delete":
            self.canon[layer].pop(entity_key, None)
        else:
            existing = self.canon[layer].get(entity_key, {})
            existing.update(data)
            self.canon[layer][entity_key] = existing

    def get_immutable_rules(self) -> list[dict[str, Any]]:
        """Return all world rules flagged as immutable."""
        return [r for r in self.canon["world_rules"].values() if r.get("is_immutable")]

    def world_context_summary(self, max_rules: int = 20) -> str:
        """Build a concise plain-text summary of the canon for use in prompts.

        Args:
            max_rules: Maximum number of world rules to include.

        Returns:
            Multi-line string describing the world state.
        """
        lines: list[str] = []

        rules = list(self.canon["world_rules"].values())[:max_rules]
        if rules:
            lines.append("=== World Rules ===")
            for r in rules:
                immutable = " [IMMUTABLE]" if r.get("is_immutable") else ""
                lines.append(f"- {r.get('rule_key', '')}{immutable}: {r.get('description', '')}")

        chars = list(self.canon["characters"].values())
        if chars:
            lines.append("\n=== Characters ===")
            for c in chars:
                lines.append(
                    f"- {c.get('name', '')}: {c.get('description', '')} "
                    f"(motivation: {c.get('core_motivation', 'unknown')})"
                )

        events = list(self.canon["timeline"].values())
        if events:
            lines.append("\n=== Timeline ===")
            for e in events:
                lines.append(
                    f"- [{e.get('timestamp_in_world', '?')}] {e.get('description', '')}"
                )

        hints = [h for h in self.canon["foreshadowing"].values() if h.get("status") == "pending"]
        if hints:
            lines.append("\n=== Pending Foreshadowing ===")
            for h in hints:
                lines.append(f"- {h.get('hint_key', '')}: {h.get('description', '')}")

        return "\n".join(lines)
