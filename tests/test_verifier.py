"""Tests for the ConsistencyVerifier."""

from __future__ import annotations

from poiesis.llm.base import LLMClient
from poiesis.verifier import ConsistencyVerifier, VerificationResult
from poiesis.world import WorldModel


class TestVerificationResult:
    """Tests for the VerificationResult dataclass."""

    def test_passed_result(self) -> None:
        result = VerificationResult(passed=True)
        assert result.passed is True
        assert result.violations == []
        assert result.warnings == []

    def test_failed_result_with_violations(self) -> None:
        result = VerificationResult(
            passed=False,
            violations=["Violated immutable rule: dead_stay_dead"],
            warnings=["Minor continuity concern"],
        )
        assert result.passed is False
        assert len(result.violations) == 1
        assert len(result.warnings) == 1


class TestConsistencyVerifierBudget:
    """Tests for the rule-based new-fact budget check."""

    def test_within_budget_no_violation(
        self, sample_world: WorldModel, mock_llm: LLMClient
    ) -> None:
        verifier = ConsistencyVerifier(new_rule_budget=3)
        changes = [
            {
                "change_type": "upsert",
                "entity_type": "world_rule",
                "entity_key": f"r{i}",
                "proposed_data": {},
            }
            for i in range(3)
        ]
        result = verifier.verify(1, "Content.", {}, sample_world, changes, mock_llm)
        assert result.passed is True

    def test_exceeds_budget_adds_violation(
        self, sample_world: WorldModel, mock_llm: LLMClient
    ) -> None:
        verifier = ConsistencyVerifier(new_rule_budget=2)
        changes = [
            {
                "change_type": "upsert",
                "entity_type": "world_rule",
                "entity_key": f"r{i}",
                "proposed_data": {},
            }
            for i in range(5)
        ]
        result = verifier.verify(1, "Content.", {}, sample_world, changes, mock_llm)
        assert result.passed is False
        assert any("budget" in v.lower() for v in result.violations)

    def test_character_upserts_do_not_count_as_rules(
        self, sample_world: WorldModel, mock_llm: LLMClient
    ) -> None:
        """Character changes should not count against the world-rule budget."""
        verifier = ConsistencyVerifier(new_rule_budget=1)
        changes = [
            {
                "change_type": "upsert",
                "entity_type": "character",
                "entity_key": f"char{i}",
                "proposed_data": {},
            }
            for i in range(5)
        ]
        result = verifier.verify(1, "Content.", {}, sample_world, changes, mock_llm)
        assert result.passed is True


class TestConsistencyVerifierLLM:
    """Tests for LLM-driven violation detection."""

    def test_llm_violations_cause_failure(
        self, sample_world: WorldModel
    ) -> None:
        """When the LLM returns violations, the result should fail."""
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "passed": False,
                "violations": ["Character resurrected despite dead_stay_dead rule."],
                "warnings": [],
            }
        )
        verifier = ConsistencyVerifier(new_rule_budget=5)
        result = verifier.verify(1, "Some content.", {}, sample_world, [], llm)
        assert result.passed is False
        assert "dead_stay_dead" in result.violations[0]

    def test_llm_warnings_do_not_fail(
        self, sample_world: WorldModel
    ) -> None:
        """LLM warnings alone should not cause the result to fail."""
        from tests.conftest import MockLLMClient

        llm = MockLLMClient(
            json_response={
                "passed": True,
                "violations": [],
                "warnings": ["Pacing is slow in this section."],
            }
        )
        verifier = ConsistencyVerifier(new_rule_budget=5)
        result = verifier.verify(1, "Content.", {}, sample_world, [], llm)
        assert result.passed is True
        assert len(result.warnings) == 1

    def test_passing_verification(
        self, sample_world: WorldModel, mock_llm: LLMClient
    ) -> None:
        """A chapter with no issues should pass verification."""
        verifier = ConsistencyVerifier(new_rule_budget=5)
        result = verifier.verify(1, "A chapter with no issues.", {}, sample_world, [], mock_llm)
        assert result.passed is True
        assert result.violations == []
