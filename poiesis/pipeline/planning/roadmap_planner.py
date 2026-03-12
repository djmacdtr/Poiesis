"""创作蓝图生成器：根据作者意图逐层扩写整书蓝图。"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Literal

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    ConceptVariantFrame,
    CreationIntent,
    FactionBlueprint,
    ImmutableRuleBlueprint,
    LocationBlueprint,
    PowerSystemBlueprint,
    RelationshipBlueprintEdge,
    RoadmapValidationIssue,
    StoryArcPlan,
    TabooRuleBlueprint,
    VariantRegenerationAttempt,
    VariantSimilarityIssue,
    WorldBlueprint,
)
from poiesis.llm.base import LLMClient
from poiesis.pipeline.planning.roadmap_verifier import RoadmapVerifier

logger = logging.getLogger(__name__)


class RoadmapPlanner:
    """负责候选方向、世界观、人物和章节路线的生成与重规划。"""

    _MAX_SINGLE_VARIANT_RETRIES = 3
    _ROADMAP_MAX_RETRIES = 2
    _TEXT_SIMILARITY_THRESHOLD = 0.70
    _HOOK_SIMILARITY_THRESHOLD = 0.82
    _SECTION_SIMILARITY_THRESHOLD = 0.88
    _STRUCTURE_OVERLAP_THRESHOLD = 3
    _KEYWORD_OVERLAP_THRESHOLD = 4

    def __init__(self) -> None:
        """初始化路线规划器，并挂载静态路线校验器。"""
        self._roadmap_verifier = RoadmapVerifier()
        # 当模型直接返回章节列表而非阶段弧线时，先暂存本轮章节，避免重复再调一次 LLM。
        self._prefetched_roadmap: list[ChapterRoadmapItem] | None = None

    def generate_concept_variants(self, intent: CreationIntent, llm: LLMClient) -> list[ConceptVariant]:
        """根据作者高层意图生成 3 版带结构分歧的候选方向。"""
        frames = self._generate_variant_frames(intent, llm)
        variants = [self._expand_variant_frame(intent, frame, llm) for frame in frames]
        return self._enforce_variant_diversity(intent, frames, variants, llm)

    def regenerate_concept_variant(
        self,
        intent: CreationIntent,
        current_variant: ConceptVariant,
        sibling_variants: list[ConceptVariant],
        llm: LLMClient,
    ) -> tuple[ConceptVariant, VariantSimilarityIssue | None, list[VariantRegenerationAttempt], bool]:
        """只重生成单条候选方向，避开已有版本的主要结构。"""
        frame = ConceptVariantFrame(
            variant_no=current_variant.variant_no,
            variant_strategy=current_variant.variant_strategy or "重生成版本",
            core_driver=current_variant.core_driver,
            conflict_source=current_variant.conflict_source,
            world_structure=current_variant.world_structure,
            protagonist_arc_mode=current_variant.protagonist_arc_mode,
            tone_signature=current_variant.tone_signature,
            ending_mode=current_variant.ending_pitch,
            differentiators=current_variant.differentiators,
        )
        attempts: list[VariantRegenerationAttempt] = []
        divergence_guidance: list[str] = []
        regenerated = current_variant.model_copy(deep=True)
        latest_issue: VariantSimilarityIssue | None = None

        for attempt_no in range(1, self._MAX_SINGLE_VARIANT_RETRIES + 1):
            regenerated = self._expand_variant_frame(
                intent,
                frame,
                llm,
                siblings=sibling_variants,
                force_diverge=True,
                divergence_guidance=divergence_guidance,
            )
            latest_issue = self._analyze_similarity_against_siblings(intent, regenerated, sibling_variants)
            if latest_issue is None:
                regenerated.diversity_note = ""
                attempts.append(
                    VariantRegenerationAttempt(
                        attempt_no=attempt_no,
                        status="applied",
                        warnings=["本轮结果已达到差异阈值，允许自动覆盖原候选。"],
                    )
                )
                return regenerated, None, attempts, True

            divergence_guidance = latest_issue.guidance
            warnings = [
                f"当前版本仍过于接近方向 {latest_issue.compared_variant_no}，需要继续拉开差异。"
            ]
            status: Literal["retrying", "needs_confirmation"] = (
                "retrying" if attempt_no < self._MAX_SINGLE_VARIANT_RETRIES else "needs_confirmation"
            )
            attempts.append(
                VariantRegenerationAttempt(
                    attempt_no=attempt_no,
                    status=status,
                    warnings=warnings,
                    similarity_issue=latest_issue,
                )
            )

        regenerated.diversity_note = "此版本与其他候选仍存在明显相似度，需人工确认是否替换。"
        return regenerated, latest_issue, attempts, False

    def generate_world(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        llm: LLMClient,
        feedback: str = "",
    ) -> WorldBlueprint:
        """围绕已选候选方向扩写世界观蓝图。"""
        skeleton = llm.complete_json(
            self._build_world_skeleton_prompt(intent, variant, feedback),
            system="你是资深世界观架构师。必须返回合法 JSON，并优先输出结构化世界蓝图。",
        )
        if not isinstance(skeleton, dict):
            skeleton = {}
        rules = llm.complete_json(
            self._build_world_rules_prompt(intent, variant, skeleton, feedback),
            system="你是资深世界规则设计师。必须返回合法 JSON，并把规则写成可持续约束正文的结构。",
        )
        if not isinstance(rules, dict):
            rules = {}
        try:
            return self._normalize_world_blueprint(intent, variant, skeleton, rules)
        except ValueError as exc:
            logger.exception(
                "世界观蓝图归一化失败",
                extra={
                    "variant_no": variant.variant_no,
                    "skeleton_preview": skeleton,
                    "rules_preview": rules,
                },
            )
            raise ValueError(self._build_world_generation_error_message(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "世界观蓝图生成出现未预期错误",
                extra={
                    "variant_no": variant.variant_no,
                    "skeleton_preview": skeleton,
                    "rules_preview": rules,
                },
            )
            raise ValueError("世界观草稿生成失败：世界结构输出不符合要求，请重试。") from exc

    def generate_characters(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        llm: LLMClient,
        feedback: str = "",
    ) -> list[CharacterBlueprint]:
        """基于世界观生成核心人物组。"""
        raw = llm.complete_json(
            self._build_character_prompt(intent, variant, world, feedback),
            system="你是资深人物策划。必须返回合法 JSON，且人物必须适配长篇连载推进。",
        )
        try:
            characters = self.normalize_character_blueprints_payload(raw)
            if characters:
                return characters
        except ValueError as exc:
            logger.exception(
                "人物蓝图归一化失败",
                extra={
                    "variant_no": variant.variant_no,
                    "characters_preview": raw,
                },
            )
            raise ValueError(self._build_character_generation_error_message(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "人物蓝图生成出现未预期错误",
                extra={
                    "variant_no": variant.variant_no,
                    "characters_preview": raw,
                },
            )
            raise ValueError("人物蓝图生成失败：角色结构输出不符合要求，请重试。") from exc

        return [
            CharacterBlueprint(
                name="主角",
                role="主角",
                public_persona="表面冷静，实则长期压抑自身欲望。",
                core_motivation=intent.protagonist_prompt or "摆脱既定命运",
                fatal_flaw="不愿真正向他人求助",
                non_negotiable_traits=["遇到大义问题时不会退缩"],
                relationship_constraints=["与关键对象存在长期情感拉扯"],
                arc_outline=["前期被动卷入", "中期主动承担", "后期以代价完成选择"],
            )
        ]

    def generate_relationship_graph(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        llm: LLMClient,
        feedback: str = "",
    ) -> list[RelationshipBlueprintEdge]:
        """基于人物蓝图和世界观生成正式关系边。"""
        raw = llm.complete_json(
            self._build_relationship_prompt(intent, variant, world, characters, feedback),
            system="你是资深人物关系编剧。必须返回合法 JSON，并显式输出人物关系边。",
        )
        try:
            edges = self._normalize_relationship_edges(raw, characters)
        except ValueError as exc:
            logger.exception(
                "人物关系图谱归一化失败",
                extra={
                    "variant_no": variant.variant_no,
                    "relationships_preview": raw,
                },
            )
            raise ValueError(self._build_relationship_generation_error_message(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "人物关系图谱生成出现未预期错误",
                extra={
                    "variant_no": variant.variant_no,
                    "relationships_preview": raw,
                },
            )
            raise ValueError("人物蓝图生成失败：人物关系结构输出不符合要求，请重试。") from exc
        if edges:
            return edges
        if len(characters) >= 2:
            return [
                RelationshipBlueprintEdge(
                    edge_id="rel-1",
                    source_character_id=self._character_id(characters[0]),
                    target_character_id=self._character_id(characters[1]),
                    relation_type="关键牵制",
                    polarity="复杂",
                    intensity=3,
                    visibility="半公开",
                    stability="脆弱",
                    summary="主角与关键对象之间存在长期牵制关系。",
                )
            ]
        return []

    def generate_roadmap(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        llm: LLMClient,
        feedback: str = "",
        starting_chapter: int = 1,
        chapter_count: int = 12,
        existing_roadmap: list[ChapterRoadmapItem] | None = None,
    ) -> list[ChapterRoadmapItem]:
        """生成或重规划章节路线，并在内部做静态重复校验。"""
        _story_arcs, roadmap, _issues = self.generate_structured_roadmap(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=llm,
            feedback=feedback,
            starting_chapter=starting_chapter,
            chapter_count=chapter_count,
            existing_roadmap=existing_roadmap or [],
        )
        return roadmap

    def regenerate_story_arc(
        self,
        *,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        llm: LLMClient,
        story_arc: StoryArcPlan,
        feedback: str = "",
        existing_roadmap: list[ChapterRoadmapItem] | None = None,
    ) -> tuple[list[ChapterRoadmapItem], list[RoadmapValidationIssue]]:
        """只重生成单个阶段覆盖的章节，并返回该阶段局部校验结果。"""
        try:
            raw = llm.complete_json(
                self._build_arc_chapter_prompt(
                    intent=intent,
                    variant=variant,
                    world=world,
                    characters=characters,
                    feedback=feedback,
                    story_arc=story_arc,
                    existing_roadmap=existing_roadmap or [],
                ),
                system="你是长篇小说总编剧。你只允许重写当前阶段，并必须修复已指出的问题。",
            )
            chapters = self.normalize_roadmap_payload(
                raw,
                starting_chapter=story_arc.start_chapter,
                chapter_count=story_arc.end_chapter - story_arc.start_chapter + 1,
            )
        except ValueError as exc:
            logger.exception(
                "阶段重生成时章节 JSON 归一化失败",
                extra={
                    "story_arc": story_arc.model_dump(mode="json"),
                },
            )
            raise ValueError(self._build_roadmap_stage_regeneration_error_message(exc)) from exc
        arc_issues = [
            issue
            for issue in self.verify_roadmap([story_arc], chapters)
            if issue.arc_number in {None, story_arc.arc_number} or issue.story_stage == story_arc.title
        ]
        return chapters, arc_issues

    def generate_structured_roadmap(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        llm: LLMClient,
        feedback: str = "",
        starting_chapter: int = 1,
        chapter_count: int = 12,
        existing_roadmap: list[ChapterRoadmapItem] | None = None,
    ) -> tuple[list[StoryArcPlan], list[ChapterRoadmapItem], list[RoadmapValidationIssue]]:
        """按“阶段 -> 章节”的分层方式生成路线，并在必要时自动回炉。"""
        self._prefetched_roadmap = None
        existing = existing_roadmap or []
        story_arcs = self._generate_story_arcs(
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=llm,
            feedback=feedback,
            starting_chapter=starting_chapter,
            chapter_count=chapter_count,
            existing_roadmap=existing,
        )
        roadmap = self._expand_story_arcs_into_chapters(
            story_arcs=story_arcs,
            intent=intent,
            variant=variant,
            world=world,
            characters=characters,
            llm=llm,
            feedback=feedback,
            existing_roadmap=existing,
        )
        issues = self.verify_roadmap(story_arcs, roadmap)
        retry_count = 0
        while retry_count < self._ROADMAP_MAX_RETRIES and any(item.severity == "fatal" for item in issues):
            retry_count += 1
            guidance = "；".join(item.message for item in issues if item.severity == "fatal")
            story_arcs = self._generate_story_arcs(
                intent=intent,
                variant=variant,
                world=world,
                characters=characters,
                llm=llm,
                feedback=f"{feedback}；请重点修复这些路线问题：{guidance}".strip("；"),
                starting_chapter=starting_chapter,
                chapter_count=chapter_count,
                existing_roadmap=existing,
            )
            roadmap = self._expand_story_arcs_into_chapters(
                story_arcs=story_arcs,
                intent=intent,
                variant=variant,
                world=world,
                characters=characters,
                llm=llm,
                feedback=f"{feedback}；请重点修复这些路线问题：{guidance}".strip("；"),
                existing_roadmap=existing,
            )
            issues = self.verify_roadmap(story_arcs, roadmap)
        fatal_issues = [item for item in issues if item.severity == "fatal"]
        if fatal_issues:
            message = "；".join(item.message for item in fatal_issues[:3])
            raise ValueError(f"章节路线生成失败：{message}")
        return story_arcs, roadmap, issues

    def derive_story_arcs_from_roadmap(self, roadmap: list[ChapterRoadmapItem]) -> list[StoryArcPlan]:
        """根据 richer roadmap 反推阶段视图，供 API 和前端统一消费。"""
        if not roadmap:
            return []
        grouped: dict[str, list[ChapterRoadmapItem]] = {}
        for item in roadmap:
            key = item.story_stage or "未分阶段"
            grouped.setdefault(key, []).append(item)
        arcs: list[StoryArcPlan] = []
        for index, (title, chapters) in enumerate(grouped.items(), start=1):
            ordered = sorted(chapters, key=lambda row: row.chapter_number)
            arcs.append(
                StoryArcPlan(
                    arc_number=index,
                    title=title,
                    purpose=ordered[0].goal,
                    start_chapter=ordered[0].chapter_number,
                    end_chapter=ordered[-1].chapter_number,
                    main_progress=list(
                        dict.fromkeys(item.story_progress for item in ordered if item.story_progress)
                    ),
                    relationship_progress=list(
                        dict.fromkeys(
                            progress
                            for item in ordered
                            for progress in item.relationship_progress
                            if progress
                        )
                    ),
                    loop_progress=list(
                        dict.fromkeys(
                            str(loop.get("title") or loop.get("summary") or loop.get("loop_id") or "")
                            for item in ordered
                            for loop in item.planned_loops
                            if isinstance(loop, dict)
                        )
                    ),
                    timeline_milestones=list(
                        dict.fromkeys(item.timeline_anchor for item in ordered if item.timeline_anchor)
                    ),
                    arc_climax=next(
                        (
                            item.turning_point
                            for item in reversed(ordered)
                            if item.chapter_function in {"反转", "揭示", "收束", "决战前夜"} and item.turning_point
                        ),
                        ordered[-1].turning_point,
                    ),
                )
            )
        return arcs

    def verify_roadmap(
        self,
        story_arcs: list[StoryArcPlan],
        roadmap: list[ChapterRoadmapItem],
    ) -> list[RoadmapValidationIssue]:
        """对章节路线执行静态 verifier。"""
        return self._roadmap_verifier.verify(story_arcs, roadmap)

    def _generate_story_arcs(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        llm: LLMClient,
        feedback: str,
        starting_chapter: int,
        chapter_count: int,
        existing_roadmap: list[ChapterRoadmapItem],
    ) -> list[StoryArcPlan]:
        """先生成阶段弧线，再由每个阶段展开成章节。"""
        try:
            raw = llm.complete_json(
                self._build_story_arc_prompt(
                    intent,
                    variant,
                    world,
                    characters,
                    feedback,
                    starting_chapter,
                    chapter_count,
                    existing_roadmap,
                ),
                system="你是长篇小说总编剧。必须先规划阶段弧线，再允许展开为章节。",
            )
            direct_roadmap = self._extract_roadmap_items(raw)
            if direct_roadmap:
                prefetched = self.normalize_roadmap_payload(
                    direct_roadmap,
                    starting_chapter=starting_chapter,
                    chapter_count=chapter_count,
                )
                self._prefetched_roadmap = prefetched
                return self.derive_story_arcs_from_roadmap(prefetched)
            arcs = self._normalize_story_arcs(
                raw,
                starting_chapter=starting_chapter,
                chapter_count=chapter_count,
            )
            if arcs:
                return arcs
        except ValueError as exc:
            logger.exception(
                "阶段弧线归一化失败",
                extra={
                    "variant_no": variant.variant_no,
                    "story_arc_preview": raw,
                },
            )
            raise ValueError(self._build_roadmap_generation_error_message(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "阶段弧线生成出现未预期错误",
                extra={
                    "variant_no": variant.variant_no,
                    "story_arc_preview": raw,
                },
            )
            raise ValueError("章节路线生成失败：阶段结构输出不符合要求，请重试。") from exc

        return self._build_fallback_story_arcs(starting_chapter, chapter_count)

    def _expand_story_arcs_into_chapters(
        self,
        story_arcs: list[StoryArcPlan],
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        llm: LLMClient,
        feedback: str,
        existing_roadmap: list[ChapterRoadmapItem],
    ) -> list[ChapterRoadmapItem]:
        """逐个阶段展开章节，避免 80 章长输出直接失控。"""
        if self._prefetched_roadmap is not None:
            prefetched = self._prefetched_roadmap
            self._prefetched_roadmap = None
            return prefetched
        roadmap: list[ChapterRoadmapItem] = []
        for arc in story_arcs:
            try:
                raw = llm.complete_json(
                    self._build_arc_chapter_prompt(
                        intent=intent,
                        variant=variant,
                        world=world,
                        characters=characters,
                        feedback=feedback,
                        story_arc=arc,
                        existing_roadmap=[*existing_roadmap, *roadmap],
                    ),
                    system="你是长篇小说总编剧。必须让当前阶段章节持续升级并承接上一阶段结果。",
                )
                chapters = self.normalize_roadmap_payload(
                    raw,
                    starting_chapter=arc.start_chapter,
                    chapter_count=arc.end_chapter - arc.start_chapter + 1,
                )
            except ValueError as exc:
                logger.exception(
                    "阶段章节归一化失败",
                    extra={
                        "story_arc": arc.model_dump(mode="json"),
                        "chapter_preview": raw,
                    },
                )
                raise ValueError(self._build_roadmap_generation_error_message(exc)) from exc
            for chapter in chapters:
                chapter.story_stage = arc.title
                if not chapter.timeline_anchor and arc.timeline_milestones:
                    chapter.timeline_anchor = arc.timeline_milestones[min(
                        max(chapter.chapter_number - arc.start_chapter, 0),
                        len(arc.timeline_milestones) - 1,
                    )]
            roadmap.extend(chapters)
        return roadmap

    def _generate_variant_frames(self, intent: CreationIntent, llm: LLMClient) -> list[ConceptVariantFrame]:
        """先生成 3 条差异骨架，锁定候选方向的分歧维度。"""
        strategy_templates = self._resolve_strategy_templates(intent)
        raw = llm.complete_json(
            self._build_variant_frame_prompt(intent, strategy_templates),
            system=(
                "你是资深小说总策划。必须返回合法 JSON。"
                "请严格围绕给定的三条分歧轨道生成 3 个候选骨架，禁止三版只是同一设定改写。"
            ),
        )
        frames = raw.get("frames")
        if not isinstance(frames, list) or len(frames) < 3:
            frames = strategy_templates
        normalized: list[ConceptVariantFrame] = []
        for index, item in enumerate(frames[:3], start=1):
            template = strategy_templates[index - 1]
            normalized.append(
                ConceptVariantFrame.model_validate(
                    {
                        "variant_no": index,
                        "variant_strategy": item.get("variant_strategy") or template["variant_strategy"],
                        "core_driver": item.get("core_driver") or template["core_driver"],
                        "conflict_source": item.get("conflict_source") or template["conflict_source"],
                        "world_structure": item.get("world_structure") or template["world_structure"],
                        "protagonist_arc_mode": item.get("protagonist_arc_mode")
                        or template["protagonist_arc_mode"],
                        "tone_signature": item.get("tone_signature") or template["tone_signature"],
                        "ending_mode": item.get("ending_mode") or template["ending_mode"],
                        "differentiators": item.get("differentiators") or template["differentiators"],
                    }
                )
            )
        return normalized

    def _expand_variant_frame(
        self,
        intent: CreationIntent,
        frame: ConceptVariantFrame,
        llm: LLMClient,
        *,
        siblings: list[ConceptVariant] | None = None,
        force_diverge: bool = False,
        divergence_guidance: list[str] | None = None,
    ) -> ConceptVariant:
        """把单条骨架扩写成完整候选方向。"""
        raw = llm.complete_json(
            self._build_variant_expansion_prompt(
                intent,
                frame,
                siblings or [],
                force_diverge=force_diverge,
                divergence_guidance=divergence_guidance or [],
            ),
            system=(
                "你是资深小说总策划。必须返回合法 JSON。"
                "请围绕既定骨架扩写成完整候选方向，并且保留骨架中的关键分歧标签。"
            ),
        )
        return ConceptVariant.model_validate(
            {
                "variant_no": frame.variant_no,
                "hook": raw.get("hook") or self._fallback_hook(intent, frame),
                "world_pitch": raw.get("world_pitch") or self._fallback_world_pitch(intent, frame),
                "main_arc_pitch": raw.get("main_arc_pitch") or self._fallback_arc_pitch(intent, frame),
                "ending_pitch": raw.get("ending_pitch") or frame.ending_mode or intent.ending_preference,
                "variant_strategy": raw.get("variant_strategy") or frame.variant_strategy,
                "core_driver": raw.get("core_driver") or frame.core_driver,
                "conflict_source": raw.get("conflict_source") or frame.conflict_source,
                "world_structure": raw.get("world_structure") or frame.world_structure,
                "protagonist_arc_mode": raw.get("protagonist_arc_mode") or frame.protagonist_arc_mode,
                "tone_signature": raw.get("tone_signature") or frame.tone_signature,
                "differentiators": raw.get("differentiators") or frame.differentiators,
                "diversity_note": "",
            }
        )

    def _enforce_variant_diversity(
        self,
        intent: CreationIntent,
        frames: list[ConceptVariantFrame],
        variants: list[ConceptVariant],
        llm: LLMClient,
    ) -> list[ConceptVariant]:
        """对候选方向做相似度校验，不够分散时自动回炉。"""
        retry_count = 0
        while retry_count < 2:
            issue = self._find_similarity_issue(variants)
            if issue is None:
                return variants
            retry_count += 1
            target_index = issue["target_index"]
            siblings = [item for idx, item in enumerate(variants) if idx != target_index]
            variants[target_index] = self._expand_variant_frame(
                intent,
                frames[target_index],
                llm,
                siblings=siblings,
                force_diverge=True,
            )

        issue = self._find_similarity_issue(variants)
        if issue is not None:
            variants[issue["target_index"]].diversity_note = "此版本与其他候选较接近，建议重点参考差异标签。"
        return variants

    def _find_similarity_issue(self, variants: list[ConceptVariant]) -> dict[str, int] | None:
        """找出最需要重生成的候选版本。"""
        if len(variants) < 2:
            return None
        worst_index: int | None = None
        worst_score = 0.0
        for left in range(len(variants)):
            for right in range(left + 1, len(variants)):
                text_score = self._variant_text_similarity(variants[left], variants[right])
                structure_overlap = self._variant_structure_overlap(variants[left], variants[right])
                if (
                    text_score >= self._TEXT_SIMILARITY_THRESHOLD
                    or structure_overlap >= self._STRUCTURE_OVERLAP_THRESHOLD
                ):
                    score = text_score + structure_overlap / 10
                    if score > worst_score:
                        worst_score = score
                        worst_index = right
        if worst_index is None:
            return None
        return {"target_index": worst_index}

    def _analyze_similarity_against_siblings(
        self,
        intent: CreationIntent,
        target: ConceptVariant,
        siblings: list[ConceptVariant],
    ) -> VariantSimilarityIssue | None:
        """分析单版候选与其余版本的最强相似点，并给出纠偏建议。"""
        if not siblings:
            return None

        worst_issue: VariantSimilarityIssue | None = None
        worst_score = 0.0
        for sibling in siblings:
            text_similarity = self._variant_text_similarity(target, sibling)
            structure_overlap = self._variant_structure_overlap(target, sibling)
            repeated_fields = self._collect_repeated_fields(target, sibling)
            repeated_sections = self._collect_repeated_sections(target, sibling)
            repeated_keywords = self._collect_repeated_keywords(target, sibling)
            if not self._is_similarity_issue(
                text_similarity,
                structure_overlap,
                repeated_fields,
                repeated_sections,
                repeated_keywords,
            ):
                continue

            issue = VariantSimilarityIssue(
                compared_variant_no=sibling.variant_no,
                text_similarity=round(text_similarity, 3),
                structure_overlap=structure_overlap,
                repeated_keywords=repeated_keywords,
                repeated_sections=repeated_sections,
                repeated_fields=repeated_fields,
                guidance=self._build_divergence_guidance(intent, target, sibling, repeated_fields, repeated_sections),
            )
            score = text_similarity + structure_overlap / 10 + len(repeated_sections) / 20 + len(repeated_keywords) / 30
            if score > worst_score:
                worst_issue = issue
                worst_score = score

        return worst_issue

    def _is_similarity_issue(
        self,
        text_similarity: float,
        structure_overlap: int,
        repeated_fields: list[str],
        repeated_sections: list[str],
        repeated_keywords: list[str],
    ) -> bool:
        """组合文本、结构和高频锚点，识别明显不达标的相似结果。"""
        return any(
            [
                text_similarity >= self._TEXT_SIMILARITY_THRESHOLD,
                structure_overlap >= self._STRUCTURE_OVERLAP_THRESHOLD,
                bool(repeated_sections),
                len(repeated_keywords) >= self._KEYWORD_OVERLAP_THRESHOLD,
                len(repeated_fields) >= self._STRUCTURE_OVERLAP_THRESHOLD,
            ]
        )

    def _variant_text_similarity(self, left: ConceptVariant, right: ConceptVariant) -> float:
        """粗粒度比较两条候选文本是否过于相似。"""
        left_text = " ".join([left.hook, left.world_pitch, left.main_arc_pitch]).strip()
        right_text = " ".join([right.hook, right.world_pitch, right.main_arc_pitch]).strip()
        if not left_text or not right_text:
            return 0.0
        return SequenceMatcher(None, left_text, right_text).ratio()

    def _variant_structure_overlap(self, left: ConceptVariant, right: ConceptVariant) -> int:
        """比较关键结构标签重叠数量。"""
        fields = [
            "core_driver",
            "conflict_source",
            "world_structure",
            "protagonist_arc_mode",
        ]
        overlap = 0
        for field in fields:
            left_value = getattr(left, field, "").strip()
            right_value = getattr(right, field, "").strip()
            if left_value and right_value and left_value == right_value:
                overlap += 1
        return overlap

    def _collect_repeated_fields(self, left: ConceptVariant, right: ConceptVariant) -> list[str]:
        """找出完全重复的关键结构字段。"""
        mapping = {
            "core_driver": "主驱动",
            "conflict_source": "冲突源",
            "world_structure": "世界结构",
            "protagonist_arc_mode": "主角弧线",
        }
        repeated: list[str] = []
        for field, label in mapping.items():
            if getattr(left, field, "").strip() and getattr(left, field, "").strip() == getattr(right, field, "").strip():
                repeated.append(label)
        if left.ending_pitch.strip() and left.ending_pitch.strip() == right.ending_pitch.strip():
            repeated.append("结局走向")
        return repeated

    def _collect_repeated_sections(self, left: ConceptVariant, right: ConceptVariant) -> list[str]:
        """找出文本层面的重复段落或摘要。"""
        repeated: list[str] = []
        if self._section_similarity(left.hook, right.hook) >= self._HOOK_SIMILARITY_THRESHOLD:
            repeated.append("开局钩子")
        if self._section_similarity(left.world_pitch, right.world_pitch) >= self._SECTION_SIMILARITY_THRESHOLD:
            repeated.append("世界摘要")
        if self._section_similarity(left.main_arc_pitch, right.main_arc_pitch) >= self._SECTION_SIMILARITY_THRESHOLD:
            repeated.append("主线摘要")
        if self._first_window(left.main_arc_pitch) and self._first_window(left.main_arc_pitch) == self._first_window(right.main_arc_pitch):
            if "主线开头段落" not in repeated:
                repeated.append("主线开头段落")
        return repeated

    def _collect_repeated_keywords(self, left: ConceptVariant, right: ConceptVariant) -> list[str]:
        """提取两版之间重复出现的高频锚点词，优先拦截几乎同文的结果。"""
        tokens_left = set(self._extract_keywords(" ".join([left.hook, left.world_pitch, left.main_arc_pitch, left.ending_pitch])))
        tokens_right = set(
            self._extract_keywords(" ".join([right.hook, right.world_pitch, right.main_arc_pitch, right.ending_pitch]))
        )
        return sorted(tokens_left & tokens_right)[:6]

    def _build_divergence_guidance(
        self,
        intent: CreationIntent,
        target: ConceptVariant,
        sibling: ConceptVariant,
        repeated_fields: list[str],
        repeated_sections: list[str],
    ) -> list[str]:
        """把相似诊断转成下一轮回炉时可直接使用的纠偏提示。"""
        guidance: list[str] = [
            f"当前版本仍过于接近方向 {sibling.variant_no}，禁止复用其核心叙事结构。",
        ]
        if "开局钩子" in repeated_sections:
            guidance.append("必须更换开局意象与第一段戏剧触发点，不能沿用相同象征物或相同事件入口。")
        if "世界摘要" in repeated_sections or "世界结构" in repeated_fields:
            guidance.append("必须切换世界权力结构或江湖秩序布局，不能继续沿用现有的组织格局。")
        if "主线摘要" in repeated_sections or "冲突源" in repeated_fields:
            guidance.append("必须改写主线驱动逻辑，核心冲突源不能继续围绕相同的师门、旧案或同一套阴谋模型。")
        if "主角弧线" in repeated_fields:
            guidance.append("必须改变主角成长终点，例如从复仇转为守护、破局或秩序重塑。")
        if "结局走向" in repeated_fields:
            guidance.append("必须改写结局代价类型，不能继续给出同一种收束方式。")

        if "武侠" in intent.genre:
            if sibling.variant_strategy == "江湖人物局":
                guidance.append("本轮应明显偏向门派秩序局或真相追查局，不要再把人物恩怨和师门情义作为唯一推进轴。")
            elif sibling.variant_strategy == "门派秩序局":
                guidance.append("本轮应弱化门派权谋，改由人物命运或秘密追查驱动主线。")
            elif sibling.variant_strategy == "真相追查局":
                guidance.append("本轮应减少谜案追查比重，改用江湖情义或门派秩序崩坏作为主推进器。")

        guidance.append(f"当前版本的目标仍是保持“{target.variant_strategy or target.core_driver}”的大方向，但必须拉开表现。")
        return guidance

    def _section_similarity(self, left: str, right: str) -> float:
        """用于局部段落的相似度比较。"""
        if not left.strip() or not right.strip():
            return 0.0
        return SequenceMatcher(None, self._normalize_text(left), self._normalize_text(right)).ratio()

    def _first_window(self, text: str, length: int = 80) -> str:
        """截取开头一段标准化文本，用来识别“几乎同样开头”。"""
        normalized = self._normalize_text(text)
        return normalized[:length]

    def _normalize_text(self, text: str) -> str:
        """压缩空白和标点差异，降低纯措辞噪音。"""
        return re.sub(r"[\s，。！？、；：“”‘’《》【】\-,.:;!?()（）]+", "", text or "")

    def _extract_keywords(self, text: str) -> list[str]:
        """粗粒度提取中文高频锚点词，用于识别几乎同文的候选。"""
        stopwords = {
            "主角",
            "江湖",
            "世界",
            "故事",
            "最终",
            "开始",
            "成为",
            "选择",
            "真相",
            "复仇",
            "门派",
            "少年",
            "天道",
            "规则",
        }
        tokens = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,8}", text or "")
        result: list[str] = []
        for token in tokens:
            if token in stopwords or token.isdigit():
                continue
            if token not in result:
                result.append(token)
        return result

    def _resolve_strategy_templates(self, intent: CreationIntent) -> list[dict[str, object]]:
        """按题材返回 3 条优先分歧轨道。"""
        genre = intent.genre.strip()
        if "武侠" in genre:
            return [
                {
                    "variant_strategy": "江湖人物局",
                    "core_driver": "人物驱动",
                    "conflict_source": "江湖恩怨与师门关系",
                    "world_structure": "单江湖秩序下的人情网络",
                    "protagonist_arc_mode": "从私仇走向自我抉择",
                    "tone_signature": "血性、克制、带宿命感",
                    "ending_mode": intent.ending_preference or "以代价换来新的江湖平衡",
                    "differentiators": ["人物关系反转", "情义与复仇并行", "以主角选择推动剧情"],
                },
                {
                    "variant_strategy": "门派秩序局",
                    "core_driver": "世界驱动",
                    "conflict_source": "门派格局失衡与旧秩序崩坏",
                    "world_structure": "多门派并立的双层江湖秩序",
                    "protagonist_arc_mode": "从旁观者走向秩序重塑者",
                    "tone_signature": "厚重、权谋、史诗感",
                    "ending_mode": intent.ending_preference or "重建秩序但失去旧日江湖",
                    "differentiators": ["门派权谋更强", "世界格局变化更大", "阵营对抗主导推进"],
                },
                {
                    "variant_strategy": "真相追查局",
                    "core_driver": "悬疑驱动",
                    "conflict_source": "旧案与隐藏势力编织的长期阴谋",
                    "world_structure": "表层平稳、深层暗网遍布的秘密江湖",
                    "protagonist_arc_mode": "从追查真相走向承担真相代价",
                    "tone_signature": "冷峻、诡谲、层层揭晓",
                    "ending_mode": intent.ending_preference or "揭开真相却必须承受代价",
                    "differentiators": ["谜案推进更强", "局中局结构", "真相递进式揭晓"],
                },
            ]
        return [
            {
                "variant_strategy": "人物命运局",
                "core_driver": "人物驱动",
                "conflict_source": intent.conflict_prompt or "角色关系冲突",
                "world_structure": "围绕角色关系张力展开的局部秩序",
                "protagonist_arc_mode": "从被动卷入走向主动选择",
                "tone_signature": intent.tone or "情感张力强烈",
                "ending_mode": intent.ending_preference or "以角色代价换来成长",
                "differentiators": ["人物关系优先", "情感反转更强", "成长弧线主导"],
            },
            {
                "variant_strategy": "世界秩序局",
                "core_driver": "世界驱动",
                "conflict_source": "秩序结构崩坏或更替",
                "world_structure": "双层或多层秩序共存的世界",
                "protagonist_arc_mode": "从个体生存走向介入秩序",
                "tone_signature": intent.tone or "宏观、厚重",
                "ending_mode": intent.ending_preference or "建立新秩序",
                "differentiators": ["世界变化更强", "阵营冲突更强", "主线更宏观"],
            },
            {
                "variant_strategy": "秘密追查局",
                "core_driver": "悬疑驱动",
                "conflict_source": "秘密事件与隐蔽势力",
                "world_structure": "表层稳定、深层裂开的世界",
                "protagonist_arc_mode": "从追查真相走向承受真相",
                "tone_signature": intent.tone or "冷感、紧张",
                "ending_mode": intent.ending_preference or "真相揭晓但留下代价",
                "differentiators": ["谜团更重", "揭晓节奏更强", "事件推进主导"],
            },
        ]

    def _build_variant_frame_prompt(self, intent: CreationIntent, strategies: list[dict[str, object]]) -> str:
        return (
            "请根据作者创作意图和预设分歧轨道，先生成 3 个候选方向骨架。"
            "三个骨架必须在主叙事引擎、冲突来源、世界结构和主角成长路径上显著不同。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"分歧轨道：{strategies}\n"
            "返回 JSON：{frames:[{variant_no, variant_strategy, core_driver, conflict_source, "
            "world_structure, protagonist_arc_mode, tone_signature, ending_mode, differentiators}]}"
        )

    def _build_variant_expansion_prompt(
        self,
        intent: CreationIntent,
        frame: ConceptVariantFrame,
        siblings: list[ConceptVariant],
        *,
        force_diverge: bool,
        divergence_guidance: list[str],
    ) -> str:
        sibling_payload = [item.model_dump(mode="json") for item in siblings]
        diverge_rule = (
            "你必须显式避开已有候选版本的世界结构、核心冲突来源、主角弧线和结局类型。"
            if force_diverge
            else "请保持与其他轨道的清晰区分。"
        )
        correction = divergence_guidance or ["如出现相似结构，必须优先改写主线冲突、世界结构和结局代价。"]
        return (
            "请把以下候选方向骨架扩写成一版完整的整书候选方向。"
            "必须保留骨架中的分歧标签，并让作者一眼看出它与其他版本不同。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"当前骨架：{frame.model_dump(mode='json')}\n"
            f"已有候选：{sibling_payload}\n"
            f"差异要求：{diverge_rule}\n"
            f"本轮纠偏要求：{correction}\n"
            "返回 JSON：{hook, world_pitch, main_arc_pitch, ending_pitch, variant_strategy, "
            "core_driver, conflict_source, world_structure, protagonist_arc_mode, tone_signature, differentiators}"
        )

    def _fallback_hook(self, intent: CreationIntent, frame: ConceptVariantFrame) -> str:
        return f"{intent.genre or '长篇小说'}的{frame.variant_strategy or frame.core_driver}开局"

    def _fallback_world_pitch(self, intent: CreationIntent, frame: ConceptVariantFrame) -> str:
        return (
            f"以“{frame.world_structure or '多层秩序'}”为基本世界结构，"
            f"围绕“{frame.conflict_source or intent.conflict_prompt or '核心冲突'}”长期展开。"
        )

    def _fallback_arc_pitch(self, intent: CreationIntent, frame: ConceptVariantFrame) -> str:
        return (
            f"主角将沿着“{frame.protagonist_arc_mode or '从卷入到承担'}”的路线推进，"
            f"在“{frame.conflict_source or intent.conflict_prompt or '核心冲突'}”中不断被迫选择。"
        )

    def _character_id(self, character: CharacterBlueprint) -> str:
        """用稳定格式构建人物节点 ID。"""
        name = re.sub(r"\s+", "_", character.name.strip())
        return name or "unknown_character"

    def _resolve_character_id(
        self,
        characters: list[CharacterBlueprint],
        raw_name: object,
        fallback_index: int,
    ) -> str:
        """把模型返回的人名映射成稳定人物节点 ID。"""
        name = str(raw_name or "").strip()
        if name:
            for character in characters:
                if character.name == name:
                    return self._character_id(character)
        if 0 <= fallback_index < len(characters):
            return self._character_id(characters[fallback_index])
        return ""

    def _normalize_world_blueprint(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        skeleton: dict[str, Any],
        rules: dict[str, Any],
    ) -> WorldBlueprint:
        """把多段世界观生成结果收口为正式富结构世界蓝图。"""
        raw_power_system = rules.get("power_system") or skeleton.get("power_system")
        return WorldBlueprint(
            setting_summary=self._normalize_string(skeleton.get("setting_summary") or variant.world_pitch),
            era_context=self._normalize_string(skeleton.get("era_context")),
            social_order=self._normalize_string(skeleton.get("social_order")),
            historical_wounds=self._normalize_string_list(
                rules.get("historical_wounds") or skeleton.get("historical_wounds")
            ),
            public_secrets=self._normalize_string_list(
                rules.get("public_secrets") or skeleton.get("public_secrets")
            ),
            geography=self._normalize_location_list(skeleton.get("geography")),
            power_system=self._normalize_power_system(raw_power_system),
            factions=self._normalize_faction_list(skeleton.get("factions")),
            immutable_rules=self._normalize_immutable_rule_list(rules.get("immutable_rules")),
            taboo_rules=self._normalize_taboo_rule_list(rules.get("taboo_rules")),
        )

    def normalize_world_blueprint_payload(self, payload: object) -> WorldBlueprint:
        """把任意来源的世界观载荷压成正式协议，供用例层统一复用。"""
        raw = payload if isinstance(payload, dict) else {}
        return WorldBlueprint(
            setting_summary=self._normalize_string(raw.get("setting_summary")),
            era_context=self._normalize_string(raw.get("era_context")),
            social_order=self._normalize_string(raw.get("social_order")),
            historical_wounds=self._normalize_string_list(raw.get("historical_wounds")),
            public_secrets=self._normalize_string_list(raw.get("public_secrets")),
            geography=self._normalize_location_list(raw.get("geography")),
            power_system=self._normalize_power_system(raw.get("power_system")),
            factions=self._normalize_faction_list(raw.get("factions")),
            immutable_rules=self._normalize_immutable_rule_list(raw.get("immutable_rules")),
            taboo_rules=self._normalize_taboo_rule_list(raw.get("taboo_rules")),
        )

    def normalize_character_blueprints_payload(self, payload: object) -> list[CharacterBlueprint]:
        """把人物蓝图原始载荷统一收口为正式角色列表。"""
        raw_items = self._extract_character_items(payload)
        normalized: list[CharacterBlueprint] = []
        for index, item in enumerate(raw_items, start=1):
            if isinstance(item, CharacterBlueprint):
                normalized.append(item)
                continue
            if not isinstance(item, dict):
                continue
            normalized.append(self._normalize_character_blueprint(item, index))
        return normalized

    def normalize_relationship_blueprint_edges_payload(
        self,
        payload: object,
        characters: list[CharacterBlueprint] | None = None,
    ) -> list[RelationshipBlueprintEdge]:
        """把人物关系原始载荷统一收口为正式关系边列表。"""
        return self._normalize_relationship_edges(payload, characters or [])

    def normalize_roadmap_payload(
        self,
        payload: object,
        *,
        starting_chapter: int = 1,
        chapter_count: int | None = None,
    ) -> list[ChapterRoadmapItem]:
        """把章节路线原始载荷统一收口为正式路线列表。"""
        raw_items = self._extract_roadmap_items(payload)
        normalized: list[ChapterRoadmapItem] = []
        for index, item in enumerate(raw_items, start=0):
            if isinstance(item, ChapterRoadmapItem):
                normalized.append(item)
                continue
            if not isinstance(item, dict):
                continue
            normalized.append(self._normalize_roadmap_item(item, starting_chapter + index))
        if normalized:
            return normalized
        if chapter_count is not None:
            return self._build_fallback_roadmap(starting_chapter, chapter_count)
        return []

    def _extract_character_items(self, payload: object) -> list[object]:
        """兼容 characters 数组、单对象和直接传列表的多种人物载荷。"""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            raw_items = payload.get("characters")
            if isinstance(raw_items, list):
                return raw_items
            if isinstance(raw_items, dict):
                return [raw_items]
            if any(key in payload for key in ("name", "role", "public_persona", "core_motivation")):
                return [payload]
        return []

    def _extract_roadmap_items(self, payload: object) -> list[object]:
        """兼容 chapters 数组、单对象和直接传列表的多种章节路线载荷。"""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            raw_items = payload.get("chapters")
            if isinstance(raw_items, list):
                return raw_items
            if isinstance(raw_items, dict):
                return [raw_items]
            if any(key in payload for key in ("chapter_number", "goal", "core_conflict", "closure_function")):
                return [payload]
        return []

    def _normalize_character_blueprint(self, item: dict[str, Any], index: int) -> CharacterBlueprint:
        """规范单个人物蓝图，避免数组字段被模型输出成整段中文。"""
        name = self._normalize_string(item.get("name")) or f"角色{index}"
        return CharacterBlueprint(
            name=name,
            role=self._normalize_string(item.get("role")),
            public_persona=self._normalize_string(item.get("public_persona")),
            core_motivation=self._normalize_string(item.get("core_motivation")),
            fatal_flaw=self._normalize_string(item.get("fatal_flaw")),
            non_negotiable_traits=self._normalize_string_list(item.get("non_negotiable_traits")),
            relationship_constraints=self._normalize_string_list(item.get("relationship_constraints")),
            arc_outline=self._normalize_string_list(item.get("arc_outline")),
        )

    def _normalize_relationship_edges(
        self,
        payload: object,
        characters: list[CharacterBlueprint],
    ) -> list[RelationshipBlueprintEdge]:
        """把人物关系原始载荷统一收口为正式关系边列表。"""
        raw_items = self._extract_relationship_items(payload)
        normalized: list[RelationshipBlueprintEdge] = []
        for index, item in enumerate(raw_items, start=1):
            if not isinstance(item, dict):
                continue
            edge = self._normalize_relationship_edge(item, characters, index)
            if edge is not None:
                normalized.append(edge)
        return normalized

    def _extract_relationship_items(self, payload: object) -> list[object]:
        """兼容 relationships 数组、单对象和直接传列表的多种关系载荷。"""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            raw_items = payload.get("relationships")
            if isinstance(raw_items, list):
                return raw_items
            if isinstance(raw_items, dict):
                return [raw_items]
            if any(key in payload for key in ("relation_type", "source_character_id", "target_character_id")):
                return [payload]
        return []

    def _normalize_relationship_edge(
        self,
        item: dict[str, Any],
        characters: list[CharacterBlueprint],
        index: int,
    ) -> RelationshipBlueprintEdge | None:
        """规范单条关系边，兼容英文枚举和半结构强度描述。"""
        source_character_id = str(
            item.get("source_character_id")
            or self._resolve_character_id(characters, item.get("source_name"), 0)
        )
        target_character_id = str(
            item.get("target_character_id")
            or self._resolve_character_id(characters, item.get("target_name"), 1)
        )
        if not source_character_id or not target_character_id:
            return None
        return RelationshipBlueprintEdge.model_validate(
            {
                "edge_id": self._normalize_string(item.get("edge_id")) or f"rel-{index}",
                "source_character_id": source_character_id,
                "target_character_id": target_character_id,
                "relation_type": self._normalize_string(item.get("relation_type")) or "关键关系",
                "polarity": self._normalize_relationship_polarity(item.get("polarity")),
                "intensity": self._normalize_relationship_intensity(item.get("intensity")),
                "visibility": self._normalize_relationship_visibility(item.get("visibility")),
                "stability": self._normalize_relationship_stability(item.get("stability")),
                "summary": self._normalize_string(item.get("summary")),
                "hidden_truth": self._normalize_string(item.get("hidden_truth")),
                "non_breakable_without_reveal": self._normalize_boolean(
                    item.get("non_breakable_without_reveal"),
                    default=False,
                ),
            }
        )

    def _normalize_roadmap_item(
        self,
        item: dict[str, Any],
        fallback_chapter_number: int,
    ) -> ChapterRoadmapItem:
        """规范单章路线，兼容数组字段被输出成整段中文或字符串线索列表。"""
        chapter_number = self._normalize_positive_int(item.get("chapter_number"), fallback=fallback_chapter_number)
        return ChapterRoadmapItem.model_validate(
            {
                "chapter_number": chapter_number,
                "title": self._normalize_string(item.get("title")) or f"第 {chapter_number} 章",
                "story_stage": self._normalize_string(item.get("story_stage")),
                "timeline_anchor": self._normalize_string(item.get("timeline_anchor")),
                "depends_on_chapters": self._normalize_int_list(item.get("depends_on_chapters")),
                "goal": self._normalize_string(item.get("goal")) or "推进主线",
                "core_conflict": self._normalize_string(item.get("core_conflict")) or "外部压力逼近",
                "turning_point": self._normalize_string(item.get("turning_point")) or "主角必须做出选择",
                "story_progress": self._normalize_string(item.get("story_progress")) or "主线局势出现新的状态变化",
                "character_progress": self._normalize_string_list(item.get("character_progress")),
                "relationship_progress": self._normalize_string_list(item.get("relationship_progress")),
                "new_reveals": self._normalize_string_list(item.get("new_reveals")),
                "status_shift": self._normalize_string_list(item.get("status_shift")),
                "chapter_function": self._normalize_string(item.get("chapter_function")) or "推进",
                "anti_repeat_signature": self._normalize_string(item.get("anti_repeat_signature"))
                or f"{self._normalize_string(item.get('chapter_function'))}:{self._normalize_string(item.get('goal'))}",
                "planned_loops": self._normalize_planned_loops(item.get("planned_loops"), chapter_number),
                "closure_function": self._normalize_string(item.get("closure_function")) or "制造下一章钩子",
            }
        )

    def _normalize_planned_loops(self, value: object, chapter_number: int) -> list[dict[str, object]]:
        """把字符串或半结构线索列表统一压成正式 planned_loops 结构。"""
        items: list[dict[str, object]] = []
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, dict):
            raw_items = [value]
        elif value is None or value == "":
            raw_items = []
        else:
            raw_items = self._normalize_string_list(value)

        for index, raw_item in enumerate(raw_items, start=1):
            if isinstance(raw_item, dict):
                title = self._normalize_string(
                    raw_item.get("title") or raw_item.get("summary") or raw_item.get("loop_id")
                ) or f"第 {chapter_number} 章线索 {index}"
                summary = self._normalize_string(raw_item.get("summary")) or title
                loop_id = self._normalize_string(raw_item.get("loop_id")) or f"chapter-{chapter_number}-loop-{index}"
                priority = self._normalize_positive_int(raw_item.get("priority"), fallback=1)
                due_start = self._normalize_optional_positive_int(
                    raw_item.get("due_start_chapter"),
                    default=chapter_number,
                )
                due_end = self._normalize_optional_positive_int(
                    raw_item.get("due_end_chapter"),
                    default=chapter_number + 2,
                )
                items.append(
                    {
                        "loop_id": loop_id,
                        "title": title,
                        "summary": summary,
                        "priority": priority,
                        "due_start_chapter": due_start,
                        "due_end_chapter": due_end,
                        "related_characters": self._normalize_string_list(raw_item.get("related_characters")),
                        "resolution_requirements": self._normalize_string_list(
                            raw_item.get("resolution_requirements")
                        ),
                    }
                )
                continue

            summary = self._normalize_string(raw_item)
            if not summary:
                continue
            items.append(
                {
                    "loop_id": f"chapter-{chapter_number}-loop-{index}",
                    "title": summary,
                    "summary": summary,
                    "priority": 1,
                    "due_start_chapter": chapter_number,
                    "due_end_chapter": chapter_number + 2,
                    "related_characters": [],
                    "resolution_requirements": [],
                }
            )
        return items

    def _build_fallback_roadmap(self, starting_chapter: int, chapter_count: int) -> list[ChapterRoadmapItem]:
        """当模型未返回可用章节路线时，提供可继续编辑的最小草稿。"""
        return [
            ChapterRoadmapItem(
                chapter_number=chapter_no,
                title=f"第 {chapter_no} 章",
                story_stage=self._fallback_story_stage(chapter_no, starting_chapter, chapter_count),
                timeline_anchor=f"第 {chapter_no} 章当日夜",
                depends_on_chapters=[chapter_no - 1] if chapter_no > starting_chapter else [],
                goal="推进主线",
                core_conflict="外部压力逼近",
                turning_point="主角必须做出选择",
                story_progress="主线局势被迫向前推进一步",
                character_progress=["主角认知发生变化"],
                relationship_progress=[],
                new_reveals=[],
                status_shift=["主角立场发生变化"],
                chapter_function=self._fallback_chapter_function(chapter_no, starting_chapter),
                anti_repeat_signature=f"fallback:{chapter_no}",
                planned_loops=[],
                closure_function="制造下一章钩子",
            )
            for chapter_no in range(starting_chapter, starting_chapter + chapter_count)
        ]

    def _normalize_story_arcs(
        self,
        payload: object,
        *,
        starting_chapter: int,
        chapter_count: int,
    ) -> list[StoryArcPlan]:
        """把阶段弧线原始载荷统一收口为正式弧线列表。"""
        raw_items = self._extract_story_arc_items(payload)
        normalized: list[StoryArcPlan] = []
        for index, item in enumerate(raw_items, start=1):
            if isinstance(item, StoryArcPlan):
                normalized.append(item)
                continue
            if not isinstance(item, dict):
                continue
            normalized.append(
                self._normalize_story_arc_item(
                    item,
                    index=index,
                    starting_chapter=starting_chapter,
                    chapter_count=chapter_count,
                )
            )
        if normalized:
            return self._ensure_story_arc_ranges(normalized, starting_chapter, chapter_count)
        return []

    def _extract_story_arc_items(self, payload: object) -> list[object]:
        """兼容 story_arcs 数组、单对象和直接传列表的多种阶段载荷。"""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            raw_items = payload.get("story_arcs") or payload.get("arcs")
            if isinstance(raw_items, list):
                return raw_items
            if isinstance(raw_items, dict):
                return [raw_items]
            if any(key in payload for key in ("arc_number", "start_chapter", "end_chapter", "arc_climax")):
                return [payload]
        return []

    def _normalize_story_arc_item(
        self,
        item: dict[str, Any],
        *,
        index: int,
        starting_chapter: int,
        chapter_count: int,
    ) -> StoryArcPlan:
        """规范单个阶段弧线，保证长篇分层结构稳定。"""
        fallback_start = starting_chapter + (index - 1) * max(1, chapter_count // max(self._infer_story_arc_count(chapter_count), 1))
        fallback_end = min(starting_chapter + chapter_count - 1, fallback_start + max(1, chapter_count // max(self._infer_story_arc_count(chapter_count), 1)) - 1)
        return StoryArcPlan.model_validate(
            {
                "arc_number": self._normalize_positive_int(item.get("arc_number"), fallback=index),
                "title": self._normalize_string(item.get("title")) or f"阶段 {index}",
                "purpose": self._normalize_string(item.get("purpose")) or "推动主线进入下一阶段",
                "start_chapter": self._normalize_positive_int(item.get("start_chapter"), fallback=fallback_start),
                "end_chapter": self._normalize_positive_int(item.get("end_chapter"), fallback=fallback_end),
                "main_progress": self._normalize_string_list(item.get("main_progress")),
                "relationship_progress": self._normalize_string_list(item.get("relationship_progress")),
                "loop_progress": self._normalize_string_list(item.get("loop_progress")),
                "timeline_milestones": self._normalize_string_list(item.get("timeline_milestones")),
                "arc_climax": self._normalize_string(item.get("arc_climax")) or "在阶段末尾制造明确转折",
            }
        )

    def _ensure_story_arc_ranges(
        self,
        story_arcs: list[StoryArcPlan],
        starting_chapter: int,
        chapter_count: int,
    ) -> list[StoryArcPlan]:
        """修正阶段范围，确保所有章节都被覆盖且不存在断裂。"""
        if not story_arcs:
            return []
        total_end = starting_chapter + chapter_count - 1
        ordered = sorted(story_arcs, key=lambda item: (item.start_chapter, item.arc_number))
        segment_count = len(ordered)
        base_size = max(1, chapter_count // max(segment_count, 1))
        remainder = max(0, chapter_count - base_size * segment_count)
        current_start = starting_chapter
        normalized: list[StoryArcPlan] = []
        for index, arc in enumerate(ordered, start=1):
            segment_size = base_size + (1 if index <= remainder else 0)
            end_chapter = min(total_end, current_start + segment_size - 1)
            normalized.append(
                arc.model_copy(
                    update={
                        "arc_number": index,
                        "start_chapter": current_start,
                        "end_chapter": end_chapter,
                    }
                )
            )
            current_start = end_chapter + 1
        if normalized:
            normalized[-1] = normalized[-1].model_copy(update={"end_chapter": total_end})
        return normalized

    def _build_fallback_story_arcs(self, starting_chapter: int, chapter_count: int) -> list[StoryArcPlan]:
        """当阶段生成失败时，构造最小可编辑的阶段骨架。"""
        arc_count = self._infer_story_arc_count(chapter_count)
        total_end = starting_chapter + chapter_count - 1
        base_size = max(1, chapter_count // max(arc_count, 1))
        remainder = max(0, chapter_count - base_size * arc_count)
        current_start = starting_chapter
        arcs: list[StoryArcPlan] = []
        for index in range(1, arc_count + 1):
            segment_size = base_size + (1 if index <= remainder else 0)
            end_chapter = min(total_end, current_start + segment_size - 1)
            arcs.append(
                StoryArcPlan(
                    arc_number=index,
                    title=f"第 {index} 幕",
                    purpose="推进主线进入下一阶段",
                    start_chapter=current_start,
                    end_chapter=end_chapter,
                    main_progress=[f"第 {index} 幕主线升级"],
                    relationship_progress=[f"第 {index} 幕人物关系发生变化"],
                    loop_progress=[f"第 {index} 幕回收或升级关键线索"],
                    timeline_milestones=[f"第 {current_start}-{end_chapter} 章阶段时间推进"],
                    arc_climax="阶段末尾抛出新的转折或揭示",
                )
            )
            current_start = end_chapter + 1
        return arcs

    def _infer_story_arc_count(self, chapter_count: int) -> int:
        """根据目标章数推导阶段数量，避免长篇直接一次性细化。"""
        if chapter_count <= 12:
            return 3
        if chapter_count <= 24:
            return 4
        if chapter_count <= 48:
            return 5
        if chapter_count <= 72:
            return 6
        return 7

    def _normalize_int_list(self, value: object) -> list[int]:
        """把章节依赖等整数列表统一收口。"""
        items = self._normalize_string_list(value)
        result: list[int] = []
        for item in items:
            if item.isdigit():
                result.append(int(item))
        return result

    def _fallback_story_stage(self, chapter_number: int, starting_chapter: int, chapter_count: int) -> str:
        """在兜底路线中给章节分配阶段标签。"""
        story_arcs = self._build_fallback_story_arcs(starting_chapter, chapter_count)
        for arc in story_arcs:
            if arc.start_chapter <= chapter_number <= arc.end_chapter:
                return arc.title
        return "未分阶段"

    def _fallback_chapter_function(self, chapter_number: int, starting_chapter: int) -> str:
        """为兜底章节路线分配基础章节功能，避免全部同质化。"""
        sequence = ["开局", "推进", "揭示", "反转", "喘息", "收束"]
        offset = max(chapter_number - starting_chapter, 0)
        return sequence[offset % len(sequence)]

    def _normalize_string(self, value: object) -> str:
        """把 LLM 的任意标量输出压成稳定字符串。"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value).strip()
        if isinstance(value, list):
            return "；".join(self._normalize_string_list(value))
        if isinstance(value, dict):
            preferred = (
                value.get("summary")
                or value.get("description")
                or value.get("content")
                or value.get("text")
                or value.get("name")
            )
            if preferred is not None:
                return self._normalize_string(preferred)
        return str(value).strip()

    def _normalize_string_list(self, value: object) -> list[str]:
        """把字符串或杂项列表稳定压成 list[str]，避免单字拆分。"""
        if value is None or value == "":
            return []
        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                if item is None:
                    continue
                normalized = self._normalize_string(item)
                if normalized:
                    result.append(normalized)
            return result
        if isinstance(value, dict):
            return [self._normalize_string(value)] if self._normalize_string(value) else []
        if isinstance(value, (int, float, bool)):
            return [str(value).strip()]

        text = str(value).strip()
        if not text:
            return []
        parts = [item.strip() for item in re.split(r"[\n；;、，]+", text) if item.strip()]
        return parts

    def _normalize_object_list(self, value: object) -> list[dict[str, Any]]:
        """把对象或对象数组统一压成列表，供 rich schema 逐项处理。"""
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    def _normalize_location_list(self, value: object) -> list[LocationBlueprint]:
        """规范地点列表。"""
        locations: list[LocationBlueprint] = []
        for item in self._normalize_object_list(value):
            locations.append(
                LocationBlueprint.model_validate(
                    {
                        "name": self._normalize_string(item.get("name")),
                        "role": self._normalize_string(item.get("role")),
                        "description": self._normalize_string(item.get("description")),
                    }
                )
            )
        return locations

    def _normalize_faction_list(self, value: object) -> list[FactionBlueprint]:
        """规范势力列表，并确保 methods 永远是 list[str]。"""
        factions: list[FactionBlueprint] = []
        for item in self._normalize_object_list(value):
            factions.append(
                FactionBlueprint.model_validate(
                    {
                        "name": self._normalize_string(item.get("name")),
                        "position": self._normalize_string(item.get("position")),
                        "goal": self._normalize_string(item.get("goal")),
                        "methods": self._normalize_string_list(item.get("methods")),
                        "public_image": self._normalize_string(item.get("public_image")),
                        "hidden_truth": self._normalize_string(item.get("hidden_truth")),
                    }
                )
            )
        return factions

    def _normalize_immutable_rule_list(self, value: object) -> list[ImmutableRuleBlueprint]:
        """规范不可变规则列表。"""
        rules: list[ImmutableRuleBlueprint] = []
        for index, item in enumerate(self._normalize_object_list(value), start=1):
            rules.append(
                ImmutableRuleBlueprint.model_validate(
                    {
                        "key": self._normalize_string(item.get("key")) or f"immutable_rule_{index}",
                        "description": self._normalize_string(item.get("description")),
                        "category": self._normalize_string(item.get("category")) or "world",
                        "rationale": self._normalize_string(item.get("rationale")),
                        "is_immutable": bool(item.get("is_immutable", True)),
                    }
                )
            )
        return rules

    def _normalize_taboo_rule_list(self, value: object) -> list[TabooRuleBlueprint]:
        """规范禁忌规则列表。"""
        rules: list[TabooRuleBlueprint] = []
        for index, item in enumerate(self._normalize_object_list(value), start=1):
            rules.append(
                TabooRuleBlueprint.model_validate(
                    {
                        "key": self._normalize_string(item.get("key")) or f"taboo_rule_{index}",
                        "description": self._normalize_string(item.get("description")),
                        "consequence": self._normalize_string(item.get("consequence")),
                        "is_immutable": bool(item.get("is_immutable", True)),
                    }
                )
            )
        return rules

    def _normalize_power_system(self, value: object) -> PowerSystemBlueprint:
        """规范力量体系，保证所有列表字段稳定为 list[str]。"""
        if isinstance(value, dict):
            payload = value
        else:
            payload = {"core_mechanics": self._normalize_string(value)}
        power_system = PowerSystemBlueprint.model_validate(
            {
                "core_mechanics": self._normalize_string(payload.get("core_mechanics")),
                "costs": self._normalize_string_list(payload.get("costs")),
                "limitations": self._normalize_string_list(payload.get("limitations")),
                "advancement_path": self._normalize_string_list(payload.get("advancement_path")),
                "symbols": self._normalize_string_list(payload.get("symbols")),
            }
        )
        return power_system

    def _normalize_relationship_polarity(self, value: object) -> Literal["正向", "负向", "复杂", "伪装"]:
        """把模型返回的关系倾向统一收口到中文正式枚举。"""
        text = self._normalize_enum_token(value)
        if text in {"正向", "positive", "ally", "friendly", "trust", "trusted", "supportive"}:
            return "正向"
        if text in {"负向", "negative", "hostile", "enemy", "rival", "opposed", "antagonistic"}:
            return "负向"
        if text in {"伪装", "masked", "disguised", "fake", "performative", "facade"}:
            return "伪装"
        if text in {"复杂", "complex", "mixed", "conflicted", "ambiguous"}:
            return "复杂"
        return "复杂"

    def _normalize_relationship_visibility(
        self,
        value: object,
    ) -> Literal["公开", "半公开", "隐藏", "误导性表象"]:
        """把关系公开程度统一收口到中文正式枚举。"""
        text = self._normalize_enum_token(value)
        if text in {"公开", "public", "open"}:
            return "公开"
        if text in {"隐藏", "hidden", "secret", "concealed"}:
            return "隐藏"
        if text in {"误导性表象", "misleading", "false_public", "facade", "misleading_public"}:
            return "误导性表象"
        if text in {"半公开", "semi_public", "partial", "known_to_some", "semiopen"}:
            return "半公开"
        return "半公开"

    def _normalize_relationship_stability(self, value: object) -> Literal["稳定", "脆弱", "正在转变"]:
        """把关系稳定性统一收口到中文正式枚举。"""
        text = self._normalize_enum_token(value)
        if text in {"稳定", "stable", "fixed", "firm", "high"}:
            return "稳定"
        if text in {"脆弱", "fragile", "unstable", "shaky", "low"}:
            return "脆弱"
        if text in {"正在转变", "changing", "evolving", "transitional", "volatile", "medium"}:
            return "正在转变"
        return "稳定"

    def _normalize_relationship_intensity(self, value: object) -> int:
        """把数字、数字字符串和强弱描述统一压成 1-5 的关系强度。"""
        if isinstance(value, bool) or value is None:
            return 3
        if isinstance(value, (int, float)):
            return max(1, min(int(value), 5))
        text = self._normalize_enum_token(value)
        if text.isdigit():
            return max(1, min(int(text), 5))
        if text in {"high", "strong", "intense"}:
            return 4
        if text in {"medium", "moderate"}:
            return 3
        if text in {"low", "weak"}:
            return 2
        return 3

    def _normalize_positive_int(self, value: object, *, fallback: int) -> int:
        """把章节号、优先级等正整数统一收口。"""
        if isinstance(value, bool) or value is None:
            return fallback
        if isinstance(value, (int, float)):
            normalized = int(value)
            return normalized if normalized > 0 else fallback
        text = self._normalize_string(value)
        if text.isdigit():
            normalized = int(text)
            return normalized if normalized > 0 else fallback
        return fallback

    def _normalize_optional_positive_int(self, value: object, *, default: int | None) -> int | None:
        """把可选正整数统一收口，并允许安全默认值。"""
        if value is None or value == "":
            return default
        normalized = self._normalize_positive_int(value, fallback=default or 1)
        return normalized if normalized > 0 else default

    def _normalize_boolean(self, value: object, *, default: bool) -> bool:
        """把布尔或文本布尔值统一收口，避免模型返回 yes/no 时失真。"""
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        text = self._normalize_enum_token(value)
        if text in {"true", "yes", "required", "需要", "是", "y"}:
            return True
        if text in {"false", "no", "optional", "否", "不需要", "n"}:
            return False
        return default

    def _normalize_enum_token(self, value: object) -> str:
        """统一枚举型文本的大小写、连字符和空格，便于兼容模型漂移。"""
        text = self._normalize_string(value).lower().strip()
        if not text:
            return ""
        return re.sub(r"[\s\-]+", "_", text)

    def _build_world_generation_error_message(self, exc: ValueError) -> str:
        """把底层校验错误压缩成用户可读的中文提示。"""
        text = str(exc)
        if "methods" in text:
            return "世界观草稿生成失败：势力的“运作方式”字段格式不正确。"
        if "core_mechanics" in text:
            return "世界观草稿生成失败：力量体系缺少核心机制。"
        if any(key in text for key in ("costs", "limitations", "advancement_path", "symbols")):
            return "世界观草稿生成失败：力量体系的列表字段格式不正确。"
        return "世界观草稿生成失败：世界结构输出不符合要求，请重试。"

    def _build_character_generation_error_message(self, exc: ValueError) -> str:
        """把人物蓝图校验错误压缩成中文提示，避免前端直接看到底层异常。"""
        text = str(exc)
        if "arc_outline" in text:
            return "人物蓝图生成失败：角色弧线字段应为列表。"
        if "non_negotiable_traits" in text:
            return "人物蓝图生成失败：不可突变特质字段应为列表。"
        if "relationship_constraints" in text:
            return "人物蓝图生成失败：人物关系约束字段应为列表。"
        return "人物蓝图生成失败：角色结构输出不符合要求，请重试。"

    def _build_relationship_generation_error_message(self, exc: ValueError) -> str:
        """把人物关系边校验错误压缩成中文提示。"""
        text = str(exc)
        if "polarity" in text:
            return "人物蓝图生成失败：人物关系的“关系倾向”字段格式不正确。"
        if "visibility" in text:
            return "人物蓝图生成失败：人物关系的“公开程度”字段格式不正确。"
        if "stability" in text:
            return "人物蓝图生成失败：人物关系的“稳定性”字段格式不正确。"
        return "人物蓝图生成失败：人物关系结构输出不符合要求，请重试。"

    def _build_roadmap_generation_error_message(self, exc: ValueError) -> str:
        """把章节路线校验错误压缩成中文提示。"""
        text = str(exc)
        if "Could not extract JSON" in text:
            return "章节路线生成失败：模型返回的章节结构不是合法 JSON，请重试。"
        if "character_progress" in text:
            return "章节路线生成失败：人物推进字段应为列表。"
        if "relationship_progress" in text:
            return "章节路线生成失败：关系推进字段应为列表。"
        if "planned_loops" in text:
            return "章节路线生成失败：计划线索字段格式不正确。"
        return "章节路线生成失败：章节结构输出不符合要求，请重试。"

    def _build_roadmap_stage_regeneration_error_message(self, exc: ValueError) -> str:
        """把阶段重生成错误压缩成用户可读提示。"""
        text = str(exc)
        if "Could not extract JSON" in text:
            return "阶段重生成失败：模型返回的阶段章节结构不是合法 JSON，请重试。"
        if "character_progress" in text:
            return "阶段重生成失败：人物推进字段应为列表。"
        if "relationship_progress" in text:
            return "阶段重生成失败：关系推进字段应为列表。"
        if "planned_loops" in text:
            return "阶段重生成失败：计划线索字段格式不正确。"
        return "阶段重生成失败：章节结构输出不符合要求，请重试。"

    def _build_world_skeleton_prompt(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        feedback: str,
    ) -> str:
        return (
            "请基于作者意图和已选候选方向，生成世界观骨架。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"微调要求：{feedback or '无'}\n"
            "必须严格返回合法 JSON。所有数组字段都必须是数组，不要写成一整段中文字符串。\n"
            "最小示例："
            "{"
            "\"setting_summary\":\"世界概述\","
            "\"era_context\":\"时代背景\","
            "\"social_order\":\"社会秩序\","
            "\"historical_wounds\":[\"历史创伤1\",\"历史创伤2\"],"
            "\"public_secrets\":[\"公开秘密1\"],"
            "\"geography\":[{\"name\":\"地点名\",\"role\":\"地点作用\",\"description\":\"地点描述\"}],"
            "\"factions\":[{\"name\":\"势力名\",\"position\":\"势力定位\",\"goal\":\"势力目标\",\"methods\":[\"手段1\",\"手段2\"],\"public_image\":\"公开形象\",\"hidden_truth\":\"隐藏真相\"}]"
            "}\n"
            "返回 JSON：{setting_summary, era_context, social_order, historical_wounds:string[], public_secrets:string[],"
            " geography:[{name, role, description}], factions:[{name, position, goal, methods:string[], public_image, hidden_truth}]}"
        )

    def _build_world_rules_prompt(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        skeleton: dict[str, Any],
        feedback: str,
    ) -> str:
        return (
            "请基于作者意图、已选方向和世界骨架，补全正式世界规则。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"世界骨架：{skeleton}\n"
            f"微调要求：{feedback or '无'}\n"
            "必须严格返回合法 JSON。所有 costs、limitations、advancement_path、symbols 都必须是 string[]，"
            "不要写成一句长中文。immutable_rules、taboo_rules 必须是对象数组。\n"
            "最小示例："
            "{"
            "\"power_system\":{\"core_mechanics\":\"核心机制\",\"costs\":[\"代价1\"],\"limitations\":[\"限制1\"],\"advancement_path\":[\"阶段1\"],\"symbols\":[\"象征1\"]},"
            "\"immutable_rules\":[{\"key\":\"规则键\",\"description\":\"规则描述\",\"category\":\"world\",\"rationale\":\"规则缘由\",\"is_immutable\":true}],"
            "\"taboo_rules\":[{\"key\":\"禁忌键\",\"description\":\"禁忌描述\",\"consequence\":\"触犯后果\",\"is_immutable\":true}],"
            "\"historical_wounds\":[\"历史创伤1\"],"
            "\"public_secrets\":[\"公开秘密1\"]"
            "}\n"
            "返回 JSON：{power_system:{core_mechanics, costs:string[], limitations:string[], advancement_path:string[], symbols:string[]},"
            " immutable_rules:[{key, description, category, rationale, is_immutable}],"
            " taboo_rules:[{key, description, consequence, is_immutable}], historical_wounds:string[], public_secrets:string[]}"
        )

    def _build_character_prompt(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        feedback: str,
    ) -> str:
        return (
            "请基于作者意图、候选方向和世界观蓝图，生成核心人物组。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"世界观：{world.model_dump(mode='json')}\n"
            f"微调要求：{feedback or '无'}\n"
            "必须严格返回合法 JSON。"
            "non_negotiable_traits、relationship_constraints、arc_outline 都必须是 string[]，"
            "不要把这些数组字段写成一整段中文说明。\n"
            "最小示例："
            "{"
            "\"characters\":[{"
            "\"name\":\"沈砚\","
            "\"role\":\"主角\","
            "\"public_persona\":\"冷静寡言的落魄少年\","
            "\"core_motivation\":\"追查父母真相\","
            "\"fatal_flaw\":\"执念过重\","
            "\"non_negotiable_traits\":[\"遇到大义不会退缩\",\"嘴硬心软\"],"
            "\"relationship_constraints\":[\"与师兄既竞争又依赖\",\"对师父始终保留戒心\"],"
            "\"arc_outline\":[\"前期被动卷入\",\"中期主动追查\",\"后期承担代价完成选择\"]"
            "}]"
            "}\n"
            "返回 JSON：{characters:[{name, role, public_persona, core_motivation, fatal_flaw,"
            " non_negotiable_traits:string[], relationship_constraints:string[], arc_outline:string[]}]}"
        )

    def _build_relationship_prompt(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        feedback: str,
    ) -> str:
        return (
            "请基于作者意图、已选方向、世界观和人物节点，输出核心人物关系图谱。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"世界观：{world.model_dump(mode='json')}\n"
            f"人物节点：{[item.model_dump(mode='json') for item in characters]}\n"
            f"微调要求：{feedback or '无'}\n"
            "必须严格返回合法 JSON。polarity、visibility、stability 必须使用中文正式枚举，"
            "禁止使用 positive、public、stable 这类英文值。intensity 必须是 1-5 的整数。\n"
            "最小示例："
            "{"
            "\"relationships\":[{"
            "\"edge_id\":\"rel-1\","
            "\"source_character_id\":\"沈砚\","
            "\"target_character_id\":\"陆行川\","
            "\"source_name\":\"沈砚\","
            "\"target_name\":\"陆行川\","
            "\"relation_type\":\"师徒\","
            "\"polarity\":\"复杂\","
            "\"intensity\":4,"
            "\"visibility\":\"半公开\","
            "\"stability\":\"正在转变\","
            "\"summary\":\"名义师徒，实则彼此试探。\","
            "\"hidden_truth\":\"陆行川隐瞒了旧案真相。\","
            "\"non_breakable_without_reveal\":true"
            "}]"
            "}\n"
            "返回 JSON：{relationships:[{edge_id, source_character_id, target_character_id, source_name, target_name,"
            " relation_type, polarity, intensity, visibility, stability, summary, hidden_truth,"
            " non_breakable_without_reveal}]}"
        )

    def _build_roadmap_prompt(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        feedback: str,
        starting_chapter: int,
        chapter_count: int,
        existing_roadmap: list[ChapterRoadmapItem],
    ) -> str:
        existing_payload: list[dict[str, Any]] = [item.model_dump(mode="json") for item in existing_roadmap]
        return (
            "请基于作者意图、候选方向、世界观和人物蓝图，生成整书章节路线。"
            "每章都要明确目标、冲突、转折、人物推进和计划中的伏笔线索。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"世界观：{world.model_dump(mode='json')}\n"
            f"人物：{[item.model_dump(mode='json') for item in characters]}\n"
            f"已有路线：{existing_payload}\n"
            f"起始章节：{starting_chapter}\n"
            f"目标章数：{chapter_count}\n"
            f"微调要求：{feedback or '无'}\n"
            "必须严格返回合法 JSON。character_progress、relationship_progress 必须是 string[]，"
            "planned_loops 必须是对象数组，绝不能只返回线索标题字符串列表。\n"
            "最小示例："
            "{"
            "\"chapters\":[{"
            "\"chapter_number\":1,"
            "\"title\":\"裂碑夜雨\","
            "\"goal\":\"让主角卷入主线\","
            "\"core_conflict\":\"主角想置身事外，但黑市与门派同时逼近\","
            "\"turning_point\":\"主角首次看到残谱异动，无法继续旁观\","
            "\"character_progress\":[\"主角从隐忍观望转向主动调查\"],"
            "\"relationship_progress\":[\"主角与师妹建立最初信任\"],"
            "\"planned_loops\":[{\"loop_id\":\"loop-1\",\"title\":\"残谱异动\",\"summary\":\"残谱对主角血脉产生共鸣\",\"priority\":1,\"due_start_chapter\":1,\"due_end_chapter\":3,\"related_characters\":[\"主角\"],\"resolution_requirements\":[\"揭示血脉来源\"]}],"
            "\"closure_function\":\"抛出下一章钩子\""
            "}]"
            "}\n"
            "返回 JSON：{chapters:[{chapter_number, title, goal, core_conflict, turning_point,"
            " character_progress:string[], relationship_progress:string[], planned_loops:[{loop_id, title, summary, priority, due_start_chapter, due_end_chapter, related_characters:string[], resolution_requirements:string[]}], closure_function}]}"
        )

    def _build_story_arc_prompt(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        feedback: str,
        starting_chapter: int,
        chapter_count: int,
        existing_roadmap: list[ChapterRoadmapItem],
    ) -> str:
        """构造阶段弧线 prompt，先锁定整书分幕再细化章节。"""
        arc_count = self._infer_story_arc_count(chapter_count)
        existing_payload = [item.model_dump(mode="json") for item in existing_roadmap]
        return (
            "请先为这部长篇小说规划阶段弧线，再由后续步骤展开章节。"
            "必须保证长篇路线具有明显递进，不能把 80 章写成重复的调查与怀疑。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"世界观：{world.model_dump(mode='json')}\n"
            f"人物：{[item.model_dump(mode='json') for item in characters]}\n"
            f"已有章节：{existing_payload}\n"
            f"起始章节：{starting_chapter}\n"
            f"目标章数：{chapter_count}\n"
            f"建议阶段数量：{arc_count}\n"
            f"微调要求：{feedback or '无'}\n"
            "硬性规则：\n"
            "1. 必须先返回 4-8 个阶段弧线，每个阶段都要有起始建立、中段升级、末段转折或收束。\n"
            "2. 相邻阶段不能重复同一种主线功能；中后期必须出现世界格局升级、关系翻转或大线索回收。\n"
            "3. timeline_milestones 必须体现时间推进，不能长期停留在同一时点。\n"
            "4. main_progress、relationship_progress、loop_progress 都必须是 string[]。\n"
            "最小示例："
            "{"
            "\"story_arcs\":[{"
            "\"arc_number\":1,"
            "\"title\":\"血月旧案开启\","
            "\"purpose\":\"让主角卷入主线并建立江湖格局\","
            "\"start_chapter\":1,"
            "\"end_chapter\":12,"
            "\"main_progress\":[\"主角确认父母旧案与血月门有关\"],"
            "\"relationship_progress\":[\"主角与师妹建立互信\",\"主角对师兄生出疑心\"],"
            "\"loop_progress\":[\"残谱异动从暗示升级为明确线索\"],"
            "\"timeline_milestones\":[\"入秋初夜\",\"七日后血月再现\"],"
            "\"arc_climax\":\"主角第一次公开与敌对势力交锋\""
            "}]"
            "}\n"
            "返回 JSON：{story_arcs:[{arc_number, title, purpose, start_chapter, end_chapter,"
            " main_progress:string[], relationship_progress:string[], loop_progress:string[],"
            " timeline_milestones:string[], arc_climax}]}"
        )

    def _build_arc_chapter_prompt(
        self,
        *,
        intent: CreationIntent,
        variant: ConceptVariant,
        world: WorldBlueprint,
        characters: list[CharacterBlueprint],
        feedback: str,
        story_arc: StoryArcPlan,
        existing_roadmap: list[ChapterRoadmapItem],
    ) -> str:
        """构造单个阶段的章节展开 prompt，要求每章都发生状态变化。"""
        existing_payload = [item.model_dump(mode="json") for item in existing_roadmap]
        chapter_count = story_arc.end_chapter - story_arc.start_chapter + 1
        return (
            "请只展开当前阶段的章节，不要越界到其他阶段。"
            "必须让每章都发生新的状态变化，避免重复调查型章节。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"世界观：{world.model_dump(mode='json')}\n"
            f"人物：{[item.model_dump(mode='json') for item in characters]}\n"
            f"当前阶段：{story_arc.model_dump(mode='json')}\n"
            f"已生成章节：{existing_payload}\n"
            f"微调要求：{feedback or '无'}\n"
            "硬性规则：\n"
            "1. 每章至少推进主线事实、人物关系、线索状态、世界局势中的一项。\n"
            "2. 连续两章不能拥有相同 chapter_function。\n"
            "3. 不要连续多章只重复“调查 / 怀疑 / 追查 / 训练”而没有状态变化。\n"
            "4. character_progress、relationship_progress、new_reveals、status_shift 必须是 string[]。\n"
            "5. planned_loops 必须是对象数组，而不是线索标题字符串列表。\n"
            "6. timeline_anchor 必须持续递进。\n"
            "最小示例："
            "{"
            "\"chapters\":[{"
            "\"chapter_number\":1,"
            "\"title\":\"裂碑夜雨\","
            "\"story_stage\":\"血月旧案开启\","
            "\"timeline_anchor\":\"入秋初夜\","
            "\"depends_on_chapters\":[],"
            "\"goal\":\"让主角卷入主线\","
            "\"core_conflict\":\"主角想置身事外，但黑市与门派同时逼近\","
            "\"turning_point\":\"主角首次看到残谱异动，无法继续旁观\","
            "\"story_progress\":\"父母旧案与血月门第一次产生明确联系\","
            "\"character_progress\":[\"主角从隐忍观望转向主动调查\"],"
            "\"relationship_progress\":[\"主角与师妹建立最初信任\"],"
            "\"new_reveals\":[\"残谱会对主角血脉产生共鸣\"],"
            "\"status_shift\":[\"主角不再只是被动逃避\"],"
            "\"chapter_function\":\"开局\","
            "\"anti_repeat_signature\":\"血月旧案开启:卷入主线\","
            "\"planned_loops\":[{\"loop_id\":\"loop-1\",\"title\":\"残谱异动\",\"summary\":\"残谱对主角血脉产生共鸣\",\"priority\":1,\"due_start_chapter\":1,\"due_end_chapter\":3,\"related_characters\":[\"主角\"],\"resolution_requirements\":[\"揭示血脉来源\"]}],"
            "\"closure_function\":\"抛出下一章钩子\""
            "}]"
            "}\n"
            f"当前阶段需要展开 {chapter_count} 章。\n"
            "返回 JSON：{chapters:[{chapter_number, title, story_stage, timeline_anchor, depends_on_chapters:number[],"
            " goal, core_conflict, turning_point, story_progress, character_progress:string[],"
            " relationship_progress:string[], new_reveals:string[], status_shift:string[],"
            " chapter_function, anti_repeat_signature, planned_loops:[{loop_id, title, summary, priority,"
            " due_start_chapter, due_end_chapter, related_characters:string[], resolution_requirements:string[]}],"
            " closure_function}]}"
        )
