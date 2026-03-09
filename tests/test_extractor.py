"""ExtractorHub 提取分类测试。"""

from __future__ import annotations

from poiesis.domain.world.model import WorldModel
from poiesis.pipeline.extraction.extractor_hub import ExtractorHub


class TestExtractorHubCharacters:
    """角色变更提取测试。"""

    def test_extracts_new_characters(self, sample_world: WorldModel) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [
                    {
                        "name": "Gideon Thorne",
                        "description": "A rogue scholar.",
                        "core_motivation": "Uncover the truth.",
                        "attributes": {"age": 35},
                    }
                ],
                "new_world_rules": [],
                "timeline_events": [],
                "foreshadowing": [],
                "character_updates": [],
            }
        )
        changes = ExtractorHub().extract(2, "Chapter content.", sample_world, llm)

        assert len(changes.characters) == 1
        assert changes.characters[0]["entity_key"] == "Gideon Thorne"
        assert changes.characters[0]["change_type"] == "upsert"

    def test_skips_characters_without_name(self, sample_world: WorldModel) -> None:
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
        changes = ExtractorHub().extract(1, "Content.", sample_world, llm)
        assert changes.characters == []


class TestExtractorHubMixed:
    """混合分类测试。"""

    def test_extracts_all_categories(self, sample_world: WorldModel) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [{"name": "NPC One", "description": "An NPC."}],
                "new_world_rules": [{"rule_key": "rule_one", "description": "A rule."}],
                "timeline_events": [{"event_key": "event_one", "description": "An event."}],
                "foreshadowing": [{"hint_key": "hint_one", "description": "A hint.", "status": "pending"}],
                "character_updates": [{"name": "Aelindra Voss", "description": "Updated description."}],
                "uncertain_claims": ["某处时间顺序可能有误"],
            }
        )
        changes = ExtractorHub().extract(4, "Rich chapter content.", sample_world, llm)

        assert len(changes.characters) == 2
        assert len(changes.world_rules) == 1
        assert len(changes.timeline_events) == 1
        assert len(changes.foreshadowing_updates) == 1
        assert len(changes.uncertain_claims) == 1
        assert any(item["change_type"] == "update" for item in changes.characters)

    def test_empty_llm_response_returns_empty_changeset(self, sample_world: WorldModel) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "new_characters": [],
                "new_world_rules": [],
                "timeline_events": [],
                "foreshadowing": [],
                "character_updates": [],
                "uncertain_claims": [],
            }
        )
        changes = ExtractorHub().extract(1, "Content.", sample_world, llm)
        assert changes.raw_staging_changes == []
