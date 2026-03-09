"""中文提示词约束测试。"""

from __future__ import annotations

from poiesis.pipeline.extraction.extractor_hub import ExtractorHub
from poiesis.pipeline.planning.story_planner import StoryPlanner
from poiesis.pipeline.summary.summarizer import ChapterSummarizer
from poiesis.pipeline.verification.semantic_verifier import LLMSemanticVerifier
from poiesis.pipeline.writing.editor import ChapterEditor
from poiesis.pipeline.writing.writer import ChapterWriter


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
    planner = StoryPlanner(
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
    prompt = ExtractorHub(language="zh-CN")._build_system_prompt()
    assert "简体中文" in prompt
    assert "合法 JSON" in prompt


def test_verifier_system_prompt_prefers_chinese_issue_descriptions() -> None:
    prompt = LLMSemanticVerifier(language="zh-CN")._build_system_prompt()
    assert "简体中文" in prompt
    assert "合法 JSON" in prompt


def test_summarizer_system_prompt_prefers_chinese_summary_values() -> None:
    prompt = ChapterSummarizer(language="zh-CN")._build_system_prompt()
    assert "简体中文" in prompt
    assert "合法 JSON" in prompt
