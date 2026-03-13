"""章节路线生成异常处理测试。"""

from __future__ import annotations

import pytest

from poiesis.application.blueprint_contracts import (
    CharacterBlueprint,
    ConceptVariant,
    CreationIntent,
    StoryArcPlan,
    WorldBlueprint,
)
from poiesis.llm.base import LLMClient
from poiesis.pipeline.planning.roadmap_planner import RoadmapPlanner


class ErrorLLMClient(LLMClient):
    """用于模拟模型服务异常的测试客户端。"""

    def __init__(self, message: str) -> None:
        super().__init__(model="error")
        self._message = message

    def _complete(self, prompt: str, system: str | None = None, **kwargs: object) -> str:  # noqa: ARG002
        raise RuntimeError(self._message)

    def _complete_json(self, prompt: str, system: str | None = None, **kwargs: object) -> dict[str, object]:  # noqa: ARG002
        raise RuntimeError(self._message)

    def _stream_complete(self, prompt: str, system: str | None = None, **kwargs: object):  # noqa: ANN202, ARG002
        yield ""


def _sample_intent() -> CreationIntent:
    return CreationIntent(genre="武侠", protagonist_prompt="少年卷入旧案", conflict_prompt="师门与旧案纠缠")


def _sample_variant() -> ConceptVariant:
    return ConceptVariant(
        variant_no=1,
        hook="残谱夜鸣",
        world_pitch="江湖暗潮涌动",
        main_arc_pitch="主角被卷入血月旧案",
        ending_pitch="主角付出代价守住江湖秩序",
    )


def _sample_world() -> WorldBlueprint:
    return WorldBlueprint(setting_summary="武侠江湖即将失衡。")


def _sample_characters() -> list[CharacterBlueprint]:
    return [
        CharacterBlueprint(name="林寒", role="主角"),
        CharacterBlueprint(name="苏璃", role="师妹"),
    ]


def test_generate_structured_roadmap_wraps_provider_500() -> None:
    """整书路线生成遇到模型服务 500 时，应返回中文友好错误。"""
    planner = RoadmapPlanner()
    llm = ErrorLLMClient("Error code: 500 - {'code': 50507, 'message': 'Request processing failed due to an unknown error.'}")

    with pytest.raises(ValueError, match="章节路线生成失败：模型服务暂时异常，请稍后重试。"):
        planner.generate_structured_roadmap(
            intent=_sample_intent(),
            variant=_sample_variant(),
            world=_sample_world(),
            characters=_sample_characters(),
            llm=llm,
            chapter_count=12,
        )


def test_regenerate_story_arc_wraps_provider_500() -> None:
    """阶段重生成遇到模型服务 500 时，应返回中文友好错误。"""
    planner = RoadmapPlanner()
    llm = ErrorLLMClient("Error code: 500 - {'code': 50507, 'message': 'Request processing failed due to an unknown error.'}")
    story_arc = StoryArcPlan(
        arc_number=1,
        title="血月旧案开启",
        start_chapter=1,
        end_chapter=4,
    )

    with pytest.raises(ValueError, match="阶段重生成失败：模型服务暂时异常，请稍后重试。"):
        planner.regenerate_story_arc(
            intent=_sample_intent(),
            variant=_sample_variant(),
            world=_sample_world(),
            characters=_sample_characters(),
            llm=llm,
            story_arc=story_arc,
        )
