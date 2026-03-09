"""审阅队列路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from poiesis.api.deps import get_db, require_admin
from poiesis.api.schemas.scene_runs import ReviewActionRequest, ReviewListResponse
from poiesis.api.services import scene_run_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/reviews", tags=["Scene Reviews"])


@router.get("", response_model=ReviewListResponse)
def list_reviews(
    book_id: int = Query(default=1, ge=1),
    db: Database = Depends(get_db),
) -> ReviewListResponse:
    """列出 review 队列。"""
    return ReviewListResponse(items=scene_run_service.list_review_queue(db, book_id))


@router.post("/{review_id}/approve")
def approve_review(
    review_id: int,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """批准 review。"""
    updated = scene_run_service.review_action(db, review_id, "approve")
    if updated is None:
        raise HTTPException(status_code=404, detail="review 不存在")
    return updated.model_dump(mode="json")


@router.post("/{review_id}/retry")
def retry_review(
    review_id: int,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """标记 retry。"""
    updated = scene_run_service.review_action(db, review_id, "retry")
    if updated is None:
        raise HTTPException(status_code=404, detail="review 不存在")
    return updated.model_dump(mode="json")


@router.post("/{review_id}/patch")
def patch_review(
    review_id: int,
    body: ReviewActionRequest,
    db: Database = Depends(get_db),
    _: Any = Depends(require_admin),
) -> dict[str, Any]:
    """提交 patch。"""
    updated = scene_run_service.review_action(db, review_id, "patch", body.patch_text)
    if updated is None:
        raise HTTPException(status_code=404, detail="review 不存在")
    return updated.model_dump(mode="json")
