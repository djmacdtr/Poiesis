"""Minimal live LLM probe test.

This test intentionally bypasses RunLoop/Writer/Planner and calls the provider
endpoint with only required parameters.

Run explicitly when needed:
    POIESIS_RUN_LIVE_LLM_TEST=1 pytest -q -s tests/test_llm_minimal_live.py
"""

from __future__ import annotations

import os
import time

import pytest
from openai import OpenAI


def _enabled() -> bool:
    return os.environ.get("POIESIS_RUN_LIVE_LLM_TEST") == "1"


@pytest.mark.skipif(not _enabled(), reason="Set POIESIS_RUN_LIVE_LLM_TEST=1 to run live probe")
def test_minimal_siliconflow_live_generation_around_100_chars() -> None:
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        pytest.skip("SILICONFLOW_API_KEY not set")

    model = os.environ.get("POIESIS_LIVE_MODEL", "Qwen/Qwen3.5-397B-A17B")
    base_url = os.environ.get("POIESIS_LIVE_BASE_URL", "https://api.siliconflow.cn/v1")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)

    prompt = "请用中文写一段约100字的奇幻场景描写，只输出正文。"

    start = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=180,
        temperature=0.7,
    )
    elapsed = time.time() - start

    text = (resp.choices[0].message.content or "").strip()

    # Print probe details for quick diagnosis in -s mode.
    print(f"MODEL={model}")
    print(f"ELAPSED_SEC={elapsed:.2f}")
    print(f"TEXT_LEN={len(text)}")
    print("TEXT_BEGIN")
    print(text)
    print("TEXT_END")

    assert text
    assert len(text) >= 60
