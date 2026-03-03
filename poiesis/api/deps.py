"""FastAPI 依赖注入：数据库连接与配置加载。"""

from __future__ import annotations

import os
from functools import lru_cache

from poiesis.config import Config, load_config
from poiesis.db.database import Database


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
    db.initialize_schema()
    return db
