# Poiesis

> **Autonomous long-form narrative generation engine**

Poiesis is a Python 3.11+ framework for generating coherent, self-consistent novels
with an LLM. It enforces world-rule immutability, tracks narrative continuity across
chapters, and maintains a living world model that evolves as the story unfolds —
all without human intervention.

---

## Architecture

```
World Seed (YAML)
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│                        RunLoop                              │
│                                                             │
│  ┌──────────┐   plan   ┌──────────┐  content  ┌──────────┐ │
│  │ Planner  │─────────▶│  Writer  │──────────▶│Extractor │ │
│  └──────────┘          └──────────┘           └────┬─────┘ │
│                                              changes│       │
│  ┌──────────┐  rewrite ┌──────────┐               ▼        │
│  │  Editor  │◀─────────│ Verifier │◀──────── WorldModel     │
│  └──────────┘          └──────────┘           (3 layers)   │
│       │                                            │        │
│       └──────── corrected ──────────── ┌───────────┘        │
│                                        │  Merger            │
│  ┌─────────────┐                       │  Summarizer        │
│  │Originality  │◀──── chapter text     │  DB + VectorStore  │
│  │  Checker    │                       └────────────────────┘
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
   poiesis.db  +  vector_store/
```

### Three-Layer World Knowledge Model

| Layer     | Contents                                 | Mutability          |
|-----------|------------------------------------------|---------------------|
| `canon`   | Approved, authoritative world facts      | Append / update     |
| `staging` | Proposed changes from new chapters       | Pending review      |
| `archive` | Rejected changes with reasons            | Immutable audit log |

---

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Set your API key

```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Initialise a world

```bash
poiesis init --config config.yaml --seed examples/world_seed.yaml
```

### 4. Generate chapters

```bash
# Generate up to the max_chapters in config.yaml
poiesis run --config config.yaml

# Override max chapters
poiesis run --config config.yaml --max-chapters 5

# Check progress
poiesis status --config config.yaml
```

### 5. Use the Python API directly

```python
from poiesis.run_loop import RunLoop

loop = RunLoop(config_path="config.yaml")
loop.load_world_seed()
loop.run(max_chapters=10)
```

---

## Configuration Reference

All settings live in `config.yaml`. A full example is in `examples/config.yaml`.

```yaml
llm:
  provider: "openai"          # "openai" | "anthropic"
  model: "gpt-4o"
  temperature: 0.8
  max_tokens: 4000

planner_llm:                  # Separate, lower-temperature LLM for planning
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.3
  max_tokens: 2000

similarity:
  originality_threshold: 0.85 # Cosine similarity above which content is flagged
  fact_retrieval_k: 10
  chapter_similarity_k: 5

generation:
  max_chapters: 100
  rewrite_retries: 3          # Max editor retries per verification failure
  new_rule_budget: 5          # Max new world facts per chapter
  target_word_count: 3000

database:
  path: "poiesis.db"

vector_store:
  path: "vector_store"
  embedding_model: "all-MiniLM-L6-v2"

world_seed: "examples/world_seed.yaml"
```

---

## Module Descriptions

| Module                         | Purpose                                              |
|--------------------------------|------------------------------------------------------|
| `poiesis/config.py`            | Pydantic v2 config models + `load_config()`         |
| `poiesis/db/database.py`       | SQLite persistence for all world state              |
| `poiesis/llm/base.py`          | Abstract `LLMClient` with retry logic               |
| `poiesis/llm/openai_client.py` | OpenAI Chat Completions implementation              |
| `poiesis/llm/anthropic_client.py` | Anthropic Messages API implementation           |
| `poiesis/vector_store/store.py`| FAISS + sentence-transformers vector store          |
| `poiesis/world.py`             | `WorldModel` — three-layer knowledge management     |
| `poiesis/planner.py`           | `ChapterPlanner` — structured JSON plan generation  |
| `poiesis/writer.py`            | `ChapterWriter` — prose generation from plan        |
| `poiesis/extractor.py`         | `FactExtractor` — mines new world facts from text   |
| `poiesis/verifier.py`          | `ConsistencyVerifier` — detects rule violations     |
| `poiesis/editor.py`            | `ChapterEditor` — surgical rewrite for violations   |
| `poiesis/merger.py`            | `WorldMerger` — applies approved changes to canon   |
| `poiesis/summarizer.py`        | `ChapterSummarizer` — archival summaries            |
| `poiesis/originality.py`       | `OriginalityChecker` — cosine-similarity guard      |
| `poiesis/run_loop.py`          | `RunLoop` — full pipeline orchestration             |
| `poiesis/cli.py`               | Click CLI: `run`, `init`, `status`                  |

---

## Running Tests

```bash
pytest                  # all tests with coverage
pytest --no-cov -v      # verbose, no coverage overhead
pytest tests/test_database.py -v
```

---

## Contributing

1. Fork the repository and create a feature branch.
2. Install dev dependencies: `pip install -e ".[dev]"`
3. Install pre-commit hooks: `pre-commit install`
4. Write tests for any new functionality.
5. Ensure `ruff check poiesis tests` and `mypy poiesis` pass.
6. Open a pull request against `main`.

### Adding a New LLM Provider

See [docs/developer_guide.md](docs/developer_guide.md#3-how-to-add-a-new-llm-provider).

### Extending Verification Rules

See [docs/developer_guide.md](docs/developer_guide.md#4-how-to-extend-verification-rules).

---

## License

MIT — see [LICENSE](LICENSE).
