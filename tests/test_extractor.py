"""Tests for the FactExtractor."""

from __future__ import annotations

from poiesis.extractor import FactExtractor
from poiesis.world import WorldModel


class TestFactExtractorCharacters:
    """Tests for character extraction."""

    def test_extracts_new_characters(
        self, sample_world: WorldModel
    ) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [
                    {
                        "name": "Gideon Thorne",
                        "description": "A rogue scholar.",
                        "core_motivation": "Uncover the truth of the Shattering.",
                        "attributes": {"age": 35},
                    }
                ],
                "new_world_rules": [],
                "timeline_events": [],
                "foreshadowing": [],
                "character_updates": [],
            }
        )
        extractor = FactExtractor()
        changes = extractor.extract(2, "Chapter content.", sample_world, llm)

        char_changes = [c for c in changes if c["entity_type"] == "character"]
        assert len(char_changes) == 1
        assert char_changes[0]["entity_key"] == "Gideon Thorne"
        assert char_changes[0]["change_type"] == "upsert"
        assert char_changes[0]["source_chapter"] == 2

    def test_skips_characters_without_name(
        self, sample_world: WorldModel
    ) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [{"description": "No name provided."}],
                "new_world_rules": [],
                "timeline_events": [],
                "foreshadowing": [],
                "character_updates": [],
            }
        )
        extractor = FactExtractor()
        changes = extractor.extract(1, "Content.", sample_world, llm)
        char_changes = [c for c in changes if c["entity_type"] == "character"]
        assert len(char_changes) == 0


class TestFactExtractorWorldRules:
    """Tests for world rule extraction."""

    def test_extracts_new_world_rules(
        self, sample_world: WorldModel
    ) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [],
                "new_world_rules": [
                    {
                        "rule_key": "sky_whales_exist",
                        "description": "Enormous whales drift through the sky void.",
                        "is_immutable": False,
                        "category": "fauna",
                    }
                ],
                "timeline_events": [],
                "foreshadowing": [],
                "character_updates": [],
            }
        )
        extractor = FactExtractor()
        changes = extractor.extract(3, "Content about sky whales.", sample_world, llm)

        rule_changes = [c for c in changes if c["entity_type"] == "world_rule"]
        assert len(rule_changes) == 1
        assert rule_changes[0]["entity_key"] == "sky_whales_exist"

    def test_skips_rules_without_key(
        self, sample_world: WorldModel
    ) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [],
                "new_world_rules": [{"description": "No key provided."}],
                "timeline_events": [],
                "foreshadowing": [],
                "character_updates": [],
            }
        )
        extractor = FactExtractor()
        changes = extractor.extract(1, "Content.", sample_world, llm)
        rule_changes = [c for c in changes if c["entity_type"] == "world_rule"]
        assert len(rule_changes) == 0


class TestFactExtractorMixed:
    """Tests for mixed extraction results."""

    def test_extracts_all_categories(
        self, sample_world: WorldModel
    ) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [{"name": "NPC One", "description": "An NPC."}],
                "new_world_rules": [
                    {"rule_key": "rule_one", "description": "A rule.", "is_immutable": False}
                ],
                "timeline_events": [
                    {"event_key": "event_one", "description": "An event.", "chapter_number": 4}
                ],
                "foreshadowing": [
                    {"hint_key": "hint_one", "description": "A hint.", "status": "pending"}
                ],
                "character_updates": [
                    {"name": "Aelindra Voss", "description": "Updated description."}
                ],
            }
        )
        extractor = FactExtractor()
        changes = extractor.extract(4, "Rich chapter content.", sample_world, llm)

        types = {c["entity_type"] for c in changes}
        assert "character" in types
        assert "world_rule" in types
        assert "timeline_event" in types
        assert "foreshadowing" in types

        # Character updates should produce "update" change_type
        updates = [c for c in changes if c["change_type"] == "update"]
        assert len(updates) == 1
        assert updates[0]["entity_key"] == "Aelindra Voss"

    def test_empty_llm_response_returns_empty_list(
        self, sample_world: WorldModel
    ) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [],
                "new_world_rules": [],
                "timeline_events": [],
                "foreshadowing": [],
                "character_updates": [],
            }
        )
        extractor = FactExtractor()
        changes = extractor.extract(1, "Content.", sample_world, llm)
        assert changes == []
