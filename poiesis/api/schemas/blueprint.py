"""创作蓝图 API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel

from poiesis.application.blueprint_contracts import (
    BlueprintReplanRequest,
    BookBlueprint,
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    CreationIntent,
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

    draft: list[CharacterBlueprint] | None = None


class ConfirmRoadmapRequest(BaseModel):
    """确认章节路线层时允许作者提交修改后的草稿。"""

    draft: list[ChapterRoadmapItem] | None = None


class BookBlueprintResponse(BookBlueprint):
    """整书蓝图响应。"""


class BlueprintRevisionListResponse(BaseModel):
    """蓝图版本历史。"""

    items: list[dict[str, object]]


class BlueprintReplanPayload(BlueprintReplanRequest):
    """未来章节重规划请求。"""
