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

    siliconflow_api_key: str | None = None
    """SiliconFlow API Key（明文，将在服务端加密存储）。"""

    embedding_provider: str | None = None
    """Embedding 提供者：local 或 remote。"""

    default_chapter_count: int | None = None
    """默认章节生成数。"""

    llm_provider: str | None = None
    """写作模型 provider（openai/anthropic/siliconflow）。"""

    llm_model: str | None = None
    """写作模型名称。"""

    planner_llm_provider: str | None = None
    """规划模型 provider（openai/anthropic/siliconflow）。"""

    planner_llm_model: str | None = None
    """规划模型名称。"""


class SystemConfigStatus(BaseModel):
    """系统配置状态响应（不返回明文 Key）。"""

    has_openai_api_key: bool = False
    """是否已配置 OpenAI API Key。"""

    openai_api_key_preview: str | None = None
    """OpenAI API Key 脱敏预览（前4后4）。"""

    has_anthropic_api_key: bool = False
    """是否已配置 Anthropic API Key。"""

    anthropic_api_key_preview: str | None = None
    """Anthropic API Key 脱敏预览（前4后4）。"""

    has_siliconflow_api_key: bool = False
    """是否已配置 SiliconFlow API Key。"""

    siliconflow_api_key_preview: str | None = None
    """SiliconFlow API Key 脱敏预览（前4后4）。"""

    embedding_provider: str | None = None
    """已保存的 Embedding 提供者（来自系统配置）。"""

    embedding_provider_effective: Literal["local", "remote"] = "local"
    """当前运行时实际使用的 Embedding 提供者（来自环境变量）。"""

    embedding_service_health: dict[str, str | bool | None] | None = None
    """remote 模式下 Embedding Service 健康状态。"""

    default_chapter_count: int | None = None
    """当前默认章节生成数。"""

    llm_provider: str | None = None
    """已保存的写作模型 provider（来自系统配置）。"""

    llm_model: str | None = None
    """已保存的写作模型名称（来自系统配置）。"""

    planner_llm_provider: str | None = None
    """已保存的规划模型 provider（来自系统配置）。"""

    planner_llm_model: str | None = None
    """已保存的规划模型名称（来自系统配置）。"""

    llm_provider_effective: str
    """写作模型实际 provider（DB 覆盖后，回退 config.yaml）。"""

    llm_model_effective: str
    """写作模型实际 model（DB 覆盖后，回退 config.yaml）。"""

    planner_llm_provider_effective: str
    """规划模型实际 provider（DB 覆盖后，回退 config.yaml）。"""

    planner_llm_model_effective: str
    """规划模型实际 model（DB 覆盖后，回退 config.yaml）。"""
