"""Scene 提取器。"""

from __future__ import annotations

from poiesis.application.scene_contracts import ChangeSet, ScenePlan
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.pipeline.extraction.extractor_hub import ExtractorHub


class SceneExtractor:
    """把现有 extractor 输出转成 scene 架构下的 ChangeSet。"""

    def __init__(self, extractor_hub: ExtractorHub) -> None:
        self._extractor_hub = extractor_hub

    def extract(
        self,
        scene_plan: ScenePlan,
        content: str,
        world: WorldModel,
        llm: LLMClient,
    ) -> ChangeSet:
        raw = self._extractor_hub.extract(
            chapter_number=scene_plan.chapter_number,
            content=content,
            world=world,
            llm=llm,
        )
        loop_updates = []
        for loop_id in scene_plan.required_loops:
            loop_updates.append(
                {
                    "loop_id": loop_id,
                    "status": "hinted",
                    "title": loop_id,
                    "source_scene": f"{scene_plan.chapter_number}-{scene_plan.scene_number}",
                }
            )
        return ChangeSet(
            characters=raw.characters,
            world_rules=raw.world_rules,
            timeline_events=raw.timeline_events,
            loop_updates=loop_updates,
            uncertain_claims=raw.uncertain_claims,
            raw_changes=raw.raw_staging_changes,
        )
