"""校验枢纽，负责聚合多个子校验器。"""

from __future__ import annotations

from typing import Any

from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.pipeline.verification.budget_verifier import BudgetVerifier
from poiesis.pipeline.verification.canon_verifier import CanonVerifier
from poiesis.pipeline.verification.result import VerificationResult
from poiesis.pipeline.verification.semantic_verifier import LLMSemanticVerifier


class VerifierHub:
    """聚合多个 verifier，并输出统一结构。"""

    def __init__(
        self,
        new_rule_budget: int = 5,
        prompt_path: str | None = None,
        language: str = "zh-CN",
    ) -> None:
        self._new_rule_budget = new_rule_budget
        self._budget_verifier = BudgetVerifier(new_rule_budget)
        self._canon_verifier = CanonVerifier()
        self._llm_verifier = LLMSemanticVerifier(prompt_path=prompt_path, language=language)

    def verify(
        self,
        chapter_number: int,
        content: str,
        plan: dict[str, Any],
        world: WorldModel,
        proposed_changes: list[dict[str, Any]],
        llm: LLMClient,
    ) -> VerificationResult:
        """按固定顺序执行子校验器，便于问题归因和后续指标统计。"""
        issues = [
            *self._budget_verifier.verify(proposed_changes),
            *self._canon_verifier.verify(world, proposed_changes),
            *self._llm_verifier.verify(
                chapter_number=chapter_number,
                content=content,
                plan=plan,
                world=world,
                proposed_changes=proposed_changes,
                llm=llm,
                new_rule_budget=self._new_rule_budget,
            ),
        ]
        violations = [issue.reason for issue in issues if issue.severity == "fatal"]
        warnings = [issue.reason for issue in issues if issue.severity == "warning"]
        return VerificationResult(
            passed=len(violations) == 0,
            issues=issues,
            violations=violations,
            warnings=warnings,
        )
