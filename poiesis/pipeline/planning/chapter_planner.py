"""章节规划器。"""

from __future__ import annotations

from poiesis.application.scene_contracts import ChapterPlan, StoryPlan
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.pipeline.planning.story_planner import StoryPlanner


class ChapterPlanner:
    """基于现有 StoryPlanner 输出正式 ChapterPlan。"""

    def __init__(self, story_planner: StoryPlanner) -> None:
        self._story_planner = story_planner

    def plan(
        self,
        chapter_number: int,
        story_plan: StoryPlan,
        world: WorldModel,
        previous_summaries: list[str],
        llm: LLMClient,
    ) -> ChapterPlan:
        """把旧 planner 输出收口为新的章节规划协议。"""
        planner_output = self._story_planner.plan(chapter_number, world, previous_summaries, llm)
        scene_count = max(3, len(planner_output.scene_stubs) or 0)
        return ChapterPlan(
            chapter_number=chapter_number,
            title=planner_output.title or f"第 {chapter_number} 章",
            goal=planner_output.chapter_goal or planner_output.summary,
            hook=planner_output.opening_hook,
            must_preserve=planner_output.must_preserve,
            must_progress_loops=planner_output.must_progress_loops or story_plan.active_loops,
            scene_count_target=scene_count,
            notes=planner_output.notes,
            source_plan=planner_output.model_dump(mode="json"),
        )
