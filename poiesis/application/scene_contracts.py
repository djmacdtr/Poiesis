"""Scene 驱动架构下的正式协议。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SceneStatus = Literal["pending", "running", "completed", "needs_review", "failed", "approved"]
ReviewAction = Literal["approve", "retry", "rewrite", "patch", "reject"]
LoopStatus = Literal["open", "hinted", "escalated", "resolved", "dropped", "overdue"]


class StoryPlan(BaseModel):
    """整本书级的当前推进意图。"""

    book_id: int
    focus: str = ""
    active_themes: list[str] = Field(default_factory=list)
    active_loops: list[str] = Field(default_factory=list)
    narrative_pressure: str = ""


class ChapterPlan(BaseModel):
    """章节级规划结果，chapter 是 scene 的聚合容器。"""

    chapter_number: int
    title: str = ""
    goal: str = ""
    hook: str = ""
    must_preserve: list[str] = Field(default_factory=list)
    must_progress_loops: list[str] = Field(default_factory=list)
    scene_count_target: int = 3
    notes: list[str] = Field(default_factory=list)
    source_plan: dict[str, Any] = Field(default_factory=dict)


class ScenePlan(BaseModel):
    """单个 scene 的正式计划。"""

    chapter_number: int
    scene_number: int
    title: str = ""
    goal: str = ""
    conflict: str = ""
    turning_point: str = ""
    location: str = ""
    pov_character: str = ""
    required_loops: list[str] = Field(default_factory=list)
    continuity_requirements: list[str] = Field(default_factory=list)


class SceneDraft(BaseModel):
    """单个 scene 的正文与上下文快照。"""

    chapter_number: int
    scene_number: int
    title: str = ""
    content: str = ""
    retrieval_context: dict[str, Any] = Field(default_factory=dict)


class VerifierIssue(BaseModel):
    """scene 级审校问题。"""

    severity: Literal["fatal", "warning", "info"] = "fatal"
    type: str
    reason: str
    repair_hint: str = ""
    location: str = ""


class ChangeSet(BaseModel):
    """scene 抽取出的状态变化。"""

    characters: list[dict[str, Any]] = Field(default_factory=list)
    world_rules: list[dict[str, Any]] = Field(default_factory=list)
    timeline_events: list[dict[str, Any]] = Field(default_factory=list)
    loop_updates: list[dict[str, Any]] = Field(default_factory=list)
    uncertain_claims: list[dict[str, Any]] = Field(default_factory=list)
    raw_changes: list[dict[str, Any]] = Field(default_factory=list)


class SceneTrace(BaseModel):
    """单个 scene 的结构化 trace。"""

    run_id: int
    chapter_number: int
    scene_number: int
    status: SceneStatus = "pending"
    scene_plan: ScenePlan
    draft: SceneDraft | None = None
    final_text: str = ""
    changeset: ChangeSet = Field(default_factory=ChangeSet)
    verifier_issues: list[VerifierIssue] = Field(default_factory=list)
    review_required: bool = False
    review_reason: str = ""
    review_status: str = "auto_approved"
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class ChapterTrace(BaseModel):
    """章节级 trace，聚合 scene 结果。"""

    run_id: int
    chapter_number: int
    status: str = "running"
    story_plan: StoryPlan
    chapter_plan: ChapterPlan
    scenes: list[SceneTrace] = Field(default_factory=list)
    assembled_text: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    review_required: bool = False
    error_message: str | None = None


class ChapterOutput(BaseModel):
    """最终发布态章节。"""

    run_id: int
    chapter_number: int
    title: str
    content: str
    summary: dict[str, Any] = Field(default_factory=dict)
    scene_count: int = 0
    status: str = "draft"


class LoopState(BaseModel):
    """正式 loop 状态。"""

    loop_id: str
    title: str
    status: LoopStatus = "open"
    introduced_in_scene: str = ""
    due_window: str = ""
    priority: int = 1
    related_characters: list[str] = Field(default_factory=list)
    resolution_requirements: list[str] = Field(default_factory=list)
    last_updated_scene: str = ""


class ReviewQueueItem(BaseModel):
    """审阅队列项。"""

    id: int
    run_id: int
    chapter_number: int
    scene_number: int
    action: str = "pending"
    status: str = "pending"
    reason: str = ""
    patch_text: str = ""
    created_at: str = ""
    updated_at: str = ""


class RunSummary(BaseModel):
    """run 列表项。"""

    id: int
    task_id: str
    book_id: int
    status: str
    current_chapter: int = 0
    total_chapters: int = 0
    created_at: str = ""
    updated_at: str = ""
    error_message: str | None = None
