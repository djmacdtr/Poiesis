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
    "story_arcs_ready",
    "roadmap_ready",
    "locked",
]
CreativeIssueSourceLayer = Literal["blueprint", "roadmap", "scene", "review", "canon"]
CreativeIssueTargetType = Literal[
    "roadmap_chapter",
    "roadmap_arc",
    "scene_chapter",
    "character",
    "relationship",
    "world",
    "canon_fact",
]
CreativeRepairability = Literal["deterministic", "llm", "manual"]
CreativeIssueStatus = Literal["open", "planned", "awaiting_approval", "applied", "verified", "escalated", "dismissed"]
CreativeRepairStrategy = Literal["field_patch", "chapter_rewrite", "arc_rewrite", "scene_rewrite", "canon_sync"]
CreativeRepairRiskLevel = Literal["low", "medium", "high"]
CreativeRepairRunStatus = Literal["queued", "running", "succeeded", "failed", "rolled_back"]
RepairOperationType = Literal[
    "set_field",
    "append_item",
    "remove_item",
    "rewrite_chapter",
    "rewrite_arc",
    "rewrite_scene",
    "sync_canon",
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
    status: Literal["draft", "in_progress", "completed", "confirmed"] = "draft"
    has_chapters: bool = False
    generated_chapter_count: int = 0
    chapter_target_count: int = 0
    next_chapter_number: int | None = None
    can_generate_next_chapter: bool = False
    blocking_arc_number: int | None = None
    expansion_issue_count: int = 0


class RoadmapValidationIssue(BaseModel):
    """蓝图阶段的静态路线校验问题。"""

    severity: Literal["fatal", "warning"] = "warning"
    type: str = ""
    message: str = ""
    chapter_number: int | None = None
    story_stage: str = ""
    arc_number: int | None = None
    scope: Literal["arc", "chapter", "global"] = "chapter"
    suggested_action: Literal[
        "generate_next_chapter",
        "regenerate_last_chapter",
        "edit_chapter",
        "review_arc",
    ] = "review_arc"


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
    key_events: list[str] = Field(default_factory=list)
    chapter_tasks: list[PlannedTaskItem] = Field(default_factory=list)
    character_progress: list[str] = Field(default_factory=list)
    relationship_beats: list[PlannedRelationshipBeat] = Field(default_factory=list)
    relationship_progress: list[str] = Field(default_factory=list)
    new_reveals: list[str] = Field(default_factory=list)
    world_updates: list[str] = Field(default_factory=list)
    status_shift: list[str] = Field(default_factory=list)
    chapter_function: str = ""
    anti_repeat_signature: str = ""
    # 伏笔改为显式结构，避免前后端长期围绕匿名 dict 补兼容逻辑。
    planned_loops: list[PlannedLoopItem] = Field(default_factory=list)
    closure_function: str = ""


class PlannedTaskItem(BaseModel):
    """章节计划里显式引入或推进的任务项。"""

    task_id: str = ""
    summary: str = ""
    status: Literal["new", "in_progress", "resolved", "failed"] = "new"
    related_characters: list[str] = Field(default_factory=list)
    due_end_chapter: int | None = None


class PlannedRelationshipBeat(BaseModel):
    """章节层显式声明的人物关系推进。"""

    source_character: str = ""
    target_character: str = ""
    summary: str = ""


class PlannedLoopItem(BaseModel):
    """章节层显式声明的伏笔/悬念项。

    设计约束：
    1. due_end_chapter 现在是强制约束，目的是阻止伏笔无限堆积；
    2. 允许跨幕，但必须给出明确的最迟兑现章；
    3. title / summary 都要求保留，前者偏展示，后者偏连续性校验和后续生成提示。
    """

    loop_id: str = ""
    title: str = ""
    summary: str = ""
    status: Literal["open", "progressed", "resolved"] = "open"
    priority: int = 1
    due_start_chapter: int | None = None
    due_end_chapter: int
    related_characters: list[str] = Field(default_factory=list)
    resolution_requirements: list[str] = Field(default_factory=list)


class BlueprintContinuityEvent(BaseModel):
    """蓝图工作态中的连续性事件摘要。"""

    chapter_number: int
    story_stage: str = ""
    timeline_anchor: str = ""
    kind: Literal["main_progress", "key_event", "reveal", "world_update"] = "key_event"
    summary: str = ""


class BlueprintRelationshipState(BaseModel):
    """基于章节路线聚合出的最新关系状态。"""

    source_character: str = ""
    target_character: str = ""
    latest_summary: str = ""
    source_chapter: int | None = None


class BlueprintContinuityLoop(BaseModel):
    """连续性工作态中的活跃伏笔摘要。

    这里保留 due_end_chapter，而不是只保留展示层别名，
    是为了让前端和后端对“最迟兑现章”的语义完全一致。
    """

    loop_id: str = ""
    label: str | None = None
    summary: str | None = None
    title: str | None = None
    status: str | None = None
    due_end_chapter: int | None = None
    payoff_due_chapter: int | None = None


class BlueprintContinuityState(BaseModel):
    """单章工作流使用的连续性工作态。"""

    last_planned_chapter: int = 0
    open_tasks: list[PlannedTaskItem] = Field(default_factory=list)
    resolved_tasks: list[PlannedTaskItem] = Field(default_factory=list)
    active_loops: list[BlueprintContinuityLoop] = Field(default_factory=list)
    recent_events: list[BlueprintContinuityEvent] = Field(default_factory=list)
    relationship_states: list[BlueprintRelationshipState] = Field(default_factory=list)
    world_updates: list[str] = Field(default_factory=list)


class BlueprintRevision(BaseModel):
    """整书蓝图的版本快照。"""

    id: int
    revision_number: int
    is_active: bool = False
    change_reason: str = ""
    change_summary: str = ""
    affected_range: list[int] = Field(default_factory=list)
    created_at: str = ""


class CreativeIssue(BaseModel):
    """统一闭环控制面中的问题项。

    设计约束：
    1. 这里不只服务 roadmap，字段必须能覆盖 scene / review / canon 的后续接入；
    2. status 是控制面状态，不等于 verifier 严重级别；
    3. suggested_strategy / repairability 直接供前端展示，避免工作台再自己猜一遍。
    4. target_ref 只承担“定位引用”职责，详细只读上下文统一放到 context_payload，
       避免后续把 review / scene 的展示细节继续硬塞进 message 或 target_ref。
    """

    issue_id: str
    book_id: int
    source_layer: CreativeIssueSourceLayer
    target_type: CreativeIssueTargetType
    target_ref: dict[str, object] = Field(default_factory=dict)
    issue_type: str
    severity: Literal["fatal", "warning"] = "warning"
    message: str = ""
    detected_by: str = ""
    repairability: CreativeRepairability = "manual"
    status: CreativeIssueStatus = "open"
    suggested_strategy: CreativeRepairStrategy | None = None
    # issue_signature 用来识别“是否还是同一类问题”，方便编排器做去重和冷却。
    issue_signature: str = ""
    context_payload: dict[str, object] = Field(default_factory=dict)


class RepairOperation(BaseModel):
    """修复提案中的原子操作。

    第一阶段虽然主要落在 roadmap，但操作类型提前按全栈闭环留齐，
    这样后续接入 scene / canon 时不用再推翻已有协议。
    """

    op_type: RepairOperationType
    target_ref: dict[str, object] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)
    reason: str = ""


