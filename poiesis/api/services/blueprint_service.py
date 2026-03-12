"""创作蓝图服务：承接 books 页面上的蓝图工作台 API。"""

from __future__ import annotations

from typing import Any, cast

from poiesis.api.services.scene_run_service import (
    _apply_model_overrides,
    _build_llm,
    _load_key_from_db,
)
from poiesis.application.blueprint_contracts import (
    BlueprintLayer,
    BlueprintReplanRequest,
    BookBlueprint,
    ConceptVariant,
    ConceptVariantRegenerationResult,
    CreationIntent,
    RelationshipBlueprintEdge,
    RelationshipConflictReport,
    RelationshipPendingItem,
    RelationshipRetconProposal,
)
from poiesis.application.blueprint_use_cases import (
    AcceptRegeneratedConceptVariantUseCase,
    BlueprintContext,
    ConfirmBlueprintLayerUseCase,
    ConfirmRelationshipGraphUseCase,
    ConfirmRelationshipPendingUseCase,
    ConfirmRelationshipReplanUseCase,
    CreateRelationshipReplanUseCase,
    GenerateCharacterBlueprintUseCase,
    GenerateConceptVariantsUseCase,
    GenerateRoadmapUseCase,
    GenerateWorldBlueprintUseCase,
    GetRelationshipGraphUseCase,
    ListRelationshipPendingUseCase,
    RegenerateConceptVariantUseCase,
    RegenerateRoadmapStageUseCase,
    RejectRelationshipPendingUseCase,
    RelationshipConflictError,
    ReplanBlueprintUseCase,
    SaveCreationIntentUseCase,
    SelectConceptVariantUseCase,
    UpsertRelationshipEdgeUseCase,
    build_book_blueprint,
)
from poiesis.config import load_config
from poiesis.db.database import Database
from poiesis.pipeline.planning.roadmap_planner import RoadmapPlanner


class RelationshipConflictHttpError(ValueError):
    """把关系冲突报告包装到 API 层。"""

    def __init__(self, report: RelationshipConflictReport) -> None:
        super().__init__(report.conflict_summary)
        self.report = report


def _build_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:
    """构建蓝图用例依赖。"""
    cfg = load_config(config_path)
    _apply_model_overrides(cfg, db)
    openai_key = _load_key_from_db(db, "OPENAI_API_KEY")
    anthropic_key = _load_key_from_db(db, "ANTHROPIC_API_KEY")
    siliconflow_key = _load_key_from_db(db, "SILICONFLOW_API_KEY")
    planner_llm = _build_llm(cfg.planner_llm, openai_key, anthropic_key, siliconflow_key)
    return BlueprintContext(
        db=db,
        llm=planner_llm,
        book_id=book_id,
        planner=RoadmapPlanner(),
    )


def get_book_blueprint(db: Database, book_id: int) -> BookBlueprint:
    """读取当前作品的整书蓝图状态。"""
    return build_book_blueprint(db, book_id)


def save_creation_intent(db: Database, config_path: str, book_id: int, payload: dict[str, Any]) -> BookBlueprint:
    """保存作者创作意图。"""
    context = _build_context(config_path, db, book_id)
    return SaveCreationIntentUseCase(context).execute(CreationIntent.model_validate(payload))


def generate_concept_variants(db: Database, config_path: str, book_id: int) -> BookBlueprint:
    """生成 3 版候选方向。"""
    context = _build_context(config_path, db, book_id)
    return GenerateConceptVariantsUseCase(context).execute()


def select_concept_variant(db: Database, config_path: str, book_id: int, variant_id: int) -> BookBlueprint:
    """选择候选方向。"""
    context = _build_context(config_path, db, book_id)
    return SelectConceptVariantUseCase(context).execute(variant_id)


def regenerate_concept_variant(
    db: Database,
    config_path: str,
    book_id: int,
    variant_id: int,
) -> ConceptVariantRegenerationResult:
    """只重生成单条候选方向。"""
    context = _build_context(config_path, db, book_id)
    return RegenerateConceptVariantUseCase(context).execute(variant_id)


def accept_regenerated_concept_variant(
    db: Database,
    config_path: str,
    book_id: int,
    variant_id: int,
    payload: dict[str, Any],
) -> BookBlueprint:
    """接受单版重生成提案，并覆盖原候选。"""
    context = _build_context(config_path, db, book_id)
    return AcceptRegeneratedConceptVariantUseCase(context).execute(variant_id, ConceptVariant.model_validate(payload))


def generate_world_blueprint(
    db: Database,
    config_path: str,
    book_id: int,
    feedback: str = "",
) -> BookBlueprint:
    """生成世界观草稿。"""
    context = _build_context(config_path, db, book_id)
    return GenerateWorldBlueprintUseCase(context).execute(feedback)


def generate_character_blueprint(
    db: Database,
    config_path: str,
    book_id: int,
    feedback: str = "",
) -> BookBlueprint:
    """生成人物蓝图草稿。"""
    context = _build_context(config_path, db, book_id)
    return GenerateCharacterBlueprintUseCase(context).execute(feedback)


