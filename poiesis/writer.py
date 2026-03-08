"""章节写作器，根据结构化规划生成叙事散文。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from poiesis.llm.base import LLMClient
from poiesis.vector_store.store import VectorStore
from poiesis.world import WorldModel

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "writer.txt"


class ChapterWriter:
    """Generates chapter prose content guided by a structured plan."""

    def __init__(
        self,
        vector_store: VectorStore,
        target_word_count: int = 3000,
        prompt_path: str | None = None,
        language: str = "zh-CN",
        style_prompt: str = "",
        naming_policy: str = "localized_zh",
    ) -> None:
        """Initialise the writer.

        Args:
            vector_store: Populated :class:`~poiesis.vector_store.store.VectorStore`.
            target_word_count: Approximate desired chapter length in words.
            prompt_path: Override path to the writer prompt template.
        """
        self._vs = vector_store
        self._target_word_count = target_word_count
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
        self._language = language
        self._style_prompt = style_prompt.strip()
        self._naming_policy = naming_policy

    def write(
        self,
        chapter_number: int,
        plan: dict[str, Any],
        world: WorldModel,
        llm: LLMClient,
        on_delta: Callable[[str], None] | None = None,
    ) -> str:
        """Generate chapter content.

        Args:
            chapter_number: Chapter number being written.
            plan: Structured plan produced by :class:`~poiesis.planner.ChapterPlanner`.
            world: Current :class:`~poiesis.world.WorldModel`.
            llm: :class:`~poiesis.llm.base.LLMClient` for prose generation.

        Returns:
            Full chapter text as a string.
        """
        world_context = world.world_context_summary(language=self._language)

        # 利用章节摘要作为查询，从向量存储中拉取相关背景信息
        query = plan.get("summary", f"第 {chapter_number} 章")
        relevant = self._vs.search(query, k=8)
        relevant_context = (
            "\n".join(f"- {r['text']}" for r in relevant) if relevant else "None."
        )

        import json as _json

        plan_text = _json.dumps(plan, indent=2)
        template = self._load_template()
        prompt = template.format(
            chapter_number=chapter_number,
            plan=plan_text,
            world_context=world_context,
            relevant_context=relevant_context,
            target_word_count=self._target_word_count,
        )

        system = self._build_system_prompt()
        if on_delta is None:
            return llm.complete(prompt, system=system)

        chunks: list[str] = []
        for delta in llm.stream_complete(prompt, system=system):
            if not delta:
                continue
            chunks.append(delta)
            on_delta(delta)
        return "".join(chunks)

    def _build_system_prompt(self) -> str:
        language_hint = (
            "请使用简体中文创作。"
            if self._language.lower().startswith("zh")
            else "Use fluent English prose."
        )
        naming_hint = (
            "专有名词默认采用中文化表达（可音译或意译），避免大段英文名词堆叠。"
            if self._naming_policy == "localized_zh"
            else "Proper nouns may keep their original form when context requires."
        )
        style_hint = self._style_prompt or "文风要求：叙事连贯，情绪与节奏稳定。"
        return (
            "你是一位长篇小说作者，需要严格遵循章节计划和世界规则完成正文。"
            f"{language_hint}{naming_hint}{style_hint}"
            "只输出章节正文，不要输出解释或标注。"
        )

    def _load_template(self) -> str:
        """Load the writer prompt template from disk."""
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Write chapter {chapter_number}.\nPlan:\n{plan}\n"
            "World:\n{world_context}\nContext:\n{relevant_context}\n"
            "Target {target_word_count} words."
        )
