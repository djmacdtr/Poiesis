"""Scene 驱动架构下的应用用例。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from poiesis.application.scene_contracts import (
    ChangeSet,
    ChapterOutput,
    ChapterPlan,
    ChapterStatus,
    ChapterTrace,
    LoopState,
    LoopStatus,
    PublishBlockers,
    ReviewQueueItem,
    SceneDraft,
    ScenePlan,
    SceneTrace,
    StoryPlan,
    VerifierIssue,
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


def _fatal_issues(issues: list[VerifierIssue]) -> list[VerifierIssue]:
    """筛出 fatal 问题，供重写与门禁判断复用。"""
    return [issue for issue in issues if issue.severity == "fatal"]


def _issue_summary(issues: list[VerifierIssue]) -> str:
    """把问题列表压缩成可显示的简短摘要。"""
    if not issues:
        return "当前场景已通过校验。"
    fatal = _fatal_issues(issues)
    if fatal:
        return "；".join(issue.reason for issue in fatal)
    return "；".join(issue.reason for issue in issues[:3])


def _build_scene_trace_from_row(run_id: int, row: dict[str, Any]) -> SceneTrace:
    """把数据库 run_scenes 行转换成正式 SceneTrace。"""
    return SceneTrace.model_validate(
        {
            "run_id": run_id,
            "chapter_number": int(row["chapter_number"]),
            "scene_number": int(row["scene_number"]),
            "status": str(row.get("status") or "pending"),
            "scene_plan": row.get("scene_plan_json") or {},
            "draft": row.get("draft_json") or None,
            "final_text": str(row.get("final_text") or ""),
            "changeset": ChangeSet.model_validate(row.get("changeset_json") or {}),
            "verifier_issues": row.get("verifier_issues_json") or [],
            "review_required": bool(row.get("review_required")),
            "review_reason": str(row.get("review_reason") or ""),
            "review_status": str(row.get("review_status") or "auto_approved"),
            "metrics": row.get("metrics_json") or {},
            "error_message": row.get("error_message"),
        }
    )


def _build_story_plan(book_id: int, payload: dict[str, Any]) -> StoryPlan:
    """统一 story plan 的默认值，避免历史记录字段缺失。"""
    merged = {
        "book_id": book_id,
        "focus": "",
        "active_themes": [],
        "active_loops": [],
        "narrative_pressure": "",
        **payload,
    }
    return StoryPlan.model_validate(merged)


def _build_chapter_plan(chapter_number: int, payload: dict[str, Any]) -> ChapterPlan:
    """统一 chapter plan 的默认值。"""
    merged = {
        "chapter_number": chapter_number,
        "title": "",
        "goal": "",
        "hook": "",
        "must_preserve": [],
        "must_progress_loops": [],
        "scene_count_target": 3,
        "notes": [],
        "source_plan": {},
        **payload,
    }
    return ChapterPlan.model_validate(merged)


def _parse_scene_ref(scene_ref: str) -> tuple[int | None, int | None]:
    """把形如 3-2 的 scene 引用解析为章号和 scene 号。"""
    if "-" not in scene_ref:
        return None, None
    chapter, scene = scene_ref.split("-", 1)
    try:
        return int(chapter), int(scene)
    except ValueError:
        return None, None


def _build_story_state_snapshot(
    chapter_trace: ChapterTrace,
    world: WorldModel,
) -> dict[str, Any]:
    """把发布时刻的 world / loop 状态压缩成正式故事快照。"""
    loops = world.list_loops()
    open_loops = [item for item in loops if item.get("status") in {"open", "hinted", "escalated"}]
    resolved_loops = [item for item in loops if item.get("status") == "resolved"]
    overdue_loops = [item for item in loops if item.get("status") == "overdue"]
    return {
        "chapter_number": chapter_trace.chapter_number,
        "last_published_chapter": chapter_trace.chapter_number,
        "published_chapters": list(
            dict.fromkeys(
                [*list(world.story_state.get("published_chapters") or []), chapter_trace.chapter_number]
            )
        ),
        "active_chapter": chapter_trace.chapter_number + 1,
        "recent_scene_refs": [
            f"{scene.chapter_number}-{scene.scene_number}"
            for scene in chapter_trace.scenes
        ],
        "published_at": datetime.now(UTC).isoformat(),
        "open_loop_count": len(open_loops),
        "resolved_loop_count": len(resolved_loops),
        "overdue_loop_count": len(overdue_loops),
        "open_loops": open_loops,
        "resolved_loops": resolved_loops,
        "overdue_loops": overdue_loops,
        "chapter_summary": dict(chapter_trace.summary),
    }


class GenerateSceneUseCase:
    """生成、重试与人工修补单个 scene。"""

    def __init__(self, context: SceneGenerationContext) -> None:
        self._context = context

    def _verify(
        self,
        scene_plan: ScenePlan,
        chapter_plan: ChapterPlan,
        content: str,
    ) -> tuple[ChangeSet, list[VerifierIssue]]:
        """统一执行抽取与校验，保证 retry/patch 走同一套逻辑。"""
        changeset = self._context.scene_extractor.extract(
            scene_plan=scene_plan,
            content=content,
            world=self._context.world,
            llm=self._context.planner_llm,
        )
        issues = self._context.scene_verifier.verify(
            scene_plan=scene_plan,
            content=content,
            chapter_plan=chapter_plan.model_dump(mode="json"),
            world=self._context.world,
            changeset=changeset,
            llm=self._context.planner_llm,
        )
        return changeset, issues

    def _to_trace(
        self,
        run_id: int,
        scene_plan: ScenePlan,
        draft: SceneDraft | None,
        final_text: str,
        changeset: ChangeSet,
        issues: list[VerifierIssue],
        error_message: str | None = None,
    ) -> SceneTrace:
        """把运行结果收口为统一的 SceneTrace。"""
        review_required = len(_fatal_issues(issues)) > 0
        return SceneTrace(
            run_id=run_id,
            chapter_number=scene_plan.chapter_number,
            scene_number=scene_plan.scene_number,
            status="needs_review" if review_required else "completed",
            scene_plan=scene_plan,
            draft=draft,
            final_text=final_text,
            changeset=changeset,
            verifier_issues=issues,
            review_required=review_required,
            review_reason=_issue_summary(issues) if review_required else "",
            review_status="pending" if review_required else "completed",
            metrics={
                "issue_count": len(issues),
                "fatal_count": len(_fatal_issues(issues)),
                "change_count": len(changeset.raw_changes),
            },
            error_message=error_message,
        )

    def execute(self, run_id: int, chapter_plan: ChapterPlan, scene_plan: ScenePlan) -> SceneTrace:
        """首次生成 scene。"""
        draft = self._context.scene_writer.write(
            scene_plan=scene_plan,
            chapter_plan=chapter_plan,
            world=self._context.world,
            llm=self._context.writer_llm,
        )
        changeset, issues = self._verify(scene_plan, chapter_plan, draft.content)
        final_text = draft.content
        fatal_issues = _fatal_issues(issues)
        if fatal_issues:
            final_text = self._context.scene_editor.rewrite(
                scene_plan=scene_plan,
                chapter_plan=chapter_plan,
                content=final_text,
                issues=[issue.reason for issue in fatal_issues],
                world=self._context.world,
                llm=self._context.writer_llm,
            )
            changeset, issues = self._verify(scene_plan, chapter_plan, final_text)

        return self._to_trace(run_id, scene_plan, draft, final_text, changeset, issues)

    def apply_patch(
        self,
        run_id: int,
        chapter_plan: ChapterPlan,
        scene_trace: SceneTrace,
        patch_text: str,
    ) -> SceneTrace:
        """把人工 patch 作为修补指令应用到当前 scene。"""
        patch_guidance = patch_text.strip()
        if not patch_guidance:
            raise ValueError("patch 文本不能为空")

        issues = [issue.reason for issue in _fatal_issues(scene_trace.verifier_issues)]
        issues.append(f"人工修补要求：{patch_guidance}")
        rewritten = self._context.scene_editor.rewrite(
            scene_plan=scene_trace.scene_plan,
            chapter_plan=chapter_plan,
            content=scene_trace.final_text,
            issues=issues,
            world=self._context.world,
            llm=self._context.writer_llm,
        )
        changeset, verifier_issues = self._verify(scene_trace.scene_plan, chapter_plan, rewritten)
        return self._to_trace(
            run_id=run_id,
            scene_plan=scene_trace.scene_plan,
            draft=scene_trace.draft,
            final_text=rewritten,
            changeset=changeset,
            issues=verifier_issues,
        )


class AdvanceLoopStateUseCase:
    """根据 scene 变更推进 loop 状态。"""

    def __init__(self, db: Database, world: WorldModel) -> None:
        self._db = db
        self._world = world

    def _normalize_loop_status(self, value: str) -> str:
        """把运行时字符串收口到合法 loop 状态。"""
        valid = {"open", "hinted", "escalated", "resolved", "dropped", "overdue"}
        return value if value in valid else "hinted"

    def _normalize_due_bound(self, value: Any) -> int | None:
        """把章节边界统一转成整数，非法值直接视为未设置。"""
        if value in {None, ""}:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _derive_status(self, action: str, existing: dict[str, Any] | None, raw_status: str) -> LoopStatus:
        """优先依据规范动作推导状态，避免上游字段语义漂移。"""
        if action == "introduced":
            return "open"
        if action == "progressed":
            return "escalated"
        if action == "resolved":
            return "resolved"
        if action == "dropped":
            return "dropped"
        if action == "reopen":
            return "open"
        if existing is not None:
            return cast(LoopStatus, self._normalize_loop_status(str(existing.get("status") or raw_status or "hinted")))
        return cast(LoopStatus, self._normalize_loop_status(raw_status or "hinted"))

    def _mark_overdue_loops(self, book_id: int, chapter_number: int) -> None:
        """根据当前章节推进结果，把已超过窗口的开放线索标记为 overdue。"""
        for existing in list(self._world.list_loops()):
            due_end = existing.get("due_end_chapter")
            status = str(existing.get("status") or "")
            if due_end is None or status not in {"open", "hinted", "escalated"}:
                continue
            if int(due_end) >= chapter_number:
                continue
            overdue_loop = {
                **existing,
                "status": "overdue",
                "due_window": existing.get("due_window") or (
                    f"第 {existing.get('due_start_chapter')}-{due_end} 章"
                    if existing.get("due_start_chapter") is not None
                    else f"最迟第 {due_end} 章"
                ),
            }
            self._db.upsert_loop(book_id, overdue_loop)
            self._world.upsert_loop(overdue_loop)

    def execute(self, book_id: int, scene: SceneTrace) -> None:
        """将 loop 更新落到 loops / loop_events。"""
        for item in scene.changeset.loop_updates:
            loop_id = str(item.get("loop_id") or f"loop-{scene.scene_number}")
            existing = self._world.get_loop(loop_id)
            due_start = self._normalize_due_bound(item.get("due_start_chapter"))
            due_end = self._normalize_due_bound(item.get("due_end_chapter"))
            action = str(item.get("action") or "")
            loop = LoopState(
                loop_id=loop_id,
                title=str(item.get("title") or (existing or {}).get("title") or loop_id or "未命名线索"),
                status=self._derive_status(action, existing, str(item.get("status") or "")),
                introduced_in_scene=str(
                    (existing or {}).get("introduced_in_scene")
                    or item.get("source_scene")
                    or f"{scene.chapter_number}-{scene.scene_number}"
                ),
                due_start_chapter=due_start if due_start is not None else (existing or {}).get("due_start_chapter"),
                due_end_chapter=due_end if due_end is not None else (existing or {}).get("due_end_chapter"),
                due_window=str(item.get("due_window") or (existing or {}).get("due_window") or ""),
                priority=int(item.get("priority") or (existing or {}).get("priority") or 1),
                related_characters=list(item.get("related_characters") or (existing or {}).get("related_characters") or []),
                resolution_requirements=list(
                    item.get("resolution_requirements") or (existing or {}).get("resolution_requirements") or []
                ),
                last_updated_scene=f"{scene.chapter_number}-{scene.scene_number}",
            )
            payload = loop.model_dump(mode="json")
            if not payload["due_window"]:
                start = payload.get("due_start_chapter")
                end = payload.get("due_end_chapter")
                if start is not None and end is not None:
                    payload["due_window"] = f"第 {start}-{end} 章"
                elif end is not None:
                    payload["due_window"] = f"最迟第 {end} 章"
                elif start is not None:
                    payload["due_window"] = f"自第 {start} 章起"
            self._db.upsert_loop(book_id, payload)
            self._world.upsert_loop(payload)
            self._db.add_loop_event(
                book_id=book_id,
                loop_id=loop.loop_id,
                chapter_number=scene.chapter_number,
                scene_number=scene.scene_number,
                event_type=action or loop.status,
                payload={**item, "status": payload["status"]},
            )
        self._mark_overdue_loops(book_id, scene.chapter_number)


class RefreshChapterAggregateUseCase:
    """根据当前 scene 状态重组章节并刷新发布门禁。"""

    def __init__(self, context: SceneGenerationContext) -> None:
        self._context = context

    def _build_blockers(
        self,
        scenes: list[SceneTrace],
        pending_reviews: int,
        chapter_plan: ChapterPlan,
    ) -> PublishBlockers:
        """把 scene 与 review 状态压缩成章节门禁结果。"""
        blockers: list[str] = []
        if any(scene.status == "needs_review" for scene in scenes):
            blockers.append("仍有待审阅场景。")
        if pending_reviews > 0:
            blockers.append(f"仍有 {pending_reviews} 条待处理审阅记录。")
        progressed_loops = {
            str(item.get("loop_id") or "")
            for scene in scenes
            for item in scene.changeset.loop_updates
            if item.get("loop_id")
        }
        missing_required = [
            loop_id
            for loop_id in chapter_plan.must_progress_loops
            if loop_id not in progressed_loops
        ]
        if missing_required:
            blockers.append(f"本章尚未推进必需剧情线索：{'、'.join(missing_required)}。")
        unfinished = [scene for scene in scenes if scene.status not in {"completed", "approved"}]
        if unfinished and not blockers:
            blockers.append("仍有场景未完成。")

        if blockers:
            status: ChapterStatus = "needs_review"
        elif scenes:
            status = "ready_to_publish"
        else:
            status = "draft"

        return PublishBlockers(
            chapter_status=status,
            can_publish=status == "ready_to_publish",
            blockers=blockers,
        )

    def execute(self, run_id: int, chapter_number: int) -> tuple[ChapterTrace, ChapterOutput, PublishBlockers]:
        """重组 chapter，并把最新草稿态写回数据库。"""
        row = self._context.db.get_run_chapter_trace(run_id, chapter_number)
        if row is None:
            raise ValueError("章节 trace 不存在")

        scene_rows = self._context.db.list_run_scene_traces(run_id, chapter_number)
        scenes = [_build_scene_trace_from_row(run_id, item) for item in scene_rows]
        story_plan = _build_story_plan(
            self._context.book_id,
            dict((row.get("retrieval_pack_json") or {}).get("story_plan") or {}),
        )
        chapter_plan = _build_chapter_plan(chapter_number, dict(row.get("planner_output_json") or {}))
        pending_reviews = self._context.db.count_pending_scene_reviews(run_id, chapter_number)
        blockers = self._build_blockers(scenes, pending_reviews, chapter_plan)
        assembled_text = "\n\n".join(scene.final_text.strip() for scene in scenes if scene.final_text.strip())

        summary: dict[str, Any]
        if assembled_text.strip():
            summary = self._context.summarizer.summarize(
                chapter_number=chapter_number,
                content=assembled_text,
                plan=chapter_plan.model_dump(mode="json"),
                world=self._context.world,
                llm=self._context.planner_llm,
            )
        else:
            summary = {
                "summary": "",
                "key_events": [],
                "characters_featured": [],
                "new_facts_introduced": [],
            }

        chapter_output = self._context.chapter_assembler.assemble(
            run_id=run_id,
            chapter_plan=chapter_plan,
            scenes=scenes,
            summary=summary,
        )
        chapter_output.status = blockers.chapter_status

        chapter_trace = ChapterTrace(
            run_id=run_id,
            chapter_number=chapter_number,
            status=blockers.chapter_status,
            story_plan=story_plan,
            chapter_plan=chapter_plan,
            scenes=scenes,
            assembled_text=chapter_output.content,
            summary=summary,
            metrics={
                "scene_count": len(scenes),
                "review_scene_count": len([scene for scene in scenes if scene.review_required]),
                "pending_review_count": pending_reviews,
            },
            review_required=blockers.chapter_status == "needs_review",
        )

        self._context.db.upsert_run_chapter_trace(
            run_id=run_id,
            chapter_number=chapter_number,
            status=blockers.chapter_status,
            planner_output=chapter_plan.model_dump(mode="json"),
            retrieval_pack={"story_plan": story_plan.model_dump(mode="json")},
            draft_text="",
            final_content=chapter_output.content,
            changeset={"scene_count": len(scenes)},
            verifier_issues=[
                issue.model_dump(mode="json")
                for scene in scenes
                for issue in scene.verifier_issues
            ],
            editor_rewrites=[],
            merge_result={
                "review_required": blockers.chapter_status == "needs_review",
                "can_publish": blockers.can_publish,
                "blockers": blockers.blockers,
            },
            summary_result=summary,
            metrics=chapter_trace.metrics,
        )
        self._context.db.upsert_chapter_output(
            self._context.book_id,
            chapter_output.model_dump(mode="json"),
        )
        self._context.db.upsert_chapter(
            chapter_number=chapter_number,
            title=chapter_output.title,
            content=chapter_output.content,
            plan=chapter_plan.model_dump(mode="json"),
            book_id=self._context.book_id,
            word_count=len(chapter_output.content),
            status=blockers.chapter_status,
        )
        self._context.db.upsert_chapter_summary(
            chapter_number=chapter_number,
            summary=str(summary.get("summary") or ""),
            book_id=self._context.book_id,
            key_events=list(summary.get("key_events") or []),
            characters_featured=list(summary.get("characters_featured") or []),
            new_facts_introduced=list(summary.get("new_facts_introduced") or []),
        )
        self._context.world.set_story_state(
            {
                **self._context.world.story_state,
                "active_chapter": chapter_number,
                "recent_scene_refs": [
                    f"{scene.chapter_number}-{scene.scene_number}"
                    for scene in scenes
                ],
            }
        )
        return chapter_trace, chapter_output, blockers


class GenerateChapterUseCase:
    """生成一个章节及其 scene 链路。"""

    def __init__(self, context: SceneGenerationContext) -> None:
        self._context = context
        self._scene_use_case = GenerateSceneUseCase(context)
        self._loop_use_case = AdvanceLoopStateUseCase(context.db, context.world)

    def execute(self, run_id: int, chapter_number: int) -> tuple[ChapterTrace, ChapterOutput]:
        """完整执行 chapter -> scenes，并把 scene trace 写入数据库。"""
        previous = self._context.db.list_chapter_outputs(book_id=self._context.book_id)
        story_plan = StoryPlan(
            book_id=self._context.book_id,
            focus=f"第 {chapter_number} 章",
            active_loops=self._context.world.active_loop_ids(),
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

        for scene_plan in scene_plans:
            scene = self._scene_use_case.execute(run_id=run_id, chapter_plan=chapter_plan, scene_plan=scene_plan)
            self._context.db.upsert_run_scene_trace(run_id, scene.model_dump(mode="json"))
            if scene.review_required:
                self._context.db.create_scene_review(
                    run_id=run_id,
                    chapter_number=scene.chapter_number,
                    scene_number=scene.scene_number,
                    reason=scene.review_reason,
                )
            else:
                self._loop_use_case.execute(self._context.book_id, scene)

        refresh = RefreshChapterAggregateUseCase(self._context)
        chapter_trace, chapter_output, _ = refresh.execute(run_id, chapter_number)
        return chapter_trace, chapter_output


class PublishChapterUseCase:
    """人工确认发布章节与状态快照。"""

    def __init__(self, context: SceneGenerationContext) -> None:
        self._context = context
        self._refresh = RefreshChapterAggregateUseCase(context)

    def execute(self, run_id: int, chapter_number: int) -> ChapterOutput:
        """只有达到 ready_to_publish 的章节才允许正式发布。"""
        chapter_trace, chapter_output, blockers = self._refresh.execute(run_id, chapter_number)
        if not blockers.can_publish:
            raise ValueError("；".join(blockers.blockers) or "章节尚未达到可发布状态")

        chapter_output.status = "published"
        self._context.db.upsert_chapter_output(
            self._context.book_id,
            chapter_output.model_dump(mode="json"),
        )
        self._context.db.upsert_chapter(
            chapter_number=chapter_number,
            title=chapter_output.title,
            content=chapter_output.content,
            plan=chapter_trace.chapter_plan.model_dump(mode="json"),
            book_id=self._context.book_id,
            word_count=len(chapter_output.content),
            status="published",
        )
        self._context.db.upsert_chapter_summary(
            chapter_number=chapter_number,
            summary=str(chapter_output.summary.get("summary") or ""),
            book_id=self._context.book_id,
            key_events=list(chapter_output.summary.get("key_events") or []),
            characters_featured=list(chapter_output.summary.get("characters_featured") or []),
            new_facts_introduced=list(chapter_output.summary.get("new_facts_introduced") or []),
        )
        self._context.db.upsert_run_chapter_trace(
            run_id=run_id,
            chapter_number=chapter_number,
            status="published",
            planner_output=chapter_trace.chapter_plan.model_dump(mode="json"),
            retrieval_pack={"story_plan": chapter_trace.story_plan.model_dump(mode="json")},
            draft_text="",
            final_content=chapter_output.content,
            changeset={"scene_count": len(chapter_trace.scenes)},
            verifier_issues=[
                issue.model_dump(mode="json")
                for scene in chapter_trace.scenes
                for issue in scene.verifier_issues
            ],
            editor_rewrites=[],
            merge_result={"review_required": False, "can_publish": True, "blockers": []},
            summary_result=chapter_output.summary,
            metrics=chapter_trace.metrics,
        )
        self._context.db.upsert_story_state_snapshot(
            self._context.book_id,
            chapter_number,
            _build_story_state_snapshot(chapter_trace, self._context.world),
        )
        self._context.world.set_story_state(
            {
                **self._context.world.story_state,
                "last_published_chapter": chapter_number,
                "published_chapters": list(
                    dict.fromkeys(
                        [
                            *list(self._context.world.story_state.get("published_chapters") or []),
                            chapter_number,
                        ]
                    )
                ),
                "active_chapter": chapter_number + 1,
                "recent_scene_refs": [
                    f"{scene.chapter_number}-{scene.scene_number}"
                    for scene in chapter_trace.scenes
                ],
            }
        )
        return chapter_output


class ReviewSceneUseCase:
    """审阅队列只负责查询，不直接承担动作执行。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def list_pending(self, book_id: int) -> list[ReviewQueueItem]:
        return [ReviewQueueItem.model_validate(item) for item in self._db.list_scene_reviews(book_id)]