def generate_roadmap(
    db: Database,
    config_path: str,
    book_id: int,
    feedback: str = "",
) -> BookBlueprint:
    """生成章节路线草稿。"""
    context = _build_context(config_path, db, book_id)
    return GenerateRoadmapUseCase(context).execute(feedback)


def regenerate_roadmap_stage(
    db: Database,
    config_path: str,
    book_id: int,
    arc_number: int,
    feedback: str = "",
) -> BookBlueprint:
    """只重生成某个阶段覆盖的章节范围。"""
    context = _build_context(config_path, db, book_id)
    return RegenerateRoadmapStageUseCase(context).execute(arc_number, feedback)


def confirm_blueprint_layer(
    db: Database,
    config_path: str,
    book_id: int,
    layer: str,
    payload: Any = None,
) -> BookBlueprint:
    """确认世界/人物/章节层。"""
    context = _build_context(config_path, db, book_id)
    return ConfirmBlueprintLayerUseCase(context).execute(cast(BlueprintLayer, layer), payload)


def replan_blueprint(
    db: Database,
    config_path: str,
    book_id: int,
    payload: dict[str, Any],
) -> BookBlueprint:
    """只针对未来章节生成新的蓝图版本。"""
    context = _build_context(config_path, db, book_id)
    return ReplanBlueprintUseCase(context).execute(BlueprintReplanRequest.model_validate(payload))


def get_relationship_graph(
    db: Database,
    config_path: str,
    book_id: int,
) -> dict[str, list[dict[str, object]]]:
    """读取关系图谱工作态。"""
    context = _build_context(config_path, db, book_id)
    return cast(dict[str, list[dict[str, object]]], GetRelationshipGraphUseCase(context).execute())


def confirm_relationship_graph(
    db: Database,
    config_path: str,
    book_id: int,
    edges: list[RelationshipBlueprintEdge],
) -> BookBlueprint:
    """确认关系图谱。"""
    context = _build_context(config_path, db, book_id)
    return ConfirmRelationshipGraphUseCase(context).execute(edges)


def upsert_relationship_edge(
    db: Database,
    config_path: str,
    book_id: int,
    edge: RelationshipBlueprintEdge,
) -> dict[str, list[dict[str, object]]]:
    """新增或更新关系边。"""
    context = _build_context(config_path, db, book_id)
    try:
        return cast(dict[str, list[dict[str, object]]], UpsertRelationshipEdgeUseCase(context).execute(edge))
    except RelationshipConflictError as exc:
        raise RelationshipConflictHttpError(exc.report) from exc


def list_relationship_pending(
    db: Database,
    config_path: str,
    book_id: int,
) -> list[RelationshipPendingItem]:
    """读取待确认人物/关系队列。"""
    context = _build_context(config_path, db, book_id)
    return ListRelationshipPendingUseCase(context).execute()


def confirm_relationship_pending(
    db: Database,
    config_path: str,
    book_id: int,
    item_id: int,
) -> dict[str, list[dict[str, object]]]:
    """确认待确认项。"""
    context = _build_context(config_path, db, book_id)
    return cast(dict[str, list[dict[str, object]]], ConfirmRelationshipPendingUseCase(context).execute(item_id))


def reject_relationship_pending(
    db: Database,
    config_path: str,
    book_id: int,
    item_id: int,
) -> dict[str, list[dict[str, object]]]:
    """拒绝待确认项。"""
    context = _build_context(config_path, db, book_id)
    return cast(dict[str, list[dict[str, object]]], RejectRelationshipPendingUseCase(context).execute(item_id))


def create_relationship_replan(
    db: Database,
    config_path: str,
    book_id: int,
    edge_id: str,
    reason: str,
    desired_change: str,
) -> dict[str, object]:
    """创建关系重规划请求。"""
    context = _build_context(config_path, db, book_id)
    return cast(dict[str, object], CreateRelationshipReplanUseCase(context).execute(edge_id, reason, desired_change))


def get_relationship_replan(
    db: Database,
    config_path: str,
    book_id: int,
    request_id: int,
) -> dict[str, object]:
    """读取关系重规划工作态。"""
    _ = config_path
    request = db.get_relationship_replan_request(request_id)
    if request is None or int(request.get("book_id") or 0) != book_id:
        raise ValueError("关系重规划请求不存在")
    proposal = db.get_relationship_replan_proposal(request_id, f"replan-{request_id}")
    if proposal is None:
        raise ValueError("关系重规划提案不存在")
    return {
        "request_id": request_id,
        "request": request,
        "proposal": RelationshipRetconProposal.model_validate(proposal.get("proposal") or {}),
    }


def confirm_relationship_replan(
    db: Database,
    config_path: str,
    book_id: int,
    request_id: int,
    proposal_id: str,
) -> dict[str, object]:
    """确认关系重规划提案。"""
    context = _build_context(config_path, db, book_id)
    return cast(dict[str, object], ConfirmRelationshipReplanUseCase(context).execute(request_id, proposal_id))
