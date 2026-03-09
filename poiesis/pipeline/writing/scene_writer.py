"""Scene 写作器。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from poiesis.application.scene_contracts import ChapterPlan, SceneDraft, ScenePlan
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.pipeline.writing.writer import ChapterWriter


class SceneWriter:
    """用现有 writer 生成单个 scene 文本。"""

    def __init__(self, chapter_writer: ChapterWriter) -> None:
        self._chapter_writer = chapter_writer

    def write(
        self,
        scene_plan: ScenePlan,
        chapter_plan: ChapterPlan,
        world: WorldModel,
        llm: LLMClient,
        on_delta: Callable[[str], None] | None = None,
    ) -> SceneDraft:
        """把 scene 计划包装成 writer 可消费的 plan。"""
        plan: dict[str, Any] = {
            "title": chapter_plan.title,
            "summary": f"{chapter_plan.goal} / Scene {scene_plan.scene_number}: {scene_plan.goal}",
            "chapter_goal": chapter_plan.goal,
            "scene_title": scene_plan.title,
            "scene_goal": scene_plan.goal,
            "scene_conflict": scene_plan.conflict,
            "scene_turning_point": scene_plan.turning_point,
            "must_preserve": chapter_plan.must_preserve,
            "must_progress_loops": scene_plan.required_loops,
            "notes": chapter_plan.notes,
        }
        content = self._chapter_writer.write(
            chapter_number=scene_plan.chapter_number,
            plan=plan,
            world=world,
            llm=llm,
            on_delta=on_delta,
        )
        return SceneDraft(
            chapter_number=scene_plan.chapter_number,
            scene_number=scene_plan.scene_number,
            title=scene_plan.title,
            content=content,
            retrieval_context={"scene_goal": scene_plan.goal, "scene_conflict": scene_plan.conflict},
        )
