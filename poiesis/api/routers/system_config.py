"""系统配置路由：GET/POST /api/system/config，POST /api/system/init。"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from poiesis.api.deps import get_db, require_admin
from poiesis.api.schemas.system_config import SystemConfigRequest, SystemConfigStatus
from poiesis.api.services import system_config_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/system", tags=["系统配置"])


@router.get("/config", response_model=SystemConfigStatus)
def get_system_config(
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> SystemConfigStatus:
    """获取系统配置状态（不返回明文 API Key，仅 admin 可访问）。"""
    return system_config_service.get_config_status(db)


@router.post("/config", response_model=SystemConfigStatus)
def save_system_config(
    body: SystemConfigRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> SystemConfigStatus:
    """保存或更新系统配置（API Key 加密存储，仅 admin 可操作）。"""
    try:
        return system_config_service.save_config(db, body)
    except system_config_service.EmbeddingConfigError as exc:
        raise HTTPException(status_code=422, detail=exc.to_detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class InitRequest(BaseModel):
    """初始化世界请求体。"""

    seed_path: str | None = None
    """可选：seed.yaml 文件路径（留空则使用默认路径）。"""


@router.post("/init")
def init_world(
    body: InitRequest | None = None,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, str]:
    """初始化世界数据库（仅 admin 可操作）。

    使用指定的 seed.yaml 路径（或默认路径）加载世界种子数据。
    """
    from poiesis.run_loop import RunLoop

    config_path = os.environ.get("POIESIS_CONFIG", "config.yaml")
    seed_path = body.seed_path if body else None

    try:
        loop = RunLoop(config_path=config_path)
        loop.load_world_seed(seed_path=seed_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail="世界种子文件不存在，请检查路径配置") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"初始化失败：{type(exc).__name__}") from exc

    return {"status": "ok", "message": "世界初始化完成"}
