# Poiesis

> **自主长篇叙事生成引擎**

Poiesis 是一个基于 Python 3.11+ 的框架，可使用大语言模型（LLM）生成连贯、自洽的长篇小说。
它强制执行世界规则的不变性，跨章节追踪叙事连续性，并维护一个随故事发展而演进的动态世界模型——
全程无需人工干预。

---

## 架构

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

## 快速开始

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

## 许可证

Apache-2.0 — 详见 [LICENSE](LICENSE)。
