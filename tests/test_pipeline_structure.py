"""Tests for the restructured domain/pipeline modules."""

from __future__ import annotations

from poiesis.application.pipeline import ChapterGenerationPipeline
from poiesis.domain.world.model import WorldModel
from poiesis.domain.world.repository import WorldRepository
from poiesis.pipeline.extraction.extractor_hub import ExtractorHub
from poiesis.pipeline.planning.story_planner import StoryPlanner
from poiesis.pipeline.verification import BudgetVerifier, CanonVerifier, LLMSemanticVerifier
from poiesis.pipeline.verification.verifier_hub import VerifierHub
from poiesis.vector_store.store import VectorStore
from tests.conftest import MockLLMClient


def test_world_repository_loads_state(tmp_db) -> None:
    tmp_db.upsert_world_rule("gravity", "重力向下", is_immutable=True)
    tmp_db.upsert_character("主角", description="测试角色")
    tmp_db.upsert_loop(
        1,
        {
            "loop_id": "loop-1",
            "title": "旧誓言",
            "status": "open",
            "introduced_in_scene": "1-1",
            "due_start_chapter": 1,
            "due_end_chapter": 3,
            "priority": 2,
            "related_characters": ["主角"],
            "resolution_requirements": ["兑现誓言"],
            "last_updated_scene": "1-1",
        },
    )
    tmp_db.upsert_story_state_snapshot(
        1,
        1,
        {
            "last_published_chapter": 1,
            "published_chapters": [1],
            "active_chapter": 2,
            "recent_scene_refs": ["1-1"],
            "open_loop_count": 1,
            "resolved_loop_count": 0,
            "overdue_loop_count": 0,
        },
    )
    repo = WorldRepository()

    snapshot = repo.load_world_state(tmp_db)

    assert "gravity" in snapshot["canon"]["world_rules"]
    assert "主角" in snapshot["canon"]["characters"]
    assert snapshot["story_state"]["last_published_chapter"] == 1
    assert snapshot["story_state"]["recent_scene_refs"] == ["1-1"]
    assert snapshot["loop_state"][0]["loop_id"] == "loop-1"
    assert snapshot["loop_state"][0]["due_end_chapter"] == 3


def test_world_repository_normalizes_canon_rows(tmp_db) -> None:
    tmp_db.upsert_world_rule("gravity", "重力向下", is_immutable=True)
    tmp_db.upsert_character("主角", description="测试角色")
    repo = WorldRepository()

    rules = repo.list_world_rules(tmp_db)
    characters = repo.list_characters(tmp_db)

    assert rules[0]["is_immutable"] is True
    assert "created_at" in rules[0]
    assert characters[0]["status"] == "active"
    assert "updated_at" in characters[0]


def test_world_repository_marks_staging_status(tmp_db) -> None:
    repo = WorldRepository()
    change_id = tmp_db.add_staging_change(
        change_type="upsert",
        entity_type="world_rule",
        entity_key="new_rule",
        proposed_data={"rule_key": "new_rule", "description": "新规则"},
        source_chapter=1,
    )

    approved = repo.mark_staging_approved(tmp_db, change_id)
    assert approved is not None
    assert approved["status"] == "approved"


def test_story_planner_returns_planner_output(tmp_path, sample_world: WorldModel) -> None:
    planner = StoryPlanner(
        vector_store=VectorStore(str(tmp_path / "vs"), embedding_model="all-MiniLM-L6-v2"),
        language="zh-CN",
    )
    llm = MockLLMClient(
        json_response={
            "title": "第一章",
            "summary": "主角启程",
            "scene_stubs": [{"title": "开场", "goal": "建立冲突"}],
            "key_events": ["离开村庄"],
        }
    )

    result = planner.plan(1, sample_world, [], llm)

    assert result.title == "第一章"
    assert result.chapter_goal == "主角启程"
    assert result.must_preserve == ["离开村庄"]
    assert result.scene_stubs[0].title == "开场"


def test_extractor_hub_returns_changeset_with_uncertain_claims(sample_world: WorldModel) -> None:
    hub = ExtractorHub(language="zh-CN")
    llm = MockLLMClient(
        json_response={
            "new_characters": [{"name": "新角色", "description": "来自雨夜"}],
            "new_world_rules": [],
            "timeline_events": [],
            "foreshadowing": [],
            "character_updates": [],
            "uncertain_claims": ["疑似有人提前知道结局"],
        }
    )

    result = hub.extract(2, "正文", sample_world, llm)

    assert len(result.characters) == 1
    assert result.characters[0]["entity_key"] == "新角色"
    assert result.uncertain_claims[0]["claim"] == "疑似有人提前知道结局"


def test_verifier_hub_emits_budget_and_canon_issues(sample_world: WorldModel, mock_llm) -> None:
    hub = VerifierHub(new_rule_budget=1, language="zh-CN")
    changes = [
        {"change_type": "upsert", "entity_type": "world_rule", "entity_key": "r1", "proposed_data": {}},
        {"change_type": "upsert", "entity_type": "world_rule", "entity_key": "r2", "proposed_data": {}},
        {
            "change_type": "update",
            "entity_type": "world_rule",
            "entity_key": "magic_costs_life",
            "proposed_data": {"description": "修改不可变规则"},
        },
    ]

    result = hub.verify(1, "正文", {}, sample_world, changes, mock_llm)

    assert result.passed is False
    assert any(issue.type == "budget" for issue in result.issues)
    assert any(issue.type == "canon" for issue in result.issues)


