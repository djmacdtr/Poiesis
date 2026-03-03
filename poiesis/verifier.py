"""生成章节的一致性验证器。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poiesis.llm.base import LLMClient
from poiesis.world import WorldModel

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "verifier.txt"


@dataclass
class VerificationResult:
    """Result of a chapter consistency check."""

    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ConsistencyVerifier:
    """Verifies that a chapter is internally consistent with world canon."""

    def __init__(self, new_rule_budget: int = 5, prompt_path: str | None = None) -> None:
        """Initialise the verifier.

        Args:
            new_rule_budget: Maximum allowed new world facts per chapter.
            prompt_path: Override path to the verifier prompt template.
        """
        self._new_rule_budget = new_rule_budget
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH

    def verify(
        self,
        chapter_number: int,
        content: str,
        plan: dict[str, Any],
        world: WorldModel,
        proposed_changes: list[dict[str, Any]],
        llm: LLMClient,
    ) -> VerificationResult:
        """Verify chapter consistency.

        Performs both rule-based and LLM-assisted checks.

        Args:
            chapter_number: Chapter number being verified.
            content: Full chapter prose.
            plan: Structured plan for the chapter.
            world: Current :class:`~poiesis.world.WorldModel`.
            proposed_changes: Staging changes extracted from the chapter.
            llm: :class:`~poiesis.llm.base.LLMClient` for LLM-based checks.

        Returns:
            :class:`VerificationResult` with pass/fail and detail lists.
        """
        violations: list[str] = []
        warnings: list[str] = []

        # --- 基于规则的静态检查 ---
        self._check_new_fact_budget(proposed_changes, violations, warnings)

        # --- 基于 LLM 的语义检查 ---
        world_context = world.world_context_summary()
        changes_text = json.dumps(proposed_changes, indent=2)
        plan_text = json.dumps(plan, indent=2)

        template = self._load_template()
        prompt = template.format(
            chapter_number=chapter_number,
            content=content,
            plan=plan_text,
            world_context=world_context,
            proposed_changes=changes_text,
            new_rule_budget=self._new_rule_budget,
        )

        system = (
            "You are a strict continuity editor. Identify every hard violation. "
            "Return ONLY valid JSON."
        )
        raw = llm.complete_json(prompt, system=system)

        violations.extend(raw.get("violations", []))
        warnings.extend(raw.get("warnings", []))
        llm_passed: bool = raw.get("passed", True)

        passed = llm_passed and len(violations) == 0
        return VerificationResult(passed=passed, violations=violations, warnings=warnings)

    # ------------------------------------------------------------------
    # Rule-based helpers
    # ------------------------------------------------------------------

    def _check_new_fact_budget(
        self,
        proposed_changes: list[dict[str, Any]],
        violations: list[str],
        warnings: list[str],
    ) -> None:
        """Flag if the number of new world facts exceeds the budget."""
        new_rules = [
            c for c in proposed_changes if c.get("entity_type") == "world_rule"
            and c.get("change_type") == "upsert"
        ]
        if len(new_rules) > self._new_rule_budget:
            violations.append(
                f"Exceeded new world-rule budget: {len(new_rules)} rules proposed, "
                f"limit is {self._new_rule_budget}."
            )

    def _load_template(self) -> str:
        """Load the verifier prompt template from disk."""
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Verify chapter {chapter_number}.\nContent:\n{content}\n"
            "Plan:\n{plan}\nWorld:\n{world_context}\n"
            "Proposed changes:\n{proposed_changes}\n"
            "New rule budget: {new_rule_budget}\n"
            'Return JSON with "passed", "violations", "warnings".'
        )
