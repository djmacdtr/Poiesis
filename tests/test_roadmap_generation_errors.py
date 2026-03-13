"""章节路线生成异常处理测试。"""

from __future__ import annotations

import pytest

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
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


def test_generate_next_arc_chapter_wraps_provider_500() -> None:
    """单章生成遇到模型服务 500 时，应返回中文友好错误。"""
    planner = RoadmapPlanner()
    llm = ErrorLLMClient("Error code: 500 - {'code': 50507, 'message': 'Request processing failed due to an unknown error.'}")
    story_arc = StoryArcPlan(
        arc_number=1,
        title="血月旧案开启",
        start_chapter=1,
        end_chapter=4,
    )

    with pytest.raises(ValueError, match="单章生成失败：模型服务暂时异常，请稍后重试。"):
        planner.generate_next_arc_chapter(
            intent=_sample_intent(),
            variant=_sample_variant(),
            world=_sample_world(),
            characters=_sample_characters(),
            llm=llm,
            story_arc=story_arc,
        )


def test_regenerate_last_arc_chapter_wraps_provider_500() -> None:
    """单章重生成遇到模型服务 500 时，应返回中文友好错误。"""
    planner = RoadmapPlanner()
    llm = ErrorLLMClient("Error code: 500 - {'code': 50507, 'message': 'Request processing failed due to an unknown error.'}")
    story_arc = StoryArcPlan(
        arc_number=1,
        title="血月旧案开启",
        start_chapter=1,
        end_chapter=4,
    )

    with pytest.raises(ValueError, match="单章重生成失败：模型服务暂时异常，请稍后重试。"):
        planner.regenerate_last_arc_chapter(
            intent=_sample_intent(),
            variant=_sample_variant(),
            world=_sample_world(),
            characters=_sample_characters(),
            llm=llm,
            story_arc=story_arc,
            chapter_number=1,
            existing_roadmap=[
                planner.normalize_single_roadmap_payload(
                    {
                        "chapter": {
                            "chapter_number": 1,
                            "title": "旧案初现",
                            "story_stage": "血月旧案开启",
                            "timeline_anchor": "初夜",
                            "goal": "卷入旧案",
                            "core_conflict": "线索逼近",
                            "turning_point": "残谱异动",
                            "story_progress": "第一次接触旧案",
                            "character_progress": ["林寒被迫入局"],
                            "relationship_progress": ["与苏璃建立初步信任"],
                            "new_reveals": ["残谱并未失传"],
                            "status_shift": ["主角不再只是旁观者"],
                            "planned_loops": [
                                {
                                    "title": "残谱异动",
                                    "summary": "残谱在主角面前第一次异动，提示旧案并未结束。",
                                    "status": "open",
                                    "due_end_chapter": 3,
                                }
                            ],
                            "chapter_function": "开局",
                            "anti_repeat_signature": "卷入旧案",
                            "closure_function": "抛出钩子",
                        }
                    },
                    fallback_chapter_number=1,
                )
            ],
        )


def test_rebuild_continuity_state_tracks_tasks_and_relationships() -> None:
    """连续性工作态应根据章节草稿回填任务、事件、关系和世界更新。"""
    planner = RoadmapPlanner()
    roadmap = planner.normalize_roadmap_payload(
        [
            {
                "chapter_number": 1,
                "title": "裂碑夜雨",
                "story_stage": "第一幕",
                "timeline_anchor": "入秋初夜",
                "depends_on_chapters": [],
                "goal": "卷入主线",
                "core_conflict": "黑市逼近",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次确认旧案并非巧合",
                "key_events": ["主角第一次看见残谱异动"],
                "chapter_tasks": [
                    {
                        "task_id": "trace-blood-moon",
                        "summary": "追查血月门与父母旧案的联系",
                        "status": "new",
                        "related_characters": ["林寒"],
                        "due_end_chapter": 3,
                    }
                ],
                "relationship_beats": [
                    {"source_character": "林寒", "target_character": "苏璃", "summary": "双方建立初步互信"}
                ],
                "world_updates": ["江湖黑市重新围绕残谱活跃"],
                "planned_loops": [
                    {
                        "loop_id": "loop-1",
                        "title": "残谱异动",
                        "summary": "残谱第一次异动，提示旧案将持续升级。",
                        "status": "open",
                        "due_end_chapter": 3,
                    }
                ],
                "chapter_function": "开局",
                "anti_repeat_signature": "第一幕:卷入主线",
                "closure_function": "抛出下一章钩子",
            },
            {
                "chapter_number": 2,
                "title": "渡口追查",
                "story_stage": "第一幕",
                "timeline_anchor": "入秋次日清晨",
                "depends_on_chapters": [1],
                "goal": "推进追查",
                "core_conflict": "线索转移",
                "turning_point": "发现账册缺页",
                "story_progress": "旧案从怀疑升级为可验证线索",
                "key_events": ["主角在渡口发现账册缺页"],
                "chapter_tasks": [
                    {
                        "task_id": "trace-blood-moon",
                        "summary": "追查血月门与父母旧案的联系",
                        "status": "in_progress",
                        "related_characters": ["林寒", "苏璃"],
                        "due_end_chapter": 3,
                    }
                ],
                "relationship_beats": [
                    {"source_character": "林寒", "target_character": "苏璃", "summary": "双方开始并肩调查"}
                ],
                "world_updates": ["裂碑渡成为黑市与门派争夺焦点"],
                "planned_loops": [
                    {
                        "loop_id": "loop-1",
                        "title": "残谱异动",
                        "summary": "残谱异动继续升级，主角确认它与血月门旧案相关。",
                        "status": "progressed",
                        "due_end_chapter": 3,
                    }
                ],
                "chapter_function": "推进",
                "anti_repeat_signature": "第一幕:推进追查",
                "closure_function": "继续追查",
            },
        ]
    )

    continuity = planner.rebuild_continuity_state(roadmap)

    assert continuity.last_planned_chapter == 2
    assert continuity.open_tasks[0].task_id == "trace-blood-moon"
    assert continuity.active_loops[0].loop_id == "loop-1"
    assert continuity.active_loops[0].due_end_chapter == 3
    assert continuity.relationship_states[0].latest_summary == "双方开始并肩调查"
    assert continuity.world_updates[-1] == "裂碑渡成为黑市与门派争夺焦点"


