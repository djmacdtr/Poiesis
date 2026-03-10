"""创作蓝图用例：负责整书蓝图的生成、确认与重规划。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from poiesis.application.blueprint_contracts import (
    BlueprintLayer,
    BlueprintReplanRequest,
    BlueprintRevision,
    BookBlueprint,
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    CreationIntent,
    WorldBlueprint,
)
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


def build_book_blueprint(db: Database, book_id: int) -> BookBlueprint:
    """把当前蓝图工作态和版本快照组装成统一响应。"""
    state = db.get_book_blueprint_state(book_id) or {}
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
        world_draft=WorldBlueprint.model_validate(state["world_draft"]) if state.get("world_draft") else None,
        world_confirmed=(
            WorldBlueprint.model_validate(state["world_confirmed"]) if state.get("world_confirmed") else None
        ),
        character_draft=[
            CharacterBlueprint.model_validate(item) for item in list(state.get("character_draft") or [])
        ],
        character_confirmed=[
            CharacterBlueprint.model_validate(item) for item in list(state.get("character_confirmed") or [])
        ],
        roadmap_draft=[
            ChapterRoadmapItem.model_validate(item) for item in list(state.get("roadmap_draft") or [])
        ],
        roadmap_confirmed=[
            ChapterRoadmapItem.model_validate(item) for item in list(state.get("roadmap_confirmed") or [])
        ],
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
        )
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
        return WorldBlueprint.model_validate(payload)

    def _require_character_confirmed(self) -> list[CharacterBlueprint]:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        payload = state.get("character_confirmed") or state.get("character_draft") or []
        if not payload:
            raise ValueError("请先生成并确认人物蓝图")
        return [CharacterBlueprint.model_validate(item) for item in payload]

    def _length_to_chapter_count(self, intent: CreationIntent) -> int:
        raw = intent.length_preference.strip()
        if raw.isdigit():
            return max(6, min(int(raw), 60))
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
                rule_key=str(rule.get("key") or ""),
                description=str(rule.get("description") or ""),
                is_immutable=bool(rule.get("is_immutable", True)),
                category=str(rule.get("category") or "world"),
            )
        if world.setting_summary:
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key="world_setting",
                description=world.setting_summary,
                is_immutable=True,
                category="setting",
            )
        if world.power_system:
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key="power_system",
                description=world.power_system,
                is_immutable=True,
                category="power",
            )
        for index, faction in enumerate(world.factions, start=1):
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key=f"faction_{index}",
                description=faction,
                is_immutable=False,
                category="faction",
            )
        for index, taboo in enumerate(world.taboo_rules, start=1):
            self._context.db.upsert_world_rule(
                book_id=self._context.book_id,
                rule_key=f"taboo_rule_{index}",
                description=taboo,
                is_immutable=True,
                category="taboo",
            )

    def _sync_characters_to_canon(self, characters: list[CharacterBlueprint]) -> None:
        """人物蓝图确认后，同步到现有角色 canon。"""
        self._context.db.delete_characters(self._context.book_id)
        for item in characters:
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

    def _sync_planned_loops(self, roadmap: list[ChapterRoadmapItem]) -> None:
        """章节路线确认后，把计划中的关键线索种到 loop 状态里。"""
        for chapter in roadmap:
            for index, raw_loop in enumerate(chapter.planned_loops, start=1):
                loop_id = str(raw_loop.get("loop_id") or f"chapter-{chapter.chapter_number}-loop-{index}")
                title = str(raw_loop.get("title") or raw_loop.get("summary") or loop_id)
                due_start = raw_loop.get("due_start_chapter")
                due_end = raw_loop.get("due_end_chapter")
                raw_priority = raw_loop.get("priority")
                raw_related_characters = raw_loop.get("related_characters")
                raw_resolution_requirements = raw_loop.get("resolution_requirements")
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
                        "status": str(raw_loop.get("status") or "open"),
                        "introduced_in_scene": "",
                        "due_start_chapter": due_start,
                        "due_end_chapter": due_end,
                        "due_window": due_window,
                        "priority": raw_priority if isinstance(raw_priority, int) else 1,
                        "related_characters": (
                            list(raw_related_characters) if isinstance(raw_related_characters, list) else []
                        ),
                        "resolution_requirements": (
                            list(raw_resolution_requirements)
                            if isinstance(raw_resolution_requirements, list)
                            else []
                        ),
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
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GenerateCharacterBlueprintUseCase(_BlueprintLayerBase):
    """生成人物蓝图草稿。"""

    def execute(self, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._context.planner.generate_characters(intent, variant, world, self._context.llm, feedback)
        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status="characters_ready",
            current_step="characters",
            character_draft=[item.model_dump(mode="json") for item in characters],
            roadmap_draft=[],
            roadmap_confirmed=[],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GenerateRoadmapUseCase(_BlueprintLayerBase):
    """生成章节路线草稿。"""

    def execute(self, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        roadmap = self._context.planner.generate_roadmap(
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
            status="roadmap_ready",
            current_step="roadmap",
            roadmap_draft=[item.model_dump(mode="json") for item in roadmap],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class ConfirmBlueprintLayerUseCase(_BlueprintLayerBase):
    """确认某一层蓝图，并推进下一层。"""

    def execute(
        self,
        layer: BlueprintLayer,
        payload: WorldBlueprint | list[CharacterBlueprint] | list[ChapterRoadmapItem] | None = None,
    ) -> BookBlueprint:
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        if layer == "world":
            world = payload if isinstance(payload, WorldBlueprint) else WorldBlueprint.model_validate(
                state.get("world_draft") or state.get("world_confirmed") or {}
            )
            self._sync_world_to_canon(world)
            self._context.db.upsert_book_blueprint_state(
                self._context.book_id,
                status="world_confirmed",
                current_step="characters",
                world_confirmed=world.model_dump(mode="json"),
            )
            return build_book_blueprint(self._context.db, self._context.book_id)

        if layer == "characters":
            raw_characters = payload if isinstance(payload, list) else state.get("character_draft") or []
            characters = [
                item if isinstance(item, CharacterBlueprint) else CharacterBlueprint.model_validate(item)
                for item in raw_characters
            ]
            self._sync_characters_to_canon(characters)
            self._context.db.upsert_book_blueprint_state(
                self._context.book_id,
                status="characters_confirmed",
                current_step="roadmap",
                character_confirmed=[item.model_dump(mode="json") for item in characters],
            )
            return build_book_blueprint(self._context.db, self._context.book_id)

        raw_roadmap = payload if isinstance(payload, list) else state.get("roadmap_draft") or []
        roadmap = [
            item if isinstance(item, ChapterRoadmapItem) else ChapterRoadmapItem.model_validate(item)
            for item in raw_roadmap
        ]
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
            roadmap_confirmed=[item.model_dump(mode="json") for item in roadmap],
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
        return self._context.db.create_blueprint_revision(
            self._context.book_id,
            revision_number=next_revision,
            selected_variant_id=state.get("selected_variant_id"),
            change_reason=change_reason,
            change_summary=change_summary,
            affected_range=affected_range,
            world_blueprint=world.model_dump(mode="json"),
            character_blueprints=[item.model_dump(mode="json") for item in characters],
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
        current_roadmap = [ChapterRoadmapItem.model_validate(item) for item in active_revision.get("roadmap") or []]
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
            roadmap_confirmed=[item.model_dump(mode="json") for item in merged],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)
