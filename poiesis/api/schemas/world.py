"""世界设定相关响应模型（Canon / Staging）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from poiesis.application.blueprint_contracts import RelationshipBlueprintEdge, WorldBlueprint


class WorldRule(BaseModel):
    """世界规则。"""

    id: int
    rule_key: str
    description: str
    is_immutable: bool
    category: str | None = None
    created_at: str


class Character(BaseModel):
    """角色。"""

    id: int
    name: str
    description: str | None = None
    core_motivation: str | None = None
    attributes: dict[str, Any] = {}
    status: str
    created_at: str
    updated_at: str


class TimelineEvent(BaseModel):
    """时间线事件。"""

    id: int
    event_key: str
    chapter_number: int | None = None
    description: str
    characters_involved: list[str] = []
    timestamp_in_world: str | None = None
    created_at: str


class Foreshadowing(BaseModel):
    """伏笔。"""

    id: int
    hint_key: str
    description: str
    introduced_in_chapter: int | None = None
    resolved_in_chapter: int | None = None
    # 数据库中状态为 'pending'/'active'/'resolved'/'dropped'
    status: str
    created_at: str


class CanonData(BaseModel):
    """Canon 数据整体响应，对应前端 CanonData 类型。"""

    world_rules: list[WorldRule] = []
    characters: list[Character] = []
    timeline: list[TimelineEvent] = []
    foreshadowing: list[Foreshadowing] = []
    story_state: dict[str, Any] = {}
    world_blueprint_summary: WorldBlueprint | None = None
    relationship_graph: list[RelationshipBlueprintEdge] = []


class StagingChange(BaseModel):
    """Staging 变更记录，对应前端 StagingChange 类型。"""

    id: int
    change_type: str
    entity_type: str
    entity_key: str
    proposed_data: dict[str, Any] = {}
    status: str
    source_chapter: int | None = None
    rejection_reason: str | None = None
    created_at: str


class ApproveRequest(BaseModel):
    """审批通过请求体（comment 为可选备注）。"""

    comment: str | None = None


class RejectRequest(BaseModel):
    """拒绝请求体（必须包含 reason）。"""

    reason: str
