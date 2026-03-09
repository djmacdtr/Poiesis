"""提取子系统内部协议。"""

from __future__ import annotations

from enum import StrEnum


class ExtractedEntityType(StrEnum):
    """当前提取器支持的实体类型。"""

    CHARACTER = "character"
    WORLD_RULE = "world_rule"
    TIMELINE_EVENT = "timeline_event"
    FORESHADOWING = "foreshadowing"

