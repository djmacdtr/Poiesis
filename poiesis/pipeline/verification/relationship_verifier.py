"""人物关系校验器：约束正文不得无解释破坏已锁定关系。"""

from __future__ import annotations

from typing import Any

from poiesis.application.contracts import VerifierIssue
from poiesis.domain.world.model import WorldModel


class RelationshipVerifier:
    """基于关系图谱执行最小可用的一致性检查。"""

    def verify(
        self,
        content: str,
        plan: dict[str, Any],
        world: WorldModel,
    ) -> list[VerifierIssue]:
        roadmap = dict(plan.get("blueprint_roadmap") or {})
        relationship_progress = [
            str(item).strip()
            for item in list(roadmap.get("relationship_progress") or [])
            if str(item).strip()
        ]
        relationship_graph = list(world.relationship_graph or [])
        if not relationship_progress and not relationship_graph:
            return []

        issues: list[VerifierIssue] = []
        normalized_content = content.strip()
        if relationship_progress and normalized_content:
            missing = [item for item in relationship_progress if item not in normalized_content]
            if missing:
                issues.append(
                    VerifierIssue(
                        severity="warning",
                        type="relationship_progress_missing",
                        reason=f"本章路线要求推进的人物关系尚未明确落地：{', '.join(missing)}",
                        repair_hint="请在正文中补足关系推进、误会升级或真相揭示等关系事件。",
                        location="chapter",
                    )
                )

        for edge in relationship_graph:
            hidden_truth = str(edge.get("hidden_truth") or "").strip()
            visibility = str(edge.get("visibility") or "")
            if hidden_truth and visibility in {"隐藏", "误导性表象"} and hidden_truth in normalized_content:
                issues.append(
                    VerifierIssue(
                        severity="fatal",
                        type="relationship_hidden_truth_leaked",
                        reason=(
                            f"关系边 {edge.get('source_character_id', '')} -> "
                            f"{edge.get('target_character_id', '')} 的隐藏真相被正文直接泄露。"
                        ),
                        repair_hint="请改为暗示、铺垫或先在关系重规划流程中标记揭示事件。",
                        location="scene",
                    )
                )

            if edge.get("non_breakable_without_reveal"):
                relation_type = str(edge.get("relation_type") or "")
                summary = str(edge.get("summary") or "")
                changed_keywords = ("决裂", "反目", "背叛", "断绝", "翻脸", "改投")
                if relation_type and relation_type in normalized_content:
                    continue
                if summary and summary in normalized_content:
                    continue
                if any(keyword in normalized_content for keyword in changed_keywords):
                    issues.append(
                        VerifierIssue(
                            severity="warning",
                            type="relationship_break_without_reveal",
                            reason=(
                                f"关系边 {edge.get('source_character_id', '')} -> "
                                f"{edge.get('target_character_id', '')} 被写成明显变化，但未看到对应揭示事件。"
                            ),
                            repair_hint="请补充触发关系反转的场景证据，或通过关系重规划工作台先锁定未来改写路径。",
                            location="scene",
                        )
                    )
        return issues
