"""世界设定路由：Canon 查询与 Staging 审批。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from poiesis.api.deps import get_db, require_admin
from poiesis.api.schemas.world import (
    ApproveRequest,
    CanonData,
    RejectRequest,
    StagingChange,
)
from poiesis.api.services import world_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/world", tags=["世界设定"])


@router.get("/canon", response_model=CanonData)
def get_canon(db: Database = Depends(get_db)) -> CanonData:
    """获取完整的 Canon 快照（世界规则、角色、时间线、伏笔）。"""
    data = world_service.get_canon(db)
    return CanonData(**data)


@router.get("/staging", response_model=list[StagingChange])
def list_staging(
    status: str | None = Query(default=None, description="过滤状态：pending/approved/rejected"),
    db: Database = Depends(get_db),
) -> list[StagingChange]:
    """获取 staging 变更列表，不传 status 则返回全部。"""
    rows = world_service.list_staging(db, status=status)
    return [StagingChange(**r) for r in rows]


@router.post("/staging/{change_id}/approve", response_model=StagingChange)
def approve_staging(
    change_id: int,
    body: ApproveRequest | None = None,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> StagingChange:
    """批准指定 staging 变更（仅 admin 可操作）。"""
    row = world_service.approve_staging(db, change_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"staging 变更 id={change_id} 不存在")
    return StagingChange(**row)


@router.post("/staging/{change_id}/reject", response_model=StagingChange)
def reject_staging(
    change_id: int,
    body: RejectRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> StagingChange:
    """拒绝指定 staging 变更，必须提供拒绝原因（仅 admin 可操作）。"""
    row = world_service.reject_staging(db, change_id, body.reason)
    if row is None:
        raise HTTPException(status_code=404, detail=f"staging 变更 id={change_id} 不存在")
    return StagingChange(**row)
