"""结构化 run trace 与章节提交的持久化助手。"""

from __future__ import annotations

from typing import Any

from poiesis.application.contracts import ChapterGenerationResult


class RunPersistenceFacade:
    """集中处理 trace 写入和章节结果落库。"""

    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime
        self._db = runtime._db

    def create_run_trace(self, task_id: str) -> int:
        """创建一次 run 的摘要记录，并返回 run_id。"""
        config_snapshot = {
            "database_path": self._runtime._config.database.path,
            "vector_store_path": self._runtime._config.vector_store.path,
            "generation": self._runtime._config.generation.model_dump(mode="json"),
        }
        llm_snapshot = {
            "writer": {
                "provider": self._runtime._config.llm.provider,
                "model": self._runtime._config.llm.model,
            },
            "planner": {
                "provider": self._runtime._config.planner_llm.provider,
                "model": self._runtime._config.planner_llm.model,
            },
        }
        return self._db.create_run_trace(
            task_id=task_id,
            book_id=self._runtime._book_id,
            status="running",
            config_snapshot=config_snapshot,
            llm_snapshot=llm_snapshot,
        ) or 0

    def update_run_status(
        self,
        run_id: int,
        status: str,
        error_message: str | None = None,
        finished: bool = False,
    ) -> None:
        """更新 run 状态；结束态时同时补 finished_at。"""
        self._db.update_run_trace_status(
            run_id=run_id,
            status=status,
            error_message=error_message,
            finished=finished,
        )

    def save_chapter_trace(self, run_id: int, result: ChapterGenerationResult) -> None:
        """保存单章当前阶段的最新 trace 快照。"""
        self._db.upsert_run_chapter_trace(
            run_id=run_id,
            chapter_number=result.chapter_number,
            status=result.status,
            planner_output=result.planner_output.model_dump(mode="json"),
            retrieval_pack=result.retrieval_pack,
            draft_text=result.draft_text,
            final_content=result.final_content,
            changeset=result.changeset.model_dump(mode="json"),
            verifier_issues=[issue.model_dump(mode="json") for issue in result.verifier_issues],
            editor_rewrites=result.editor_rewrites,
            merge_result=result.merge_result,
            summary_result=result.summary_result,
            metrics=result.metrics.model_dump(mode="json"),
            error_message=result.error_message,
        )

    def commit_generated_chapter(self, result: ChapterGenerationResult) -> ChapterGenerationResult:
        """提交章节最终结果。

        顺序上先落章节，再批量批准 staging changes，最后写摘要与语义索引。
        这样前端读取章节详情时，不会出现“任务完成但章节不存在”的错位状态。
        """
        self._db.upsert_chapter(
            book_id=self._runtime._book_id,
            chapter_number=result.chapter_number,
            content=result.final_content,
            title=result.planner_output.title,
            plan=result.planner_output.to_runtime_plan(),
            word_count=len(result.final_content.split()),
            status=result.status,
        )

        approved: list[dict[str, Any]] = []
        for change in result.changeset.all_changes():
            # 第一阶段仍沿用 staging -> approved -> merge 的旧路径，
            # 先不引入更复杂的审核流，确保改造兼容。
            change_id = self._db.add_staging_change(
                book_id=self._runtime._book_id,
                change_type=change["change_type"],
                entity_type=change["entity_type"],
                entity_key=change["entity_key"],
                proposed_data=change["proposed_data"],
                source_chapter=result.chapter_number,
            )
            self._db.update_staging_status(change_id, "approved")
            approved_change = dict(change)
            approved_change["id"] = change_id
            approved_change["book_id"] = self._runtime._book_id
            approved.append(approved_change)

        merged_count = self._runtime._merger.merge(
            approved,
            self._runtime._world,
            self._db,
            self._runtime._vs,
        )

        summary = result.summary_result
        self._db.upsert_chapter_summary(
            book_id=self._runtime._book_id,
            chapter_number=result.chapter_number,
            summary=summary.get("summary", ""),
            key_events=summary.get("key_events", []),
            characters_featured=summary.get("characters_featured", []),
            new_facts_introduced=summary.get("new_facts_introduced", []),
        )
        self._runtime._vs.add(
            # 章节正文索引保留旧行为，供原创性检测和后续检索复用。
            key=f"chapter:{result.chapter_number}",
            text=result.final_content[:2000],
            metadata={"chapter_number": result.chapter_number},
        )

        result.merge_result = {
            "approved_change_ids": [item["id"] for item in approved],
            "approved_count": len(approved),
            "merged_count": merged_count,
            "chapter_status": result.status,
        }
        return result
