"""Chapter writer that generates narrative prose guided by a plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

    def write(
        self,
        chapter_number: int,
        plan: dict[str, Any],
        world: WorldModel,
        llm: LLMClient,
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
        world_context = world.world_context_summary()

        # Pull relevant context from vector store using the plan summary
        query = plan.get("summary", f"chapter {chapter_number}")
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

        system = (
            "You are a literary author writing a chapter of an ongoing novel. "
            "Write vivid, engaging prose that honours the plan and world rules exactly."
        )
        return llm.complete(prompt, system=system)

    def _load_template(self) -> str:
        """Load the writer prompt template from disk."""
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Write chapter {chapter_number}.\nPlan:\n{plan}\n"
            "World:\n{world_context}\nContext:\n{relevant_context}\n"
            "Target {target_word_count} words."
        )
