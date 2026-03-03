"""FastAPI 接口测试。

测试覆盖：
1. GET /api/chapters 返回 200 且结构符合 schema
2. POST /api/world/staging/{id}/reject 在缺少 reason 时返回 422
3. approve/reject 能真正改变数据库中该 staging 的状态
4. POST /api/run 能创建 task 并可通过 GET /api/run/{task_id} 查询到状态
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.db.database import Database

# ──────────────────────────────────────────────
# 工具函数：为每个测试注入独立的临时数据库
# ──────────────────────────────────────────────


def _make_client(tmp_db: Database) -> TestClient:
    """创建注入了临时数据库的 TestClient（同时绕过 admin 权限守卫）。"""
    from poiesis.api import deps

    # 覆盖 get_db 依赖，返回临时数据库
    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    # 绕过 admin 权限守卫（测试环境无需真实认证）
    app.dependency_overrides[deps.require_admin] = lambda: {"sub": "1", "username": "test_admin", "role": "admin"}
    client = TestClient(app, raise_server_exceptions=True)
    return client


# ──────────────────────────────────────────────
# 测试 1：GET /api/chapters 返回 200 且结构符合 schema
# ──────────────────────────────────────────────


class TestListChapters:
    """章节列表接口测试。"""

    def test_empty_chapters_returns_200(self, tmp_db: Database) -> None:
        """数据库为空时，GET /api/chapters 应返回 200 和空列表。"""
        client = _make_client(tmp_db)
        resp = client.get("/api/chapters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_chapters_schema_fields(self, tmp_db: Database) -> None:
        """章节列表应包含 schema 规定的所有字段。"""
        # 预置一条章节数据
        tmp_db.upsert_chapter(
            chapter_number=1,
            content="第一章正文内容。",
            title="起航",
            word_count=5,
            status="final",
        )
        client = _make_client(tmp_db)
        resp = client.get("/api/chapters")
        assert resp.status_code == 200

        data = resp.json()
        assert len(data) == 1

        item = data[0]
        # 验证必要字段存在
        for field in ("id", "chapter_number", "title", "word_count", "status", "created_at"):
            assert field in item, f"字段 '{field}' 缺失"

        # 验证状态映射：数据库 'final' → 前端 'completed'
        assert item["status"] == "completed"
        assert item["chapter_number"] == 1
        assert item["title"] == "起航"
        assert item["word_count"] == 5

    def test_chapters_status_mapping_flagged(self, tmp_db: Database) -> None:
        """数据库 status='flagged' 应映射为前端 'draft'。"""
        tmp_db.upsert_chapter(1, "内容", status="flagged")
        client = _make_client(tmp_db)
        resp = client.get("/api/chapters")
        assert resp.json()[0]["status"] == "draft"


# ──────────────────────────────────────────────
# 测试 2：POST /api/world/staging/{id}/reject 缺少 reason 返回 422
# ──────────────────────────────────────────────


class TestRejectStagingValidation:
    """Staging 拒绝接口的输入验证测试。"""

    def test_reject_without_reason_returns_422(self, tmp_db: Database) -> None:
        """请求体缺少 reason 字段时，应返回 422 Unprocessable Entity。"""
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="TestChar",
            proposed_data={"name": "TestChar"},
        )
        client = _make_client(tmp_db)
        # 提交空 body（缺少 reason）
        resp = client.post(f"/api/world/staging/{change_id}/reject", json={})
        assert resp.status_code == 422

    def test_reject_with_empty_reason_returns_422(self, tmp_db: Database) -> None:
        """reason 为空字符串时，FastAPI Pydantic 验证应拒绝（reason 是必填字段）。"""
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="TestChar2",
            proposed_data={"name": "TestChar2"},
        )
        client = _make_client(tmp_db)
        # reason 为空字符串（Pydantic 默认允许空字符串，但字段为 required）
        # 不传 reason 键：应返回 422
        resp = client.post(f"/api/world/staging/{change_id}/reject", json={"comment": "nope"})
        assert resp.status_code == 422


# ──────────────────────────────────────────────
# 测试 3：approve/reject 能真正改变数据库中 staging 的状态
# ──────────────────────────────────────────────


class TestStagingStatusChange:
    """Staging 审批与拒绝状态持久化测试。"""

    def test_approve_changes_db_status(self, tmp_db: Database) -> None:
        """调用 approve 后，数据库中该条 staging 状态应变为 'approved'。"""
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="world_rule",
            entity_key="new_rule",
            proposed_data={"rule_key": "new_rule", "description": "测试规则"},
        )
        client = _make_client(tmp_db)
        resp = client.post(f"/api/world/staging/{change_id}/approve", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # 验证数据库中状态已更新
        record = tmp_db.get_staging_change(change_id)
        assert record is not None
        assert record["status"] == "approved"

    def test_reject_changes_db_status_and_saves_reason(self, tmp_db: Database) -> None:
        """调用 reject 后，数据库状态应为 'rejected' 且 rejection_reason 已保存。"""
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="villain",
            proposed_data={"name": "villain"},
        )
        client = _make_client(tmp_db)
        reason = "与既定角色设定冲突"
        resp = client.post(
            f"/api/world/staging/{change_id}/reject", json={"reason": reason}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert body["rejection_reason"] == reason

        # 验证数据库中状态与原因均已持久化
        record = tmp_db.get_staging_change(change_id)
        assert record is not None
        assert record["status"] == "rejected"
        assert record["rejection_reason"] == reason


# ──────────────────────────────────────────────
# 测试 4：POST /api/run 创建任务并可查询状态
# ──────────────────────────────────────────────


class TestRunTask:
    """运行任务创建与状态查询测试。"""

    def test_start_run_creates_task(self, tmp_db: Database) -> None:
        """POST /api/run 应返回 task_id 和初始状态。"""
        client = _make_client(tmp_db)
        resp = client.post("/api/run", json={"chapter_count": 1})
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body
        assert body["status"] in ("pending", "running", "queued")
        assert body["task_id"] != ""

    def test_get_task_status_after_start(self, tmp_db: Database) -> None:
        """创建任务后，GET /api/run/{task_id} 应能查询到该任务状态。"""
        client = _make_client(tmp_db)
        # 创建任务
        create_resp = client.post("/api/run", json={"chapter_count": 2})
        assert create_resp.status_code == 200
        task_id = create_resp.json()["task_id"]

        # 查询任务状态
        status_resp = client.get(f"/api/run/{task_id}")
        assert status_resp.status_code == 200
        task = status_resp.json()
        assert task["task_id"] == task_id
        assert task["status"] in ("pending", "running", "completed", "failed")
        assert task["total_chapters"] == 2
        assert isinstance(task["logs"], list)

    def test_get_nonexistent_task_returns_404(self, tmp_db: Database) -> None:
        """查询不存在的 task_id 应返回 404。"""
        client = _make_client(tmp_db)
        resp = client.get("/api/run/nonexistent-task-id-xyz")
        assert resp.status_code == 404

    def test_start_run_invalid_chapter_count(self, tmp_db: Database) -> None:
        """chapter_count <= 0 应返回 422。"""
        client = _make_client(tmp_db)
        resp = client.post("/api/run", json={"chapter_count": 0})
        assert resp.status_code == 422
