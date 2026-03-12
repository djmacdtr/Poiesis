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
    CreationIntent,
)
from poiesis.application.blueprint_use_cases import (
    BlueprintContext,
    ConfirmBlueprintLayerUseCase,
    GenerateCharacterBlueprintUseCase,
    GenerateConceptVariantsUseCase,
    GenerateRoadmapUseCase,
    GenerateWorldBlueprintUseCase,
    RegenerateConceptVariantUseCase,
    ReplanBlueprintUseCase,
    SaveCreationIntentUseCase,
    SelectConceptVariantUseCase,
    build_book_blueprint,
)
from poiesis.config import load_config
from poiesis.db.database import Database
from poiesis.pipeline.planning.roadmap_planner import RoadmapPlanner


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


def regenerate_concept_variant(db: Database, config_path: str, book_id: int, variant_id: int) -> BookBlueprint:
    """只重生成单条候选方向。"""
    context = _build_context(config_path, db, book_id)
    return RegenerateConceptVariantUseCase(context).execute(variant_id)


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
