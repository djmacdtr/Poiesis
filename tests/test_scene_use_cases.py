"""Scene 聚合用例的回归测试。"""

from __future__ import annotations

from poiesis.application.scene_contracts import (
    ChangeSet,
    ChapterPlan,
    SceneDraft,
    ScenePlan,
    VerifierIssue,
)
from poiesis.application.use_cases import (
    GenerateChapterUseCase,
    RefreshChapterAggregateUseCase,
    SceneGenerationContext,
)
from poiesis.db.database import Database
from poiesis.pipeline.assembly.chapter_assembler import ChapterAssembler
from tests.conftest import MockLLMClient


class _StubChapterPlanner:
    """返回稳定章节规划，避免测试依赖真实规划链路。"""

    def plan(self, chapter_number, story_plan, world, previous_summaries, llm):  # noqa: ANN001
        return ChapterPlan(
            chapter_number=chapter_number,
            title=f"第 {chapter_number} 章",
            goal="推进主线",
            must_progress_loops=["loop-1"],
            source_plan={
                "scene_stubs": [
                    {
                        "title": "开场",
                        "goal": "引出冲突",
                        "conflict": "线索逼近",
                        "turning_point": "角色被迫表态",
                    }
                ]
            },
        )


class _StubScenePlanner:
    """固定把章节拆成一个 scene，便于定位聚合问题。"""

    def plan(self, chapter_plan: ChapterPlan) -> list[ScenePlan]:
        return [
            ScenePlan(
                chapter_number=chapter_plan.chapter_number,
                scene_number=1,
                title="开场",
                goal="引出冲突",
                conflict="线索逼近",
                turning_point="角色被迫表态",
                required_loops=["loop-1"],
            )
        ]


class _StubSceneWriter:
    """返回稳定正文，确保失败只来自聚合逻辑而不是写作层。"""

    def __init__(self, content: str = "场景正文") -> None:
        self._content = content

    def write(self, scene_plan, chapter_plan, world, llm):  # noqa: ANN001
        return SceneDraft(
            chapter_number=scene_plan.chapter_number,
            scene_number=scene_plan.scene_number,
            title=scene_plan.title,
            content=self._content,
            retrieval_context={},
        )


class _StubSceneExtractor:
    """提供最小变更集，并推进必需 loop。"""

    def extract(self, scene_plan, content, world, llm):  # noqa: ANN001
        return ChangeSet(
            raw_changes=[],
            loop_updates=[
                {
                    "loop_id": "loop-1",
                    "title": "主线悬念",
                    "action": "introduced",
                }
            ],
        )


class _AlwaysFatalVerifier:
    """无论输入如何都返回 fatal，模拟进入人工审阅。"""

    def verify(self, scene_plan, content, chapter_plan, world, changeset, llm):  # noqa: ANN001
        return [
            VerifierIssue(
                severity="fatal",
                type="semantic",
                reason="仍需人工审核",
                repair_hint="补充上下文",
                location="scene",
            )
        ]


class _PassingVerifier:
    """始终通过校验，用于验证补建后的 ready_to_publish 状态。"""

    def verify(self, scene_plan, content, chapter_plan, world, changeset, llm):  # noqa: ANN001
        return []


class _StubSceneEditor:
    """模拟重写但保留 fatal 结果，确保章节进入待审核。"""

    def rewrite(self, scene_plan, chapter_plan, content, issues, world, llm):  # noqa: ANN001
        return f"{content}\n重写意见：{'；'.join(issues)}"


class _StubSummarizer:
    """返回稳定摘要，避免测试触发真实 LLM。"""

    def summarize(self, chapter_number, content, plan, world, llm):  # noqa: ANN001
        return {
            "summary": f"第 {chapter_number} 章摘要",
            "key_events": ["场景聚合完成"],
            "characters_featured": [],
            "new_facts_introduced": [],
        }


def _make_context(tmp_db: Database, sample_world, verifier) -> SceneGenerationContext:  # noqa: ANN001
    llm = MockLLMClient()
    return SceneGenerationContext(
        db=tmp_db,
        world=sample_world,
        planner_llm=llm,
        writer_llm=llm,
        chapter_planner=_StubChapterPlanner(),
        scene_planner=_StubScenePlanner(),
        scene_writer=_StubSceneWriter(),
        scene_extractor=_StubSceneExtractor(),
        scene_verifier=verifier,
        scene_editor=_StubSceneEditor(),
        chapter_assembler=ChapterAssembler(),
        summarizer=_StubSummarizer(),
        book_id=1,
    )


