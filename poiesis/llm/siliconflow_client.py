"""SiliconFlow LLM client implementation (OpenAI-compatible API)."""

from __future__ import annotations

import os

from poiesis.llm.openai_client import OpenAIClient

DEFAULT_SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"


class SiliconFlowClient(OpenAIClient):
    """LLM client backed by SiliconFlow's OpenAI-compatible API."""

    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-72B-Instruct",
        temperature: float = 0.8,
        max_tokens: int = 4000,
        api_key: str | None = None,
        base_url: str = DEFAULT_SILICONFLOW_BASE_URL,
    ) -> None:
        """Initialise the SiliconFlow client.

        Args:
            model: SiliconFlow model identifier.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the completion.
            api_key: Optional API key; falls back to ``SILICONFLOW_API_KEY``
                environment variable when *None*.
            base_url: API base URL for SiliconFlow's compatible endpoint.
        """
        resolved_key = api_key or os.environ.get("SILICONFLOW_API_KEY")

        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=resolved_key,
            base_url=base_url,
        )
