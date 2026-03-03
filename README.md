# Poiesis

> **自主长篇叙事生成引擎**

Poiesis 是一个基于 Python 3.11+ 的框架，可使用大语言模型（LLM）生成连贯、自洽的长篇小说。
它强制执行世界规则的不变性，跨章节追踪叙事连续性，并维护一个随故事发展而演进的动态世界模型——
全程无需人工干预。

---

## 🚀 推荐：Docker 一键启动（部署/演示）

```bash
# 1. 克隆仓库
git clone https://github.com/djmacdtr/Poiesis.git && cd Poiesis

# 2. 准备环境变量（填写 POIESIS_SECRET_KEY 与管理员密码）
cp .env.example .env

# 3. 创建数据持久化目录
mkdir -p data

# 4. 一键启动（首次构建约需 2~5 分钟）
docker compose up -d --build
# 或：bash scripts/up.sh
```

访问：
- **Web 控制台**：http://127.0.0.1:18080
- **后端 API**：http://127.0.0.1:18000（调试用，仅本机）

启动后在浏览器中完成：
1. 登录（默认账号 `admin`，密码见 `.env` 中的 `POIESIS_ADMIN_PASS`）
2. **系统设置** → 配置 OpenAI/Anthropic API Key
3. **系统设置** → 点击 **初始化世界**
4. **运行控制** → 设置章节数 → 点击 **开始生成**

**初始化世界（首次，也可通过浏览器完成）：**

```bash
docker compose run --rm api poiesis init \
    --config /app/config.yaml \
    --seed /app/examples/world_seed.yaml
```

**常见问题：**

- 页面能打开但 `/api` 返回 404 → 检查 `docker/nginx.conf` 中 `/api/` 的 `proxy_pass` 配置
- 触发生成任务后报错（缺少 Key）→ 属于预期，在浏览器系统设置或 `.env` 中配置 API Key
- 服务启动失败（embedding 下载超时）→ 在 `.env` 设置 `POIESIS_EMBEDDING_MODE=dummy` 先跑通页面
- 数据持久化在 `data/` 目录 → 备份时复制该目录即可

> **安全提醒**：生产环境请务必在 `.env` 中设置强密码的 `POIESIS_SECRET_KEY` 和 `POIESIS_ADMIN_PASS`。

---

## 部署模式对照

| 模式 | 适用场景 | 启动方式 |
|------|----------|----------|
| 部署/演示（推荐） | 首次体验、生产部署 | `docker compose up -d --build` |
| 开发联调（可选） | 前端/后端本地调试 | `poiesis serve` + Vite（见下方章节） |

---

```
世界种子 (YAML)
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│                        RunLoop（运行循环）                   │
│                                                             │
│  ┌──────────┐  计划   ┌──────────┐  内容    ┌──────────┐   │
│  │ Planner  │────────▶│  Writer  │─────────▶│Extractor │   │
│  │（规划器） │         │（写作器）│          │（提取器）│   │
│  └──────────┘         └──────────┘          └────┬─────┘   │
│                                           变更│            │
│  ┌──────────┐  重写   ┌──────────┐             ▼           │
│  │  Editor  │◀────────│ Verifier │◀──────── WorldModel      │
│  │（编辑器）│         │（验证器）│          （世界模型）     │
│  └──────────┘         └──────────┘          （3层结构）     │
│       │                                          │          │
│       └──────── 已修正 ──────────── ┌─────────────┘         │
│                                    │  Merger（合并器）       │
│  ┌─────────────┐                   │  Summarizer（摘要器）   │
│  │Originality  │◀──── 章节文本     │  DB + VectorStore      │
│  │ Checker     │                   └────────────────────────┘
│  │（原创检测器）│                                            │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
   poiesis.db  +  vector_store/
```

### 三层世界知识模型

| 层级       | 内容                           | 可变性               |
|------------|--------------------------------|----------------------|
| `canon`    | 已审批的权威世界事实           | 追加 / 更新          |
| `staging`  | 来自新章节的待审改动           | 待审核               |
| `archive`  | 已拒绝的改动及原因             | 不可变审计日志       |

---

## CLI 模式（高级/开发者）

### 1. 安装

```bash
pip install -e ".[dev]"
```

### 2. 设置 API 密钥

```bash
export OPENAI_API_KEY="sk-..."
# 或
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. 初始化世界

```bash
poiesis init --config config.yaml --seed examples/world_seed.yaml
```

### 4. 生成章节

```bash
# 按 config.yaml 中设定的 max_chapters 生成
poiesis run --config config.yaml

# 覆盖最大章节数
poiesis run --config config.yaml --max-chapters 5

# 查看当前进度
poiesis status --config config.yaml
```

### 5. 直接使用 Python API

```python
from poiesis.run_loop import RunLoop

loop = RunLoop(config_path="config.yaml")
loop.load_world_seed()
loop.run(max_chapters=10)
```

---

## 配置参考

所有设置均位于 `config.yaml`，完整示例见 `examples/config.yaml`。

```yaml
llm:
  provider: "openai"          # 可选 "openai" 或 "anthropic"
  model: "gpt-4o"
  temperature: 0.8
  max_tokens: 4000

