"""Scene 驱动架构下的应用用例。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from poiesis.application.scene_contracts import (
    ChapterOutput,
    ChapterPlan,
    ChapterTrace,
    LoopState,
    LoopStatus,
    ReviewQueueItem,
    SceneTrace,
    StoryPlan,
)
from poiesis.db.database import Database
from poiesis.domain.world.model import WorldModel
from poiesis.pipeline.assembly.chapter_assembler import ChapterAssembler
from poiesis.pipeline.extraction.scene_extractor import SceneExtractor
from poiesis.pipeline.planning.chapter_planner import ChapterPlanner
from poiesis.pipeline.planning.scene_planner import ScenePlanner
from poiesis.pipeline.summary.summarizer import ChapterSummarizer
from poiesis.pipeline.verification.scene_verifier import SceneVerifier
from poiesis.pipeline.writing.scene_editor import SceneEditor
from poiesis.pipeline.writing.scene_writer import SceneWriter


@dataclass
class SceneGenerationContext:
    """显式依赖集合，替代旧 runtime 巨型对象。"""

    db: Database
    world: WorldModel
    planner_llm: Any
    writer_llm: Any
    chapter_planner: ChapterPlanner
    scene_planner: ScenePlanner
    scene_writer: SceneWriter
    scene_extractor: SceneExtractor
    scene_verifier: SceneVerifier
    scene_editor: SceneEditor
    chapter_assembler: ChapterAssembler
    summarizer: ChapterSummarizer
    book_id: int


class GenerateSceneUseCase:
    """生成单个 scene。"""

    def __init__(self, context: SceneGenerationContext) -> None:
        self._context = context

    def execute(self, run_id: int, chapter_plan: ChapterPlan, scene_plan: Any) -> SceneTrace:
        """生成、抽取、审校并必要时进入 review。"""
        draft = self._context.scene_writer.write(
            scene_plan=scene_plan,
            chapter_plan=chapter_plan,
            world=self._context.world,
            llm=self._context.writer_llm,
        )
        changeset = self._context.scene_extractor.extract(
            scene_plan=scene_plan,
            content=draft.content,
            world=self._context.world,
            llm=self._context.planner_llm,
        )
        issues = self._context.scene_verifier.verify(
            scene_plan=scene_plan,
            content=draft.content,
            chapter_plan=chapter_plan.model_dump(mode="json"),
            world=self._context.world,
            changeset=changeset,
            llm=self._context.planner_llm,
        )
        final_text = draft.content
        fatal_issues = [issue.reason for issue in issues if issue.severity == "fatal"]
        if fatal_issues:
            final_text = self._context.scene_editor.rewrite(
                scene_plan=scene_plan,
                chapter_plan=chapter_plan,
                content=final_text,
                issues=fatal_issues,
                world=self._context.world,
                llm=self._context.writer_llm,
            )
            issues = self._context.scene_verifier.verify(
                scene_plan=scene_plan,
                content=final_text,
                chapter_plan=chapter_plan.model_dump(mode="json"),
                world=self._context.world,
                changeset=changeset,
                llm=self._context.planner_llm,
            )

        review_required = len([issue for issue in issues if issue.severity == "fatal"]) > 0
        return SceneTrace(
            run_id=run_id,
            chapter_number=chapter_plan.chapter_number,
            scene_number=scene_plan.scene_number,
            status="needs_review" if review_required else "completed",
            scene_plan=scene_plan,
            draft=draft,
            final_text=final_text,
            changeset=changeset,
            verifier_issues=issues,
            review_required=review_required,
            review_reason="; ".join(issue.reason for issue in issues if issue.severity == "fatal"),
            review_status="pending" if review_required else "auto_approved",
            metrics={
                "issue_count": len(issues),
                "fatal_count": len([issue for issue in issues if issue.severity == "fatal"]),
                "change_count": len(changeset.raw_changes),
            },
        )


class AdvanceLoopStateUseCase:
    """根据 scene 变更推进 loop 状态。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def _normalize_loop_status(self, value: str) -> str:
        """把运行时字符串收口到合法 loop 状态。"""
        valid = {"open", "hinted", "escalated", "resolved", "dropped", "overdue"}
        return value if value in valid else "hinted"

    def execute(self, book_id: int, scene: SceneTrace) -> None:
        """将 loop 更新落到 loops / loop_events。"""
        for item in scene.changeset.loop_updates:
            loop = LoopState(
                loop_id=str(item.get("loop_id") or f"loop-{scene.scene_number}"),
                title=str(item.get("title") or item.get("loop_id") or "未命名线索"),
                status=cast(
                    LoopStatus,
                    self._normalize_loop_status(str(item.get("status") or "hinted")),
                ),
                introduced_in_scene=str(item.get("source_scene") or f"{scene.chapter_number}-{scene.scene_number}"),
                due_window=str(item.get("due_window") or ""),
                priority=int(item.get("priority") or 1),
                related_characters=list(item.get("related_characters") or []),
                resolution_requirements=list(item.get("resolution_requirements") or []),
                last_updated_scene=f"{scene.chapter_number}-{scene.scene_number}",
            )
            self._db.upsert_loop(book_id, loop.model_dump(mode="json"))
            self._db.add_loop_event(
                book_id=book_id,
                loop_id=loop.loop_id,
                chapter_number=scene.chapter_number,
                scene_number=scene.scene_number,
                event_type=loop.status,
                payload=item,
            )


