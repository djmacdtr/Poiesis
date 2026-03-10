"""系统配置路由：GET/POST /api/system/config。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

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
