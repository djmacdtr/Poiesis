"""LLM 客户端抽象基类。"""

from __future__ import annotations

import ast
import json
import re
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
        text = text.strip()
        candidates = [text]

        # 尝试从 Markdown 代码块中提取 JSON。
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if match:
            candidates.append(match.group(1).strip())

        balanced = LLMClient._find_first_balanced_json_block(text)
        if balanced:
            candidates.append(balanced)

        seen: set[str] = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            parsed = LLMClient._parse_json_candidate(candidate)
            if isinstance(parsed, dict):
                return parsed

        raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")

    @staticmethod
    def _parse_json_candidate(candidate: str) -> dict[str, Any] | None:
        """尝试用多种容错策略解析候选 JSON 文本。"""
        candidate = candidate.strip()
        if not candidate:
            return None

        # 先走标准 JSON。
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        # 再尝试只解析前缀中的第一个合法 JSON 对象，容忍后面附带解释文本。
        decoder = json.JSONDecoder()
        for marker in ("{", "["):
            start = candidate.find(marker)
            if start == -1:
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[start:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

        # 处理常见的轻微格式问题：尾逗号、全角标点、Python/JS 字面量漂移。
        repaired = (
            candidate.replace("“", '"')
            .replace("”", '"')
            .replace("’", "'")
            .replace("‘", "'")
            .replace("：", ":")
            .replace("\u00a0", " ")
        )
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        repaired = re.sub(r"\bTrue\b", "true", repaired)
        repaired = re.sub(r"\bFalse\b", "false", repaired)
        repaired = re.sub(r"\bNone\b", "null", repaired)
        repaired = re.sub(r"\bundefined\b", "null", repaired)
        try:
            parsed = json.loads(repaired)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        # 最后容忍 Python dict 风格输出，例如单引号、尾逗号。
        python_like = re.sub(r"\btrue\b", "True", repaired)
        python_like = re.sub(r"\bfalse\b", "False", python_like)
        python_like = re.sub(r"\bnull\b", "None", python_like)
        try:
            parsed = ast.literal_eval(python_like)
            return parsed if isinstance(parsed, dict) else None
        except (SyntaxError, ValueError):
            return None

    @staticmethod
    def _find_first_balanced_json_block(text: str) -> str | None:
        """从任意文本中提取第一个括号平衡的 JSON 对象块。"""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None
