# Poiesis
### Narrative Generation Engine for Long-Form Fiction

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-Frontend-61DAFB?logo=react&logoColor=0B0F19">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-AGPLv3-black">
</p>

> 🚀 自托管长篇叙事生成引擎（Web Console + API + Optional Embedding Service）
> 🎯 聚焦“持续一致性”而不是“一次性生成”。

---

## ✨ Why Poiesis

- 🧠 **Consistency First**: 通过 world model 维护角色、规则、时间线、伏笔一致性
- 🛠️ **Operational Ready**: 内置控制台、任务编排、审批流、统计页
- 🔌 **Deployment Flexible**: 默认轻量模式，按需切换 remote embedding
- 🧩 **Composable Pipeline**: Planner -> Writer -> Extractor -> Verifier -> Editor -> Merger -> Summarizer

---

## 🏗️ Architecture

### 🧭 System Topology

```mermaid
flowchart LR
  U[Browser]
  W[Web Container\nNginx + SPA]
  A[Poiesis API\nFastAPI]
  EL[Local Embedding\nDeterministic Hash]
  ER[Embedding Service\npoiesis-embed]
  DB[(SQLite\npoiesis.db)]
  VS[(vector_store/)]

  U -->|HTTP| W
  W -->|/api| A
  A -->|local mode| EL
  A -->|remote mode| ER
  A --> DB
  A --> VS
```

### 🔄 Generation Pipeline (RunLoop)

```mermaid
flowchart TD
  Seed[World Seed\nYAML] --> RL

  subgraph RL[RunLoop]
    P[Planner\n规划器] -->|计划| W[Writer\n写作器]
    W -->|章节内容| X[Extractor\n提取器]
    X -->|proposed changes| V[Verifier\n验证器]
    V -->|violations| E[Editor\n编辑器]
    E -->|已修正内容| V

    WM[WorldModel\ncanon / staging / archive] --> P
    WM --> X
    WM --> V
    V -->|通过| M[Merger\n合并器]
    X --> M

    W --> O[Originality Checker\n原创检测]
    M --> S[Summarizer\n摘要器]
  end

  M --> DB[(poiesis.db)]
  M --> VS[(vector_store/)]
  S --> DB
  O --> VS
```

### 🧱 Three-Layer World Model

| Layer | 内容 | 可变性 |
|---|---|---|
| `canon` | 已审批的权威世界事实 | 追加 / 更新 |
| `staging` | 来自新章节的待审改动 | 待审核 |
| `archive` | 已拒绝改动及原因 | 不可变审计日志 |

---

## 🖥️ System Requirements

### ⚡ 轻量模式（local embedding）最低配置

| 资源 | 最低要求 |
|---|---|
| CPU | 2 核 |
| 内存 | 2 GB |
| 磁盘 | 2 GB（镜像约 550MB + 数据目录） |

### 🚀 完整模式（remote embedding + embed 服务）推荐配置

| 资源 | 推荐配置 | 最低可用 |
|---|---|---|
| CPU | 4 核 | 2 核（较慢） |
| 内存 | 8 GB | 4 GB（可能较慢或 OOM） |
| 磁盘 | 10 GB | 含镜像约 3.5GB + 模型缓存约 90MB + 数据目录 |

---

## 🚀 Quick Start (Docker)

### 1. 📦 Prepare

```bash
git clone https://github.com/djmacdtr/Poiesis.git
cd Poiesis
cp .env.example .env
mkdir -p data
```

### 2. ▶️ Start (lightweight mode, default)

```bash
docker compose pull
docker compose up -d
```

### 3. ✅ Verify

```bash
docker compose ps
curl -I http://127.0.0.1:18080/
curl -I http://127.0.0.1:18080/openapi.json
```

### 4. 🌐 Open Console

- Web: `http://127.0.0.1:18080`
- API: `http://127.0.0.1:18000`

首次进入建议流程：
1. 登录（默认账号 `admin`，密码见 `.env` 的 `POIESIS_ADMIN_PASS`）
2. 在系统设置配置 OpenAI/Anthropic Key
3. 初始化世界（UI 或 CLI）
4. 在 Run 页面设置章节数并启动任务

---

## 🎛️ Deployment Modes

| Mode | Command | Use Case |
|---|---|---|
| `local` (default) | `docker compose up -d` | 快速启动、低资源、离线可用 |
| `remote` (semantic) | `docker compose --profile full up -d` | 真实语义检索与更强一致性 |

完整模式需要在 `.env` 中设置：

```dotenv
POIESIS_EMBEDDING_PROVIDER=remote
POIESIS_EMBEDDING_URL=http://embed:9000
```

---

## 🛠️ Local Development (Minimal)

```bash
# Backend
pip install -e ".[dev]"
poiesis serve --config config.yaml

# Frontend
cd frontend
npm install
npm run dev
```

---

## 📚 Documentation

- Developer Guide: `docs/developer_guide.md`
- Frontend Guide: `frontend/README.md`
- Docker Topology: `docker-compose.yml`
- API Smoke Test: `scripts/smoke_test_api.py`

---

## 🧯 Common Issues

- `/api` 返回 502: 确认 `api` 容器健康且 `web` 可解析服务名 `api`
- 运行任务报缺少 Key: 在系统设置或 `.env` 补齐 LLM Key
- 选择 `remote` provider 失败: 使用 `--profile full` 启动并检查 `embed` 健康状态

---

## 🤝 Contributing

参与贡献

1. Fork 本仓库并创建功能分支。
2. 如需添加新功能，请先通过 Issue 讨论需求与方案。
3. 安装开发依赖：`pip install -e ".[dev]"`
4. 安装 pre-commit 钩子：`pre-commit install`
5. 为新功能编写测试用例。
6. 确保 `ruff check poiesis tests` 和 `mypy poiesis` 通过检查。
7. 向 `main` 分支提交 Pull Request。

添加新的 LLM 提供商

参见 `docs/developer_guide.md`。

扩展验证规则

参见 `docs/developer_guide.md`。

如果喜欢本项目，欢迎点亮 Star，并通过 Issue 或 Pull Request 提交反馈与改进建议。

---

## 📄 License

本项目采用 GNU AGPLv3 协议：允许使用、修改与分发；若将修改版本用于对外网络服务，也需向用户提供对应源码。

GNU AGPLv3. See `LICENSE`.
