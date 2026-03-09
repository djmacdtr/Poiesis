"""设定一致性校验器。"""

from __future__ import annotations

from typing import Any

from poiesis.application.contracts import VerifierIssue
from poiesis.domain.world.model import WorldModel


class CanonVerifier:
    """负责规则、角色、时间线等基础一致性检查。"""

    def verify(
        self,
        world: WorldModel,
        proposed_changes: list[dict[str, Any]],
    ) -> list[VerifierIssue]:
        """当前先覆盖最容易出错的不可变规则更新。"""
        issues: list[VerifierIssue] = []
        for change in proposed_changes:
            if change.get("entity_type") == "world_rule" and change.get("change_type") == "update":
                entity_key = str(change.get("entity_key") or "")
                existing = world.canon["world_rules"].get(entity_key)
                if existing and existing.get("is_immutable"):
                    issues.append(
                        VerifierIssue(
                            severity="fatal",
                            type="canon",
                            reason=f"Attempted to update immutable world rule: {entity_key}.",
                            repair_hint="不要修改不可变规则，改为解释或回避当前情节冲突。",
                            location=f"world_rule:{entity_key}",
                        )
                    )
        return issues
