"""VerifierHub 聚合行为测试。"""

from __future__ import annotations

from poiesis.domain.world.model import WorldModel
from poiesis.pipeline.verification.hub import VerifierHub
from poiesis.pipeline.verification.result import VerificationResult


class TestVerificationResult:
    """结果类型基础测试。"""

    def test_passed_result(self) -> None:
        result = VerificationResult(passed=True)
        assert result.passed is True
        assert result.violations == []
        assert result.warnings == []


class TestVerifierHubBudget:
    """预算校验测试。"""

    def test_within_budget_no_violation(self, sample_world: WorldModel, mock_llm) -> None:
        verifier = VerifierHub(new_rule_budget=3)
        changes = [
            {"change_type": "upsert", "entity_type": "world_rule", "entity_key": f"r{i}", "proposed_data": {}}
            for i in range(3)
        ]
        result = verifier.verify(1, "Content.", {}, sample_world, changes, mock_llm)
        assert result.passed is True

    def test_exceeds_budget_adds_violation(self, sample_world: WorldModel, mock_llm) -> None:
        verifier = VerifierHub(new_rule_budget=2)
        changes = [
            {"change_type": "upsert", "entity_type": "world_rule", "entity_key": f"r{i}", "proposed_data": {}}
            for i in range(5)
        ]
        result = verifier.verify(1, "Content.", {}, sample_world, changes, mock_llm)
        assert result.passed is False
        assert any("budget" in issue.reason.lower() for issue in result.issues)


class TestVerifierHubSemantic:
    """LLM 语义校验测试。"""

    def test_llm_violations_cause_failure(self, sample_world: WorldModel) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "passed": False,
                "violations": ["Character resurrected despite dead_stay_dead rule."],
                "warnings": [],
            }
        )
        result = VerifierHub(new_rule_budget=5).verify(1, "Some content.", {}, sample_world, [], llm)
        assert result.passed is False
        assert "dead_stay_dead" in result.violations[0]

    def test_llm_warnings_do_not_fail(self, sample_world: WorldModel) -> None:
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "passed": True,
                "violations": [],
                "warnings": ["Pacing is slow in this section."],
            }
        )
        result = VerifierHub(new_rule_budget=5).verify(1, "Content.", {}, sample_world, [], llm)
        assert result.passed is True
        assert len(result.warnings) == 1