def test_verify_roadmap_marks_missing_structured_fields_as_fatal() -> None:
    """缺少 key_events、任务/伏笔推进和合法承接时，应被标记为 fatal。"""
    planner = RoadmapPlanner()
    issues = planner.verify_roadmap(
        [StoryArcPlan(arc_number=1, title="第一幕", start_chapter=1, end_chapter=2)],
        [
            ChapterRoadmapItem(
                chapter_number=1,
                title="裂碑夜雨",
                story_stage="第一幕",
                timeline_anchor="入秋初夜",
                depends_on_chapters=[],
                goal="卷入主线",
                core_conflict="黑市逼近",
                turning_point="残谱异动",
                story_progress="主角第一次确认旧案并非巧合",
                key_events=[],
                chapter_tasks=[],
                relationship_beats=[],
                character_progress=[],
                relationship_progress=[],
                new_reveals=[],
                world_updates=[],
                status_shift=[],
                chapter_function="开局",
                anti_repeat_signature="第一幕:卷入主线",
                planned_loops=[],
                closure_function="抛出下一章钩子",
            ),
            ChapterRoadmapItem(
                chapter_number=2,
                title="再查旧案",
                story_stage="第一幕",
                timeline_anchor="入秋初夜",
                depends_on_chapters=[],
                goal="继续追查",
                core_conflict="主角不敢惊动师门",
                turning_point="账册缺页",
                story_progress="主角第二次确认旧案并非巧合",
                key_events=[],
                chapter_tasks=[],
                relationship_beats=[],
                character_progress=[],
                relationship_progress=[],
                new_reveals=[],
                world_updates=[],
                status_shift=[],
                chapter_function="调查",
                anti_repeat_signature="第一幕:继续追查",
                planned_loops=[],
                closure_function="继续追查",
            ),
        ],
    )

    issue_types = {item.type for item in issues if item.severity == "fatal"}
    assert "missing_key_events" in issue_types
    assert "missing_task_or_loop_progress" in issue_types
    assert "missing_previous_dependency" in issue_types
    assert "timeline_not_advanced" in issue_types


def test_normalize_single_roadmap_payload_requires_loop_due_end_for_new_generation() -> None:
    """单章生成路径下，伏笔缺少最迟兑现章时应直接报错，而不是静默补默认值。"""
    planner = RoadmapPlanner()

    with pytest.raises(ValueError, match="planned_loops_due_end_required"):
        planner.normalize_single_roadmap_payload(
            {
                "chapter": {
                    "chapter_number": 1,
                    "title": "残谱裂痕",
                    "story_stage": "第一幕",
                    "timeline_anchor": "入秋初夜",
                    "goal": "卷入旧案",
                    "core_conflict": "主角被迫入局",
                    "turning_point": "残谱异动",
                    "story_progress": "主角第一次确认旧案与自己有关",
                    "key_events": ["主角第一次看见残谱异动"],
                    "chapter_tasks": [],
                    "relationship_beats": [],
                    "character_progress": [],
                    "relationship_progress": [],
                    "new_reveals": [],
                    "world_updates": [],
                    "status_shift": [],
                    "chapter_function": "开局",
                    "anti_repeat_signature": "第一幕:卷入旧案",
                    "planned_loops": [{"loop_id": "loop-1", "title": "残谱异动", "summary": "残谱第一次异动。"}],
                    "closure_function": "抛出下一章钩子",
                }
            },
            fallback_chapter_number=1,
            strict_loop_constraints=True,
            fallback_stage_end_chapter=3,
            fallback_max_chapter=3,
        )


def test_verify_roadmap_marks_invalid_loop_window_as_fatal() -> None:
    """伏笔的兑现窗口不能缺失或反向，否则连续性校验应直接阻断锁定。"""
    planner = RoadmapPlanner()
    issues = planner.verify_roadmap(
        [StoryArcPlan(arc_number=1, title="第一幕", start_chapter=1, end_chapter=3)],
        [
            ChapterRoadmapItem(
                chapter_number=2,
                title="渡口惊讯",
                story_stage="第一幕",
                timeline_anchor="入秋次日清晨",
                depends_on_chapters=[1],
                goal="推进追查",
                core_conflict="线索被人抢先转移",
                turning_point="发现残谱缺页",
                story_progress="主角确认残谱与父母旧案直接相连",
                key_events=["渡口账册出现残谱缺页"],
                chapter_tasks=[],
                relationship_beats=[],
                character_progress=[],
                relationship_progress=[],
                new_reveals=[],
                world_updates=[],
                status_shift=[],
                chapter_function="推进",
                anti_repeat_signature="第一幕:推进追查",
                planned_loops=[
                    {
                        "loop_id": "loop-1",
                        "title": "残谱缺页",
                        "summary": "缺页账册暗示幕后势力已经提前布局。",
                        "status": "open",
                        "priority": 1,
                        "due_start_chapter": 4,
                        "due_end_chapter": 3,
                        "related_characters": ["林寒"],
                        "resolution_requirements": [],
                    }
                ],
                closure_function="继续追查",
            )
        ],
    )

    issue_types = {item.type for item in issues if item.severity == "fatal"}
    assert "loop_due_window_invalid" in issue_types
