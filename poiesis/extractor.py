"""事实提取器，从生成的章节中解析新的世界事实。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from poiesis.llm.base import LLMClient
from poiesis.world import WorldModel

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extractor.txt"


class FactExtractor:
    """Extracts new canonical facts from chapter text for staging."""

    def __init__(
        self,
        prompt_path: str | None = None,
        language: str = "zh-CN",
    ) -> None:
        """Initialise the extractor.

        Args:
            prompt_path: Override path to the extractor prompt template.
        """
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
        self._language = language

    def extract(
        self,
        chapter_number: int,
        content: str,
        world: WorldModel,
        llm: LLMClient,
    ) -> list[dict[str, Any]]:
        """Extract new facts from chapter content and return as staging changes.

        Args:
            chapter_number: Chapter that was just written.
            content: Full chapter prose.
            world: Current :class:`~poiesis.world.WorldModel`.
            llm: :class:`~poiesis.llm.base.LLMClient` for extraction.

        Returns:
            List of staging-change dicts, each with keys:
            ``change_type``, ``entity_type``, ``entity_key``,
            ``proposed_data``, ``source_chapter``.
        """
        world_context = world.world_context_summary(language=self._language)
        template = self._load_template()
        prompt = template.format(
            chapter_number=chapter_number,
            content=content,
            world_context=world_context,
        )

        system = self._build_system_prompt()
        raw = llm.complete_json(prompt, system=system)

        staging: list[dict[str, Any]] = []

        # 处理新角色
        for char in raw.get("new_characters", []):
            name = char.get("name", "")
            if not name:
                continue
            staging.append(
                {
                    "change_type": "upsert",
                    "entity_type": "character",
                    "entity_key": name,
                    "proposed_data": char,
                    "source_chapter": chapter_number,
                }
            )

        # 处理新世界规则
        for rule in raw.get("new_world_rules", []):
            key = rule.get("rule_key", "")
            if not key:
                continue
            staging.append(
                {
                    "change_type": "upsert",
                    "entity_type": "world_rule",
                    "entity_key": key,
                    "proposed_data": rule,
                    "source_chapter": chapter_number,
                }
            )

        # 处理时间线事件
        for event in raw.get("timeline_events", []):
            key = event.get("event_key", "")
            if not key:
                continue
            staging.append(
                {
                    "change_type": "upsert",
                    "entity_type": "timeline_event",
                    "entity_key": key,
                    "proposed_data": event,
                    "source_chapter": chapter_number,
                }
            )

        # 处理伏笔提示
        for hint in raw.get("foreshadowing", []):
            key = hint.get("hint_key", "")
            if not key:
                continue
            staging.append(
                {
                    "change_type": "upsert",
                    "entity_type": "foreshadowing",
                    "entity_key": key,
                    "proposed_data": hint,
                    "source_chapter": chapter_number,
                }
            )

        # 处理角色属性更新
        for update in raw.get("character_updates", []):
            name = update.get("name", "")
            if not name:
                continue
            staging.append(
                {
                    "change_type": "update",
                    "entity_type": "character",
                    "entity_key": name,
                    "proposed_data": update,
                    "source_chapter": chapter_number,
                }
            )

        return staging

    def _build_system_prompt(self) -> str:
        language_hint = (
            "JSON 字段值优先使用简体中文。"
            if self._language.lower().startswith("zh")
            else "Use concise English for JSON values."
        )
        return (
            "你是世界设定分析师，只提取真正新增或变化的事实。"
            f"{language_hint}只返回合法 JSON，不要输出其他文本。"
        )

    def _load_template(self) -> str:
        """Load the extractor prompt template from disk."""
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Extract new facts from chapter {chapter_number}.\n"
            "Content:\n{content}\nWorld:\n{world_context}\n"
            "Return JSON with new_characters, new_world_rules, timeline_events, "
            "foreshadowing, character_updates."
        )
