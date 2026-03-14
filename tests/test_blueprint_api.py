"""创作蓝图工作台 API 测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.application.blueprint_contracts import (
    ChapterRoadmapItem,
    CharacterBlueprint,
    ConceptVariant,
    CreationIntent,
    StoryArcPlan,
    WorldBlueprint,
)
from poiesis.application.blueprint_use_cases import (
    BlueprintContext,
    PlanCreativeRepairsUseCase,
    ReverifyCreativeIssuesUseCase,
    build_book_blueprint,
)
from poiesis.application.creative_orchestrator import CreativeOrchestrator
from poiesis.db.database import Database
from poiesis.llm.base import LLMClient
from poiesis.pipeline.planning.roadmap_planner import RoadmapPlanner
from tests.conftest import MockLLMClient


def _make_client(tmp_db: Database) -> TestClient:
    from poiesis.api import deps

    app.dependency_overrides[deps.get_db] = lambda: tmp_db
    app.dependency_overrides[deps.require_admin] = lambda: {
        "sub": "1",
        "username": "test_admin",
        "role": "admin",
    }
    return TestClient(app, raise_server_exceptions=True)


class _SequencedJsonLLM(LLMClient):
    """按顺序返回 JSON，用于验证候选方向的自动回炉。"""

    def __init__(self, responses: list[dict[str, object]]) -> None:
        super().__init__(model="mock", temperature=0.0, max_tokens=100)
        self._responses = responses

    def _complete(self, prompt: str, system: str | None = None, **kwargs):  # noqa: ANN001, ARG002
        return ""

    def _complete_json(self, prompt: str, system: str | None = None, **kwargs):  # noqa: ANN001, ARG002
        if not self._responses:
            return {}
        return self._responses.pop(0)

    def _stream_complete(self, prompt: str, system: str | None = None, **kwargs):  # noqa: ANN001, ARG002
        yield ""


def test_roadmap_planner_regenerates_similar_variant() -> None:
    """候选方向若过于相似，应自动回炉并拉开核心驱动差异。"""
    planner = RoadmapPlanner()
    llm = _SequencedJsonLLM(
        [
            {
                "frames": [
                    {
                        "variant_no": 1,
                        "variant_strategy": "江湖人物局",
                        "core_driver": "人物驱动",
                        "conflict_source": "师门与私仇",
                        "world_structure": "单江湖",
                        "protagonist_arc_mode": "复仇",
                        "tone_signature": "肃杀",
                        "ending_mode": "代价胜利",
                        "differentiators": ["人物关系"],
                    },
                    {
                        "variant_no": 2,
                        "variant_strategy": "门派秩序局",
                        "core_driver": "世界驱动",
                        "conflict_source": "门派秩序崩坏",
                        "world_structure": "双秩序",
                        "protagonist_arc_mode": "守护",
                        "tone_signature": "厚重",
                        "ending_mode": "新秩序",
                        "differentiators": ["世界格局"],
                    },
                    {
                        "variant_no": 3,
                        "variant_strategy": "真相追查局",
                        "core_driver": "悬疑驱动",
                        "conflict_source": "旧案阴谋",
                        "world_structure": "暗网江湖",
                        "protagonist_arc_mode": "破局",
                        "tone_signature": "冷峻",
                        "ending_mode": "真相代价",
                        "differentiators": ["谜案追查"],
                    },
                ]
            },
            {
                "hook": "少年剑客误入风暴",
                "world_pitch": "同一座江湖被旧秩序支配。",
                "main_arc_pitch": "主角被迫在追查真相与守护关系之间摇摆。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "师门与私仇",
                "world_structure": "单江湖",
                "protagonist_arc_mode": "复仇",
                "tone_signature": "肃杀",
                "variant_strategy": "江湖人物局",
                "differentiators": ["人物关系"],
            },
            {
                "hook": "少年剑客误入风暴",
                "world_pitch": "同一座江湖被旧秩序支配。",
                "main_arc_pitch": "主角被迫在追查真相与守护关系之间摇摆。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "师门与私仇",
                "world_structure": "单江湖",
                "protagonist_arc_mode": "复仇",
                "tone_signature": "肃杀",
                "variant_strategy": "门派秩序局",
                "differentiators": ["世界格局"],
            },
            {
                "hook": "少年剑客误入风暴",
                "world_pitch": "同一座江湖被旧秩序支配。",
                "main_arc_pitch": "主角被迫在追查真相与守护关系之间摇摆。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "师门与私仇",
                "world_structure": "单江湖",
                "protagonist_arc_mode": "复仇",
                "tone_signature": "肃杀",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案追查"],
            },
            {
                "hook": "诸门并立，旧规将崩",
                "world_pitch": "多门派并立的双层江湖秩序被旧规与新势力同时撕裂。",
                "main_arc_pitch": "主角从旁观者被推到秩序裂缝中央，被迫决定守哪一边的江湖。",
                "ending_pitch": "新秩序",
                "core_driver": "世界驱动",
                "conflict_source": "门派秩序崩坏",
                "world_structure": "双秩序",
                "protagonist_arc_mode": "守护",
                "tone_signature": "厚重",
                "variant_strategy": "门派秩序局",
                "differentiators": ["世界格局", "阵营对抗"],
            },
            {
                "hook": "江湖旧案撕开暗网",
                "world_pitch": "表层江湖平静，暗网江湖以旧案牵动各方势力。",
                "main_arc_pitch": "主角从追查真相走向承担真相代价，并被迫与隐秘组织周旋。",
                "ending_pitch": "真相代价",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案阴谋",
                "world_structure": "暗网江湖",
                "protagonist_arc_mode": "破局",
                "tone_signature": "冷峻",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案追查", "层层揭晓"],
            },
        ]
    )

    variants = planner.generate_concept_variants(
        CreationIntent(
            genre="武侠",
            themes=["成长", "背叛"],
            tone="悲怆",
            protagonist_prompt="少年剑客",
            conflict_prompt="追查灭门真相",
            ending_preference="高代价完成",
            forbidden_elements=["系统流"],
            length_preference="12",
            target_experience="起伏跌宕",
            variant_preference="尽量风格拉开",
        ),
        llm,
    )

    assert len(variants) == 3
    assert len({item.core_driver for item in variants}) == 3
    assert variants[1].core_driver == "世界驱动"
    assert variants[2].core_driver == "悬疑驱动"
    assert variants[2].hook == "江湖旧案撕开暗网"


def test_roadmap_planner_generate_world_accepts_rich_structure() -> None:
    """世界观生成应直接接受富结构 JSON，而不是再退回扁平字符串。"""
    planner = RoadmapPlanner()
    llm = _SequencedJsonLLM(
        [
            {
                "setting_summary": "乱世武林被裂开的旧秩序与新禁忌共同塑形。",
                "era_context": "王朝式微、江湖诸派争衡。",
                "social_order": "门派、镖局与地方豪强共同维系表层平衡。",
                "geography": [
                    {"name": "天机峡", "role": "禁地", "description": "传说中埋有旧时代的机关残卷。"},
                ],
                "power_system": {
                    "core_mechanics": "以真气为骨、机关为辅，二者可短暂共鸣。",
                    "costs": ["强行催动会折损经脉"],
                    "limitations": ["只有具备对应血脉者才能承载机关共鸣"],
                    "advancement_path": ["炼体", "化气", "合鸣"],
                    "symbols": ["裂纹玉牌"],
                },
                "factions": [
                    {
                        "name": "天机阁",
                        "position": "隐秘秩序维护者",
                        "goal": "封存旧时代机关术",
                        "methods": ["暗线监控", "收拢秘卷"],
                        "public_image": "避世门派",
                        "hidden_truth": "长期操盘江湖均势",
                    }
                ],
            },
            {
                "immutable_rules": [
                    {
                        "key": "血脉共鸣",
                        "description": "机关术必须以特定血脉激活。",
                        "category": "power",
                        "rationale": "维持力量稀缺性",
                        "is_immutable": True,
                    }
                ],
                "taboo_rules": [
                    {
                        "key": "逆转经脉",
                        "description": "逆行真气强开机关术。",
                        "consequence": "会迅速损毁经脉并招致失控。",
                        "is_immutable": True,
                    }
                ],
                "historical_wounds": ["百年前天机阁内乱导致武林大洗牌"],
                "public_secrets": ["各门派都知道天机阁曾经主持过一次大清洗"],
            },
        ]
    )

    world = planner.generate_world(
        intent=CreationIntent(
            genre="武侠",
            themes=["成长", "禁忌"],
            tone="压抑",
            protagonist_prompt="身负机关血脉的少年",
            conflict_prompt="追查父母之死与旧时代机关术",
            ending_preference="高代价真相",
            forbidden_elements=["系统流"],
            length_preference="12",
            target_experience="层层揭晓",
            variant_preference="世界差异优先",
        ),
        variant=ConceptVariant(
            variant_no=1,
            hook="旧案重启",
            world_pitch="暗网江湖浮出水面。",
            main_arc_pitch="主角在真相与秩序之间选择。",
            ending_pitch="高代价真相",
            variant_strategy="真相追查局",
            core_driver="悬疑驱动",
            conflict_source="旧案阴谋",
            world_structure="暗网江湖",
            protagonist_arc_mode="破局",
            tone_signature="冷峻",
            differentiators=["谜案推进"],
            diversity_note="",
        ),
        llm=llm,
        feedback="更强调机关血脉与武学共鸣",
    )

    assert world.power_system.core_mechanics
    assert world.factions[0].name == "天机阁"
    assert world.immutable_rules[0].key == "血脉共鸣"
    assert world.taboo_rules[0].consequence


def test_roadmap_planner_generate_world_normalizes_string_lists() -> None:
    """世界观归一化应容忍字符串型列表字段和单对象字段。"""
    planner = RoadmapPlanner()
    llm = _SequencedJsonLLM(
        [
            {
                "setting_summary": "江湖分裂，旧门规与暗网交易并行。",
                "era_context": "王朝崩坏后的群雄割据时代。",
                "social_order": "门派、镖局与地方豪强共同维持表层稳定。",
                "historical_wounds": "天机阁血案；边城屠门",
                "public_secrets": "旧机关谱重现，黑市在争抢残页",
                "geography": {
                    "name": "断潮关",
                    "role": "边境要冲",
                    "description": "多方势力长期争夺的交通隘口",
                },
                "factions": {
                    "name": "铁衣盟",
                    "position": "边地新兴势力",
                    "goal": "垄断黑市与边贸",
                    "methods": "暗桩渗透，悬赏追捕、收编败军",
                    "public_image": "护商义盟",
                    "hidden_truth": "以战养商，操控边贸命脉",
                },
            },
            {
                "power_system": {
                    "core_mechanics": "真气与机关术短暂共鸣后会引发反噬。",
                    "costs": "经脉折损；寿命缩减",
                    "limitations": "必须持有残谱；血脉适配者优先",
                    "advancement_path": "炼体、聚气、合鸣",
                    "symbols": "裂纹玉符，机关残页",
                },
                "immutable_rules": {
                    "key": "残谱共鸣",
                    "description": "机关残谱只能由适配血脉激活。",
                    "category": "power",
                    "rationale": "维持力量稀缺性",
                    "is_immutable": True,
                },
                "taboo_rules": {
                    "key": "逆转合鸣",
                    "description": "逆行真气强行驱动机关残谱。",
                    "consequence": "经脉崩坏并诱发走火入魔",
                    "is_immutable": True,
                },
            },
        ]
    )

    world = planner.generate_world(
        intent=CreationIntent(
            genre="武侠",
            themes=["成长", "禁忌"],
            tone="冷峻",
            protagonist_prompt="被卷入旧案的少年剑客",
            conflict_prompt="黑市与门派争夺失落机关谱",
            ending_preference="代价胜利",
            forbidden_elements=["系统流"],
            length_preference="12",
            target_experience="层层揭晓",
            variant_preference="世界差异优先",
        ),
        variant=ConceptVariant(
            variant_no=1,
            hook="断潮关旧案重启",
            world_pitch="江湖与黑市秩序同时失衡。",
            main_arc_pitch="主角在旧案追查中被迫介入新旧势力之争。",
            ending_pitch="代价胜利",
            variant_strategy="真相追查局",
            core_driver="悬疑驱动",
            conflict_source="旧案阴谋",
            world_structure="暗网江湖",
            protagonist_arc_mode="破局",
            tone_signature="冷峻",
            differentiators=["黑市暗网"],
            diversity_note="",
        ),
        llm=llm,
    )

    assert world.historical_wounds == ["天机阁血案", "边城屠门"]
    assert world.public_secrets == ["旧机关谱重现", "黑市在争抢残页"]
    assert world.geography[0].name == "断潮关"
    assert world.factions[0].methods == ["暗桩渗透", "悬赏追捕", "收编败军"]
    assert world.power_system.costs == ["经脉折损", "寿命缩减"]
    assert world.power_system.limitations == ["必须持有残谱", "血脉适配者优先"]
    assert world.power_system.advancement_path == ["炼体", "聚气", "合鸣"]
    assert world.power_system.symbols == ["裂纹玉符", "机关残页"]
    assert world.immutable_rules[0].key == "残谱共鸣"
    assert world.taboo_rules[0].key == "逆转合鸣"


def test_roadmap_planner_generate_characters_normalizes_string_lists() -> None:
    """人物蓝图归一化应容忍字符串型列表字段。"""
    planner = RoadmapPlanner()
    llm = _SequencedJsonLLM(
        [
            {
                "characters": {
                    "name": "沈砚",
                    "role": "主角",
                    "public_persona": "冷静寡言的落魄少年",
                    "core_motivation": "追查父母真相",
                    "fatal_flaw": "执念过重",
                    "non_negotiable_traits": "嘴硬心软；遇到大义不会退缩",
                    "relationship_constraints": "对师父始终保留戒心、与师兄既竞争又依赖",
                    "arc_outline": "前期被动卷入；中期主动追查；后期承担代价完成选择",
                }
            }
        ]
    )

    characters = planner.generate_characters(
        intent=CreationIntent(
            genre="武侠",
            themes=["成长", "背叛"],
            tone="冷峻",
            protagonist_prompt="落魄少年",
            conflict_prompt="追查父母之死",
            ending_preference="代价胜利",
            forbidden_elements=["系统流"],
            length_preference="12",
            target_experience="层层揭晓",
            variant_preference="人物差异优先",
        ),
        variant=ConceptVariant(
            variant_no=1,
            hook="旧案重启",
            world_pitch="暗网江湖浮出水面。",
            main_arc_pitch="主角在真相与秩序之间选择。",
            ending_pitch="代价胜利",
            variant_strategy="真相追查局",
            core_driver="悬疑驱动",
            conflict_source="旧案阴谋",
            world_structure="暗网江湖",
            protagonist_arc_mode="破局",
            tone_signature="冷峻",
            differentiators=["谜案推进"],
            diversity_note="",
        ),
        world=WorldBlueprint(setting_summary="暗网江湖浮出水面。"),
        llm=llm,
    )

    assert len(characters) == 1
    assert characters[0].non_negotiable_traits == ["嘴硬心软", "遇到大义不会退缩"]
    assert characters[0].relationship_constraints == ["对师父始终保留戒心", "与师兄既竞争又依赖"]
    assert characters[0].arc_outline == ["前期被动卷入", "中期主动追查", "后期承担代价完成选择"]


def test_roadmap_planner_generate_relationships_normalizes_enum_fields() -> None:
    """人物关系边归一化应兼容英文枚举、半结构强度和文本布尔值。"""
    planner = RoadmapPlanner()
    llm = _SequencedJsonLLM(
        [
            {
                "relationships": {
                    "edge_id": "rel-1",
                    "source_character_id": "沈砚",
                    "target_character_id": "陆行川",
                    "relation_type": "师徒",
                    "polarity": "positive",
                    "visibility": "public",
                    "stability": "high",
                    "intensity": "4",
                    "summary": "名义师徒，实则相互试探。",
                    "hidden_truth": "师父隐瞒了旧案真相。",
                    "non_breakable_without_reveal": "required",
                }
            }
        ]
    )

    edges = planner.generate_relationship_graph(
        intent=CreationIntent(
            genre="武侠",
            themes=["成长", "背叛"],
            tone="冷峻",
            protagonist_prompt="落魄少年",
            conflict_prompt="追查父母之死",
            ending_preference="代价胜利",
            forbidden_elements=["系统流"],
            length_preference="12",
            target_experience="层层揭晓",
            variant_preference="人物差异优先",
        ),
        variant=ConceptVariant(
            variant_no=1,
            hook="旧案重启",
            world_pitch="暗网江湖浮出水面。",
            main_arc_pitch="主角在真相与秩序之间选择。",
            ending_pitch="代价胜利",
            variant_strategy="真相追查局",
            core_driver="悬疑驱动",
            conflict_source="旧案阴谋",
            world_structure="暗网江湖",
            protagonist_arc_mode="破局",
            tone_signature="冷峻",
            differentiators=["谜案推进"],
            diversity_note="",
        ),
        world=WorldBlueprint(setting_summary="暗网江湖浮出水面。"),
        characters=[
            CharacterBlueprint(
                name="沈砚",
                role="主角",
                public_persona="冷静寡言的落魄少年",
                core_motivation="追查真相",
                fatal_flaw="执念过重",
                non_negotiable_traits=["不愿退缩"],
                relationship_constraints=["与师父彼此试探"],
                arc_outline=["前期卷入", "中期追查", "后期承担代价"],
            ),
            CharacterBlueprint(
                name="陆行川",
                role="师父",
                public_persona="表面冷静的隐世剑客",
                core_motivation="压住旧案余波",
                fatal_flaw="习惯隐瞒真相",
                non_negotiable_traits=["不轻易表露软弱"],
                relationship_constraints=["对主角既保护又设防"],
                arc_outline=["前期试探", "中期让位", "后期揭示真相"],
            ),
        ],
        llm=llm,
    )

    assert len(edges) == 1
    assert edges[0].polarity == "正向"
    assert edges[0].visibility == "公开"
    assert edges[0].stability == "稳定"
    assert edges[0].intensity == 4
    assert edges[0].non_breakable_without_reveal is True


def test_roadmap_planner_generate_roadmap_normalizes_half_structured_payload() -> None:
    """章节路线归一化应兼容字符串推进字段和字符串型线索列表。"""
    planner = RoadmapPlanner()
    llm = _SequencedJsonLLM(
        [
            {
                "chapters": {
                    "chapter_number": "1",
                    "title": "裂碑夜雨",
                    "goal": "让主角卷入主线",
                    "core_conflict": "主角想置身事外，但门派与黑市都在逼近",
                    "turning_point": "主角首次看到残谱异动，无法继续旁观",
                    "character_progress": "林寒第一次主动追查父母之死；苏璃开始意识到门内有人隐瞒真相",
                    "relationship_progress": "林寒与苏璃建立初步信任、林寒开始怀疑赵无极的真实立场",
                    "planned_loops": ["残谱异动", "天机令纹路闪现"],
                    "closure_function": "抛出下一章钩子",
                }
            }
        ]
    )

    roadmap = planner.generate_roadmap(
        intent=CreationIntent(
            genre="武侠",
            themes=["成长", "背叛"],
            tone="冷峻",
            protagonist_prompt="被卷入旧案的少年",
            conflict_prompt="追查父母之死与机关残谱",
            ending_preference="代价胜利",
            forbidden_elements=["系统流"],
            length_preference="12",
            target_experience="层层揭晓",
            variant_preference="世界差异优先",
        ),
        variant=ConceptVariant(
            variant_no=1,
            hook="裂碑夜雨",
            world_pitch="表层江湖平静，暗网秩序暗流涌动。",
            main_arc_pitch="主角在旧案追查中不断被迫介入各方势力的博弈。",
            ending_pitch="代价胜利",
            variant_strategy="真相追查局",
            core_driver="悬疑驱动",
            conflict_source="旧案阴谋",
            world_structure="暗网江湖",
            protagonist_arc_mode="破局",
            tone_signature="冷峻",
            differentiators=["谜案推进"],
            diversity_note="",
        ),
        world=WorldBlueprint(setting_summary="暗网江湖浮出水面。"),
        characters=[
            CharacterBlueprint(
                name="林寒",
                role="主角",
                public_persona="冷静寡言的少年",
                core_motivation="追查父母真相",
                fatal_flaw="执念过重",
                non_negotiable_traits=["不会轻易退缩"],
                relationship_constraints=["对师门保持警惕"],
                arc_outline=["前期卷入", "中期追查", "后期承担代价"],
            ),
            CharacterBlueprint(
                name="苏璃",
                role="师妹",
                public_persona="活泼却敏锐",
                core_motivation="守住师门",
                fatal_flaw="过度保护",
                non_negotiable_traits=["关键时刻会站到主角身边"],
                relationship_constraints=["与主角逐步建立信任"],
                arc_outline=["前期陪伴", "中期动摇", "后期共同承担"],
            ),
        ],
        llm=llm,
        chapter_count=1,
    )

    assert len(roadmap) == 1
    assert roadmap[0].character_progress == ["林寒第一次主动追查父母之死", "苏璃开始意识到门内有人隐瞒真相"]
    assert roadmap[0].relationship_progress == ["林寒与苏璃建立初步信任", "林寒开始怀疑赵无极的真实立场"]
    assert roadmap[0].planned_loops[0].title == "残谱异动"
    assert roadmap[0].planned_loops[0].due_start_chapter == 1
    assert roadmap[0].planned_loops[1].loop_id == "chapter-1-loop-2"


def test_arc_last_chapter_regenerate_api_returns_updated_blueprint(tmp_db: Database, monkeypatch) -> None:
    """末章重生成接口应返回更新后的路线草稿。"""
    from poiesis.api.services import blueprint_service

    book_id = tmp_db.create_book("阶段重生成测试", "zh-CN", "literary_cn", "", "localized_zh")
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="roadmap_ready",
        current_step="roadmap",
        story_arcs_draft=[
            {
                "arc_number": 1,
                "title": "第一幕",
                "purpose": "主角卷入旧案",
                "start_chapter": 1,
                "end_chapter": 3,
                "main_progress": ["主角接触旧案"],
                "relationship_progress": ["与师妹建立初步信任"],
                "loop_progress": ["残谱异动"],
                "timeline_milestones": ["初夜"],
                "arc_climax": "旧案第一次暴露",
            }
        ],
        roadmap_draft=[
            {
                "chapter_number": 1,
                "title": "旧案初现",
                "story_stage": "第一幕",
                "timeline_anchor": "初夜",
                "depends_on_chapters": [],
                "goal": "卷入旧案",
                "core_conflict": "主角想躲，但线索逼近",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次接触旧案",
                "character_progress": ["林寒被迫入局"],
                "relationship_progress": ["与苏璃建立初步信任"],
                "new_reveals": ["残谱并未失传"],
                "status_shift": ["主角不再只是旁观者"],
                "planned_loops": [
                    {
                        "title": "残谱异动",
                        "summary": "残谱第一次异动，提示旧案仍在暗处发酵。",
                        "status": "open",
                        "due_end_chapter": 3,
                    }
                ],
                "chapter_function": "开局",
                "anti_repeat_signature": "卷入旧案",
                "closure_function": "抛出钩子",
            }
        ],
        roadmap_validation_issues=[],
    )

    def _fake_regenerate(
        db: Database,
        config_path: str,
        target_book_id: int,
        arc_number: int,
        chapter_number: int,
        feedback: str = "",
    ):
        assert target_book_id == book_id
        assert arc_number == 1
        assert chapter_number == 1
        assert "升级" in feedback
        tmp_db.upsert_book_blueprint_state(
            book_id,
            status="roadmap_ready",
            current_step="roadmap",
            story_arcs_draft=[
                {
                    "arc_number": 1,
                    "title": "第一幕：局势升级",
                    "purpose": "主角卷入旧案并被迫面对更大局势",
                    "start_chapter": 1,
                    "end_chapter": 3,
                    "main_progress": ["主角接触旧案", "局势明确升级"],
                    "relationship_progress": ["与师妹从试探转为并肩"],
                    "loop_progress": ["残谱异动", "天机阁暗线浮出"],
                    "timeline_milestones": ["初夜", "次日拂晓"],
                    "arc_climax": "第一幕结尾形成局势反转",
                }
            ],
            roadmap_draft=[
                {
                    "chapter_number": 1,
                    "title": "局势骤变",
                    "story_stage": "第一幕：局势升级",
                    "timeline_anchor": "次日拂晓",
                    "depends_on_chapters": [],
                    "goal": "让局势快速升级",
                    "core_conflict": "旧案背后势力主动出手",
                    "turning_point": "天机阁暗线暴露",
                    "story_progress": "旧案正式升级为江湖势力冲突",
                    "character_progress": ["林寒第一次主动反击"],
                    "relationship_progress": ["与苏璃形成并肩关系"],
                    "new_reveals": ["幕后势力来自天机阁"],
                    "status_shift": ["主角不再被动应对"],
                    "planned_loops": [
                        {
                            "title": "天机阁暗线",
                            "summary": "暗线第一次显形，提示天机阁已介入旧案。",
                            "status": "open",
                            "due_end_chapter": 3,
                        }
                    ],
                    "chapter_function": "升级",
                    "anti_repeat_signature": "局势升级",
                    "closure_function": "推动进入下一章",
                }
            ],
            roadmap_validation_issues=[],
        )
        return build_book_blueprint(tmp_db, book_id)

    monkeypatch.setattr(blueprint_service, "regenerate_arc_chapter", _fake_regenerate)
    client = _make_client(tmp_db)

    response = client.post(
        f"/api/books/{book_id}/blueprint/story-arcs/1/chapters/1:regenerate",
        json={"feedback": "请让第一幕更早出现局势升级"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_arcs_draft"][0]["title"] == "第一幕：局势升级"
    assert payload["roadmap_draft"][0]["chapter_function"] == "升级"
    assert payload["roadmap_validation_issues"][0]["suggested_action"] == "generate_next_chapter"


def test_blueprint_creation_flow_can_lock_book_blueprint(tmp_db: Database, monkeypatch) -> None:
    """从创作意图到整书蓝图锁定，应形成完整的工作流。"""
    from poiesis.api.services import blueprint_service

    class _BlueprintFlowLLM(MockLLMClient):
        def _complete_json(self, prompt: str, system: str | None = None, **kwargs: object) -> dict[str, object]:  # noqa: ARG002
            if "返回 JSON：{chapter:" in prompt:
                chapter_no = 1
                for token in prompt.splitlines():
                    if "目标章号：第 " in token:
                        chapter_no = int(token.split("目标章号：第 ", 1)[1].split(" 章", 1)[0])
                        break
                stage = "第 1 幕"
                for token in prompt.splitlines():
                    if token.startswith("当前阶段："):
                        if '"title":' in token:
                            stage = token.split('"title": "', 1)[1].split('"', 1)[0]
                        break
                return {
                    "chapter": {
                        "chapter_number": chapter_no,
                        "title": f"第 {chapter_no} 章",
                        "story_stage": stage,
                        "timeline_anchor": f"第 {chapter_no} 日",
                        "depends_on_chapters": [] if chapter_no == 1 else [chapter_no - 1],
                        "goal": f"推进第 {chapter_no} 章主线",
                        "core_conflict": f"第 {chapter_no} 章外部压力逼近",
                        "turning_point": f"第 {chapter_no} 章出现新的转折",
                        "story_progress": f"第 {chapter_no} 章主线发生新变化",
                        "key_events": [f"第 {chapter_no} 章关键事件"],
                        "chapter_tasks": [
                            {
                                "task_id": f"chapter-task-{chapter_no}",
                                "summary": f"第 {chapter_no} 章局部任务",
                                "status": "new",
                                "related_characters": [],
                                "due_end_chapter": chapter_no + 100,
                            }
                        ],
                        "character_progress": [f"角色在第 {chapter_no} 章发生变化"],
                        "relationship_beats": [
                            {
                                "source_character": "主角",
                                "target_character": "师妹",
                                "summary": f"第 {chapter_no} 章关系推进",
                            }
                        ],
                        "relationship_progress": [f"关系在第 {chapter_no} 章前进"],
                        "new_reveals": [f"第 {chapter_no} 章揭示新信息"],
                        "world_updates": [f"第 {chapter_no} 章世界局势更新"],
                        "status_shift": [f"第 {chapter_no} 章局势变化"],
                        "chapter_function": "推进" if chapter_no % 2 else "揭示",
                        "anti_repeat_signature": f"chapter-{chapter_no}",
                        "planned_loops": [
                            {
                                "title": f"线索{chapter_no}",
                                "summary": f"第 {chapter_no} 章引入的新线索，要求在后续章节明确回收。",
                                "status": "resolved",
                                "due_end_chapter": chapter_no,
                            }
                        ],
                        "closure_function": "抛出下一章钩子",
                    }
                }
            return super()._complete_json(prompt, system=system, **kwargs)

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=_BlueprintFlowLLM(json_response={}),
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)

    created = client.post(
        "/api/books",
        json={
            "name": "蓝图测试作品",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "",
            "naming_policy": "localized_zh",
            "is_default": False,
        },
    )
    assert created.status_code == 200
    book_id = created.json()["id"]

    intent_resp = client.post(
        f"/api/books/{book_id}/creation-intent",
        json={
            "genre": "武侠",
            "themes": ["成长", "背叛"],
            "tone": "悲怆",
            "protagonist_prompt": "少年剑客",
            "conflict_prompt": "追查灭门真相",
            "ending_preference": "高代价完成",
            "forbidden_elements": ["系统流"],
            "length_preference": "12",
            "target_experience": "起伏跌宕",
        },
    )
    assert intent_resp.status_code == 200
    assert intent_resp.json()["current_step"] == "concept"

    concept_resp = client.post(f"/api/books/{book_id}/concept-variants:generate", json={})
    assert concept_resp.status_code == 200
    variants = concept_resp.json()["concept_variants"]
    assert len(variants) == 3
    assert variants[0]["core_driver"]
    assert variants[0]["variant_strategy"]

    variant_id = variants[0]["id"]
    select_resp = client.post(f"/api/books/{book_id}/concept-variants/{variant_id}/select", json={})
    assert select_resp.status_code == 200
    assert select_resp.json()["selected_variant_id"] == variant_id

    world_resp = client.post(
        f"/api/books/{book_id}/blueprint/world:generate",
        json={"feedback": "更偏江湖氛围"},
    )
    assert world_resp.status_code == 200
    assert world_resp.json()["status"] == "world_ready"

    confirm_world = client.post(f"/api/books/{book_id}/blueprint/world:confirm", json={})
    assert confirm_world.status_code == 200
    assert confirm_world.json()["status"] == "world_confirmed"

    char_resp = client.post(
        f"/api/books/{book_id}/blueprint/characters:generate",
        json={"feedback": "主角更复杂"},
    )
    assert char_resp.status_code == 200
    assert char_resp.json()["status"] == "characters_ready"

    confirm_char = client.post(f"/api/books/{book_id}/blueprint/characters:confirm", json={})
    assert confirm_char.status_code == 200
    assert confirm_char.json()["status"] == "characters_confirmed"

    story_arcs_resp = client.post(
        f"/api/books/{book_id}/blueprint/story-arcs:generate",
        json={"feedback": "前三章开局更强"},
    )
    assert story_arcs_resp.status_code == 200
    assert story_arcs_resp.json()["status"] == "story_arcs_ready"
    arc_numbers = [item["arc_number"] for item in story_arcs_resp.json()["story_arcs_draft"]]
    assert arc_numbers

    first_confirm = client.post(f"/api/books/{book_id}/blueprint/roadmap:confirm", json={})
    assert first_confirm.status_code == 400
    assert "仍有阶段未完成章节生成" in first_confirm.json()["detail"]

    for arc_number in arc_numbers:
        while True:
            expanded = client.post(
                f"/api/books/{book_id}/blueprint/story-arcs/{arc_number}:expand",
                json={"feedback": f"生成第 {arc_number} 幕下一章"},
            )
            assert expanded.status_code == 200
            if arc_number in expanded.json()["expanded_arc_numbers"]:
                break

    confirm_roadmap = client.post(f"/api/books/{book_id}/blueprint/roadmap:confirm", json={})
    assert confirm_roadmap.status_code == 200
    assert confirm_roadmap.json()["status"] == "locked"
    assert confirm_roadmap.json()["active_revision_id"] is not None

    detail = client.get(f"/api/books/{book_id}/blueprint")
    assert detail.status_code == 200
    assert detail.json()["roadmap_confirmed"]
    assert detail.json()["revisions"][0]["is_active"] is True


def test_world_generate_api_normalizes_rich_payload(tmp_db: Database, monkeypatch) -> None:
    """世界观生成接口应在 rich JSON 形状不稳定时仍返回规范化结果。"""
    from poiesis.api.services import blueprint_service

    llm = _SequencedJsonLLM(
        [
            {
                "setting_summary": "武林旧秩序正在裂解，边地黑市同步坐大。",
                "era_context": "王朝式微后的群雄割据时代。",
                "social_order": "门派与商会互相依赖却彼此提防。",
                "historical_wounds": "边城屠门；旧谱失窃",
                "public_secrets": "人人都知道黑市在追残谱",
                "geography": {
                    "name": "裂碑渡",
                    "role": "货物流转枢纽",
                    "description": "各方势力都试图控制的渡口",
                },
                "factions": {
                    "name": "渡口盟",
                    "position": "边地商武共同体",
                    "goal": "控制渡口和残谱流向",
                    "methods": "收买、渗透；雇佣死士",
                    "public_image": "维持商路秩序",
                    "hidden_truth": "暗中替黑市洗白残谱交易",
                },
            },
            {
                "power_system": {
                    "core_mechanics": "残谱会放大持有者真气回路，但必须付出经脉代价。",
                    "costs": "经脉灼伤；真气紊乱",
                    "limitations": "需要残谱碎页、血脉承载",
                    "advancement_path": "炼体、凝脉、合谱",
                    "symbols": "残谱碎页；裂碑印记",
                },
                "immutable_rules": {
                    "key": "残谱承载",
                    "description": "残谱只能被少数适配者稳定承载。",
                    "category": "power",
                    "rationale": "限制力量泛滥",
                    "is_immutable": True,
                },
                "taboo_rules": {
                    "key": "燃脉催谱",
                    "description": "燃烧经脉强开残谱。",
                    "consequence": "短期爆发后迅速崩毁",
                    "is_immutable": True,
                },
            },
        ]
    )

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=llm,
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)

    created = client.post(
        "/api/books",
        json={
            "name": "世界观归一化接口测试",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "",
            "naming_policy": "localized_zh",
            "is_default": False,
        },
    )
    book_id = created.json()["id"]
    tmp_db.upsert_creation_intent(
        book_id,
        {
            "genre": "武侠",
            "themes": ["成长"],
            "tone": "冷峻",
            "protagonist_prompt": "少年剑客",
            "conflict_prompt": "追查残谱旧案",
            "ending_preference": "代价胜利",
            "forbidden_elements": [],
            "length_preference": "12",
            "target_experience": "层层揭晓",
            "variant_preference": "世界差异优先",
        },
    )
    tmp_db.replace_concept_variants(
        book_id,
        [
            {
                "variant_no": 1,
                "hook": "渡口旧案重启",
                "world_pitch": "武林旧秩序与黑市暗网同时失衡。",
                "main_arc_pitch": "主角在追查残谱时被迫卷入商武两界的角力。",
                "ending_pitch": "代价胜利",
                "variant_strategy": "真相追查局",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案阴谋",
                "world_structure": "暗网江湖",
                "protagonist_arc_mode": "破局",
                "tone_signature": "冷峻",
                "differentiators": ["黑市暗网"],
            }
        ],
    )
    variant_id = tmp_db.list_concept_variants(book_id)[0]["id"]
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="concept_selected",
        current_step="world",
        selected_variant_id=variant_id,
    )

    response = client.post(
        f"/api/books/{book_id}/blueprint/world:generate",
        json={"feedback": "更强调边地黑市与残谱代价"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "world_ready"
    world = payload["world_draft"]
    assert world["factions"][0]["methods"] == ["收买", "渗透", "雇佣死士"]
    assert world["power_system"]["costs"] == ["经脉灼伤", "真气紊乱"]
    assert world["historical_wounds"] == ["边城屠门", "旧谱失窃"]


def test_roadmap_generate_api_normalizes_half_structured_payload(tmp_db: Database, monkeypatch) -> None:
    """章节路线生成接口应在半结构 payload 下返回规范化后的正式结构。"""
    from poiesis.api.services import blueprint_service

    llm = _SequencedJsonLLM(
        [
            {
                "story_arcs": [
                    {
                        "arc_number": 1,
                        "title": "血月旧案开启",
                        "purpose": "让主角卷入主线并建立江湖格局",
                        "start_chapter": 1,
                        "end_chapter": 12,
                        "main_progress": "主角确认父母旧案与血月门有关",
                        "relationship_progress": "林寒与苏璃建立互信",
                        "loop_progress": ["残谱异动"],
                        "timeline_milestones": "入秋初夜；三日后",
                        "arc_climax": "主角第一次公开与敌对势力交锋",
                    }
                ]
            },
            {
                "chapters": [
                    {
                        "chapter_number": 1,
                        "title": "裂碑夜雨",
                        "story_stage": "血月旧案开启",
                        "timeline_anchor": "入秋初夜",
                        "depends_on_chapters": [],
                        "goal": "让主角卷入主线",
                        "core_conflict": "主角想置身事外，但黑市与师门都在逼近",
                        "turning_point": "主角第一次看见残谱异动",
                        "story_progress": "父母旧案与血月门第一次产生明确联系",
                        "character_progress": "林寒第一次主动追查父母之死；苏璃发现门内气氛异常",
                        "relationship_progress": "林寒与苏璃建立初步信任、林寒开始怀疑赵无极",
                        "new_reveals": "残谱会对主角血脉产生共鸣",
                        "status_shift": "主角不再只是被动逃避",
                        "chapter_function": "开局",
                        "anti_repeat_signature": "血月旧案开启:卷入主线",
                        "planned_loops": [
                            {
                                "title": "残谱异动",
                                "summary": "残谱第一次在主角面前异动，提示旧案仍在暗中发酵。",
                                "status": "open",
                                "due_end_chapter": 3,
                            },
                            {
                                "title": "天机令纹路闪现",
                                "summary": "天机令的纹路短暂显现，暗示幕后势力已提前介入。",
                                "status": "open",
                                "due_end_chapter": 6,
                            },
                        ],
                        "closure_function": "抛出下一章钩子",
                    }
                ]
            }
        ]
    )

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=llm,
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)

    created = client.post(
        "/api/books",
        json={
            "name": "章节路线归一化接口测试",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "",
            "naming_policy": "localized_zh",
            "is_default": False,
        },
    )
    book_id = created.json()["id"]
    tmp_db.upsert_creation_intent(
        book_id,
        {
            "genre": "武侠",
            "themes": ["成长"],
            "tone": "冷峻",
            "protagonist_prompt": "被卷入旧案的少年",
            "conflict_prompt": "追查父母之死与残谱",
            "ending_preference": "代价胜利",
            "forbidden_elements": [],
            "length_preference": "12",
            "target_experience": "层层揭晓",
            "variant_preference": "世界差异优先",
        },
    )
    tmp_db.replace_concept_variants(
        book_id,
        [
            {
                "variant_no": 1,
                "hook": "裂碑夜雨",
                "world_pitch": "表层江湖平静，暗网秩序暗流涌动。",
                "main_arc_pitch": "主角在旧案追查中不断被迫介入各方势力的博弈。",
                "ending_pitch": "代价胜利",
                "variant_strategy": "真相追查局",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案阴谋",
                "world_structure": "暗网江湖",
                "protagonist_arc_mode": "破局",
                "tone_signature": "冷峻",
                "differentiators": ["谜案推进"],
            }
        ],
    )
    variant_id = tmp_db.list_concept_variants(book_id)[0]["id"]
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="characters_confirmed",
        current_step="roadmap",
        selected_variant_id=variant_id,
        world_confirmed=WorldBlueprint(setting_summary="暗网江湖浮出水面。").model_dump(mode="json"),
        character_confirmed=[
            CharacterBlueprint(
                name="林寒",
                role="主角",
                public_persona="冷静寡言的少年",
                core_motivation="追查父母真相",
                fatal_flaw="执念过重",
                non_negotiable_traits=["不会轻易退缩"],
                relationship_constraints=["对师门保持警惕"],
                arc_outline=["前期卷入", "中期追查", "后期承担代价"],
            ).model_dump(mode="json"),
            CharacterBlueprint(
                name="苏璃",
                role="师妹",
                public_persona="活泼却敏锐",
                core_motivation="守住师门",
                fatal_flaw="过度保护",
                non_negotiable_traits=["关键时刻会站到主角身边"],
                relationship_constraints=["与主角逐步建立信任"],
                arc_outline=["前期陪伴", "中期动摇", "后期共同承担"],
            ).model_dump(mode="json"),
        ],
    )

    arcs_resp = client.post(
        f"/api/books/{book_id}/blueprint/story-arcs:generate",
        json={"feedback": "前三章开局更猛"},
    )

    assert arcs_resp.status_code == 200
    arcs_body = arcs_resp.json()
    assert arcs_body["story_arcs_draft"][0]["title"] == "血月旧案开启"
    assert arcs_body["expanded_arc_numbers"] == []
    assert arcs_body["roadmap_draft"] == []

    expand_resp = client.post(
        f"/api/books/{book_id}/blueprint/story-arcs/1:expand",
        json={"feedback": "第一幕前三章开局更猛"},
    )

    assert expand_resp.status_code == 200
    body = expand_resp.json()
    payload = body["roadmap_draft"]
    assert body["expanded_arc_numbers"] == []
    assert body["story_arcs_draft"][0]["generated_chapter_count"] == 1
    assert body["story_arcs_draft"][0]["chapter_target_count"] == 12
    assert body["story_arcs_draft"][0]["next_chapter_number"] == 2
    assert payload[0]["story_stage"] == "血月旧案开启"
    assert payload[0]["timeline_anchor"] == "入秋初夜"
    assert payload[0]["story_progress"] == "父母旧案与血月门第一次产生明确联系"
    assert payload[0]["key_events"] == ["主角第一次看见残谱异动"]
    assert payload[0]["chapter_tasks"][0]["task_id"] == "chapter-1-task-1"
    assert payload[0]["chapter_function"] == "开局"
    assert payload[0]["character_progress"] == ["林寒第一次主动追查父母之死", "苏璃发现门内气氛异常"]
    assert payload[0]["relationship_progress"] == ["林寒与苏璃建立初步信任", "林寒开始怀疑赵无极"]
    assert payload[0]["planned_loops"][0]["title"] == "残谱异动"
    assert payload[0]["planned_loops"][1]["loop_id"] == "chapter-1-loop-2"
    assert body["continuity_state"]["open_tasks"][0]["task_id"] == "chapter-1-task-1"
    assert body["continuity_state"]["recent_events"][0]["summary"] == "父母旧案与血月门第一次产生明确联系"


def test_build_book_blueprint_normalizes_stored_half_structured_roadmap(tmp_db: Database) -> None:
    """读取蓝图工作态时，应自动规范化旧的半结构章节路线。"""
    book_id = tmp_db.create_book("章节路线读取归一化", "zh-CN", "literary_cn", "", "localized_zh")
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="roadmap_ready",
        current_step="roadmap",
        roadmap_draft=[
            {
                "chapter_number": "3",
                "title": "夜渡裂碑",
                "goal": "推进调查",
                "core_conflict": "主角想隐忍，但线索开始逼近",
                "turning_point": "裂碑渡异动暴露残谱踪迹",
                "character_progress": "林寒开始主动追查；苏璃第一次公开站队",
                "relationship_progress": "林寒与苏璃建立互信、林寒与赵无极出现裂痕",
                "planned_loops": ["裂碑渡异动", "残谱缺页现身"],
                "closure_function": "抛出后续追查线索",
            }
        ],
    )

    blueprint = build_book_blueprint(tmp_db, book_id)

    assert blueprint.roadmap_draft[0].chapter_number == 3
    assert blueprint.roadmap_draft[0].key_events == ["裂碑渡异动暴露残谱踪迹"]
    assert blueprint.roadmap_draft[0].chapter_tasks[0].summary == "推进调查"
    assert blueprint.roadmap_draft[0].character_progress == ["林寒开始主动追查", "苏璃第一次公开站队"]
    assert blueprint.roadmap_draft[0].planned_loops[0].title == "裂碑渡异动"
    assert blueprint.continuity_state.open_tasks[0].task_id == "chapter-3-task-1"


def test_build_book_blueprint_blocks_future_arc_generation_and_expand_api_rejects_it(
    tmp_db: Database,
    monkeypatch,
) -> None:
    """前序阶段未完成时，后续阶段必须被标记为不可生成，并且接口会直接拒绝。"""
    from poiesis.api.services import blueprint_service

    client = _make_client(tmp_db)
    book_id = tmp_db.create_book("顺序门禁测试", "zh-CN", "literary_cn", "", "localized_zh")
    tmp_db.upsert_creation_intent(
        book_id,
        {
            "genre": "武侠",
            "themes": ["成长"],
            "tone": "冷峻",
            "protagonist_prompt": "被卷入旧案的少年",
            "conflict_prompt": "追查父母之死与残谱",
            "ending_preference": "代价胜利",
            "forbidden_elements": [],
            "length_preference": "24",
            "target_experience": "层层揭晓",
            "variant_preference": "世界差异优先",
        },
    )
    tmp_db.replace_concept_variants(
        book_id,
        [
            {
                "variant_no": 1,
                "hook": "裂碑夜雨",
                "world_pitch": "表层江湖平静，暗网秩序暗流涌动。",
                "main_arc_pitch": "主角在旧案追查中不断被迫介入各方势力的博弈。",
                "ending_pitch": "代价胜利",
            }
        ],
    )
    variant_id = tmp_db.list_concept_variants(book_id)[0]["id"]
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="story_arcs_ready",
        current_step="roadmap",
        selected_variant_id=variant_id,
        world_confirmed=WorldBlueprint(setting_summary="暗网江湖浮出水面。").model_dump(mode="json"),
        character_confirmed=[
            CharacterBlueprint(name="林寒", role="主角").model_dump(mode="json"),
            CharacterBlueprint(name="苏璃", role="师妹").model_dump(mode="json"),
        ],
        story_arcs_draft=[
            StoryArcPlan(
                arc_number=1,
                title="血月旧案开启",
                purpose="卷入主线",
                start_chapter=1,
                end_chapter=12,
            ).model_dump(mode="json"),
            StoryArcPlan(
                arc_number=2,
                title="天机令迷雾",
                purpose="追查真相",
                start_chapter=13,
                end_chapter=24,
            ).model_dump(mode="json"),
        ],
        roadmap_draft=[
            {
                "chapter_number": 1,
                "title": "裂碑夜雨",
                "story_stage": "血月旧案开启",
                "timeline_anchor": "入秋初夜",
                "depends_on_chapters": [],
                "goal": "让主角卷入主线",
                "core_conflict": "主角想置身事外，但黑市逼近",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次确认旧案并非巧合",
                "key_events": ["主角第一次看见残谱异动"],
                "chapter_tasks": [
                    {
                        "task_id": "trace-blood-moon",
                        "summary": "追查血月门与父母旧案的联系",
                        "status": "new",
                        "related_characters": ["林寒"],
                        "due_end_chapter": 3,
                    }
                ],
                "character_progress": ["林寒开始主动追查"],
                "relationship_beats": [
                    {"source_character": "林寒", "target_character": "苏璃", "summary": "双方建立初步互信"}
                ],
                "relationship_progress": ["林寒与苏璃建立初步互信"],
                "new_reveals": ["残谱会对主角血脉产生共鸣"],
                "world_updates": ["江湖黑市重新围绕残谱活跃"],
                "status_shift": ["主角不再只是旁观者"],
                "chapter_function": "开局",
                "anti_repeat_signature": "血月旧案开启:卷入主线",
                "planned_loops": [
                    {
                        "loop_id": "loop-1",
                        "title": "残谱异动",
                        "summary": "残谱对主角血脉产生共鸣",
                        "status": "open",
                        "priority": 1,
                        "due_start_chapter": 1,
                        "due_end_chapter": 3,
                        "related_characters": ["林寒"],
                        "resolution_requirements": ["揭示血脉来源"],
                    }
                ],
                "closure_function": "抛出下一章钩子",
            }
        ],
        expanded_arc_numbers=[],
    )

    def _fake_context(config_path: str, db: Database, target_book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=MockLLMClient(json_response={}),
            book_id=target_book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)

    detail = client.get(f"/api/books/{book_id}/blueprint")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["story_arcs_draft"][0]["can_generate_next_chapter"] is True
    assert payload["story_arcs_draft"][1]["can_generate_next_chapter"] is False
    assert payload["story_arcs_draft"][1]["blocking_arc_number"] == 1

    blocked = client.post(
        f"/api/books/{book_id}/blueprint/story-arcs/2:expand",
        json={"feedback": "直接生成第二幕"},
    )
    assert blocked.status_code == 400
    assert "请先完成前序阶段：第 1 幕" in blocked.json()["detail"]


def test_build_book_blueprint_derives_story_arcs_and_roadmap_warnings(tmp_db: Database) -> None:
    """读取蓝图时，应派生阶段视图并暴露重复功能章警示。"""
    book_id = tmp_db.create_book("长篇路线校验", "zh-CN", "literary_cn", "", "localized_zh")
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="roadmap_ready",
        current_step="roadmap",
        roadmap_draft=[
            {
                "chapter_number": 1,
                "title": "夜查旧案",
                "story_stage": "第一幕",
                "timeline_anchor": "初夜",
                "goal": "调查旧案",
                "core_conflict": "主角不敢惊动师门",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次确认旧案并非巧合",
                "character_progress": ["主角开始怀疑师门"],
                "relationship_progress": [],
                "chapter_function": "调查",
                "anti_repeat_signature": "第一幕:调查旧案",
                "planned_loops": [],
                "closure_function": "继续追查",
            },
            {
                "chapter_number": 2,
                "title": "再查旧案",
                "story_stage": "第一幕",
                "timeline_anchor": "初夜",
                "goal": "调查旧案",
                "core_conflict": "主角不敢惊动师门",
                "turning_point": "账册缺页",
                "story_progress": "主角第二次确认旧案并非巧合",
                "character_progress": ["主角对师兄产生疑心"],
                "relationship_progress": [],
                "chapter_function": "调查",
                "anti_repeat_signature": "第一幕:调查旧案",
                "planned_loops": [],
                "closure_function": "继续追查",
            },
        ],
    )

    blueprint = build_book_blueprint(tmp_db, book_id)

    assert blueprint.story_arcs_draft[0].title == "第一幕"
    assert any(item.type == "repeated_chapter_function" for item in blueprint.roadmap_validation_issues)


def test_character_generate_api_normalizes_rich_payload(tmp_db: Database, monkeypatch) -> None:
    """人物蓝图生成 API 应容忍字符串型数组字段。"""
    from poiesis.api.services import blueprint_service

    llm = _SequencedJsonLLM(
        [
            {
                "characters": [
                    {
                        "name": "沈砚",
                        "role": "主角",
                        "public_persona": "冷静寡言的落魄少年",
                        "core_motivation": "追查父母真相",
                        "fatal_flaw": "执念过重",
                        "non_negotiable_traits": "嘴硬心软；遇到大义不会退缩",
                        "relationship_constraints": "对师父始终保留戒心、与师兄既竞争又依赖",
                        "arc_outline": "前期被动卷入；中期主动追查；后期承担代价完成选择",
                    }
                ]
            },
            {
                "relationships": [],
            },
        ]
    )

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=llm,
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="人物归一化测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    tmp_db.upsert_creation_intent(
        book_id,
        {
            "genre": "武侠",
            "themes": ["成长"],
            "tone": "冷峻",
            "protagonist_prompt": "落魄少年",
            "conflict_prompt": "追查父母之死",
            "ending_preference": "代价胜利",
            "forbidden_elements": [],
            "length_preference": "12",
            "target_experience": "层层揭晓",
            "variant_preference": "人物差异优先",
        },
    )
    tmp_db.replace_concept_variants(
        book_id,
        [
            {
                "variant_no": 1,
                "hook": "旧案重启",
                "world_pitch": "暗网江湖浮出水面。",
                "main_arc_pitch": "主角在真相与秩序之间选择。",
                "ending_pitch": "代价胜利",
                "variant_strategy": "真相追查局",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案阴谋",
                "world_structure": "暗网江湖",
                "protagonist_arc_mode": "破局",
                "tone_signature": "冷峻",
                "differentiators": ["谜案推进"],
            }
        ],
    )
    variant_id = tmp_db.list_concept_variants(book_id)[0]["id"]
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="world_confirmed",
        current_step="characters",
        selected_variant_id=variant_id,
        world_confirmed={
            "setting_summary": "暗网江湖浮出水面。",
            "era_context": "王朝衰微",
            "social_order": "门派与豪强维持表面平衡",
            "historical_wounds": [],
            "public_secrets": [],
            "geography": [],
            "power_system": {
                "core_mechanics": "真气与机关术共鸣",
                "costs": [],
                "limitations": [],
                "advancement_path": [],
                "symbols": [],
            },
            "factions": [],
            "immutable_rules": [],
            "taboo_rules": [],
        },
    )

    response = client.post(
        f"/api/books/{book_id}/blueprint/characters:generate",
        json={"feedback": "主角更复杂一些"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "characters_ready"
    character = payload["character_draft"][0]
    assert character["arc_outline"] == ["前期被动卷入", "中期主动追查", "后期承担代价完成选择"]
    assert character["relationship_constraints"] == ["对师父始终保留戒心", "与师兄既竞争又依赖"]


def test_character_generate_api_normalizes_relationship_enum_payload(
    tmp_db: Database,
    monkeypatch,
) -> None:
    """人物蓝图生成接口应把关系边中的英文枚举映射成中文正式值。"""
    from poiesis.api.services import blueprint_service

    llm = _SequencedJsonLLM(
        [
            {
                "characters": [
                    {
                        "name": "沈砚",
                        "role": "主角",
                        "public_persona": "落魄少年",
                        "core_motivation": "追查真相",
                        "fatal_flaw": "执念过重",
                        "non_negotiable_traits": ["嘴硬心软"],
                        "relationship_constraints": ["对师父既依赖又怀疑"],
                        "arc_outline": ["前期卷入", "中期追查", "后期承担代价"],
                    },
                    {
                        "name": "陆行川",
                        "role": "师父",
                        "public_persona": "隐世剑客",
                        "core_motivation": "压住旧案余波",
                        "fatal_flaw": "习惯隐瞒真相",
                        "non_negotiable_traits": ["不轻易失控"],
                        "relationship_constraints": ["对主角既保护又设防"],
                        "arc_outline": ["前期试探", "中期让位", "后期揭示真相"],
                    },
                ]
            },
            {
                "relationships": [
                    {
                        "edge_id": "rel-1",
                        "source_character_id": "沈砚",
                        "target_character_id": "陆行川",
                        "relation_type": "师徒",
                        "polarity": "positive",
                        "visibility": "public",
                        "stability": "high",
                        "intensity": "4",
                        "summary": "名义师徒，实则彼此试探。",
                        "hidden_truth": "师父隐瞒了旧案真相。",
                        "non_breakable_without_reveal": "yes",
                    }
                ]
            },
        ]
    )

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=llm,
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="人物关系枚举归一化测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    tmp_db.upsert_creation_intent(
        book_id,
        {
            "genre": "武侠",
            "themes": ["成长", "背叛"],
            "tone": "冷峻",
            "protagonist_prompt": "落魄少年",
            "conflict_prompt": "追查父母之死",
            "ending_preference": "代价胜利",
            "forbidden_elements": ["系统流"],
            "length_preference": "12",
            "target_experience": "层层揭晓",
            "variant_preference": "人物差异优先",
        },
    )
    tmp_db.replace_concept_variants(
        book_id,
        [
            {
                "variant_no": 1,
                "selected": True,
                "hook": "旧案重启",
                "world_pitch": "暗网江湖浮出水面。",
                "main_arc_pitch": "主角在真相与秩序之间选择。",
                "ending_pitch": "代价胜利",
                "variant_strategy": "真相追查局",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案阴谋",
                "world_structure": "暗网江湖",
                "protagonist_arc_mode": "破局",
                "tone_signature": "冷峻",
                "differentiators": ["谜案推进"],
            }
        ],
    )
    variant_id = tmp_db.list_concept_variants(book_id)[0]["id"]
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="world_confirmed",
        current_step="characters",
        selected_variant_id=variant_id,
        world_confirmed={
            "setting_summary": "暗网江湖浮出水面。",
            "era_context": "王朝衰微",
            "social_order": "门派与豪强维持表面平衡",
            "historical_wounds": [],
            "public_secrets": [],
            "geography": [],
            "power_system": {
                "core_mechanics": "真气与机关术共鸣",
                "costs": [],
                "limitations": [],
                "advancement_path": [],
                "symbols": [],
            },
            "factions": [],
            "immutable_rules": [],
            "taboo_rules": [],
        },
    )

    response = client.post(
        f"/api/books/{book_id}/blueprint/characters:generate",
        json={"feedback": "关系里要有明显试探感"},
    )
    assert response.status_code == 200
    payload = response.json()
    relationship = payload["relationship_graph_draft"][0]
    assert relationship["polarity"] == "正向"
    assert relationship["visibility"] == "公开"
    assert relationship["stability"] == "稳定"
    assert relationship["intensity"] == 4
    assert relationship["non_breakable_without_reveal"] is True


def test_get_blueprint_normalizes_stored_world_and_character_payload(tmp_db: Database) -> None:
    """读取蓝图工作态时，应自动把历史半结构草稿收口成正式协议。"""
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="读取草稿归一化测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="characters_ready",
        current_step="characters",
        world_draft={
            "setting_summary": "旧秩序与暗网并存。",
            "power_system": {
                "core_mechanics": "真气与机关术共鸣",
                "costs": "经脉灼伤；真气紊乱",
                "limitations": "血脉适配；残谱加持",
                "advancement_path": "炼体、化气",
                "symbols": "裂纹玉牌，机关残页",
            },
            "factions": {
                "name": "天机阁",
                "position": "隐秘门派",
                "goal": "维持均势",
                "methods": "暗线操盘；收拢秘卷",
                "public_image": "避世门派",
                "hidden_truth": "操盘江湖均势",
            },
        },
        character_draft=[
            {
                "name": "沈砚",
                "role": "主角",
                "public_persona": "落魄少年",
                "core_motivation": "追查真相",
                "fatal_flaw": "执念过重",
                "non_negotiable_traits": "嘴硬心软；不肯退缩",
                "relationship_constraints": "对师父保留戒心、与师兄相互牵制",
                "arc_outline": "前期卷入；中期追查；后期承担代价",
            }
        ],
    )

    response = client.get(f"/api/books/{book_id}/blueprint")
    assert response.status_code == 200
    payload = response.json()
    assert payload["world_draft"]["factions"][0]["methods"] == ["暗线操盘", "收拢秘卷"]
    assert payload["world_draft"]["power_system"]["costs"] == ["经脉灼伤", "真气紊乱"]
    assert payload["character_draft"][0]["arc_outline"] == ["前期卷入", "中期追查", "后期承担代价"]


def test_can_regenerate_single_concept_variant_before_selection(tmp_db: Database, monkeypatch) -> None:
    """作者应能只重生成某一版候选方向，而不必整组重来。"""
    from poiesis.api.services import blueprint_service

    llm = _SequencedJsonLLM(
        [
            {
                "hook": "江湖旧案撕开暗网",
                "world_pitch": "表层江湖平静，深层秘密组织以旧案操控门派平衡。",
                "main_arc_pitch": "主角从追查真相走向承受真相代价，被迫在复仇与止乱之间选边。",
                "ending_pitch": "真相代价",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案阴谋",
                "world_structure": "暗网江湖",
                "protagonist_arc_mode": "破局",
                "tone_signature": "冷峻",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案追查", "层层揭晓"],
            }
        ]
    )

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=llm,
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)

    created = client.post(
        "/api/books",
        json={
            "name": "重生成候选测试",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "",
            "naming_policy": "localized_zh",
            "is_default": False,
        },
    )
    book_id = created.json()["id"]
    client.post(
        f"/api/books/{book_id}/creation-intent",
        json={
            "genre": "武侠",
            "themes": ["成长"],
            "tone": "冷峻",
            "protagonist_prompt": "落魄剑客",
            "conflict_prompt": "追查旧案",
            "ending_preference": "代价胜利",
            "forbidden_elements": [],
            "length_preference": "12",
            "target_experience": "层层揭晓",
            "variant_preference": "世界差异优先",
        },
    )
    tmp_db.replace_concept_variants(
        book_id,
        [
            {
                "variant_no": 1,
                "hook": "血色月夜，断剑照见背叛。",
                "world_pitch": "江湖以血债和师门恩怨交缠。",
                "main_arc_pitch": "主角在复仇与守护之间撕扯。",
                "ending_pitch": "代价胜利",
                "variant_strategy": "江湖人物局",
                "core_driver": "人物驱动",
                "conflict_source": "江湖恩怨与师门关系",
                "world_structure": "单江湖秩序下的人情网络",
                "protagonist_arc_mode": "从私仇走向自我抉择",
                "tone_signature": "血性、克制、带宿命感",
                "differentiators": ["人物关系反转"],
            },
            {
                "variant_no": 2,
                "hook": "门规松动，旧秩序裂开第一道缝。",
                "world_pitch": "多门派双层秩序相互制衡。",
                "main_arc_pitch": "主角从旁观者走向秩序重塑者。",
                "ending_pitch": "新秩序",
                "variant_strategy": "门派秩序局",
                "core_driver": "世界驱动",
                "conflict_source": "门派格局失衡与旧秩序崩坏",
                "world_structure": "多门派并立的双层江湖秩序",
                "protagonist_arc_mode": "从旁观者走向秩序重塑者",
                "tone_signature": "厚重、权谋、史诗感",
                "differentiators": ["阵营对抗主导推进"],
            },
            {
                "variant_no": 3,
                "hook": "旧案重启，天机阁的影子再度浮现。",
                "world_pitch": "秘密江湖暗流汹涌，诸派被旧案牵连。",
                "main_arc_pitch": "主角沿着旧案追查真相，却被迫承担更大的代价。",
                "ending_pitch": "真相代价",
                "variant_strategy": "真相追查局",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案与隐藏势力编织的长期阴谋",
                "world_structure": "表层平稳、深层暗网遍布的秘密江湖",
                "protagonist_arc_mode": "从追查真相走向承担真相代价",
                "tone_signature": "冷峻、诡谲、层层揭晓",
                "differentiators": ["谜案推进更强"],
            },
        ],
    )
    variants = tmp_db.list_concept_variants(book_id)
    tmp_db.upsert_book_blueprint_state(book_id, status="concept_generated", current_step="concept")
    target_id = variants[1]["id"]

    regenerated = client.post(f"/api/books/{book_id}/concept-variants/{target_id}:regenerate", json={})
    assert regenerated.status_code == 200
    payload = regenerated.json()
    assert payload["status"] == "applied"
    assert payload["target_variant_id"] == target_id
    assert payload["applied_variant"]["core_driver"] == "悬疑驱动"
    refreshed = client.get(f"/api/books/{book_id}/blueprint").json()
    target_variant = next(item for item in refreshed["concept_variants"] if item["id"] == target_id)
    assert target_variant["hook"] == "江湖旧案撕开暗网"


def test_regenerate_similar_variant_returns_confirmation_proposal(tmp_db: Database, monkeypatch) -> None:
    """多轮回炉后仍过于相似时，不应自动覆盖旧候选，而应退回人工确认。"""
    from poiesis.api.services import blueprint_service

    llm = _SequencedJsonLLM(
        [
            {
                "hook": "血色月夜，断剑照见背叛。",
                "world_pitch": "江湖以血债和师门恩怨交缠。",
                "main_arc_pitch": "主角在复仇与守护之间撕扯。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "江湖恩怨与师门关系",
                "world_structure": "单江湖秩序下的人情网络",
                "protagonist_arc_mode": "从私仇走向自我抉择",
                "tone_signature": "血性、克制、带宿命感",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案推进更强"],
            },
            {
                "hook": "血色月夜，断剑照见背叛。",
                "world_pitch": "江湖以血债和师门恩怨交缠。",
                "main_arc_pitch": "主角在复仇与守护之间撕扯。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "江湖恩怨与师门关系",
                "world_structure": "单江湖秩序下的人情网络",
                "protagonist_arc_mode": "从私仇走向自我抉择",
                "tone_signature": "血性、克制、带宿命感",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案推进更强"],
            },
            {
                "hook": "血色月夜，断剑照见背叛。",
                "world_pitch": "江湖以血债和师门恩怨交缠。",
                "main_arc_pitch": "主角在复仇与守护之间撕扯。",
                "ending_pitch": "代价胜利",
                "core_driver": "人物驱动",
                "conflict_source": "江湖恩怨与师门关系",
                "world_structure": "单江湖秩序下的人情网络",
                "protagonist_arc_mode": "从私仇走向自我抉择",
                "tone_signature": "血性、克制、带宿命感",
                "variant_strategy": "真相追查局",
                "differentiators": ["谜案推进更强"],
            },
        ]
    )

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=llm,
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)

    created = client.post(
        "/api/books",
        json={
            "name": "相似提案测试",
            "language": "zh-CN",
            "style_preset": "literary_cn",
            "style_prompt": "",
            "naming_policy": "localized_zh",
            "is_default": False,
        },
    )
    book_id = created.json()["id"]
    tmp_db.upsert_creation_intent(
        book_id,
        {
            "genre": "武侠",
            "themes": ["成长"],
            "tone": "冷峻",
            "protagonist_prompt": "落魄剑客",
            "conflict_prompt": "追查旧案",
            "ending_preference": "代价胜利",
            "forbidden_elements": [],
            "length_preference": "12",
            "target_experience": "层层揭晓",
            "variant_preference": "世界差异优先",
        },
    )
    tmp_db.replace_concept_variants(
        book_id,
        [
            {
                "variant_no": 1,
                "hook": "血色月夜，断剑照见背叛。",
                "world_pitch": "江湖以血债和师门恩怨交缠。",
                "main_arc_pitch": "主角在复仇与守护之间撕扯。",
                "ending_pitch": "代价胜利",
                "variant_strategy": "江湖人物局",
                "core_driver": "人物驱动",
                "conflict_source": "江湖恩怨与师门关系",
                "world_structure": "单江湖秩序下的人情网络",
                "protagonist_arc_mode": "从私仇走向自我抉择",
                "tone_signature": "血性、克制、带宿命感",
                "differentiators": ["人物关系反转"],
            },
            {
                "variant_no": 2,
                "hook": "门规松动，旧秩序裂开第一道缝。",
                "world_pitch": "多门派双层秩序相互制衡。",
                "main_arc_pitch": "主角从旁观者走向秩序重塑者。",
                "ending_pitch": "新秩序",
                "variant_strategy": "门派秩序局",
                "core_driver": "世界驱动",
                "conflict_source": "门派格局失衡与旧秩序崩坏",
                "world_structure": "多门派并立的双层江湖秩序",
                "protagonist_arc_mode": "从旁观者走向秩序重塑者",
                "tone_signature": "厚重、权谋、史诗感",
                "differentiators": ["阵营对抗主导推进"],
            },
            {
                "variant_no": 3,
                "hook": "旧案重启，天机阁的影子再度浮现。",
                "world_pitch": "秘密江湖暗流汹涌，诸派被旧案牵连。",
                "main_arc_pitch": "主角沿着旧案追查真相，却被迫承担更大的代价。",
                "ending_pitch": "真相代价",
                "variant_strategy": "真相追查局",
                "core_driver": "悬疑驱动",
                "conflict_source": "旧案与隐藏势力编织的长期阴谋",
                "world_structure": "表层平稳、深层暗网遍布的秘密江湖",
                "protagonist_arc_mode": "从追查真相走向承担真相代价",
                "tone_signature": "冷峻、诡谲、层层揭晓",
                "differentiators": ["谜案推进更强"],
            },
        ],
    )
    tmp_db.upsert_book_blueprint_state(book_id, status="concept_generated", current_step="concept")
    target_id = tmp_db.list_concept_variants(book_id)[2]["id"]

    regenerated = client.post(f"/api/books/{book_id}/concept-variants/{target_id}:regenerate", json={})
    assert regenerated.status_code == 200
    payload = regenerated.json()
    assert payload["status"] == "needs_confirmation"
    assert payload["proposed_variant"]["diversity_note"]
    original = tmp_db.get_concept_variant(target_id)
    assert original is not None
    assert original["hook"] == "旧案重启，天机阁的影子再度浮现。"

    accepted = client.post(
        f"/api/books/{book_id}/concept-variants/{target_id}:accept-regenerated",
        json={"proposal": payload["proposed_variant"]},
    )
    assert accepted.status_code == 200
    updated = tmp_db.get_concept_variant(target_id)
    assert updated is not None
    assert updated["hook"] == payload["proposed_variant"]["hook"]


def test_canon_api_returns_structured_world_and_relationship_graph(tmp_db: Database) -> None:
    """Canon 接口应返回结构化世界蓝图摘要与人物关系图谱。"""
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="世界图谱测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    revision_id = tmp_db.create_blueprint_revision(
        book_id,
        revision_number=1,
        selected_variant_id=None,
        change_reason="初始化结构化蓝图",
        change_summary="用于 Canon API 测试",
        affected_range=[1, 12],
        world_blueprint={
            "setting_summary": "江湖与暗网并存。",
            "era_context": "王朝衰微",
            "social_order": "门派与豪强维系脆弱平衡",
            "historical_wounds": ["天机阁清洗旧武林"],
            "public_secrets": ["江湖都知道有一批失落的机关残卷"],
            "geography": [{"name": "天机峡", "role": "禁地", "description": "旧案发源地"}],
            "power_system": {
                "core_mechanics": "真气与机关术共鸣",
                "costs": ["折损经脉"],
                "limitations": ["需血脉承载"],
                "advancement_path": ["炼体", "化气"],
                "symbols": ["裂纹玉牌"],
            },
            "factions": [
                {
                    "name": "天机阁",
                    "position": "隐秘门派",
                    "goal": "维持均势",
                    "methods": ["暗线操盘"],
                    "public_image": "避世",
                    "hidden_truth": "操盘江湖",
                }
            ],
            "immutable_rules": [
                {
                    "key": "血脉共鸣",
                    "description": "机关术必须以血脉激活",
                    "category": "power",
                    "rationale": "维持稀缺性",
                    "is_immutable": True,
                }
            ],
            "taboo_rules": [
                {
                    "key": "逆转经脉",
                    "description": "逆行真气强开机关术",
                    "consequence": "经脉崩毁",
                    "is_immutable": True,
                }
            ],
        },
        character_blueprints=[
            {
                "name": "沈砚",
                "role": "主角",
                "public_persona": "落魄少年",
                "core_motivation": "追查真相",
                "fatal_flaw": "执念过重",
                "non_negotiable_traits": ["嘴硬"],
                "relationship_constraints": [],
                "arc_outline": ["从复仇到守护"],
            }
        ],
        relationship_graph=[
            {
                "edge_id": "rel-1",
                "source_character_id": "沈砚",
                "target_character_id": "陆行川",
                "relation_type": "师徒",
                "polarity": "复杂",
                "intensity": 4,
                "visibility": "半公开",
                "stability": "正在转变",
                "summary": "名义师徒，实则彼此试探。",
                "hidden_truth": "陆行川隐瞒了旧案真相。",
                "non_breakable_without_reveal": True,
            }
        ],
        roadmap=[],
        is_active=True,
    )
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="locked",
        current_step="locked",
        active_revision_id=revision_id,
        world_confirmed={
            "setting_summary": "江湖与暗网并存。",
            "era_context": "王朝衰微",
            "social_order": "门派与豪强维系脆弱平衡",
            "historical_wounds": ["天机阁清洗旧武林"],
            "public_secrets": ["江湖都知道有一批失落的机关残卷"],
            "geography": [{"name": "天机峡", "role": "禁地", "description": "旧案发源地"}],
            "power_system": {
                "core_mechanics": "真气与机关术共鸣",
                "costs": ["折损经脉"],
                "limitations": ["需血脉承载"],
                "advancement_path": ["炼体", "化气"],
                "symbols": ["裂纹玉牌"],
            },
            "factions": [
                {
                    "name": "天机阁",
                    "position": "隐秘门派",
                    "goal": "维持均势",
                    "methods": ["暗线操盘"],
                    "public_image": "避世",
                    "hidden_truth": "操盘江湖",
                }
            ],
            "immutable_rules": [
                {
                    "key": "血脉共鸣",
                    "description": "机关术必须以血脉激活",
                    "category": "power",
                    "rationale": "维持稀缺性",
                    "is_immutable": True,
                }
            ],
            "taboo_rules": [
                {
                    "key": "逆转经脉",
                    "description": "逆行真气强开机关术",
                    "consequence": "经脉崩毁",
                    "is_immutable": True,
                }
            ],
        },
        relationship_graph_confirmed=[
            {
                "edge_id": "rel-1",
                "source_character_id": "沈砚",
                "target_character_id": "陆行川",
                "relation_type": "师徒",
                "polarity": "复杂",
                "intensity": 4,
                "visibility": "半公开",
                "stability": "正在转变",
                "summary": "名义师徒，实则彼此试探。",
                "hidden_truth": "陆行川隐瞒了旧案真相。",
                "non_breakable_without_reveal": True,
            }
        ],
    )

    response = client.get(f"/api/canon?book_id={book_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["world_blueprint_summary"]["power_system"]["core_mechanics"] == "真气与机关术共鸣"
    assert payload["relationship_graph"][0]["relation_type"] == "师徒"


def test_creative_repair_control_plane_can_plan_apply_and_rollback(
    tmp_db: Database,
    monkeypatch,
) -> None:
    """闭环控制面应支持问题识别、提案生成、执行修复与回滚。"""
    from poiesis.api.services import blueprint_service

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=MockLLMClient(),
            book_id=book_id,
            planner=RoadmapPlanner(),
        )

    monkeypatch.setattr(blueprint_service, "_build_context", _fake_context)
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="闭环控制面测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="story_arcs_ready",
        current_step="roadmap",
        story_arcs_draft=[
            {
                "arc_number": 1,
                "title": "血月旧案开启",
                "purpose": "让主角卷入旧案",
                "start_chapter": 1,
                "end_chapter": 3,
                "main_progress": ["主角第一次确认父母旧案并非巧合"],
                "relationship_progress": [],
                "loop_progress": ["血月门遗迹"],
                "timeline_milestones": ["入秋初夜"],
                "arc_climax": "主角在遗迹入口被迫出手",
            }
        ],
        roadmap_draft=[
            {
                "chapter_number": 1,
                "title": "裂碑夜雨",
                "story_stage": "血月旧案开启",
                "timeline_anchor": "入秋初夜",
                "depends_on_chapters": [],
                "goal": "卷入主线",
                "core_conflict": "黑市逼近",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次确认父母旧案并非巧合",
                "key_events": ["主角第一次看见残谱异动"],
                "chapter_tasks": [
                    {
                        "task_id": "trace-bloodline",
                        "summary": "确认主角血脉与残谱的联系",
                        "status": "in_progress",
                        "related_characters": ["林寒"],
                        "due_end_chapter": 2,
                    }
                ],
                "relationship_beats": [],
                "character_progress": ["林寒从旁观转向主动追查"],
                "relationship_progress": [],
                "new_reveals": ["残谱会对主角血脉产生共鸣"],
                "world_updates": [],
                "status_shift": ["主角不再只是旁观者"],
                "chapter_function": "开局",
                "anti_repeat_signature": "第一幕:卷入主线",
                "planned_loops": [
                    {
                        "loop_id": "loop-1",
                        "title": "残谱异动",
                        "summary": "残谱第一次在主角面前异动。",
                        "status": "open",
                        "priority": 1,
                        "due_start_chapter": 1,
                        "due_end_chapter": 3,
                        "related_characters": ["林寒"],
                        "resolution_requirements": ["解释残谱与血脉的关系"],
                    }
                ],
                "closure_function": "抛出下一章钩子",
            }
        ],
        expanded_arc_numbers=[],
    )

    issues_response = client.get(f"/api/books/{book_id}/creative-issues")
    assert issues_response.status_code == 200
    issues_payload = issues_response.json()
    target_issue = next(item for item in issues_payload["items"] if item["issue_type"] == "task_status_jump")
    assert target_issue["repairability"] == "deterministic"
    assert target_issue["suggested_strategy"] == "field_patch"

    plan_response = client.post(
        f"/api/books/{book_id}/creative-issues:plan-repairs",
        json={"issue_ids": [target_issue["issue_id"]]},
    )
    assert plan_response.status_code == 200
    plan_payload = plan_response.json()
    assert len(plan_payload["creative_repair_proposals"]) == 1
    proposal = plan_payload["creative_repair_proposals"][0]
    assert proposal["strategy_type"] == "field_patch"
    assert proposal["status"] == "awaiting_approval"

    proposal_response = client.get(f"/api/books/{book_id}/repair-proposals/{proposal['proposal_id']}")
    assert proposal_response.status_code == 200
    assert proposal_response.json()["proposal_id"] == proposal["proposal_id"]

    apply_response = client.post(f"/api/books/{book_id}/repair-proposals/{proposal['proposal_id']}:apply", json={})
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert not any(item["issue_type"] == "task_status_jump" for item in apply_payload["creative_issues"])
    assert apply_payload["roadmap_draft"][0]["chapter_tasks"][0]["status"] == "new"
    assert apply_payload["creative_repair_runs"][-1]["status"] == "succeeded"

    rollback_run = apply_payload["creative_repair_runs"][-1]
    rollback_response = client.post(
        f"/api/books/{book_id}/repair-runs/{rollback_run['run_id']}:rollback",
        json={},
    )
    assert rollback_response.status_code == 200
    rollback_payload = rollback_response.json()
    assert any(item["issue_type"] == "task_status_jump" for item in rollback_payload["creative_issues"])
    assert rollback_payload["roadmap_draft"][0]["chapter_tasks"][0]["status"] == "in_progress"


def test_creative_repair_planner_marks_semantic_issue_as_rewrite(tmp_db: Database) -> None:
    """语义连续性问题应升级为重写提案，而不是伪装成字段级修补。"""
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="语义重写策略测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="story_arcs_ready",
        current_step="roadmap",
        story_arcs_draft=[
            {
                "arc_number": 1,
                "title": "第一幕",
                "purpose": "卷入主线",
                "start_chapter": 1,
                "end_chapter": 3,
                "main_progress": ["把旧案从传闻推进到可验证线索"],
                "relationship_progress": [],
                "loop_progress": [],
                "timeline_milestones": ["入秋初夜"],
                "arc_climax": "在渡口确认幕后有人提前布局",
            }
        ],
        roadmap_draft=[
            {
                "chapter_number": 1,
                "title": "旧案初现",
                "story_stage": "第一幕",
                "timeline_anchor": "入秋初夜",
                "depends_on_chapters": [],
                "goal": "卷入主线",
                "core_conflict": "主角不敢惊动师门",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次确认旧案并非巧合",
                "key_events": ["主角第一次看见残谱异动"],
                "chapter_tasks": [],
                "relationship_beats": [],
                "character_progress": [],
                "relationship_progress": [],
                "new_reveals": [],
                "world_updates": [],
                "status_shift": [],
                "chapter_function": "调查",
                "anti_repeat_signature": "第一幕:调查旧案",
                "planned_loops": [],
                "closure_function": "继续调查",
            },
            {
                "chapter_number": 2,
                "title": "再查旧案",
                "story_stage": "第一幕",
                "timeline_anchor": "入秋次日清晨",
                "depends_on_chapters": [1],
                "goal": "继续追查",
                "core_conflict": "主角仍不敢惊动师门",
                "turning_point": "账册缺页",
                "story_progress": "主角继续确认旧案并非巧合",
                "key_events": ["渡口账册出现缺页"],
                "chapter_tasks": [],
                "relationship_beats": [],
                "character_progress": [],
                "relationship_progress": [],
                "new_reveals": [],
                "world_updates": [],
                "status_shift": [],
                "chapter_function": "调查",
                "anti_repeat_signature": "第一幕:继续调查",
                "planned_loops": [],
                "closure_function": "继续调查",
            },
        ],
        expanded_arc_numbers=[],
    )

    response = client.get(f"/api/books/{book_id}/creative-issues")
    assert response.status_code == 200
    issues = response.json()["items"]
    repeated_issue = next(item for item in issues if item["issue_type"] == "repeated_chapter_function")
    assert repeated_issue["repairability"] == "llm"
    assert repeated_issue["suggested_strategy"] == "chapter_rewrite"


def test_global_repair_planning_skips_arc_rewrite_issue_by_default() -> None:
    """全量生成修复方案时，不应自动把阶段级骨架重写问题卷进去。"""
    planner = RoadmapPlanner()
    orchestrator = CreativeOrchestrator(planner)
    story_arcs = [
        StoryArcPlan(
            arc_number=1,
            title="第一幕",
            purpose="卷入主线",
            start_chapter=1,
            end_chapter=3,
            main_progress=["旧案从传闻升级为可验证线索"],
            relationship_progress=[],
            loop_progress=[],
            timeline_milestones=["入秋初夜"],
            arc_climax="发现布局者比预想更近",
        )
    ]
    roadmap = [
        ChapterRoadmapItem(
            chapter_number=1,
            title="旧案初现",
            story_stage="第一幕",
            timeline_anchor="入秋初夜",
            depends_on_chapters=[],
            goal="卷入主线",
            core_conflict="主角不敢惊动师门",
            turning_point="残谱异动",
            story_progress="主角继续确认旧案并非巧合",
            key_events=["主角第一次看见残谱异动"],
            chapter_tasks=[],
            relationship_beats=[],
            character_progress=[],
            relationship_progress=[],
            new_reveals=[],
            world_updates=[],
            status_shift=[],
            chapter_function="开局",
            anti_repeat_signature="第一幕:调查旧案",
            planned_loops=[
                {
                    "loop_id": "loop-1",
                    "title": "残谱异动",
                    "summary": "残谱第一次在主角面前异动。",
                    "status": "open",
                    "priority": 1,
                    "due_start_chapter": 1,
                    "due_end_chapter": 4,
                    "related_characters": ["林寒"],
                    "resolution_requirements": ["解释残谱与血脉的关系"],
                }
            ],
            closure_function="继续调查",
        ),
        ChapterRoadmapItem(
            chapter_number=2,
            title="再查旧案",
            story_stage="第一幕",
            timeline_anchor="入秋次日清晨",
            depends_on_chapters=[1],
            goal="继续追查",
            core_conflict="主角仍不敢惊动师门",
            turning_point="账册缺页",
            story_progress="主角继续确认旧案并非巧合",
            key_events=["渡口账册出现缺页"],
            chapter_tasks=[],
            relationship_beats=[],
            character_progress=[],
            relationship_progress=[],
            new_reveals=[],
            world_updates=[],
            status_shift=[],
            chapter_function="推进",
            anti_repeat_signature="第一幕:继续追查",
            planned_loops=[
                {
                    "loop_id": "loop-2",
                    "title": "账册缺页",
                    "summary": "缺页账册背后有人刻意掩盖资金流向。",
                    "status": "open",
                    "priority": 1,
                    "due_start_chapter": 2,
                    "due_end_chapter": 4,
                    "related_characters": ["林寒"],
                    "resolution_requirements": ["确认是谁取走了缺失账页"],
                }
            ],
            closure_function="继续调查",
        ),
        ChapterRoadmapItem(
            chapter_number=3,
            title="旧案余震",
            story_stage="第一幕",
            timeline_anchor="入秋次日傍晚",
            depends_on_chapters=[2],
            goal="继续追查",
            core_conflict="主角仍不敢惊动师门",
            turning_point="线索暂时断裂",
            story_progress="主角继续确认旧案并非巧合",
            key_events=["主角发现账册缺页背后另有掩护者"],
            chapter_tasks=[],
            relationship_beats=[],
            character_progress=[],
            relationship_progress=[],
            new_reveals=[],
            world_updates=[],
            status_shift=[],
            chapter_function="施压",
            anti_repeat_signature="第一幕:线索受阻",
            planned_loops=[
                {
                    "loop_id": "loop-3",
                    "title": "掩护者现身",
                    "summary": "账册缺页背后显然有专门掩护者在场外压线。",
                    "status": "open",
                    "priority": 1,
                    "due_start_chapter": 3,
                    "due_end_chapter": 5,
                    "related_characters": ["林寒"],
                    "resolution_requirements": ["确认掩护者身份及其阵营"],
                }
            ],
            closure_function="留下后续压力",
        ),
    ]
    issues = planner.verify_roadmap(story_arcs, roadmap)
    assert any(item.type in {"arc_story_progress_stagnation", "arc_missing_climax"} for item in issues)

    with pytest.raises(ValueError, match="当前没有可生成修复方案的问题"):
        orchestrator.plan_roadmap_repairs(
            book_id=1,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=issues,
            stored_proposals=[],
            issue_ids=[],
            intent=CreationIntent(
                genre="武侠",
                themes=["成长"],
                tone="冷峻",
                protagonist_prompt="少年剑客",
                conflict_prompt="追查旧案",
                ending_preference="代价胜利",
                forbidden_elements=[],
                length_preference="3",
                target_experience="递进",
                variant_preference="",
            ),
            variant=ConceptVariant(
                variant_no=1,
                hook="少年剑客误入风暴",
                world_pitch="旧案引动暗流",
                main_arc_pitch="主角被迫卷入真相",
                ending_pitch="代价胜利",
            ),
            world=WorldBlueprint(setting_summary="旧案背后有江湖暗网。"),
            characters=[],
            llm=MockLLMClient(json_response={"story_arcs": []}),
        )


def test_explicit_arc_rewrite_generation_deduplicates_pending_and_applied_proposals() -> None:
    """显式点阶段问题时仍可生成骨架修复方案，但同签名方案不应重复堆叠。"""
    planner = RoadmapPlanner()
    orchestrator = CreativeOrchestrator(planner)
    story_arcs = [
        StoryArcPlan(
            arc_number=1,
            title="第一幕",
            purpose="卷入主线",
            start_chapter=1,
            end_chapter=3,
            main_progress=["旧案从传闻升级为可验证线索"],
            relationship_progress=[],
            loop_progress=[],
            timeline_milestones=["入秋初夜"],
            arc_climax="发现布局者比预想更近",
        )
    ]
    roadmap = [
        ChapterRoadmapItem(
            chapter_number=1,
            title="旧案初现",
            story_stage="第一幕",
            timeline_anchor="入秋初夜",
            depends_on_chapters=[],
            goal="卷入主线",
            core_conflict="主角不敢惊动师门",
            turning_point="残谱异动",
            story_progress="主角第一次确认旧案并非巧合",
            key_events=["主角第一次看见残谱异动"],
            chapter_tasks=[],
            relationship_beats=[],
            character_progress=[],
            relationship_progress=[],
            new_reveals=[],
            world_updates=[],
            status_shift=[],
            chapter_function="调查",
            anti_repeat_signature="第一幕:调查旧案",
            planned_loops=[],
            closure_function="继续调查",
        ),
        ChapterRoadmapItem(
            chapter_number=2,
            title="再查旧案",
            story_stage="第一幕",
            timeline_anchor="入秋次日清晨",
            depends_on_chapters=[1],
            goal="继续追查",
            core_conflict="主角仍不敢惊动师门",
            turning_point="账册缺页",
            story_progress="主角继续确认旧案并非巧合",
            key_events=["渡口账册出现缺页"],
            chapter_tasks=[],
            relationship_beats=[],
            character_progress=[],
            relationship_progress=[],
            new_reveals=[],
            world_updates=[],
            status_shift=[],
            chapter_function="调查",
            anti_repeat_signature="第一幕:继续调查",
            planned_loops=[],
            closure_function="继续调查",
        ),
    ]
    issues = planner.verify_roadmap(story_arcs, roadmap)
    creative_issues = orchestrator.build_creative_issues(
        book_id=1,
        story_arcs=story_arcs,
        roadmap=roadmap,
        roadmap_issues=issues,
        stored_proposals=[],
    )
    target_issue = next(item for item in creative_issues if item.issue_type == "arc_function_monotony")

    proposals = orchestrator.plan_roadmap_repairs(
        book_id=1,
        story_arcs=story_arcs,
        roadmap=roadmap,
        roadmap_issues=issues,
        stored_proposals=[],
        issue_ids=[target_issue.issue_id],
        intent=CreationIntent(
            genre="武侠",
            themes=["成长"],
            tone="冷峻",
            protagonist_prompt="少年剑客",
            conflict_prompt="追查旧案",
            ending_preference="代价胜利",
            forbidden_elements=[],
            length_preference="3",
            target_experience="递进",
            variant_preference="",
        ),
        variant=ConceptVariant(
            variant_no=1,
            hook="少年剑客误入风暴",
            world_pitch="旧案引动暗流",
            main_arc_pitch="主角被迫卷入真相",
            ending_pitch="代价胜利",
        ),
        world=WorldBlueprint(setting_summary="旧案背后有江湖暗网。"),
        characters=[],
        llm=MockLLMClient(
            json_response={
                "story_arcs": [
                    {
                        "arc_number": 1,
                        "title": "第一幕",
                        "purpose": "卷入主线并建立江湖格局",
                        "start_chapter": 1,
                        "end_chapter": 3,
                        "main_progress": ["旧案从传闻升级为可验证线索", "主角确认幕后布局正在逼近"],
                        "relationship_progress": ["主角与线人建立初步互信"],
                        "loop_progress": ["血脉异动从异常现象转向明确线索"],
                        "timeline_milestones": ["入秋初夜", "入秋次日夜"],
                        "arc_climax": "主角在渡口确认布局者早已盯上自己",
                    }
                ]
            }
        ),
    )

    arc_rewrite = next(item for item in proposals if item.strategy_type == "arc_rewrite")
    assert arc_rewrite.proposal_signature

    with pytest.raises(ValueError, match="当前没有可生成修复方案的问题"):
        orchestrator.plan_roadmap_repairs(
            book_id=1,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=issues,
            stored_proposals=proposals,
            issue_ids=[target_issue.issue_id],
            intent=CreationIntent(
                genre="武侠",
                themes=["成长"],
                tone="冷峻",
                protagonist_prompt="少年剑客",
                conflict_prompt="追查旧案",
                ending_preference="代价胜利",
                forbidden_elements=[],
                length_preference="3",
                target_experience="递进",
                variant_preference="",
            ),
            variant=ConceptVariant(
                variant_no=1,
                hook="少年剑客误入风暴",
                world_pitch="旧案引动暗流",
                main_arc_pitch="主角被迫卷入真相",
                ending_pitch="代价胜利",
            ),
            world=WorldBlueprint(setting_summary="旧案背后有江湖暗网。"),
            characters=[],
            llm=MockLLMClient(json_response={"story_arcs": []}),
        )

    applied_proposal = proposals[0].model_copy(update={"status": "applied"})
    with pytest.raises(ValueError, match="暂无新的修复方案"):
        orchestrator.plan_roadmap_repairs(
            book_id=1,
            story_arcs=story_arcs,
            roadmap=roadmap,
            roadmap_issues=issues,
            stored_proposals=[applied_proposal],
            issue_ids=[target_issue.issue_id],
            intent=CreationIntent(
                genre="武侠",
                themes=["成长"],
                tone="冷峻",
                protagonist_prompt="少年剑客",
                conflict_prompt="追查旧案",
                ending_preference="代价胜利",
                forbidden_elements=[],
                length_preference="3",
                target_experience="递进",
                variant_preference="",
            ),
            variant=ConceptVariant(
                variant_no=1,
                hook="少年剑客误入风暴",
                world_pitch="旧案引动暗流",
                main_arc_pitch="主角被迫卷入真相",
                ending_pitch="代价胜利",
            ),
            world=WorldBlueprint(setting_summary="旧案背后有江湖暗网。"),
            characters=[],
            llm=MockLLMClient(json_response={"story_arcs": []}),
        )


def test_reverify_keeps_waiting_roadmap_proposal_binding(tmp_db: Database) -> None:
    """重新复验后，已经挂在待确认提案上的 roadmap issue 仍应保留 awaiting_approval 状态。"""
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="复验状态保持测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="story_arcs_ready",
        current_step="roadmap",
        story_arcs_draft=[
            {
                "arc_number": 1,
                "title": "第一幕",
                "purpose": "卷入主线",
                "start_chapter": 1,
                "end_chapter": 2,
                "main_progress": ["让旧案从模糊传闻升级为可验证线索"],
                "relationship_progress": [],
                "loop_progress": [],
                "timeline_milestones": ["入秋初夜"],
                "arc_climax": "确认血脉与旧案存在直接关联",
            }
        ],
        roadmap_draft=[
            {
                "chapter_number": 1,
                "title": "旧案初现",
                "story_stage": "第一幕",
                "timeline_anchor": "入秋初夜",
                "depends_on_chapters": [],
                "goal": "卷入主线",
                "core_conflict": "主角不敢惊动师门",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次确认旧案并非巧合",
                "key_events": ["主角第一次看见残谱异动"],
                "chapter_tasks": [
                    {
                        "task_id": "trace-bloodline",
                        "summary": "确认主角血脉与残谱的联系",
                        "status": "in_progress",
                        "related_characters": ["林寒"],
                        "due_end_chapter": 2,
                    }
                ],
                "relationship_beats": [],
                "character_progress": ["林寒从旁观转向主动追查"],
                "relationship_progress": [],
                "new_reveals": ["残谱会对主角血脉产生共鸣"],
                "world_updates": [],
                "status_shift": ["主角不再只是旁观者"],
                "chapter_function": "开局",
                "anti_repeat_signature": "第一幕:卷入主线",
                "planned_loops": [
                    {
                        "loop_id": "loop-1",
                        "title": "残谱异动",
                        "summary": "残谱第一次在主角面前异动。",
                        "status": "open",
                        "priority": 1,
                        "due_start_chapter": 1,
                        "due_end_chapter": 2,
                        "related_characters": ["林寒"],
                        "resolution_requirements": ["解释残谱与血脉的关系"],
                    }
                ],
                "closure_function": "抛出下一章钩子",
            }
        ],
        expanded_arc_numbers=[],
    )

    issues_payload = client.get(f"/api/books/{book_id}/creative-issues").json()
    target_issue = next(item for item in issues_payload["items"] if item["issue_type"] == "task_status_jump")

    plan_payload = PlanCreativeRepairsUseCase(
        BlueprintContext(db=tmp_db, llm=MockLLMClient(), book_id=book_id, planner=RoadmapPlanner())
    ).execute([target_issue["issue_id"]]).model_dump(mode="json")
    assert plan_payload["creative_repair_proposals"][0]["status"] == "awaiting_approval"

    reverify_payload = ReverifyCreativeIssuesUseCase(
        BlueprintContext(db=tmp_db, llm=MockLLMClient(), book_id=book_id, planner=RoadmapPlanner())
    ).execute().model_dump(mode="json")
    reverified_issue = next(item for item in reverify_payload["creative_issues"] if item["issue_type"] == "task_status_jump")
    assert reverified_issue["status"] == "awaiting_approval"
    assert reverify_payload["creative_repair_proposals"][0]["status"] == "awaiting_approval"


def test_creative_issue_list_includes_pending_review_queue_item(tmp_db: Database) -> None:
    """待审阅 scene 会以只读 CreativeIssue 的方式进入统一控制面。"""
    client = _make_client(tmp_db)
    book_id = tmp_db.create_book(
        name="审阅队列接入测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    run_id = tmp_db.create_run_trace(
        task_id="review-creative-issue",
        book_id=book_id,
        status="running",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    review_id = tmp_db.create_scene_review(run_id, 3, 2, "场景存在设定冲突，需人工审阅")

    response = client.get(f"/api/books/{book_id}/creative-issues")
    assert response.status_code == 200
    payload = response.json()
    review_issue = next(item for item in payload["items"] if item["issue_id"] == f"review-issue-{review_id}")
    assert review_issue["source_layer"] == "review"
    assert review_issue["target_type"] == "scene_chapter"
    assert review_issue["repairability"] == "manual"
    assert review_issue["suggested_strategy"] == "scene_rewrite"
    assert "第 3 章第 2 场待审阅" in review_issue["message"]
    assert review_issue["context_payload"]["review_id"] == review_id
    assert review_issue["context_payload"]["run_id"] == run_id
    assert review_issue["context_payload"]["chapter_number"] == 3
    assert review_issue["context_payload"]["scene_number"] == 2
    assert review_issue["context_payload"]["review_status"] == "pending"
    assert review_issue["context_payload"]["reason"] == "场景存在设定冲突，需人工审阅"
    assert review_issue["context_payload"]["scene_status"] == "needs_review"
    assert review_issue["context_payload"]["event_count"] == 0


def test_review_issue_does_not_participate_in_roadmap_repair_planning(tmp_db: Database) -> None:
    """review 只读接入统一控制面，不应被 roadmap 修复提案链错误接管。"""
    book_id = tmp_db.create_book(
        name="只读审阅问题测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    run_id = tmp_db.create_run_trace(
        task_id="review-readonly-issue",
        book_id=book_id,
        status="running",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    tmp_db.upsert_book_blueprint_state(
        book_id,
        status="story_arcs_ready",
        current_step="roadmap",
        story_arcs_draft=[
            {
                "arc_number": 1,
                "title": "第一幕",
                "purpose": "卷入主线",
                "start_chapter": 1,
                "end_chapter": 1,
                "main_progress": ["把旧案从传闻推进到可验证线索"],
                "relationship_progress": [],
                "loop_progress": [],
                "timeline_milestones": ["入秋初夜"],
                "arc_climax": "确认旧案并非巧合",
            }
        ],
        roadmap_draft=[
            {
                "chapter_number": 1,
                "title": "旧案初现",
                "story_stage": "第一幕",
                "timeline_anchor": "入秋初夜",
                "depends_on_chapters": [],
                "goal": "卷入主线",
                "core_conflict": "主角不敢惊动师门",
                "turning_point": "残谱异动",
                "story_progress": "主角第一次确认旧案并非巧合",
                "key_events": ["主角第一次看见残谱异动"],
                "chapter_tasks": [],
                "relationship_beats": [],
                "character_progress": [],
                "relationship_progress": [],
                "new_reveals": [],
                "world_updates": [],
                "status_shift": [],
                "chapter_function": "开局",
                "anti_repeat_signature": "第一幕:卷入主线",
                "planned_loops": [],
                "closure_function": "抛出下一章钩子",
            }
        ],
        expanded_arc_numbers=[],
    )
    review_id = tmp_db.create_scene_review(run_id, 2, 1, "场景冲突需要人工判断")

    use_case = PlanCreativeRepairsUseCase(
        BlueprintContext(db=tmp_db, llm=MockLLMClient(), book_id=book_id, planner=RoadmapPlanner())
    )
    try:
        use_case.execute([f"review-issue-{review_id}"])
    except ValueError as exc:
        assert str(exc) == "当前没有可生成修复方案的问题。"
    else:
        raise AssertionError("review 只读问题不应该进入 roadmap 修复提案链。")


def test_reverify_keeps_pending_review_issue_visible(tmp_db: Database) -> None:
    """重新复验不会误删 review 只读问题，它仍然由 scene review 队列驱动。"""
    book_id = tmp_db.create_book(
        name="审阅问题复验保持测试",
        language="zh-CN",
        style_preset="literary_cn",
        style_prompt="",
        naming_policy="localized_zh",
        is_default=False,
    )
    run_id = tmp_db.create_run_trace(
        task_id="review-reverify-issue",
        book_id=book_id,
        status="running",
        config_snapshot={"mode": "scene"},
        llm_snapshot={"writer": "mock"},
    )
    review_id = tmp_db.create_scene_review(run_id, 4, 2, "当前 scene 需要人工审阅")

    payload = ReverifyCreativeIssuesUseCase(
        BlueprintContext(db=tmp_db, llm=MockLLMClient(), book_id=book_id, planner=RoadmapPlanner())
    ).execute().model_dump(mode="json")

    review_issue = next(item for item in payload["creative_issues"] if item["issue_id"] == f"review-issue-{review_id}")
    assert review_issue["source_layer"] == "review"
    assert review_issue["status"] == "open"
    assert review_issue["context_payload"]["chapter_number"] == 4
    assert review_issue["context_payload"]["scene_number"] == 2
