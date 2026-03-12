"""创作蓝图生成器：根据作者意图逐层扩写整书蓝图。"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    ConceptVariantFrame,
    CreationIntent,
    WorldBlueprint,
)
from poiesis.llm.base import LLMClient


class RoadmapPlanner:
    """负责候选方向、世界观、人物和章节路线的生成与重规划。"""

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
    ) -> ConceptVariant:
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
        regenerated = self._expand_variant_frame(
            intent,
            frame,
            llm,
            siblings=sibling_variants,
            force_diverge=True,
        )
        siblings_with_new = [*sibling_variants, regenerated]
        if self._find_similarity_issue(siblings_with_new) is not None:
            regenerated.diversity_note = "此版本与其他候选仍存在一定相似度，建议结合差异标签选择。"
        return regenerated

    def generate_world(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        llm: LLMClient,
        feedback: str = "",
    ) -> WorldBlueprint:
        """围绕已选候选方向扩写世界观蓝图。"""
        raw = llm.complete_json(
            self._build_world_prompt(intent, variant, feedback),
            system="你是资深世界观架构师。必须返回合法 JSON，并且所有内容适合长篇连载控制。",
        )
        return WorldBlueprint.model_validate(
            {
                "setting_summary": raw.get("setting_summary") or variant.world_pitch,
                "immutable_rules": raw.get("immutable_rules") or [],
                "power_system": raw.get("power_system") or "",
                "factions": raw.get("factions") or [],
                "taboo_rules": raw.get("taboo_rules") or [],
            }
        )

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
        items = raw.get("characters") or []
        if not isinstance(items, list) or not items:
            items = [
                {
                    "name": "主角",
                    "role": "主角",
                    "public_persona": "表面冷静，实则长期压抑自身欲望。",
                    "core_motivation": intent.protagonist_prompt or "摆脱既定命运",
                    "fatal_flaw": "不愿真正向他人求助",
                    "non_negotiable_traits": ["遇到大义问题时不会退缩"],
                    "relationship_constraints": ["与关键对象存在长期情感拉扯"],
                    "arc_outline": ["前期被动卷入", "中期主动承担", "后期以代价完成选择"],
                }
            ]
        return [CharacterBlueprint.model_validate(item) for item in items]

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
        """生成或重规划章节路线。"""
        raw = llm.complete_json(
            self._build_roadmap_prompt(
                intent,
                variant,
                world,
                characters,
                feedback,
                starting_chapter,
                chapter_count,
                existing_roadmap or [],
            ),
            system="你是长篇小说总编剧。必须返回合法 JSON，章节路线要能长期支撑后续 scene 细化。",
        )
        items = raw.get("chapters") or []
        if not isinstance(items, list) or not items:
            items = [
                {
                    "chapter_number": chapter_no,
                    "title": f"第 {chapter_no} 章",
                    "goal": "推进主线",
                    "core_conflict": "外部压力逼近",
                    "turning_point": "主角必须做出选择",
                    "character_progress": ["主角认知发生变化"],
                    "planned_loops": [],
                    "closure_function": "制造下一章钩子",
                }
                for chapter_no in range(starting_chapter, starting_chapter + chapter_count)
            ]
        return [ChapterRoadmapItem.model_validate(item) for item in items]

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
    ) -> ConceptVariant:
        """把单条骨架扩写成完整候选方向。"""
        raw = llm.complete_json(
            self._build_variant_expansion_prompt(intent, frame, siblings or [], force_diverge=force_diverge),
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
                if text_score >= 0.70 or structure_overlap >= 3:
                    score = text_score + structure_overlap / 10
                    if score > worst_score:
                        worst_score = score
                        worst_index = right
        if worst_index is None:
            return None
        return {"target_index": worst_index}

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
    ) -> str:
        sibling_payload = [item.model_dump(mode="json") for item in siblings]
        diverge_rule = (
            "你必须显式避开已有候选版本的世界结构、核心冲突来源、主角弧线和结局类型。"
            if force_diverge
            else "请保持与其他轨道的清晰区分。"
        )
        return (
            "请把以下候选方向骨架扩写成一版完整的整书候选方向。"
            "必须保留骨架中的分歧标签，并让作者一眼看出它与其他版本不同。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"当前骨架：{frame.model_dump(mode='json')}\n"
            f"已有候选：{sibling_payload}\n"
            f"差异要求：{diverge_rule}\n"
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

    def _build_world_prompt(
        self,
        intent: CreationIntent,
        variant: ConceptVariant,
        feedback: str,
    ) -> str:
        return (
            "请基于作者意图和已选候选方向，扩写一个可长期使用的世界观蓝图。\n"
            f"作者意图：{intent.model_dump(mode='json')}\n"
            f"候选方向：{variant.model_dump(mode='json')}\n"
            f"微调要求：{feedback or '无'}\n"
            "返回 JSON：{setting_summary, immutable_rules:[{key, description, is_immutable, category}],"
            " power_system, factions, taboo_rules}"
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
            "返回 JSON：{characters:[{name, role, public_persona, core_motivation, fatal_flaw,"
            " non_negotiable_traits, relationship_constraints, arc_outline}]}"
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
            "返回 JSON：{chapters:[{chapter_number, title, goal, core_conflict, turning_point,"
            " character_progress, planned_loops, closure_function}]}"
        )
