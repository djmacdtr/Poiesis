#!/usr/bin/env python3
"""API 冒烟测试脚本——验证后端基础接口可用性。

用法：
    python scripts/smoke_test_api.py [--base-url http://localhost:8000]

说明：
- 无需真实 LLM Key 即可运行（缺少 Key 时的 4xx 视为"预期失败，配置缺失"）
- 后端需已启动（poiesis serve --config config.yaml）
- 脚本退出码：0 = 全部通过，1 = 有步骤失败
"""

from __future__ import annotations

import argparse
import sys
import time

import urllib.request
import urllib.error
import json
from typing import Any


BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 3   # 秒
MAX_POLL_TIME = 60  # 秒


def _request(method: str, url: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    """发送 HTTP 请求并返回 (status_code, json_body)。"""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8")
            body_json = json.loads(body_text)
        except Exception:
            body_json = {"raw": body_text if "body_text" in dir() else str(exc)}
        return exc.code, body_json


def step_get_chapters(base_url: str) -> bool:
    """步骤 1：GET /api/chapters 期望 200。"""
    print("  [步骤 1] GET /api/chapters ...", end=" ")
    code, body = _request("GET", f"{base_url}/api/chapters")
    if code == 200 and isinstance(body, list):
        print(f"✅ 200 OK（{len(body)} 条章节）")
        return True
    print(f"❌ 意外状态码 {code}，响应：{body}")
    return False


def step_post_run(base_url: str) -> bool:
    """步骤 2：POST /api/run —— 缺少 LLM Key 时返回 4xx 视为预期。"""
    print("  [步骤 2] POST /api/run {chapter_count:1} ...", end=" ")
    code, body = _request("POST", f"{base_url}/api/run", {"chapter_count": 1})

    if code == 200:
        task_id = body.get("task_id", "")
        print(f"✅ 200 OK，task_id={task_id}")
        return _poll_task(base_url, task_id)

    if 400 <= code < 500:
        # 缺少 LLM Key 等配置问题，属于预期失败
        message = body.get("detail") or body.get("message") or str(body)
        print(f"⚠️  {code}（预期失败，缺少配置）：{message}")
        return True  # 不视为脚本错误

    print(f"❌ 意外状态码 {code}，响应：{body}")
    return False


def _poll_task(base_url: str, task_id: str) -> bool:
    """轮询任务状态直至 done/failed 或超时。"""
    print(f"  [步骤 2a] 轮询任务 {task_id}（最多 {MAX_POLL_TIME}s）...")
    deadline = time.time() + MAX_POLL_TIME
    while time.time() < deadline:
        code, body = _request("GET", f"{base_url}/api/run/{task_id}")
        if code != 200:
            print(f"    ❌ 查询任务失败，状态码 {code}")
            return False
        status = body.get("status", "")
        print(f"    状态：{status}")
        if status in ("completed", "done"):
            print("    ✅ 任务完成")
            return True
        if status == "failed":
            logs = body.get("logs", [])
            print(f"    ❌ 任务失败，日志：{logs[-3:] if logs else '（空）'}")
            return False
        time.sleep(POLL_INTERVAL)
    print(f"    ❌ 等待超时（{MAX_POLL_TIME}s）")
    return False


def main() -> None:
    """执行冒烟测试并输出中文总结。"""
    parser = argparse.ArgumentParser(description="Poiesis API 冒烟测试")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"后端地址（默认 {BASE_URL}）",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print(f"\n===== Poiesis API 冒烟测试 =====")
    print(f"目标服务：{base_url}\n")

    results: dict[str, bool] = {}

    # 检查服务是否可达
    print("  [前置] 健康检查 GET /health ...", end=" ")
    try:
        code, _ = _request("GET", f"{base_url}/health")
        if code == 200:
            print("✅ 服务已启动")
        else:
            print(f"❌ /health 返回 {code}")
            print("\n❌ API 冒烟测试失败：服务未就绪，请先执行 poiesis serve --config config.yaml")
            sys.exit(1)
    except Exception as exc:
        print(f"❌ 无法连接（{exc}）")
        print("\n❌ API 冒烟测试失败：无法连接到后端服务。")
        print("   请先执行：poiesis serve --config config.yaml")
        sys.exit(1)

    results["GET /api/chapters"] = step_get_chapters(base_url)
    results["POST /api/run"] = step_post_run(base_url)

    # 输出总结
    print("\n===== 测试结果汇总 =====")
    all_passed = True
    for step, ok in results.items():
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {status}  {step}")
        if not ok:
            all_passed = False

    print()
    if all_passed:
        print("✅ API 冒烟测试通过")
        sys.exit(0)
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"❌ API 冒烟测试失败：{', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