planner_llm:                  # 规划专用 LLM，温度较低以确保结构稳定
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.3
  max_tokens: 2000

similarity:
  originality_threshold: 0.85 # 余弦相似度超过该阈值时标记为重复风险
  fact_retrieval_k: 10
  chapter_similarity_k: 5

generation:
  max_chapters: 100
  rewrite_retries: 3          # 每次验证失败后编辑器的最大重试次数
  new_rule_budget: 5          # 每章最多允许引入的新世界事实数
  target_word_count: 3000

database:
  path: "poiesis.db"

vector_store:
  path: "vector_store"
  embedding_model: "all-MiniLM-L6-v2"

world_seed: "examples/world_seed.yaml"
```

---

## 模块说明

| 模块                              | 功能描述                                         |
|-----------------------------------|--------------------------------------------------|
| `poiesis/config.py`               | Pydantic v2 配置模型 + `load_config()` 加载函数  |
| `poiesis/db/database.py`          | 所有世界状态的 SQLite 持久化管理                 |
| `poiesis/llm/base.py`             | 带重试逻辑的抽象 `LLMClient` 基类               |
| `poiesis/llm/openai_client.py`    | OpenAI Chat Completions 接口实现                 |
| `poiesis/llm/anthropic_client.py` | Anthropic Messages API 接口实现                  |
| `poiesis/vector_store/store.py`   | 基于 FAISS + sentence-transformers 的向量存储    |
| `poiesis/world.py`                | `WorldModel` — 三层知识管理                      |
| `poiesis/planner.py`              | `ChapterPlanner` — 结构化 JSON 章节规划          |
| `poiesis/writer.py`               | `ChapterWriter` — 根据规划生成散文               |
| `poiesis/extractor.py`            | `FactExtractor` — 从文本中挖掘新世界事实         |
| `poiesis/verifier.py`             | `ConsistencyVerifier` — 检测规则违反             |
| `poiesis/editor.py`               | `ChapterEditor` — 针对违规的精准重写             |
| `poiesis/merger.py`               | `WorldMerger` — 将已批准的改动应用到 canon 层    |
| `poiesis/summarizer.py`           | `ChapterSummarizer` — 生成章节存档摘要           |
| `poiesis/originality.py`          | `OriginalityChecker` — 余弦相似度原创性检测      |
| `poiesis/run_loop.py`             | `RunLoop` — 完整生成管线的编排与调度             |
| `poiesis/cli.py`                  | Click 命令行接口：`run`、`init`、`status`        |

---

## 运行测试

```bash
pytest                  # 运行全部测试并生成覆盖率报告
pytest --no-cov -v      # 详细输出，不生成覆盖率报告
pytest tests/test_database.py -v
```

---

## 后端 API 服务

Poiesis 内置了一个基于 **FastAPI** 的 HTTP API 服务层，供前端控制台（`frontend/`）调用真实数据。

### 启动 API 服务

```bash
# 方式一：通过 CLI 子命令（推荐）
poiesis serve --config config.yaml

# 方式二：直接运行模块
python -m poiesis.api.main --config config.yaml

# 可选参数
poiesis serve --config config.yaml --host 127.0.0.1 --port 8000 --reload
```

服务默认监听 `http://localhost:8000`，可通过 `--host` / `--port` 调整。

启动后可访问自动生成的 API 文档：
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `POIESIS_CONFIG` | 配置文件路径（同 `--config`） | `config.yaml` |
| `POIESIS_EMBEDDING_MODE` | Embedding 模式：`real`（sentence-transformers 真实向量）或 `dummy`（离线哈希向量，用于测试/CI） | `real` |

#### POIESIS_EMBEDDING_MODE 说明

- **`real`**（默认）：使用 `sentence-transformers` 加载语义模型（`all-MiniLM-L6-v2`），首次使用时会从 HuggingFace 下载模型。
- **`dummy`**：使用确定性 SHA-256 哈希生成 384 维向量，纯本地、零网络依赖。  
  适用场景：pytest、GitHub Actions CI、任何无外网环境。  
  **注意**：dummy 向量不具备语义相似度，不得用于生产相似度判断。

```bash
# 使用 dummy 模式运行测试（无网络）
POIESIS_EMBEDDING_MODE=dummy pytest

# 生产运行使用真实 embedding（默认）
poiesis serve --config config.yaml
```

---

## 冒烟测试

使用 `scripts/smoke_test_api.py` 对已启动的后端进行一键联调验证：

```bash
# 1. 先启动后端
poiesis serve --config config.yaml

# 2. 另开终端执行冒烟测试
python scripts/smoke_test_api.py

# 可选：指定非默认地址
python scripts/smoke_test_api.py --base-url http://localhost:8000
```

脚本行为：
- `GET /api/chapters`：期望 200，可为空列表
- `POST /api/run`：若未配置 LLM Key 返回 4xx，脚本视为"预期失败（缺少配置）"并继续；若配置齐全则轮询任务直至完成（最多 60 秒）
- 最终输出中文总结："API 冒烟测试通过/失败"