class GenerateChapterUseCase:
    """生成一个章节及其 scene 链路。"""

    def __init__(self, context: SceneGenerationContext) -> None:
        self._context = context
        self._scene_use_case = GenerateSceneUseCase(context)
        self._loop_use_case = AdvanceLoopStateUseCase(context.db)

    def execute(self, run_id: int, chapter_number: int) -> tuple[ChapterTrace, ChapterOutput]:
        """完整执行 chapter -> scenes -> assemble -> summary。"""
        previous = self._context.db.list_chapter_outputs(book_id=self._context.book_id)
        story_plan = StoryPlan(
            book_id=self._context.book_id,
            focus=f"第 {chapter_number} 章",
            active_loops=[item["loop_id"] for item in self._context.db.list_loops(self._context.book_id)],
            narrative_pressure="持续升级",
        )
        chapter_plan = self._context.chapter_planner.plan(
            chapter_number=chapter_number,
            story_plan=story_plan,
            world=self._context.world,
            previous_summaries=[item.get("summary_text", "") for item in previous],
            llm=self._context.planner_llm,
        )
        scene_plans = self._context.scene_planner.plan(chapter_plan)
        scenes: list[SceneTrace] = []

        for scene_plan in scene_plans:
            scene = self._scene_use_case.execute(run_id=run_id, chapter_plan=chapter_plan, scene_plan=scene_plan)
            scenes.append(scene)
            self._context.db.upsert_run_scene_trace(run_id, scene.model_dump(mode="json"))
            self._loop_use_case.execute(self._context.book_id, scene)
            if scene.review_required:
                self._context.db.create_scene_review(
                    run_id=run_id,
                    chapter_number=scene.chapter_number,
                    scene_number=scene.scene_number,
                    reason=scene.review_reason,
                )

        assembled_text = "\n\n".join(scene.final_text for scene in scenes)
        summary = self._context.summarizer.summarize(
            chapter_number=chapter_number,
            content=assembled_text,
            plan=chapter_plan.model_dump(mode="json"),
            world=self._context.world,
            llm=self._context.planner_llm,
        )
        chapter_output = self._context.chapter_assembler.assemble(
            run_id=run_id,
            chapter_plan=chapter_plan,
            scenes=scenes,
            summary=summary,
        )
        chapter_trace = ChapterTrace(
            run_id=run_id,
            chapter_number=chapter_number,
            status="needs_review" if any(scene.review_required for scene in scenes) else "completed",
            story_plan=story_plan,
            chapter_plan=chapter_plan,
            scenes=scenes,
            assembled_text=chapter_output.content,
            summary=summary,
            review_required=any(scene.review_required for scene in scenes),
            metrics={
                "scene_count": len(scenes),
                "review_scene_count": len([scene for scene in scenes if scene.review_required]),
            },
        )
        return chapter_trace, chapter_output


class PublishChapterUseCase:
    """发布章节与状态快照。"""

    def __init__(self, db: Database, world: WorldModel, book_id: int) -> None:
        self._db = db
        self._world = world
        self._book_id = book_id

    def execute(self, chapter: ChapterOutput, trace: ChapterTrace) -> ChapterOutput:
        """保存章节正文、摘要与状态快照。"""
        chapter.status = "review" if trace.review_required else "published"
        self._db.upsert_chapter_output(self._book_id, chapter.model_dump(mode="json"))
        self._db.upsert_chapter(
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            content=chapter.content,
            plan=trace.chapter_plan.model_dump(mode="json"),
            book_id=self._book_id,
            word_count=len(chapter.content),
            status=chapter.status,
        )
        self._db.upsert_chapter_summary(
            chapter_number=chapter.chapter_number,
            summary=str(chapter.summary.get("summary") or ""),
            book_id=self._book_id,
            key_events=list(chapter.summary.get("key_events") or []),
            characters_featured=list(chapter.summary.get("characters_featured") or []),
            new_facts_introduced=list(chapter.summary.get("new_facts_introduced") or []),
        )
        self._db.upsert_story_state_snapshot(
            self._book_id,
            chapter.chapter_number,
            {
                "canon_summary": self._world.world_context_summary(language="zh-CN"),
                "open_loops": self._db.list_loops(self._book_id),
                "review_required": trace.review_required,
            },
        )
        return chapter


class ReviewSceneUseCase:
    """审阅队列读取与动作更新。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def list_pending(self, book_id: int) -> list[ReviewQueueItem]:
        return [ReviewQueueItem.model_validate(item) for item in self._db.list_scene_reviews(book_id)]

    def update_action(self, review_id: int, action: str) -> ReviewQueueItem | None:
        updated = self._db.update_scene_review(review_id, action=action, status="completed")
        return ReviewQueueItem.model_validate(updated) if updated else None


class ApplyPatchUseCase:
    """记录 patch 并关闭 review。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def execute(self, review_id: int, patch_text: str) -> ReviewQueueItem | None:
        review = self._db.get_scene_review(review_id)
        if review is None:
            return None
        self._db.add_scene_patch(
            review["run_id"],
            review["chapter_number"],
            review["scene_number"],
            patch_text,
        )
        updated = self._db.update_scene_review(review_id, action="patch", status="completed", patch_text=patch_text)
        return ReviewQueueItem.model_validate(updated) if updated else None