class CreativeRepairProposal(BaseModel):
    """面向作者展示和确认的修复提案。

    默认自治级别是“建议后执行”，因此提案必须包含足够的 diff 和预期结果，
    让作者能先看清楚系统打算怎么改，再决定是否接受。
    """

    proposal_id: str
    book_id: int
    issue_ids: list[str] = Field(default_factory=list)
    strategy_type: CreativeRepairStrategy
    risk_level: CreativeRepairRiskLevel = "medium"
    status: Literal["draft", "awaiting_approval", "applied", "failed", "rolled_back"] = "awaiting_approval"
    # proposal_signature 用来识别“是否已经存在同一类提案”，避免当前提案区持续堆同一方案。
    proposal_signature: str = ""
    operations: list[RepairOperation] = Field(default_factory=list)
    summary: str = ""
    diff_preview: list[dict[str, object]] = Field(default_factory=list)
    expected_post_conditions: list[str] = Field(default_factory=list)
    requires_llm: bool = False
    created_at: str = ""


class CreativeRepairRun(BaseModel):
    """记录一次修复提案的执行结果与回滚锚点。"""

    run_id: str
    book_id: int
    proposal_id: str
    execution_mode: Literal["preview", "apply"] = "apply"
    status: CreativeRepairRunStatus = "queued"
    logs: list[str] = Field(default_factory=list)
    before_snapshot_ref: str | None = None
    after_snapshot_ref: str | None = None
    created_at: str = ""
    error_message: str = ""


class CreativeStateSnapshot(BaseModel):
    """闭环控制面使用的轻量快照。

    这里保存的是“蓝图工作态业务真源”，不把 proposals / runs 自己也卷进快照，
    否则回滚时会把执行历史一并抹掉，后续就无法审计。
    """

    snapshot_id: str
    book_id: int
    payload: dict[str, object] = Field(default_factory=dict)
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
    expanded_arc_numbers: list[int] = Field(default_factory=list)
    roadmap_draft: list[ChapterRoadmapItem] = Field(default_factory=list)
    roadmap_confirmed: list[ChapterRoadmapItem] = Field(default_factory=list)
    continuity_state: BlueprintContinuityState = Field(default_factory=BlueprintContinuityState)
    roadmap_validation_issues: list[RoadmapValidationIssue] = Field(default_factory=list)
    creative_issues: list[CreativeIssue] = Field(default_factory=list)
    creative_repair_proposals: list[CreativeRepairProposal] = Field(default_factory=list)
    creative_repair_runs: list[CreativeRepairRun] = Field(default_factory=list)
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