def _seed_blueprint(tmp_db: Database) -> None:
    """为生成用例补齐最小蓝图前置条件。"""
    tmp_db.upsert_creation_intent(
        1,
        {
            "genre": "奇幻",
            "themes": ["成长"],
            "tone": "压抑",
            "protagonist_prompt": "主角背负秘密",
            "conflict_prompt": "主线冲突不断升级",
            "ending_preference": "高代价完成",
            "forbidden_elements": [],
            "length_preference": "12",
            "target_experience": "起伏跌宕",
        },
    )
    tmp_db.replace_concept_variants(
        1,
        [
            {
                "variant_no": 1,
                "hook": "候选方向 1",
                "world_pitch": "裂隙世界",
                "main_arc_pitch": "主线推进",
                "ending_pitch": "高代价完成",
                "differentiators": ["主线明确"],
                "selected": True,
            }
        ],
    )
    variant = tmp_db.list_concept_variants(1)[0]
    revision_id = tmp_db.create_blueprint_revision(
        1,
        revision_number=1,
        selected_variant_id=variant["id"],
        change_reason="初始化蓝图",
        change_summary="测试场景使用的最小蓝图",
        affected_range=[1, 12],
        world_blueprint={
            "setting_summary": "裂隙世界",
            "immutable_rules": [],
            "power_system": "",
            "factions": [],
            "taboo_rules": [],
        },
        character_blueprints=[],
        roadmap=[
            {
                "chapter_number": 1,
                "title": "第 1 章",
                "goal": "推进主线",
                "core_conflict": "线索逼近",
                "turning_point": "角色被迫表态",
                "character_progress": [],
                "planned_loops": [{"loop_id": "loop-1", "title": "主线悬念"}],
                "closure_function": "抛出钩子",
            }
        ],
        is_active=True,
    )
    tmp_db.upsert_book_blueprint_state(
        1,
        status="locked",
        current_step="locked",
        selected_variant_id=variant["id"],
        active_revision_id=revision_id,
        world_confirmed={"setting_summary": "裂隙世界", "immutable_rules": [], "power_system": "", "factions": [], "taboo_rules": []},
        character_confirmed=[],
        roadmap_confirmed=[
            {
                "chapter_number": 1,
                "title": "第 1 章",
                "goal": "推进主线",
                "core_conflict": "线索逼近",
                "turning_point": "角色被迫表态",
                "character_progress": [],
                "planned_loops": [{"loop_id": "loop-1", "title": "主线悬念"}],
                "closure_function": "抛出钩子",
            }
        ],
    )


def test_generate_chapter_creates_initial_trace_before_first_refresh(tmp_db: Database, sample_world) -> None:
    """首次 scene 聚合前应先创建章节 trace，避免 refresh 因空记录失败。"""
    _seed_blueprint(tmp_db)
    run_id = tmp_db.create_run_trace(
        task_id="scene-bootstrap-run",
        book_id=1,
        status="running",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    context = _make_context(tmp_db, sample_world, _AlwaysFatalVerifier())

    chapter_trace, _chapter_output = GenerateChapterUseCase(context).execute(run_id=run_id, chapter_number=1)

    persisted = tmp_db.get_run_chapter_trace(run_id, 1)
    assert persisted is not None
    assert chapter_trace.status == "needs_review"
    assert persisted["status"] == "needs_review"
    assert tmp_db.count_pending_scene_reviews(run_id, 1) == 1
    assert persisted["planner_output_json"]["title"] == "第 1 章"


def test_refresh_chapter_can_bootstrap_missing_chapter_trace_from_scenes(tmp_db: Database, sample_world) -> None:
    """历史 run 只有 scene trace 时，refresh 应补建章节 trace 而不是直接抛错。"""
    run_id = tmp_db.create_run_trace(
        task_id="scene-refresh-fallback",
        book_id=1,
        status="running",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    tmp_db.upsert_run_scene_trace(
        run_id,
        {
            "chapter_number": 1,
            "scene_number": 1,
            "status": "completed",
            "scene_plan": {
                "chapter_number": 1,
                "scene_number": 1,
                "title": "场景1",
                "goal": "引出冲突",
                "conflict": "线索逼近",
                "turning_point": "角色被迫表态",
                "required_loops": ["loop-1"],
            },
            "draft": None,
            "final_text": "场景正文",
            "changeset": {"loop_updates": [{"loop_id": "loop-1", "action": "introduced", "title": "主线悬念"}]},
            "verifier_issues": [],
            "review_required": False,
            "review_reason": "",
            "review_status": "completed",
            "metrics": {},
        },
    )
    context = _make_context(tmp_db, sample_world, _PassingVerifier())

    chapter_trace, chapter_output, blockers = RefreshChapterAggregateUseCase(context).execute(run_id, 1)

    persisted = tmp_db.get_run_chapter_trace(run_id, 1)
    assert persisted is not None
    assert chapter_trace.status == "ready_to_publish"
    assert chapter_output.status == "ready_to_publish"
    assert blockers.can_publish is True
    assert persisted["planner_output_json"]["scene_count_target"] == 1
