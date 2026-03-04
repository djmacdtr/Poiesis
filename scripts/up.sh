#!/usr/bin/env bash
# scripts/up.sh — 日常启动 Poiesis（不重新构建镜像）
# 若需重新构建，请使用 scripts/rebuild.sh
set -euo pipefail

echo "🚀 正在启动 Poiesis 服务……"
docker compose up -d

echo ""
echo "✅ 服务已启动："
echo "   🌐 Web 控制台：http://127.0.0.1:18080"
echo "   🔧 后端 API  ：http://127.0.0.1:18000"
echo ""
echo "💡 提示："
echo "   - 首次启动请在浏览器打开 http://127.0.0.1:18080 并登录（默认账号 admin/admin，请及时修改密码）"
echo "   - 若服务器已配置外部 Nginx，请将其反代到 127.0.0.1:18080"
echo "   - 查看日志：docker compose logs -f"
echo "   - 如需重新构建（代码有更新）：bash scripts/rebuild.sh"
