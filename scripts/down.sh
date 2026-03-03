#!/usr/bin/env bash
# scripts/down.sh — 停止 Poiesis（Docker Compose）
set -euo pipefail

echo "🛑 正在停止 Poiesis 服务……"
docker compose down

echo ""
echo "✅ 服务已停止。数据已保留在 ./data/ 目录中。"
