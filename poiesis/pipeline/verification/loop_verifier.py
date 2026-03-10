"""剧情线索规则校验器。"""

from __future__ import annotations

from typing import Any

from poiesis.application.contracts import VerifierIssue
from poiesis.domain.world.model import WorldModel


class LoopVerifier:
    """负责检查 loop 生命周期与章节推进约束。"""

    def verify(
        self,
        chapter_number: int,
        world: WorldModel,
        required_loops: list[str],
        loop_updates: list[dict[str, Any]],
    ) -> list[VerifierIssue]:
        issues: list[VerifierIssue] = []
        update_map = {str(item.get("loop_id") or ""): item for item in loop_updates if item.get("loop_id")}
        introduced_loops = {
            loop_id
            for loop_id, item in update_map.items()
            if str(item.get("action") or "") == "introduced"
        }

        for loop_id in required_loops:
            if world.get_loop(loop_id) is None and loop_id not in introduced_loops:
                issues.append(
                    VerifierIssue(
                        severity="fatal",
                        type="loop",
                        reason=f"规划要求推进线索 {loop_id}，但当前世界状态中不存在该线索。",
                        repair_hint="请改用现有线索 ID，或在当前 scene 明确引入新线索。",
                        location=f"loop:{loop_id}",
                    )
                )

        for loop_id, item in update_map.items():
            existing = world.get_loop(loop_id)
            action = str(item.get("action") or "")
            if existing and existing.get("status") == "resolved" and action not in {"introduced", "reopen"}:
                issues.append(
                    VerifierIssue(
                        severity="fatal",
                        type="loop",
                        reason=f"线索 {loop_id} 已解决，不应再次被推进。",
                        repair_hint="请改为引用新的线索，或显式声明这是新的支线问题。",
                        location=f"loop:{loop_id}",
                    )
                )

        for loop in world.list_loops():
            status = str(loop.get("status") or "")
            due_end = loop.get("due_end_chapter")
            current_update = update_map.get(str(loop.get("loop_id") or ""))
            if status not in {"open", "hinted", "escalated"}:
                continue
            if due_end is None or int(due_end) >= chapter_number:
                continue
            if str((current_update or {}).get("action") or "") in {"resolved", "dropped"}:
                continue
            issues.append(
                VerifierIssue(
                    severity="warning",
                    type="loop",
                    reason=f"线索 {loop.get('loop_id')} 已超过建议回收章节（第 {due_end} 章）。",
                    repair_hint="本章可考虑推进或回收该线索；若暂不处理，请在后续章节尽快收束。",
                    location=f"loop:{loop.get('loop_id')}",
                )
            )

        return issues
