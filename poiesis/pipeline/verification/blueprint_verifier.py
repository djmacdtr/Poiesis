"""蓝图约束校验器：确保正文仍在已锁定整书蓝图内推进。"""

from __future__ import annotations

from typing import Any

from poiesis.application.contracts import VerifierIssue
from poiesis.domain.world.model import WorldModel


class BlueprintVerifier:
    """执行蓝图层的结构化约束检查。"""

    def verify(
        self,
        chapter_number: int,
        plan: dict[str, Any],
        world: WorldModel,
        loop_updates: list[dict[str, Any]],
    ) -> list[VerifierIssue]:
        roadmap = dict(plan.get("blueprint_roadmap") or {})
        if not roadmap:
            return []

        issues: list[VerifierIssue] = []
        if int(roadmap.get("chapter_number") or chapter_number) != chapter_number:
            issues.append(
                VerifierIssue(
                    severity="fatal",
                    type="blueprint_route_mismatch",
                    reason="当前章节未绑定到正确的整书路线项。",
                    repair_hint="请重新读取蓝图路线并按该章节规划生成正文。",
                    location="chapter",
                )
            )

        planned_loops = [str(item.get("loop_id") or "") for item in roadmap.get("planned_loops") or [] if item]
        progressed = {str(item.get("loop_id") or "") for item in loop_updates}
        missing = [loop_id for loop_id in planned_loops if loop_id and loop_id not in progressed]
        if missing:
            issues.append(
                VerifierIssue(
                    severity="warning",
                    type="blueprint_loop_missing",
                    reason=f"本章路线中规划的关键线索尚未显式推进：{', '.join(missing)}",
                    repair_hint="请在正文或场景规划中补上这些线索的推进动作。",
                    location="chapter",
                )
            )

        locked_characters = {
            str(char.get("name") or "")
            for char in world.canon.get("characters", {}).values()
            if char.get("name")
        }
        referenced = {
            str(item)
            for item in roadmap.get("character_progress") or []
            if isinstance(item, str) and item.strip()
        }
        unknown = [item for item in referenced if item not in locked_characters]
        if unknown:
            issues.append(
                VerifierIssue(
                    severity="warning",
                    type="blueprint_character_unknown",
                    reason=f"章节路线里引用了未锁定的人物推进项：{', '.join(unknown)}",
                    repair_hint="请先确认人物蓝图，或修正章节路线中的人物名称。",
                    location="chapter",
                )
            )
        return issues
