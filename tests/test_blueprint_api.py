"""创作蓝图工作台 API 测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.application.blueprint_contracts import CreationIntent
from poiesis.application.blueprint_use_cases import BlueprintContext
from poiesis.db.database import Database
from poiesis.llm.base import LLMClient
from poiesis.pipeline.planning.roadmap_planner import RoadmapPlanner
from tests.conftest import MockLLMClient


def _make_client(tmp_db: Database) -> TestClient:
    from poiesis.api import deps

    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    app.dependency_overrides[deps.require_admin] = lambda: {
        "sub": "1",
        "username": "test_admin",
        "role": "admin",
    }
    return TestClient(app, raise_server_exceptions=True)


class _SequencedJsonLLM(LLMClient):
    """按顺序返回 JSON，用于验证候选方向的自动回炉。"""

    def __init__(self, responses: list[dict[str, object]]) -> None:
        super().__init__(model="mock", temperature=0.0, max_tokens=100)
        self._responses = responses

    def _complete(self, prompt: str, system: str | None = None, **kwargs):  # noqa: ANN001, ARG002
        return ""

    def _complete_json(self, prompt: str, system: str | None = None, **kwargs):  # noqa: ANN001, ARG002
        if not self._responses:
            return {}
        return self._responses.pop(0)

    def _stream_complete(self, prompt: str, system: str | None = None, **kwargs):  # noqa: ANN001, ARG002
        yield ""


def test_roadmap_planner_regenerates_similar_variant() -> None:
    """候选方向若过于相似，应自动回炉并拉开核心驱动差异。"""
    planner = RoadmapPlanner()
    llm = _SequencedJsonLLM(
        [
            {
                "frames": [
                    {
                        "variant_no": 1,
                        "variant_strategy": "江湖人物局",
                        "core_driver": "人物驱动",
                        "conflict_source": "师门与私仇",
                        "world_structure": "单江湖",
                        "protagonist_arc_mode": "复仇",
                        "tone_signature": "肃杀",
                        "ending_mode": "代价胜利",
                        "differentiators": ["人物关系"],
                    },
                    {
                        "variant_no": 2,
                        "variant_strategy": "门派秩序局",
                        "core_driver": "世界驱动",
                        "conflict_source": "门派秩序崩坏",
                        "world_structure": "双秩序",
                        "protagonist_arc_mode": "守护",
                        "tone_signature": "厚重",
                        "ending_mode": "新秩序",
                        "differentiators": ["世界格局"],
                    },
                    {
                        "variant_no": 3,
                        "variant_strategy": "真相追查局",
                        "core_driver": "悬疑驱动",
                        "conflict_source": "旧案阴谋",
                        "world_structure": "暗网江湖",
                        "protagonist_arc_mode": "破局",
                        "tone_signature": "冷峻",
                        "ending_mode": "真相代价",
                        "differentiators": ["谜案追查"],
                    },
                ]
            },
            {
                "hook": "少年剑客误入风暴",
                "world_pitch": "同一座江湖被旧秩序支配。",
                "main_arc_pitch": "主角被迫在追查真相与守护关系之间摇摆。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "师门与私仇",
                "world_structure": "单江湖",
                "protagonist_arc_mode": "复仇",
                "tone_signature": "肃杀",
                "variant_strategy": "江湖人物局",
                "differentiators": ["人物关系"],
            },
            {
                "hook": "少年剑客误入风暴",
                "world_pitch": "同一座江湖被旧秩序支配。",
                "main_arc_pitch": "主角被迫在追查真相与守护关系之间摇摆。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "师门与私仇",
                "world_structure": "单江湖",
                "protagonist_arc_mode": "复仇",
                "tone_signature": "肃杀",
                "variant_strategy": "门派秩序局",
                "differentiators": ["世界格局"],
            },
            {
                "hook": "少年剑客误入风暴",
                "world_pitch": "同一座江湖被旧秩序支配。",
                "main_arc_pitch": "主角被迫在追查真相与守护关系之间摇摆。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "师门与私仇",
                "world_structure": "单江湖",
                "protagonist_arc_mode": "复仇",
                "tone_signature": "肃杀",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案追查"],
            },
            {
                "hook": "诸门并立，旧规将崩",
                "world_pitch": "多门派并立的双层江湖秩序被旧规与新势力同时撕裂。",
                "main_arc_pitch": "主角从旁观者被推到秩序裂缝中央，被迫决定守哪一边的江湖。",
                "ending_pitch": "新秩序",
                "core_driver": "世界驱动",
                "conflict_source": "门派秩序崩坏",
                "world_structure": "双秩序",
                "protagonist_arc_mode": "守护",
                "tone_signature": "厚重",
                "variant_strategy": "门派秩序局",
                "differentiators": ["世界格局", "阵营对抗"],
            },
            {
                "hook": "江湖旧案撕开暗网",
                "world_pitch": "表层江湖平静，暗网江湖以旧案牵动各方势力。",
                "main_arc_pitch": "主角从追查真相走向承担真相代价，并被迫与隐秘组织周旋。",
                "ending_pitch": "真相代价",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案阴谋",
                "world_structure": "暗网江湖",
                "protagonist_arc_mode": "破局",
                "tone_signature": "冷峻",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案追查", "层层揭晓"],
            },
        ]
    )

    variants = planner.generate_concept_variants(
        CreationIntent(
            genre="武侠",
            themes=["成长", "背叛"],
            tone="悲怆",
            protagonist_prompt="少年剑客",
            conflict_prompt="追查灭门真相",
            ending_preference="高代价完成",
            forbidden_elements=["系统流"],
            length_preference="12",
            target_experience="起伏跌宕",
            variant_preference="尽量风格拉开",
        ),
        llm,
    )

    assert len(variants) == 3
    assert len({item.core_driver for item in variants}) == 3
    assert variants[1].core_driver == "世界驱动"
    assert variants[2].core_driver == "悬疑驱动"
    assert variants[2].hook == "江湖旧案撕开暗网"


def test_blueprint_creation_flow_can_lock_book_blueprint(tmp_db: Database, monkeypatch) -> None:
    """从创作意图到整书蓝图锁定，应形成完整的工作流。"""
    from poiesis.api.services import blueprint_service

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=MockLLMClient(json_response={}),
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)

    created = client.post(
        "/api/books",
        json={
            "name": "蓝图测试作品",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "",
            "naming_policy": "localized_zh",
            "is_default": False,
        },
    )
    assert created.status_code == 200
    book_id = created.json()["id"]

    intent_resp = client.post(
        f"/api/books/{book_id}/creation-intent",
        json={
            "genre": "武侠",
            "themes": ["成长", "背叛"],
            "tone": "悲怆",
            "protagonist_prompt": "少年剑客",
            "conflict_prompt": "追查灭门真相",
            "ending_preference": "高代价完成",
            "forbidden_elements": ["系统流"],
            "length_preference": "12",
            "target_experience": "起伏跌宕",
        },
    )
    assert intent_resp.status_code == 200
    assert intent_resp.json()["current_step"] == "concept"

    concept_resp = client.post(f"/api/books/{book_id}/concept-variants:generate", json={})
    assert concept_resp.status_code == 200
    variants = concept_resp.json()["concept_variants"]
    assert len(variants) == 3
    assert variants[0]["core_driver"]
    assert variants[0]["variant_strategy"]

    variant_id = variants[0]["id"]
    select_resp = client.post(f"/api/books/{book_id}/concept-variants/{variant_id}/select", json={})
    assert select_resp.status_code == 200
    assert select_resp.json()["selected_variant_id"] == variant_id

    world_resp = client.post(
        f"/api/books/{book_id}/blueprint/world:generate",
        json={"feedback": "更偏江湖氛围"},
    )
    assert world_resp.status_code == 200
    assert world_resp.json()["status"] == "world_ready"

    confirm_world = client.post(f"/api/books/{book_id}/blueprint/world:confirm", json={})
    assert confirm_world.status_code == 200
    assert confirm_world.json()["status"] == "world_confirmed"

    char_resp = client.post(
        f"/api/books/{book_id}/blueprint/characters:generate",
        json={"feedback": "主角更复杂"},
    )
    assert char_resp.status_code == 200
    assert char_resp.json()["status"] == "characters_ready"

    confirm_char = client.post(f"/api/books/{book_id}/blueprint/characters:confirm", json={})
    assert confirm_char.status_code == 200
    assert confirm_char.json()["status"] == "characters_confirmed"

    roadmap_resp = client.post(
        f"/api/books/{book_id}/blueprint/roadmap:generate",
        json={"feedback": "前三章开局更强"},
    )
    assert roadmap_resp.status_code == 200
    assert roadmap_resp.json()["status"] == "roadmap_ready"

    confirm_roadmap = client.post(f"/api/books/{book_id}/blueprint/roadmap:confirm", json={})
    assert confirm_roadmap.status_code == 200
    assert confirm_roadmap.json()["status"] == "locked"
    assert confirm_roadmap.json()["active_revision_id"] is not None

    detail = client.get(f"/api/books/{book_id}/blueprint")
    assert detail.status_code == 200
    assert detail.json()["roadmap_confirmed"]
    assert detail.json()["revisions"][0]["is_active"] is True


def test_can_regenerate_single_concept_variant_before_selection(tmp_db: Database, monkeypatch) -> None:
    """作者应能只重生成某一版候选方向，而不必整组重来。"""
    from poiesis.api.services import blueprint_service

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=MockLLMClient(json_response={}),
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)

    created = client.post(
        "/api/books",
        json={
            "name": "重生成候选测试",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "",
            "naming_policy": "localized_zh",
            "is_default": False,
        },
    )
    book_id = created.json()["id"]
    client.post(
        f"/api/books/{book_id}/creation-intent",
        json={
            "genre": "武侠",
            "themes": ["成长"],
            "tone": "冷峻",
            "protagonist_prompt": "落魄剑客",
            "conflict_prompt": "追查旧案",
            "ending_preference": "代价胜利",
            "forbidden_elements": [],
            "length_preference": "12",
            "target_experience": "层层揭晓",
            "variant_preference": "世界差异优先",
        },
    )
    generated = client.post(f"/api/books/{book_id}/concept-variants:generate", json={})
    variants = generated.json()["concept_variants"]
    target_id = variants[1]["id"]

    regenerated = client.post(f"/api/books/{book_id}/concept-variants/{target_id}:regenerate", json={})
    assert regenerated.status_code == 200
    payload = regenerated.json()
    assert len(payload["concept_variants"]) == 3
    target_variant = next(item for item in payload["concept_variants"] if item["id"] == target_id)
    assert target_variant["core_driver"]
    assert target_variant["variant_strategy"]
