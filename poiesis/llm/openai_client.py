"""OpenAI LLM client implementation."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from poiesis.llm.base import LLMClient


class OpenAIClient(LLMClient):
    """LLM client backed by the OpenAI Chat Completions API."""

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.8,
        max_tokens: int = 4000,
        api_key: str | None = None,
    ) -> None:
        """Initialise the OpenAI client.

        Args:
            model: OpenAI model identifier (e.g. ``"gpt-4o"``).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the completion.
            api_key: Optional API key; falls back to the ``OPENAI_API_KEY``
                environment variable when *None*.
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def _complete(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def _complete_json(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = response.choices[0].message.content or "{}"
        return self._extract_json(raw)
