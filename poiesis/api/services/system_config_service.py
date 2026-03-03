"""系统配置服务层：加密存储与读取 API Key 等敏感配置。"""

from __future__ import annotations

from poiesis.api.schemas.system_config import SystemConfigRequest, SystemConfigStatus
from poiesis.crypto import decrypt, encrypt
from poiesis.db.database import Database

# 配置键名常量
KEY_OPENAI = "OPENAI_API_KEY"
KEY_ANTHROPIC = "ANTHROPIC_API_KEY"
KEY_EMBEDDING_MODE = "embedding_mode"
KEY_DEFAULT_CHAPTER_COUNT = "default_chapter_count"

# 需要加密存储的键
_ENCRYPTED_KEYS = {KEY_OPENAI, KEY_ANTHROPIC}


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

    # 保存 Embedding 模式
    if req.embedding_mode is not None:
        db.set_system_config(KEY_EMBEDDING_MODE, req.embedding_mode)

    # 保存默认章节数
    if req.default_chapter_count is not None:
        db.set_system_config(KEY_DEFAULT_CHAPTER_COUNT, str(req.default_chapter_count))

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
    embedding_mode = db.get_system_config(KEY_EMBEDDING_MODE)
    chapter_count_str = db.get_system_config(KEY_DEFAULT_CHAPTER_COUNT)

    default_chapter_count: int | None = None
    if chapter_count_str:
        try:
            default_chapter_count = int(chapter_count_str)
        except ValueError:
            pass

    return SystemConfigStatus(
        has_openai_api_key=bool(openai_val),
        has_anthropic_api_key=bool(anthropic_val),
        embedding_mode=embedding_mode,
        default_chapter_count=default_chapter_count,
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
