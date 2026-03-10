"""Scene 驱动架构的新 API 测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.application.scene_contracts import ChangeSet, SceneDraft
from poiesis.application.use_cases import SceneGenerationContext
from poiesis.db.database import Database
from poiesis.pipeline.assembly.chapter_assembler import ChapterAssembler
from tests.conftest import MockLLMClient


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


class _StubSceneWriter:
    """固定返回可通过校验的重试文本。"""

    def write(self, scene_plan, chapter_plan, world, llm, on_delta=None) -> SceneDraft:  # noqa: ANN001
        return SceneDraft(
            chapter_number=scene_plan.chapter_number,
            scene_number=scene_plan.scene_number,
            title=scene_plan.title,
            content=f"重试后的正文：{scene_plan.title}",
            retrieval_context={},
        )


class _StubSceneExtractor:
    """返回稳定的空变更集，便于测试状态流。"""

    def extract(self, scene_plan, content, world, llm) -> ChangeSet:  # noqa: ANN001
        return ChangeSet(raw_changes=[], loop_updates=[])


class _StubSceneVerifier:
    """只在文本包含“失败”时返回 fatal 问题。"""

    def verify(self, scene_plan, content, chapter_plan, world, changeset, llm):  # noqa: ANN001
        if "失败" in content:
            return [
                {
                    "severity": "fatal",
                    "type": "semantic",
                    "reason": "仍存在 fatal 问题",
                    "repair_hint": "继续修补",
                    "location": "scene",
                }
            ]
        return []


class _StubSceneEditor:
    """把 patch 要求直接转换成新的 scene 文本。"""

    def rewrite(self, scene_plan, chapter_plan, content, issues, world, llm) -> str:  # noqa: ANN001
        return f"{content}\n修补结果：{'；'.join(issues)}"


class _StubSummarizer:
    """返回固定摘要，避免依赖真实 LLM。"""

    def summarize(self, chapter_number, content, plan, world, llm):  # noqa: ANN001
        return {
            "summary": f"第 {chapter_number} 章摘要",
            "key_events": ["场景已重组"],
            "characters_featured": [],
            "new_facts_introduced": [],
        }


def _make_context(tmp_db: Database, sample_world) -> SceneGenerationContext:  # noqa: ANN001
    llm = MockLLMClient()
    return SceneGenerationContext(
        db=tmp_db,
        world=sample_world,
        planner_llm=llm,
        writer_llm=llm,
        chapter_planner=object(),  # 当前 API 动作不会用到这两个依赖
        scene_planner=object(),
        scene_writer=_StubSceneWriter(),
        scene_extractor=_StubSceneExtractor(),
        scene_verifier=_StubSceneVerifier(),
        scene_editor=_StubSceneEditor(),
        chapter_assembler=ChapterAssembler(),
        summarizer=_StubSummarizer(),
        book_id=1,
    )


def _seed_review_scene(tmp_db: Database, scene_number: int = 1) -> tuple[int, int]:
    """插入 run/chapter/scene/review 的最小测试数据。"""
    run_id = tmp_db.create_run_trace(
        task_id=f"scene-task-{scene_number}",
        book_id=1,
        status="running",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    tmp_db.upsert_run_chapter_trace(
        run_id=run_id,
        chapter_number=1,
        status="needs_review",
        planner_output={
            "chapter_number": 1,
            "title": "第一章",
            "goal": "推进主线",
            "must_progress_loops": ["loop-1"],
        },
        retrieval_pack={"story_plan": {"book_id": 1, "focus": "第 1 章"}},
        draft_text="",
        final_content="待审章节正文",
        changeset={"scene_count": 1},
        verifier_issues=[{"severity": "fatal", "reason": "存在设定冲突"}],
        editor_rewrites=[],
        merge_result={"review_required": True, "can_publish": False, "blockers": ["仍有待审阅场景。"]},
        summary_result={"summary": "章节摘要"},
        metrics={"scene_count": 1},
    )
    tmp_db.upsert_run_scene_trace(
        run_id,
        {
            "chapter_number": 1,
            "scene_number": scene_number,
            "status": "needs_review",
            "scene_plan": {
                "chapter_number": 1,
                "scene_number": scene_number,
                "title": f"场景{scene_number}",
                "goal": "建立冲突",
                "conflict": "压力来袭",
                "turning_point": "角色做决定",
            },
            "draft": {
                "chapter_number": 1,
                "scene_number": scene_number,
                "title": f"场景{scene_number}",
                "content": "旧正文",
            },
            "final_text": "旧正文",
            "changeset": {"loop_updates": [{"loop_id": "loop-1"}]},
            "verifier_issues": [
                {
                    "severity": "fatal",
                    "type": "semantic",
                    "reason": "存在设定冲突",
                    "repair_hint": "修正冲突",
                    "location": "scene",
                }
            ],
            "review_required": True,
            "review_reason": "存在设定冲突",
            "review_status": "pending",
            "metrics": {"issue_count": 1},
        },
    )
    review_id = tmp_db.create_scene_review(run_id, 1, scene_number, "存在设定冲突")
    return run_id, review_id


def test_scene_run_detail_and_publish_flow(tmp_db: Database, sample_world, monkeypatch) -> None:
    """approve 后应刷新 chapter 门禁，并允许人工发布。"""
    from poiesis.api.services import scene_run_service

    run_id, review_id = _seed_review_scene(tmp_db)
    context = _make_context(tmp_db, sample_world)
    monkeypatch.setattr(
        scene_run_service,
        "_build_context_from_db",
        lambda config_path, db, book_id, auto_seed=True: (context, object(), {"id": book_id}),
    )

    client = _make_client(tmp_db)

    approve_resp = client.post(f"/api/reviews/{review_id}/approve", json={})
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "completed"
    assert approve_resp.json()["resolved_scene_status"] == "approved"

    chapter_resp = client.get(f"/api/runs/{run_id}/chapters/1")
    assert chapter_resp.status_code == 200
    chapter_body = chapter_resp.json()
    assert chapter_body["publish"]["can_publish"] is True
    assert chapter_body["publish"]["chapter_status"] == "ready_to_publish"

    publish_resp = client.post(f"/api/runs/{run_id}/chapters/1/publish", json={})
    assert publish_resp.status_code == 200
    assert publish_resp.json()["status"] == "published"

    scene_resp = client.get(f"/api/runs/{run_id}/chapters/1/scenes/1")
    assert scene_resp.status_code == 200
    scene_body = scene_resp.json()
    assert scene_body["review"]["status"] == "completed"
    assert scene_body["review_events"][0]["action"] == "approve"
    assert scene_body["publish_blockers"]["chapter_status"] == "published"


def test_retry_and_patch_actions_update_trace_and_history(tmp_db: Database, sample_world, monkeypatch) -> None:
    """retry 和 patch 都应更新 scene trace，并留下事件与 patch 历史。"""
    from poiesis.api.services import scene_run_service

    run_id, review_id = _seed_review_scene(tmp_db, scene_number=1)
    second_review_id = tmp_db.create_scene_review(run_id, 1, 2, "需要修补")
    tmp_db.upsert_run_scene_trace(
        run_id,
        {
            "chapter_number": 1,
            "scene_number": 2,
            "status": "needs_review",
            "scene_plan": {
                "chapter_number": 1,
                "scene_number": 2,
                "title": "场景2",
                "goal": "继续推进",
                "conflict": "秘密暴露",
                "turning_point": "决定暂缓",
            },
            "draft": {
                "chapter_number": 1,
                "scene_number": 2,
                "title": "场景2",
                "content": "第二段旧正文",
            },
            "final_text": "第二段旧正文",
            "changeset": {"loop_updates": []},
            "verifier_issues": [
                {
                    "severity": "fatal",
                    "type": "semantic",
                    "reason": "需要人工修补",
                    "repair_hint": "调整措辞",
                    "location": "scene",
                }
            ],
            "review_required": True,
            "review_reason": "需要人工修补",
            "review_status": "pending",
            "metrics": {"issue_count": 1},
        },
    )
    context = _make_context(tmp_db, sample_world)
    monkeypatch.setattr(
        scene_run_service,
        "_build_context_from_db",
        lambda config_path, db, book_id, auto_seed=True: (context, object(), {"id": book_id}),
    )

    client = _make_client(tmp_db)

    retry_resp = client.post(f"/api/reviews/{review_id}/retry", json={})
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "completed"
    scene_after_retry = client.get(f"/api/runs/{run_id}/chapters/1/scenes/1").json()
    assert scene_after_retry["scene"]["final_text"].startswith("重试后的正文")
    assert scene_after_retry["review_events"][0]["action"] == "retry"

    patch_resp = client.post(
        f"/api/reviews/{second_review_id}/patch",
        json={"patch_text": "把冲突改为更克制的表达"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "completed"
    scene_after_patch = client.get(f"/api/runs/{run_id}/chapters/1/scenes/2").json()
    assert len(scene_after_patch["patches"]) == 1
    assert scene_after_patch["patches"][0]["before_text"] == "第二段旧正文"
    assert scene_after_patch["patches"][0]["applied_successfully"] is True
    assert "人工修补要求" in scene_after_patch["scene"]["final_text"]
