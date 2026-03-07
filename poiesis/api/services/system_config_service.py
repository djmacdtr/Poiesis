"""系统配置服务层：加密存储与读取 API Key 等敏感配置。"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Literal

import httpx

from poiesis.api.schemas.system_config import SystemConfigRequest, SystemConfigStatus
from poiesis.config import load_config
from poiesis.crypto import decrypt, encrypt
from poiesis.db.database import Database

# 配置键名常量
KEY_OPENAI = "OPENAI_API_KEY"
KEY_ANTHROPIC = "ANTHROPIC_API_KEY"
KEY_SILICONFLOW = "SILICONFLOW_API_KEY"
KEY_EMBEDDING_PROVIDER = "embedding_provider"
KEY_DEFAULT_CHAPTER_COUNT = "default_chapter_count"
KEY_LLM_PROVIDER = "llm_provider"
KEY_LLM_MODEL = "llm_model"
KEY_PLANNER_LLM_PROVIDER = "planner_llm_provider"
KEY_PLANNER_LLM_MODEL = "planner_llm_model"

# 需要加密存储的键
_ENCRYPTED_KEYS = {KEY_OPENAI, KEY_ANTHROPIC, KEY_SILICONFLOW}
_ALLOWED_LLM_PROVIDERS = {"openai", "anthropic", "siliconflow"}


def _mask_key_preview(key_value: str | None) -> str | None:
    """Return masked API key preview as first 4 + last 4 chars."""
    if not key_value:
        return None

    value = key_value.strip()
    if len(value) <= 8:
        return f"{value[:4]}...{value[-4:]}"
    return f"{value[:4]}...{value[-4:]}"


class EmbeddingConfigError(Exception):
    """Embedding 配置校验失败异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        provider: str,
        url: str | None = None,
        error: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider
        self.url = url
        self.error = error
        self.suggestion = suggestion

    def to_detail(self) -> dict[str, str | None]:
        """转换为 HTTP 异常 detail 结构。"""
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "url": self.url,
            "error": self.error,
            "suggestion": self.suggestion,
        }


def _normalize_embedding_provider(provider: str) -> str:
    """规范化并校验 embedding provider 值。"""
    value = provider.strip().lower()
    if value not in {"local", "remote"}:
        raise EmbeddingConfigError(
            code="INVALID_EMBEDDING_PROVIDER",
            message="embedding_provider 仅支持 local 或 remote",
            provider=value,
            suggestion="请选择 local（轻量）或 remote（完整模式）",
        )
    return value


def _normalize_llm_provider(provider: str) -> str:
    """规范化并校验 LLM provider。"""
    value = provider.strip().lower()
    if value not in _ALLOWED_LLM_PROVIDERS:
        allowed = ", ".join(sorted(_ALLOWED_LLM_PROVIDERS))
        raise ValueError(f"llm provider 仅支持：{allowed}")
    return value


def _get_effective_embedding_provider() -> Literal["local", "remote"]:
    """读取运行时实际 provider（来自环境变量）。"""
    provider = os.environ.get("POIESIS_EMBEDDING_PROVIDER", "local").strip().lower()
    if provider == "remote":
        return "remote"
    return "local"


def _check_embedding_service_health() -> dict[str, str | bool | None]:
    """检查 remote embedding 服务健康状态。"""
    url = os.environ.get("POIESIS_EMBEDDING_URL", "http://embed:9000").rstrip("/")
    checked_at = datetime.now(UTC).isoformat(timespec="seconds")
    health_url = f"{url}/health"

    try:
        resp = httpx.get(health_url, timeout=5.0)
        if resp.status_code == 200:
            return {
                "provider": "remote",
                "reachable": True,
                "url": url,
                "status": "ok",
                "error_msg": None,
                "checked_at": checked_at,
            }
        return {
            "provider": "remote",
            "reachable": False,
            "url": url,
            "status": "error",
            "error_msg": f"HTTP {resp.status_code}",
            "checked_at": checked_at,
        }
    except httpx.TimeoutException:
        return {
            "provider": "remote",
            "reachable": False,
            "url": url,
            "status": "unreachable",
            "error_msg": "timeout",
            "checked_at": checked_at,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "remote",
            "reachable": False,
            "url": url,
            "status": "unreachable",
            "error_msg": str(exc),
            "checked_at": checked_at,
        }


