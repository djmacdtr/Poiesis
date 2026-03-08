"""Language and style prompt guardrail tests."""

from __future__ import annotations

from poiesis.editor import ChapterEditor
from poiesis.extractor import FactExtractor
from poiesis.planner import ChapterPlanner
from poiesis.summarizer import ChapterSummarizer
from poiesis.verifier import ConsistencyVerifier
from poiesis.writer import ChapterWriter


class _DummyVectorStore:
    def search(self, query: str, k: int = 8):
        return []


def test_writer_system_prompt_prefers_chinese_and_localized_naming() -> None:
    writer = ChapterWriter(
        vector_store=_DummyVectorStore(),
        language="zh-CN",
        style_prompt="文风要求：情绪内敛，细节真实。",
        naming_policy="localized_zh",
    )

    prompt = writer._build_system_prompt()
    assert "简体中文" in prompt
    assert "中文化" in prompt
    assert "文风要求" in prompt


def test_planner_system_prompt_prefers_chinese_json_values() -> None:
    planner = ChapterPlanner(
        vector_store=_DummyVectorStore(),
        language="zh-CN",
        style_prompt="文风要求：叙事一致。",
        naming_policy="localized_zh",
    )

    prompt = planner._build_system_prompt()
    assert "简体中文" in prompt
    assert "合法 JSON" in prompt


def test_editor_system_prompt_prefers_chinese_output() -> None:
    editor = ChapterEditor(language="zh-CN", naming_policy="localized_zh")
    prompt = editor._build_system_prompt()
    assert "简体中文" in prompt
    assert "修复违规" in prompt


def test_extractor_system_prompt_prefers_chinese_json_values() -> None:
    extractor = FactExtractor(language="zh-CN")
    prompt = extractor._build_system_prompt()
    assert "简体中文" in prompt
    assert "合法 JSON" in prompt


def test_verifier_system_prompt_prefers_chinese_issue_descriptions() -> None:
    verifier = ConsistencyVerifier(language="zh-CN")
    prompt = verifier._build_system_prompt()
    assert "简体中文" in prompt
    assert "合法 JSON" in prompt


def test_summarizer_system_prompt_prefers_chinese_summary_values() -> None:
    summarizer = ChapterSummarizer(language="zh-CN")
    prompt = summarizer._build_system_prompt()
    assert "简体中文" in prompt
    assert "合法 JSON" in prompt
