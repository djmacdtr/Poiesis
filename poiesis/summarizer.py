"""章节摘要器，生成可归档的章节摘要。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from poiesis.llm.base import LLMClient
from poiesis.world import WorldModel

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "summarizer.txt"


class ChapterSummarizer:
    """Summarizes a completed chapter for inclusion in the world archive."""

    def __init__(
        self,
        prompt_path: str | None = None,
        language: str = "zh-CN",
        style_prompt: str = "",
    ) -> None:
        """Initialise the summarizer.

        Args:
            prompt_path: Override path to the summarizer prompt template.
        """
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
        self._language = language
        self._style_prompt = style_prompt.strip()

    def summarize(
        self,
        chapter_number: int,
        content: str,
        plan: dict[str, Any],
        world: WorldModel,
        llm: LLMClient,
    ) -> dict[str, Any]:
        """Summarize a chapter for the world archive.

        Args:
            chapter_number: Chapter number being summarized.
            content: Full chapter prose.
            plan: Structured plan used to generate the chapter.
            world: Current :class:`~poiesis.world.WorldModel`.
            llm: :class:`~poiesis.llm.base.LLMClient` for summarization.

        Returns:
            Summary dict with keys: ``summary``, ``key_events``,
            ``characters_featured``, ``new_facts_introduced``.
        """
        template = self._load_template()
        prompt = template.format(
            chapter_number=chapter_number,
            content=content,
        )

        system = self._build_system_prompt()
        raw = llm.complete_json(prompt, system=system)

        raw.setdefault("summary", "")
        raw.setdefault("key_events", [])
        raw.setdefault("characters_featured", [])
        raw.setdefault("new_facts_introduced", [])
        return raw

    def _build_system_prompt(self) -> str:
        language_hint = "请使用简体中文输出摘要信息。" if self._language.lower().startswith("zh") else "Use English for summary values."
        style_hint = self._style_prompt or "摘要应客观、简洁、可检索。"
        return (
            "你是小说档案管理员，负责生成可入库的章节摘要。"
            f"{language_hint}{style_hint}只返回合法 JSON。"
        )

    def _load_template(self) -> str:
        """Load the summarizer prompt template from disk."""
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Summarize chapter {chapter_number}.\nContent:\n{content}\n"
            'Return JSON with "summary", "key_events", "characters_featured", '
            '"new_facts_introduced".'
        )
