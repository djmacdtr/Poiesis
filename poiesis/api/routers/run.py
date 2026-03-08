"""运行任务路由：POST /api/run, GET /api/run/{task_id}。"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from poiesis.api.deps import require_admin
from poiesis.api.schemas.run import RunRequest, RunResponse, TaskDetail
from poiesis.api.services import run_service
from poiesis.api.task_registry import registry

router = APIRouter(prefix="/api/run", tags=["运行任务"])


def _config_path() -> str:
    """从环境变量读取 config 路径，默认为 config.yaml。"""
    return os.environ.get("POIESIS_CONFIG", "config.yaml")


@router.post("", response_model=RunResponse)
def start_run(
    body: RunRequest,
    _: Any = Depends(require_admin),
) -> RunResponse:
    """启动后台写作任务，立即返回 task_id（非阻塞，仅 admin 可操作）。"""
    if body.chapter_count < 1:
        raise HTTPException(status_code=422, detail="chapter_count 必须大于 0")
    if body.book_id < 1:
        raise HTTPException(status_code=422, detail="book_id 必须大于 0")
    task_dict = run_service.start_run(
        config_path=_config_path(),
        chapter_count=body.chapter_count,
        book_id=body.book_id,
    )
    return RunResponse(
        task_id=task_dict["task_id"],
        status=task_dict["status"],
        message=f"已创建任务，将生成 {body.chapter_count} 章",
    )


@router.get("", response_model=list[TaskDetail])
def list_tasks() -> list[TaskDetail]:
    """查询任务列表（按最近更新时间倒序，无需认证）。"""
    task_dicts = run_service.list_tasks()
    return [TaskDetail(**item) for item in task_dicts]


@router.delete("/history")
def prune_task_history(
    keep: int = Query(default=20, ge=0, le=500),
    _: Any = Depends(require_admin),
) -> dict[str, int]:
    """清理历史任务（保留运行中任务 + 最近 N 条已结束任务）。"""
    return run_service.prune_task_history(keep_recent=keep)


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: str) -> TaskDetail:
    """查询任务状态与最近日志（供前端轮询，无需认证）。"""
    task_dict = run_service.get_task(task_id)
    if task_dict is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return TaskDetail(**task_dict)


@router.get("/{task_id}/events")
def task_events(task_id: str) -> StreamingResponse:
    """SSE 日志流（前端如暂未接入 SSE，可先保留此接口备用）。"""
    task = registry.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    def _event_generator() -> Generator[str, None, None]:
        sent = 0
        sent_preview_chars = 0

        if task.preview_text:
            payload = {"delta": task.preview_text}
            yield f"event: preview\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            sent_preview_chars = len(task.preview_text)

        while True:
            logs = task.logs
            for line in logs[sent:]:
                payload = {"message": line}
                yield f"event: log\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                sent += 1

            preview_text = task.preview_text
            if len(preview_text) > sent_preview_chars:
                delta = preview_text[sent_preview_chars:]
                payload = {"delta": delta}
                yield f"event: preview\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                sent_preview_chars = len(preview_text)

            if task.status in ("completed", "failed", "interrupted"):
                payload = {"status": task.status}
                yield f"event: status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break
            time.sleep(1)

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
