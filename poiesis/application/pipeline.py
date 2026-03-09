"""章节级生成流水线，负责产出结构化 trace。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from poiesis.application.contracts import (
    ChangeSet,
    ChapterGenerationError,
    ChapterGenerationResult,
    ChapterMetrics,
    PlannerOutput,
    normalize_verifier_issues,
)


class ChapterGenerationPipeline:
    """封装单章生成的业务编排。"""

    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime

    def generate_chapter(
        self,
        chapter_number: int,
        on_writer_delta: Callable[[str], None] | None = None,
        on_stage: Callable[[str], None] | None = None,
        on_trace_update: Callable[[ChapterGenerationResult], None] | None = None,
    ) -> ChapterGenerationResult:
        """执行单章生成，并在每个关键阶段输出可持久化的快照。"""
        result = ChapterGenerationResult(chapter_number=chapter_number)

        def _emit() -> None:
            if on_trace_update is not None:
                # 这里深拷贝一份结果，避免后续阶段继续修改导致 trace 读到“未来状态”。
                on_trace_update(result.model_copy(deep=True))

        def _report(message: str) -> None:
            if on_stage is not None:
                on_stage(message)

        try:
            _report(f"第 {chapter_number} 章：规划中…")
            previous_summaries = self._runtime._get_previous_summaries()
            planner_query = f"第 {chapter_number} 章 叙事线"
            planner_hits = self._runtime._vs.search(planner_query, k=10)
            # 第一阶段尚未正式引入 Retrieval Composer，先把上下文快照显式记录下来。
            result.retrieval_pack = {
                "planner_query": planner_query,
                "planner_hits": planner_hits,
                "previous_summaries": previous_summaries[-5:],
            }
            planner_output = self._runtime._planner.plan(
                chapter_number,
                self._runtime._world,
                previous_summaries,
                self._runtime._planner_llm,
            )
            if isinstance(planner_output, PlannerOutput):
                result.planner_output = planner_output
            else:
                result.planner_output = PlannerOutput.model_validate(
                    {**planner_output, "raw_payload": dict(planner_output)}
                )
            _emit()

            _report(f"第 {chapter_number} 章：写作中…")
            writer_query = result.planner_output.summary or result.planner_output.chapter_goal or f"第 {chapter_number} 章"
            writer_hits = self._runtime._vs.search(writer_query, k=8)
            result.retrieval_pack["writer_query"] = writer_query
            result.retrieval_pack["writer_hits"] = writer_hits
            _emit()

            content = self._runtime._writer.write(
                chapter_number,
                result.planner_output.to_runtime_plan(),
                self._runtime._world,
                self._runtime._writer_llm,
                on_delta=on_writer_delta,
            )
            result.draft_text = content
            result.final_content = content
            _emit()

            _report(f"第 {chapter_number} 章：原创性检查中…")
            originality = self._runtime._originality.check(content, self._runtime._vs)
            result.retrieval_pack["originality"] = {
                "is_original": originality.is_original,
                "risk_score": originality.risk_score,
            }
            _emit()

            _report(f"第 {chapter_number} 章：事实提取中…")
            extracted = self._runtime._extractor.extract(
                chapter_number,
                content,
                self._runtime._world,
                self._runtime._planner_llm,
            )
            if isinstance(extracted, ChangeSet):
                result.changeset = extracted
            else:
                result.changeset = ChangeSet.model_validate(
                    {
                        "characters": [
                            change for change in extracted if change.get("entity_type") == "character"
                        ],
                        "world_rules": [
                            change for change in extracted if change.get("entity_type") == "world_rule"
                        ],
                        "timeline_events": [
                            change for change in extracted if change.get("entity_type") == "timeline_event"
                        ],
                        "foreshadowing_updates": [
                            change for change in extracted if change.get("entity_type") == "foreshadowing"
                        ],
                        "raw_staging_changes": extracted,
                    }
                )
            _emit()

            rewrite_retries = self._runtime._config.generation.rewrite_retries
            passed = False

            for attempt in range(rewrite_retries + 1):
                _report(f"第 {chapter_number} 章：一致性校验中（第 {attempt + 1} 次）…")
                verification = self._runtime._verifier.verify(
                    chapter_number,
                    content,
                    result.planner_output.to_runtime_plan(),
                    self._runtime._world,
                    result.changeset.all_changes(),
                    self._runtime._planner_llm,
                )
                result.verifier_issues = normalize_verifier_issues(verification)
                _emit()

                if verification.passed:
                    passed = True
                    break

                if attempt < rewrite_retries:
                    _report(f"第 {chapter_number} 章：自动修订中…")
                    before_edit = content
                    content = self._runtime._editor.edit(
                        chapter_number,
                        content,
                        [issue.reason for issue in result.verifier_issues if issue.severity == "fatal"],
                        result.planner_output.to_runtime_plan(),
                        self._runtime._world,
                        self._runtime._writer_llm,
                    )
                    result.editor_rewrites.append(
                        {
                            "attempt": attempt + 1,
                            # 保留结构化 issues，方便后续前端做问题分类和 diff 展示。
                            "issues": [issue.model_dump(mode="json") for issue in result.verifier_issues],
                            "before_excerpt": before_edit[:500],
                            "after_excerpt": content[:500],
                        }
                    )
                    result.final_content = content
                    _emit()

            _report(f"第 {chapter_number} 章：生成摘要与索引…")
            summary = self._runtime._summarizer.summarize(
                chapter_number,
                content,
                result.planner_output.to_runtime_plan(),
                self._runtime._world,
                self._runtime._planner_llm,
            )
            result.summary_result = dict(summary)
            result.final_content = content
            result.status = "final" if passed else "flagged"
            result.metrics = ChapterMetrics(
                accepted_first_pass=passed and len(result.editor_rewrites) == 0,
                edit_loop_count=len(result.editor_rewrites),
                issues_count=len(result.verifier_issues),
                changes_count=len(result.changeset.all_changes()),
            )
            _emit()
            return result

        except Exception as exc:
            # 即使失败也把当前已生成的阶段信息落到 trace，便于失败回放。
            result.status = "failed"
            result.error_message = str(exc)
            _emit()
            raise ChapterGenerationError(result, str(exc)) from exc
