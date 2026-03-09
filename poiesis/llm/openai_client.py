"""OpenAI LLM 客户端实现。"""

from __future__ import annotations

import os
from collections.abc import Iterator
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
        base_url: str | None = None,
        request_timeout: float | None = None,
    ) -> None:
        """Initialise the OpenAI client.

        Args:
            model: OpenAI model identifier (e.g. ``"gpt-4o"``).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the completion.
            api_key: Optional API key; falls back to the ``OPENAI_API_KEY``
                environment variable when *None*.
            base_url: Optional API base URL for OpenAI-compatible providers.
        """
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        timeout = request_timeout
        if timeout is None:
            try:
                timeout = float(os.environ.get("POIESIS_LLM_TIMEOUT_SEC", "180"))
            except ValueError:
                timeout = 180.0

        client_kwargs: dict[str, Any] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url
        if timeout and timeout > 0:
            client_kwargs["timeout"] = timeout
        self._client = OpenAI(**client_kwargs)

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
        message = response.choices[0].message
        content = message.content or ""
        if content:
            return content
        return getattr(message, "reasoning_content", None) or ""

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

        response = self._client.chat.completions.create(  # type: ignore[call-overload]
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = response.choices[0].message.content or "{}"
        return self._extract_json(raw)

    def _stream_complete(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            **kwargs,
        )

        for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            text = delta.content or getattr(delta, "reasoning_content", None)
            if text:
                yield text
