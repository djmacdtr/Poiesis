"""章节级故事规划器。"""

from __future__ import annotations

from pathlib import Path

from poiesis.application.contracts import PlannerOutput
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.vector_store.store import VectorStore

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "planner.txt"


class StoryPlanner:
    """负责生成章节级故事推进计划。"""

    def __init__(
        self,
        vector_store: VectorStore,
        new_rule_budget: int = 5,
        prompt_path: str | None = None,
        language: str = "zh-CN",
        style_prompt: str = "",
        naming_policy: str = "localized_zh",
    ) -> None:
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
    ) -> PlannerOutput:
        """输出稳定的 PlannerOutput，而不是松散 dict。"""
        prompt = self._build_prompt(
            chapter_number=chapter_number,
            world=world,
            previous_summaries=previous_summaries,
        )
        raw_plan = llm.complete_json(prompt, system=self._build_system_prompt())
        raw_plan.setdefault("title", f"第 {chapter_number} 章")
        raw_plan.setdefault("summary", "")
        raw_plan.setdefault("chapter_goal", raw_plan.get("summary", ""))
        raw_plan.setdefault("key_events", [])
        raw_plan.setdefault("character_arcs", {})
        raw_plan.setdefault("new_facts_budget", min(self._new_rule_budget, 3))
        raw_plan.setdefault("foreshadowing_hints", [])
        raw_plan.setdefault("must_preserve", raw_plan.get("key_events", []))
        raw_plan.setdefault("must_progress_loops", raw_plan.get("foreshadowing_hints", []))
        raw_plan.setdefault("scene_stubs", [])
        raw_plan.setdefault("notes", [])
        raw_plan.setdefault("tone", "克制而有张力")
        raw_plan.setdefault("opening_hook", "")
        return PlannerOutput.model_validate({**raw_plan, "raw_payload": dict(raw_plan)})

    def _build_prompt(
        self,
        chapter_number: int,
        world: WorldModel,
        previous_summaries: list[str],
    ) -> str:
        """拆开 prompt 组装，便于后续插入 ScenePlanner 与 RetrievalComposer。"""
        template = self._load_template()
        return template.format(
            chapter_number=chapter_number,
            world_context=self._build_world_context(chapter_number, world),
            previous_summaries=self._build_summary_context(previous_summaries),
            new_rule_budget=self._new_rule_budget,
        )

    def _build_world_context(self, chapter_number: int, world: WorldModel) -> str:
        world_context = world.world_context_summary(language=self._language)
        relevant = self._build_retrieval_context(chapter_number)
        if relevant:
            world_context += "\n\n=== Relevant Past Facts ===\n"
            world_context += relevant
        return world_context

    def _build_summary_context(self, previous_summaries: list[str]) -> str:
        return "\n\n".join(previous_summaries[-5:]) if previous_summaries else "No previous chapters."

    def _build_retrieval_context(self, chapter_number: int) -> str:
        relevant = self._vs.search(f"第 {chapter_number} 章 叙事线", k=10)
        return "\n".join(f"- {item['text']}" for item in relevant) if relevant else ""

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
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Plan chapter {chapter_number}.\n"
            "World: {world_context}\n"
            "Summaries: {previous_summaries}\n"
            "New fact budget: {new_rule_budget}\n"
            'Return JSON with title, chapter_goal, scene_stubs, must_preserve, must_progress_loops, '
            'notes, summary, key_events, character_arcs, new_facts_budget, foreshadowing_hints, tone, opening_hook.'
        )