def test_verifier_hub_emits_loop_issues(sample_world: WorldModel, mock_llm) -> None:
    sample_world.upsert_loop(
        {
            "loop_id": "loop-1",
            "title": "旧誓言",
            "status": "resolved",
            "introduced_in_scene": "1-1",
            "due_start_chapter": 1,
            "due_end_chapter": 1,
            "due_window": "第 1 章",
            "priority": 2,
            "related_characters": ["Aelindra Voss"],
            "resolution_requirements": ["兑现誓言"],
            "last_updated_scene": "1-1",
        }
    )
    sample_world.upsert_loop(
        {
            "loop_id": "loop-overdue",
            "title": "旧债",
            "status": "open",
            "introduced_in_scene": "1-1",
            "due_start_chapter": 1,
            "due_end_chapter": 1,
            "due_window": "第 1 章",
            "priority": 2,
            "related_characters": ["Aelindra Voss"],
            "resolution_requirements": ["偿还旧债"],
            "last_updated_scene": "1-2",
        }
    )
    hub = VerifierHub(new_rule_budget=3, language="zh-CN")

    result = hub.verify(
        3,
        "正文",
        {"must_progress_loops": ["loop-1"]},
        sample_world,
        [],
        mock_llm,
        required_loops=["loop-1"],
        loop_updates=[{"loop_id": "loop-1", "action": "progressed"}],
    )

    assert result.passed is False
    assert any(issue.type == "loop" and issue.severity == "fatal" for issue in result.issues)
    assert any(issue.type == "loop" and issue.severity == "warning" for issue in result.issues)


def test_budget_verifier_can_be_used_independently() -> None:
    verifier = BudgetVerifier(new_rule_budget=1)

    issues = verifier.verify(
        [
            {"change_type": "upsert", "entity_type": "world_rule", "entity_key": "r1", "proposed_data": {}},
            {"change_type": "upsert", "entity_type": "world_rule", "entity_key": "r2", "proposed_data": {}},
        ]
    )

    assert len(issues) == 1
    assert issues[0].type == "budget"


def test_canon_verifier_can_be_used_independently(sample_world: WorldModel) -> None:
    verifier = CanonVerifier()

    issues = verifier.verify(
        sample_world,
        [
            {
                "change_type": "update",
                "entity_type": "world_rule",
                "entity_key": "magic_costs_life",
                "proposed_data": {"description": "新规则描述"},
            }
        ],
    )

    assert len(issues) == 1
    assert issues[0].type == "canon"


def test_llm_semantic_verifier_can_be_used_independently(sample_world: WorldModel) -> None:
    verifier = LLMSemanticVerifier(language="zh-CN")
    llm = MockLLMClient(
        json_response={
            "violations": ["主角行为动机与前文冲突"],
            "warnings": ["节奏略慢"],
        }
    )

    issues = verifier.verify(
        chapter_number=3,
        content="正文",
        plan={"title": "第三章"},
        world=sample_world,
        proposed_changes=[],
        llm=llm,
        new_rule_budget=3,
    )

    assert len(issues) == 2
    assert {issue.severity for issue in issues} == {"fatal", "warning"}


def test_chapter_generation_pipeline_consumes_new_module_contracts(sample_world: WorldModel, mock_llm, sample_config, tmp_db) -> None:
    class _FakeRuntime:
        def __init__(self) -> None:
            self._config = sample_config
            self._world = sample_world
            self._vs = VectorStore(sample_config.vector_store.path, sample_config.vector_store.embedding_model)
            self._planner_llm = mock_llm
            self._writer_llm = mock_llm
            self._planner = StoryPlanner(self._vs, language="zh-CN")
            self._extractor = ExtractorHub(language="zh-CN")
            self._verifier = VerifierHub(language="zh-CN")
            self._writer = type(
                "_Writer",
                (),
                {"write": lambda self2, chapter_number, plan, world, llm, on_delta=None: "正文内容"},
            )()
            self._editor = type(
                "_Editor",
                (),
                {"edit": lambda self2, chapter_number, content, violations, plan, world, llm: content},
            )()
            self._summarizer = type(
                "_Summarizer",
                (),
                {
                    "summarize": lambda self2, chapter_number, content, plan, world, llm: {
                        "summary": "摘要",
                        "key_events": [],
                        "characters_featured": [],
                        "new_facts_introduced": [],
                    }
                },
            )()
            self._originality = type(
                "_Originality",
                (),
                {"check": lambda self2, content, vs: type("_Result", (), {"is_original": True, "risk_score": 0.0})()},
            )()
            self._db = tmp_db

        def _get_previous_summaries(self) -> list[str]:
            return []

    pipeline = ChapterGenerationPipeline(_FakeRuntime())
    result = pipeline.generate_chapter(1)

    assert result.planner_output.title == "The First Step"
    assert result.summary_result["summary"] == "摘要"
    assert isinstance(result.verifier_issues, list)
