"""Poiesis 主生成循环。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from poiesis.config import Config, load_config
from poiesis.db.database import Database
from poiesis.editor import ChapterEditor
from poiesis.extractor import FactExtractor
from poiesis.llm.anthropic_client import AnthropicClient
from poiesis.llm.base import LLMClient
from poiesis.llm.openai_client import OpenAIClient
from poiesis.merger import WorldMerger
from poiesis.originality import OriginalityChecker
from poiesis.planner import ChapterPlanner
from poiesis.summarizer import ChapterSummarizer
from poiesis.vector_store.store import VectorStore
from poiesis.verifier import ConsistencyVerifier
from poiesis.world import WorldModel
from poiesis.writer import ChapterWriter

console = Console()


def _build_llm(cfg: Any) -> LLMClient:
    """Instantiate an LLM client from a ModelConfig."""
    if cfg.provider == "anthropic":
        return AnthropicClient(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    return OpenAIClient(
        model=cfg.model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )


class RunLoop:
    """Orchestrates the full Poiesis generation pipeline."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        """Initialise the run loop from a config file.

        Args:
            config_path: Path to the YAML configuration file.
        """
        self._config: Config = load_config(config_path)
        self._db = Database(self._config.database.path)
        self._db.initialize_schema()

        self._vs = VectorStore(
            store_path=self._config.vector_store.path,
            embedding_model=self._config.vector_store.embedding_model,
        )

        self._writer_llm = _build_llm(self._config.llm)
        self._planner_llm = _build_llm(self._config.planner_llm)

        gen = self._config.generation
        self._planner = ChapterPlanner(
            vector_store=self._vs, new_rule_budget=gen.new_rule_budget
        )
        self._writer = ChapterWriter(
            vector_store=self._vs, target_word_count=gen.target_word_count
        )
        self._extractor = FactExtractor()
        self._verifier = ConsistencyVerifier(new_rule_budget=gen.new_rule_budget)
        self._editor = ChapterEditor()
        self._merger = WorldMerger()
        self._summarizer = ChapterSummarizer()
        self._originality = OriginalityChecker()

        self._world = WorldModel()
        self._world.load_from_db(self._db)

    # ------------------------------------------------------------------
    # Seed loading
    # ------------------------------------------------------------------

    def load_world_seed(self, seed_path: str | None = None) -> None:
        """Populate the database and world model from a world seed YAML.

        Args:
            seed_path: Path to world_seed.yaml; falls back to
                ``config.world_seed``.
        """
        import yaml

        path = Path(seed_path or self._config.world_seed)
        if not path.exists():
            console.print(f"[yellow]World seed not found at {path}, skipping.[/yellow]")
            return

        with path.open("r", encoding="utf-8") as fh:
            seed: dict[str, Any] = yaml.safe_load(fh) or {}

        for rule in seed.get("immutable_rules", []):
            self._db.upsert_world_rule(
                rule_key=rule["key"],
                description=rule["description"],
                is_immutable=rule.get("is_immutable", True),
            )

        for char in seed.get("characters", []):
            self._db.upsert_character(
                name=char["name"],
                description=char.get("description"),
                core_motivation=char.get("core_motivation"),
                attributes=char.get("attributes", {}),
            )

        for event in seed.get("timeline_events", []):
            self._db.upsert_timeline_event(
                event_key=event["event_key"],
                description=event["description"],
                timestamp_in_world=event.get("timestamp_in_world"),
            )

        for hint in seed.get("foreshadowing", []):
            self._db.upsert_foreshadowing(
                hint_key=hint["hint_key"],
                description=hint["description"],
                status=hint.get("status", "pending"),
            )

        # 刷新内存中的世界模型
        self._world.load_from_db(self._db)
        console.print(f"[green]World seed loaded from {path}[/green]")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, max_chapters: int | None = None) -> None:
        """Run the generation loop.

        Args:
            max_chapters: Override the maximum chapters from config.
                ``None`` uses the config value.
        """
        limit = max_chapters or self._config.generation.max_chapters
        existing = self._db.list_chapters()
        start_chapter = len(existing) + 1

        console.print(
            Panel(
                f"[bold]Poiesis Generation Loop[/bold]\n"
                f"Starting at chapter {start_chapter}, target: {limit}",
                style="blue",
            )
        )

        for chapter_number in range(start_chapter, limit + 1):
            self._generate_chapter(chapter_number)

        console.print(Panel("[bold green]Generation complete![/bold green]"))

    def _generate_chapter(self, chapter_number: int) -> None:
        """Run the full pipeline for a single chapter."""
        rewrite_retries = self._config.generation.rewrite_retries

        console.rule(f"[bold]Chapter {chapter_number}[/bold]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # 第一步：规划章节
            task = progress.add_task("Planning chapter...", total=None)
            summaries = self._get_previous_summaries()
            plan = self._planner.plan(
                chapter_number, self._world, summaries, self._planner_llm
            )
            progress.remove_task(task)
            console.print(f"  [cyan]Plan:[/cyan] {plan.get('title', '')}")

            # 第二步：写作章节
            task = progress.add_task("Writing chapter...", total=None)
            content = self._writer.write(chapter_number, plan, self._world, self._writer_llm)
            progress.remove_task(task)
            word_count = len(content.split())
            console.print(f"  [cyan]Written:[/cyan] {word_count} words")

            # 第三步：检查原创性
            task = progress.add_task("Checking originality...", total=None)
            orig_result = self._originality.check(content, self._vs)
            progress.remove_task(task)
            if not orig_result.is_original:
                risk = orig_result.risk_score
                console.print(
                    f"  [yellow]Originality warning: risk_score={risk:.2f}[/yellow]"
                )

            # 第四步：提取事实
            task = progress.add_task("Extracting facts...", total=None)
            proposed_changes = self._extractor.extract(
                chapter_number, content, self._world, self._planner_llm
            )
            progress.remove_task(task)
            console.print(f"  [cyan]Proposed changes:[/cyan] {len(proposed_changes)}")

            # 第五步：一致性验证 + 编辑循环
            passed = False
            for attempt in range(rewrite_retries + 1):
                task = progress.add_task(
                    f"Verifying (attempt {attempt + 1})...", total=None
                )
                result = self._verifier.verify(
                    chapter_number,
                    content,
                    plan,
                    self._world,
                    proposed_changes,
                    self._planner_llm,
                )
                progress.remove_task(task)

                if result.passed:
                    passed = True
                    console.print("  [green]Verification passed[/green]")
                    break

                console.print(
                    f"  [red]Violations ({len(result.violations)}):[/red] "
                    + "; ".join(result.violations[:3])
                )

                if attempt < rewrite_retries:
                    task = progress.add_task("Editing chapter...", total=None)
                    content = self._editor.edit(
                        chapter_number,
                        content,
                        result.violations,
                        plan,
                        self._world,
                        self._writer_llm,
                    )
                    progress.remove_task(task)

            if not passed:
                console.print(
                    f"  [yellow]Chapter {chapter_number} saved with unresolved violations.[/yellow]"
                )

            # 第六步：持久化章节到数据库
            self._db.upsert_chapter(
                chapter_number=chapter_number,
                content=content,
                title=plan.get("title"),
                plan=plan,
                word_count=len(content.split()),
                status="final" if passed else "flagged",
            )

            # 第七步：持久化暂存变更并批量批准
            task = progress.add_task("Merging world changes...", total=None)
            approved: list[dict[str, Any]] = []
            for change in proposed_changes:
                change_id = self._db.add_staging_change(
                    change_type=change["change_type"],
                    entity_type=change["entity_type"],
                    entity_key=change["entity_key"],
                    proposed_data=change["proposed_data"],
                    source_chapter=chapter_number,
                )
                self._db.update_staging_status(change_id, "approved")
                change["id"] = change_id
                approved.append(change)

            merged = self._merger.merge(approved, self._world, self._db, self._vs)
            progress.remove_task(task)
            console.print(f"  [cyan]Merged:[/cyan] {merged} world changes")

            # 第八步：生成章节摘要
            task = progress.add_task("Summarizing...", total=None)
            summary = self._summarizer.summarize(
                chapter_number, content, plan, self._world, self._planner_llm
            )
            self._db.upsert_chapter_summary(
                chapter_number=chapter_number,
                summary=summary["summary"],
                key_events=summary.get("key_events", []),
                characters_featured=summary.get("characters_featured", []),
                new_facts_introduced=summary.get("new_facts_introduced", []),
            )
            # 将章节索引到向量存储，以供后续原创性检测使用
            self._vs.add(
                key=f"chapter:{chapter_number}",
                text=content[:2000],
                metadata={"chapter_number": chapter_number},
            )
            progress.remove_task(task)

        console.print(f"  [bold green]Chapter {chapter_number} complete.[/bold green]\n")

    def _get_previous_summaries(self) -> list[str]:
        """Return narrative summaries for all completed chapters."""
        rows = self._db.list_chapter_summaries()
        return [r["summary"] for r in rows if r.get("summary")]
