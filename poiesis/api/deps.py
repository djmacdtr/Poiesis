"""FastAPI 依赖注入：数据库连接、配置加载与权限控制。"""

from __future__ import annotations

import os
import logging
import sqlite3
from functools import lru_cache
from typing import Any

from fastapi import Cookie, Depends, HTTPException

from poiesis.config import Config, load_config
from poiesis.db.database import Database

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """加载并缓存配置对象（从环境变量 POIESIS_CONFIG 或默认路径读取）。"""
    config_path = os.environ.get("POIESIS_CONFIG", "config.yaml")
    return load_config(config_path)


def get_db() -> Database:
    """返回已初始化的数据库实例（按请求创建，不在进程间共享连接）。

    注意：SQLite 单连接不跨线程，此处每次请求新建连接以保证线程安全。
    生产环境如需高并发，建议迁移至支持连接池的数据库。
    """
    cfg = get_config()
    db = Database(cfg.database.path)
    try:
        db.initialize_schema()
    except sqlite3.OperationalError as exc:
        details = db.debug_info()
        logger.exception(
            "Database initialization failed: path=%s exists=%s parent_exists=%s cwd=%s",
            details["db_path"],
            details["exists"],
            details["parent_exists"],
            details["cwd"],
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "数据库不可用：无法打开 SQLite 文件。"
                f" path={details['db_path']} exists={details['exists']}"
            ),
        ) from exc
    return db


def get_current_user(
    poiesis_token: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """从 HttpOnly Cookie 中解析 JWT，返回当前用户 payload。

    未登录或 token 无效时抛出 401。
    """
    from poiesis.api.services.auth_service import decode_access_token

    if not poiesis_token:
        raise HTTPException(status_code=401, detail="未登录，请先访问 /api/auth/login")
    payload = decode_access_token(poiesis_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return payload


def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """仅允许 admin 角色访问，否则抛出 403。"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return current_user
