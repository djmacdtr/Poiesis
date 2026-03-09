"""预算类校验器。"""

from __future__ import annotations

from typing import Any

from poiesis.application.contracts import VerifierIssue


class BudgetVerifier:
    """负责数量与预算类硬约束。"""

    def __init__(self, new_rule_budget: int) -> None:
        self._new_rule_budget = new_rule_budget

    def verify(self, proposed_changes: list[dict[str, Any]]) -> list[VerifierIssue]:
        """限制单章新增世界规则数量，避免设定膨胀失控。"""
        new_rules = [
            change
            for change in proposed_changes
            if change.get("entity_type") == "world_rule" and change.get("change_type") == "upsert"
        ]
        if len(new_rules) <= self._new_rule_budget:
            return []
        return [
            VerifierIssue(
                severity="fatal",
                type="budget",
                reason=(
                    f"Exceeded new world-rule budget: {len(new_rules)} rules proposed, "
                    f"limit is {self._new_rule_budget}."
                ),
                repair_hint="减少本章引入的新世界规则数量，或把部分信息降级为未确认事实。",
            )
        ]
