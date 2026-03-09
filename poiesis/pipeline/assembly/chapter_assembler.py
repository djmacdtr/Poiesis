"""章节组装器。"""

from __future__ import annotations

from poiesis.application.scene_contracts import ChapterOutput, ChapterPlan, SceneTrace


class ChapterAssembler:
    """把多个 scene 拼接成最终章节。"""

    def assemble(
        self,
        run_id: int,
        chapter_plan: ChapterPlan,
        scenes: list[SceneTrace],
        summary: dict[str, object],
    ) -> ChapterOutput:
        content = "\n\n".join(scene.final_text.strip() for scene in scenes if scene.final_text.strip())
        return ChapterOutput(
            run_id=run_id,
            chapter_number=chapter_plan.chapter_number,
            title=chapter_plan.title,
            content=content,
            summary=summary,
            scene_count=len(scenes),
            status="draft",
        )
