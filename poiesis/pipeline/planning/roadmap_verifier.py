"""章节路线静态校验器：在蓝图阶段尽早识别连续性断裂、重复和停滞问题。"""

from __future__ import annotations

from difflib import SequenceMatcher

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    PlannedLoopItem,
    RelationshipBlueprintEdge,
    RoadmapValidationIssue,
    StoryArcPlan,
    WorldBlueprint,
)


class RoadmapVerifier:
    """对章节路线做不依赖正文的静态校验。"""

    _SIMILARITY_THRESHOLD = 0.84
    _RELATION_RUPTURE_KEYWORDS = ("决裂", "反目", "背叛", "断裂", "敌对", "仇视", "杀意")
    _WORLD_NEGATION_KEYWORDS = ("打破", "违背", "无视", "绕过", "废除", "解除", "失效")
    _TASK_STATUS_LABELS = {
        "new": "新建",
        "in_progress": "推进中",
        "resolved": "已解决",
        "failed": "失败",
    }

    def verify(
        self,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
        *,
        world: WorldBlueprint | None = None,
        relationship_graph: list[RelationshipBlueprintEdge] | None = None,
    ) -> list[RoadmapValidationIssue]:
        """检查重复章节、结构化字段缺失和连续性冲突。"""
        issues: list[RoadmapValidationIssue] = []
        ordered = sorted(roadmap, key=lambda item: item.chapter_number)
        stage_to_arc = {arc.title: arc.arc_number for arc in story_arcs}
        previous: ChapterRoadmapItem | None = None
        repeated_function_count = 0
        empty_loop_progress_count = 0
        empty_relationship_progress_count = 0
        known_tasks: dict[str, tuple[str, int | None]] = {}
        latest_tasks: dict[str, tuple[str, int, str, str]] = {}
        latest_loops: dict[str, tuple[int, PlannedLoopItem]] = {}

        for item in ordered:
            arc_number = stage_to_arc.get(item.story_stage)
            issues.extend(self._verify_required_fields(item, arc_number))
            issues.extend(self._verify_dependencies(item, previous, arc_number))
            issues.extend(self._verify_task_flow(item, known_tasks, latest_tasks, arc_number))
            issues.extend(self._verify_loop_flow(item, latest_loops, arc_number))
            issues.extend(self._verify_relationship_conflicts(item, relationship_graph or [], arc_number))
            issues.extend(self._verify_world_conflicts(item, world, arc_number))

            if previous is not None:
                if item.chapter_function and item.chapter_function == previous.chapter_function:
                    repeated_function_count += 1
                else:
                    repeated_function_count = 0
                if repeated_function_count >= 1:
                    issues.append(
                        RoadmapValidationIssue(
                            severity="fatal",
                            type="repeated_chapter_function",
                            message=(
                                f"第 {previous.chapter_number}-{item.chapter_number} 章连续使用“{item.chapter_function}”功能，"
                                "缺少有效升级。"
                            ),
                            chapter_number=item.chapter_number,
                            story_stage=item.story_stage,
                            arc_number=arc_number,
                            suggested_action="regenerate_last_chapter",
                        )
                    )

                if self._is_similar_chapter(previous, item):
                    issues.append(
                        RoadmapValidationIssue(
                            severity="fatal",
                            type="chapter_similarity",
                            message=(
                                f"第 {previous.chapter_number} 章与第 {item.chapter_number} 章在标题/目标/冲突上高度相似，"
                                "疑似重复功能章。"
                            ),
                            chapter_number=item.chapter_number,
                            story_stage=item.story_stage,
                            arc_number=arc_number,
                            suggested_action="regenerate_last_chapter",
                        )
                    )

            if item.planned_loops:
                empty_loop_progress_count = 0
            else:
                empty_loop_progress_count += 1
            if empty_loop_progress_count >= 3:
                issues.append(
                    RoadmapValidationIssue(
                        severity="warning",
                        type="loop_stagnation",
                        message=(
                            f"第 {item.chapter_number - 2}-{item.chapter_number} 章连续缺少计划线索推进，"
                            "主线悬念容易停滞。"
                        ),
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="review_arc",
                    )
                )

            if item.relationship_progress or item.relationship_beats:
                empty_relationship_progress_count = 0
            else:
                empty_relationship_progress_count += 1
            if empty_relationship_progress_count >= 4:
                issues.append(
                    RoadmapValidationIssue(
                        severity="warning",
                        type="relationship_stagnation",
                        message=(
                            f"第 {item.chapter_number - 3}-{item.chapter_number} 章长期没有关系推进，"
                            "人物线可能缺少递进。"
                        ),
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="review_arc",
                    )
                )

            previous = item

        issues.extend(self._verify_story_arcs(story_arcs, ordered))
        issues.extend(self._verify_overdue_tasks(latest_tasks, ordered, stage_to_arc))
        issues.extend(self._verify_overdue_loops(latest_loops, ordered, stage_to_arc))
        return self._dedupe_issues(issues)

    def _verify_required_fields(
        self,
        item: ChapterRoadmapItem,
        arc_number: int | None,
    ) -> list[RoadmapValidationIssue]:
        """结构化单章工作流要求每章至少具备主线推进、关键事件和任务/伏笔变化。"""
        issues: list[RoadmapValidationIssue] = []
        if not item.story_progress.strip():
            issues.append(
                RoadmapValidationIssue(
                    severity="fatal",
                    type="missing_story_progress",
                    message=f"第 {item.chapter_number} 章没有明确主线推进。",
                    chapter_number=item.chapter_number,
                    story_stage=item.story_stage,
                    arc_number=arc_number,
                    suggested_action="edit_chapter",
                )
            )
        if not any(event.strip() for event in item.key_events):
            issues.append(
                RoadmapValidationIssue(
                    severity="fatal",
                    type="missing_key_events",
                    message=f"第 {item.chapter_number} 章缺少结构化关键事件。",
                    chapter_number=item.chapter_number,
                    story_stage=item.story_stage,
                    arc_number=arc_number,
                    suggested_action="edit_chapter",
                )
            )
        if not item.chapter_tasks and not item.planned_loops:
            issues.append(
                RoadmapValidationIssue(
                    severity="fatal",
                    type="missing_task_or_loop_progress",
                    message=f"第 {item.chapter_number} 章既没有任务变化，也没有伏笔推进。",
                    chapter_number=item.chapter_number,
                    story_stage=item.story_stage,
                    arc_number=arc_number,
                    suggested_action="edit_chapter",
                )
            )
        return issues

    def _verify_dependencies(
        self,
        item: ChapterRoadmapItem,
        previous: ChapterRoadmapItem | None,
        arc_number: int | None,
    ) -> list[RoadmapValidationIssue]:
        """单章工作流严格按顺序推进，承接章节不能缺失、越界或倒退。"""
        issues: list[RoadmapValidationIssue] = []
        if any(dep >= item.chapter_number for dep in item.depends_on_chapters):
            issues.append(
                RoadmapValidationIssue(
                    severity="fatal",
                    type="invalid_chapter_dependency",
                    message=f"第 {item.chapter_number} 章引用了未来章节或自身作为承接章节。",
                    chapter_number=item.chapter_number,
                    story_stage=item.story_stage,
                    arc_number=arc_number,
                    suggested_action="edit_chapter",
                )
            )
        if previous is not None:
            if previous.chapter_number not in item.depends_on_chapters:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="missing_previous_dependency",
                        message=f"第 {item.chapter_number} 章没有承接上一章（第 {previous.chapter_number} 章）。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            if item.timeline_anchor.strip() and item.timeline_anchor == previous.timeline_anchor:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="timeline_not_advanced",
                        message=f"第 {item.chapter_number} 章时间锚点没有相对上一章推进。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="regenerate_last_chapter",
                    )
                )
        return issues

    def _verify_task_flow(
        self,
        item: ChapterRoadmapItem,
        known_tasks: dict[str, tuple[str, int | None]],
        latest_tasks: dict[str, tuple[str, int, str, str]],
        arc_number: int | None,
    ) -> list[RoadmapValidationIssue]:
        """任务状态必须单调推进，不能凭空解决未引入的任务。"""
        issues: list[RoadmapValidationIssue] = []
        for task in item.chapter_tasks:
            if not task.task_id or not task.summary:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="invalid_task_payload",
                        message=f"第 {item.chapter_number} 章存在结构不完整的任务项。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
                continue
            previous_status, previous_due_end = known_tasks.get(task.task_id, ("", None))
            if task.status == "new" and task.task_id in known_tasks:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="duplicate_task_creation",
                        message=(
                            f"第 {item.chapter_number} 章重复创建了任务“{self._format_task_display(task.task_id, task.summary)}”。"
                        ),
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            if task.status in {"in_progress", "resolved", "failed"} and task.task_id not in known_tasks:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="task_status_jump",
                        message=(
                            f"第 {item.chapter_number} 章让未出现过的任务“{self._format_task_display(task.task_id, task.summary)}”"
                            f"直接进入“{self._format_task_status(task.status)}”状态。"
                        ),
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            if previous_status in {"resolved", "failed"} and task.status in {"new", "in_progress"}:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="task_reopened_without_reset",
                        message=(
                            f"第 {item.chapter_number} 章让已结束任务“{self._format_task_display(task.task_id, task.summary)}”"
                            "回到未完成状态。"
                        ),
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            effective_due_end = task.due_end_chapter if task.due_end_chapter is not None else previous_due_end
            if effective_due_end is not None and item.chapter_number > effective_due_end and task.status not in {"resolved", "failed"}:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="task_overdue",
                        message=(
                            f"第 {item.chapter_number} 章任务“{self._format_task_display(task.task_id, task.summary)}”"
                            "已超过最迟章号仍未解决。"
                        ),
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="regenerate_last_chapter",
                    )
                )
            known_tasks[task.task_id] = (task.status, effective_due_end)
            latest_tasks[task.task_id] = (task.status, item.chapter_number, item.story_stage, task.summary)
        return issues

    def _verify_loop_flow(
        self,
        item: ChapterRoadmapItem,
        latest_loops: dict[str, tuple[int, PlannedLoopItem]],
        arc_number: int | None,
    ) -> list[RoadmapValidationIssue]:
        """伏笔在路线阶段也要显式维护状态和最迟回收窗口。"""
        issues: list[RoadmapValidationIssue] = []
        for raw_loop in item.planned_loops:
            loop_id = raw_loop.loop_id.strip()
            if not loop_id:
                continue
            latest_loops[loop_id] = (item.chapter_number, raw_loop)
            display_name = self._format_loop_display(raw_loop, fallback_loop_id=loop_id)
            if not raw_loop.title.strip():
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="loop_missing_title",
                        message=f"第 {item.chapter_number} 章的伏笔“{display_name}”缺少标题。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            if not raw_loop.summary.strip():
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="loop_missing_summary",
                        message=f"第 {item.chapter_number} 章的伏笔“{display_name}”缺少摘要说明。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            due_start = raw_loop.due_start_chapter
            due_end = raw_loop.due_end_chapter
            status = raw_loop.status
            if due_end is None:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="loop_missing_due_end",
                        message=f"第 {item.chapter_number} 章的伏笔“{display_name}”缺少最迟兑现章。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
                continue
            if due_end < item.chapter_number:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="loop_due_end_before_intro",
                        message=f"第 {item.chapter_number} 章的伏笔“{display_name}”最迟兑现章早于引入章。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            if due_start is not None and due_start > due_end:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="loop_due_window_invalid",
                        message=f"第 {item.chapter_number} 章的伏笔“{display_name}”开始章晚于最迟兑现章。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            if status == "resolved" and not raw_loop.resolution_requirements and not raw_loop.summary.strip():
                issues.append(
                    RoadmapValidationIssue(
                        severity="warning",
                        type="loop_resolved_without_context",
                        message=f"第 {item.chapter_number} 章将伏笔“{display_name}”标为已解决，但缺少回收说明。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
            if item.chapter_number > due_end and status != "resolved":
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="loop_overdue",
                        message=f"第 {item.chapter_number} 章的伏笔“{display_name}”已超过回收窗口仍未解决。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="regenerate_last_chapter",
                    )
                )
        return issues

    def _verify_relationship_conflicts(
        self,
        item: ChapterRoadmapItem,
        relationship_graph: list[RelationshipBlueprintEdge],
        arc_number: int | None,
    ) -> list[RoadmapValidationIssue]:
        """只做保守型关系冲突拦截：不可直接翻转“必须揭示后才能破坏”的关系。"""
        issues: list[RoadmapValidationIssue] = []
        if not relationship_graph or not item.relationship_beats:
            return issues
        for beat in item.relationship_beats:
            edge = self._find_matching_edge(beat.source_character, beat.target_character, relationship_graph)
            if edge is None or not edge.non_breakable_without_reveal:
                continue
            if any(keyword in beat.summary for keyword in self._RELATION_RUPTURE_KEYWORDS) and not item.new_reveals:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="relationship_break_without_reveal",
                        message=(
                            f"第 {item.chapter_number} 章尝试直接破坏关系“{edge.relation_type}”，"
                            "但该关系要求先发生揭示。"
                        ),
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
        return issues

    def _verify_world_conflicts(
        self,
        item: ChapterRoadmapItem,
        world: WorldBlueprint | None,
        arc_number: int | None,
    ) -> list[RoadmapValidationIssue]:
        """对世界更新做保守型冲突校验，避免直接否定已确认的不可变规则。"""
        issues: list[RoadmapValidationIssue] = []
        if world is None or not item.world_updates:
            return issues
        immutable_keys = [
            *(rule.key for rule in world.immutable_rules if rule.key),
            *(rule.description for rule in world.immutable_rules if rule.description),
            *(rule.key for rule in world.taboo_rules if rule.key),
            *(rule.description for rule in world.taboo_rules if rule.description),
        ]
        for update in item.world_updates:
            if not update.strip():
                continue
            if any(keyword in update for keyword in self._WORLD_NEGATION_KEYWORDS) and any(
                key and key in update for key in immutable_keys
            ):
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="world_rule_conflict",
                        message=f"第 {item.chapter_number} 章的世界更新直接冲撞了已确认的不可变设定。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=arc_number,
                        suggested_action="edit_chapter",
                    )
                )
        return issues

    def _verify_story_arcs(
        self,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
    ) -> list[RoadmapValidationIssue]:
        """检查每个阶段是否具备起承转合和明显升级。"""
        issues: list[RoadmapValidationIssue] = []
        for arc in story_arcs:
            arc_chapters = [
                item for item in roadmap if arc.start_chapter <= item.chapter_number <= arc.end_chapter
            ]
            if not arc_chapters:
                continue
            functions = {item.chapter_function for item in arc_chapters if item.chapter_function}
            if len(arc_chapters) >= 2 and len(functions) < 2:
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="arc_function_monotony",
                        message=f"阶段“{arc.title}”内部章节功能过于单一，缺少递进。",
                        chapter_number=arc.end_chapter,
                        story_stage=arc.title,
                        arc_number=arc.arc_number,
                        suggested_action="review_arc",
                    )
                )
            if len(arc_chapters) >= 3 and not any(
                item.chapter_function in {"反转", "揭示", "收束", "决战前夜"}
                for item in arc_chapters
            ):
                issues.append(
                    RoadmapValidationIssue(
                        severity="warning",
                        type="arc_missing_climax",
                        message=f"阶段“{arc.title}”缺少明确转折或收束节点。",
                        chapter_number=arc.end_chapter,
                        story_stage=arc.title,
                        arc_number=arc.arc_number,
                        suggested_action="review_arc",
                    )
                )
            if len(arc_chapters) >= 3 and len(
                {item.story_progress for item in arc_chapters if item.story_progress}
            ) < max(2, len(arc_chapters) // 3):
                issues.append(
                    RoadmapValidationIssue(
                        severity="warning",
                        type="arc_story_progress_stagnation",
                        message=f"阶段“{arc.title}”的主线推进变化不足，容易出现重复章节。",
                        chapter_number=arc.end_chapter,
                        story_stage=arc.title,
                        arc_number=arc.arc_number,
                        suggested_action="review_arc",
                    )
                )
        return issues

    def _verify_overdue_tasks(
        self,
        latest_tasks: dict[str, tuple[str, int, str, str]],
        roadmap: list[ChapterRoadmapItem],
        stage_to_arc: dict[str, int],
    ) -> list[RoadmapValidationIssue]:
        """在整条路线层面补抓已经拖过期却仍未结束的任务。"""
        if not roadmap:
            return []
        last_chapter = roadmap[-1].chapter_number
        issues: list[RoadmapValidationIssue] = []
        for task_id, (status, chapter_number, story_stage, summary) in latest_tasks.items():
            if status not in {"new", "in_progress"}:
                continue
            chapter = next((item for item in roadmap if item.chapter_number == chapter_number), None)
            if chapter is None:
                continue
            task = next((item for item in chapter.chapter_tasks if item.task_id == task_id), None)
            if task is None or task.due_end_chapter is None or task.due_end_chapter >= last_chapter:
                continue
            issues.append(
                RoadmapValidationIssue(
                    severity="fatal",
                    type="task_still_overdue",
                    message=(
                        f"任务“{self._format_task_display(task_id, summary)}”已经超过最迟章号仍未解决。"
                    ),
                    chapter_number=chapter_number,
                    story_stage=story_stage,
                    arc_number=stage_to_arc.get(story_stage),
                    suggested_action="review_arc",
                )
            )
        return issues

    def _format_task_display(self, task_id: str, summary: str) -> str:
        """优先向作者展示任务摘要，只有摘要缺失时才回退到内部 task_id。"""
        normalized_summary = summary.strip()
        if normalized_summary:
            return normalized_summary
        return task_id.strip() or "未命名任务"

    def _format_task_status(self, status: str) -> str:
        """把内部任务状态码转换为作者界面可读的中文状态。"""
        return self._TASK_STATUS_LABELS.get(status, status)

    def _format_loop_display(self, loop: PlannedLoopItem, *, fallback_loop_id: str) -> str:
        """优先展示伏笔标题或摘要，只有都缺失时才回退到内部 loop_id。"""
        if loop.title.strip():
            return loop.title.strip()
        if loop.summary.strip():
            return loop.summary.strip()
        return fallback_loop_id.strip() or "未命名伏笔"

    def _verify_overdue_loops(
        self,
        latest_loops: dict[str, tuple[int, PlannedLoopItem]],
        roadmap: list[ChapterRoadmapItem],
        stage_to_arc: dict[str, int],
    ) -> list[RoadmapValidationIssue]:
        """在整条路线层面补抓已过最迟回收窗口的伏笔。"""
        if not roadmap:
            return []
        last_chapter = roadmap[-1].chapter_number
        issues: list[RoadmapValidationIssue] = []
        for loop_id, (chapter_number, loop) in latest_loops.items():
            due_end = loop.due_end_chapter
            status = loop.status
            if due_end is None or due_end >= last_chapter or status == "resolved":
                continue
            chapter = next((item for item in roadmap if item.chapter_number == chapter_number), None)
            if chapter is None:
                continue
            issues.append(
                RoadmapValidationIssue(
                    severity="fatal",
                    type="loop_still_overdue",
                    message=f"伏笔“{self._format_loop_display(loop, fallback_loop_id=loop_id)}”已经过了最迟回收窗口但仍未解决。",
                    chapter_number=chapter_number,
                    story_stage=chapter.story_stage,
                    arc_number=stage_to_arc.get(chapter.story_stage),
                    suggested_action="review_arc",
                )
            )
        return issues

    def _find_matching_edge(
        self,
        source_character: str,
        target_character: str,
        relationship_graph: list[RelationshipBlueprintEdge],
    ) -> RelationshipBlueprintEdge | None:
        """关系推进允许正反向匹配同一条边，避免前端输入方向不一致导致误报。"""
        source = source_character.strip()
        target = target_character.strip()
        for edge in relationship_graph:
            pair = {
                edge.source_character_id.replace("_", " "),
                edge.target_character_id.replace("_", " "),
            }
            if {source, target} == pair:
                return edge
        return None

    def _is_similar_chapter(self, left: ChapterRoadmapItem, right: ChapterRoadmapItem) -> bool:
        """用标题/目标/冲突的综合相似度识别相邻重复章节。"""
        title_ratio = self._ratio(left.title, right.title)
        goal_ratio = self._ratio(left.goal, right.goal)
        conflict_ratio = self._ratio(left.core_conflict, right.core_conflict)
        signature_equal = (
            left.anti_repeat_signature
            and right.anti_repeat_signature
            and left.anti_repeat_signature == right.anti_repeat_signature
        )
        return signature_equal or (
            title_ratio >= self._SIMILARITY_THRESHOLD
            and goal_ratio >= self._SIMILARITY_THRESHOLD
            and conflict_ratio >= self._SIMILARITY_THRESHOLD
        )

    def _ratio(self, left: str, right: str) -> float:
        """计算两个文本片段的粗粒度相似度。"""
        if not left or not right:
            return 0.0
        return SequenceMatcher(None, left, right).ratio()

    def _dedupe_issues(self, issues: list[RoadmapValidationIssue]) -> list[RoadmapValidationIssue]:
        """避免同一个问题在同一章节被重复展示。"""
        seen: set[tuple[str, int | None, str]] = set()
        unique: list[RoadmapValidationIssue] = []
        for item in issues:
            key = (item.type, item.chapter_number, item.story_stage)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique
