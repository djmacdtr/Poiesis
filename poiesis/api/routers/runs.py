"""Scene 驱动 run 路由。"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from poiesis.api.deps import get_db, require_admin
from poiesis.api.schemas.scene_runs import (
    ChapterDetailResponse,
    RunDetailResponse,
    SceneDetailResponse,
    StartRunRequest,
    StartRunResponse,
)
from poiesis.api.services import scene_run_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/runs", tags=["Scene Runs"])


def _config_path() -> str:
    return os.environ.get("POIESIS_CONFIG", "config.yaml")


@router.post("", response_model=StartRunResponse)
def start_run(body: StartRunRequest, _: Any = Depends(require_admin)) -> StartRunResponse:
    """启动新的 scene 驱动 run。"""
    result = scene_run_service.start_run(_config_path(), body.chapter_count, body.book_id)
    return StartRunResponse(task_id=result["task_id"], status=result["status"])


@router.get("", response_model=list[dict[str, Any]])
def list_runs(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    """列出 runs。"""
    return [item.model_dump(mode="json") for item in scene_run_service.list_runs(db)]


@router.get("/{run_id}", response_model=RunDetailResponse)
def get_run_detail(run_id: int, db: Database = Depends(get_db)) -> RunDetailResponse:
    """读取 run 详情。"""
    payload = scene_run_service.get_run_detail(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在")
    return RunDetailResponse(**payload)


@router.get("/{run_id}/chapters/{chapter_number}", response_model=ChapterDetailResponse)
def get_chapter_detail(run_id: int, chapter_number: int, db: Database = Depends(get_db)) -> ChapterDetailResponse:
    """读取单章详情。"""
    payload = scene_run_service.get_chapter_detail(db, run_id, chapter_number)
    if payload is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    return ChapterDetailResponse(**payload)


@router.get(
    "/{run_id}/chapters/{chapter_number}/scenes/{scene_number}",
    response_model=SceneDetailResponse,
)
def get_scene_detail(
    run_id: int,
    chapter_number: int,
    scene_number: int,
    db: Database = Depends(get_db),
) -> SceneDetailResponse:
    """读取单个 scene 详情。"""
    payload = scene_run_service.get_scene_detail(db, run_id, chapter_number, scene_number)
    if payload is None:
        raise HTTPException(status_code=404, detail="scene 不存在")
    return SceneDetailResponse(**payload)
