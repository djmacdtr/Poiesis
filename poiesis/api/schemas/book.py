"""书籍配置相关数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookBase(BaseModel):
    """书籍基础字段。"""

    name: str = Field(min_length=1, max_length=120)
    language: str = Field(default="zh-CN", min_length=2, max_length=20)
    style_preset: str = Field(default="literary_cn", min_length=1, max_length=64)
    style_prompt: str = ""
    naming_policy: str = Field(default="localized_zh", min_length=1, max_length=64)
    is_default: bool = False


class BookCreateRequest(BookBase):
    """创建书籍请求。"""


class BookUpdateRequest(BookBase):
    """更新书籍请求。"""


class BookItem(BookBase):
    """书籍响应项。"""

    id: int
    created_at: str
    updated_at: str
