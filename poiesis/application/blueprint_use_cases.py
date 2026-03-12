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
    RelationshipBlueprintEdge,
    RelationshipConflictReport,
    RelationshipPendingItem,
    RelationshipRetconProposal,
    RoadmapValidationIssue,
    StoryArcPlan,
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
    planner = RoadmapPlanner()
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
    story_arcs_draft = planner.derive_story_arcs_from_roadmap(roadmap_draft)
    story_arcs_confirmed = planner.derive_story_arcs_from_roadmap(roadmap_confirmed)
    roadmap_issues = planner.verify_roadmap(
        story_arcs_draft or story_arcs_confirmed,
        roadmap_draft or roadmap_confirmed,
    ) if (roadmap_draft or roadmap_confirmed) else []

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
        story_arcs_draft=[StoryArcPlan.model_validate(item.model_dump(mode="json")) for item in story_arcs_draft],
        story_arcs_confirmed=[
            StoryArcPlan.model_validate(item.model_dump(mode="json")) for item in story_arcs_confirmed
        ],
        roadmap_draft=roadmap_draft,
        roadmap_confirmed=roadmap_confirmed,
        roadmap_validation_issues=[
            RoadmapValidationIssue.model_validate(item.model_dump(mode="json"))
            for item in roadmap_issues
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
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class GenerateRoadmapUseCase(_BlueprintLayerBase):
    """生成章节路线草稿。"""

    def execute(self, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        story_arcs, roadmap, issues = self._context.planner.generate_structured_roadmap(
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
            story_arcs_draft=[item.model_dump(mode="json") for item in story_arcs],
            roadmap_draft=[item.model_dump(mode="json") for item in roadmap],
            roadmap_validation_issues=[item.model_dump(mode="json") for item in issues],
        )
        return build_book_blueprint(self._context.db, self._context.book_id)


class RegenerateRoadmapStageUseCase(_BlueprintLayerBase):
    """只重生成一个阶段，作为路线工作台的主修复入口。"""

    def execute(self, arc_number: int, feedback: str = "") -> BookBlueprint:
        intent = self._require_intent()
        variant = self._require_selected_variant()
        world = self._require_world_confirmed()
        characters = self._require_character_confirmed()
        state = self._context.db.get_book_blueprint_state(self._context.book_id) or {}
        current_roadmap = self._context.planner.normalize_roadmap_payload(
            state.get("roadmap_draft") or state.get("roadmap_confirmed") or []
        )
        if not current_roadmap:
            raise ValueError("当前还没有章节路线，请先生成整书路线。")
        story_arcs = self._context.planner.derive_story_arcs_from_roadmap(current_roadmap)
        target_arc = next((item for item in story_arcs if item.arc_number == arc_number), None)
        if target_arc is None:
            raise ValueError(f"第 {arc_number} 幕不存在。")

        preserved_before = [item for item in current_roadmap if item.chapter_number < target_arc.start_chapter]
        preserved_after = [item for item in current_roadmap if item.chapter_number > target_arc.end_chapter]
        current_issues = self._context.planner.verify_roadmap(story_arcs, current_roadmap)
        target_issue_messages = [
            item.message
            for item in current_issues
            if item.arc_number == arc_number or item.story_stage == target_arc.title
        ]
        regeneration_feedback = "；".join(
            part
            for part in [
                feedback.strip(),
                f"请重点修复当前阶段的问题：{'；'.join(target_issue_messages)}" if target_issue_messages else "",
            ]
            if part
        )
        regenerated_stage, arc_issues = self._context.planner.regenerate_story_arc(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=self._context.llm,
            story_arc=target_arc,
            feedback=regeneration_feedback,
            existing_roadmap=preserved_before,
        )
        if any(item.severity == "fatal" for item in arc_issues):
            detail = "；".join(item.message for item in arc_issues if item.severity == "fatal")
            raise ValueError(f"阶段重生成失败：{detail}")

        merged = [*preserved_before, *regenerated_stage, *preserved_after]
        merged_arcs = self._context.planner.derive_story_arcs_from_roadmap(merged)
        merged_issues = self._context.planner.verify_roadmap(merged_arcs, merged)
        merged_arc_issues = [
            item for item in merged_issues if item.arc_number == arc_number or item.story_stage == target_arc.title
        ]
        if any(item.severity == "fatal" for item in merged_arc_issues):
            detail = "；".join(item.message for item in merged_arc_issues if item.severity == "fatal")
            raise ValueError(f"阶段重生成失败：{detail}")

        self._context.db.upsert_book_blueprint_state(
            self._context.book_id,
            status=str(state.get("status") or "roadmap_ready"),
            current_step="roadmap",
            story_arcs_draft=[item.model_dump(mode="json") for item in merged_arcs],
            roadmap_draft=[item.model_dump(mode="json") for item in merged],
            roadmap_validation_issues=[item.model_dump(mode="json") for item in merged_issues],
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
            )
            return build_book_blueprint(self._context.db, self._context.book_id)

        raw_roadmap = payload if isinstance(payload, list) else state.get("roadmap_draft") or []
        roadmap = self._context.planner.normalize_roadmap_payload(raw_roadmap)
        story_arcs = self._context.planner.derive_story_arcs_from_roadmap(roadmap)
        roadmap_issues = self._context.planner.verify_roadmap(story_arcs, roadmap)
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
            roadmap_confirmed=[item.model_dump(mode="json") for item in roadmap],
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
        merged_issues = self._context.planner.verify_roadmap(merged_arcs, merged)
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
