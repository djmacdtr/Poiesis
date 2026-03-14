"""创作蓝图 API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel

from poiesis.application.blueprint_contracts import (
    BlueprintReplanRequest,
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
    WorldBlueprint,
)


class CreationIntentRequest(CreationIntent):
    """保存创作意图的请求体。"""


class ConceptVariantListResponse(BaseModel):
    """候选方向列表。"""

    items: list[ConceptVariant]


class BlueprintLayerGenerateRequest(BaseModel):
    """生成世界/人物/路线时的微调提示。"""

    feedback: str = ""


class SelectConceptVariantResponse(BookBlueprint):
    """选择候选方向后的聚合响应。"""


class ConfirmWorldBlueprintRequest(BaseModel):
    """确认世界观层时允许作者提交修改后的草稿。"""

    draft: WorldBlueprint | None = None


class ConfirmCharacterBlueprintRequest(BaseModel):
    """确认人物层时允许作者提交修改后的草稿。"""

    characters: list[CharacterBlueprint] | None = None
    relationship_graph: list[RelationshipBlueprintEdge] | None = None


class ConfirmRoadmapRequest(BaseModel):
    """确认章节路线层时允许作者提交修改后的草稿。"""

    draft: list[ChapterRoadmapItem] | None = None


class BookBlueprintResponse(BookBlueprint):
    """整书蓝图响应。"""


class RegenerateConceptVariantResponse(ConceptVariantRegenerationResult):
    """单版重生成结果。"""


class AcceptRegeneratedConceptVariantRequest(BaseModel):
    """人工接受单版重生成提案。"""

    proposal: ConceptVariant


class BlueprintRevisionListResponse(BaseModel):
    """蓝图版本历史。"""

    items: list[dict[str, object]]


class BlueprintReplanPayload(BlueprintReplanRequest):
    """未来章节重规划请求。"""


class RelationshipGraphResponse(BaseModel):
    """人物关系图谱工作态响应。"""

    nodes: list[CharacterNode]
    edges: list[RelationshipBlueprintEdge]
    pending: list[RelationshipPendingItem]


class ConfirmRelationshipGraphRequest(BaseModel):
    """确认关系图谱。"""

    edges: list[RelationshipBlueprintEdge]


class UpsertRelationshipEdgeRequest(BaseModel):
    """新增或编辑关系边。"""

    edge: RelationshipBlueprintEdge


class RelationshipConflictResponse(BaseModel):
    """关系编辑命中冲突时返回的结构化报告。"""

    report: RelationshipConflictReport


class RelationshipPendingListResponse(BaseModel):
    """待确认关系/人物列表。"""

    items: list[RelationshipPendingItem]


class RelationshipReplanCreateRequest(BaseModel):
    """创建关系重规划请求。"""

    edge_id: str
    reason: str = ""
    desired_change: str = ""


class RelationshipReplanConfirmRequest(BaseModel):
    """确认关系重规划提案。"""

    proposal_id: str


class RelationshipReplanResponse(BaseModel):
    """关系重规划工作态。"""

    request_id: int
    request: dict[str, object]
    proposal: RelationshipRetconProposal


class CreativeIssueListResponse(BaseModel):
    """统一闭环控制面的问题列表响应。"""

    items: list[CreativeIssue]


class PlanCreativeRepairsRequest(BaseModel):
    """生成修复提案时可指定只处理部分 issue。"""

    issue_ids: list[str] = []


class CreativeRepairProposalResponse(CreativeRepairProposal):
    """单条修复提案响应。"""


class CreativeRepairRunListResponse(BaseModel):
    """执行记录列表。"""

    items: list[CreativeRepairRun]
