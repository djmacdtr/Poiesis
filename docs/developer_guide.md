# Poiesis Developer Guide / 开发者指南

## Table of Contents / 目录

1. [Architecture Overview](#1-architecture-overview)
2. [Module Responsibilities](#2-module-responsibilities)
3. [How to Add a New LLM Provider](#3-how-to-add-a-new-llm-provider)
4. [How to Extend Verification Rules](#4-how-to-extend-verification-rules)
5. [How to Work with Scene Runs](#5-how-to-work-with-scene-runs)
6. [Database Notes](#6-database-notes)
7. [Vector Store Management](#7-vector-store-management)
8. [Running Tests](#8-running-tests)
9. [Configuration Reference](#9-configuration-reference)

---

## 1. Architecture Overview / 架构总览

Poiesis 已从旧的 chapter 黑盒编排切换到 `Scene 优先` 的正式架构。

当前主链：

```text
StoryPlanner
  -> ChapterPlanner
    -> ScenePlanner
      -> SceneWriter
        -> SceneExtractor
          -> SceneVerifier
            -> SceneEditor (when needed)
              -> ChapterAssembler
                -> ChapterSummarizer
```

### Runtime Model / 运行时模型

- `run`: 一次完整生成任务
- `chapter`: 章节级目标和 scene 聚合结果
- `scene`: 一等执行单元
- `review`: scene 级人工处理入口（人工审阅队列）
- `loop`: 故事承诺 / 伏笔 / 未闭合叙事线

### Persistence Model / 持久化模型

数据库已围绕 scene 工作流重构，核心表包括：

- `runs`
- `run_chapters`
- `run_scenes`
- `story_state_snapshots`
- `loops`
- `loop_events`
- `scene_reviews`
- `scene_patches`
- `chapter_outputs`

旧 `/api/run/*` 和旧 `RunLoop` 主入口已移除。

---

## 2. Module Responsibilities / 模块职责

| Module（模块） | Responsibility（职责） |
|---|---|
| `poiesis/config.py` | 配置模型与 `load_config()` |
| `poiesis/db/database.py` | SQLite 持久化层 |
| `poiesis/domain/world/model.py` | `WorldModel` 领域对象 |
| `poiesis/domain/world/repository.py` | 世界状态装载与标准化 |
| `poiesis/application/scene_contracts.py` | Scene 架构核心协议 |
| `poiesis/application/use_cases.py` | 显式 use case（用例）组合 |
| `poiesis/api/services/scene_run_service.py` | 新架构运行入口、世界初始化、同步/异步 run |
| `poiesis/pipeline/planning/story_planner.py` | 章节级故事规划 |
| `poiesis/pipeline/planning/chapter_planner.py` | StoryPlan -> ChapterPlan |
| `poiesis/pipeline/planning/scene_planner.py` | ChapterPlan -> ScenePlan[] |
| `poiesis/pipeline/writing/scene_writer.py` | scene 正文生成 |
| `poiesis/pipeline/extraction/scene_extractor.py` | scene 变更提取适配层 |
| `poiesis/pipeline/extraction/extractor_hub.py` | ChangeSet 聚合与分类 |
| `poiesis/pipeline/verification/scene_verifier.py` | scene 校验适配层 |
| `poiesis/pipeline/verification/hub.py` | VerifierHub 聚合 |
| `poiesis/pipeline/writing/scene_editor.py` | scene 重写 |
| `poiesis/pipeline/assembly/chapter_assembler.py` | chapter 聚合 |
| `poiesis/pipeline/summary/summarizer.py` | 章节摘要生成 |
| `poiesis/api/routers/runs.py` | run / chapter / scene 查询与启动 |
| `poiesis/api/routers/reviews.py` | review 队列与动作 |
| `poiesis/api/routers/loops.py` | loop board |
| `poiesis/api/routers/canon.py` | canon explorer |

---

## 3. How to Add a New LLM Provider / 如何新增 LLM 提供商

1. 新建 `poiesis/llm/<provider>_client.py`
2. 继承 `LLMClient`
3. 实现 `_complete` / `_complete_json`
4. 在 `poiesis/api/services/scene_run_service.py` 的 `_build_llm()` 中注册新 provider
5. 在 `pyproject.toml` 中补充依赖

示例：

```python
from poiesis.llm.base import LLMClient


class MyProviderClient(LLMClient):
    def __init__(self, model: str, temperature: float, max_tokens: int) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)

    def _complete(self, prompt: str, system: str | None = None, **kwargs) -> str:
        ...

    def _complete_json(self, prompt: str, system: str | None = None, **kwargs) -> dict:
        ...
```

---

## 4. How to Extend Verification Rules / 如何扩展校验规则

当前建议不要再往旧风格的“一个 verifier 文件里加私有方法”扩展，而是继续沿用 hub 拆分方式。

### 添加新的规则子校验器

1. 在 `poiesis/pipeline/verification/` 下新增文件，例如 `loop_verifier.py`
2. 返回统一的 `VerifierIssue[]`
3. 在 `VerifierHub` 中按固定顺序注册

最小接口形态建议：

```python
from poiesis.application.contracts import VerifierIssue


class LoopVerifier:
    def verify(self, world, proposed_changes) -> list[VerifierIssue]:
        return []
```

### 修改语义校验 Prompt（提示词）

编辑 `prompts/verifier.txt`。当前语义校验统一由 `LLMSemanticVerifier` 负责。

---

## 5. How to Work with Scene Runs / 如何使用 Scene Runs

### 启动一个 run（运行任务）

- API: `POST /api/runs`
- CLI: `poiesis run --config config.yaml --max-chapters 2`

### 读取运行详情

- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/chapters/{chapter_number}`
- `GET /api/runs/{run_id}/chapters/{chapter_number}/scenes/{scene_number}`

### 处理 review（审阅动作）

- `GET /api/reviews`
- `POST /api/reviews/{review_id}/approve`
- `POST /api/reviews/{review_id}/retry`
- `POST /api/reviews/{review_id}/patch`

### 查询 loops（剧情线索）

- `GET /api/loops`

---

## 6. Database Notes / 数据库说明

当前数据库按新模型设计，不再考虑旧 schema 兼容。

### 结构原则

- `scene` 是一等实体
- `trace`（轨迹）、`review`（审阅）、`patch`（修补）、`state snapshot`（状态快照）分表存储
- `canon` 与 `process` 数据分层
- 稳定领域对象优先结构化表字段；不稳定 payload（载荷）再放 JSON

### 初始化方式

```python
from poiesis.db.database import Database

db = Database("poiesis.db")
db.initialize_schema()
```

---

## 7. Vector Store Management / 向量存储管理

向量存储仍由 `poiesis/vector_store/store.py` 管理。

### 存储布局

```text
vector_store/
├── index.faiss
└── metadata.pkl
```

### 重要说明

- 更换 embedding model（嵌入模型）后，需要重建 `vector_store/`
- 当前 scene 主链仍会使用向量检索作为 prompt（提示词）上下文补充

---

## 8. Running Tests / 运行测试

```bash
pip install -e ".[dev]"
ruff check poiesis tests
mypy poiesis
pytest
cd frontend && npm run build
```

如果需要验证容器链路（Docker smoke）：

```bash
docker build -f docker/Dockerfile.api -t ghcr.io/djmacdtr/poiesis-api:ci-smoke --build-arg EMBEDDING_MODE=dummy .
docker build -f docker/Dockerfile.web -t ghcr.io/djmacdtr/poiesis-web:ci-smoke .
docker compose up -d
```

---

## 9. Configuration Reference / 配置参考

| Key（配置项） | Type（类型） | Default（默认值） | Description（说明） |
|---|---|---|---|
| `llm.provider` | string | `"openai"` | writer / scene writer 使用的 provider |
| `llm.model` | string | `"gpt-4o"` | writer 模型 |
| `planner_llm.provider` | string | `"openai"` | planner / verifier 使用的 provider |
| `planner_llm.model` | string | `"gpt-4o"` | planner 模型 |
| `generation.max_chapters` | int | `100` | CLI 默认最大章节数 |
| `generation.rewrite_retries` | int | `3` | scene 重写上限 |
| `generation.new_rule_budget` | int | `5` | 单章新规则预算 |
| `generation.target_word_count` | int | `3000` | 目标章节字数 |
| `database.path` | string | `"poiesis.db"` | SQLite 文件路径 |
| `vector_store.path` | string | `"vector_store"` | 向量索引目录 |
| `vector_store.embedding_model` | string | `"all-MiniLM-L6-v2"` | embedding model |
