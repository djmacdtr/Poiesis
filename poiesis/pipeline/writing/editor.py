"""章节编辑器，针对一致性违规对内容进行精准重写。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "editor.txt"


class ChapterEditor:
    """Rewrites chapter sections that contain consistency violations."""

    def __init__(
        self,
        prompt_path: str | None = None,
        language: str = "zh-CN",
        style_prompt: str = "",
        naming_policy: str = "localized_zh",
    ) -> None:
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
        self._language = language
        self._style_prompt = style_prompt.strip()
        self._naming_policy = naming_policy

    def edit(
        self,
        chapter_number: int,
        content: str,
        violations: list[str],
        plan: dict[str, Any],
        world: WorldModel,
        llm: LLMClient,
    ) -> str:
        prompt = self._load_template().format(
            chapter_number=chapter_number,
            content=content,
            violations="\n".join(f"- {v}" for v in violations),
            plan=json.dumps(plan, indent=2),
            world_context=world.world_context_summary(language=self._language),
        )
        return llm.complete(prompt, system=self._build_system_prompt())

    def _build_system_prompt(self) -> str:
        language_hint = (
            "请使用简体中文输出修订结果。"
            if self._language.lower().startswith("zh")
            else "Return edited prose in English."
        )
        naming_hint = (
            "专有名词优先中文化处理。"
            if self._naming_policy == "localized_zh"
            else "Keep proper nouns consistent with the draft."
        )
        style_hint = self._style_prompt or "保持原章叙事风格，不做无关改写。"
        return (
            "你是严谨的小说编辑，只修复违规内容，不改变有效段落。"
            f"{language_hint}{naming_hint}{style_hint}"
            "返回完整章节正文，不要附加说明。"
        )

    def _load_template(self) -> str:
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Fix violations in chapter {chapter_number}.\n"
            "Original:\n{content}\nViolations:\n{violations}\n"
            "Plan:\n{plan}\nWorld:\n{world_context}\n"
            "Return the complete corrected chapter."
        )
