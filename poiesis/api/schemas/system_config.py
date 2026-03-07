"""系统配置 API 数据模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SystemConfigRequest(BaseModel):
    """保存系统配置请求体。"""

    openai_api_key: str | None = None
    """OpenAI API Key（明文，将在服务端加密存储）。"""

    anthropic_api_key: str | None = None
    """Anthropic API Key（明文，将在服务端加密存储）。"""

    embedding_provider: str | None = None
    """Embedding 提供者：local 或 remote。"""

    default_chapter_count: int | None = None
    """默认章节生成数。"""


class SystemConfigStatus(BaseModel):
    """系统配置状态响应（不返回明文 Key）。"""

    has_openai_api_key: bool = False
    """是否已配置 OpenAI API Key。"""

    has_anthropic_api_key: bool = False
    """是否已配置 Anthropic API Key。"""

    embedding_provider: str | None = None
    """已保存的 Embedding 提供者（来自系统配置）。"""

    embedding_provider_effective: Literal["local", "remote"] = "local"
    """当前运行时实际使用的 Embedding 提供者（来自环境变量）。"""

    embedding_service_health: dict[str, str | bool | None] | None = None
    """remote 模式下 Embedding Service 健康状态。"""

    default_chapter_count: int | None = None
    """当前默认章节生成数。"""
