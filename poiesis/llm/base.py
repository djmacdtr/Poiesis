"""LLM 客户端抽象基类。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential


class LLMClient(ABC):
    """Abstract LLM client with built-in retry logic."""

    def __init__(self, model: str, temperature: float = 0.8, max_tokens: int = 4000) -> None:
        """Initialise the LLM client.

        Args:
            model: Model identifier string.
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum tokens to generate.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a text completion.

        Args:
            prompt: User-facing prompt text.
            system: Optional system message.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Generated text response.
        """
        return self._complete(prompt, system=system, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a JSON completion.

        Args:
            prompt: User-facing prompt text.
            system: Optional system message.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Parsed JSON response as a dictionary.
        """
        return self._complete_json(prompt, system=system, **kwargs)

    def stream_complete(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream text completion chunks as they are generated."""
        return self._stream_complete(prompt, system=system, **kwargs)

    @abstractmethod
    def _complete(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Provider-specific text completion implementation."""
        ...

    @abstractmethod
    def _complete_json(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Provider-specific JSON completion implementation."""
        ...

    @abstractmethod
    def _stream_complete(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Provider-specific streaming completion implementation."""
        ...

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract a JSON object from arbitrary text.

        Tries direct parsing first, then attempts to find a JSON block.
        """
        # 先尝试直接解析 JSON 字符串
        text = text.strip()
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

        # 尝试从 Markdown 代码块中提取 JSON
        import re

        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

        # 最后手段：查找文本中第一个完整的 { ... } 块
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")
