"""系统配置 API 数据模型。"""

from __future__ import annotations

from pydantic import BaseModel


class SystemConfigRequest(BaseModel):
    """保存系统配置请求体。"""

    openai_api_key: str | None = None
    """OpenAI API Key（明文，将在服务端加密存储）。"""

    anthropic_api_key: str | None = None
    """Anthropic API Key（明文，将在服务端加密存储）。"""

    embedding_mode: str | None = None
    """Embedding 模式：real 或 dummy。"""

    default_chapter_count: int | None = None
    """默认章节生成数。"""


class SystemConfigStatus(BaseModel):
    """系统配置状态响应（不返回明文 Key）。"""

    has_openai_api_key: bool = False
    """是否已配置 OpenAI API Key。"""

    has_anthropic_api_key: bool = False
    """是否已配置 Anthropic API Key。"""

    embedding_mode: str | None = None
    """当前 Embedding 模式。"""

    default_chapter_count: int | None = None
    """当前默认章节生成数。"""
