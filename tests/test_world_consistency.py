"""Tests for the WorldModel three-layer knowledge model."""

from __future__ import annotations

from typing import Any

import pytest

from poiesis.db.database import Database
from poiesis.domain.world.model import WorldModel


class TestWorldModelLayers:
    """Tests for canon, staging, and archive layer operations."""

    def test_initial_state(self) -> None:
        """A new WorldModel has empty canon, staging, and archive."""
        world = WorldModel()
        assert world.canon["characters"] == {}
        assert world.canon["world_rules"] == {}
        assert world.canon["timeline"] == {}
        assert world.canon["foreshadowing"] == {}
        assert world.staging == []
        assert world.archive == []

    def test_load_from_db_populates_canon(self, tmp_db: Database) -> None:
        """load_from_db fills all canon layers from the database."""
        tmp_db.upsert_world_rule(
            rule_key="gravity",
            description="Objects fall downward.",
            is_immutable=True,
        )
        tmp_db.upsert_character(
            name="TestChar",
            description="A test character.",
            core_motivation="Test.",
        )
        world = WorldModel()
        world.load_from_db(tmp_db)

        assert "gravity" in world.canon["world_rules"]
        assert "TestChar" in world.canon["characters"]

    def test_propose_change_adds_to_staging(self, sample_world: WorldModel) -> None:
        """propose_change appends a valid change to the staging list."""
        initial_count = len(sample_world.staging)
        change: dict[str, Any] = {
            "change_type": "upsert",
            "entity_type": "world_rule",
            "entity_key": "new_rule",
            "proposed_data": {"rule_key": "new_rule", "description": "A new rule."},
        }
        sample_world.propose_change(change)
        assert len(sample_world.staging) == initial_count + 1

    def test_propose_change_missing_keys_raises(self, sample_world: WorldModel) -> None:
        """propose_change raises ValueError when required keys are missing."""
        with pytest.raises(ValueError, match="missing required keys"):
            sample_world.propose_change({"change_type": "upsert"})

    def test_approve_change_moves_to_canon(self, tmp_db: Database) -> None:
        """approve_change moves a staging entry into the in-memory canon."""
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="world_rule",
            entity_key="flying_ships",
            proposed_data={"rule_key": "flying_ships", "description": "Ships can fly."},
            source_chapter=1,
        )

        world = WorldModel()
        world.load_from_db(tmp_db)

        assert "flying_ships" not in world.canon["world_rules"]
        world.approve_change(change_id, tmp_db)
        assert "flying_ships" in world.canon["world_rules"]

        # Staging list should no longer contain this change
        staging_ids = [s.get("id") for s in world.staging]
        assert change_id not in staging_ids

    def test_reject_change_moves_to_archive(self, tmp_db: Database) -> None:
        """reject_change moves a staging entry into the archive."""
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="BadChar",
            proposed_data={"name": "BadChar", "description": "Contradicts canon."},
            source_chapter=2,
        )

        world = WorldModel()
        world.load_from_db(tmp_db)

        world.reject_change(change_id, reason="Contradicts immutable rule.", db=tmp_db)

        # Should appear in archive with rejection reason
        reason = "Contradicts immutable rule."
        assert any(a.get("rejection_reason") == reason for a in world.archive)

        # Pending staging should not contain it
        pending = tmp_db.list_staging_changes(status="pending")
        assert not any(s["id"] == change_id for s in pending)

    def test_approve_nonexistent_change_raises(self, tmp_db: Database) -> None:
        """approve_change raises ValueError for a non-existent change id."""
        world = WorldModel()
        world.load_from_db(tmp_db)
        with pytest.raises(ValueError):
            world.approve_change(99999, tmp_db)

    def test_reject_nonexistent_change_raises(self, tmp_db: Database) -> None:
        """reject_change raises ValueError for a non-existent change id."""
        world = WorldModel()
        world.load_from_db(tmp_db)
        with pytest.raises(ValueError):
            world.reject_change(99999, reason="N/A", db=tmp_db)


class TestImmutableRules:
    """Tests ensuring immutable rules are correctly identified."""

    def test_get_immutable_rules_returns_only_immutable(self, sample_world: WorldModel) -> None:
        """get_immutable_rules returns only rules with is_immutable=True."""
        immutable = sample_world.get_immutable_rules()
        assert all(r.get("is_immutable") for r in immutable)
        keys = [r["rule_key"] for r in immutable]
        assert "magic_costs_life" in keys
        assert "dead_stay_dead" in keys
        # mutable_trade_rule should NOT be included
        assert "mutable_trade_rule" not in keys

    def test_world_context_summary_includes_rules(self, sample_world: WorldModel) -> None:
        """world_context_summary includes world rules and characters."""
        summary = sample_world.world_context_summary()
        assert "magic_costs_life" in summary
        assert "Aelindra Voss" in summary

    def test_world_context_summary_flags_immutable(self, sample_world: WorldModel) -> None:
        """world_context_summary marks immutable rules with [IMMUTABLE]."""
        summary = sample_world.world_context_summary(language="en-US")
        assert "[IMMUTABLE]" in summary