class _ReviewActionBase:
    """审阅动作共用逻辑。"""

    def __init__(self, context: SceneGenerationContext) -> None:
        self._context = context
        self._scene_use_case = GenerateSceneUseCase(context)
        self._refresh = RefreshChapterAggregateUseCase(context)
        self._loop_use_case = AdvanceLoopStateUseCase(context.db, context.world)

    def _load_review_scene(
        self,
        review_id: int,
    ) -> tuple[dict[str, Any], ChapterPlan, SceneTrace]:
        """读取 review、chapter 和 scene 当前状态。"""
        review = self._context.db.get_scene_review(review_id)
        if review is None:
            raise ValueError("review 不存在")
        if review["status"] != "pending":
            raise ValueError("review 已完成，不可重复执行")

        chapter_row = self._context.db.get_run_chapter_trace(review["run_id"], review["chapter_number"])
        if chapter_row is None:
            raise ValueError("章节 trace 不存在")
        scene_row = self._context.db.get_run_scene_trace(
            review["run_id"],
            review["chapter_number"],
            review["scene_number"],
        )
        if scene_row is None:
            raise ValueError("scene trace 不存在")

        chapter_plan = _build_chapter_plan(review["chapter_number"], chapter_row.get("planner_output_json") or {})
        scene_trace = _build_scene_trace_from_row(review["run_id"], scene_row)
        return review, chapter_plan, scene_trace

    def _finalize_review(
        self,
        review_id: int,
        action: str,
        operator: str,
        scene_trace: SceneTrace,
        result_summary: str,
        input_payload: dict[str, Any],
    ) -> ReviewQueueItem:
        """根据新 scene 结果更新 review 状态并记录事件。"""
        if scene_trace.review_required:
            event_status = "failed"
            self._context.db.update_scene_review(
                review_id=review_id,
                action=action,
                status="pending",
                reason=scene_trace.review_reason,
                result_summary=result_summary,
                resolved_scene_status=scene_trace.status,
            )
        else:
            event_status = "succeeded"
            self._context.db.close_scene_review(
                review_id=review_id,
                action=action,
                status="completed",
                resolved_scene_status=scene_trace.status,
                result_summary=result_summary,
                patch_text=input_payload.get("patch_text"),
            )

        self._context.db.add_scene_review_event(
            review_id=review_id,
            action=action,
            status=event_status,
            operator=operator,
            input_payload=input_payload,
            result_payload={
                "scene_status": scene_trace.status,
                "review_required": scene_trace.review_required,
                "review_reason": scene_trace.review_reason,
                "issue_count": len(scene_trace.verifier_issues),
            },
        )
        updated = self._context.db.get_scene_review(review_id)
        if updated is None:
            raise ValueError("review 更新失败")
        return ReviewQueueItem.model_validate(updated)


