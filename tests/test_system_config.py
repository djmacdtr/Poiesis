"""系统配置 API 测试。

覆盖：
1. GET /api/system/config - 返回空配置状态
2. POST /api/system/config - 保存配置后返回正确状态
3. API Key 加密存储（数据库中不存明文）
4. crypto 模块加密/解密功能
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.db.database import Database


def _make_client(tmp_db: Database) -> TestClient:
    """创建注入了临时数据库的 TestClient（同时绕过 admin 权限守卫）。"""
    from poiesis.api import deps

    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    # 绕过 admin 权限守卫（测试环境无需真实认证）
    app.dependency_overrides[deps.require_admin] = lambda: {
        "sub": "1", "username": "test_admin", "role": "admin"
    }
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
        assert body["has_siliconflow_api_key"] is False
        assert body["embedding_provider"] is None
        assert body["embedding_provider_effective"] in ("local", "remote")
        assert body["embedding_service_health"] is None
        assert body["default_chapter_count"] is None
        assert body["llm_provider"] is None
        assert body["llm_model"] is None
        assert body["planner_llm_provider"] is None
        assert body["planner_llm_model"] is None
        assert isinstance(body["llm_provider_effective"], str)
        assert isinstance(body["llm_model_effective"], str)
        assert isinstance(body["planner_llm_provider_effective"], str)
        assert isinstance(body["planner_llm_model_effective"], str)


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

    def test_save_siliconflow_key_shows_configured(self, tmp_db: Database) -> None:
        """保存 SiliconFlow Key 后，has_siliconflow_api_key 应为 True。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={"siliconflow_api_key": "sk-siliconflow-test-key"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_siliconflow_api_key"] is True

    def test_save_embedding_provider_and_chapter_count(self, tmp_db: Database) -> None:
        """保存 embedding_provider 与 default_chapter_count 应正确返回。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={"embedding_provider": "local", "default_chapter_count": 3},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["embedding_provider"] == "local"
        assert body["embedding_provider_effective"] in ("local", "remote")
        assert body["embedding_service_health"] is None
        assert body["default_chapter_count"] == 3

    def test_save_remote_provider_requires_reachable_service(self, tmp_db: Database) -> None:
        """保存 remote 时若 embed 不可达，应返回 422。"""
        from poiesis.api.services import system_config_service

        client = _make_client(tmp_db)

        original = system_config_service._check_embedding_service_health
        def _fake_unreachable() -> dict[str, str | bool | None]:
            return {
                "provider": "remote",
                "reachable": False,
                "url": "http://embed:9000",
                "status": "unreachable",
                "error_msg": "connection refused",
                "checked_at": "2026-03-07T00:00:00+00:00",
            }

        system_config_service._check_embedding_service_health = _fake_unreachable
        try:
            resp = client.post(
                "/api/system/config",
                json={"embedding_provider": "remote"},
            )
        finally:
            system_config_service._check_embedding_service_health = original

        assert resp.status_code == 422
        body = resp.json()
        assert body["detail"]["code"] == "EMBEDDING_SERVICE_UNREACHABLE"

    def test_save_remote_provider_when_service_reachable(self, tmp_db: Database) -> None:
        """保存 remote 且 embed 可达时应成功。"""
        from poiesis.api.services import system_config_service

        client = _make_client(tmp_db)

        original = system_config_service._check_embedding_service_health
        def _fake_reachable() -> dict[str, str | bool | None]:
            return {
                "provider": "remote",
                "reachable": True,
                "url": "http://embed:9000",
                "status": "ok",
                "error_msg": None,
                "checked_at": "2026-03-07T00:00:00+00:00",
            }

        system_config_service._check_embedding_service_health = _fake_reachable
        try:
            resp = client.post(
                "/api/system/config",
                json={"embedding_provider": "remote"},
            )
        finally:
            system_config_service._check_embedding_service_health = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["embedding_provider"] == "remote"
        assert body["embedding_service_health"] is not None
        assert body["embedding_service_health"]["reachable"] is True

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

    def test_clear_siliconflow_key_by_empty_string(self, tmp_db: Database) -> None:
        """传入空字符串应清除已保存的 SiliconFlow Key。"""
        client = _make_client(tmp_db)
        client.post("/api/system/config", json={"siliconflow_api_key": "sk-sf-test"})

        resp = client.post("/api/system/config", json={"siliconflow_api_key": ""})
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_siliconflow_api_key"] is False

    def test_siliconflow_key_stored_encrypted_and_decryptable(self, tmp_db: Database) -> None:
        """SiliconFlow Key 应加密存储且可通过服务层解密读取。"""
        from poiesis.api.services.system_config_service import (
            KEY_SILICONFLOW,
            get_decrypted_key,
        )

        client = _make_client(tmp_db)
        plaintext = "sk-sf-very-secret"
        client.post("/api/system/config", json={"siliconflow_api_key": plaintext})

        raw = tmp_db.get_system_config(KEY_SILICONFLOW)
        assert raw is not None
        assert raw != plaintext
        assert get_decrypted_key(tmp_db, KEY_SILICONFLOW) == plaintext

    def test_save_llm_and_planner_model_config(self, tmp_db: Database) -> None:
        """保存 llm/planner_llm 的 provider+model 应正确回显并给出 effective 值。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={
                "llm_provider": "anthropic",
                "llm_model": "claude-3-7-sonnet-latest",
                "planner_llm_provider": "openai",
                "planner_llm_model": "gpt-4o-mini",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["llm_provider"] == "anthropic"
        assert body["llm_model"] == "claude-3-7-sonnet-latest"
        assert body["planner_llm_provider"] == "openai"
        assert body["planner_llm_model"] == "gpt-4o-mini"
        assert body["llm_provider_effective"] == "anthropic"
        assert body["llm_model_effective"] == "claude-3-7-sonnet-latest"
        assert body["planner_llm_provider_effective"] == "openai"
        assert body["planner_llm_model_effective"] == "gpt-4o-mini"

    def test_invalid_llm_provider_returns_422(self, tmp_db: Database) -> None:
        """非法 llm_provider 应返回 422。"""
        client = _make_client(tmp_db)
        resp = client.post(
            "/api/system/config",
            json={"llm_provider": "unknown-provider"},
        )
        assert resp.status_code == 422

    def test_clear_model_config_falls_back_to_yaml(self, tmp_db: Database) -> None:
        """清空模型配置后，effective 值应回退到 config.yaml 默认值。"""
        client = _make_client(tmp_db)

        save_resp = client.post(
            "/api/system/config",
            json={
                "llm_provider": "anthropic",
                "llm_model": "claude-3-7-sonnet-latest",
                "planner_llm_provider": "siliconflow",
                "planner_llm_model": "Qwen/Qwen2.5-72B-Instruct",
            },
        )
        assert save_resp.status_code == 200

        clear_resp = client.post(
            "/api/system/config",
            json={
                "llm_provider": "",
                "llm_model": "",
                "planner_llm_provider": "",
                "planner_llm_model": "",
            },
        )
        assert clear_resp.status_code == 200
        body = clear_resp.json()

        assert body["llm_provider"] is None
        assert body["llm_model"] is None
        assert body["planner_llm_provider"] is None
        assert body["planner_llm_model"] is None
        assert body["llm_provider_effective"] == "openai"
        assert body["llm_model_effective"] == "gpt-4o"
        assert body["planner_llm_provider_effective"] == "openai"
        assert body["planner_llm_model_effective"] == "gpt-4o"


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
