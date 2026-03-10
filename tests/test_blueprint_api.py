"""创作蓝图工作台 API 测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.application.blueprint_use_cases import BlueprintContext
from poiesis.db.database import Database
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

