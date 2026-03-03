"""系统配置 API 测试。

覆盖：
1. GET /api/system/config - 返回空配置状态
2. POST /api/system/config - 保存配置后返回正确状态
3. API Key 加密存储（数据库中不存明文）
4. crypto 模块加密/解密功能
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.db.database import Database


def _make_client(tmp_db: Database) -> TestClient:
    """创建注入了临时数据库的 TestClient（同时绕过 admin 权限守卫）。"""
    from poiesis.api import deps

    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    # 绕过 admin 权限守卫（测试环境无需真实认证）
    app.dependency_overrides[deps.require_admin] = lambda: {"sub": "1", "username": "test_admin", "role": "admin"}
    return TestClient(app, raise_server_exceptions=True)


class TestGetSystemConfig:
    """GET /api/system/config 测试。"""

    def test_returns_empty_status_when_no_config(self, tmp_db: Database) -> None:
        """数据库为空时应返回全 false 的配置状态。"""
        client = _make_client(tmp_db)
        resp = client.get("/api/system/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_openai_api_key"] is False
        assert body["has_anthropic_api_key"] is False
        assert body["embedding_mode"] is None
        assert body["default_chapter_count"] is None


class TestPostSystemConfig:
    """POST /api/system/config 测试。"""

    def test_save_openai_key_shows_configured(self, tmp_db: Database) -> None:
        """保存 OpenAI Key 后，has_openai_api_key 应为 True。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={"openai_api_key": "sk-test-openai-key"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_openai_api_key"] is True
        assert body["has_anthropic_api_key"] is False

    def test_save_anthropic_key_shows_configured(self, tmp_db: Database) -> None:
        """保存 Anthropic Key 后，has_anthropic_api_key 应为 True。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={"anthropic_api_key": "sk-ant-test-key"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_anthropic_api_key"] is True

    def test_response_does_not_contain_plaintext_key(self, tmp_db: Database) -> None:
        """响应体不应包含明文 API Key。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={"openai_api_key": "sk-secret-should-not-appear"},
        )
        assert resp.status_code == 200
        resp_text = resp.text
        assert "sk-secret-should-not-appear" not in resp_text

    def test_save_embedding_mode_and_chapter_count(self, tmp_db: Database) -> None:
        """保存 embedding_mode 与 default_chapter_count 应正确返回。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={"embedding_mode": "dummy", "default_chapter_count": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["embedding_mode"] == "dummy"
        assert body["default_chapter_count"] == 3

    def test_key_stored_encrypted_in_db(self, tmp_db: Database) -> None:
        """API Key 在数据库中应以密文存储，不能直接读出明文。"""
        client = _make_client(tmp_db)
        plaintext = "sk-very-secret-key-12345"
        client.post("/api/system/config", json={"openai_api_key": plaintext})

        # 直接从数据库读取原始值
        raw = tmp_db.get_system_config("OPENAI_API_KEY")
        assert raw is not None
        # 原始值不应是明文
        assert raw != plaintext

    def test_get_decrypted_key_returns_original(self, tmp_db: Database) -> None:
        """get_decrypted_key 应能还原原始 API Key。"""
        from poiesis.api.services.system_config_service import (
            KEY_OPENAI,
            get_decrypted_key,
        )

        client = _make_client(tmp_db)
        original = "sk-decrypt-test-key"
        client.post("/api/system/config", json={"openai_api_key": original})

        decrypted = get_decrypted_key(tmp_db, KEY_OPENAI)
        assert decrypted == original

    def test_clear_key_by_empty_string(self, tmp_db: Database) -> None:
        """传入空字符串应清除已保存的 Key。"""
        client = _make_client(tmp_db)
        # 先保存
        client.post("/api/system/config", json={"openai_api_key": "sk-test"})
        # 再清空
        resp = client.post("/api/system/config", json={"openai_api_key": ""})
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_openai_api_key"] is False


class TestCrypto:
    """加密/解密模块测试。"""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """加密后再解密应还原原始字符串。"""
        from poiesis.crypto import decrypt, encrypt

        original = "hello-secret-world"
        ciphertext = encrypt(original)
        assert ciphertext != original
        assert decrypt(ciphertext) == original

    def test_encrypt_with_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """设置 POIESIS_SECRET_KEY 环境变量后加密应正常工作。"""
        from cryptography.fernet import Fernet

        from poiesis.crypto import decrypt, encrypt

        key = Fernet.generate_key().decode()
        monkeypatch.setenv("POIESIS_SECRET_KEY", key)

        original = "test-key-with-env"
        ciphertext = encrypt(original)
        assert decrypt(ciphertext) == original
