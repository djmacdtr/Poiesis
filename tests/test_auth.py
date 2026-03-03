"""认证相关测试。

覆盖：
1. admin 自动创建逻辑（ensure_admin_exists）
2. 登录接口返回正确的 Cookie
3. 未登录访问受限接口返回 401
4. settings 写入后 GET 只返回 configured 状态（不含明文 Key）
5. 登出后 Cookie 被清除
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.db.database import Database

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

COOKIE_NAME = "poiesis_token"


def _make_client(tmp_db: Database) -> TestClient:
    """创建注入了临时数据库的 TestClient（不绕过认证，用于测试真实认证流程）。"""
    from poiesis.api import deps

    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    # 清除 require_admin 覆盖，保证真实认证生效
    app.dependency_overrides.pop(deps.require_admin, None)
    return TestClient(app, raise_server_exceptions=True)


def _make_authed_client(tmp_db: Database) -> TestClient:
    """创建已登录的 TestClient（先注册 admin，再登录获取 Cookie）。"""
    client = _make_client(tmp_db)
    # 自动创建 admin（环境变量 POIESIS_ADMIN_USER/PASS 默认 admin/admin）
    from poiesis.api.services.auth_service import ensure_admin_exists
    ensure_admin_exists(tmp_db)
    # 登录
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, f"登录失败：{resp.text}"
    return client


# ──────────────────────────────────────────────
# 测试 1：admin 自动创建逻辑
# ──────────────────────────────────────────────


class TestEnsureAdminExists:
    """ensure_admin_exists 函数测试。"""

    def test_creates_admin_when_none_exists(self, tmp_db: Database) -> None:
        """数据库中无 admin 时应自动创建一个。"""
        from poiesis.api.services.auth_service import ensure_admin_exists

        assert tmp_db.count_admins() == 0
        ensure_admin_exists(tmp_db)
        assert tmp_db.count_admins() == 1

    def test_does_not_duplicate_admin(self, tmp_db: Database) -> None:
        """已存在 admin 时，重复调用不应新建用户。"""
        from poiesis.api.services.auth_service import ensure_admin_exists

        ensure_admin_exists(tmp_db)
        ensure_admin_exists(tmp_db)  # 第二次调用
        assert tmp_db.count_admins() == 1

    def test_uses_env_vars(
        self, tmp_db: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """应从环境变量读取用户名与密码。"""
        from poiesis.api.services.auth_service import ensure_admin_exists, verify_password

        monkeypatch.setenv("POIESIS_ADMIN_USER", "myadmin")
        monkeypatch.setenv("POIESIS_ADMIN_PASS", "mypassword123")
        ensure_admin_exists(tmp_db)

        user = tmp_db.get_user_by_username("myadmin")
        assert user is not None
        assert user["role"] == "admin"
        assert verify_password("mypassword123", user["password_hash"])

    def test_password_stored_as_hash(self, tmp_db: Database) -> None:
        """密码应以 bcrypt 哈希存储，数据库中不存明文。"""
        from poiesis.api.services.auth_service import ensure_admin_exists

        ensure_admin_exists(tmp_db)
        user = tmp_db.get_user_by_username("admin")
        assert user is not None
        # 哈希不等于明文
        assert user["password_hash"] != "admin"
        # 哈希以 bcrypt 前缀开头（$2b$ 为当前 bcrypt 标准版本）
        assert user["password_hash"].startswith("$2b$")


# ──────────────────────────────────────────────
# 测试 2：登录接口
# ──────────────────────────────────────────────


class TestLogin:
    """POST /api/auth/login 测试。"""

    def test_login_success_sets_cookie(self, tmp_db: Database) -> None:
        """登录成功后应写入 HttpOnly Cookie 并返回用户信息。"""
        from poiesis.api.services.auth_service import ensure_admin_exists

        ensure_admin_exists(tmp_db)
        client = _make_client(tmp_db)
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "admin"
        assert body["role"] == "admin"
        # Cookie 应已设置
        assert COOKIE_NAME in client.cookies

    def test_login_wrong_password_returns_401(self, tmp_db: Database) -> None:
        """密码错误时应返回 401。"""
        from poiesis.api.services.auth_service import ensure_admin_exists

        ensure_admin_exists(tmp_db)
        client = _make_client(tmp_db)
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user_returns_401(self, tmp_db: Database) -> None:
        """不存在的用户应返回 401。"""
        client = _make_client(tmp_db)
        resp = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
        assert resp.status_code == 401

    def test_get_me_returns_user_info(self, tmp_db: Database) -> None:
        """登录后 GET /api/auth/me 应返回当前用户信息。"""
        client = _make_authed_client(tmp_db)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "admin"
        assert body["role"] == "admin"


# ──────────────────────────────────────────────
# 测试 3：未登录访问受限接口返回 401
# ──────────────────────────────────────────────


class TestUnauthorizedAccess:
    """未登录访问受限接口测试。"""

    def test_post_system_config_without_auth_returns_401(self, tmp_db: Database) -> None:
        """未登录时 POST /api/system/config 应返回 401。"""
        client = _make_client(tmp_db)
        resp = client.post("/api/system/config", json={"openai_api_key": "sk-test"})
        assert resp.status_code == 401

    def test_get_system_config_without_auth_returns_401(self, tmp_db: Database) -> None:
        """未登录时 GET /api/system/config 应返回 401。"""
        client = _make_client(tmp_db)
        resp = client.get("/api/system/config")
        assert resp.status_code == 401

    def test_post_run_without_auth_returns_401(self, tmp_db: Database) -> None:
        """未登录时 POST /api/run 应返回 401。"""
        client = _make_client(tmp_db)
        resp = client.post("/api/run", json={"chapter_count": 1})
        assert resp.status_code == 401

    def test_approve_staging_without_auth_returns_401(self, tmp_db: Database) -> None:
        """未登录时 POST /api/world/staging/{id}/approve 应返回 401。"""
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="TestChar",
            proposed_data={"name": "TestChar"},
        )
        client = _make_client(tmp_db)
        resp = client.post(f"/api/world/staging/{change_id}/approve", json={})
        assert resp.status_code == 401

    def test_public_endpoints_accessible_without_auth(self, tmp_db: Database) -> None:
        """公开只读接口（chapters、canon）无需认证即可访问。"""
        client = _make_client(tmp_db)
        assert client.get("/api/chapters").status_code == 200
        assert client.get("/api/world/canon").status_code == 200
        assert client.get("/health").status_code == 200


# ──────────────────────────────────────────────
# 测试 4：settings 写入后 GET 只返回 configured 状态
# ──────────────────────────────────────────────


class TestSettingsConfiguredStatus:
    """settings 接口安全性测试。"""

    def test_get_config_only_returns_status_not_plaintext(self, tmp_db: Database) -> None:
        """写入 API Key 后，GET /api/system/config 应只返回配置状态，不含明文 Key。"""
        client = _make_authed_client(tmp_db)

        # 写入 key
        plaintext = "sk-super-secret-key-should-never-appear"
        resp = client.post("/api/system/config", json={"openai_api_key": plaintext})
        assert resp.status_code == 200
        assert plaintext not in resp.text

        # 读取状态
        resp2 = client.get("/api/system/config")
        assert resp2.status_code == 200
        body = resp2.json()
        # 仅返回布尔状态
        assert body["has_openai_api_key"] is True
        # 明文 Key 绝对不出现在响应中
        assert plaintext not in resp2.text


# ──────────────────────────────────────────────
# 测试 5：登出
# ──────────────────────────────────────────────


class TestLogout:
    """POST /api/auth/logout 测试。"""

    def test_logout_clears_cookie(self, tmp_db: Database) -> None:
        """登出后 Cookie 应被清除，再次访问受限接口应返回 401。"""
        client = _make_authed_client(tmp_db)
        # 确认已登录
        assert client.get("/api/auth/me").status_code == 200
        # 登出
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        # 登出后访问受限接口应 401
        resp2 = client.get("/api/system/config")
        assert resp2.status_code == 401
