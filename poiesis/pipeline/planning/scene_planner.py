"""Scene 规划器。"""

from __future__ import annotations

from poiesis.application.scene_contracts import ChapterPlan, ScenePlan


class ScenePlanner:
    """把章节规划拆成多个可执行 scene。"""

    def plan(self, chapter_plan: ChapterPlan) -> list[ScenePlan]:
        """优先复用上游 scene_stubs，若缺失则给出稳定默认拆分。"""
        raw_stubs = list(chapter_plan.source_plan.get("scene_stubs") or [])
        if not raw_stubs:
            raw_stubs = [
                {"title": "开场推进", "goal": "建立当前冲突", "conflict": "外部压力抬升", "turning_point": ""},
                {"title": "中段升级", "goal": "放大人物抉择", "conflict": "核心矛盾升级", "turning_point": ""},
                {"title": "结尾转折", "goal": "形成新局面", "conflict": "代价显现", "turning_point": "抛出下一章钩子"},
            ]

        scenes: list[ScenePlan] = []
        for index, raw in enumerate(raw_stubs, start=1):
            scenes.append(
                ScenePlan(
                    chapter_number=chapter_plan.chapter_number,
                    scene_number=index,
                    title=str(raw.get("title") or f"Scene {index}"),
                    goal=str(raw.get("goal") or chapter_plan.goal),
                    conflict=str(raw.get("conflict") or ""),
                    turning_point=str(raw.get("turning_point") or ""),
                    required_loops=list(chapter_plan.must_progress_loops),
                    continuity_requirements=list(chapter_plan.must_preserve),
                )
            )
        return scenes
