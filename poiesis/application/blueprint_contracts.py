"""创作蓝图协议：统一定义新书创建与蓝图锁定的正式结构。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BlueprintLayer = Literal["world", "characters", "roadmap"]
BlueprintStatus = Literal[
    "intent_pending",
    "concept_generated",
    "concept_selected",
    "world_ready",
    "world_confirmed",
    "characters_ready",
    "characters_confirmed",
    "roadmap_ready",
    "locked",
]


class CreationIntent(BaseModel):
    """作者给系统的高层创作意图。"""

    genre: str = ""
    themes: list[str] = Field(default_factory=list)
    tone: str = ""
    protagonist_prompt: str = ""
    conflict_prompt: str = ""
    ending_preference: str = ""
    forbidden_elements: list[str] = Field(default_factory=list)
    length_preference: str = ""
    target_experience: str = ""
    variant_preference: str = ""


class LocationBlueprint(BaseModel):
    """世界中的关键地点蓝图。"""

    name: str = ""
    role: str = ""
    description: str = ""


class PowerSystemBlueprint(BaseModel):
    """力量体系蓝图。"""

    core_mechanics: str = ""
    costs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    advancement_path: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)


class FactionBlueprint(BaseModel):
    """势力蓝图。"""

    name: str = ""
    position: str = ""
    goal: str = ""
    methods: list[str] = Field(default_factory=list)
    public_image: str = ""
    hidden_truth: str = ""


class ImmutableRuleBlueprint(BaseModel):
    """不可变世界规则。"""

    key: str = ""
    description: str = ""
    category: str = "world"
    rationale: str = ""
    is_immutable: bool = True


class TabooRuleBlueprint(BaseModel):
    """禁忌规则。"""

    key: str = ""
    description: str = ""
    consequence: str = ""
    is_immutable: bool = True


class ConceptVariantFrame(BaseModel):
    """候选方向骨架，先锁定分歧维度，再扩写成完整版本。"""

    variant_no: int
    variant_strategy: str = ""
    core_driver: str = ""
    conflict_source: str = ""
    world_structure: str = ""
    protagonist_arc_mode: str = ""
    tone_signature: str = ""
    ending_mode: str = ""
    differentiators: list[str] = Field(default_factory=list)


class ConceptVariant(BaseModel):
    """候选创作方向，由系统一次生成多版供作者选择。"""

    id: int | None = None
    variant_no: int
    hook: str
    world_pitch: str
    main_arc_pitch: str
    ending_pitch: str
    variant_strategy: str = ""
    core_driver: str = ""
    conflict_source: str = ""
    world_structure: str = ""
    protagonist_arc_mode: str = ""
    tone_signature: str = ""
    differentiators: list[str] = Field(default_factory=list)
    diversity_note: str = ""
    selected: bool = False


class VariantSimilarityIssue(BaseModel):
    """描述单版候选与其他候选过于相似时的结构化诊断。"""

    compared_variant_no: int
    text_similarity: float = 0.0
    structure_overlap: int = 0
    repeated_keywords: list[str] = Field(default_factory=list)
    repeated_sections: list[str] = Field(default_factory=list)
    repeated_fields: list[str] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)


class VariantRegenerationAttempt(BaseModel):
    """单版重生成时的单轮回炉记录。"""

    attempt_no: int
    status: Literal["retrying", "applied", "needs_confirmation"]
    warnings: list[str] = Field(default_factory=list)
    similarity_issue: VariantSimilarityIssue | None = None


class ConceptVariantRegenerationResult(BaseModel):
    """单版重生成的结果态。"""

    status: Literal["applied", "needs_confirmation"]
    target_variant_id: int
    attempt_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    applied_variant: ConceptVariant | None = None
    proposed_variant: ConceptVariant | None = None
    similarity_report: VariantSimilarityIssue | None = None
    attempts: list[VariantRegenerationAttempt] = Field(default_factory=list)
    blueprint: BookBlueprint


class WorldBlueprint(BaseModel):
    """世界观蓝图，作为后续角色与章节路线的上游约束。"""

    setting_summary: str = ""
    era_context: str = ""
    social_order: str = ""
    historical_wounds: list[str] = Field(default_factory=list)
    public_secrets: list[str] = Field(default_factory=list)
    geography: list[LocationBlueprint] = Field(default_factory=list)
    power_system: PowerSystemBlueprint = Field(default_factory=PowerSystemBlueprint)
    factions: list[FactionBlueprint] = Field(default_factory=list)
    immutable_rules: list[ImmutableRuleBlueprint] = Field(default_factory=list)
    taboo_rules: list[TabooRuleBlueprint] = Field(default_factory=list)


class CharacterBlueprint(BaseModel):
    """人物蓝图。"""

    name: str
    role: str = ""
    public_persona: str = ""
    core_motivation: str = ""
    fatal_flaw: str = ""
    non_negotiable_traits: list[str] = Field(default_factory=list)
    relationship_constraints: list[str] = Field(default_factory=list)
    arc_outline: list[str] = Field(default_factory=list)


class CharacterNode(BaseModel):
    """人物关系图谱中的角色节点。"""

    character_id: str
    name: str
    role: str = ""
    public_persona: str = ""
    core_motivation: str = ""
    fatal_flaw: str = ""
    non_negotiable_traits: list[str] = Field(default_factory=list)
    arc_outline: list[str] = Field(default_factory=list)
    faction_affiliation: str = ""
    status: str = "active"


class RelationshipBlueprintEdge(BaseModel):
    """蓝图层确认的人物关系边。"""

    edge_id: str
    source_character_id: str
    target_character_id: str
    relation_type: str
    polarity: Literal["正向", "负向", "复杂", "伪装"] = "复杂"
    intensity: int = 3
    visibility: Literal["公开", "半公开", "隐藏", "误导性表象"] = "半公开"
    stability: Literal["稳定", "脆弱", "正在转变"] = "稳定"
    summary: str = ""
    hidden_truth: str = ""
    non_breakable_without_reveal: bool = False


class RelationshipState(BaseModel):
    """执行态关系状态。"""

    edge_id: str
    current_relation_type: str
    current_intensity: int = 3
    visibility: Literal["公开", "半公开", "隐藏", "误导性表象"] = "半公开"
    stability: Literal["稳定", "脆弱", "正在转变"] = "稳定"
    revealed: bool = False
    latest_chapter: int | None = None
    latest_scene_ref: str = ""
    pending_confirmation: bool = False


class RelationshipEvent(BaseModel):
    """关系推进事件。"""

    event_id: str
    edge_id: str
    event_type: Literal["introduced", "progressed", "revealed", "intensified", "weakened", "reversed"] = "introduced"
    chapter_number: int | None = None
    scene_ref: str = ""
    summary: str = ""
    revealed_fact: str = ""


class RelationshipConflictReport(BaseModel):
    """编辑关系时的冲突报告。"""

    edge_id: str
    source_chapter: int
    source_scene_ref: str = ""
    conflict_summary: str
    immutable_fact: str
    recommended_paths: list[str] = Field(default_factory=list)


class RelationshipRetconProposal(BaseModel):
    """关系重规划/反转提案。"""

    proposal_id: str
    edge_id: str
    request_reason: str = ""
    change_summary: str = ""
    strategy: Literal["未来关系重规划", "关系反转提案", "表象关系与真相关系分层"] = "未来关系重规划"
    affected_future_chapters: list[int] = Field(default_factory=list)
    future_edge: RelationshipBlueprintEdge
    required_reveals: list[str] = Field(default_factory=list)


class RelationshipPendingItem(BaseModel):
    """章节推进时自动接入但尚未确认的人物/关系项。"""

    id: int | None = None
    item_type: Literal["character", "relationship"] = "character"
    status: Literal["pending", "confirmed", "rejected"] = "pending"
    source_chapter: int | None = None
    source_scene_ref: str = ""
    summary: str = ""
    character: CharacterNode | None = None
    relationship: RelationshipBlueprintEdge | None = None


class StoryArcPlan(BaseModel):
    """整书蓝图中的阶段/卷级路线。"""

    arc_number: int
    title: str = ""
    purpose: str = ""
    start_chapter: int = 1
    end_chapter: int = 1
    main_progress: list[str] = Field(default_factory=list)
    relationship_progress: list[str] = Field(default_factory=list)
    loop_progress: list[str] = Field(default_factory=list)
    timeline_milestones: list[str] = Field(default_factory=list)
    arc_climax: str = ""


class RoadmapValidationIssue(BaseModel):
    """蓝图阶段的静态路线校验问题。"""

    severity: Literal["fatal", "warning"] = "warning"
    type: str = ""
    message: str = ""
    chapter_number: int | None = None
    story_stage: str = ""
    arc_number: int | None = None
    suggested_action: Literal["regenerate_stage", "edit_chapter", "review_stage"] = "review_stage"


class ChapterRoadmapItem(BaseModel):
    """整书路线中的单章规划。"""

    chapter_number: int
    title: str = ""
    story_stage: str = ""
    timeline_anchor: str = ""
    depends_on_chapters: list[int] = Field(default_factory=list)
    goal: str = ""
    core_conflict: str = ""
    turning_point: str = ""
    story_progress: str = ""
    character_progress: list[str] = Field(default_factory=list)
    relationship_progress: list[str] = Field(default_factory=list)
    new_reveals: list[str] = Field(default_factory=list)
    status_shift: list[str] = Field(default_factory=list)
    chapter_function: str = ""
    anti_repeat_signature: str = ""
    planned_loops: list[dict[str, object]] = Field(default_factory=list)
    closure_function: str = ""


class BlueprintRevision(BaseModel):
    """整书蓝图的版本快照。"""

    id: int
    revision_number: int
    is_active: bool = False
    change_reason: str = ""
    change_summary: str = ""
    affected_range: list[int] = Field(default_factory=list)
    created_at: str = ""


class BookBlueprint(BaseModel):
    """当前作品的创作蓝图聚合。"""

    book_id: int
    status: BlueprintStatus = "intent_pending"
    current_step: str = "intent"
    active_revision_id: int | None = None
    selected_variant_id: int | None = None
    intent: CreationIntent | None = None
    concept_variants: list[ConceptVariant] = Field(default_factory=list)
    selected_variant: ConceptVariant | None = None
    world_draft: WorldBlueprint | None = None
    world_confirmed: WorldBlueprint | None = None
    character_draft: list[CharacterBlueprint] = Field(default_factory=list)
    character_confirmed: list[CharacterBlueprint] = Field(default_factory=list)
    relationship_graph_draft: list[RelationshipBlueprintEdge] = Field(default_factory=list)
    relationship_graph_confirmed: list[RelationshipBlueprintEdge] = Field(default_factory=list)
    relationship_pending: list[RelationshipPendingItem] = Field(default_factory=list)
    story_arcs_draft: list[StoryArcPlan] = Field(default_factory=list)
    story_arcs_confirmed: list[StoryArcPlan] = Field(default_factory=list)
    roadmap_draft: list[ChapterRoadmapItem] = Field(default_factory=list)
    roadmap_confirmed: list[ChapterRoadmapItem] = Field(default_factory=list)
    roadmap_validation_issues: list[RoadmapValidationIssue] = Field(default_factory=list)
    revisions: list[BlueprintRevision] = Field(default_factory=list)


class BlueprintConstraintViolation(BaseModel):
    """正文偏离蓝图时的正式违规结构。"""

    severity: Literal["fatal", "warning"] = "fatal"
    type: str
    message: str
    chapter_number: int | None = None
    scene_number: int | None = None


class BlueprintLayerDraftRequest(BaseModel):
    """生成某一层蓝图时可附带微调要求。"""

    feedback: str = ""


class BlueprintReplanRequest(BaseModel):
    """重规划未来章节时的请求。"""

    starting_chapter: int = 1
    reason: str = ""
    guidance: str = ""
