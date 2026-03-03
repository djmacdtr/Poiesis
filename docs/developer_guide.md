# Poiesis Developer Guide

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Responsibilities](#2-module-responsibilities)
3. [How to Add a New LLM Provider](#3-how-to-add-a-new-llm-provider)
4. [How to Extend Verification Rules](#4-how-to-extend-verification-rules)
5. [Database Migration Guide](#5-database-migration-guide)
6. [Vector Store Management](#6-vector-store-management)
7. [Running Tests](#7-running-tests)
8. [Configuration Reference](#8-configuration-reference)

---

## 1. Architecture Overview

Poiesis is built around a **six-stage generation pipeline** that runs once per chapter:

```
World Seed / Prior State
        │
        ▼
┌───────────────┐
│  ChapterPlanner│  ← Produces a structured JSON plan
└──────┬────────┘
       │ plan
       ▼
┌───────────────┐
│  ChapterWriter │  ← Generates prose guided by the plan
└──────┬────────┘
       │ content
       ▼
┌───────────────┐
│  FactExtractor │  ← Parses new world facts into staging changes
└──────┬────────┘
       │ proposed_changes
       ▼
┌────────────────────┐
│ConsistencyVerifier  │  ← Checks for rule violations (LLM + rule-based)
└──────┬─────────────┘
       │ violations?
    ┌──┴──┐
   yes   no
    │     │
    ▼     ▼
┌────────┐ ┌──────────────┐
│ Editor │ │  WorldMerger  │  ← Approves & merges staging → canon
└──┬─────┘ └──────┬───────┘
   │ retry        │
   └──────────────┤
                  ▼
         ┌─────────────────┐
         │ChapterSummarizer │  ← Produces archival summary
         └─────────────────┘
```

### Three-Layer Knowledge Model

| Layer    | Contents                              | Mutability         |
|----------|---------------------------------------|--------------------|
| `canon`  | Approved world facts                  | Append/update only |
| `staging`| Proposed changes from new chapters    | Pending review     |
| `archive`| Rejected changes with reasons         | Immutable audit log|

---

## 2. Module Responsibilities

| Module                       | Responsibility                                                  |
|------------------------------|-----------------------------------------------------------------|
| `poiesis/config.py`          | Pydantic v2 configuration models; `load_config(path)`          |
| `poiesis/db/database.py`     | SQLite persistence layer; CRUD for all tables                  |
| `poiesis/db/schema.sql`      | Table definitions; run via `initialize_schema()`               |
| `poiesis/llm/base.py`        | `LLMClient` ABC with retry logic and JSON extraction helpers   |
| `poiesis/llm/openai_client.py`  | OpenAI Chat Completions implementation                      |
| `poiesis/llm/anthropic_client.py` | Anthropic Messages API implementation                     |
| `poiesis/vector_store/store.py` | FAISS + sentence-transformers; add/search/remove + persistence |
| `poiesis/world.py`           | `WorldModel`: in-memory three-layer state; staging operations  |
| `poiesis/planner.py`         | `ChapterPlanner`: structured JSON chapter plan generation      |
| `poiesis/writer.py`          | `ChapterWriter`: prose generation guided by plan               |
| `poiesis/extractor.py`       | `FactExtractor`: new-fact mining from chapter text             |
| `poiesis/verifier.py`        | `ConsistencyVerifier`: rule-based + LLM consistency checking   |
| `poiesis/editor.py`          | `ChapterEditor`: surgical rewrite to fix violations            |
| `poiesis/merger.py`          | `WorldMerger`: staging → canon + vector store + DB persistence |
| `poiesis/summarizer.py`      | `ChapterSummarizer`: archival chapter summaries                |
| `poiesis/originality.py`     | `OriginalityChecker`: cosine-similarity plagiarism guard       |
| `poiesis/run_loop.py`        | `RunLoop`: orchestrates the full pipeline; CLI-facing          |
| `poiesis/cli.py`             | Click CLI: `run`, `init`, `status` commands                    |

---

## 3. How to Add a New LLM Provider

1. **Create a new file** `poiesis/llm/<provider>_client.py`.

2. **Subclass `LLMClient`** and implement `_complete` and `_complete_json`:

```python
from poiesis.llm.base import LLMClient

class MyProviderClient(LLMClient):
    def __init__(self, model: str, temperature: float, max_tokens: int) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        # Initialise SDK client here

    def _complete(self, prompt: str, system: str | None = None, **kwargs) -> str:
        # Call the provider API and return text
        ...

    def _complete_json(self, prompt: str, system: str | None = None, **kwargs) -> dict:
        raw = self._complete(prompt + "\nReturn ONLY valid JSON.", system=system)
        return self._extract_json(raw)  # inherited helper
```

3. **Register the provider** in `poiesis/run_loop.py` inside `_build_llm`:

```python
elif cfg.provider == "myprovider":
    from poiesis.llm.myprovider_client import MyProviderClient
    return MyProviderClient(model=cfg.model, temperature=cfg.temperature, max_tokens=cfg.max_tokens)
```

4. **Set the provider** in `config.yaml`:

```yaml
llm:
  provider: "myprovider"
  model: "my-model-name"
```

5. **Add the SDK dependency** to `pyproject.toml` under `[project] dependencies`.

---

## 4. How to Extend Verification Rules

### Adding a Rule-Based Check

Add a private method to `ConsistencyVerifier` in `poiesis/verifier.py`:

```python
def _check_my_new_rule(
    self,
    content: str,
    world: WorldModel,
    violations: list[str],
    warnings: list[str],
) -> None:
    """Check that content does not violate my new rule."""
    if "forbidden phrase" in content.lower():
        violations.append("Forbidden phrase detected in chapter.")
```

Then call it inside `verify()` before the LLM check:

```python
self._check_my_new_rule(content, world, violations, warnings)
```

### Extending the LLM Check

Edit `prompts/verifier.txt` to add a new numbered item to the checklist.
The LLM response format (`violations` / `warnings` arrays) is already flexible
enough to carry any new checks without code changes.

---

## 5. Database Migration Guide

Poiesis uses SQLite with a single schema file (`poiesis/db/schema.sql`).
There is no migration framework; the schema uses `CREATE TABLE IF NOT EXISTS`
so re-running `initialize_schema()` is always safe on an existing database.

**Adding a new column to an existing table:**

```sql
ALTER TABLE characters ADD COLUMN aliases JSON DEFAULT '[]';
```

Add this statement to `schema.sql` inside an `IF NOT EXISTS` guard pattern
by placing it in a separate migration file and running it manually, or by
checking for the column in Python before issuing the ALTER:

```python
def _migrate_add_aliases(self) -> None:
    conn = self._get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(characters)")
    cols = {row['name'] for row in cur.fetchall()}
    if 'aliases' not in cols:
        conn.execute("ALTER TABLE characters ADD COLUMN aliases JSON DEFAULT '[]'")
        conn.commit()
```

**Adding a completely new table:** simply add the `CREATE TABLE IF NOT EXISTS`
block to `schema.sql` and call `initialize_schema()` again.

---

## 6. Vector Store Management

The vector store is managed by `poiesis/vector_store/store.py` using FAISS
with sentence-transformers embeddings.

### Storage Layout

```
vector_store/
├── index.faiss    # FAISS flat inner-product index
└── metadata.pkl   # Python pickle of aligned metadata list
```

### Key Operations

| Operation         | Method              | Notes                                          |
|-------------------|---------------------|------------------------------------------------|
| Add document      | `store.add(key, text, metadata)` | Replaces existing doc with same key  |
| Similarity search | `store.search(query, k=5)` | Returns k nearest with scores            |
| Remove document   | `store.remove(key)` | Rebuilds index (O(n)); avoid in hot path      |
| Document count    | `len(store)`        | Includes only live (non-deleted) documents    |

### Changing the Embedding Model

Update `vector_store.embedding_model` in `config.yaml`. **Important:** changing
the model invalidates the existing index because embedding dimensions change.
Delete the `vector_store/` directory and re-index from scratch:

```bash
rm -rf vector_store/
poiesis init --config config.yaml
```

### Re-indexing from the Database

```python
from poiesis.db.database import Database
from poiesis.vector_store.store import VectorStore

db = Database("poiesis.db")
db.initialize_schema()
vs = VectorStore("vector_store")

for rule in db.list_world_rules():
    vs.add(
        key=f"world_rule:{rule['rule_key']}",
        text=rule["description"],
        metadata={"entity_type": "world_rule"},
    )
# Repeat for characters, timeline events, foreshadowing, chapter summaries
```

---

## 7. Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests with coverage
pytest

# Run a specific test file
pytest tests/test_database.py -v

# Run a specific test class
pytest tests/test_world_consistency.py::TestImmutableRules -v

# Run without coverage (faster)
pytest --no-cov
```

Tests that touch the vector store (e.g., `test_originality.py`) require
`sentence-transformers` and will download `all-MiniLM-L6-v2` on first run.
Subsequent runs use the cached model.

---

## 8. Configuration Reference

All fields have defaults. Override in `config.yaml`.

| Key                              | Type    | Default                    | Description                                      |
|----------------------------------|---------|----------------------------|--------------------------------------------------|
| `llm.provider`                   | string  | `"openai"`                 | LLM provider: `"openai"` or `"anthropic"`        |
| `llm.model`                      | string  | `"gpt-4o"`                 | Model identifier                                 |
| `llm.temperature`                | float   | `0.8`                      | Sampling temperature (0.0–2.0)                   |
| `llm.max_tokens`                 | int     | `4000`                     | Maximum tokens per completion                    |
| `planner_llm.*`                  | —       | Same structure as `llm`    | Separate LLM config for the planner              |
| `similarity.originality_threshold` | float | `0.85`                    | Cosine similarity above which content is flagged |
| `similarity.fact_retrieval_k`    | int     | `10`                       | Facts to retrieve from vector store per query    |
| `similarity.chapter_similarity_k`| int    | `5`                        | Chapters to compare for originality              |
| `generation.max_chapters`        | int     | `100`                      | Total chapters to generate before stopping       |
| `generation.rewrite_retries`     | int     | `3`                        | Max editor retries per verification failure      |
| `generation.new_rule_budget`     | int     | `5`                        | Max new world facts introduced per chapter       |
| `generation.target_word_count`   | int     | `3000`                     | Target chapter length in words                   |
| `database.path`                  | string  | `"poiesis.db"`             | SQLite file path                                 |
| `vector_store.path`              | string  | `"vector_store"`           | Directory for FAISS index files                  |
| `vector_store.embedding_model`   | string  | `"all-MiniLM-L6-v2"`       | Sentence-transformers model name                 |
| `world_seed`                     | string  | `"examples/world_seed.yaml"` | World seed file loaded on `init`               |
