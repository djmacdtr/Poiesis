"""创作蓝图生成器：根据作者意图逐层扩写整书蓝图。"""

from __future__ import annotations

from typing import Any

from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    CreationIntent,
    WorldBlueprint,
)
from poiesis.llm.base import LLMClient


class RoadmapPlanner:
    """负责候选方向、世界观、人物和章节路线的生成与重规划。"""

    def generate_concept_variants(self, intent: CreationIntent, llm: LLMClient) -> list[ConceptVariant]:
        """根据作者高层意图生成 3 版差异化候选方向。"""
        raw = llm.complete_json(
            self._build_concept_prompt(intent),
            system=(
                "你是资深小说总策划。必须返回合法 JSON。"
                "请生成 3 版差异明显但都可长期展开的创作方向。"
            ),
        )
        variants = raw.get("variants")
        if not isinstance(variants, list) or not variants:
            variants = [
                {
                    "variant_no": 1,
                    "hook": f"{intent.genre or '长篇小说'}的命运开局",
                    "world_pitch": f"围绕“{intent.conflict_prompt or intent.themes[:1] or '核心冲突'}”展开的世界。",
                    "main_arc_pitch": "主角被迫卷入更大的秩序与个人命运冲突中。",
                    "ending_pitch": intent.ending_preference or "苦乐参半的完成式结局。",
                    "differentiators": ["主线张力突出", "人物成长路线清晰"],
                },
                {
                    "variant_no": 2,
                    "hook": f"{intent.genre or '长篇小说'}的双线对照开局",
                    "world_pitch": "世界表层秩序稳定，深层结构正在崩坏。",
                    "main_arc_pitch": "主角的个人选择与更大历史进程互相牵连。",
                    "ending_pitch": intent.ending_preference or "在失去中获得新的秩序。",
                    "differentiators": ["伏笔空间更大", "群像更强"],
                },
                {
                    "variant_no": 3,
                    "hook": f"{intent.genre or '长篇小说'}的极端困局开局",
                    "world_pitch": "一开始就存在高压环境与必须被揭开的真相。",
                    "main_arc_pitch": "主角被逼着在情感与使命之间长期拉扯。",
                    "ending_pitch": intent.ending_preference or "高代价但完成宿命闭环。",
                    "differentiators": ["开局钩子最强", "情绪波动更剧烈"],
                },
            ]
        return [
            ConceptVariant.model_validate(
                {
                    "variant_no": index,
                    "hook": item.get("hook") or f"候选方向 {index}",
                    "world_pitch": item.get("world_pitch") or "",
                    "main_arc_pitch": item.get("main_arc_pitch") or "",
                    "ending_pitch": item.get("ending_pitch") or "",
                    "differentiators": item.get("differentiators") or [],
                }
            )
            for index, item in enumerate(variants[:3], start=1)
        ]

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

    def _build_concept_prompt(self, intent: CreationIntent) -> str:
        return (
            "请根据以下作者创作意图，生成 3 版风格和主线明显不同的整书候选方向。\n"
            f"题材：{intent.genre}\n"
            f"主题：{', '.join(intent.themes)}\n"
            f"目标体验：{intent.target_experience}\n"
            f"主角提示：{intent.protagonist_prompt}\n"
            f"核心冲突：{intent.conflict_prompt}\n"
            f"结局倾向：{intent.ending_preference}\n"
            f"禁用元素：{', '.join(intent.forbidden_elements)}\n"
            f"篇幅偏好：{intent.length_preference}\n"
            "返回 JSON：{variants:[{variant_no, hook, world_pitch, main_arc_pitch, ending_pitch, differentiators}]}"
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