def save_config(db: Database, req: SystemConfigRequest) -> SystemConfigStatus:
    """将配置保存到数据库（API Key 加密后存储）。

    Args:
        db: 数据库实例。
        req: 前端提交的配置请求。

    Returns:
        更新后的配置状态（不含明文 Key）。
    """
    # 保存 OpenAI Key（加密）
    if req.openai_api_key is not None:
        # 空字符串表示清空
        if req.openai_api_key:
            db.set_system_config(KEY_OPENAI, encrypt(req.openai_api_key))
        else:
            db.set_system_config(KEY_OPENAI, "")

    # 保存 Anthropic Key（加密）
    if req.anthropic_api_key is not None:
        if req.anthropic_api_key:
            db.set_system_config(KEY_ANTHROPIC, encrypt(req.anthropic_api_key))
        else:
            db.set_system_config(KEY_ANTHROPIC, "")

    # 保存 SiliconFlow Key（加密）
    if req.siliconflow_api_key is not None:
        if req.siliconflow_api_key:
            db.set_system_config(KEY_SILICONFLOW, encrypt(req.siliconflow_api_key))
        else:
            db.set_system_config(KEY_SILICONFLOW, "")

    # 保存 Embedding 提供者（仅支持 local / remote）
    if req.embedding_provider is not None:
        provider = _normalize_embedding_provider(req.embedding_provider)
        if provider == "remote":
            health = _check_embedding_service_health()
            if not bool(health["reachable"]):
                raise EmbeddingConfigError(
                    code="EMBEDDING_SERVICE_UNREACHABLE",
                    message="无法保存 remote 配置：Embedding Service 不可达",
                    provider=provider,
                    url=str(health["url"]),
                    error=health["error_msg"] if isinstance(health["error_msg"], str) else None,
                    suggestion="请先执行 docker compose --profile full up -d，再重试保存",
                )
        db.set_system_config(KEY_EMBEDDING_PROVIDER, provider)

    # 保存默认章节数
    if req.default_chapter_count is not None:
        db.set_system_config(KEY_DEFAULT_CHAPTER_COUNT, str(req.default_chapter_count))

    # 保存写作模型 provider
    if req.llm_provider is not None:
        value = req.llm_provider.strip()
        if value:
            db.set_system_config(KEY_LLM_PROVIDER, _normalize_llm_provider(value))
        else:
            db.set_system_config(KEY_LLM_PROVIDER, "")

    # 保存写作模型 model
    if req.llm_model is not None:
        db.set_system_config(KEY_LLM_MODEL, req.llm_model.strip())

    # 保存规划模型 provider
    if req.planner_llm_provider is not None:
        value = req.planner_llm_provider.strip()
        if value:
            db.set_system_config(
                KEY_PLANNER_LLM_PROVIDER,
                _normalize_llm_provider(value),
            )
        else:
            db.set_system_config(KEY_PLANNER_LLM_PROVIDER, "")

    # 保存规划模型 model
    if req.planner_llm_model is not None:
        db.set_system_config(KEY_PLANNER_LLM_MODEL, req.planner_llm_model.strip())

    return get_config_status(db)


