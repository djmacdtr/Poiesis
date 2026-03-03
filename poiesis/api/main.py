"""Poiesis FastAPI 服务入口。

启动方式：
    # 直接运行（开发模式）
    python -m poiesis.api.main --config path/to/config.yaml

    # 通过 CLI 子命令
    poiesis serve --config path/to/config.yaml

环境变量：
    POIESIS_CONFIG  配置文件路径（默认 config.yaml）
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from poiesis.api.routers import chapters, run, system_config, world

# 创建 FastAPI 应用
app = FastAPI(
    title="Poiesis API",
    description="Poiesis 后端 HTTP API，供前端控制台调用。",
    version="0.1.0",
)

# ──────────────────────────────────────────────
# CORS：允许前端本地开发服务器访问
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 默认开发端口
        "http://localhost:3000",  # 备用端口
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ──────────────────────────────────────────────
# 路由注册
# ──────────────────────────────────────────────
app.include_router(chapters.router)
app.include_router(world.router)
app.include_router(run.router)
app.include_router(system_config.router)


@app.get("/health", tags=["健康检查"])
def health_check() -> dict[str, str]:
    """健康检查端点，返回服务状态。"""
    return {"status": "ok", "service": "Poiesis API"}


# ──────────────────────────────────────────────
# 直接运行入口（python -m poiesis.api.main）
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="启动 Poiesis API 服务")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="开启热重载（开发模式）")
    args = parser.parse_args()

    # 将 config 路径写入环境变量，供 deps.py 读取
    os.environ["POIESIS_CONFIG"] = args.config

    uvicorn.run(
        "poiesis.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
