"""Chapter editor that rewrites content to fix consistency violations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from poiesis.llm.base import LLMClient
from poiesis.world import WorldModel

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "editor.txt"


class ChapterEditor:
    """Rewrites chapter sections that contain consistency violations."""

    def __init__(self, prompt_path: str | None = None) -> None:
        """Initialise the editor.

        Args:
            prompt_path: Override path to the editor prompt template.
        """
        self._prompt_path = Path(prompt_path) if prompt_path else _PROMPT_PATH

    def edit(
        self,
        chapter_number: int,
        content: str,
        violations: list[str],
        plan: dict[str, Any],
        world: WorldModel,
        llm: LLMClient,
    ) -> str:
        """Rewrite a chapter to fix listed violations.

        Args:
            chapter_number: Chapter number being edited.
            content: Original chapter prose with violations.
            violations: List of violation descriptions to fix.
            plan: Structured plan the chapter must still honour.
            world: Current :class:`~poiesis.world.WorldModel`.
            llm: :class:`~poiesis.llm.base.LLMClient` for rewriting.

        Returns:
            Corrected chapter text.
        """
        world_context = world.world_context_summary()
        violations_text = "\n".join(f"- {v}" for v in violations)
        plan_text = json.dumps(plan, indent=2)

        template = self._load_template()
        prompt = template.format(
            chapter_number=chapter_number,
            content=content,
            violations=violations_text,
            plan=plan_text,
            world_context=world_context,
        )

        system = (
            "You are a surgical editor. Fix only what is broken. "
            "Return the complete corrected chapter with no meta-commentary."
        )
        return llm.complete(prompt, system=system)

    def _load_template(self) -> str:
        """Load the editor prompt template from disk."""
        if self._prompt_path.exists():
            return self._prompt_path.read_text(encoding="utf-8")
        return (
            "Fix violations in chapter {chapter_number}.\n"
            "Original:\n{content}\nViolations:\n{violations}\n"
            "Plan:\n{plan}\nWorld:\n{world_context}\n"
            "Return the complete corrected chapter."
        )
