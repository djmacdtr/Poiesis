"""当前保留 API 的基础回归测试。"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.db.database import Database


def _make_client(tmp_db: Database) -> TestClient:
    """注入临时数据库，并绕过 admin 权限守卫。"""
    from poiesis.api import deps

    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    app.dependency_overrides[deps.require_admin] = lambda: {
        "sub": "1",
        "username": "test_admin",
        "role": "admin",
    }
    return TestClient(app, raise_server_exceptions=True)


class TestListChapters:
    """章节列表接口测试。"""

    def test_empty_chapters_returns_200(self, tmp_db: Database) -> None:
        client = _make_client(tmp_db)
        resp = client.get("/api/chapters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_chapters_schema_fields(self, tmp_db: Database) -> None:
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

        item = resp.json()[0]
        for field in ("id", "chapter_number", "title", "word_count", "status", "created_at"):
            assert field in item
        assert item["status"] == "completed"
        assert item["chapter_number"] == 1

    def test_chapters_list_can_filter_by_book_id(self, tmp_db: Database) -> None:
        second_book_id = tmp_db.create_book(name="第二本", language="zh-CN")
        tmp_db.upsert_chapter(1, "默认书章节", title="默认书-第一章", status="final", book_id=1)
        tmp_db.upsert_chapter(
            1,
            "第二本章节",
            title="第二本-第一章",
            status="final",
            book_id=second_book_id,
        )

        client = _make_client(tmp_db)
        resp_default = client.get("/api/chapters?book_id=1")
        resp_second = client.get(f"/api/chapters?book_id={second_book_id}")

        assert resp_default.status_code == 200
        assert resp_second.status_code == 200
        assert resp_default.json()[0]["book_id"] == 1
        assert resp_second.json()[0]["book_id"] == second_book_id


class TestBooksApi:
    """书籍路由测试。"""

    def test_list_books_returns_default_book(self, tmp_db: Database) -> None:
        client = _make_client(tmp_db)
        resp = client.get("/api/books")
        assert resp.status_code == 200
        assert any(item.get("id") == 1 for item in resp.json())

    def test_list_books_returns_503_when_db_unavailable(self, monkeypatch) -> None:
        from poiesis.api import deps

        app.dependency_overrides.clear()
        original = Database.initialize_schema

        def _boom(self: Database, schema_path: str | None = None) -> None:
            raise sqlite3.OperationalError("unable to open database file")

        monkeypatch.setattr(Database, "initialize_schema", _boom)
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.get("/api/books")
        finally:
            monkeypatch.setattr(Database, "initialize_schema", original)
            app.dependency_overrides.clear()

        assert resp.status_code == 503
        assert "数据库不可用" in resp.text

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
        assert resp.json()["name"] == payload["name"]

    def test_update_book_to_duplicate_name_returns_409(self, tmp_db: Database) -> None:
        client = _make_client(tmp_db)
        first = client.post(
            "/api/books",
            json={
                "name": "第一本",
                "language": "zh-CN",
                "style_preset": "neutral_cn",
                "style_prompt": "",
                "naming_policy": "localized_zh",
                "is_default": False,
            },
        )
        second = client.post(
            "/api/books",
            json={
                "name": "第二本",
                "language": "zh-CN",
                "style_preset": "neutral_cn",
                "style_prompt": "",
                "naming_policy": "localized_zh",
                "is_default": False,
            },
        )
        assert first.status_code == 200
        assert second.status_code == 200

        update_resp = client.put(
            f"/api/books/{second.json()['id']}",
            json={
                "name": "第一本",
                "language": "zh-CN",
                "style_preset": "neutral_cn",
                "style_prompt": "",
                "naming_policy": "localized_zh",
                "is_default": False,
            },
        )
        assert update_resp.status_code == 409


class TestCanonBookScopedQueries:
    """Canon Explorer 按书过滤测试。"""

    def test_canon_can_filter_by_book_id(self, tmp_db: Database) -> None:
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
        resp_default = client.get("/api/canon?book_id=1")
        resp_second = client.get(f"/api/canon?book_id={second_book_id}")

        assert resp_default.status_code == 200
        assert resp_second.status_code == 200
        assert resp_default.json()["timeline"][0]["event_key"] == "ev-book-1"
        assert resp_second.json()["timeline"][0]["event_key"] == "ev-book-2"


class TestHealthApi:
    """健康检查测试。"""

    def test_health_returns_database_status(self, tmp_db: Database) -> None:
        from poiesis.api import deps

        app.dependency_overrides[deps.get_db] = lambda: tmp_db
        client = TestClient(app, raise_server_exceptions=True)
        try:
            resp = client.get("/health")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["database"] == "ok"

    def test_health_returns_503_when_db_unavailable(self, monkeypatch) -> None:
        original = Database.initialize_schema

        def _boom(self: Database, schema_path: str | None = None) -> None:
            raise sqlite3.OperationalError("unable to open database file")

        monkeypatch.setattr(Database, "initialize_schema", _boom)
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.get("/health")
        finally:
            monkeypatch.setattr(Database, "initialize_schema", original)
            app.dependency_overrides.clear()

        assert resp.status_code == 503
        assert "数据库不可用" in resp.text
