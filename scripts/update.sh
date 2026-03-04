#!/usr/bin/env bash
# scripts/update.sh — 一键更新 Poiesis：拉取最新代码 + 清理旧镜像 + 重新构建部署
# 适用场景：服务器上执行代码更新并完整重部署
set -euo pipefail

# 推荐开启 BuildKit 以启用 pip/npm 缓存挂载，加速重复构建
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

echo "📥 正在拉取最新代码……"
git pull

echo ""
echo "🛑 正在停止旧服务……"
docker compose down

echo ""
echo "🧹 正在清理旧镜像（释放磁盘空间）……"
# 使用 compose 自身清理本项目的本地构建镜像，避免因项目名不匹配导致遗漏
docker compose down --rmi local 2>/dev/null || true

echo ""
echo "🔨 正在重新构建并启动 Poiesis 服务……"
docker compose up -d --build

echo ""
echo "✅ 更新完成，服务已启动："
echo "   🌐 Web 控制台：http://127.0.0.1:18080"
echo "   🔧 后端 API  ：http://127.0.0.1:18000"
echo ""
echo "💡 提示："
echo "   - 查看日志：docker compose logs -f"
echo "   - 停止服务：bash scripts/down.sh"
