"""创作闭环编排器：把 verifier 问题升级为可预览、可执行、可回滚的修复提案。

第一阶段只要求 roadmap 真正闭环落地，但这里的协议和操作类型已经按全栈闭环留齐：
- roadmap / continuity 先跑通完整链路；
- scene / review / canon 后续只是在同一控制面里补 detector / agent；
- 默认执行模式固定为“建议后执行”，因此这里不会静默直写真源。
"""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    CreativeIssue,
    CreativeRepairProposal,
    CreativeRepairRun,
    GenerationEvalRecord,
    RepairCandidate,
    RepairEvalSummary,
    RepairJudgeScore,
    RepairOperation,
    RoadmapValidationIssue,
    StoryArcPlan,
    WorldBlueprint,
)
from poiesis.llm.base import LLMClient
from poiesis.pipeline.planning.roadmap_planner import RoadmapPlanner


def _now_iso() -> str:
    """统一生成控制面时间戳。"""
    return datetime.now().isoformat(timespec="seconds")


def _build_issue_id(issue: RoadmapValidationIssue) -> str:
    """为路线问题生成稳定 issue_id，保证复验后能尽量识别“同一类问题”。"""
    raw = "|".join(
        [
            issue.type,
            str(issue.chapter_number or 0),
            str(issue.arc_number or 0),
            issue.story_stage.strip(),
            issue.scope,
        ]
    )
    return f"roadmap-issue-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _normalize_signature_text(value: str) -> str:
    """把展示文案规整成稳定签名片段，避免空白差异导致重复提案判定失效。"""
    return " ".join(value.strip().split())


def _build_issue_signature(issue: RoadmapValidationIssue) -> str:
    """为问题生成稳定签名，供控制面做去重和冷却。"""
    raw = "|".join(
        [
            issue.type,
            str(issue.chapter_number or 0),
            str(issue.arc_number or 0),
            issue.story_stage.strip(),
            issue.scope,
            _normalize_signature_text(issue.message),
        ]
    )
    return f"issue-signature-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _build_proposal_id(issue_ids: list[str], strategy_type: str) -> str:
    """提案 id 只要保证书内稳定唯一即可，不要求全局可读。"""
    raw = "|".join(sorted(issue_ids) + [strategy_type, _now_iso()])
    return f"proposal-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _build_proposal_signature(issue_signatures: list[str], strategy_type: str) -> str:
    """提案签名不带时间戳，专门用来识别“是否已经存在同类方案”。

    提案 id 负责唯一性，proposal_signature 负责“这是同一类方案吗”。
    两者分开后，控制面才能同时保留历史记录又避免当前提案区重复堆叠。
    """

    raw = "|".join(sorted(issue_signatures) + [strategy_type])
    return f"proposal-signature-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _build_run_id(proposal_id: str) -> str:
    """执行记录需要强唯一性，不能再依赖秒级时间戳。"""
    return f"repair-run-{uuid4().hex[:12]}"


def _build_candidate_id(prefix: str) -> str:
    """候选会在同一次规划里成批生成，因此必须使用真正唯一的 id。"""
    return f"candidate-{prefix}-{uuid4().hex[:10]}"


def _build_generation_eval_id(book_id: int, task_type: str) -> str:
    """评测记录允许高频写入，id 需要避免同秒碰撞。"""
    return f"eval-{book_id}-{task_type}-{uuid4().hex[:10]}"


def _build_snapshot_id(book_id: int, kind: str) -> str:
    raw = f"{book_id}|{kind}|{_now_iso()}"
    return f"snapshot-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