class ApproveSceneReviewUseCase(_ReviewActionBase):
    """人工确认当前 scene 可通过。"""

    def execute(self, review_id: int, operator: str) -> ReviewQueueItem:
        review, _chapter_plan, scene_trace = self._load_review_scene(review_id)
        approved_trace = scene_trace.model_copy(
            update={
                "status": "approved",
                "review_required": False,
                "review_status": "completed",
                "review_reason": "",
            }
        )
        self._context.db.upsert_run_scene_trace(
            review["run_id"],
            approved_trace.model_dump(mode="json"),
        )
        updated_review = self._finalize_review(
            review_id=review_id,
            action="approve",
            operator=operator,
            scene_trace=approved_trace,
            result_summary="人工审阅通过，保留当前场景文本。",
            input_payload={},
        )
        self._loop_use_case.execute(self._context.book_id, approved_trace)
        self._refresh.execute(review["run_id"], review["chapter_number"])
        return updated_review


class RetrySceneUseCase(_ReviewActionBase):
    """重新生成单个 scene，并自动刷新所属 chapter。"""

    def execute(self, review_id: int, operator: str) -> ReviewQueueItem:
        review, chapter_plan, scene_trace = self._load_review_scene(review_id)
        retried_trace = self._scene_use_case.execute(
            run_id=review["run_id"],
            chapter_plan=chapter_plan,
            scene_plan=scene_trace.scene_plan,
        )
        self._context.db.upsert_run_scene_trace(
            review["run_id"],
            retried_trace.model_dump(mode="json"),
        )
        updated_review = self._finalize_review(
            review_id=review_id,
            action="retry",
            operator=operator,
            scene_trace=retried_trace,
            result_summary=(
                "重试后已通过校验。"
                if not retried_trace.review_required
                else f"重试后仍存在 fatal 问题：{retried_trace.review_reason}"
            ),
            input_payload={},
        )
        if not retried_trace.review_required:
            self._loop_use_case.execute(self._context.book_id, retried_trace)
        self._refresh.execute(review["run_id"], review["chapter_number"])
        return updated_review


