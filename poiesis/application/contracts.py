"""生成流水线与 trace API 使用的结构化协议。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SceneStub(BaseModel):
    """为后续 scene 级规划预留的最小结构。"""

    title: str = ""
    goal: str = ""
    conflict: str = ""
    turning_point: str = ""


class PlannerOutput(BaseModel):
    """规划器稳定输出协议。

    这里保留旧版 planner 的关键信息，同时补上新阶段需要的统一字段，
    让 trace、前端展示和后续重构都依赖同一份结构。
    """

    title: str = ""
    chapter_goal: str = ""
    scene_stubs: list[SceneStub] = Field(default_factory=list)
    must_preserve: list[str] = Field(default_factory=list)
    must_progress_loops: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    summary: str = ""
    key_events: list[str] = Field(default_factory=list)
    character_arcs: dict[str, Any] = Field(default_factory=dict)
    new_facts_budget: int = 0
    foreshadowing_hints: list[str] = Field(default_factory=list)
    tone: str = ""
    opening_hook: str = ""
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    def to_runtime_plan(self) -> dict[str, Any]:
        """回投为旧模块可直接消费的 dict，降低渐进重构成本。"""
        payload = {
            "title": self.title,
            "summary": self.summary,
            "key_events": self.key_events,
            "character_arcs": self.character_arcs,
            "new_facts_budget": self.new_facts_budget,
            "foreshadowing_hints": self.foreshadowing_hints,
            "tone": self.tone,
            "opening_hook": self.opening_hook,
            "chapter_goal": self.chapter_goal,
            "scene_stubs": [item.model_dump() for item in self.scene_stubs],
            "must_preserve": self.must_preserve,
            "must_progress_loops": self.must_progress_loops,
            "notes": self.notes,
        }
        # 尽量保留旧 planner 的原始字段，避免 writer / verifier 丢信息。
        if self.raw_payload:
            payload.update(self.raw_payload)
        return payload


class ChangeSet(BaseModel):
    """从正文提取出的结构化变更集合。"""

    characters: list[dict[str, Any]] = Field(default_factory=list)
    world_rules: list[dict[str, Any]] = Field(default_factory=list)
    timeline_events: list[dict[str, Any]] = Field(default_factory=list)
    foreshadowing_updates: list[dict[str, Any]] = Field(default_factory=list)
    uncertain_claims: list[dict[str, Any]] = Field(default_factory=list)
    raw_staging_changes: list[dict[str, Any]] = Field(default_factory=list)

    def all_changes(self) -> list[dict[str, Any]]:
        """返回兼容旧 merger 逻辑的原始 staging changes。"""
        return list(self.raw_staging_changes)


IssueSeverity = Literal["fatal", "warning", "info"]


class VerifierIssue(BaseModel):
    """统一的校验问题结构，供 trace API 和前端直接展示。"""

    severity: IssueSeverity = "fatal"
    type: str = "consistency"
    reason: str
    repair_hint: str = ""
    location: str = ""
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ChapterMetrics(BaseModel):
    """章节级轻量指标快照。"""

    accepted_first_pass: bool = False
    edit_loop_count: int = 0
    issues_count: int = 0
    changes_count: int = 0


class RunTraceSummary(BaseModel):
    """一次运行的摘要信息。"""

    run_id: int
    task_id: str
    book_id: int
    status: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    llm_snapshot: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: str = ""
    finished_at: str | None = None


class RunTraceChapterView(BaseModel):
    """读取 API 返回的单章 trace 视图。"""

    run_id: int
    chapter_number: int
    status: str
    planner_output: PlannerOutput = Field(default_factory=PlannerOutput)
    retrieval_pack: dict[str, Any] = Field(default_factory=dict)
    draft_text: str = ""
    final_content: str = ""
    changeset: ChangeSet = Field(default_factory=ChangeSet)
    verifier_issues: list[VerifierIssue] = Field(default_factory=list)
    editor_rewrites: list[dict[str, Any]] = Field(default_factory=list)
    merge_result: dict[str, Any] = Field(default_factory=dict)
    summary_result: dict[str, Any] = Field(default_factory=dict)
    metrics: ChapterMetrics = Field(default_factory=ChapterMetrics)
    error_message: str | None = None
    created_at: str = ""
    updated_at: str = ""


class ChapterGenerationResult(BaseModel):
    """单章生成的结构化结果。"""

    chapter_number: int
    status: str = "running"
    planner_output: PlannerOutput = Field(default_factory=PlannerOutput)
    retrieval_pack: dict[str, Any] = Field(default_factory=dict)
    draft_text: str = ""
    final_content: str = ""
    changeset: ChangeSet = Field(default_factory=ChangeSet)
    verifier_issues: list[VerifierIssue] = Field(default_factory=list)
    editor_rewrites: list[dict[str, Any]] = Field(default_factory=list)
    merge_result: dict[str, Any] = Field(default_factory=dict)
    summary_result: dict[str, Any] = Field(default_factory=dict)
    metrics: ChapterMetrics = Field(default_factory=ChapterMetrics)
    error_message: str | None = None

    def to_trace_view(self, run_id: int, created_at: str = "", updated_at: str = "") -> RunTraceChapterView:
        """将运行时结果映射为 API 直接返回的 trace 视图。"""
        return RunTraceChapterView(
            run_id=run_id,
            chapter_number=self.chapter_number,
            status=self.status,
            planner_output=self.planner_output,
            retrieval_pack=self.retrieval_pack,
            draft_text=self.draft_text,
            final_content=self.final_content,
            changeset=self.changeset,
            verifier_issues=self.verifier_issues,
            editor_rewrites=self.editor_rewrites,
            merge_result=self.merge_result,
            summary_result=self.summary_result,
            metrics=self.metrics,
            error_message=self.error_message,
            created_at=created_at,
            updated_at=updated_at,
        )


class ChapterGenerationError(RuntimeError):
    """生成失败但已经产生部分 trace 时抛出的异常。"""

    def __init__(self, result: ChapterGenerationResult, message: str) -> None:
        super().__init__(message)
        self.result = result


def normalize_planner_output(raw_plan: dict[str, Any]) -> PlannerOutput:
    """把旧 planner 的松散 dict 归一化为稳定协议。"""
    scene_items = raw_plan.get("scene_stubs") or []
    scene_stubs = [
        item if isinstance(item, SceneStub) else SceneStub.model_validate(item)
        for item in scene_items
        if isinstance(item, (dict, SceneStub))
    ]

    return PlannerOutput(
        title=str(raw_plan.get("title") or ""),
        chapter_goal=str(raw_plan.get("chapter_goal") or raw_plan.get("summary") or ""),
        scene_stubs=scene_stubs,
        must_preserve=[str(item) for item in raw_plan.get("must_preserve", raw_plan.get("key_events", []))],
        must_progress_loops=[
            str(item) for item in raw_plan.get("must_progress_loops", raw_plan.get("foreshadowing_hints", []))
        ],
        notes=[str(item) for item in raw_plan.get("notes", [])],
        summary=str(raw_plan.get("summary") or ""),
        key_events=[str(item) for item in raw_plan.get("key_events", [])],
        character_arcs=dict(raw_plan.get("character_arcs") or {}),
        new_facts_budget=int(raw_plan.get("new_facts_budget") or 0),
        foreshadowing_hints=[str(item) for item in raw_plan.get("foreshadowing_hints", [])],
        tone=str(raw_plan.get("tone") or ""),
        opening_hook=str(raw_plan.get("opening_hook") or ""),
        raw_payload=dict(raw_plan),
    )


def normalize_changeset(raw_changes: list[dict[str, Any]]) -> ChangeSet:
    """把旧 extractor 返回的 staging changes 按类别归并。"""
    characters: list[dict[str, Any]] = []
    world_rules: list[dict[str, Any]] = []
    timeline_events: list[dict[str, Any]] = []
    foreshadowing_updates: list[dict[str, Any]] = []

    for change in raw_changes:
        entity_type = str(change.get("entity_type") or "")
        # 这里先按当前系统已有的四类世界对象分桶，后续扩展时只需加分类。
        if entity_type == "character":
            characters.append(change)
        elif entity_type == "world_rule":
            world_rules.append(change)
        elif entity_type == "timeline_event":
            timeline_events.append(change)
        elif entity_type == "foreshadowing":
            foreshadowing_updates.append(change)

    return ChangeSet(
        characters=characters,
        world_rules=world_rules,
        timeline_events=timeline_events,
        foreshadowing_updates=foreshadowing_updates,
        raw_staging_changes=raw_changes,
    )


def normalize_verifier_issues(result: Any) -> list[VerifierIssue]:
    """把旧 verifier 的字符串结果转换成统一 issue 结构。"""
    if getattr(result, "issues", None):
        return [
            issue if isinstance(issue, VerifierIssue) else VerifierIssue.model_validate(issue)
            for issue in result.issues
        ]
    issues: list[VerifierIssue] = []
    for violation in result.violations:
        issues.append(
            VerifierIssue(
                severity="fatal",
                type="consistency",
                reason=str(violation),
                repair_hint="修复与世界规则、时间线或章节规划相冲突的内容。",
            )
        )
    for warning in result.warnings:
        issues.append(
            VerifierIssue(
                severity="warning",
                type="consistency",
                reason=str(warning),
                repair_hint="检查该风险是否需要在下一轮重写中处理。",
            )
        )
    return issues
