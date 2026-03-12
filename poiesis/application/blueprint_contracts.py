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


class WorldBlueprint(BaseModel):
    """世界观蓝图，作为后续角色与章节路线的上游约束。"""

    setting_summary: str = ""
    immutable_rules: list[dict[str, str | bool]] = Field(default_factory=list)
    power_system: str = ""
    factions: list[str] = Field(default_factory=list)
    taboo_rules: list[str] = Field(default_factory=list)


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


class ChapterRoadmapItem(BaseModel):
    """整书路线中的单章规划。"""

    chapter_number: int
    title: str = ""
    goal: str = ""
    core_conflict: str = ""
    turning_point: str = ""
    character_progress: list[str] = Field(default_factory=list)
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
    roadmap_draft: list[ChapterRoadmapItem] = Field(default_factory=list)
    roadmap_confirmed: list[ChapterRoadmapItem] = Field(default_factory=list)
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
