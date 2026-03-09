"""新架构下的 canon explorer 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from poiesis.api.deps import get_db
from poiesis.api.schemas.world import CanonData
from poiesis.api.services import world_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/canon", tags=["Canon Explorer"])


@router.get("", response_model=CanonData)
def get_canon(book_id: int = Query(default=1, ge=1), db: Database = Depends(get_db)) -> CanonData:
    """复用新的 world repository 聚合 canon。"""
    return CanonData(**world_service.get_canon(db, book_id=book_id))
