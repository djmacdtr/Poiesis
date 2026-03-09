"""Scene 编辑器。"""

from __future__ import annotations

from poiesis.application.scene_contracts import ChapterPlan, ScenePlan
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.pipeline.writing.editor import ChapterEditor


class SceneEditor:
    """复用现有 editor 对 scene 进行重写。"""

    def __init__(self, chapter_editor: ChapterEditor) -> None:
        self._chapter_editor = chapter_editor

    def rewrite(
        self,
        scene_plan: ScenePlan,
        chapter_plan: ChapterPlan,
        content: str,
        issues: list[str],
        world: WorldModel,
        llm: LLMClient,
    ) -> str:
        plan = {
            "title": chapter_plan.title,
            "summary": chapter_plan.goal,
            "scene_title": scene_plan.title,
            "scene_goal": scene_plan.goal,
            "must_progress_loops": scene_plan.required_loops,
        }
        return self._chapter_editor.edit(
            chapter_number=scene_plan.chapter_number,
            content=content,
            violations=issues,
            plan=plan,
            world=world,
            llm=llm,
        )
