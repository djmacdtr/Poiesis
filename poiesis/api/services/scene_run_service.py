"""Scene 驱动的运行服务。

这里集中承接新的运行主链与 LLM 构建逻辑，
用于替代旧的 RunLoop 入口。
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any

from poiesis.api.task_registry import TaskInfo, registry
from poiesis.application.scene_contracts import (
    ChangeSet,
    ChapterOutput,
    ChapterPlan,
    ChapterStatus,
    ChapterTrace,
    LoopState,
    PublishBlockers,
    ReviewQueueItem,
    RunSummary,
    SceneTrace,
    StoryPlan,
)
from poiesis.application.use_cases import (
    ApplyPatchUseCase,
    ApproveSceneReviewUseCase,
    GenerateChapterUseCase,
    PublishChapterUseCase,
    RetrySceneUseCase,
    ReviewSceneUseCase,
    SceneGenerationContext,
)
from poiesis.config import Config, load_config
from poiesis.db.database import Database
from poiesis.domain.world.model import WorldModel
from poiesis.domain.world.repository import WorldRepository
from poiesis.llm.anthropic_client import AnthropicClient
from poiesis.llm.openai_client import OpenAIClient
from poiesis.llm.siliconflow_client import DEFAULT_SILICONFLOW_BASE_URL, SiliconFlowClient
from poiesis.pipeline.assembly.chapter_assembler import ChapterAssembler
from poiesis.pipeline.extraction.extractor_hub import ExtractorHub
from poiesis.pipeline.extraction.scene_extractor import SceneExtractor
from poiesis.pipeline.planning.chapter_planner import ChapterPlanner
from poiesis.pipeline.planning.scene_planner import ScenePlanner
from poiesis.pipeline.planning.story_planner import StoryPlanner
from poiesis.pipeline.summary.summarizer import ChapterSummarizer
from poiesis.pipeline.verification.hub import VerifierHub
from poiesis.pipeline.verification.scene_verifier import SceneVerifier
from poiesis.pipeline.writing.editor import ChapterEditor
from poiesis.pipeline.writing.scene_editor import SceneEditor
from poiesis.pipeline.writing.scene_writer import SceneWriter
from poiesis.pipeline.writing.writer import ChapterWriter
from poiesis.vector_store.store import VectorStore

_PROVIDER_TO_KEY = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
}


def _build_llm(cfg: Any, openai_key: str | None, anthropic_key: str | None, siliconflow_key: str | None) -> Any:
    """按配置构建 LLM 客户端。"""
    base_url = getattr(cfg, "base_url", None)
    if cfg.provider == "anthropic":
        return AnthropicClient(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=anthropic_key,
        )
    if cfg.provider == "siliconflow":
        return SiliconFlowClient(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=siliconflow_key,
            base_url=base_url or DEFAULT_SILICONFLOW_BASE_URL,
        )
    return OpenAIClient(
        model=cfg.model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        api_key=openai_key,
        base_url=base_url,
    )


def _load_key_from_db(db: Database, config_key: str) -> str | None:
    """优先从数据库读取 API Key，缺失时回退到环境变量。"""
    try:
        from poiesis.api.services.system_config_service import get_decrypted_key

        return get_decrypted_key(db, config_key) or os.getenv(config_key)
    except Exception:
        return os.getenv(config_key)


def _apply_model_overrides(cfg: Config, db: Database) -> None:
    """从数据库读取模型配置覆盖，确保控制台设置优先生效。"""
    llm_provider = db.get_system_config("llm_provider")
    llm_model = db.get_system_config("llm_model")
    planner_provider = db.get_system_config("planner_llm_provider")
    planner_model = db.get_system_config("planner_llm_model")
    judge_provider = db.get_system_config("judge_llm_provider")
    judge_model = db.get_system_config("judge_llm_model")

    if llm_provider:
        cfg.llm.provider = str(llm_provider)
    if llm_model:
        cfg.llm.model = str(llm_model)
    if planner_provider:
        cfg.planner_llm.provider = str(planner_provider)
    if planner_model:
        cfg.planner_llm.model = str(planner_model)
    if hasattr(cfg, "judge_llm") and judge_provider:
        cfg.judge_llm.provider = str(judge_provider)
    if hasattr(cfg, "judge_llm") and judge_model:
        cfg.judge_llm.model = str(judge_model)


def _build_context_from_db(
    config_path: str,
    db: Database,
    book_id: int,
) -> tuple[SceneGenerationContext, Config, dict[str, Any]]:
    """基于已有数据库连接构建运行上下文。"""
    cfg = load_config(config_path)
    _apply_model_overrides(cfg, db)
    book = db.get_book(book_id)
    if book is None:
        raise ValueError(f"book_id={book_id} 不存在")
    language = str(book.get("language") or "zh-CN")
    style_prompt = str(book.get("style_prompt") or "")
    naming_policy = str(book.get("naming_policy") or "localized_zh")

    openai_key = _load_key_from_db(db, "OPENAI_API_KEY")
    anthropic_key = _load_key_from_db(db, "ANTHROPIC_API_KEY")
    siliconflow_key = _load_key_from_db(db, "SILICONFLOW_API_KEY")

    planner_llm = _build_llm(cfg.planner_llm, openai_key, anthropic_key, siliconflow_key)
    writer_llm = _build_llm(cfg.llm, openai_key, anthropic_key, siliconflow_key)
    vector_store = VectorStore(cfg.vector_store.path, cfg.vector_store.embedding_model)
    story_planner = StoryPlanner(
        vector_store=vector_store,
        new_rule_budget=cfg.generation.new_rule_budget,
        language=language,
        style_prompt=style_prompt,
        naming_policy=naming_policy,
    )
    chapter_writer = ChapterWriter(
        vector_store=vector_store,
        target_word_count=max(600, cfg.generation.target_word_count // 3),
        language=language,
        style_prompt=style_prompt,
        naming_policy=naming_policy,
    )
    world = WorldModel()
    world.load_from_db(db, book_id=book_id)

    context = SceneGenerationContext(
        db=db,
        world=world,
        planner_llm=planner_llm,
        writer_llm=writer_llm,
        chapter_planner=ChapterPlanner(story_planner),
        scene_planner=ScenePlanner(),
        scene_writer=SceneWriter(chapter_writer),
        scene_extractor=SceneExtractor(ExtractorHub(language=language)),
        scene_verifier=SceneVerifier(VerifierHub(new_rule_budget=cfg.generation.new_rule_budget, language=language)),
        scene_editor=SceneEditor(ChapterEditor(language=language, style_prompt=style_prompt, naming_policy=naming_policy)),
        chapter_assembler=ChapterAssembler(),
        summarizer=ChapterSummarizer(language=language, style_prompt=style_prompt),
        book_id=book_id,
    )
    return context, cfg, book


def _build_context(
    config_path: str,
    book_id: int,
) -> tuple[SceneGenerationContext, Config, dict[str, Any]]:
    """构建新架构所需的显式依赖。"""
    db = Database(load_config(config_path).database.path)
    db.initialize_schema()
    return _build_context_from_db(config_path, db, book_id)


def _chapter_publish_blockers(chapter_row: dict[str, Any]) -> PublishBlockers:
    """把 run_chapters 中的 merge_result 反序列化成正式门禁结构。"""
    merge_result = chapter_row.get("merge_result_json") or {}
    return PublishBlockers.model_validate(
        {
            "chapter_status": chapter_row.get("status") or "draft",
            "can_publish": bool(merge_result.get("can_publish")),
            "blockers": list(merge_result.get("blockers") or []),
        }
    )


def _compute_publish_blockers(
    chapter_row: dict[str, Any],
    scene_rows: list[dict[str, Any]],
    pending_reviews: int,
) -> PublishBlockers:
    """基于当前 chapter/scene 实时重算发布门禁，避免依赖陈旧 merge_result。"""
    if str(chapter_row.get("status") or "") == "published":
        return PublishBlockers(chapter_status="published", can_publish=True, blockers=[])

    blockers: list[str] = []
    if any(str(item.get("status") or "") == "needs_review" for item in scene_rows):
        blockers.append("仍有待审阅场景。")
    if pending_reviews > 0:
        blockers.append(f"仍有 {pending_reviews} 条待处理审阅记录。")

    planner_output = chapter_row.get("planner_output_json") or {}
    must_progress_loops = [str(item) for item in planner_output.get("must_progress_loops") or []]
    progressed_loops = {
        str(update.get("loop_id") or "")
        for scene in scene_rows
        for update in (scene.get("changeset_json") or {}).get("loop_updates", [])
        if update.get("loop_id")
    }
    missing_required = [loop_id for loop_id in must_progress_loops if loop_id not in progressed_loops]
    if missing_required:
        blockers.append(f"本章尚未推进必需剧情线索：{'、'.join(missing_required)}。")

    status: ChapterStatus
    if blockers:
        status = "needs_review"
    elif scene_rows:
        status = "ready_to_publish"
    else:
        status = "draft"
    return PublishBlockers(
        chapter_status=status,
        can_publish=status == "ready_to_publish",
        blockers=blockers,
    )


def _compute_scene_only_publish_blockers(
    scene_rows: list[dict[str, Any]],
    pending_reviews: int,
) -> PublishBlockers:
    """当章节 trace 缺失时，仅依据 scene/review 状态推导最小门禁结果。"""
    blockers: list[str] = []
    if any(str(item.get("status") or "") == "needs_review" for item in scene_rows):
        blockers.append("仍有待审阅场景。")
    if pending_reviews > 0:
        blockers.append(f"仍有 {pending_reviews} 条待处理审阅记录。")

    status: ChapterStatus
    if blockers:
        status = "needs_review"
    elif scene_rows:
        status = "ready_to_publish"
    else:
        status = "draft"
    return PublishBlockers(
        chapter_status=status,
        can_publish=status == "ready_to_publish",
        blockers=blockers,
    )


def _build_fallback_chapter_plan(chapter_number: int, scene_rows: list[dict[str, Any]]) -> ChapterPlan:
    """针对历史残缺 run，使用 scene trace 反推出最小章节规划。"""
    first_plan = dict((scene_rows[0] if scene_rows else {}).get("scene_plan_json") or {})
    must_progress_loops: list[str] = []
    must_preserve: list[str] = []
    source_stubs: list[dict[str, Any]] = []
    for row in scene_rows:
        scene_plan = dict(row.get("scene_plan_json") or {})
        source_stubs.append(
            {
                "title": str(scene_plan.get("title") or ""),
                "goal": str(scene_plan.get("goal") or ""),
                "conflict": str(scene_plan.get("conflict") or ""),
                "turning_point": str(scene_plan.get("turning_point") or ""),
            }
        )
        for loop_id in scene_plan.get("required_loops") or []:
            if loop_id not in must_progress_loops:
                must_progress_loops.append(str(loop_id))
        for item in scene_plan.get("continuity_requirements") or []:
            if item not in must_preserve:
                must_preserve.append(str(item))

    return ChapterPlan(
        chapter_number=chapter_number,
        title=f"第 {chapter_number} 章",
        goal=str(first_plan.get("goal") or ""),
        must_preserve=must_preserve,
        must_progress_loops=must_progress_loops,
        scene_count_target=max(len(scene_rows), 1),
        source_plan={"scene_stubs": source_stubs},
    )


def _build_fallback_chapter_trace(
    db: Database,
    run_id: int,
    book_id: int,
    chapter_number: int,
    scene_rows: list[dict[str, Any]],
) -> tuple[ChapterTrace, PublishBlockers]:
    """为缺少 run_chapters 记录的历史任务构造只读章节视图。"""
    pending_reviews = db.count_pending_scene_reviews(run_id, chapter_number)
    publish = _compute_scene_only_publish_blockers(scene_rows, pending_reviews)
    scenes = [_build_scene_trace(run_id, scene) for scene in scene_rows]
    return (
        ChapterTrace(
            run_id=run_id,
            chapter_number=chapter_number,
            status=publish.chapter_status,
            story_plan=StoryPlan(book_id=book_id, focus=f"第 {chapter_number} 章"),
            chapter_plan=_build_fallback_chapter_plan(chapter_number, scene_rows),
            scenes=scenes,
            assembled_text="\n\n".join(scene.final_text.strip() for scene in scenes if scene.final_text.strip()),
            summary={},
            metrics={
                "scene_count": len(scene_rows),
                "review_scene_count": len(
                    [scene for scene in scene_rows if str(scene.get("status") or "") == "needs_review"]
                ),
                "pending_review_count": pending_reviews,
            },
            review_required=publish.chapter_status == "needs_review",
            error_message="章节 trace 缺失，当前视图由 scene trace 自动补建。",
        ),
        publish,
    )


def _build_scene_trace(run_id: int, scene_row: dict[str, Any]) -> SceneTrace:
    """把数据库记录映射为正式 SceneTrace。"""
    return SceneTrace.model_validate(
        {
            "run_id": run_id,
            "chapter_number": int(scene_row["chapter_number"]),
            "scene_number": int(scene_row["scene_number"]),
            "status": str(scene_row["status"]),
            "scene_plan": scene_row["scene_plan_json"],
            "draft": scene_row.get("draft_json") or None,
            "final_text": str(scene_row.get("final_text") or ""),
            "changeset": ChangeSet.model_validate(scene_row.get("changeset_json") or {}),
            "verifier_issues": scene_row.get("verifier_issues_json") or [],
            "review_required": bool(scene_row.get("review_required")),
            "review_reason": str(scene_row.get("review_reason") or ""),
            "review_status": str(scene_row.get("review_status") or "completed"),
            "metrics": scene_row.get("metrics_json") or {},
            "error_message": scene_row.get("error_message"),
        }
    )


def _build_chapter_trace(run_id: int, row: dict[str, Any], scenes: list[dict[str, Any]]) -> ChapterTrace:
    """把数据库记录映射为正式 ChapterTrace。"""
    planner_output = row.get("planner_output_json") or {}
    story_plan = StoryPlan.model_validate(
        {
            "book_id": 1,
            **dict((row.get("retrieval_pack_json") or {}).get("story_plan") or {}),
        }
    )
    return ChapterTrace(
        run_id=run_id,
        chapter_number=int(row["chapter_number"]),
        status=str(row["status"]),
        story_plan=story_plan,
        chapter_plan=ChapterPlan(
            chapter_number=int(row["chapter_number"]),
            title=str(planner_output.get("title") or ""),
            goal=str(planner_output.get("goal") or planner_output.get("chapter_goal") or ""),
            hook=str(planner_output.get("hook") or ""),
            must_preserve=list(planner_output.get("must_preserve") or []),
            must_progress_loops=list(planner_output.get("must_progress_loops") or []),
            scene_count_target=int(planner_output.get("scene_count_target") or 3),
            notes=list(planner_output.get("notes") or []),
            source_plan=dict(planner_output),
        ),
        scenes=[_build_scene_trace(run_id, scene) for scene in scenes],
        assembled_text=str(row.get("final_content") or ""),
        summary=dict(row.get("summary_json") or {}),
        metrics=dict(row.get("metrics_json") or {}),
        review_required=bool((row.get("merge_result_json") or {}).get("review_required")),
        error_message=row.get("error_message"),
    )


def _build_review_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把数据库 review 事件行映射成 API 响应结构。"""
    return [
        {
            "id": int(item["id"]),
            "review_id": int(item["review_id"]),
            "action": str(item["action"]),
            "status": str(item["status"]),
            "operator": str(item.get("operator") or ""),
            "input_payload": item.get("input_payload_json") or {},
            "result_payload": item.get("result_payload_json") or {},
            "created_at": str(item.get("created_at") or ""),
        }
        for item in rows
    ]