---

## 本地开发联调（可选）

### 1. 配置前端 API 地址

在 `frontend/` 目录下，复制并编辑环境变量文件：

```bash
cd frontend
cp .env.example .env.local
# 编辑 .env.local，设置：
# VITE_API_BASE_URL=http://localhost:8000
```

### 2. 启动后端

```bash
# 在项目根目录
poiesis serve --config config.yaml
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
# 前端默认运行在 http://localhost:5173
```

### 4. 最小联调验收流程

1. 打开浏览器访问 `http://localhost:5173`（Dashboard 页面）
2. 查看 **章节列表**（Chapters 页面）——确认能看到已生成的章节
3. 点击 **Run**，设置章节数为 1，触发生成任务
4. 通过轮询 `GET /api/run/{task_id}` 或刷新 Chapters 页面，确认新章节出现
5. 如有 staging 变更，在 **Staging** 页面审批或拒绝

### 已实现接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/chapters` | 章节列表 |
| GET | `/api/chapters/{id}` | 章节详情 |
| GET | `/api/world/canon` | Canon 快照（规则/角色/时间线/伏笔） |
| GET | `/api/world/staging` | Staging 变更列表（可 `?status=pending` 筛选） |
| POST | `/api/world/staging/{id}/approve` | 批准变更 |
| POST | `/api/world/staging/{id}/reject` | 拒绝变更（必须提供 `reason`） |
| POST | `/api/run` | 启动写作任务 |
| GET | `/api/run/{task_id}` | 查询任务状态与日志 |
| GET | `/api/run/{task_id}/events` | SSE 实时日志流 |
| GET | `/health` | 健康检查 |

---

## 参与贡献

1. Fork 本仓库并创建功能分支。
2. 安装开发依赖：`pip install -e ".[dev]"`
3. 安装 pre-commit 钩子：`pre-commit install`
4. 为新功能编写测试用例。
5. 确保 `ruff check poiesis tests` 和 `mypy poiesis` 通过检查。
6. 向 `main` 分支提交 Pull Request。

### 添加新的 LLM 提供商

参见 [docs/developer_guide.md](docs/developer_guide.md#3-how-to-add-a-new-llm-provider)。

### 扩展验证规则

参见 [docs/developer_guide.md](docs/developer_guide.md#4-how-to-extend-verification-rules)。

---

## 生产部署（服务器 Nginx 反代）

Docker compose 只提供应用容器，不直接监听公网 80/443 端口。
生产环境推荐使用服务器上已有的 Nginx 统一管理 HTTPS 与域名，Docker 仅作为应用容器运行。

### 架构说明

```
外部请求（浏览器）
      │ HTTPS 443（或 HTTP 80）
      ▼
 服务器 Nginx（宿主机）          ← 负责 SSL 证书、域名、访问控制
      │ proxy_pass http://127.0.0.1:18080
      ▼
 Docker web 容器（Nginx）        ← 托管前端静态文件，内部反代 /api
      │ proxy_pass http://api:8000
      ▼
 Docker api 容器（FastAPI）      ← Poiesis 后端
```

### 服务器 Nginx 示例配置

将以下配置添加到服务器 Nginx 的 `sites-available/` 目录（如 `/etc/nginx/sites-available/poiesis`）：

```nginx
# Poiesis Web 控制台 — 服务器 Nginx 反代配置示例
# 将外部请求转发到 Docker 容器的 web 服务（127.0.0.1:18080）

server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或服务器 IP

    # 如已配置 HTTPS，可在此添加 HTTP → HTTPS 跳转：
    # return 301 https://$host$request_uri;

    location / {
        # 反代到 Docker web 容器
        proxy_pass         http://127.0.0.1:18080;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        # SSE 实时日志流需要关闭缓冲
        proxy_buffering    off;
        proxy_read_timeout 300s;
    }
}

# HTTPS 配置示例（需先用 certbot 申请证书）
# server {
#     listen 443 ssl;
#     server_name your-domain.com;
#
#     ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
#     ssl_protocols       TLSv1.2 TLSv1.3;
#
#     location / {
#         proxy_pass         http://127.0.0.1:18080;
#         proxy_http_version 1.1;
#         proxy_set_header   Host              $host;
#         proxy_set_header   X-Real-IP         $remote_addr;
#         proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
#         proxy_set_header   X-Forwarded-Proto $scheme;
#         proxy_buffering    off;
#         proxy_read_timeout 300s;
#     }
# }
```

启用配置并重载 Nginx：

```bash
sudo ln -s /etc/nginx/sites-available/poiesis /etc/nginx/sites-enabled/poiesis
sudo nginx -t          # 语法检查
sudo systemctl reload nginx
```

### 配置 HTTPS（Let's Encrypt）

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
# certbot 会自动修改 nginx 配置并续期证书
```

---

## 许可证

Apache-2.0 — 详见 [LICENSE](LICENSE)。
