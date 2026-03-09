"""章节结构化提取枢纽。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from poiesis.application.contracts import ChangeSet
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.pipeline.extraction.types import ExtractedEntityType

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "extractor.txt"


class ExtractorHub:
    """负责把一次 LLM 提取结果整理为 ChangeSet。"""

    def __init__(self, prompt_path: str | None = None, language: str = "zh-CN") -> None:
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH
        self._language = language

    def extract(
        self,
        chapter_number: int,
        content: str,
        world: WorldModel,
        llm: LLMClient,
    ) -> ChangeSet:
        """统一输出 ChangeSet。"""
        template = self._load_template()
        prompt = template.format(
            chapter_number=chapter_number,
            content=content,
            world_context=world.world_context_summary(language=self._language),
        )
        raw = llm.complete_json(prompt, system=self._build_system_prompt())
        raw_staging_changes = [
            *self._extract_character_changes(raw, chapter_number),
            *self._extract_world_rule_changes(raw, chapter_number),
            *self._extract_timeline_changes(raw, chapter_number),
            *self._extract_foreshadowing_changes(raw, chapter_number),
            *self._extract_character_updates(raw, chapter_number),
        ]
        return ChangeSet(
            characters=[c for c in raw_staging_changes if c["entity_type"] == ExtractedEntityType.CHARACTER],
            world_rules=[c for c in raw_staging_changes if c["entity_type"] == ExtractedEntityType.WORLD_RULE],
            timeline_events=[c for c in raw_staging_changes if c["entity_type"] == ExtractedEntityType.TIMELINE_EVENT],
            foreshadowing_updates=[
                c for c in raw_staging_changes if c["entity_type"] == ExtractedEntityType.FORESHADOWING
            ],
            uncertain_claims=self._extract_uncertain_claims(raw, chapter_number),
            raw_staging_changes=raw_staging_changes,
        )

    def _extract_character_changes(
        self, raw: dict[str, Any], chapter_number: int
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for char in raw.get("new_characters", []):
            name = char.get("name", "")
            if not name:
                continue
            changes.append(
                {
                    "change_type": "upsert",
                    "entity_type": ExtractedEntityType.CHARACTER,
                    "entity_key": name,
                    "proposed_data": char,
                    "source_chapter": chapter_number,
                }
            )
        return changes

    def _extract_world_rule_changes(
        self, raw: dict[str, Any], chapter_number: int
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for rule in raw.get("new_world_rules", []):
            key = rule.get("rule_key", "")
            if not key:
                continue
            changes.append(
                {
                    "change_type": "upsert",
                    "entity_type": ExtractedEntityType.WORLD_RULE,
                    "entity_key": key,
                    "proposed_data": rule,
                    "source_chapter": chapter_number,
                }
            )
        return changes

    def _extract_timeline_changes(
        self, raw: dict[str, Any], chapter_number: int
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for event in raw.get("timeline_events", []):
            key = event.get("event_key", "")
            if not key:
                continue
            changes.append(
                {
                    "change_type": "upsert",
                    "entity_type": ExtractedEntityType.TIMELINE_EVENT,
                    "entity_key": key,
                    "proposed_data": event,
                    "source_chapter": chapter_number,
                }
            )
        return changes

    def _extract_foreshadowing_changes(
        self, raw: dict[str, Any], chapter_number: int
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for hint in raw.get("foreshadowing", []):
            key = hint.get("hint_key", "")
            if not key:
                continue
            changes.append(
                {
                    "change_type": "upsert",
                    "entity_type": ExtractedEntityType.FORESHADOWING,
                    "entity_key": key,
                    "proposed_data": hint,
                    "source_chapter": chapter_number,
                }
            )
        return changes

    def _extract_character_updates(
        self, raw: dict[str, Any], chapter_number: int
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for update in raw.get("character_updates", []):
            name = update.get("name", "")
            if not name:
                continue
            changes.append(
                {
                    "change_type": "update",
                    "entity_type": ExtractedEntityType.CHARACTER,
                    "entity_key": name,
                    "proposed_data": update,
                    "source_chapter": chapter_number,
                }
            )
        return changes

    def _extract_uncertain_claims(
        self, raw: dict[str, Any], chapter_number: int
    ) -> list[dict[str, Any]]:
        """显式保留不确定事实，为后续审核流和 LoopManager 预留入口。"""
        claims = raw.get("uncertain_claims", [])
        return [{"chapter_number": chapter_number, "claim": item} for item in claims]

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
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Extract new facts from chapter {chapter_number}.\n"
            "Content:\n{content}\nWorld:\n{world_context}\n"
            "Return JSON with new_characters, new_world_rules, timeline_events, "
            "foreshadowing, character_updates, uncertain_claims."
        )