def _build_patch_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 patch 留痕映射成正式响应结构。"""
    return [
        {
            "id": int(item["id"]),
            "run_id": int(item["run_id"]),
            "chapter_number": int(item["chapter_number"]),
            "scene_number": int(item["scene_number"]),
            "patch_text": str(item.get("patch_text") or ""),
            "before_text": str(item.get("before_text") or ""),
            "after_text": str(item.get("after_text") or ""),
            "verifier_issues": item.get("verifier_issues_json") or [],
            "applied_successfully": bool(item.get("applied_successfully")),
            "created_at": str(item.get("created_at") or ""),
        }
        for item in rows
    ]


def _run_in_background(task: TaskInfo, config_path: str, chapter_count: int, book_id: int) -> None:
    """后台执行 scene 驱动生成。"""
    task.status = "running"
    task.add_log("任务开始：初始化 Scene 驱动写作链路…")

    try:
        context, cfg, _book = _build_context(config_path, book_id)
        run_id = context.db.create_run_trace(
            task_id=task.task_id,
            book_id=book_id,
            status="running",
            config_snapshot={"chapter_count": chapter_count, "mode": "scene_driven"},
            llm_snapshot={"writer": cfg.llm.model, "planner": cfg.planner_llm.model},
        )
        generator = GenerateChapterUseCase(context)

        existing = context.db.list_chapter_outputs(book_id)
        start_chapter = len(existing) + 1
        end_chapter = start_chapter + chapter_count - 1
        task.add_log(f"准备生成第 {start_chapter} 至第 {end_chapter} 章（Scene 模式）…")

        for i, chapter_number in enumerate(range(start_chapter, end_chapter + 1), start=1):
            task.current_chapter = i - 1
            task.add_log(f"第 {chapter_number} 章：开始规划和 scene 生成…")
            chapter_trace, _chapter_output = generator.execute(run_id=run_id, chapter_number=chapter_number)
            task.current_chapter = i
            task.add_log(f"第 {chapter_number} 章完成，包含 {len(chapter_trace.scenes)} 个 scene。")

        task.status = "completed"
        context.db.update_run_trace_status(run_id, "completed", finished=True)
        task.add_log("全部章节生成完成。")
    except Exception as exc:  # noqa: BLE001
        task.status = "failed"
        task.error = str(exc)
        task.add_log(f"生成失败：{exc}")
        if "run_id" in locals():
            try:
                context.db.update_run_trace_status(
                    run_id,
                    "failed",
                    error_message=str(exc),
                    finished=True,
                )
            except Exception:  # noqa: BLE001
                pass
        if "context" in locals():
            try:
                context.db.close()
            except Exception:  # noqa: BLE001
                pass


def start_run(config_path: str, chapter_count: int, book_id: int = 1) -> dict[str, Any]:
    """创建新 run 任务。"""
    db = Database(load_config(config_path).database.path)
    try:
        db.initialize_schema()
        if db.get_active_blueprint_revision(book_id) is None:
            raise ValueError("当前作品尚未锁定整书蓝图，请先在作品与蓝图管理页完成蓝图确认")
    finally:
        db.close()
    task = registry.create(total_chapters=chapter_count)
    thread = threading.Thread(
        target=_run_in_background,
        args=(task, config_path, chapter_count, book_id),
        daemon=True,
        name=f"poiesis-scene-run-{task.task_id[:8]}",
    )
    thread.start()
    return task.to_dict()


def run_sync(
    config_path: str,
    chapter_count: int,
    book_id: int = 1,
    log: Callable[[str], None] | None = None,
) -> int:
    """同步执行 scene 主链，供 CLI 使用。"""
    context, cfg, _book = _build_context(config_path, book_id)
    logger = log or (lambda _msg: None)
    try:
        if context.db.get_active_blueprint_revision(book_id) is None:
            raise ValueError("当前作品尚未锁定整书蓝图，请先在作品与蓝图管理页完成蓝图确认")
        run_id = context.db.create_run_trace(
            task_id=f"cli-run-{threading.get_ident()}",
            book_id=book_id,
            status="running",
            config_snapshot={"chapter_count": chapter_count, "mode": "scene_driven_cli"},
            llm_snapshot={"writer": cfg.llm.model, "planner": cfg.planner_llm.model},
        )
        generator = GenerateChapterUseCase(context)
        existing = context.db.list_chapter_outputs(book_id)
        start_chapter = len(existing) + 1

        for offset in range(chapter_count):
            chapter_number = start_chapter + offset
            logger(f"开始生成第 {chapter_number} 章（Scene 模式）")
            chapter_trace, _chapter_output = generator.execute(run_id=run_id, chapter_number=chapter_number)
            logger(f"第 {chapter_number} 章完成，包含 {len(chapter_trace.scenes)} 个 scene")

        context.db.update_run_trace_status(run_id, "completed", finished=True)
        return run_id
    except Exception:
        # 同步 CLI 需要把失败状态也写回 runs，便于后续排查。
        try:
            if "run_id" in locals():
                context.db.update_run_trace_status(run_id, "failed", finished=True)
        finally:
            raise
    finally:
        context.db.close()


def list_runs(db: Database) -> list[RunSummary]:
    """列出新的 scene 驱动 runs。"""
    runs = []
    for task in registry.all_tasks():
        record = db.get_run_trace_by_task_id(task.task_id)
        if record is None:
            continue
        runs.append(
            RunSummary(
                id=int(record["id"]),
                task_id=str(record["task_id"]),
                book_id=int(record["book_id"]),
                status=str(task.status),
                current_chapter=int(task.current_chapter),
                total_chapters=int(task.total_chapters),
                created_at=str(task.created_at),
                updated_at=str(task.updated_at),
                error_message=task.error,
            )
        )
    return sorted(runs, key=lambda item: item.updated_at, reverse=True)


def get_run_detail(db: Database, run_id: int) -> dict[str, Any] | None:
    """读取 run 详情。"""
    run_item = db.get_run_trace(run_id)
    if run_item is None:
        return None
    chapter_rows = {
        int(item["chapter_number"]): item for item in db.list_run_chapter_traces(run_id)
    }
    scene_rows = db.list_run_scene_traces(run_id)
    scenes_by_chapter: dict[int, list[dict[str, Any]]] = {}
    for item in scene_rows:
        scenes_by_chapter.setdefault(int(item["chapter_number"]), []).append(item)

    chapter_numbers = sorted(set(chapter_rows) | set(scenes_by_chapter))
    chapter_summaries = []
    for chapter_number in chapter_numbers:
        chapter_row: dict[str, Any] | None = chapter_rows.get(chapter_number)
        scenes = scenes_by_chapter.get(chapter_number, [])
        pending_reviews = db.count_pending_scene_reviews(run_id, chapter_number)
        summary: dict[str, Any]
        metrics: dict[str, Any]
        if chapter_row is None:
            publish = _compute_scene_only_publish_blockers(scenes, pending_reviews)
            summary = {}
            metrics = {
                "scene_count": len(scenes),
                "review_scene_count": len(
                    [scene for scene in scenes if str(scene.get("status") or "") == "needs_review"]
                ),
                "pending_review_count": pending_reviews,
            }
        else:
            publish = _compute_publish_blockers(chapter_row, scenes, pending_reviews)
            summary = chapter_row.get("summary_json") or {}
            metrics = chapter_row.get("metrics_json") or {}
        chapter_summaries.append(
            {
                "chapter_number": chapter_number,
                "status": publish.chapter_status,
                "summary": summary,
                "metrics": metrics,
                "review_required": publish.chapter_status == "needs_review",
                "can_publish": publish.can_publish,
                "blockers": publish.blockers,
            }
        )
    return {
        "run": RunSummary(
            id=int(run_item["id"]),
            task_id=str(run_item["task_id"]),
            book_id=int(run_item["book_id"]),
            status=str(run_item["status"]),
            current_chapter=len(chapter_numbers),
            total_chapters=len(chapter_numbers),
            created_at=str(run_item.get("started_at") or ""),
            updated_at=str(run_item.get("finished_at") or run_item.get("started_at") or ""),
            error_message=run_item.get("error_message"),
        ),
        "chapters": chapter_summaries,
    }


def get_chapter_detail(db: Database, run_id: int, chapter_number: int) -> dict[str, Any] | None:
    """读取单章和其 scenes。"""
    row = db.get_run_chapter_trace(run_id, chapter_number)
    scenes = db.list_run_scene_traces(run_id, chapter_number)
    if row is None:
        if not scenes:
            return None
        run_item = db.get_run_trace(run_id)
        if run_item is None:
            return None
        trace, publish = _build_fallback_chapter_trace(
            db,
            run_id,
            int(run_item["book_id"]),
            chapter_number,
            scenes,
        )
    else:
        publish = _compute_publish_blockers(
            row,
            scenes,
            db.count_pending_scene_reviews(run_id, chapter_number),
        )
        trace = _build_chapter_trace(run_id, row, scenes)
    output_row = db.get_chapter_output(trace.story_plan.book_id, chapter_number)
    output: ChapterOutput | None = None
    if output_row:
        output = ChapterOutput.model_validate(
            {
                "run_id": output_row["run_id"],
                "chapter_number": output_row["chapter_number"],
                "title": output_row["title"],
                "content": output_row["content"],
                "summary": output_row["summary_json"],
                "scene_count": output_row["scene_count"],
                "status": output_row["status"],
            }
        )
    return {
        "trace": trace,
        "output": output,
        "publish": publish,
    }


def get_scene_detail(db: Database, run_id: int, chapter_number: int, scene_number: int) -> dict[str, Any] | None:
    """读取单个 scene。"""
    scene = db.get_run_scene_trace(run_id, chapter_number, scene_number)
    if scene is None:
        return None
    review = db.get_scene_review_by_scene(run_id, chapter_number, scene_number)
    chapter = db.get_run_chapter_trace(run_id, chapter_number)
    chapter_scenes = db.list_run_scene_traces(run_id, chapter_number)
    pending_reviews = db.count_pending_scene_reviews(run_id, chapter_number)
    return {
        "scene": _build_scene_trace(run_id, scene),
        "review": review,
        "review_events": _build_review_events(db.list_scene_review_events(int(review["id"]))) if review else [],
        "patches": _build_patch_records(db.list_scene_patches(run_id, chapter_number, scene_number)),
        "publish_blockers": (
            _compute_publish_blockers(chapter, chapter_scenes, pending_reviews)
            if chapter
            else _compute_scene_only_publish_blockers(chapter_scenes, pending_reviews)
        ),
    }


def list_review_queue(db: Database, book_id: int = 1) -> list[ReviewQueueItem]:
    """读取审阅队列。"""
    return ReviewSceneUseCase(db).list_pending(book_id)


def review_action(
    db: Database,
    config_path: str,
    review_id: int,
    action: str,
    patch_text: str = "",
    operator: str = "admin",
) -> ReviewQueueItem | None:
    """执行审阅动作。"""
    review = db.get_scene_review(review_id)
    if review is None:
        return None
    run = db.get_run_trace(int(review["run_id"]))
    if run is None:
        return None
    context, _cfg, _book = _build_context_from_db(config_path, db, int(run["book_id"]))
    if action == "approve":
        return ApproveSceneReviewUseCase(context).execute(review_id, operator)
    if action == "retry":
        return RetrySceneUseCase(context).execute(review_id, operator)
    if action == "patch":
        return ApplyPatchUseCase(context).execute(review_id, patch_text, operator)
    raise ValueError(f"不支持的 review 动作：{action}")


def publish_chapter(
    db: Database,
    config_path: str,
    run_id: int,
    chapter_number: int,
) -> ChapterOutput:
    """人工确认发布章节。"""
    run = db.get_run_trace(run_id)
    if run is None:
        raise ValueError("run 不存在")
    context, _cfg, _book = _build_context_from_db(config_path, db, int(run["book_id"]))
    return PublishChapterUseCase(context).execute(run_id, chapter_number)


def list_loops(db: Database, book_id: int = 1) -> list[LoopState]:
    """返回 loop 列表。"""
    repo = WorldRepository()
    return [LoopState.model_validate(item) for item in repo.list_loops(db, book_id)]
