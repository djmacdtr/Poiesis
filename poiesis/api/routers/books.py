"""书籍路由：创建、查询、更新按书配置。"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from poiesis.api.deps import get_db, require_admin
from poiesis.api.schemas.blueprint import (
    AcceptRegeneratedConceptVariantRequest,
    BlueprintLayerGenerateRequest,
    BlueprintReplanPayload,
    BlueprintRevisionListResponse,
    BookBlueprintResponse,
    ConfirmCharacterBlueprintRequest,
    ConfirmRelationshipGraphRequest,
    ConfirmRoadmapRequest,
    ConfirmWorldBlueprintRequest,
    CreationIntentRequest,
    RegenerateConceptVariantResponse,
    RegenerateRoadmapStageRequest,
    RelationshipGraphResponse,
    RelationshipPendingListResponse,
    RelationshipReplanConfirmRequest,
    RelationshipReplanCreateRequest,
    RelationshipReplanResponse,
    UpsertRelationshipEdgeRequest,
)
from poiesis.api.schemas.book import BookCreateRequest, BookItem, BookUpdateRequest
from poiesis.api.services import blueprint_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/books", tags=["书籍"])


def _config_path() -> str:
    return os.environ.get("POIESIS_CONFIG", "config.yaml")


@router.get("", response_model=list[BookItem])
def list_books(db: Database = Depends(get_db)) -> list[BookItem]:
    """返回所有书籍（默认书在前）。"""
    rows = db.list_books()
    return [BookItem(**row) for row in rows]


@router.post("", response_model=BookItem)
def create_book(
    body: BookCreateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookItem:
    """创建书籍并返回详情。"""
    try:
        book_id = db.create_book(
            name=body.name.strip(),
            language=body.language.strip(),
            style_preset=body.style_preset.strip(),
            style_prompt=body.style_prompt,
            naming_policy=body.naming_policy.strip(),
            is_default=body.is_default,
        )
    except sqlite3.IntegrityError as exc:
        if "books.name" in str(exc):
            raise HTTPException(status_code=409, detail="书名已存在，请更换后重试") from exc
        raise HTTPException(status_code=422, detail=f"创建书籍失败：{exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"创建书籍失败：{exc}") from exc

    row = db.get_book(book_id)
    if row is None:
        raise HTTPException(status_code=500, detail="书籍创建后读取失败")
    return BookItem(**row)


@router.put("/{book_id}", response_model=BookItem)
def update_book(
    book_id: int,
    body: BookUpdateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookItem:
    """更新书籍配置。"""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail=f"书籍 id={book_id} 不存在")

    try:
        db.update_book(
            book_id=book_id,
            name=body.name.strip(),
            language=body.language.strip(),
            style_preset=body.style_preset.strip(),
            style_prompt=body.style_prompt,
            naming_policy=body.naming_policy.strip(),
            is_default=body.is_default,
        )
    except sqlite3.IntegrityError as exc:
        if "books.name" in str(exc):
            raise HTTPException(status_code=409, detail="书名已存在，请更换后重试") from exc
        raise HTTPException(status_code=422, detail=f"更新书籍失败：{exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"更新书籍失败：{exc}") from exc

    row = db.get_book(book_id)
    if row is None:
        raise HTTPException(status_code=500, detail="书籍更新后读取失败")
    return BookItem(**row)


@router.get("/{book_id}/blueprint", response_model=BookBlueprintResponse)
def get_book_blueprint(book_id: int, db: Database = Depends(get_db)) -> BookBlueprintResponse:
    """读取当前作品的蓝图工作态与版本历史。"""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail="书籍不存在")
    return BookBlueprintResponse(**blueprint_service.get_book_blueprint(db, book_id).model_dump(mode="json"))


@router.post("/{book_id}/creation-intent", response_model=BookBlueprintResponse)
def save_creation_intent(
    book_id: int,
    body: CreationIntentRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """保存作者的高层创作意图。"""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail="书籍不存在")
    payload = blueprint_service.save_creation_intent(db, _config_path(), book_id, body.model_dump(mode="json"))
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/concept-variants:generate", response_model=BookBlueprintResponse)
def generate_concept_variants(
    book_id: int,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """生成 3 版候选方向。"""
    try:
        payload = blueprint_service.generate_concept_variants(db, _config_path(), book_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/concept-variants/{variant_id}/select", response_model=BookBlueprintResponse)
def select_concept_variant(
    book_id: int,
    variant_id: int,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """选择候选方向。"""
    try:
        payload = blueprint_service.select_concept_variant(db, _config_path(), book_id, variant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/concept-variants/{variant_id}:regenerate", response_model=RegenerateConceptVariantResponse)
def regenerate_concept_variant(
    book_id: int,
    variant_id: int,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> RegenerateConceptVariantResponse:
    """只重生成单条候选方向。"""
    try:
        payload = blueprint_service.regenerate_concept_variant(db, _config_path(), book_id, variant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegenerateConceptVariantResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/concept-variants/{variant_id}:accept-regenerated", response_model=BookBlueprintResponse)
def accept_regenerated_concept_variant(
    book_id: int,
    variant_id: int,
    body: AcceptRegeneratedConceptVariantRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """人工接受单版重生成提案，并覆盖原候选。"""
    try:
        payload = blueprint_service.accept_regenerated_concept_variant(
            db,
            _config_path(),
            book_id,
            variant_id,
            body.proposal.model_dump(mode="json"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/world:generate", response_model=BookBlueprintResponse)
def generate_world_blueprint(
    book_id: int,
    body: BlueprintLayerGenerateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """生成世界观草稿。"""
    try:
        payload = blueprint_service.generate_world_blueprint(db, _config_path(), book_id, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/characters:generate", response_model=BookBlueprintResponse)
def generate_character_blueprint(
    book_id: int,
    body: BlueprintLayerGenerateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """生成人物蓝图草稿。"""
    try:
        payload = blueprint_service.generate_character_blueprint(db, _config_path(), book_id, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/roadmap:generate", response_model=BookBlueprintResponse)
def generate_roadmap(
    book_id: int,
    body: BlueprintLayerGenerateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """生成章节路线草稿。"""
    try:
        payload = blueprint_service.generate_roadmap(db, _config_path(), book_id, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/story-arcs:generate", response_model=BookBlueprintResponse)
def generate_story_arcs(
    book_id: int,
    body: BlueprintLayerGenerateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """首次只生成整书阶段骨架。"""
    try:
        payload = blueprint_service.generate_story_arcs(db, _config_path(), book_id, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/story-arcs/{arc_number}:expand", response_model=BookBlueprintResponse)
def expand_story_arc(
    book_id: int,
    arc_number: int,
    body: RegenerateRoadmapStageRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """展开某一幕的章节。"""
    try:
        payload = blueprint_service.expand_story_arc(db, _config_path(), book_id, arc_number, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/story-arcs/{arc_number}:regenerate", response_model=BookBlueprintResponse)
def regenerate_story_arc(
    book_id: int,
    arc_number: int,
    body: RegenerateRoadmapStageRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """只重生成某一幕的阶段骨架。"""
    try:
        payload = blueprint_service.regenerate_story_arc(db, _config_path(), book_id, arc_number, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/roadmap/stages/{arc_number}:regenerate", response_model=BookBlueprintResponse)
def regenerate_roadmap_stage(
    book_id: int,
    arc_number: int,
    body: RegenerateRoadmapStageRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """只重生成某个阶段，作为路线工作台的主修复入口。"""
    try:
        payload = blueprint_service.regenerate_roadmap_stage(db, _config_path(), book_id, arc_number, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/world:confirm", response_model=BookBlueprintResponse)
def confirm_world_blueprint(
    book_id: int,
    body: ConfirmWorldBlueprintRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """确认世界观层。"""
    try:
        payload = blueprint_service.confirm_blueprint_layer(db, _config_path(), book_id, "world", body.draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/characters:confirm", response_model=BookBlueprintResponse)
def confirm_character_blueprint(
    book_id: int,
    body: ConfirmCharacterBlueprintRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """确认人物层。"""
    try:
        payload = blueprint_service.confirm_blueprint_layer(
            db,
            _config_path(),
            book_id,
            "characters",
            {
                "characters": body.characters,
                "relationship_graph": body.relationship_graph,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/roadmap:confirm", response_model=BookBlueprintResponse)
def confirm_roadmap(
    book_id: int,
    body: ConfirmRoadmapRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """确认章节路线层并锁定整书蓝图。"""
    try:
        payload = blueprint_service.confirm_blueprint_layer(db, _config_path(), book_id, "roadmap", body.draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/blueprint/replan", response_model=BookBlueprintResponse)
def replan_blueprint(
    book_id: int,
    body: BlueprintReplanPayload,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """对未来未发布章节做重规划。"""
    try:
        payload = blueprint_service.replan_blueprint(db, _config_path(), book_id, body.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.get("/{book_id}/blueprint/revisions", response_model=BlueprintRevisionListResponse)
def list_blueprint_revisions(book_id: int, db: Database = Depends(get_db)) -> BlueprintRevisionListResponse:
    """读取蓝图版本历史。"""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail="书籍不存在")
    payload = blueprint_service.get_book_blueprint(db, book_id)
    return BlueprintRevisionListResponse(
        items=[item.model_dump(mode="json") for item in payload.revisions]
    )


@router.get("/{book_id}/relationship-graph", response_model=RelationshipGraphResponse)
def get_relationship_graph(book_id: int, db: Database = Depends(get_db)) -> RelationshipGraphResponse:
    """读取人物关系图谱工作态。"""
    try:
        payload = blueprint_service.get_relationship_graph(db, _config_path(), book_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationshipGraphResponse.model_validate(payload)


@router.post("/{book_id}/relationship-graph/confirm", response_model=BookBlueprintResponse)
def confirm_relationship_graph(
    book_id: int,
    body: ConfirmRelationshipGraphRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> BookBlueprintResponse:
    """确认当前关系图谱。"""
    try:
        payload = blueprint_service.confirm_relationship_graph(db, _config_path(), book_id, body.edges)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BookBlueprintResponse(**payload.model_dump(mode="json"))


@router.post("/{book_id}/relationship-edges", response_model=RelationshipGraphResponse)
def upsert_relationship_edge(
    book_id: int,
    body: UpsertRelationshipEdgeRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> RelationshipGraphResponse:
    """新增或编辑关系边。"""
    try:
        payload = blueprint_service.upsert_relationship_edge(db, _config_path(), book_id, body.edge)
    except blueprint_service.RelationshipConflictHttpError as exc:
        raise HTTPException(status_code=409, detail=exc.report.model_dump(mode="json")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationshipGraphResponse.model_validate(payload)


@router.put("/{book_id}/relationship-edges/{edge_id}", response_model=RelationshipGraphResponse)
def update_relationship_edge(
    book_id: int,
    edge_id: str,
    body: UpsertRelationshipEdgeRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> RelationshipGraphResponse:
    """更新关系边，edge_id 以路径参数为准。"""
    edge = body.edge.model_copy(update={"edge_id": edge_id})
    try:
        payload = blueprint_service.upsert_relationship_edge(db, _config_path(), book_id, edge)
    except blueprint_service.RelationshipConflictHttpError as exc:
        raise HTTPException(status_code=409, detail=exc.report.model_dump(mode="json")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationshipGraphResponse.model_validate(payload)


@router.get("/{book_id}/relationship-pending", response_model=RelationshipPendingListResponse)
def list_relationship_pending(book_id: int, db: Database = Depends(get_db)) -> RelationshipPendingListResponse:
    """读取待确认人物/关系。"""
    items = blueprint_service.list_relationship_pending(db, _config_path(), book_id)
    return RelationshipPendingListResponse.model_validate(
        {"items": [item.model_dump(mode="json") for item in items]}
    )


@router.post("/{book_id}/relationship-pending/{item_id}/confirm", response_model=RelationshipGraphResponse)
def confirm_relationship_pending(
    book_id: int,
    item_id: int,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> RelationshipGraphResponse:
    """确认待确认项。"""
    try:
        payload = blueprint_service.confirm_relationship_pending(db, _config_path(), book_id, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationshipGraphResponse.model_validate(payload)


@router.post("/{book_id}/relationship-pending/{item_id}/reject", response_model=RelationshipGraphResponse)
def reject_relationship_pending(
    book_id: int,
    item_id: int,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> RelationshipGraphResponse:
    """拒绝待确认项。"""
    try:
        payload = blueprint_service.reject_relationship_pending(db, _config_path(), book_id, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationshipGraphResponse.model_validate(payload)


@router.post("/{book_id}/relationship-replan", response_model=RelationshipReplanResponse)
def create_relationship_replan(
    book_id: int,
    body: RelationshipReplanCreateRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> RelationshipReplanResponse:
    """创建关系重规划/反转提案。"""
    try:
        payload = blueprint_service.create_relationship_replan(
            db,
            _config_path(),
            book_id,
            body.edge_id,
            body.reason,
            body.desired_change,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationshipReplanResponse.model_validate(payload)


@router.get("/{book_id}/relationship-replan/{request_id}", response_model=RelationshipReplanResponse)
def get_relationship_replan(
    book_id: int,
    request_id: int,
    db: Database = Depends(get_db),
) -> RelationshipReplanResponse:
    """读取关系重规划提案。"""
    try:
        payload = blueprint_service.get_relationship_replan(db, _config_path(), book_id, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RelationshipReplanResponse.model_validate(payload)


@router.post("/{book_id}/relationship-replan/{request_id}/confirm", response_model=RelationshipGraphResponse)
def confirm_relationship_replan(
    book_id: int,
    request_id: int,
    body: RelationshipReplanConfirmRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> RelationshipGraphResponse:
    """确认关系重规划提案。"""
    try:
        payload = blueprint_service.confirm_relationship_replan(
            db,
            _config_path(),
            book_id,
            request_id,
            body.proposal_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    graph = payload.get("graph") if isinstance(payload, dict) else None
    if not isinstance(graph, dict):
        raise HTTPException(status_code=500, detail="关系重规划结果缺少图谱快照")
    return RelationshipGraphResponse.model_validate(graph)
