"""Anthropic LLM client implementation."""

from __future__ import annotations

from typing import Any

import anthropic

from poiesis.llm.base import LLMClient


class AnthropicClient(LLMClient):
    """LLM client backed by the Anthropic Messages API."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.8,
        max_tokens: int = 4000,
        api_key: str | None = None,
    ) -> None:
        """Initialise the Anthropic client.

        Args:
            model: Anthropic model identifier.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the completion.
            api_key: Optional API key; falls back to the
                ``ANTHROPIC_API_KEY`` environment variable when *None*.
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def _complete(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            create_kwargs["system"] = system
        create_kwargs.update(kwargs)

        response = self._client.messages.create(**create_kwargs)
        block = response.content[0]
        return block.text if hasattr(block, "text") else ""

    def _complete_json(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        json_hint = "\n\nRespond with ONLY valid JSON, no other text."
        full_prompt = prompt + json_hint

        raw = self._complete(full_prompt, system=system, **kwargs)
        return self._extract_json(raw)