class ApplyPatchUseCase(_ReviewActionBase):
    """应用人工 patch，重新校验并重组所属 chapter。"""

    def execute(self, review_id: int, patch_text: str, operator: str) -> ReviewQueueItem:
        review, chapter_plan, scene_trace = self._load_review_scene(review_id)
        patched_trace = self._scene_use_case.apply_patch(
            run_id=review["run_id"],
            chapter_plan=chapter_plan,
            scene_trace=scene_trace,
            patch_text=patch_text,
        )
        self._context.db.upsert_run_scene_trace(
            review["run_id"],
            patched_trace.model_dump(mode="json"),
        )
        self._context.db.add_scene_patch(
            run_id=review["run_id"],
            chapter_number=review["chapter_number"],
            scene_number=review["scene_number"],
            patch_text=patch_text,
            before_text=scene_trace.final_text,
            after_text=patched_trace.final_text,
            verifier_issues=[issue.model_dump(mode="json") for issue in patched_trace.verifier_issues],
            applied_successfully=not patched_trace.review_required,
        )
        updated_review = self._finalize_review(
            review_id=review_id,
            action="patch",
            operator=operator,
            scene_trace=patched_trace,
            result_summary=(
                "修补后已通过校验。"
                if not patched_trace.review_required
                else f"修补后仍需人工处理：{patched_trace.review_reason}"
            ),
            input_payload={"patch_text": patch_text},
        )
        if not patched_trace.review_required:
            self._loop_use_case.execute(self._context.book_id, patched_trace)
        self._refresh.execute(review["run_id"], review["chapter_number"])
        return updated_review
