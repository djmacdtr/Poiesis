"""基于 LLM 的语义一致性校验器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from poiesis.application.contracts import VerifierIssue
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "verifier.txt"


class LLMSemanticVerifier:
    """负责现有基于 LLM 的语义一致性检查。"""

    def __init__(self, prompt_path: str | None = None, language: str = "zh-CN") -> None:
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
        self._language = language

    def verify(
        self,
        chapter_number: int,
        content: str,
        plan: dict[str, Any],
        world: WorldModel,
        proposed_changes: list[dict[str, Any]],
        llm: LLMClient,
        new_rule_budget: int,
    ) -> list[VerifierIssue]:
        """调用 LLM 做高阶语义审校，并统一转成结构化 issue。"""
        prompt = self._load_template().format(
            chapter_number=chapter_number,
            content=content,
            plan=json.dumps(plan, indent=2),
            world_context=world.world_context_summary(language=self._language),
            proposed_changes=json.dumps(proposed_changes, indent=2),
            new_rule_budget=new_rule_budget,
        )
        raw = llm.complete_json(prompt, system=self._build_system_prompt())
        issues: list[VerifierIssue] = []
        for violation in raw.get("violations", []):
            issues.append(
                VerifierIssue(
                    severity="fatal",
                    type="semantic",
                    reason=str(violation),
                    repair_hint="修正与世界设定、角色动机或章节规划冲突的叙述。",
                )
            )
        for warning in raw.get("warnings", []):
            issues.append(
                VerifierIssue(
                    severity="warning",
                    type="semantic",
                    reason=str(warning),
                    repair_hint="评估是否需要在重写轮次中处理该风险。",
                )
            )
        return issues

    def _build_system_prompt(self) -> str:
        """保留独立方法，兼容旧测试对提示词的直接断言。"""
        language_hint = (
            "JSON 中的 violations/warnings 优先使用简体中文。"
            if self._language.lower().startswith("zh")
            else "Return violations/warnings in English."
        )
        return (
            f"你是严格的连贯性审校员，必须识别硬性冲突与设定违规。{language_hint}只返回合法 JSON。"
        )

    def _load_template(self) -> str:
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Verify chapter {chapter_number}.\nContent:\n{content}\n"
            "Plan:\n{plan}\nWorld:\n{world_context}\n"
            "Proposed changes:\n{proposed_changes}\n"
            "New rule budget: {new_rule_budget}\n"
            'Return JSON with "passed", "violations", "warnings".'
        )
