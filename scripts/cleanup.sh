#!/usr/bin/env bash
# scripts/cleanup.sh — 清理 Docker BuildKit 缓存与无用镜像，释放磁盘空间
#
# 使用场景：
#   - 磁盘空间不足时（系统盘快写满）
#   - 定期维护，防止缓存无限积累
#
# 清理内容：
#   1. 删除 7 天前（168 小时）的 BuildKit builder 缓存
#   2. 删除所有停止的容器、未被使用的镜像、悬空网络与 build 缓存
#
# 注意：此脚本会删除所有项目的 build 缓存，下次构建将重新下载依赖
set -euo pipefail

echo "🧹 开始清理 Docker 缓存与无用资源……"
echo ""

# 第一步：清理 7 天前的 BuildKit builder 缓存（保留近期缓存以加速后续构建）
echo "📦 清理 7 天前的 BuildKit 构建缓存（--filter until=168h）……"
docker builder prune -af --filter "until=168h"
echo ""

# 第二步：清理所有停止的容器、未使用的镜像、悬空网络与剩余 build 缓存
echo "🗑️  清理停止的容器、未使用的镜像与网络……"
docker system prune -af
echo ""

echo "✅ 清理完成！磁盘空间已释放。"
echo ""
echo "💡 提示："
echo "   - 下次执行 'bash scripts/rebuild.sh' 时将重新下载依赖（首次构建耗时稍长）"
echo "   - 若要限制 BuildKit 缓存上限，请参阅 README 中的 daemon.json 配置示例"
