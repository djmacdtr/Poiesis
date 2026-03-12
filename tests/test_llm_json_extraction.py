"""LLM JSON 提取容错测试。"""

from __future__ import annotations

from poiesis.llm.base import LLMClient


def test_extract_json_accepts_valid_prefix_with_trailing_text() -> None:
    """兼容供应商在合法 JSON 后附带解释文本的情况。"""
    raw = '{"chapters":[{"chapter_number":1,"title":"裂碑夜雨"}]}\n补充说明：以上为当前阶段章节。'
    parsed = LLMClient._extract_json(raw)
    assert parsed["chapters"][0]["title"] == "裂碑夜雨"


def test_extract_json_accepts_python_like_json() -> None:
    """兼容单引号、True/False、尾逗号等 Python 风格字典。"""
    raw = """```json
    {'chapters': [{'chapter_number': 1, 'title': '裂碑夜雨', 'published': True,}],}
    ```"""
    parsed = LLMClient._extract_json(raw)
    assert parsed["chapters"][0]["published"] is True