class CreativeOrchestrator:
    """统一把 roadmap 校验问题升级为“问题队列 -> 修复提案 -> 执行结果”。

    这层故意不直接依赖前端，也不直接做数据库 IO：
    - 控制面规则统一收口在这里；
    - 用例层负责把这里的结果持久化到蓝图工作态；
    - 后续 scene / canon 接入时，只需要在这里补 detector / planner 分支。

    当前阶段的边界刻意收得比较严：
    - roadmap 是第一阶段唯一真正闭环的来源层；
    - review 先在用例层以只读 CreativeIssue 形式并入，不经过这里的提案/执行链；
    - scene / canon 等真正需要跨层真源的问题，等持久化边界明确后再接 detector。
    """

    _DETERMINISTIC_ISSUE_TYPES = {
        "task_status_jump",
        "duplicate_task_creation",
        "invalid_chapter_dependency",
        "missing_previous_dependency",
        "loop_missing_title",
        "loop_missing_summary",
        "loop_missing_due_end",
        "loop_due_end_before_intro",
        "loop_due_window_invalid",
        "loop_overdue",
        "loop_still_overdue",
        "task_overdue",
        "task_still_overdue",
    }
    _CHAPTER_REWRITE_ISSUE_TYPES = {
        "missing_story_progress",
        "missing_key_events",
        "missing_task_or_loop_progress",
        "timeline_not_advanced",
        "repeated_chapter_function",
        "chapter_similarity",
    }
    _ARC_REWRITE_ISSUE_TYPES = {
        "arc_function_monotony",
        "arc_story_progress_stagnation",
        "arc_missing_climax",
    }
    _AUTO_PLAN_EXCLUDED_ISSUE_TYPES = _ARC_REWRITE_ISSUE_TYPES

    def __init__(self, planner: RoadmapPlanner) -> None:
        self._planner = planner

    def build_creative_issues(
        self,
        *,
        book_id: int,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        roadmap_issues: list[RoadmapValidationIssue],
        stored_proposals: list[CreativeRepairProposal],
        issue_feedback: dict[str, dict[str, object]] | None = None,
        stored_runs: list[CreativeRepairRun] | None = None,
    ) -> list[CreativeIssue]:
        """把 verifier 原始结果升级成统一问题队列。"""
        active_issue_ids = {
            issue_id
            for proposal in stored_proposals
            if proposal.status == "awaiting_approval"
            for issue_id in proposal.issue_ids
        }
        planning_feedback = issue_feedback or {}
        residual_issue_feedback: dict[str, dict[str, object]] = {}
        for run in reversed(stored_runs or []):
            eval_summary = run.eval_summary
            if eval_summary is None:
                continue
            for issue_id in eval_summary.residual_issue_ids:
                residual_issue_feedback.setdefault(
                    issue_id,
                    {
                        "post_apply_residual": True,
                        "last_run_id": run.run_id,
                        "last_run_status": run.status,
                        "recommended_next_action": eval_summary.recommended_next_action,
                        "target_residual_issue_count": eval_summary.target_residual_issue_count,
                        "introduced_issue_count": eval_summary.introduced_issue_count,
                    },
                )
        issues: list[CreativeIssue] = []
        for issue in roadmap_issues:
            issue_id = _build_issue_id(issue)
            issue_signature = _build_issue_signature(issue)
            target_type = "roadmap_chapter" if issue.chapter_number is not None else "roadmap_arc"
            repairability, suggested_strategy = self._classify_issue(issue, story_arcs, roadmap)
            context_payload = {
                **planning_feedback.get(issue_id, {}),
                **residual_issue_feedback.get(issue_id, {}),
            }
            status = "awaiting_approval" if issue_id in active_issue_ids else "open"
            if status == "open" and planning_feedback.get(issue_id):
                status = "planned"
            issues.append(
                CreativeIssue(
                    issue_id=issue_id,
                    book_id=book_id,
                    source_layer="roadmap",
                    target_type=target_type,
                    target_ref={
                        "chapter_number": issue.chapter_number,
                        "arc_number": issue.arc_number,
                        "story_stage": issue.story_stage,
                    },
                    issue_type=issue.type,
                    severity=issue.severity,
                    message=issue.message,
                    detected_by="roadmap_verifier",
                    repairability=repairability,
                    status=cast(Any, status),
                    suggested_strategy=suggested_strategy,
                    issue_signature=issue_signature,
                    context_payload=context_payload,
                )
            )
        issues.sort(
            key=lambda item: (
                0 if item.severity == "fatal" else 1,
                int(item.target_ref.get("chapter_number") or 0),
                int(item.target_ref.get("arc_number") or 0),
                item.issue_type,
            )
        )
        return issues

    def _candidate_total_score(self, candidate: RepairCandidate) -> float:
        """统一计算候选综合分，避免排序和门禁各自算出两套结果。"""
        return sum(item.score for item in candidate.judge_scores)

    def evaluate_candidate_gate(
        self,
        *,
        candidate: RepairCandidate,
        before_issues: list[CreativeIssue],
        after_issues: list[CreativeIssue],
        target_issue_ids: list[str],
        judge_threshold: float,
        requires_model_judge: bool,
    ) -> RepairCandidate:
        """把“候选排序”和“候选能否执行”拆成两层规则。

        当前最重要的收口点在这里：
        - best candidate 只代表“相对最不差”的候选；
        - execution_readiness 才决定它是否足够安全，能不能给作者“接受并执行”按钮。
        """

        before_issue_ids = {item.issue_id for item in before_issues}
        after_issue_map = {item.issue_id: item for item in after_issues}
        target_ids = set(target_issue_ids)
        if after_issue_map:
            candidate.target_resolved_issue_ids = sorted(target_ids - set(after_issue_map))
            candidate.target_residual_issue_ids = sorted(target_ids & set(after_issue_map))
        elif candidate.residual_issue_types:
            # 某些阶段级候选目前只能拿到“残留问题类型”而没有完整 issue 列表。
            # 这里宁可保守地视为目标问题仍残留，也不要误判为可直接执行。
            candidate.target_resolved_issue_ids = []
            candidate.target_residual_issue_ids = sorted(target_ids)
        else:
            candidate.target_resolved_issue_ids = sorted(target_ids)
            candidate.target_residual_issue_ids = []
        candidate.target_resolved_issue_count = len(candidate.target_resolved_issue_ids)
        candidate.target_residual_issue_count = len(candidate.target_residual_issue_ids)
        candidate.introduced_fatal_issue_ids = sorted(
            issue_id
            for issue_id, issue in after_issue_map.items()
            if issue_id not in before_issue_ids and issue.severity == "fatal"
        )
        candidate.introduced_warning_issue_ids = sorted(
            issue_id
            for issue_id, issue in after_issue_map.items()
            if issue_id not in before_issue_ids and issue.severity != "fatal"
        )

        before_fatal_count = sum(1 for item in before_issues if item.severity == "fatal")
        before_warning_count = sum(1 for item in before_issues if item.severity != "fatal")
        blocking_reasons: list[str] = []
        if candidate.target_residual_issue_count > 0:
            blocking_reasons.append("目标问题仍有残留，当前候选不能视为真正修复成功。")
        if candidate.introduced_fatal_issue_ids:
            blocking_reasons.append("当前候选会引入新的严重问题，不能自动执行。")
        if candidate.verifier_fatal_count > before_fatal_count:
            blocking_reasons.append("当前候选的严重问题数比修复前更多，属于回归。")
        if candidate.verifier_warning_count > before_warning_count:
            blocking_reasons.append("当前候选的提醒问题数比修复前更多，属于回归。")
        if requires_model_judge and candidate.judge_mode != "model":
            blocking_reasons.append("judge 模型不可用，语义类修复已降级为仅参考，不允许自动执行。")
        if requires_model_judge and self._candidate_total_score(candidate) < judge_threshold:
            blocking_reasons.append("当前候选的评审综合分低于执行阈值，不允许自动执行。")

        candidate.blocking_reasons = blocking_reasons
        if blocking_reasons:
            candidate.execution_readiness = "blocked" if requires_model_judge and candidate.judge_mode != "model" else "preview_only"
        else:
            candidate.execution_readiness = "executable"
        return candidate

    def plan_roadmap_repairs(
        self,
        *,
        book_id: int,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        roadmap_issues: list[RoadmapValidationIssue],
        stored_proposals: list[CreativeRepairProposal],
        issue_ids: list[str],
        intent: Any | None,
        variant: ConceptVariant | None,
        world: WorldBlueprint | None,
        characters: list[CharacterBlueprint],
        llm: LLMClient | None,
        judge_llm: LLMClient | None = None,
        relationship_graph: list[Any] | None = None,
        candidate_count: int = 3,
        judge_threshold: float = 0.0,
    ) -> tuple[list[CreativeRepairProposal], dict[str, dict[str, object]]]:
        """为当前 open issue 生成预览提案。"""
        available_issues = self.build_creative_issues(
            book_id=book_id,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=roadmap_issues,
            stored_proposals=stored_proposals,
        )
        selectable = [issue for issue in available_issues if issue.status == "open"]
        selected_ids = (
            set(issue_ids)
            if issue_ids
            else {
                issue.issue_id
                for issue in selectable
                if issue.repairability != "manual" and issue.issue_type not in self._AUTO_PLAN_EXCLUDED_ISSUE_TYPES
            }
        )
        selected_issues = [issue for issue in selectable if issue.issue_id in selected_ids]
        if not selected_issues:
            raise ValueError("当前没有可生成修复方案的问题。")

        next_proposals = list(stored_proposals)
        generated_proposals: list[CreativeRepairProposal] = []
        planning_feedback: dict[str, dict[str, object]] = {}
        field_patch_proposals, field_patch_feedback = self._build_field_patch_proposals(
            book_id,
            story_arcs,
            roadmap,
            roadmap_issues,
            selected_issues,
            stored_proposals,
        )
        generated_proposals.extend(field_patch_proposals)
        planning_feedback.update(field_patch_feedback)
        rewrite_proposals, rewrite_feedback = self._build_rewrite_proposals(
            book_id=book_id,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=roadmap_issues,
            selected_issues=selected_issues,
            stored_proposals=stored_proposals,
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=llm,
            judge_llm=judge_llm,
            relationship_graph=relationship_graph or [],
            candidate_count=candidate_count,
            judge_threshold=judge_threshold,
        )
        generated_proposals.extend(rewrite_proposals)
        planning_feedback.update(rewrite_feedback)
        if not generated_proposals and not planning_feedback:
            raise ValueError("当前问题暂无新的修复方案；可能已有待确认方案，或同类骨架重写刚执行过。")
        next_proposals.extend(generated_proposals)
        return sorted(next_proposals, key=lambda item: item.created_at, reverse=True), planning_feedback

    def _build_issue_planning_feedback(
        self,
        *,
        candidate_count: int,
        selected_candidate: RepairCandidate,
        recommended_next_action: str,
    ) -> dict[str, object]:
        """把“已评审但不可执行”的结果写成问题详情的只读反馈。"""

        return {
            "has_planning_feedback": True,
            "candidate_count": candidate_count,
            "selected_candidate_summary": selected_candidate.summary,
            "judge_mode": selected_candidate.judge_mode,
            "judge_health_status": selected_candidate.judge_health_status,
            "execution_readiness": selected_candidate.execution_readiness,
            "target_residual_issue_count": selected_candidate.target_residual_issue_count,
            "introduced_issue_count": len(selected_candidate.introduced_issue_types),
            "introduced_fatal_issue_count": len(selected_candidate.introduced_fatal_issue_ids),
            "blocking_reasons": list(selected_candidate.blocking_reasons),
            "recommended_next_action": recommended_next_action,
        }

    def apply_proposal(
        self,
        *,
        proposal: CreativeRepairProposal,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        expanded_arc_numbers: list[int],
    ) -> tuple[list[StoryArcPlan], list[ChapterRoadmapItem], list[int]]:
        """把提案操作真正应用到 roadmap 工作态。

        对 rewrite_arc 这里额外补一层区间保护：
        - proposal 虽然来自 planner，但 apply 仍要防守“坏提案/旧提案/手工篡改提案”；
        - 一旦发现阶段区间断裂或重叠，直接中止执行，不把损坏的分幕状态写回。
        """
        next_story_arcs = [arc.model_copy(deep=True) for arc in story_arcs]
        next_roadmap = [chapter.model_copy(deep=True) for chapter in roadmap]
        next_expanded_arc_numbers = list(expanded_arc_numbers)

        for operation in proposal.operations:
            if operation.op_type == "set_field":
                next_roadmap = self._apply_set_field_operation(next_roadmap, operation)
            elif operation.op_type == "rewrite_chapter":
                payload = operation.payload.get("chapter") or {}
                chapter = ChapterRoadmapItem.model_validate(payload)
                next_roadmap = [
                    chapter if item.chapter_number == chapter.chapter_number else item
                    for item in next_roadmap
                ]
            elif operation.op_type == "rewrite_arc":
                target_arc_number = int(operation.target_ref.get("arc_number") or 0)
                payload = operation.payload.get("story_arc") or {}
                replacement = StoryArcPlan.model_validate(payload)
                original_arc = next((arc for arc in next_story_arcs if arc.arc_number == target_arc_number), None)
                if original_arc is None:
                    raise ValueError(f"待重写的第 {target_arc_number} 幕不存在。")
                replacement = self._planner.preserve_story_arc_range(original_arc, replacement)
                next_story_arcs = [
                    replacement if arc.arc_number == target_arc_number else arc
                    for arc in next_story_arcs
                ]
                clear_numbers = {
                    int(number)
                    for number in operation.payload.get("clear_chapter_numbers") or []
                    if isinstance(number, int)
                }
                next_roadmap = [
                    item for item in next_roadmap if item.chapter_number not in clear_numbers
                ]
                next_expanded_arc_numbers = [
                    number for number in next_expanded_arc_numbers if number != target_arc_number
                ]

        next_roadmap.sort(key=lambda item: item.chapter_number)
        next_story_arcs.sort(key=lambda item: item.arc_number)
        self._planner.validate_story_arc_ranges(next_story_arcs)
        return next_story_arcs, next_roadmap, next_expanded_arc_numbers

    def build_snapshot_payload(self, state: dict[str, Any]) -> dict[str, object]:
        """只截取蓝图业务真源，避免回滚时把控制面历史一并抹掉。"""
        keys = [
            "status",
            "current_step",
            "selected_variant_id",
            "active_revision_id",
            "world_draft",
            "world_confirmed",
            "character_draft",
            "character_confirmed",
            "relationship_graph_draft",
            "relationship_graph_confirmed",
            "story_arcs_draft",
            "story_arcs_confirmed",
            "expanded_arc_numbers",
            "roadmap_draft",
            "roadmap_confirmed",
            "blueprint_continuity_state",
            "roadmap_validation_issues",
        ]
        return {key: copy.deepcopy(state.get(key)) for key in keys}

    def append_snapshot(
        self,
        *,
        book_id: int,
        snapshots: list[dict[str, object]],
        payload: dict[str, object],
        kind: str,
    ) -> tuple[list[dict[str, object]], str]:
        """新增一条快照，并限制历史长度。"""
        snapshot_id = _build_snapshot_id(book_id, kind)
        next_snapshots = [
            *snapshots,
            {
                "snapshot_id": snapshot_id,
                "book_id": book_id,
                "payload": payload,
                "created_at": _now_iso(),
            },
        ]
        return next_snapshots[-20:], snapshot_id

    def rollback_from_snapshot(
        self,
        *,
        snapshots: list[dict[str, object]],
        snapshot_id: str,
    ) -> dict[str, object]:
        """按快照 id 恢复业务真源。"""
        match = next((item for item in snapshots if str(item.get("snapshot_id")) == snapshot_id), None)
        if match is None:
            raise ValueError("回滚快照不存在。")
        payload = match.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("回滚快照损坏，无法恢复。")
        return copy.deepcopy(payload)

    def build_success_run(
        self,
        *,
        book_id: int,
        proposal_id: str,
        before_snapshot_ref: str,
        after_snapshot_ref: str,
        logs: list[str],
        eval_summary: RepairEvalSummary | None = None,
    ) -> CreativeRepairRun:
        return CreativeRepairRun(
            run_id=_build_run_id(proposal_id),
            book_id=book_id,
            proposal_id=proposal_id,
            execution_mode="apply",
            status="succeeded",
            logs=logs,
            before_snapshot_ref=before_snapshot_ref,
            after_snapshot_ref=after_snapshot_ref,
            eval_summary=eval_summary,
            created_at=_now_iso(),
        )

    def build_failed_run(
        self,
        *,
        book_id: int,
        proposal_id: str,
        error_message: str,
    ) -> CreativeRepairRun:
        return CreativeRepairRun(
            run_id=_build_run_id(proposal_id),
            book_id=book_id,
            proposal_id=proposal_id,
            execution_mode="apply",
            status="failed",
            logs=["修复提案执行失败。"],
            created_at=_now_iso(),
            error_message=error_message,
        )

    def build_repair_eval_summary(
        self,
        *,
        before_issues: list[CreativeIssue],
        after_issues: list[CreativeIssue],
        target_issue_ids: list[str],
        selected_candidate: RepairCandidate | None = None,
    ) -> RepairEvalSummary:
        """把一次执行前后的问题差异收口成作者可读的效果回执。

        这里刻意不把“执行成功”直接等同于“问题已修复”：
        - run 成功只说明补丁已落库、复验已跑完；
        - 真正有没有修好，要靠 before / after issue 差异来判定。
        """

        before_ids = {item.issue_id for item in before_issues}
        after_ids = {item.issue_id for item in after_issues}
        target_ids = set(target_issue_ids)
        resolved_issue_ids = sorted(target_ids - after_ids)
        residual_issue_ids = sorted(target_ids & after_ids)
        introduced_issue_ids = sorted(after_ids - before_ids)
        introduced_fatal_issue_ids = sorted(
            item.issue_id
            for item in after_issues
            if item.issue_id in introduced_issue_ids and item.severity == "fatal"
        )
        introduced_warning_issue_ids = sorted(
            item.issue_id
            for item in after_issues
            if item.issue_id in introduced_issue_ids and item.severity != "fatal"
        )
        before_issue_types = sorted({item.issue_type for item in before_issues})
        after_issue_types = sorted({item.issue_type for item in after_issues})

        if residual_issue_ids:
            next_action = "变更已应用，但目标问题仍有残留；建议查看右侧详情，决定继续重写、手动细修或推进后再复验。"
        elif introduced_issue_ids:
            next_action = "目标问题已缓解，但引入了新的后续问题；建议优先处理新增问题。"
        else:
            next_action = "目标问题已清除，可以继续推进当前路线。"

        return RepairEvalSummary(
            before_issue_ids=sorted(before_ids),
            after_issue_ids=sorted(after_ids),
            resolved_issue_ids=resolved_issue_ids,
            residual_issue_ids=residual_issue_ids,
            introduced_issue_ids=introduced_issue_ids,
            target_resolved_issue_ids=resolved_issue_ids,
            target_residual_issue_ids=residual_issue_ids,
            introduced_fatal_issue_ids=introduced_fatal_issue_ids,
            introduced_warning_issue_ids=introduced_warning_issue_ids,
            before_issue_types=before_issue_types,
            after_issue_types=after_issue_types,
            resolved_issue_count=len(resolved_issue_ids),
            residual_issue_count=len(residual_issue_ids),
            introduced_issue_count=len(introduced_issue_ids),
            target_resolved_issue_count=len(resolved_issue_ids),
            target_residual_issue_count=len(residual_issue_ids),
            judge_mode=selected_candidate.judge_mode if selected_candidate is not None else "none",
            execution_readiness=selected_candidate.execution_readiness if selected_candidate is not None else "executable",
            blocking_reasons=list(selected_candidate.blocking_reasons) if selected_candidate is not None else [],
            recommended_next_action=next_action,
        )

    def build_generation_eval_record(
        self,
        *,
        book_id: int,
        layer: str,
        task_type: str,
        source_model: str,
        prompt_version: str,
        candidate_count: int,
        selected_candidate: RepairCandidate,
        eval_summary: RepairEvalSummary,
        accepted_by: str,
        context_payload: dict[str, object] | None = None,
    ) -> GenerationEvalRecord:
        """把一次生成/重写的评审结果落成统一评测记录。"""

        return GenerationEvalRecord(
            eval_id=_build_generation_eval_id(book_id, task_type),
            book_id=book_id,
            layer=cast(Any, layer),
            task_type=cast(Any, task_type),
            source_model=source_model,
            prompt_version=prompt_version,
            candidate_count=candidate_count,
            selected_candidate_id=selected_candidate.candidate_id,
            before_issue_types=eval_summary.before_issue_types,
            after_issue_types=eval_summary.after_issue_types,
            resolved_issue_count=eval_summary.resolved_issue_count,
            residual_issue_count=eval_summary.residual_issue_count,
            introduced_issue_count=eval_summary.introduced_issue_count,
            judge_scores=selected_candidate.judge_scores,
            accepted_by=cast(Any, accepted_by),
            context_payload=context_payload or {},
            created_at=_now_iso(),
        )

    def judge_candidate(
        self,
        *,
        judge_llm: LLMClient | None,
        task_type: str,
        candidate_summary: str,
        target_issue_messages: list[str],
        residual_issue_types: list[str],
        introduced_issue_types: list[str],
        fixed_constraints: list[str],
    ) -> tuple[list[RepairJudgeScore], str, str, str]:
        """用 judge 模型给候选打分；失败时退回到稳定的启发式打分。

        这里的 judge 只负责排序，不负责直接修改真源：
        - 即使本地 judge 模型未来替换，生成真源的主语义也不会受影响；
        - 评测记录里保留 judge 分数，后续才能比较模型和提示词版本的真实效果。
        """

        if judge_llm is None:
            scores, summary = self._fallback_judge_scores(
                residual_issue_types=residual_issue_types,
                introduced_issue_types=introduced_issue_types,
            )
            return scores, summary, "none", "provider_unavailable"
        if not str(getattr(judge_llm, "model", "") or "").strip():
            scores, summary = self._fallback_judge_scores(
                residual_issue_types=residual_issue_types,
                introduced_issue_types=introduced_issue_types,
            )
            return scores, summary, "none", "config_invalid"

        prompt = (
            "你是长篇小说修复候选的评审器。请只返回 JSON。\n"
            f"任务类型：{task_type}\n"
            f"目标问题：{target_issue_messages}\n"
            f"候选摘要：{candidate_summary}\n"
            f"残留问题类型：{residual_issue_types}\n"
            f"新增问题类型：{introduced_issue_types}\n"
            f"硬约束：{fixed_constraints}\n"
            "请返回："
            "{summary, scores:[{dimension, score, rationale}]}"
        )
        try:
            raw = judge_llm.complete_json(
                prompt,
                system="你是严谨的小说质量评审。必须从问题解决、结构升级和连续性三个维度打分。",
            )
        except Exception:  # noqa: BLE001
            scores, summary = self._fallback_judge_scores(
                residual_issue_types=residual_issue_types,
                introduced_issue_types=introduced_issue_types,
            )
            return scores, summary, "heuristic", "provider_unavailable"
        try:
            raw_scores = raw.get("scores") if isinstance(raw.get("scores"), list) else []
            scores = [
                RepairJudgeScore.model_validate(item)
                for item in raw_scores
                if isinstance(item, dict)
            ]
            if scores:
                return scores, str(raw.get("summary") or "").strip(), "model", "model_ok"
        except Exception:  # noqa: BLE001
            pass
        scores, summary = self._fallback_judge_scores(
            residual_issue_types=residual_issue_types,
            introduced_issue_types=introduced_issue_types,
        )
        return scores, summary, "heuristic", "json_parse_failed"

    def select_best_candidate(
        self,
        candidates: list[RepairCandidate],
        *,
        judge_threshold: float = 0.0,
    ) -> RepairCandidate:
        """从多个候选里挑一个真正最值得落库的版本。

        排序规则刻意偏保守：
        1. 先看 fatal 是否减少；
        2. 再看残留问题和新增问题；
        3. 最后再参考 judge 总分。
        这样可以避免“文风更顺但问题没解决”的候选被误选。
        """

        if not candidates:
            raise ValueError("当前没有可选候选。")

        ordered = sorted(
            candidates,
            key=lambda item: (
                item.target_residual_issue_count,
                len(item.introduced_fatal_issue_ids),
                len(item.introduced_issue_types),
                item.verifier_fatal_count,
                -self._candidate_total_score(item),
            ),
        )
        best = ordered[0]
        for item in candidates:
            item.selected = item.candidate_id == best.candidate_id
        return best

    def _fallback_judge_scores(
        self,
        *,
        residual_issue_types: list[str],
        introduced_issue_types: list[str],
    ) -> tuple[list[RepairJudgeScore], str]:
        """当 judge 不可用时，用稳定启发式维持可排序性。"""

        issue_resolution = max(0.0, 5.0 - float(len(residual_issue_types) * 1.5))
        safety = max(0.0, 5.0 - float(len(introduced_issue_types)))
        scores = [
            RepairJudgeScore(
                dimension="issue_resolution",
                score=issue_resolution,
                rationale="残留问题越少，说明候选越接近真正解决目标问题。",
            ),
            RepairJudgeScore(
                dimension="safety",
                score=safety,
                rationale="新增问题越少，说明候选越稳，不会把旧问题换成新问题。",
            ),
        ]
        return scores, "judge 模型不可用，已退回到启发式排序。"

    def _classify_issue(
        self,
        issue: RoadmapValidationIssue,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
    ) -> tuple[str, str | None]:
        if issue.type in self._DETERMINISTIC_ISSUE_TYPES:
            return "deterministic", "field_patch"
        if issue.type in self._ARC_REWRITE_ISSUE_TYPES:
            # 阶段级问题仍然保留 arc_rewrite 能力，但默认不再混入“全量生成修复方案”。
            # 只有作者显式点到该问题时，才会真正规划骨架重写，避免反复打断继续展开。
            return "llm", "arc_rewrite"
        if issue.type in self._CHAPTER_REWRITE_ISSUE_TYPES:
            if issue.chapter_number is not None and self._can_rewrite_as_last_chapter(issue.chapter_number, story_arcs, roadmap):
                return "llm", "chapter_rewrite"
            return "llm", "arc_rewrite"
        if issue.type in {"relationship_break_without_reveal", "world_rule_conflict"}:
            return "manual", None
        return "manual", None

    def _can_rewrite_as_last_chapter(
        self,
        chapter_number: int,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
    ) -> bool:
        arc = self._find_arc_for_chapter(chapter_number, story_arcs)
        if arc is None:
            return False
        arc_chapters = self._planner.get_arc_chapters(arc, roadmap)
        return bool(arc_chapters) and arc_chapters[-1].chapter_number == chapter_number

    def _build_field_patch_proposals(
        self,
        book_id: int,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        roadmap_issues: list[RoadmapValidationIssue],
        selected_issues: list[CreativeIssue],
        stored_proposals: list[CreativeRepairProposal],
    ) -> tuple[list[CreativeRepairProposal], dict[str, dict[str, object]]]:
        issue_map = {_build_issue_id(issue): issue for issue in roadmap_issues}
        grouped: dict[int, list[CreativeIssue]] = {}
        planning_feedback: dict[str, dict[str, object]] = {}
        for issue in selected_issues:
            if issue.repairability != "deterministic":
                continue
            chapter_number = int(issue.target_ref.get("chapter_number") or 0)
            if chapter_number > 0:
                grouped.setdefault(chapter_number, []).append(issue)

        proposals: list[CreativeRepairProposal] = []
        before_issue_models = self.build_creative_issues(
            book_id=book_id,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=roadmap_issues,
            stored_proposals=stored_proposals,
        )
        for chapter_number, issues in grouped.items():
            chapter = next((item for item in roadmap if item.chapter_number == chapter_number), None)
            if chapter is None:
                continue
            arc = self._find_arc_for_chapter(chapter_number, story_arcs)
            operations: list[RepairOperation] = []
            diff_preview: list[dict[str, object]] = []
            for issue in issues:
                original_issue = issue_map.get(issue.issue_id)
                if original_issue is None:
                    continue
                new_ops, preview_rows = self._build_field_patch_operations_for_issue(
                    issue=original_issue,
                    chapter=chapter,
                    roadmap=roadmap,
                    arc=arc,
                )
                operations.extend(new_ops)
                diff_preview.extend(preview_rows)
            if not operations:
                continue
            proposal_signature = _build_proposal_signature(
                [issue.issue_signature for issue in issues],
                "field_patch",
            )
            if self._has_proposal_signature(
                stored_proposals,
                proposal_signature,
                statuses={"awaiting_approval"},
            ):
                continue
            candidate_roadmap = [item.model_copy(deep=True) for item in roadmap]
            for operation in operations:
                if operation.op_type == "set_field":
                    candidate_roadmap = self._apply_set_field_operation(candidate_roadmap, operation)
            after_issues = self._planner.verify_roadmap(
                story_arcs,
                candidate_roadmap,
                world=None,
                relationship_graph=[],
            )
            after_issue_models = self.build_creative_issues(
                book_id=book_id,
                story_arcs=story_arcs,
                roadmap=candidate_roadmap,
                roadmap_issues=after_issues,
                stored_proposals=stored_proposals,
            )
            candidate = self.evaluate_candidate_gate(
                candidate=RepairCandidate(
                    candidate_id=_build_candidate_id(f"field-patch-{chapter_number}"),
                    prompt_version="repair.field_patch.v1",
                    summary=f"结构补丁候选：修复第 {chapter_number} 章的 {len(issues)} 个结构问题",
                    applied_issue_ids=[issue.issue_id for issue in issues],
                    judge_mode="none",
                    judge_health_status="model_ok",
                    diff_preview=diff_preview,
                    verifier_fatal_count=sum(1 for item in after_issue_models if item.severity == "fatal"),
                    verifier_warning_count=sum(1 for item in after_issue_models if item.severity != "fatal"),
                    model_name="deterministic",
                ),
                before_issues=before_issue_models,
                after_issues=after_issue_models,
                target_issue_ids=[issue.issue_id for issue in issues],
                judge_threshold=0.0,
                requires_model_judge=False,
            )
            if candidate.execution_readiness != "executable":
                feedback = self._build_issue_planning_feedback(
                    candidate_count=1,
                    selected_candidate=candidate,
                    recommended_next_action="结构补丁无法稳定清除目标问题，请改为手动细修，或切换到更大粒度的重写。",
                )
                for issue in issues:
                    planning_feedback[issue.issue_id] = feedback
                continue
            proposals.append(
                CreativeRepairProposal(
                    proposal_id=_build_proposal_id([issue.issue_id for issue in issues], "field_patch"),
                    book_id=book_id,
                    issue_ids=[issue.issue_id for issue in issues],
                    strategy_type="field_patch",
                    risk_level="low",
                    status="awaiting_approval",
                    proposal_signature=proposal_signature,
                    operations=operations,
                    summary=f"修复第 {chapter_number} 章的 {len(issues)} 个结构问题",
                    diff_preview=diff_preview,
                    candidates=[candidate],
                    expected_post_conditions=["当前章节的结构型 fatal 应明显减少或消失。"],
                    requires_llm=False,
                    created_at=_now_iso(),
                )
            )
        return proposals, planning_feedback

    def _build_rewrite_proposals(
        self,
        *,
        book_id: int,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        roadmap_issues: list[RoadmapValidationIssue],
        selected_issues: list[CreativeIssue],
        stored_proposals: list[CreativeRepairProposal],
        intent: Any | None,
        variant: ConceptVariant | None,
        world: WorldBlueprint | None,
        characters: list[CharacterBlueprint],
        llm: LLMClient | None,
        judge_llm: LLMClient | None,
        relationship_graph: list[Any],
        candidate_count: int,
        judge_threshold: float,
    ) -> tuple[list[CreativeRepairProposal], dict[str, dict[str, object]]]:
        if intent is None or variant is None or world is None or llm is None:
            return [], {}
        issue_map = {_build_issue_id(issue): issue for issue in roadmap_issues}
        proposals: list[CreativeRepairProposal] = []
        planning_feedback: dict[str, dict[str, object]] = {}
        before_issue_models = self.build_creative_issues(
            book_id=book_id,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=roadmap_issues,
            stored_proposals=stored_proposals,
        )

        chapter_groups: dict[int, list[CreativeIssue]] = {}
        arc_groups: dict[int, list[CreativeIssue]] = {}
        for issue in selected_issues:
            if issue.repairability != "llm":
                continue
            chapter_number = int(issue.target_ref.get("chapter_number") or 0)
            arc_number = int(issue.target_ref.get("arc_number") or 0)
            if issue.suggested_strategy == "chapter_rewrite" and chapter_number > 0:
                chapter_groups.setdefault(chapter_number, []).append(issue)
            elif arc_number > 0:
                arc_groups.setdefault(arc_number, []).append(issue)

        for chapter_number, issues in chapter_groups.items():
            arc = self._find_arc_for_chapter(chapter_number, story_arcs)
            if arc is None or not self._can_rewrite_as_last_chapter(chapter_number, story_arcs, roadmap):
                if arc is not None:
                    arc_groups.setdefault(arc.arc_number, []).extend(issues)
                continue
            current_chapter = next((item for item in roadmap if item.chapter_number == chapter_number), None)
            if current_chapter is None:
                continue
            feedback = self._build_rewrite_feedback([issue_map[item.issue_id] for item in issues if item.issue_id in issue_map])
            proposal_signature = _build_proposal_signature(
                [issue.issue_signature for issue in issues],
                "chapter_rewrite",
            )
            if self._has_proposal_signature(
                stored_proposals,
                proposal_signature,
                statuses={"awaiting_approval"},
            ):
                continue
            target_issue_messages = [issue_map[item.issue_id].message for item in issues if item.issue_id in issue_map]
            target_issue_types = {
                issue_map[item.issue_id].type
                for item in issues
                if item.issue_id in issue_map
            }
            chapter_candidates: list[RepairCandidate] = []
            rewritten_by_candidate_id: dict[str, ChapterRoadmapItem] = {}
            for _ in range(max(1, candidate_count)):
                rewritten = self._planner.regenerate_last_arc_chapter(
                    intent=intent,
                    variant=variant,
                    world=world,
                    characters=characters,
                    llm=llm,
                    story_arc=arc,
                    chapter_number=chapter_number,
                    feedback=feedback,
                    existing_roadmap=roadmap,
                )
                candidate_roadmap = [
                    rewritten if item.chapter_number == chapter_number else item
                    for item in roadmap
                ]
                after_issues = self._planner.verify_roadmap(
                    story_arcs,
                    candidate_roadmap,
                    world=world,
                    relationship_graph=relationship_graph,
                )
                residual_issue_types = sorted({item.type for item in after_issues if item.type in target_issue_types})
                introduced_issue_types = sorted({item.type for item in after_issues if item.type not in target_issue_types})
                judge_scores, judge_summary, judge_mode, judge_health_status = self.judge_candidate(
                    judge_llm=judge_llm,
                    task_type="rewrite_chapter",
                    candidate_summary=(
                        f"标题：{rewritten.title}\n"
                        f"章节功能：{rewritten.chapter_function}\n"
                        f"主线推进：{rewritten.story_progress}\n"
                        f"关键事件：{'；'.join(rewritten.key_events)}"
                    ),
                    target_issue_messages=target_issue_messages,
                    residual_issue_types=residual_issue_types,
                    introduced_issue_types=introduced_issue_types,
                    fixed_constraints=["必须保留前文连续性", "不能破坏当前阶段的章号和顺序"],
                )
                after_issue_models = self.build_creative_issues(
                    book_id=book_id,
                    story_arcs=story_arcs,
                    roadmap=candidate_roadmap,
                    roadmap_issues=after_issues,
                    stored_proposals=stored_proposals,
                )
                candidate = self.evaluate_candidate_gate(
                    candidate=RepairCandidate(
                    candidate_id=_build_candidate_id(f"chapter-rewrite-{chapter_number}"),
                    prompt_version="repair.rewrite_chapter.v1",
                    summary=judge_summary or f"候选章节：{rewritten.title}",
                    applied_issue_ids=[issue.issue_id for issue in issues],
                    judge_scores=judge_scores,
                    residual_issue_types=residual_issue_types,
                    introduced_issue_types=introduced_issue_types,
                    judge_mode=cast(Any, judge_mode),
                    judge_health_status=cast(Any, judge_health_status),
                    diff_preview=self._build_chapter_rewrite_preview(current_chapter, rewritten),
                    verifier_fatal_count=sum(1 for item in after_issues if item.severity == "fatal"),
                    verifier_warning_count=sum(1 for item in after_issues if item.severity == "warning"),
                    model_name=llm.model,
                    ),
                    before_issues=before_issue_models,
                    after_issues=after_issue_models,
                    target_issue_ids=[issue.issue_id for issue in issues],
                    judge_threshold=judge_threshold,
                    requires_model_judge=True,
                )
                chapter_candidates.append(candidate)
                rewritten_by_candidate_id[candidate.candidate_id] = rewritten

            best_candidate = self.select_best_candidate(chapter_candidates, judge_threshold=judge_threshold)
            if best_candidate.execution_readiness != "executable":
                feedback = self._build_issue_planning_feedback(
                    candidate_count=len(chapter_candidates),
                    selected_candidate=best_candidate,
                    recommended_next_action="已评审多个单章候选，但当前没有可自动执行的方案；建议手动细修该章，或在 judge 恢复后重新生成。",
                )
                for issue in issues:
                    planning_feedback[issue.issue_id] = feedback
                continue
            rewritten = rewritten_by_candidate_id[best_candidate.candidate_id]
            proposals.append(
                CreativeRepairProposal(
                    proposal_id=_build_proposal_id([issue.issue_id for issue in issues], "chapter_rewrite"),
                    book_id=book_id,
                    issue_ids=[issue.issue_id for issue in issues],
                    strategy_type="chapter_rewrite",
                    risk_level="medium",
                    status="awaiting_approval",
                    proposal_signature=proposal_signature,
                    operations=[
                        RepairOperation(
                            op_type="rewrite_chapter",
                            target_ref={"chapter_number": chapter_number, "arc_number": arc.arc_number},
                            payload={"chapter": rewritten.model_dump(mode="json")},
                            reason=feedback,
                        )
                    ],
                    summary=f"重写第 {chapter_number} 章以解决语义连续性问题",
                    diff_preview=best_candidate.diff_preview,
                    candidates=chapter_candidates,
                    expected_post_conditions=["当前章节的重复、停滞或缺失结构问题应在复验后消失。"],
                    requires_llm=True,
                    created_at=_now_iso(),
                )
            )

        for arc_number, issues in arc_groups.items():
            if arc_number <= 0:
                continue
            arc = next((item for item in story_arcs if item.arc_number == arc_number), None)
            if arc is None:
                continue
            total_start_chapter = min((item.start_chapter for item in story_arcs), default=arc.start_chapter)
            total_end_chapter = max((item.end_chapter for item in story_arcs), default=arc.end_chapter)
            feedback = self._build_rewrite_feedback([issue_map[item.issue_id] for item in issues if item.issue_id in issue_map])
            proposal_signature = _build_proposal_signature(
                [issue.issue_signature for issue in issues],
                "arc_rewrite",
            )
            if self._has_proposal_signature(
                stored_proposals,
                proposal_signature,
                statuses={"awaiting_approval", "applied"},
            ):
                continue
            clear_numbers = [
                item.chapter_number
                for item in roadmap
                if arc.start_chapter <= item.chapter_number <= arc.end_chapter
            ]
            target_issue_messages = [issue_map[item.issue_id].message for item in issues if item.issue_id in issue_map]
            target_issue_types = {
                issue_map[item.issue_id].type
                for item in issues
                if item.issue_id in issue_map
            }
            arc_candidates: list[RepairCandidate] = []
            replacement_by_candidate_id: dict[str, StoryArcPlan] = {}
            for _ in range(max(1, candidate_count)):
                regenerated_arcs = self._planner.regenerate_story_arc_skeleton(
                    intent=intent,
                    variant=variant,
                    world=world,
                    characters=characters,
                    llm=llm,
                    story_arcs=story_arcs,
                    arc_number=arc_number,
                    feedback=feedback,
                    starting_chapter=total_start_chapter,
                    chapter_count=total_end_chapter - total_start_chapter + 1,
                    existing_roadmap=[item for item in roadmap if item.chapter_number < arc.start_chapter],
                )
                replacement = next((item for item in regenerated_arcs if item.arc_number == arc_number), None)
                if replacement is None:
                    continue
                residual_issue_types = (
                    sorted(target_issue_types)
                    if (
                        replacement.purpose == arc.purpose
                        and replacement.main_progress == arc.main_progress
                        and replacement.arc_climax == arc.arc_climax
                    )
                    else []
                )
                judge_scores, judge_summary, judge_mode, judge_health_status = self.judge_candidate(
                    judge_llm=judge_llm,
                    task_type="rewrite_arc",
                    candidate_summary=(
                        f"阶段目的：{replacement.purpose}\n"
                        f"主线推进：{'；'.join(replacement.main_progress)}\n"
                        f"关系推进：{'；'.join(replacement.relationship_progress)}\n"
                        f"阶段高潮：{replacement.arc_climax}"
                    ),
                    target_issue_messages=target_issue_messages,
                    residual_issue_types=residual_issue_types,
                    introduced_issue_types=[],
                    fixed_constraints=["必须保留当前幕原有章号区间", "不能改动后续阶段的章号边界"],
                )
                candidate = self.evaluate_candidate_gate(
                    candidate=RepairCandidate(
                    candidate_id=_build_candidate_id(f"arc-rewrite-{arc_number}"),
                    prompt_version="repair.rewrite_arc.v1",
                    summary=judge_summary or f"候选阶段目的：{replacement.purpose}",
                    applied_issue_ids=[issue.issue_id for issue in issues],
                    judge_scores=judge_scores,
                    residual_issue_types=residual_issue_types,
                    introduced_issue_types=[],
                    judge_mode=cast(Any, judge_mode),
                    judge_health_status=cast(Any, judge_health_status),
                    diff_preview=self._build_arc_rewrite_preview(arc, replacement, clear_numbers),
                    verifier_fatal_count=len(residual_issue_types),
                    verifier_warning_count=0,
                    model_name=llm.model,
                    ),
                    before_issues=before_issue_models,
                    after_issues=[],
                    target_issue_ids=[issue.issue_id for issue in issues],
                    judge_threshold=judge_threshold,
                    requires_model_judge=True,
                )
                arc_candidates.append(candidate)
                replacement_by_candidate_id[candidate.candidate_id] = replacement
            if not arc_candidates:
                continue
            best_candidate = self.select_best_candidate(arc_candidates, judge_threshold=judge_threshold)
            if best_candidate.execution_readiness != "executable":
                feedback = self._build_issue_planning_feedback(
                    candidate_count=len(arc_candidates),
                    selected_candidate=best_candidate,
                    recommended_next_action="当前幕已评审多个骨架候选，但都未达到自动执行门槛；建议先手动细化章节，或等 judge 恢复后再重新评审。",
                )
                for issue in issues:
                    planning_feedback[issue.issue_id] = feedback
                continue
            replacement = replacement_by_candidate_id[best_candidate.candidate_id]
            proposals.append(
                CreativeRepairProposal(
                    proposal_id=_build_proposal_id([issue.issue_id for issue in issues], "arc_rewrite"),
                    book_id=book_id,
                    issue_ids=[issue.issue_id for issue in issues],
                    strategy_type="arc_rewrite",
                    risk_level="high",
                    status="awaiting_approval",
                    proposal_signature=proposal_signature,
                    operations=[
                        RepairOperation(
                            op_type="rewrite_arc",
                            target_ref={"arc_number": arc_number},
                            payload={
                                "story_arc": replacement.model_dump(mode="json"),
                                "clear_chapter_numbers": clear_numbers,
                            },
                            reason=feedback,
                        )
                    ],
                    summary=f"重写第 {arc_number} 幕骨架（保留本幕章号区间），并清空该幕已生成章节以重新展开",
                    diff_preview=best_candidate.diff_preview,
                    candidates=arc_candidates,
                    expected_post_conditions=[
                        "该幕的结构性重复或停滞问题应通过重新展开得到缓解。",
                        "当前幕的章号区间保持不变，后续幕的分幕范围不会被一起改写。",
                    ],
                    requires_llm=True,
                    created_at=_now_iso(),
                )
            )

        return proposals, planning_feedback

    def _has_proposal_signature(
        self,
        proposals: list[CreativeRepairProposal],
        proposal_signature: str,
        *,
        statuses: set[str],
    ) -> bool:
        """判断当前是否已经存在同签名提案。

        这里把“当前待确认”和“最近已执行”分开控制：
        - 所有提案至少要避免在 awaiting_approval 状态下重复堆叠；
        - arc_rewrite 还需要额外避开“刚执行过又立刻再来一次”的噪音。
        """

        return any(
            proposal.proposal_signature == proposal_signature and proposal.status in statuses
            for proposal in proposals
        )

    def _build_field_patch_operations_for_issue(
        self,
        *,
        issue: RoadmapValidationIssue,
        chapter: ChapterRoadmapItem,
        roadmap: list[ChapterRoadmapItem],
        arc: StoryArcPlan | None,
    ) -> tuple[list[RepairOperation], list[dict[str, object]]]:
        previous_tasks = {
            task.task_id
            for item in roadmap
            if item.chapter_number < chapter.chapter_number
            for task in item.chapter_tasks
        }
        operations: list[RepairOperation] = []
        preview: list[dict[str, object]] = []

        def add_set_field(
            *,
            target_ref: dict[str, object],
            field_name: str,
            before: object,
            after: object,
            reason: str,
        ) -> None:
            if before == after:
                return
            operations.append(
                RepairOperation(
                    op_type="set_field",
                    target_ref=target_ref,
                    payload={"field_name": field_name, "value": after},
                    reason=reason,
                )
            )
            preview.append(
                {
                    "kind": "field_patch",
                    "target": target_ref,
                    "field_name": field_name,
                    "before": before,
                    "after": after,
                    "reason": reason,
                }
            )

        if issue.type == "task_status_jump":
            for task in chapter.chapter_tasks:
                if task.task_id not in previous_tasks and task.status in {"in_progress", "resolved", "failed"}:
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "task_id": task.task_id, "entity": "chapter_task"},
                        field_name="status",
                        before=task.status,
                        after="new",
                        reason="首次出现的任务不能直接进入推进中或已结束状态。",
                    )
        elif issue.type == "duplicate_task_creation":
            for task in chapter.chapter_tasks:
                if task.task_id in previous_tasks and task.status == "new":
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "task_id": task.task_id, "entity": "chapter_task"},
                        field_name="status",
                        before=task.status,
                        after="in_progress",
                        reason="重复出现的任务更像继续推进，而不是再次新建。",
                    )
        elif issue.type in {"invalid_chapter_dependency", "missing_previous_dependency"}:
            valid_dependencies = sorted({dep for dep in chapter.depends_on_chapters if dep < chapter.chapter_number})
            if chapter.chapter_number > 1 and chapter.chapter_number - 1 not in valid_dependencies:
                valid_dependencies.append(chapter.chapter_number - 1)
            add_set_field(
                target_ref={"chapter_number": chapter.chapter_number, "entity": "chapter"},
                field_name="depends_on_chapters",
                before=chapter.depends_on_chapters,
                after=sorted(valid_dependencies),
                reason="当前章节必须承接上一章，且不能依赖未来章节或自身。",
            )
        elif issue.type in {"task_overdue", "task_still_overdue"}:
            for task in chapter.chapter_tasks:
                target_due = max(chapter.chapter_number, arc.end_chapter if arc is not None else chapter.chapter_number)
                if task.due_end_chapter is not None and task.due_end_chapter < target_due and task.status not in {"resolved", "failed"}:
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "task_id": task.task_id, "entity": "chapter_task"},
                        field_name="due_end_chapter",
                        before=task.due_end_chapter,
                        after=target_due,
                        reason="任务已过最迟章号却未结束，先把截止边界调整到当前阶段末尾。",
                    )
        elif issue.type in {"loop_missing_title", "loop_missing_summary", "loop_missing_due_end", "loop_due_end_before_intro", "loop_due_window_invalid", "loop_overdue", "loop_still_overdue"}:
            for index, loop in enumerate(chapter.planned_loops, start=1):
                target_due = max(
                    chapter.chapter_number,
                    loop.due_start_chapter or chapter.chapter_number,
                    arc.end_chapter if arc is not None else chapter.chapter_number,
                )
                if issue.type == "loop_missing_title" and not loop.title.strip():
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "loop_id": loop.loop_id, "entity": "planned_loop"},
                        field_name="title",
                        before=loop.title,
                        after=loop.summary or f"伏笔 {index}",
                        reason="伏笔标题缺失时，优先用摘要或默认标题补齐。",
                    )
                if issue.type == "loop_missing_summary" and not loop.summary.strip():
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "loop_id": loop.loop_id, "entity": "planned_loop"},
                        field_name="summary",
                        before=loop.summary,
                        after=loop.title or f"伏笔 {index}",
                        reason="伏笔摘要缺失时，先用标题补齐，保证后续连续性可读。",
                    )
                if issue.type == "loop_missing_due_end" and loop.due_end_chapter is None:
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "loop_id": loop.loop_id, "entity": "planned_loop"},
                        field_name="due_end_chapter",
                        before=loop.due_end_chapter,
                        after=target_due,
                        reason="缺少最迟兑现章时，先用当前阶段末章兜住回收边界。",
                    )
                if issue.type in {"loop_due_end_before_intro", "loop_overdue", "loop_still_overdue"} and loop.due_end_chapter is not None and loop.due_end_chapter < target_due:
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "loop_id": loop.loop_id, "entity": "planned_loop"},
                        field_name="due_end_chapter",
                        before=loop.due_end_chapter,
                        after=target_due,
                        reason="伏笔的最迟兑现章不能早于引入章，也不能在未回收前已经过期。",
                    )
                if issue.type == "loop_due_window_invalid" and loop.due_start_chapter is not None and loop.due_start_chapter > (loop.due_end_chapter or target_due):
                    add_set_field(
                        target_ref={"chapter_number": chapter.chapter_number, "loop_id": loop.loop_id, "entity": "planned_loop"},
                        field_name="due_end_chapter",
                        before=loop.due_end_chapter,
                        after=target_due,
                        reason="开始章晚于截止章时，先把截止章调到不小于开始章。",
                    )

        return operations, preview

    def _build_rewrite_feedback(self, issues: list[RoadmapValidationIssue]) -> str:
        issue_lines = [f"{index + 1}. {item.message}" for index, item in enumerate(issues)]
        return "请优先修复以下问题，并保持前文连续性：\n" + "\n".join(issue_lines)

    def _build_chapter_rewrite_preview(
        self,
        before: ChapterRoadmapItem,
        after: ChapterRoadmapItem,
    ) -> list[dict[str, object]]:
        return [
            {"kind": "chapter_rewrite", "field_name": "title", "before": before.title, "after": after.title},
            {"kind": "chapter_rewrite", "field_name": "chapter_function", "before": before.chapter_function, "after": after.chapter_function},
            {"kind": "chapter_rewrite", "field_name": "story_progress", "before": before.story_progress, "after": after.story_progress},
            {"kind": "chapter_rewrite", "field_name": "key_events", "before": before.key_events, "after": after.key_events},
        ]

    def _build_arc_rewrite_preview(
        self,
        before: StoryArcPlan,
        after: StoryArcPlan,
        clear_numbers: list[int],
    ) -> list[dict[str, object]]:
        return [
            {"kind": "arc_rewrite", "field_name": "purpose", "before": before.purpose, "after": after.purpose},
            {"kind": "arc_rewrite", "field_name": "main_progress", "before": before.main_progress, "after": after.main_progress},
            {"kind": "arc_rewrite", "field_name": "arc_climax", "before": before.arc_climax, "after": after.arc_climax},
            {"kind": "arc_rewrite", "field_name": "clear_chapter_numbers", "before": [], "after": clear_numbers},
        ]

    def _apply_set_field_operation(
        self,
        roadmap: list[ChapterRoadmapItem],
        operation: RepairOperation,
    ) -> list[ChapterRoadmapItem]:
        chapter_number = int(operation.target_ref.get("chapter_number") or 0)
        entity = str(operation.target_ref.get("entity") or "chapter")
        field_name = str(operation.payload.get("field_name") or "")
        value = operation.payload.get("value")
        next_roadmap: list[ChapterRoadmapItem] = []

        for chapter in roadmap:
            if chapter.chapter_number != chapter_number:
                next_roadmap.append(chapter)
                continue
            updated = chapter.model_copy(deep=True)
            if entity == "chapter":
                next_roadmap.append(updated.model_copy(update={field_name: value}))
                continue
            if entity == "chapter_task":
                task_id = str(operation.target_ref.get("task_id") or "")
                next_tasks = [
                    task.model_copy(update={field_name: value}) if task.task_id == task_id else task
                    for task in updated.chapter_tasks
                ]
                next_roadmap.append(updated.model_copy(update={"chapter_tasks": next_tasks}))
                continue
            if entity == "planned_loop":
                loop_id = str(operation.target_ref.get("loop_id") or "")
                next_loops = [
                    loop.model_copy(update={field_name: value}) if loop.loop_id == loop_id else loop
                    for loop in updated.planned_loops
                ]
                next_roadmap.append(updated.model_copy(update={"planned_loops": next_loops}))
                continue
            next_roadmap.append(updated)
        return next_roadmap

    def _find_arc_for_chapter(
        self,
        chapter_number: int,
        story_arcs: list[StoryArcPlan],
    ) -> StoryArcPlan | None:
        return next(
            (arc for arc in story_arcs if arc.start_chapter <= chapter_number <= arc.end_chapter),
            None,
        )
