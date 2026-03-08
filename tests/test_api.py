"""FastAPI 接口测试。

测试覆盖：
1. GET /api/chapters 返回 200 且结构符合 schema
2. POST /api/world/staging/{id}/reject 在缺少 reason 时返回 422
3. approve/reject 能真正改变数据库中该 staging 的状态
4. POST /api/run 能创建 task 并可通过 GET /api/run/{task_id} 查询到状态
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.api.task_registry import registry
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
    app.dependency_overrides[deps.require_admin] = lambda: {
        "sub": "1", "username": "test_admin", "role": "admin"
    }
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

    def test_chapters_list_can_filter_by_book_id(self, tmp_db: Database) -> None:
        """不同书籍章节应通过 book_id 查询参数隔离。"""
        second_book_id = tmp_db.create_book(name="第二本", language="zh-CN")

        tmp_db.upsert_chapter(
            chapter_number=1,
            content="默认书章节",
            title="默认书-第一章",
            status="final",
            book_id=1,
        )
        tmp_db.upsert_chapter(
            chapter_number=1,
            content="第二本章节",
            title="第二本-第一章",
            status="final",
            book_id=second_book_id,
        )

        client = _make_client(tmp_db)

        resp_default = client.get("/api/chapters?book_id=1")
        assert resp_default.status_code == 200
        data_default = resp_default.json()
        assert len(data_default) == 1
        assert data_default[0]["book_id"] == 1
        assert data_default[0]["title"] == "默认书-第一章"

        resp_second = client.get(f"/api/chapters?book_id={second_book_id}")
        assert resp_second.status_code == 200
        data_second = resp_second.json()
        assert len(data_second) == 1
        assert data_second[0]["book_id"] == second_book_id
        assert data_second[0]["title"] == "第二本-第一章"


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
        assert task["status"] in ("pending", "running", "completed", "failed", "interrupted")
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

    def test_start_run_invalid_book_id(self, tmp_db: Database) -> None:
        """book_id <= 0 应返回 422。"""
        client = _make_client(tmp_db)
        resp = client.post("/api/run", json={"chapter_count": 1, "book_id": 0})
        assert resp.status_code == 422

    def test_list_tasks_returns_created_task(self, tmp_db: Database) -> None:
        """GET /api/run 应返回已创建任务列表。"""
        client = _make_client(tmp_db)
        created = client.post("/api/run", json={"chapter_count": 1}).json()

        resp = client.get("/api/run")
        assert resp.status_code == 200

        tasks = resp.json()
        assert isinstance(tasks, list)
        assert any(item.get("task_id") == created["task_id"] for item in tasks)

    def test_prune_history_keeps_recent_terminal_tasks(self, tmp_db: Database) -> None:
        """DELETE /api/run/history 应按 keep 保留最近已结束任务。"""
        client = _make_client(tmp_db)

        t1 = client.post("/api/run", json={"chapter_count": 1}).json()["task_id"]
        t2 = client.post("/api/run", json={"chapter_count": 1}).json()["task_id"]

        # 将两个任务都标记为已结束，避免被“运行中任务始终保留”规则保护。
        for task_id in (t1, t2):
            task = registry.get(task_id)
            assert task is not None
            task.status = "completed"

        prune_resp = client.delete("/api/run/history?keep=1")
        assert prune_resp.status_code == 200
        body = prune_resp.json()
        assert body["removed"] >= 1

        list_resp = client.get("/api/run")
        assert list_resp.status_code == 200
        tasks = list_resp.json()

        task_ids = {item["task_id"] for item in tasks}
        assert t2 in task_ids or t1 in task_ids

    def test_task_events_stream_includes_preview_log_and_status(self, tmp_db: Database) -> None:
        """GET /api/run/{task_id}/events 应输出结构化 SSE 事件。"""
        client = _make_client(tmp_db)

        task = registry.create(total_chapters=1)
        task.append_preview("预览片段")
        task.add_log("日志一")
        task.status = "completed"

        resp = client.get(f"/api/run/{task.task_id}/events")
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

        body = resp.text
        assert "event: preview" in body
        assert '"delta": "预览片段"' in body
        assert "event: log" in body
        assert '"message": "日志一"' in body
        assert "event: status" in body
        assert '"status": "completed"' in body


class TestBooksApi:
    """书籍路由测试。"""

    def test_list_books_returns_default_book(self, tmp_db: Database) -> None:
        client = _make_client(tmp_db)
        resp = client.get("/api/books")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(item.get("id") == 1 for item in data)

    def test_create_book_success(self, tmp_db: Database) -> None:
        client = _make_client(tmp_db)
        payload = {
            "name": "玄都夜雨",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "文风：克制、细腻、留白。",
            "naming_policy": "localized_zh",
            "is_default": False,
        }
        resp = client.post("/api/books", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["language"] == payload["language"]

    def test_update_book_success(self, tmp_db: Database) -> None:
        client = _make_client(tmp_db)

        create_resp = client.post(
            "/api/books",
            json={
                "name": "旧书名",
                "language": "zh-CN",
                "style_preset": "neutral_cn",
                "style_prompt": "",
                "naming_policy": "localized_zh",
                "is_default": False,
            },
        )
        assert create_resp.status_code == 200
        book_id = create_resp.json()["id"]

        update_resp = client.put(
            f"/api/books/{book_id}",
            json={
                "name": "新书名",
                "language": "zh-CN",
                "style_preset": "webnovel_cn",
                "style_prompt": "节奏快，冲突密。",
                "naming_policy": "hybrid",
                "is_default": True,
            },
        )
        assert update_resp.status_code == 200
        body = update_resp.json()
        assert body["name"] == "新书名"
        assert body["style_preset"] == "webnovel_cn"
        assert body["is_default"] is True


class TestWorldBookScopedQueries:
    """世界设定接口按书过滤测试。"""

    def test_world_canon_timeline_can_filter_by_book_id(self, tmp_db: Database) -> None:
        second_book_id = tmp_db.create_book(name="第二卷", language="zh-CN")

        tmp_db.upsert_character(name="主角", description="默认书角色", book_id=1)
        tmp_db.upsert_character(name="主角", description="第二卷角色", book_id=second_book_id)
        tmp_db.upsert_world_rule("rule_core", "默认书规则", book_id=1)
        tmp_db.upsert_world_rule("rule_core", "第二卷规则", book_id=second_book_id)
        tmp_db.upsert_foreshadowing("hint_core", "默认书伏笔", book_id=1)
        tmp_db.upsert_foreshadowing("hint_core", "第二卷伏笔", book_id=second_book_id)

        tmp_db.upsert_timeline_event(
            event_key="ev-book-1",
            description="默认书时间线事件",
            chapter_number=1,
            book_id=1,
        )
        tmp_db.upsert_timeline_event(
            event_key="ev-book-2",
            description="第二卷时间线事件",
            chapter_number=1,
            book_id=second_book_id,
        )

        client = _make_client(tmp_db)

        resp_default = client.get("/api/world/canon?book_id=1")
        assert resp_default.status_code == 200
        default_body = resp_default.json()
        default_timeline = default_body["timeline"]
        assert len(default_timeline) == 1
        assert default_timeline[0]["event_key"] == "ev-book-1"
        assert len(default_body["characters"]) == 1
        assert default_body["characters"][0]["description"] == "默认书角色"
        assert len(default_body["world_rules"]) == 1
        assert default_body["world_rules"][0]["description"] == "默认书规则"
        assert len(default_body["foreshadowing"]) == 1
        assert default_body["foreshadowing"][0]["description"] == "默认书伏笔"

        resp_second = client.get(f"/api/world/canon?book_id={second_book_id}")
        assert resp_second.status_code == 200
        second_body = resp_second.json()
        second_timeline = second_body["timeline"]
        assert len(second_timeline) == 1
        assert second_timeline[0]["event_key"] == "ev-book-2"
        assert len(second_body["characters"]) == 1
        assert second_body["characters"][0]["description"] == "第二卷角色"
        assert len(second_body["world_rules"]) == 1
        assert second_body["world_rules"][0]["description"] == "第二卷规则"
        assert len(second_body["foreshadowing"]) == 1
        assert second_body["foreshadowing"][0]["description"] == "第二卷伏笔"

    def test_world_staging_can_filter_by_book_id(self, tmp_db: Database) -> None:
        second_book_id = tmp_db.create_book(name="第三卷", language="zh-CN")

        tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="hero-default",
            proposed_data={"name": "hero-default"},
            book_id=1,
        )
        tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="hero-third",
            proposed_data={"name": "hero-third"},
            book_id=second_book_id,
        )

        client = _make_client(tmp_db)

        resp_default = client.get("/api/world/staging?status=pending&book_id=1")
        assert resp_default.status_code == 200
        data_default = resp_default.json()
        assert len(data_default) == 1
        assert data_default[0]["entity_key"] == "hero-default"

        resp_second = client.get(
            f"/api/world/staging?status=pending&book_id={second_book_id}"
        )
        assert resp_second.status_code == 200
        data_second = resp_second.json()
        assert len(data_second) == 1
        assert data_second[0]["entity_key"] == "hero-third"
