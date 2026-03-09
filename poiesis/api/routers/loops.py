"""Loop board 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from poiesis.api.deps import get_db
from poiesis.api.schemas.scene_runs import LoopListResponse
from poiesis.api.services import scene_run_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/loops", tags=["Loop Board"])


@router.get("", response_model=LoopListResponse)
def list_loops(book_id: int = Query(default=1, ge=1), db: Database = Depends(get_db)) -> LoopListResponse:
    """返回 loop 列表。"""
    return LoopListResponse(items=scene_run_service.list_loops(db, book_id))
