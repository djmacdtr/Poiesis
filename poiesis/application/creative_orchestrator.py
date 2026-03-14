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
from typing import Any

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    CreativeIssue,
    CreativeRepairProposal,
    CreativeRepairRun,
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
    raw = f"{proposal_id}|{_now_iso()}"
    return f"repair-run-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


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
    ) -> list[CreativeIssue]:
        """把 verifier 原始结果升级成统一问题队列。"""
        active_issue_ids = {
            issue_id
            for proposal in stored_proposals
            if proposal.status == "awaiting_approval"
            for issue_id in proposal.issue_ids
        }
        issues: list[CreativeIssue] = []
        for issue in roadmap_issues:
            issue_id = _build_issue_id(issue)
            issue_signature = _build_issue_signature(issue)
            target_type = "roadmap_chapter" if issue.chapter_number is not None else "roadmap_arc"
            repairability, suggested_strategy = self._classify_issue(issue, story_arcs, roadmap)
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
                    status="awaiting_approval" if issue_id in active_issue_ids else "open",
                    suggested_strategy=suggested_strategy,
                    issue_signature=issue_signature,
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
    ) -> list[CreativeRepairProposal]:
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
        generated_proposals.extend(
            self._build_field_patch_proposals(
                book_id,
                story_arcs,
                roadmap,
                roadmap_issues,
                selected_issues,
                stored_proposals,
            )
        )
        generated_proposals.extend(
            self._build_rewrite_proposals(
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
            )
        )
        if not generated_proposals:
            raise ValueError("当前问题暂无新的修复方案；可能已有待确认方案，或同类骨架重写刚执行过。")
        next_proposals.extend(generated_proposals)
        return sorted(next_proposals, key=lambda item: item.created_at, reverse=True)

    def apply_proposal(
        self,
        *,
        proposal: CreativeRepairProposal,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        expanded_arc_numbers: list[int],
    ) -> tuple[list[StoryArcPlan], list[ChapterRoadmapItem], list[int]]:
        """把提案操作真正应用到 roadmap 工作态。"""
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
    ) -> list[CreativeRepairProposal]:
        issue_map = {_build_issue_id(issue): issue for issue in roadmap_issues}
        grouped: dict[int, list[CreativeIssue]] = {}
        for issue in selected_issues:
            if issue.repairability != "deterministic":
                continue
            chapter_number = int(issue.target_ref.get("chapter_number") or 0)
            if chapter_number > 0:
                grouped.setdefault(chapter_number, []).append(issue)

        proposals: list[CreativeRepairProposal] = []
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
                    expected_post_conditions=["当前章节的结构型 fatal 应明显减少或消失。"],
                    requires_llm=False,
                    created_at=_now_iso(),
                )
            )
        return proposals

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
    ) -> list[CreativeRepairProposal]:
        if intent is None or variant is None or world is None or llm is None:
            return []
        issue_map = {_build_issue_id(issue): issue for issue in roadmap_issues}
        proposals: list[CreativeRepairProposal] = []

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
                    diff_preview=self._build_chapter_rewrite_preview(current_chapter, rewritten),
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
            regenerated_arcs = self._planner.regenerate_story_arc_skeleton(
                intent=intent,
                variant=variant,
                world=world,
                characters=characters,
                llm=llm,
                story_arcs=story_arcs,
                arc_number=arc_number,
                feedback=feedback,
                existing_roadmap=[item for item in roadmap if item.chapter_number < arc.start_chapter],
            )
            replacement = next((item for item in regenerated_arcs if item.arc_number == arc_number), None)
            if replacement is None:
                continue
            clear_numbers = [
                item.chapter_number
                for item in roadmap
                if arc.start_chapter <= item.chapter_number <= arc.end_chapter
            ]
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
                    summary=f"重写第 {arc_number} 幕骨架，并清空该幕已生成章节以重新展开",
                    diff_preview=self._build_arc_rewrite_preview(arc, replacement, clear_numbers),
                    expected_post_conditions=["该幕的结构性重复或停滞问题应通过重新展开得到缓解。"],
                    requires_llm=True,
                    created_at=_now_iso(),
                )
            )

        return proposals

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