def get_config_status(db: Database) -> SystemConfigStatus:
    """读取配置状态（不返回明文 Key）。

    Args:
        db: 数据库实例。

    Returns:
        配置状态对象。
    """
    openai_val = db.get_system_config(KEY_OPENAI)
    anthropic_val = db.get_system_config(KEY_ANTHROPIC)
    siliconflow_val = db.get_system_config(KEY_SILICONFLOW)
    embedding_provider = db.get_system_config(KEY_EMBEDDING_PROVIDER)
    chapter_count_str = db.get_system_config(KEY_DEFAULT_CHAPTER_COUNT)
    llm_provider = db.get_system_config(KEY_LLM_PROVIDER)
    llm_model = db.get_system_config(KEY_LLM_MODEL)
    planner_llm_provider = db.get_system_config(KEY_PLANNER_LLM_PROVIDER)
    planner_llm_model = db.get_system_config(KEY_PLANNER_LLM_MODEL)

    if embedding_provider:
        embedding_provider = embedding_provider.strip().lower()
        if embedding_provider not in {"local", "remote"}:
            embedding_provider = None

    if llm_provider:
        llm_provider = llm_provider.strip().lower()
        if llm_provider not in _ALLOWED_LLM_PROVIDERS:
            llm_provider = None
    else:
        llm_provider = None

    llm_model = llm_model.strip() if llm_model else None

    if planner_llm_provider:
        planner_llm_provider = planner_llm_provider.strip().lower()
        if planner_llm_provider not in _ALLOWED_LLM_PROVIDERS:
            planner_llm_provider = None
    else:
        planner_llm_provider = None

    planner_llm_model = planner_llm_model.strip() if planner_llm_model else None

    effective_provider = _get_effective_embedding_provider()
    embedding_service_health: dict[str, str | bool | None] | None = None
    if embedding_provider == "remote" or effective_provider == "remote":
        embedding_service_health = _check_embedding_service_health()

    default_chapter_count: int | None = None
    if chapter_count_str:
        try:
            default_chapter_count = int(chapter_count_str)
        except ValueError:
            pass

    config_path = os.environ.get("POIESIS_CONFIG", "config.yaml")
    cfg = load_config(config_path)

    llm_provider_effective = llm_provider or cfg.llm.provider
    llm_model_effective = llm_model or cfg.llm.model
    planner_llm_provider_effective = planner_llm_provider or cfg.planner_llm.provider
    planner_llm_model_effective = planner_llm_model or cfg.planner_llm.model

    openai_preview = _mask_key_preview(get_decrypted_key(db, KEY_OPENAI))
    anthropic_preview = _mask_key_preview(get_decrypted_key(db, KEY_ANTHROPIC))
    siliconflow_preview = _mask_key_preview(get_decrypted_key(db, KEY_SILICONFLOW))

    return SystemConfigStatus(
        has_openai_api_key=bool(openai_val),
        openai_api_key_preview=openai_preview,
        has_anthropic_api_key=bool(anthropic_val),
        anthropic_api_key_preview=anthropic_preview,
        has_siliconflow_api_key=bool(siliconflow_val),
        siliconflow_api_key_preview=siliconflow_preview,
        embedding_provider=embedding_provider,
        embedding_provider_effective=effective_provider,
        embedding_service_health=embedding_service_health,
        default_chapter_count=default_chapter_count,
        llm_provider=llm_provider,
        llm_model=llm_model,
        planner_llm_provider=planner_llm_provider,
        planner_llm_model=planner_llm_model,
        llm_provider_effective=llm_provider_effective,
        llm_model_effective=llm_model_effective,
        planner_llm_provider_effective=planner_llm_provider_effective,
        planner_llm_model_effective=planner_llm_model_effective,
    )


def get_decrypted_key(db: Database, config_key: str) -> str | None:
    """获取解密后的 API Key（仅供内部使用，不在日志中打印）。

    Args:
        db: 数据库实例。
        config_key: 配置键名（如 OPENAI_API_KEY）。

    Returns:
        解密后的明文 Key，若未配置或为空则返回 None。
    """
    raw = db.get_system_config(config_key)
    if not raw:
        return None
    if config_key in _ENCRYPTED_KEYS:
        try:
            return decrypt(raw)
        except Exception:  # noqa: BLE001
            # 解密失败（如密钥变更），返回 None
            return None
    return raw
