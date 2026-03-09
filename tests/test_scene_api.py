"""Scene 驱动架构的新 API 测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.db.database import Database


def _make_client(tmp_db: Database) -> TestClient:
    """创建注入临时数据库的客户端。"""
    from poiesis.api import deps

    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    app.dependency_overrides[deps.require_admin] = lambda: {
        "sub": "1",
        "username": "test_admin",
        "role": "admin",
    }
    return TestClient(app, raise_server_exceptions=True)


def test_scene_run_detail_and_scene_detail(tmp_db: Database) -> None:
    """新 run 详情接口应返回 chapter 和 scene 结构。"""
    run_id = tmp_db.create_run_trace(
        task_id="scene-task",
        book_id=1,
        status="completed",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    tmp_db.upsert_run_chapter_trace(
        run_id=run_id,
        chapter_number=1,
        status="completed",
        planner_output={"title": "第一章", "goal": "推进主线", "must_progress_loops": ["loop-1"]},
        retrieval_pack={"story_plan": {"focus": "第 1 章"}},
        draft_text="",
        final_content="组装后的正文",
        changeset={"scene_count": 1},
        verifier_issues=[],
        editor_rewrites=[],
        merge_result={"review_required": False},
        summary_result={"summary": "章节摘要"},
        metrics={"scene_count": 1},
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
                "title": "开场",
                "goal": "建立冲突",
                "conflict": "压力来袭",
                "turning_point": "角色做决定",
            },
            "draft": {"chapter_number": 1, "scene_number": 1, "title": "开场", "content": "scene 正文"},
            "final_text": "scene 正文",
            "changeset": {"loop_updates": [{"loop_id": "loop-1"}]},
            "verifier_issues": [],
            "review_required": False,
            "review_reason": "",
            "review_status": "auto_approved",
            "metrics": {"issue_count": 0},
        },
    )
    tmp_db.upsert_chapter_output(
        1,
        {
            "run_id": run_id,
            "chapter_number": 1,
            "title": "第一章",
            "content": "组装后的正文",
            "summary": {"summary": "章节摘要"},
            "scene_count": 1,
            "status": "published",
        },
    )

    client = _make_client(tmp_db)

    run_resp = client.get(f"/api/runs/{run_id}")
    assert run_resp.status_code == 200
    run_body = run_resp.json()
    assert run_body["run"]["id"] == run_id
    assert run_body["chapters"][0]["chapter_number"] == 1

    chapter_resp = client.get(f"/api/runs/{run_id}/chapters/1")
    assert chapter_resp.status_code == 200
    chapter_body = chapter_resp.json()
    assert chapter_body["trace"]["chapter_plan"]["title"] == "第一章"
    assert chapter_body["trace"]["scenes"][0]["scene_plan"]["title"] == "开场"

    scene_resp = client.get(f"/api/runs/{run_id}/chapters/1/scenes/1")
    assert scene_resp.status_code == 200
    scene_body = scene_resp.json()
    assert scene_body["scene"]["scene_plan"]["goal"] == "建立冲突"
    assert scene_body["scene"]["final_text"] == "scene 正文"


def test_review_and_loop_endpoints(tmp_db: Database) -> None:
    """review 队列和 loop board 应能读取并更新新表。"""
    tmp_db.upsert_loop(
        1,
        {
            "loop_id": "loop-1",
            "title": "主角身世",
            "status": "open",
            "introduced_in_scene": "1-1",
            "due_window": "3-5",
            "priority": 2,
            "related_characters": ["主角"],
            "resolution_requirements": ["揭示真相"],
            "last_updated_scene": "1-1",
        },
    )
    run_id = tmp_db.create_run_trace(
        task_id="review-task",
        book_id=1,
        status="running",
        config_snapshot={},
        llm_snapshot={},
    )
    review_id = tmp_db.create_scene_review(run_id, 1, 2, "存在 fatal 设定冲突")

    client = _make_client(tmp_db)

    loops_resp = client.get("/api/loops?book_id=1")
    assert loops_resp.status_code == 200
    assert loops_resp.json()["items"][0]["loop_id"] == "loop-1"

    reviews_resp = client.get("/api/reviews?book_id=1")
    assert reviews_resp.status_code == 200
    assert reviews_resp.json()["items"][0]["id"] == review_id

    approve_resp = client.post(f"/api/reviews/{review_id}/approve", json={})
    assert approve_resp.status_code == 200
    assert approve_resp.json()["action"] == "approve"

    review_id_2 = tmp_db.create_scene_review(run_id, 1, 3, "需要人工 patch")
    patch_resp = client.post(
        f"/api/reviews/{review_id_2}/patch",
        json={"patch_text": "改成主角没有直接说出真相。"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["action"] == "patch"
    patches = tmp_db.list_scene_patches(run_id, 1, 3)
    assert len(patches) == 1
