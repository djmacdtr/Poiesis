"""章节路线静态校验器：在蓝图阶段尽早识别重复和停滞问题。"""

from __future__ import annotations

from difflib import SequenceMatcher

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    RoadmapValidationIssue,
    StoryArcPlan,
)


class RoadmapVerifier:
    """对章节路线做不依赖正文的静态校验。"""

    _SIMILARITY_THRESHOLD = 0.84

    def verify(
        self,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
    ) -> list[RoadmapValidationIssue]:
        """检查重复章节、主线停滞和阶段缺少升级/转折。"""
        issues: list[RoadmapValidationIssue] = []
        stage_to_arc = {arc.title: arc.arc_number for arc in story_arcs}
        previous: ChapterRoadmapItem | None = None
        repeated_function_count = 0
        stagnant_timeline_count = 0
        empty_loop_progress_count = 0
        empty_relationship_progress_count = 0

        for item in roadmap:
            if not item.story_progress.strip():
                issues.append(
                    RoadmapValidationIssue(
                        severity="fatal",
                        type="missing_story_progress",
                        message=f"第 {item.chapter_number} 章没有明确主线推进。",
                        chapter_number=item.chapter_number,
                        story_stage=item.story_stage,
                        arc_number=stage_to_arc.get(item.story_stage),
                        suggested_action="edit_chapter",
                    )
                )

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
                            arc_number=stage_to_arc.get(item.story_stage),
                            suggested_action="regenerate_stage",
                        )
                    )

                if item.timeline_anchor and item.timeline_anchor == previous.timeline_anchor:
                    stagnant_timeline_count += 1
                else:
                    stagnant_timeline_count = 0
                if stagnant_timeline_count >= 2:
                    issues.append(
                        RoadmapValidationIssue(
                            severity="warning",
                            type="timeline_stagnation",
                            message=(
                                f"第 {item.chapter_number - 2}-{item.chapter_number} 章时间锚点长期停留在“{item.timeline_anchor}”，"
                                "建议加入明确时间推进。"
                            ),
                            chapter_number=item.chapter_number,
                            story_stage=item.story_stage,
                            arc_number=stage_to_arc.get(item.story_stage),
                            suggested_action="review_stage",
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
                            arc_number=stage_to_arc.get(item.story_stage),
                            suggested_action="regenerate_stage",
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
                        arc_number=stage_to_arc.get(item.story_stage),
                        suggested_action="review_stage",
                    )
                )

            if item.relationship_progress:
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
                        arc_number=stage_to_arc.get(item.story_stage),
                        suggested_action="review_stage",
                    )
                )

            previous = item

        issues.extend(self._verify_story_arcs(story_arcs, roadmap))
        return self._dedupe_issues(issues)

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
                        suggested_action="regenerate_stage",
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
                        suggested_action="review_stage",
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
                        suggested_action="regenerate_stage",
                    )
                )
        return issues

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
