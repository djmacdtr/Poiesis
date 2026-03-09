"""章节规划器，生成结构化 JSON 章节计划。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from poiesis.llm.base import LLMClient
from poiesis.vector_store.store import VectorStore
from poiesis.world import WorldModel

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.txt"


class ChapterPlanner:
    """Produces structured chapter plans using world context and LLM reasoning."""

    def __init__(
        self,
        vector_store: VectorStore,
        new_rule_budget: int = 5,
        prompt_path: str | None = None,
        language: str = "zh-CN",
        style_prompt: str = "",
        naming_policy: str = "localized_zh",
    ) -> None:
        """Initialise the planner.

        Args:
            vector_store: Populated :class:`~poiesis.vector_store.store.VectorStore`.
            new_rule_budget: Maximum new world facts allowed per chapter.
            prompt_path: Override path to the planner prompt template.
        """
        self._vs = vector_store
        self._new_rule_budget = new_rule_budget
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
        self._language = language
        self._style_prompt = style_prompt.strip()
        self._naming_policy = naming_policy

    def plan(
        self,
        chapter_number: int,
        world: WorldModel,
        previous_summaries: list[str],
        llm: LLMClient,
    ) -> dict[str, Any]:
        """Generate a structured chapter plan.

        Args:
            chapter_number: Chapter number being planned.
            world: Current :class:`~poiesis.world.WorldModel`.
            previous_summaries: List of narrative summaries for past chapters.
            llm: :class:`~poiesis.llm.base.LLMClient` to use for planning.

        Returns:
            Plan dictionary with keys: ``title``, ``summary``,
            ``key_events``, ``character_arcs``, ``new_facts_budget``,
            ``foreshadowing_hints``, ``tone``, ``opening_hook``.
        """
        world_context = world.world_context_summary(language=self._language)

        # 从向量存储中检索与当前章节相关的历史事实
        relevant = self._vs.search(f"第 {chapter_number} 章 叙事线", k=10)
        if relevant:
            world_context += "\n\n=== Relevant Past Facts ===\n"
            world_context += "\n".join(f"- {r['text']}" for r in relevant)

        summaries_text = (
            "\n\n".join(previous_summaries[-5:]) if previous_summaries else "No previous chapters."
        )

        template = self._load_template()
        prompt = template.format(
            chapter_number=chapter_number,
            world_context=world_context,
            previous_summaries=summaries_text,
            new_rule_budget=self._new_rule_budget,
        )

        system = self._build_system_prompt()
        raw_plan = llm.complete_json(prompt, system=system)

        # 为必要字段设置合理的默认值，防止 LLM 返回不完整的 JSON
        raw_plan.setdefault("title", f"第 {chapter_number} 章")
        raw_plan.setdefault("summary", "")
        raw_plan.setdefault("key_events", [])
        raw_plan.setdefault("character_arcs", {})
        raw_plan.setdefault("new_facts_budget", min(self._new_rule_budget, 3))
        raw_plan.setdefault("foreshadowing_hints", [])
        raw_plan.setdefault("tone", "克制而有张力")
        raw_plan.setdefault("opening_hook", "")

        return raw_plan

    def _build_system_prompt(self) -> str:
        language_hint = (
            "请以简体中文规划章节，JSON 字段值优先使用中文。"
            if self._language.lower().startswith("zh")
            else "Plan in English with concise JSON values."
        )
        naming_hint = (
            "人物名、地名等默认中文化。"
            if self._naming_policy == "localized_zh"
            else "Proper nouns may remain untranslated if needed."
        )
        style_hint = self._style_prompt or "文风要求：叙事统一，避免风格跳变。"
        return (
            "你是资深小说结构师。必须返回合法 JSON，且结构严格遵循模板。"
            f"{language_hint}{naming_hint}{style_hint}"
        )

    def _load_template(self) -> str:
        """Load the planner prompt template from disk."""
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Plan chapter {chapter_number}.\n"
            "World: {world_context}\n"
            "Summaries: {previous_summaries}\n"
            "New fact budget: {new_rule_budget}\n"
            'Return JSON with title, summary, key_events, character_arcs, '
            'new_facts_budget, foreshadowing_hints, tone, opening_hook.'
        )
