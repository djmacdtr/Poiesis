#!/usr/bin/env bash
# scripts/rebuild.sh — 重新构建镜像并启动 Poiesis
# 适用场景：代码有更新后需要将变更打包进镜像
# 日常重启（代码无变更）请使用 scripts/up.sh（更快）
set -euo pipefail

# 推荐开启 BuildKit 以启用 pip/npm 缓存挂载，加速重复构建
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

echo "🔨 正在重新构建并启动 Poiesis 服务……"
docker compose up -d --build

echo ""
echo "✅ 构建完成，服务已启动："
echo "   🌐 Web 控制台：http://127.0.0.1:18080"
echo "   🔧 后端 API  ：http://127.0.0.1:18000"
echo ""
echo "💡 提示："
echo "   - 查看日志：docker compose logs -f"
echo "   - 停止服务：bash scripts/down.sh"
