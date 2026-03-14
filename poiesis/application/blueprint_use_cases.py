"""创作蓝图用例：负责整书蓝图的生成、确认与重规划。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from poiesis.application.blueprint_contracts import (
    BlueprintLayer,
    BlueprintReplanRequest,
    BlueprintRevision,
    BookBlueprint,
    ChapterRoadmapItem,
    CharacterBlueprint,
    CharacterNode,
    ConceptVariant,
    ConceptVariantRegenerationResult,
    CreationIntent,
    CreativeIssue,
    CreativeRepairProposal,
    CreativeRepairRun,
    RelationshipBlueprintEdge,
    RelationshipConflictReport,
    RelationshipPendingItem,
    RelationshipRetconProposal,
    RoadmapValidationIssue,
    StoryArcPlan,
    WorldBlueprint,
)
from poiesis.application.creative_orchestrator import CreativeOrchestrator
from poiesis.db.database import Database
from poiesis.llm.base import LLMClient
from poiesis.pipeline.planning.roadmap_planner import RoadmapPlanner


@dataclass
class BlueprintContext:
    """蓝图用例的显式依赖。"""

    db: Database
    llm: LLMClient
    book_id: int
    planner: RoadmapPlanner


def _normalize_expanded_arc_numbers(raw: object, story_arcs: list[StoryArcPlan]) -> list[int]:
    """只保留有效阶段编号，避免前端和状态层出现脏数据。"""
    valid_numbers = {item.arc_number for item in story_arcs}
    values = raw if isinstance(raw, list) else []
    return sorted(
        {
            int(item)
            for item in values
            if isinstance(item, (int, float, str)) and str(item).isdigit() and int(item) in valid_numbers
        }
    )


def _decorate_story_arcs(
    planner: RoadmapPlanner,
    story_arcs: list[StoryArcPlan],
    roadmap: list[ChapterRoadmapItem],
    issues: list[RoadmapValidationIssue],
    completed_arc_numbers: list[int],
    *,
    confirmed: bool,
) -> list[StoryArcPlan]:
    """统一使用规划器补阶段工作台字段，避免前后端出现不同的门禁判断。"""
    return planner.decorate_story_arcs_for_workspace(
        story_arcs,
        roadmap,
        issues,
        completed_arc_numbers,
        confirmed=confirmed,
    )


def _build_unexpanded_arc_issues(
    planner: RoadmapPlanner,
    story_arcs: list[StoryArcPlan],
    completed_arc_numbers: list[int],
    roadmap: list[ChapterRoadmapItem],
) -> list[RoadmapValidationIssue]:
    """为未完成阶段补充动作型提示。

    这里不再给所有未完成阶段都发“生成下一章”动作，只允许当前最早未完成阶段真正可点击。
    """
    issues: list[RoadmapValidationIssue] = []
    decorated = planner.decorate_story_arcs_for_workspace(
        story_arcs,
        roadmap,
        [],
        completed_arc_numbers,
        confirmed=False,
    )
    for arc in decorated:
        if arc.arc_number in completed_arc_numbers or arc.next_chapter_number is None:
            continue
        action: Literal["generate_next_chapter", "review_arc"] = (
            "generate_next_chapter" if arc.can_generate_next_chapter else "review_arc"
        )
        message = (
            f"阶段“{arc.title}”当前仅完成 {arc.generated_chapter_count}/{arc.chapter_target_count} 章，"
            f"请先继续生成第 {arc.next_chapter_number} 章。"
            if arc.can_generate_next_chapter
            else (
                f"阶段“{arc.title}”尚未轮到生成，"
                f"请先完成第 {arc.blocking_arc_number} 幕。"
            )
        )
        issues.append(
            RoadmapValidationIssue(
                severity="warning",
                type="arc_not_completed",
                message=message,
                chapter_number=arc.next_chapter_number,
                story_stage=arc.title,
                arc_number=arc.arc_number,
                scope="arc",
                suggested_action=action,
            )
        )
    return issues


def _build_review_queue_creative_issues(db: Database, book_id: int) -> list[CreativeIssue]:
    """把待审阅 scene 项折叠进统一问题队列。

    当前属于第二阶段“最小接入”：
    - review / scene 先只进入统一控制面，方便作者在同一页看到跨层问题来源；
    - 这些问题暂时仍是只读，不接入 apply / rollback；
    - 后续如果 scene verifier 与 review queue 分开建 detector，这里再细分 source_layer。
    """
    issues: list[CreativeIssue] = []
    if not hasattr(db, "list_scene_reviews"):
        return issues

    for review in db.list_scene_reviews(book_id):
        if str(review.get("status") or "") != "pending":
            continue
        review_id = int(review.get("id") or 0)
        run_id = int(review.get("run_id") or 0)
        chapter_number = int(review.get("chapter_number") or 0) or None
        scene_number = int(review.get("scene_number") or 0) or None
        review_status = str(review.get("status") or "").strip()
        reason = str(review.get("reason") or "").strip()
        scene_status = str(review.get("scene_status") or "").strip() or "needs_review"
        latest_result_summary = str(review.get("latest_result_summary") or "").strip()
        patch_text = str(review.get("patch_text") or "").strip()
        event_count = int(review.get("event_count") or 0)
        message = (
            f"第 {chapter_number} 章第 {scene_number} 场待审阅：{reason or latest_result_summary or '存在需要人工处理的场景问题。'}"
            if chapter_number and scene_number
            else reason or latest_result_summary or "存在需要人工处理的场景问题。"
        )
        issues.append(
            CreativeIssue(
                issue_id=f"review-issue-{review_id}",
                book_id=book_id,
                source_layer="review",
                target_type="scene_chapter",
                target_ref={
                    "review_id": review_id,
                    "run_id": run_id,
                    "chapter_number": chapter_number,
                    "scene_number": scene_number,
                },
                issue_type="scene_review_pending",
                severity="fatal",
                message=message,
                detected_by="scene_review_queue",
                repairability="manual",
                status="open",
                suggested_strategy="scene_rewrite",
                # review 当前只读接入工作台，因此把详情显式塞进 context_payload。
                # 这样前端 inspector 可以展示结构化审阅信息，而不是从 message 里反向拆字段。
                context_payload={
                    "review_id": review_id,
                    "run_id": run_id,
                    "chapter_number": chapter_number,
                    "scene_number": scene_number,
                    "review_status": review_status,
                    "reason": reason,
                    "scene_status": scene_status,
                    "latest_result_summary": latest_result_summary,
                    "event_count": event_count,
                    "patch_text": patch_text,
                },
            )
        )
    return issues


def _load_creative_repair_proposals(state: dict[str, Any]) -> list[CreativeRepairProposal]:
    """把蓝图状态里的修复提案反序列化成正式模型。"""
    return [
        CreativeRepairProposal.model_validate(item)
        for item in state.get("creative_repair_proposals") or []
        if isinstance(item, dict)
    ]


def _load_creative_repair_runs(state: dict[str, Any]) -> list[CreativeRepairRun]:
    """把蓝图状态里的执行记录反序列化成正式模型。"""
    return [
        CreativeRepairRun.model_validate(item)
        for item in state.get("creative_repair_runs") or []
        if isinstance(item, dict)
    ]


def _load_creative_control_snapshots(state: dict[str, Any]) -> list[dict[str, object]]:
    """读取控制面快照列表。

    快照暂时只在用例层按 dict 处理，避免为第一阶段回滚额外引入一层不必要的数据库结构。
    """
    return [
        item
        for item in state.get("creative_control_snapshots") or []
        if isinstance(item, dict)
    ]


def _upsert_blueprint_business_state(
    db: Database,
    book_id: int,
    payload: dict[str, object],
    *,
    creative_repair_proposals: list[dict[str, object]] | None = None,
    creative_repair_runs: list[dict[str, object]] | None = None,
    creative_control_snapshots: list[dict[str, object]] | None = None,
) -> None:
    """把业务真源和控制面状态一次性写回 book_blueprints。

    回滚时需要恢复一整个蓝图工作态，但又不能把 proposals / runs 历史抹掉，
    因此这里把“业务真源”和“控制面元数据”显式分开。
    """
    db.upsert_book_blueprint_state(
        book_id,
        status=str(payload.get("status") or "intent_pending"),
        current_step=str(payload.get("current_step") or "intent"),
        selected_variant_id=cast(int | None, payload.get("selected_variant_id")),
        active_revision_id=cast(int | None, payload.get("active_revision_id")),
        world_draft=cast(dict[str, Any] | None, payload.get("world_draft")),
        world_confirmed=cast(dict[str, Any] | None, payload.get("world_confirmed")),
        character_draft=cast(list[dict[str, Any]] | None, payload.get("character_draft")),
        character_confirmed=cast(list[dict[str, Any]] | None, payload.get("character_confirmed")),
        relationship_graph_draft=cast(list[dict[str, Any]] | None, payload.get("relationship_graph_draft")),
        relationship_graph_confirmed=cast(list[dict[str, Any]] | None, payload.get("relationship_graph_confirmed")),
        story_arcs_draft=cast(list[dict[str, Any]] | None, payload.get("story_arcs_draft")),
        story_arcs_confirmed=cast(list[dict[str, Any]] | None, payload.get("story_arcs_confirmed")),
        expanded_arc_numbers=cast(list[int] | None, payload.get("expanded_arc_numbers")),
        roadmap_draft=cast(list[dict[str, Any]] | None, payload.get("roadmap_draft")),
        roadmap_confirmed=cast(list[dict[str, Any]] | None, payload.get("roadmap_confirmed")),
        blueprint_continuity_state=cast(dict[str, Any] | None, payload.get("blueprint_continuity_state")),
        roadmap_validation_issues=cast(list[dict[str, Any]] | None, payload.get("roadmap_validation_issues")),
        creative_repair_proposals=creative_repair_proposals,
        creative_repair_runs=creative_repair_runs,
        creative_control_snapshots=creative_control_snapshots,
    )


def _load_confirmed_world(planner: RoadmapPlanner, state: dict[str, Any]) -> WorldBlueprint | None:
    """连续性校验只参考已确认世界观，没有确认就退回到 None。"""
    if not state.get("world_confirmed"):
        return None
    return planner.normalize_world_blueprint_payload(state.get("world_confirmed") or {})


def _load_confirmed_relationship_graph(
    planner: RoadmapPlanner,
    state: dict[str, Any],
) -> list[RelationshipBlueprintEdge]:
    """关系冲突校验只使用已确认关系图，不拿草稿关系做硬阻塞。"""
    characters = planner.normalize_character_blueprints_payload(
        state.get("character_confirmed") or state.get("character_draft") or []
    )
    return planner.normalize_relationship_blueprint_edges_payload(
        state.get("relationship_graph_confirmed") or [],
        characters,
    )


def build_book_blueprint(db: Database, book_id: int) -> BookBlueprint:
    """把当前蓝图工作态和版本快照组装成统一响应。"""
    state = db.get_book_blueprint_state(book_id) or {}
    planner = RoadmapPlanner()
    orchestrator = CreativeOrchestrator(planner)
    intent_row = db.get_creation_intent(book_id)
    variants = [ConceptVariant.model_validate(item) for item in db.list_concept_variants(book_id)]
    selected_variant = None
    selected_variant_id = state.get("selected_variant_id")
    for item in variants:
        if item.id == selected_variant_id or item.selected:
            selected_variant = item
            break

    revisions = [
        BlueprintRevision.model_validate(
            {
                "id": item["id"],
                "revision_number": item["revision_number"],
                "is_active": bool(item.get("is_active")),
                "change_reason": str(item.get("change_reason") or ""),
                "change_summary": str(item.get("change_summary") or ""),
                "affected_range": list(item.get("affected_range") or []),
                "created_at": str(item.get("created_at") or ""),
            }
        )
        for item in db.list_blueprint_revisions(book_id)
    ]
    roadmap_draft = planner.normalize_roadmap_payload(state.get("roadmap_draft") or [])
    roadmap_confirmed = planner.normalize_roadmap_payload(state.get("roadmap_confirmed") or [])
    raw_story_arcs_draft = state.get("story_arcs_draft") or []
    raw_story_arcs_confirmed = state.get("story_arcs_confirmed") or []
    story_arcs_draft = planner.normalize_story_arcs_payload(raw_story_arcs_draft)
    story_arcs_confirmed = planner.normalize_story_arcs_payload(raw_story_arcs_confirmed)
    confirmed_world = _load_confirmed_world(planner, state)
    confirmed_relationship_graph = _load_confirmed_relationship_graph(planner, state)
    if not story_arcs_draft and roadmap_draft:
        story_arcs_draft = planner.derive_story_arcs_from_roadmap(roadmap_draft)
    if not story_arcs_confirmed and roadmap_confirmed:
        story_arcs_confirmed = planner.derive_story_arcs_from_roadmap(roadmap_confirmed)
    base_story_arcs = story_arcs_confirmed or story_arcs_draft
    base_roadmap = roadmap_confirmed or roadmap_draft
    expanded_arc_numbers = _normalize_expanded_arc_numbers(state.get("expanded_arc_numbers"), base_story_arcs)
    if not expanded_arc_numbers and base_story_arcs and base_roadmap:
        expanded_arc_numbers = [
            arc.arc_number
            for arc in base_story_arcs
            if all(
                any(item.chapter_number == chapter_number for item in base_roadmap)
                for chapter_number in range(arc.start_chapter, arc.end_chapter + 1)
            )
        ]
    roadmap_issues = (
        planner.verify_roadmap(
            base_story_arcs,
            base_roadmap,
            world=confirmed_world,
            relationship_graph=confirmed_relationship_graph,
        )
        if (base_story_arcs and base_roadmap)
        else []
    )
    roadmap_issues = [
        *roadmap_issues,
        *_build_unexpanded_arc_issues(planner, base_story_arcs, expanded_arc_numbers, base_roadmap),
    ]
    creative_repair_proposals = _load_creative_repair_proposals(state)
    creative_repair_runs = _load_creative_repair_runs(state)
    roadmap_creative_issues = orchestrator.build_creative_issues(
        book_id=book_id,
        story_arcs=base_story_arcs,
        roadmap=base_roadmap,
        roadmap_issues=roadmap_issues,
        stored_proposals=creative_repair_proposals,
    )
    review_creative_issues = _build_review_queue_creative_issues(db, book_id)
    creative_issues = sorted(
        [*roadmap_creative_issues, *review_creative_issues],
        key=lambda item: (
            0 if item.severity == "fatal" else 1,
            0 if item.source_layer == "roadmap" else 1,
            int(item.target_ref.get("chapter_number") or 0),
            item.issue_type,
        ),
    )
    decorated_story_arcs_draft = _decorate_story_arcs(
        planner,
        story_arcs_draft,
        roadmap_draft,
        roadmap_issues,
        expanded_arc_numbers,
        confirmed=False,
    )
    decorated_story_arcs_confirmed = _decorate_story_arcs(
        planner,
        story_arcs_confirmed,
        roadmap_confirmed,
        roadmap_issues,
        expanded_arc_numbers,
        confirmed=bool(roadmap_confirmed),
    )
    continuity_state = planner.rebuild_continuity_state(base_roadmap)

    return BookBlueprint(
        book_id=book_id,
        status=cast(
            Literal[
                "intent_pending",
                "concept_generated",
                "concept_selected",
                "world_ready",
                "world_confirmed",
                "characters_ready",
                "characters_confirmed",
                "story_arcs_ready",
                "roadmap_ready",
                "locked",
            ],
            str(state.get("status") or "intent_pending"),
        ),
        current_step=str(state.get("current_step") or "intent"),
        active_revision_id=state.get("active_revision_id"),
        selected_variant_id=selected_variant_id,
        intent=CreationIntent.model_validate(intent_row) if intent_row else None,
        concept_variants=variants,
        selected_variant=selected_variant,
        world_draft=planner.normalize_world_blueprint_payload(state["world_draft"]) if state.get("world_draft") else None,
        world_confirmed=(
            planner.normalize_world_blueprint_payload(state["world_confirmed"])
            if state.get("world_confirmed")
            else None
        ),
        character_draft=planner.normalize_character_blueprints_payload(state.get("character_draft") or []),
        character_confirmed=planner.normalize_character_blueprints_payload(state.get("character_confirmed") or []),
        relationship_graph_draft=planner.normalize_relationship_blueprint_edges_payload(
            state.get("relationship_graph_draft") or [],
            planner.normalize_character_blueprints_payload(state.get("character_draft") or []),
        ),
        relationship_graph_confirmed=planner.normalize_relationship_blueprint_edges_payload(
            state.get("relationship_graph_confirmed") or [],
            planner.normalize_character_blueprints_payload(
                state.get("character_confirmed") or state.get("character_draft") or []
            ),
        ),
        relationship_pending=[
            RelationshipPendingItem.model_validate(item)
            for item in db.list_relationship_pending_items(book_id, status="pending")
        ]
        if hasattr(db, "list_relationship_pending_items")
        else [],
        story_arcs_draft=[
            StoryArcPlan.model_validate(item.model_dump(mode="json")) for item in decorated_story_arcs_draft
        ],
        story_arcs_confirmed=[
            StoryArcPlan.model_validate(item.model_dump(mode="json")) for item in decorated_story_arcs_confirmed
        ],
        expanded_arc_numbers=expanded_arc_numbers,
        roadmap_draft=roadmap_draft,
        roadmap_confirmed=roadmap_confirmed,
        continuity_state=continuity_state,
        roadmap_validation_issues=[
            RoadmapValidationIssue.model_validate(item.model_dump(mode="json"))
            for item in roadmap_issues
        ],
        creative_issues=creative_issues,
        creative_repair_proposals=creative_repair_proposals,
        creative_repair_runs=creative_repair_runs,
        revisions=revisions,
    )


class SaveCreationIntentUseCase:
    """保存创作意图，并初始化蓝图工作态。"""

    def __init__(self, context: BlueprintContext) -> None:
        self._context = context

    def execute(self, payload: CreationIntent) -> BookBlueprint:
        self._context.db.upsert_creation_intent(self._context.book_id, payload.model_dump(mode="json"))
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="intent_pending",
            current_step="concept",
            blueprint_continuity_state={},
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GenerateConceptVariantsUseCase:
    """根据创作意图生成 3 版候选方向。"""

    def __init__(self, context: BlueprintContext) -> None:
        self._context = context

    def execute(self) -> BookBlueprint:
        intent_row = self._context.db.get_creation_intent(self._context.book_id)
        if intent_row is None:
            raise ValueError("请先填写创作意图")
        variants = self._context.planner.generate_concept_variants(
            CreationIntent.model_validate(intent_row),
            self._context.llm,
        )
        self._context.db.replace_concept_variants(
            self._context.book_id,
            [item.model_dump(mode="json") for item in variants],
        )
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="concept_generated",
            current_step="concept",
            blueprint_continuity_state={},
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class RegenerateConceptVariantUseCase:
    """只重生成单条候选方向，避免作者每次整组重来。"""

    def __init__(self, context: BlueprintContext) -> None:
        self._context = context

    def execute(self, variant_id: int) -> ConceptVariantRegenerationResult:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        if str(state.get("status") or "") != "concept_generated":
            raise ValueError("只有在候选方向阶段才能重生成单条方向")
        variant = self._context.db.get_concept_variant(variant_id)
        if variant is None or int(variant["book_id"]) != self._context.book_id:
            raise ValueError("候选方向不存在")
        intent_row = self._context.db.get_creation_intent(self._context.book_id)
        if intent_row is None:
            raise ValueError("请先填写创作意图")

        siblings = [
            ConceptVariant.model_validate(item)
            for item in self._context.db.list_concept_variants(self._context.book_id)
            if int(item["id"]) != variant_id
        ]
        regenerated, similarity_issue, attempts, applied = self._context.planner.regenerate_concept_variant(
            CreationIntent.model_validate(intent_row),
            ConceptVariant.model_validate(variant),
            siblings,
            self._context.llm,
        )
        if applied:
            self._context.db.update_concept_variant(variant_id, regenerated.model_dump(mode="json"))
            blueprint = build_book_blueprint(self._context.db, self._context.book_id)
            return ConceptVariantRegenerationResult(
                status="applied",
                target_variant_id=variant_id,
                attempt_count=len(attempts),
                warnings=["已自动替换为差异更明显的新版本。"],
                applied_variant=next(
                    (item for item in blueprint.concept_variants if item.id == variant_id),
                    regenerated,
                ),
                similarity_report=similarity_issue,
                attempts=attempts,
                blueprint=blueprint,
            )
        return ConceptVariantRegenerationResult(
            status="needs_confirmation",
            target_variant_id=variant_id,
            attempt_count=len(attempts),
            warnings=["多轮回炉后仍存在明显相似度，请人工决定是否替换原候选。"],
            proposed_variant=regenerated,
            similarity_report=similarity_issue,
            attempts=attempts,
            blueprint=build_book_blueprint(self._context.db, self._context.book_id),
        )


class AcceptRegeneratedConceptVariantUseCase:
    """作者确认接受一版仍偏相似但更符合方向需求的候选提案。"""

    def __init__(self, context: BlueprintContext) -> None:
        self._context = context

    def execute(self, variant_id: int, proposal: ConceptVariant) -> BookBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        if str(state.get("status") or "") != "concept_generated":
            raise ValueError("只有在候选方向阶段才能确认重生成提案")
        variant = self._context.db.get_concept_variant(variant_id)
        if variant is None or int(variant["book_id"]) != self._context.book_id:
            raise ValueError("候选方向不存在")
        current = ConceptVariant.model_validate(variant)
        if proposal.variant_no != current.variant_no:
            raise ValueError("重生成提案与当前候选编号不匹配")
        proposal.id = current.id
        proposal.selected = current.selected
        self._context.db.update_concept_variant(variant_id, proposal.model_dump(mode="json"))
        return build_book_blueprint(self._context.db, self._context.book_id)


class SelectConceptVariantUseCase:
    """选定一个候选方向作为后续蓝图的基础。"""

    def __init__(self, context: BlueprintContext) -> None:
        self._context = context

    def execute(self, variant_id: int) -> BookBlueprint:
        variant = self._context.db.get_concept_variant(variant_id)
        if variant is None or int(variant["book_id"]) != self._context.book_id:
            raise ValueError("候选方向不存在")
        self._context.db.select_concept_variant(self._context.book_id, variant_id)
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="concept_selected",
            current_step="world",
            selected_variant_id=variant_id,
            world_draft={},
            character_draft=[],
            roadmap_draft=[],
            blueprint_continuity_state={},
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class _BlueprintLayerBase:
    """生成/确认蓝图层时共享的加载与同步逻辑。"""

    def __init__(self, context: BlueprintContext) -> None:
        self._context = context

    def _require_intent(self) -> CreationIntent:
        intent_row = self._context.db.get_creation_intent(self._context.book_id)
        if intent_row is None:
            raise ValueError("创作意图不存在")
        return CreationIntent.model_validate(intent_row)

    def _require_selected_variant(self) -> ConceptVariant:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        variant_id = state.get("selected_variant_id")
        if not variant_id:
            raise ValueError("请先选择候选方向")
        row = self._context.db.get_concept_variant(int(variant_id))
        if row is None:
            raise ValueError("已选候选方向不存在")
        return ConceptVariant.model_validate(row)

    def _require_world_confirmed(self) -> WorldBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        payload = state.get("world_confirmed") or state.get("world_draft")
        if not payload:
            raise ValueError("请先生成并确认世界观蓝图")
        return self._context.planner.normalize_world_blueprint_payload(payload)

    def _require_character_confirmed(self) -> list[CharacterBlueprint]:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        payload = state.get("character_confirmed") or state.get("character_draft") or []
        if not payload:
            raise ValueError("请先生成并确认人物蓝图")
        characters = self._context.planner.normalize_character_blueprints_payload(payload)
        if not characters:
            raise ValueError("请先生成并确认人物蓝图")
        return characters

    def _load_confirmed_world_optional(self) -> WorldBlueprint | None:
        """路线校验只读取已确认世界观，避免世界观草稿在未确认时成为硬约束。"""
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        return _load_confirmed_world(self._context.planner, state)

    def _load_confirmed_relationship_graph(self) -> list[RelationshipBlueprintEdge]:
        """路线校验只使用已确认关系图，避免草稿层误伤章节生成。"""
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        return _load_confirmed_relationship_graph(self._context.planner, state)

    def _verify_roadmap(
        self,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
    ) -> list[RoadmapValidationIssue]:
        """统一走同一套 verifier，并把已确认世界/关系约束带进去。"""
        return self._context.planner.verify_roadmap(
            story_arcs,
            roadmap,
            world=self._load_confirmed_world_optional(),
            relationship_graph=self._load_confirmed_relationship_graph(),
        )

    def _rebuild_continuity_state(self, roadmap: list[ChapterRoadmapItem]) -> dict[str, object]:
        """连续性工作态始终从 roadmap 重建，避免局部修改留下脏状态。"""
        return self._context.planner.rebuild_continuity_state(roadmap).model_dump(mode="json")

    def _creative_orchestrator(self) -> CreativeOrchestrator:
        """统一返回当前上下文使用的闭环编排器。

        第一阶段虽然只落 roadmap，但问题识别、提案策略和回滚约束已经集中收口到
        CreativeOrchestrator，避免后续 scene / canon 再各写一套相似逻辑。
        """
        return CreativeOrchestrator(self._context.planner)

    def _load_story_arcs_and_roadmap(
        self,
        state: dict[str, Any],
    ) -> tuple[list[StoryArcPlan], list[ChapterRoadmapItem], list[int]]:
        """从当前蓝图工作态读取“正在生效的路线真源”。

        这里优先取 draft，是因为第一阶段闭环控制面主要服务蓝图工作台；
        只有在草稿为空时，才退回到 confirmed，保证老数据仍然能被只读检查。
        """
        story_arcs = self._context.planner.normalize_story_arcs_payload(
            state.get("story_arcs_draft") or state.get("story_arcs_confirmed") or []
        )
        roadmap = self._context.planner.normalize_roadmap_payload(
            state.get("roadmap_draft") or state.get("roadmap_confirmed") or []
        )
        expanded_arc_numbers = _normalize_expanded_arc_numbers(state.get("expanded_arc_numbers"), story_arcs)
        return story_arcs, roadmap, expanded_arc_numbers

    def _verify_roadmap_with_gate_issues(
        self,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        expanded_arc_numbers: list[int],
    ) -> list[RoadmapValidationIssue]:
        """把静态 verifier 结果和阶段门禁提示合并成统一问题集合。"""
        issues = self._verify_roadmap(story_arcs, roadmap) if (story_arcs and roadmap) else []
        return [
            *issues,
            *_build_unexpanded_arc_issues(
                self._context.planner,
                story_arcs,
                expanded_arc_numbers,
                roadmap,
            ),
        ]

    def _length_to_chapter_count(self, intent: CreationIntent) -> int:
        raw = intent.length_preference.strip()
        if raw.isdigit():
            return max(6, min(int(raw), 80))
        if "短" in raw:
            return 8
        if "长" in raw or "宏大" in raw:
            return 20
        return 12

    def _sync_world_to_canon(self, world: WorldBlueprint) -> None:
        """世界观确认后，把核心规则同步到现有 canon。"""
        self._context.db.delete_world_rules(self._context.book_id)
        for rule in world.immutable_rules:
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key=rule.key,
                description=rule.description,
                is_immutable=bool(rule.is_immutable),
                category=rule.category or "world",
            )
        if world.setting_summary:
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key="world_setting",
                description=world.setting_summary,
                is_immutable=True,
                category="setting",
            )
        if world.era_context:
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key="era_context",
                description=world.era_context,
                is_immutable=True,
                category="setting",
            )
        if world.social_order:
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key="social_order",
                description=world.social_order,
                is_immutable=False,
                category="setting",
            )
        if world.power_system.core_mechanics:
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key="power_system_core",
                description=world.power_system.core_mechanics,
                is_immutable=True,
                category="power",
            )
        for faction in world.factions:
            if not faction.name:
                continue
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key=f"faction:{faction.name}",
                description=f"{faction.position}｜{faction.goal}",
                is_immutable=False,
                category="faction",
            )
        for taboo in world.taboo_rules:
            if not taboo.key:
                continue
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key=f"taboo:{taboo.key}",
                description=f"{taboo.description}｜后果：{taboo.consequence}",
                is_immutable=True,
                category="taboo",
            )

    def _sync_characters_to_canon(self, characters: list[CharacterBlueprint]) -> None:
        """人物蓝图确认后，同步到现有角色 canon。"""
        self._context.db.delete_characters(self._context.book_id)
        nodes: list[dict[str, object]] = []
        for item in characters:
            node = CharacterNode(
                character_id=self._character_id(item.name),
                name=item.name,
                role=item.role,
                public_persona=item.public_persona,
                core_motivation=item.core_motivation,
                fatal_flaw=item.fatal_flaw,
                non_negotiable_traits=item.non_negotiable_traits,
                arc_outline=item.arc_outline,
            )
            nodes.append(node.model_dump(mode="json"))
            self._context.db.upsert_character(
                book_id=self._context.book_id,
                name=item.name,
                description=item.public_persona,
                core_motivation=item.core_motivation,
                attributes={
                    "role": item.role,
                    "fatal_flaw": item.fatal_flaw,
                    "non_negotiable_traits": item.non_negotiable_traits,
                    "relationship_constraints": item.relationship_constraints,
                    "arc_outline": item.arc_outline,
                },
            )
        self._context.db.replace_character_nodes(self._context.book_id, nodes)

    def _sync_relationship_graph(
        self,
        edges: list[RelationshipBlueprintEdge],
    ) -> None:
        """把确认后的关系图谱同步到执行态表。"""
        self._context.db.replace_relationship_graph(
            self._context.book_id,
            [item.model_dump(mode="json") for item in edges],
        )

    def _character_id(self, name: str) -> str:
        """统一人物节点 ID，避免前后端和执行层命名漂移。"""
        return name.strip().replace(" ", "_")

    def _sync_planned_loops(self, roadmap: list[ChapterRoadmapItem]) -> None:
        """章节路线确认后，把计划中的关键线索种到 loop 状态里。"""
        for chapter in roadmap:
            for index, raw_loop in enumerate(chapter.planned_loops, start=1):
                loop_id = raw_loop.loop_id or f"chapter-{chapter.chapter_number}-loop-{index}"
                title = raw_loop.title or raw_loop.summary or loop_id
                due_start = raw_loop.due_start_chapter
                due_end = raw_loop.due_end_chapter
                due_window = ""
                if due_start is not None and due_end is not None:
                    due_window = f"第 {due_start}-{due_end} 章"
                elif due_end is not None:
                    due_window = f"最迟第 {due_end} 章"
                self._context.db.upsert_loop(
                    self._context.book_id,
                    {
                        "loop_id": loop_id,
                        "title": title,
                        "status": raw_loop.status or "open",
                        "introduced_in_scene": "",
                        "due_start_chapter": due_start,
                        "due_end_chapter": due_end,
                        "due_window": due_window,
                        "priority": raw_loop.priority,
                        "related_characters": list(raw_loop.related_characters),
                        "resolution_requirements": list(raw_loop.resolution_requirements),
                        "last_updated_scene": "",
                    },
                )


class GenerateWorldBlueprintUseCase(_BlueprintLayerBase):
    """生成世界观草稿。"""

    def execute(self, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._context.planner.generate_world(intent, variant, self._context.llm, feedback)
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="world_ready",
            current_step="world",
            world_draft=world.model_dump(mode="json"),
            character_draft=[],
            character_confirmed=[],
            roadmap_draft=[],
            roadmap_confirmed=[],
            blueprint_continuity_state={},
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GenerateCharacterBlueprintUseCase(_BlueprintLayerBase):
    """生成人物蓝图草稿。"""

    def execute(self, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._context.planner.generate_characters(intent, variant, world, self._context.llm, feedback)
        relationship_graph = self._context.planner.generate_relationship_graph(
            intent,
            variant,
            world,
            characters,
            self._context.llm,
            feedback,
        )
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="characters_ready",
            current_step="characters",
            character_draft=[item.model_dump(mode="json") for item in characters],
            relationship_graph_draft=[item.model_dump(mode="json") for item in relationship_graph],
            roadmap_draft=[],
            roadmap_confirmed=[],
            blueprint_continuity_state={},
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GenerateStoryArcsUseCase(_BlueprintLayerBase):
    """首次只生成整书阶段骨架，不立即展开章节。"""

    def execute(self, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        story_arcs = self._context.planner.generate_story_arcs_only(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=self._context.llm,
            feedback=feedback,
            chapter_count=self._length_to_chapter_count(intent),
        )
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="story_arcs_ready",
            current_step="roadmap",
            story_arcs_draft=[item.model_dump(mode="json") for item in story_arcs],
            expanded_arc_numbers=[],
            roadmap_draft=[],
            blueprint_continuity_state={},
            roadmap_validation_issues=[],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GenerateRoadmapUseCase(GenerateStoryArcsUseCase):
    """兼容旧命名，首次生成时只返回阶段骨架。"""


class GenerateNextArcChapterUseCase(_BlueprintLayerBase):
    """顺序生成单个阶段的下一章，作为路线工作台主入口。"""

    def execute(self, arc_number: int, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        story_arcs = self._context.planner.normalize_story_arcs_payload(
            state.get("story_arcs_draft") or state.get("story_arcs_confirmed") or []
        )
        if not story_arcs:
            raise ValueError("当前还没有阶段骨架，请先生成阶段骨架。")
        expanded_arc_numbers = _normalize_expanded_arc_numbers(state.get("expanded_arc_numbers"), story_arcs)
        gate_decorated_arcs = self._context.planner.decorate_story_arcs_for_workspace(
            story_arcs,
            self._context.planner.normalize_roadmap_payload(
                state.get("roadmap_draft") or state.get("roadmap_confirmed") or []
            ),
            [],
            expanded_arc_numbers,
            confirmed=False,
        )
        target_gate_arc = next((item for item in gate_decorated_arcs if item.arc_number == arc_number), None)
        if target_gate_arc is not None and not target_gate_arc.can_generate_next_chapter:
            raise ValueError(f"请先完成前序阶段：第 {target_gate_arc.blocking_arc_number} 幕。")
        target_arc = next((item for item in story_arcs if item.arc_number == arc_number), None)
        if target_arc is None:
            raise ValueError(f"第 {arc_number} 幕不存在。")
        current_roadmap = self._context.planner.normalize_roadmap_payload(
            state.get("roadmap_draft") or state.get("roadmap_confirmed") or []
        )
        progress = self._context.planner.summarize_story_arc_progress(target_arc, current_roadmap)
        next_chapter_number = cast(int | None, progress["next_chapter_number"])
        if next_chapter_number is None:
            raise ValueError(f"第 {arc_number} 幕已完成全部章节生成。")
        next_chapter = self._context.planner.generate_next_arc_chapter(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=self._context.llm,
            story_arc=target_arc,
            feedback=feedback,
            existing_roadmap=current_roadmap,
        )
        merged = sorted([*current_roadmap, next_chapter], key=lambda item: item.chapter_number)
        target_progress_after = self._context.planner.summarize_story_arc_progress(target_arc, merged)
        next_expanded_arc_numbers = (
            sorted(set([*expanded_arc_numbers, arc_number]))
            if bool(target_progress_after["completed"])
            else expanded_arc_numbers
        )
        merged_issues = self._verify_roadmap(story_arcs, merged)
        merged_arcs = [
            arc
            for arc in story_arcs
        ]
        status = "roadmap_ready" if len(next_expanded_arc_numbers) == len(story_arcs) and story_arcs else "story_arcs_ready"

        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status=status,
            current_step="roadmap",
            story_arcs_draft=[item.model_dump(mode="json") for item in merged_arcs],
            expanded_arc_numbers=next_expanded_arc_numbers,
            roadmap_draft=[item.model_dump(mode="json") for item in merged],
            blueprint_continuity_state=self._rebuild_continuity_state(merged),
            roadmap_validation_issues=[item.model_dump(mode="json") for item in merged_issues],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class RegenerateStoryArcUseCase(_BlueprintLayerBase):
    """只重生成阶段骨架，不直接覆盖章节。"""

    def execute(self, arc_number: int, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        story_arcs = self._context.planner.normalize_story_arcs_payload(
            state.get("story_arcs_draft") or state.get("story_arcs_confirmed") or []
        )
        if not story_arcs:
            raise ValueError("当前还没有阶段骨架，请先生成阶段骨架。")
        expanded_arc_numbers = _normalize_expanded_arc_numbers(state.get("expanded_arc_numbers"), story_arcs)
        expanded_later = [number for number in expanded_arc_numbers if number > arc_number]
        if expanded_later:
            raise ValueError(f"第 {arc_number} 幕之后已存在已完成阶段，请先处理后续阶段或重新生成整书阶段骨架。")
        current_roadmap = self._context.planner.normalize_roadmap_payload(
            state.get("roadmap_draft") or state.get("roadmap_confirmed") or []
        )
        target_arc = next((item for item in story_arcs if item.arc_number == arc_number), None)
        if target_arc is None:
            raise ValueError(f"第 {arc_number} 幕不存在。")
        regenerated_arcs = self._context.planner.regenerate_story_arc_skeleton(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=self._context.llm,
            story_arcs=story_arcs,
            arc_number=arc_number,
            feedback=feedback,
            chapter_count=self._length_to_chapter_count(intent),
            existing_roadmap=[item for item in current_roadmap if item.chapter_number < target_arc.start_chapter],
        )
        preserved_roadmap = [
            item
            for item in current_roadmap
            if item.chapter_number < target_arc.start_chapter or item.chapter_number > target_arc.end_chapter
        ]
        next_expanded_arc_numbers = [number for number in expanded_arc_numbers if number != arc_number]
        issues = (
            self._verify_roadmap(regenerated_arcs, preserved_roadmap)
            if preserved_roadmap
            else _build_unexpanded_arc_issues(
                self._context.planner,
                regenerated_arcs,
                next_expanded_arc_numbers,
                preserved_roadmap,
            )
        )
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="story_arcs_ready",
            current_step="roadmap",
            story_arcs_draft=[item.model_dump(mode="json") for item in regenerated_arcs],
            expanded_arc_numbers=next_expanded_arc_numbers,
            roadmap_draft=[item.model_dump(mode="json") for item in preserved_roadmap],
            blueprint_continuity_state=self._rebuild_continuity_state(preserved_roadmap),
            roadmap_validation_issues=[item.model_dump(mode="json") for item in issues],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class RegenerateArcChapterUseCase(_BlueprintLayerBase):
    """只重生成当前阶段最后一章。"""

    def execute(self, arc_number: int, chapter_number: int, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        story_arcs = self._context.planner.normalize_story_arcs_payload(
            state.get("story_arcs_draft") or state.get("story_arcs_confirmed") or []
        )
        if not story_arcs:
            raise ValueError("当前还没有阶段骨架，请先生成阶段骨架。")
        target_arc = next((item for item in story_arcs if item.arc_number == arc_number), None)
        if target_arc is None:
            raise ValueError(f"第 {arc_number} 幕不存在。")
        current_roadmap = self._context.planner.normalize_roadmap_payload(
            state.get("roadmap_draft") or state.get("roadmap_confirmed") or []
        )
        regenerated = self._context.planner.regenerate_last_arc_chapter(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=self._context.llm,
            story_arc=target_arc,
            chapter_number=chapter_number,
            feedback=feedback,
            existing_roadmap=current_roadmap,
        )
        merged = sorted(
            [item for item in current_roadmap if item.chapter_number != chapter_number] + [regenerated],
            key=lambda item: item.chapter_number,
        )
        expanded_arc_numbers = _normalize_expanded_arc_numbers(state.get("expanded_arc_numbers"), story_arcs)
        target_progress = self._context.planner.summarize_story_arc_progress(target_arc, merged)
        next_expanded_arc_numbers = (
            sorted(set([*expanded_arc_numbers, arc_number]))
            if bool(target_progress["completed"])
            else [number for number in expanded_arc_numbers if number != arc_number]
        )
        merged_issues = self._verify_roadmap(story_arcs, merged)
        status = "roadmap_ready" if len(next_expanded_arc_numbers) == len(story_arcs) and story_arcs else "story_arcs_ready"
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status=status,
            current_step="roadmap",
            story_arcs_draft=[item.model_dump(mode="json") for item in story_arcs],
            expanded_arc_numbers=next_expanded_arc_numbers,
            roadmap_draft=[item.model_dump(mode="json") for item in merged],
            blueprint_continuity_state=self._rebuild_continuity_state(merged),
            roadmap_validation_issues=[item.model_dump(mode="json") for item in merged_issues],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class PlanCreativeRepairsUseCase(_BlueprintLayerBase):
    """基于当前问题队列生成修复提案。

    第一阶段只接 roadmap，但这里已经按统一控制面的方式组织：
    - issue 先统一标准化；
    - 再按 deterministic / llm 分流成不同粒度的提案；
    - 提案只写入控制面状态，不直接修改路线真源。
    """

    def execute(self, issue_ids: list[str] | None = None) -> BookBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        story_arcs, roadmap, expanded_arc_numbers = self._load_story_arcs_and_roadmap(state)
        if not story_arcs and not roadmap:
            raise ValueError("当前还没有可修复的章节路线。")
        orchestrator = self._creative_orchestrator()
        proposals = orchestrator.plan_roadmap_repairs(
            book_id=self._context.book_id,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=self._verify_roadmap_with_gate_issues(story_arcs, roadmap, expanded_arc_numbers),
            stored_proposals=_load_creative_repair_proposals(state),
            issue_ids=list(issue_ids or []),
            intent=self._require_intent() if self._context.db.get_creation_intent(self._context.book_id) else None,
            variant=self._require_selected_variant() if state.get("selected_variant_id") else None,
            world=self._load_confirmed_world_optional(),
            characters=self._require_character_confirmed() if (state.get("character_confirmed") or state.get("character_draft")) else [],
            llm=self._context.llm,
        )
        _upsert_blueprint_business_state(
            self._context.db,
            self._context.book_id,
            payload=orchestrator.build_snapshot_payload(state),
            creative_repair_proposals=[item.model_dump(mode="json") for item in proposals],
            creative_repair_runs=[item.model_dump(mode="json") for item in _load_creative_repair_runs(state)],
            creative_control_snapshots=_load_creative_control_snapshots(state),
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GetCreativeRepairProposalUseCase(_BlueprintLayerBase):
    """按 proposal_id 读取单条修复提案。"""

    def execute(self, proposal_id: str) -> CreativeRepairProposal:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        proposal = next(
            (
                item
                for item in _load_creative_repair_proposals(state)
                if item.proposal_id == proposal_id
            ),
            None,
        )
        if proposal is None:
            raise ValueError("修复提案不存在。")
        return proposal


class ApplyCreativeRepairProposalUseCase(_BlueprintLayerBase):
    """执行一条已生成的修复提案，并自动复验。

    设计原则：
    - apply 前先存 before 快照；
    - apply 后重新构建 continuity / verifier；
    - 失败时保留提案和失败 run，方便作者回看原因。
    """

    def execute(self, proposal_id: str) -> BookBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        orchestrator = self._creative_orchestrator()
        proposals = _load_creative_repair_proposals(state)
        runs = _load_creative_repair_runs(state)
        snapshots = _load_creative_control_snapshots(state)
        proposal = next((item for item in proposals if item.proposal_id == proposal_id), None)
        if proposal is None:
            raise ValueError("修复提案不存在。")
        if proposal.status not in {"awaiting_approval", "failed"}:
            raise ValueError("当前提案不处于可执行状态。")
        if str(state.get("status") or "") == "locked" and proposal.strategy_type != "field_patch":
            raise ValueError("已锁定蓝图只允许字段级修复；大范围改写请改用未来章节重规划。")

        story_arcs, roadmap, expanded_arc_numbers = self._load_story_arcs_and_roadmap(state)
        before_payload = orchestrator.build_snapshot_payload(state)
        next_snapshots, before_snapshot_id = orchestrator.append_snapshot(
            book_id=self._context.book_id,
            snapshots=snapshots,
            payload=before_payload,
            kind="before_apply",
        )

        try:
            next_story_arcs, next_roadmap, next_expanded_arc_numbers = orchestrator.apply_proposal(
                proposal=proposal,
                story_arcs=story_arcs,
                roadmap=roadmap,
                expanded_arc_numbers=expanded_arc_numbers,
            )
            next_issues = self._verify_roadmap_with_gate_issues(
                next_story_arcs,
                next_roadmap,
                next_expanded_arc_numbers,
            )
            business_payload = {
                **before_payload,
                "story_arcs_draft": [item.model_dump(mode="json") for item in next_story_arcs],
                "expanded_arc_numbers": next_expanded_arc_numbers,
                "roadmap_draft": [item.model_dump(mode="json") for item in next_roadmap],
                "blueprint_continuity_state": self._rebuild_continuity_state(next_roadmap),
                "roadmap_validation_issues": [item.model_dump(mode="json") for item in next_issues],
                "status": (
                    "roadmap_ready"
                    if next_story_arcs and len(next_expanded_arc_numbers) == len(next_story_arcs)
                    else str(before_payload.get("status") or "story_arcs_ready")
                ),
                "current_step": "roadmap",
            }
            next_snapshots, after_snapshot_id = orchestrator.append_snapshot(
                book_id=self._context.book_id,
                snapshots=next_snapshots,
                payload=business_payload,
                kind="after_apply",
            )
            updated_proposals: list[CreativeRepairProposal] = []
            for item in proposals:
                if item.proposal_id == proposal_id:
                    updated_proposals.append(item.model_copy(update={"status": "applied"}))
                else:
                    updated_proposals.append(item)
            updated_runs = [
                *runs,
                orchestrator.build_success_run(
                    book_id=self._context.book_id,
                    proposal_id=proposal_id,
                    before_snapshot_ref=before_snapshot_id,
                    after_snapshot_ref=after_snapshot_id,
                    logs=[
                        f"已执行提案：{proposal.summary}",
                        "系统已自动重建连续性工作态并复验当前章节路线。",
                    ],
                ),
            ]
            _upsert_blueprint_business_state(
                self._context.db,
                self._context.book_id,
                payload=business_payload,
                creative_repair_proposals=[item.model_dump(mode="json") for item in updated_proposals],
                creative_repair_runs=[item.model_dump(mode="json") for item in updated_runs],
                creative_control_snapshots=next_snapshots,
            )
            return build_book_blueprint(self._context.db, self._context.book_id)
        except Exception as exc:  # noqa: BLE001
            failed_proposals = [
                item.model_copy(update={"status": "failed"}) if item.proposal_id == proposal_id else item
                for item in proposals
            ]
            failed_runs = [
                *runs,
                orchestrator.build_failed_run(
                    book_id=self._context.book_id,
                    proposal_id=proposal_id,
                    error_message=str(exc),
                ),
            ]
            _upsert_blueprint_business_state(
                self._context.db,
                self._context.book_id,
                payload=before_payload,
                creative_repair_proposals=[item.model_dump(mode="json") for item in failed_proposals],
                creative_repair_runs=[item.model_dump(mode="json") for item in failed_runs],
                creative_control_snapshots=next_snapshots,
            )
            raise


class RollbackCreativeRepairRunUseCase(_BlueprintLayerBase):
    """把一次已执行的修复回滚到 apply 前快照。"""

    def execute(self, run_id: str) -> BookBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        orchestrator = self._creative_orchestrator()
        proposals = _load_creative_repair_proposals(state)
        runs = _load_creative_repair_runs(state)
        snapshots = _load_creative_control_snapshots(state)
        target_run = next((item for item in runs if item.run_id == run_id), None)
        if target_run is None:
            raise ValueError("修复执行记录不存在。")
        if target_run.status != "succeeded" or not target_run.before_snapshot_ref:
            raise ValueError("当前执行记录不支持回滚。")
        restored_payload = orchestrator.rollback_from_snapshot(
            snapshots=snapshots,
            snapshot_id=target_run.before_snapshot_ref,
        )
        updated_proposals = [
            item.model_copy(update={"status": "rolled_back"}) if item.proposal_id == target_run.proposal_id else item
            for item in proposals
        ]
        rollback_run = CreativeRepairRun(
            run_id=f"{run_id}-rollback",
            book_id=self._context.book_id,
            proposal_id=target_run.proposal_id,
            execution_mode="apply",
            status="rolled_back",
            logs=["已根据执行前快照回滚修复结果。"],
            before_snapshot_ref=target_run.before_snapshot_ref,
            after_snapshot_ref=target_run.after_snapshot_ref,
            created_at=target_run.created_at,
        )
        _upsert_blueprint_business_state(
            self._context.db,
            self._context.book_id,
            payload=restored_payload,
            creative_repair_proposals=[item.model_dump(mode="json") for item in updated_proposals],
            creative_repair_runs=[item.model_dump(mode="json") for item in [*runs, rollback_run]],
            creative_control_snapshots=snapshots,
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class ReverifyCreativeIssuesUseCase(_BlueprintLayerBase):
    """重新扫描当前章节路线，刷新问题队列和复验结果。"""

    def execute(self) -> BookBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        story_arcs, roadmap, expanded_arc_numbers = self._load_story_arcs_and_roadmap(state)
        refreshed_issues = self._verify_roadmap_with_gate_issues(story_arcs, roadmap, expanded_arc_numbers)
        _upsert_blueprint_business_state(
            self._context.db,
            self._context.book_id,
            payload={
                **self._creative_orchestrator().build_snapshot_payload(state),
                "roadmap_validation_issues": [item.model_dump(mode="json") for item in refreshed_issues],
                "blueprint_continuity_state": self._rebuild_continuity_state(roadmap),
            },
            creative_repair_proposals=[item.model_dump(mode="json") for item in _load_creative_repair_proposals(state)],
            creative_repair_runs=[item.model_dump(mode="json") for item in _load_creative_repair_runs(state)],
            creative_control_snapshots=_load_creative_control_snapshots(state),
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class ConfirmBlueprintLayerUseCase(_BlueprintLayerBase):
    """确认某一层蓝图，并推进下一层。"""

    def execute(
        self,
        layer: BlueprintLayer,
        payload: WorldBlueprint | list[CharacterBlueprint] | list[ChapterRoadmapItem] | dict[str, Any] | None = None,
    ) -> BookBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        if layer == "world":
            if isinstance(payload, WorldBlueprint):
                world = payload
            else:
                world = self._context.planner.normalize_world_blueprint_payload(
                    payload if isinstance(payload, dict) else state.get("world_draft") or state.get("world_confirmed") or {}
                )
            self._sync_world_to_canon(world)
            self._context.db.upsert_book_blueprint_state(
                self._context.book_id,
                status="world_confirmed",
                current_step="characters",
                world_confirmed=world.model_dump(mode="json"),
                blueprint_continuity_state={},
            )
            return build_book_blueprint(self._context.db, self._context.book_id)

        if layer == "characters":
            if isinstance(payload, dict):
                raw_characters = payload.get("characters") or state.get("character_draft") or []
                raw_relationships = payload.get("relationship_graph") or state.get("relationship_graph_draft") or []
            else:
                raw_characters = payload if isinstance(payload, list) else state.get("character_draft") or []
                raw_relationships = state.get("relationship_graph_draft") or []
            characters = self._context.planner.normalize_character_blueprints_payload(raw_characters)
            relationship_graph = self._context.planner.normalize_relationship_blueprint_edges_payload(
                raw_relationships,
                characters,
            )
            self._sync_characters_to_canon(characters)
            self._sync_relationship_graph(relationship_graph)
            self._context.db.upsert_book_blueprint_state(
                self._context.book_id,
                status="characters_confirmed",
                current_step="roadmap",
                character_confirmed=[item.model_dump(mode="json") for item in characters],
                relationship_graph_confirmed=[item.model_dump(mode="json") for item in relationship_graph],
                blueprint_continuity_state={},
            )
            return build_book_blueprint(self._context.db, self._context.book_id)

        raw_roadmap = payload if isinstance(payload, list) else state.get("roadmap_draft") or []
        roadmap = self._context.planner.normalize_roadmap_payload(raw_roadmap)
        story_arcs = self._context.planner.normalize_story_arcs_payload(
            state.get("story_arcs_draft") or state.get("story_arcs_confirmed") or []
        )
        if not story_arcs:
            raise ValueError("请先生成阶段骨架。")
        expanded_arc_numbers = _normalize_expanded_arc_numbers(state.get("expanded_arc_numbers"), story_arcs)
        if len(expanded_arc_numbers) != len(story_arcs):
            missing_arcs = [str(item.arc_number) for item in story_arcs if item.arc_number not in expanded_arc_numbers]
            raise ValueError(f"仍有阶段未完成章节生成：第 {'、'.join(missing_arcs)} 幕。")
        roadmap_issues = self._verify_roadmap(story_arcs, roadmap)
        fatal_issues = [item.message for item in roadmap_issues if item.severity == "fatal"]
        if fatal_issues:
            raise ValueError(f"当前章节路线仍存在严重问题：{'；'.join(fatal_issues[:3])}")
        revision_id = self._create_revision(
            roadmap=roadmap,
            change_reason="初次锁定整书蓝图",
            change_summary="确认世界观、人物和章节路线，进入可写作状态。",
            affected_range=[1, roadmap[-1].chapter_number if roadmap else 1],
        )
        self._sync_planned_loops(roadmap)
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="locked",
            current_step="locked",
            active_revision_id=revision_id,
            story_arcs_confirmed=[item.model_dump(mode="json") for item in story_arcs],
            expanded_arc_numbers=expanded_arc_numbers,
            roadmap_confirmed=[item.model_dump(mode="json") for item in roadmap],
            blueprint_continuity_state=self._rebuild_continuity_state(roadmap),
            roadmap_validation_issues=[item.model_dump(mode="json") for item in roadmap_issues],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)

    def _create_revision(
        self,
        roadmap: list[ChapterRoadmapItem],
        change_reason: str,
        change_summary: str,
        affected_range: list[int],
    ) -> int:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        revisions = self._context.db.list_blueprint_revisions(self._context.book_id)
        next_revision = (max((int(item["revision_number"]) for item in revisions), default=0) + 1)
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        relationship_graph = self._context.planner.normalize_relationship_blueprint_edges_payload(
            list(state.get("relationship_graph_confirmed") or []),
            characters,
        )
        return self._context.db.create_blueprint_revision(
            self._context.book_id,
            revision_number=next_revision,
            selected_variant_id=state.get("selected_variant_id"),
            change_reason=change_reason,
            change_summary=change_summary,
            affected_range=affected_range,
            world_blueprint=world.model_dump(mode="json"),
            character_blueprints=[item.model_dump(mode="json") for item in characters],
            relationship_graph=[item.model_dump(mode="json") for item in relationship_graph],
            roadmap=[item.model_dump(mode="json") for item in roadmap],
            is_active=True,
        )


class ReplanBlueprintUseCase(_BlueprintLayerBase):
    """只对未来未发布章节做重规划，并生成新版本。"""

    def execute(self, payload: BlueprintReplanRequest) -> BookBlueprint:
        active_revision = self._context.db.get_active_blueprint_revision(self._context.book_id)
        if active_revision is None:
            raise ValueError("当前作品尚未锁定整书蓝图")
        latest_snapshot = self._context.db.get_latest_story_state_snapshot(self._context.book_id)
        last_published = int((latest_snapshot or {}).get("chapter_number") or 0)
        if payload.starting_chapter <= last_published:
            raise ValueError("只能重规划未来未发布章节")

        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        current_roadmap = self._context.planner.normalize_roadmap_payload(active_revision.get("roadmap") or [])
        preserved = [item for item in current_roadmap if item.chapter_number < payload.starting_chapter]
        future_count = max(len([item for item in current_roadmap if item.chapter_number >= payload.starting_chapter]), 1)
        replanned = self._context.planner.generate_roadmap(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=self._context.llm,
            feedback=payload.guidance,
            starting_chapter=payload.starting_chapter,
            chapter_count=future_count,
            existing_roadmap=preserved,
        )
        merged = [*preserved, *replanned]
        merged_arcs = self._context.planner.derive_story_arcs_from_roadmap(merged)
        merged_issues = self._verify_roadmap(merged_arcs, merged)
        revision_id = ConfirmBlueprintLayerUseCase(self._context)._create_revision(
            roadmap=merged,
            change_reason=payload.reason or "未来章节重规划",
            change_summary=payload.guidance or "根据作者要求调整未来章节走向。",
            affected_range=[payload.starting_chapter, merged[-1].chapter_number if merged else payload.starting_chapter],
        )
        self._sync_planned_loops(replanned)
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="locked",
            current_step="locked",
            active_revision_id=revision_id,
            story_arcs_confirmed=[item.model_dump(mode="json") for item in merged_arcs],
            roadmap_confirmed=[item.model_dump(mode="json") for item in merged],
            blueprint_continuity_state=self._rebuild_continuity_state(merged),
            roadmap_validation_issues=[item.model_dump(mode="json") for item in merged_issues],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class RelationshipConflictError(ValueError):
    """关系编辑命中已发布事实冲突时抛出结构化异常。"""

    def __init__(self, report: RelationshipConflictReport) -> None:
        super().__init__(report.conflict_summary)
        self.report = report


class GetRelationshipGraphUseCase(_BlueprintLayerBase):
    """读取当前作品的关系图谱工作态。"""

    def execute(self) -> dict[str, Any]:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        raw_characters = self._context.planner.normalize_character_blueprints_payload(
            state.get("character_confirmed") or state.get("character_draft") or []
        )
        raw_relationships = state.get("relationship_graph_confirmed") or state.get("relationship_graph_draft") or []
        nodes = [
            CharacterNode(
                character_id=self._character_id(item.name),
                name=item.name,
                role=item.role,
                public_persona=item.public_persona,
                core_motivation=item.core_motivation,
                fatal_flaw=item.fatal_flaw,
                non_negotiable_traits=item.non_negotiable_traits,
                arc_outline=item.arc_outline,
            )
            for item in raw_characters
        ]
        edges = self._context.planner.normalize_relationship_blueprint_edges_payload(
            raw_relationships,
            raw_characters,
        )
        pending = [
            RelationshipPendingItem.model_validate(item)
            for item in self._context.db.list_relationship_pending_items(self._context.book_id)
        ]
        return {
            "nodes": [item.model_dump(mode="json") for item in nodes],
            "edges": [item.model_dump(mode="json") for item in edges],
            "pending": [item.model_dump(mode="json") for item in pending],
        }


class ConfirmRelationshipGraphUseCase(_BlueprintLayerBase):
    """确认并同步当前关系图谱。"""

    def execute(self, edges: list[RelationshipBlueprintEdge]) -> BookBlueprint:
        self._sync_relationship_graph(edges)
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="characters_confirmed",
            current_step="roadmap",
            relationship_graph_confirmed=[item.model_dump(mode="json") for item in edges],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class UpsertRelationshipEdgeUseCase(_BlueprintLayerBase):
    """新增或编辑关系边；若命中已发布事实冲突则转入重规划流程。"""

    def _load_published_chapters(self) -> list[int]:
        snapshot = self._context.db.get_latest_story_state_snapshot(self._context.book_id) or {}
        raw = dict(snapshot.get("snapshot_json") or {})
        return [int(item) for item in list(raw.get("published_chapters") or [])]

    def _build_conflict_report(
        self,
        existing: dict[str, Any],
        edge: RelationshipBlueprintEdge,
    ) -> RelationshipConflictReport:
        latest_chapter = int(existing.get("latest_chapter") or 0)
        return RelationshipConflictReport(
            edge_id=edge.edge_id,
            source_chapter=latest_chapter or 1,
            source_scene_ref=str(existing.get("latest_scene_ref") or ""),
            conflict_summary="当前关系已在已发布章节中形成明确事实，不能直接改写。",
            immutable_fact=f"已发布关系：{existing.get('relation_type') or '未命名关系'}｜{existing.get('summary') or ''}",
            recommended_paths=["未来关系重规划", "关系反转提案", "表象关系与真相关系分层"],
        )

    def execute(self, edge: RelationshipBlueprintEdge) -> dict[str, Any]:
        existing = self._context.db.get_relationship_edge(self._context.book_id, edge.edge_id)
        published_chapters = self._load_published_chapters()
        if existing is not None and published_chapters:
            changed = any(
                [
                    str(existing.get("relation_type") or "") != edge.relation_type,
                    str(existing.get("polarity") or "") != edge.polarity,
                    str(existing.get("visibility") or "") != edge.visibility,
                    bool(existing.get("non_breakable_without_reveal")) != edge.non_breakable_without_reveal,
                ]
            )
            if changed:
                raise RelationshipConflictError(self._build_conflict_report(existing, edge))

        self._context.db.upsert_relationship_edge(self._context.book_id, edge.model_dump(mode="json"))
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        raw_relationships = list(state.get("relationship_graph_confirmed") or state.get("relationship_graph_draft") or [])
        merged: list[dict[str, Any]] = []
        replaced = False
        for item in raw_relationships:
            if str(item.get("edge_id") or "") == edge.edge_id:
                merged.append(edge.model_dump(mode="json"))
                replaced = True
            else:
                merged.append(item)
        if not replaced:
            merged.append(edge.model_dump(mode="json"))
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status=str(state.get("status") or "characters_ready"),
            current_step=str(state.get("current_step") or "characters"),
            relationship_graph_draft=merged,
            relationship_graph_confirmed=merged if state.get("relationship_graph_confirmed") else None,
        )
        return self.execute_graph_snapshot()

    def execute_graph_snapshot(self) -> dict[str, Any]:
        return GetRelationshipGraphUseCase(self._context).execute()


class ListRelationshipPendingUseCase(_BlueprintLayerBase):
    """读取待确认人物/关系列表。"""

    def execute(self) -> list[RelationshipPendingItem]:
        return [
            RelationshipPendingItem.model_validate(item)
            for item in self._context.db.list_relationship_pending_items(self._context.book_id)
        ]


class ConfirmRelationshipPendingUseCase(_BlueprintLayerBase):
    """确认自动接入的待确认项。"""

    def execute(self, item_id: int) -> dict[str, Any]:
        item = self._context.db.get_relationship_pending_item(item_id)
        if item is None or int(item.get("book_id") or 0) != self._context.book_id:
            raise ValueError("待确认项不存在")
        if str(item.get("status") or "") != "pending":
            raise ValueError("待确认项已处理")
        self._context.db.update_relationship_pending_item_status(item_id, "confirmed")
        if item.get("item_type") == "character" and item.get("character"):
            self._context.db.replace_character_nodes(
                self._context.book_id,
                [
                    *self._context.db.list_character_nodes(self._context.book_id),
                    dict(item["character"]),
                ],
            )
        if item.get("item_type") == "relationship" and item.get("relationship"):
            self._context.db.upsert_relationship_edge(self._context.book_id, dict(item["relationship"]))
        return GetRelationshipGraphUseCase(self._context).execute()


class RejectRelationshipPendingUseCase(_BlueprintLayerBase):
    """拒绝待确认项。"""

    def execute(self, item_id: int) -> dict[str, Any]:
        item = self._context.db.get_relationship_pending_item(item_id)
        if item is None or int(item.get("book_id") or 0) != self._context.book_id:
            raise ValueError("待确认项不存在")
        self._context.db.update_relationship_pending_item_status(item_id, "rejected")
        return GetRelationshipGraphUseCase(self._context).execute()


class CreateRelationshipReplanUseCase(_BlueprintLayerBase):
    """为冲突关系创建未来重规划/反转提案。"""

    def execute(self, edge_id: str, reason: str, desired_change: str) -> dict[str, Any]:
        edge = self._context.db.get_relationship_edge(self._context.book_id, edge_id)
        if edge is None:
            raise ValueError("关系边不存在")
        latest_chapter = int(edge.get("latest_chapter") or 1)
        report = RelationshipConflictReport(
            edge_id=edge_id,
            source_chapter=latest_chapter,
            source_scene_ref=str(edge.get("latest_scene_ref") or ""),
            conflict_summary="当前关系已被已发布章节确认，不能直接改写，只能生成未来重规划提案。",
            immutable_fact=f"{edge.get('relation_type') or ''}｜{edge.get('summary') or ''}",
            recommended_paths=["未来关系重规划", "关系反转提案", "表象关系与真相关系分层"],
        )
        request_id = self._context.db.create_relationship_replan_request(
            self._context.book_id,
            {
                "edge_id": edge_id,
                "request_reason": reason,
                "desired_change": desired_change,
                "conflict_report": report.model_dump(mode="json"),
                "status": "pending",
            },
        )
        future_edge = RelationshipBlueprintEdge(
            edge_id=edge_id,
            source_character_id=str(edge.get("source_character_id") or ""),
            target_character_id=str(edge.get("target_character_id") or ""),
            relation_type=desired_change or str(edge.get("relation_type") or ""),
            polarity="复杂",
            intensity=int(edge.get("intensity") or 3),
            visibility="公开",
            stability="正在转变",
            summary=f"通过未来章节重规划，把关系逐步推向：{desired_change or edge.get('relation_type')}",
            hidden_truth=str(edge.get("hidden_truth") or ""),
            non_breakable_without_reveal=True,
        )
        proposal = RelationshipRetconProposal(
            proposal_id=f"replan-{request_id}",
            edge_id=edge_id,
            request_reason=reason,
            change_summary=desired_change,
            strategy="未来关系重规划",
            affected_future_chapters=[latest_chapter + 1, latest_chapter + 2],
            future_edge=future_edge,
            required_reveals=[
                "先在未来章节建立关系异动迹象",
                "通过关键揭示解释旧关系为何发生反转",
            ],
        )
        self._context.db.add_relationship_replan_proposal(
            request_id,
            proposal.proposal_id,
            proposal.model_dump(mode="json"),
        )
        request = self._context.db.get_relationship_replan_request(request_id) or {}
        return {
            "request_id": request_id,
            "request": request,
            "proposal": proposal.model_dump(mode="json"),
        }


class ConfirmRelationshipReplanUseCase(_BlueprintLayerBase):
    """确认关系重规划提案，并更新未来执行态关系。"""

    def execute(self, request_id: int, proposal_id: str) -> dict[str, Any]:
        request = self._context.db.get_relationship_replan_request(request_id)
        if request is None or int(request.get("book_id") or 0) != self._context.book_id:
            raise ValueError("关系重规划请求不存在")
        proposal_row = self._context.db.get_relationship_replan_proposal(request_id, proposal_id)
        if proposal_row is None:
            raise ValueError("关系重规划提案不存在")
        proposal = RelationshipRetconProposal.model_validate(proposal_row.get("proposal") or {})
        edge_payload = proposal.future_edge.model_dump(mode="json")
        edge_payload["status"] = "confirmed"
        self._context.db.upsert_relationship_edge(self._context.book_id, edge_payload)
        self._context.db.add_relationship_event(
            self._context.book_id,
            {
                "edge_id": proposal.edge_id,
                "event_id": proposal.proposal_id,
                "event_type": "reversed" if proposal.strategy == "关系反转提案" else "progressed",
                "chapter_number": min(proposal.affected_future_chapters) if proposal.affected_future_chapters else None,
                "scene_ref": "",
                "summary": proposal.change_summary,
                "revealed_fact": "、".join(proposal.required_reveals),
            },
        )
        self._context.db.update_relationship_replan_status(request_id, "confirmed")
        return {
            "request": self._context.db.get_relationship_replan_request(request_id),
            "graph": GetRelationshipGraphUseCase(self._context).execute(),
        }
