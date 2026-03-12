"""创作蓝图工作台 API 测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from poiesis.api.main import app
from poiesis.application.blueprint_contracts import ConceptVariant, CreationIntent
from poiesis.application.blueprint_use_cases import BlueprintContext
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


def test_blueprint_creation_flow_can_lock_book_blueprint(tmp_db: Database, monkeypatch) -> None:
    """从创作意图到整书蓝图锁定，应形成完整的工作流。"""
    from poiesis.api.services import blueprint_service

    def _fake_context(config_path: str, db: Database, book_id: int) -> BlueprintContext:  # noqa: ARG001
        return BlueprintContext(
            db=db,
            llm=MockLLMClient(json_response={}),
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

    roadmap_resp = client.post(
        f"/api/books/{book_id}/blueprint/roadmap:generate",
        json={"feedback": "前三章开局更强"},
    )
    assert roadmap_resp.status_code == 200
    assert roadmap_resp.json()["status"] == "roadmap_ready"

    confirm_roadmap = client.post(f"/api/books/{book_id}/blueprint/roadmap:confirm", json={})
    assert confirm_roadmap.status_code == 200
    assert confirm_roadmap.json()["status"] == "locked"
    assert confirm_roadmap.json()["active_revision_id"] is not None

    detail = client.get(f"/api/books/{book_id}/blueprint")
    assert detail.status_code == 200
    assert detail.json()["roadmap_confirmed"]
    assert detail.json()["revisions"][0]["is_active"] is True


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
