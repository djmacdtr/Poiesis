"""Contract normalization tests for phase-1 structured trace schemas."""

from __future__ import annotations

from poiesis.application.contracts import (
    ChangeSet,
    PlannerOutput,
    VerifierIssue,
    normalize_changeset,
    normalize_planner_output,
)


def test_normalize_planner_output_preserves_legacy_fields() -> None:
    payload = {
        "title": "第一章",
        "summary": "主角第一次出发",
        "key_events": ["离开村庄"],
        "foreshadowing_hints": ["黑塔"],
        "tone": "克制",
    }

    normalized = normalize_planner_output(payload)

    assert isinstance(normalized, PlannerOutput)
    assert normalized.title == "第一章"
    assert normalized.chapter_goal == "主角第一次出发"
    assert normalized.must_preserve == ["离开村庄"]
    assert normalized.must_progress_loops == ["黑塔"]
    assert normalized.to_runtime_plan()["summary"] == "主角第一次出发"


def test_normalize_changeset_groups_staging_changes() -> None:
    changes = [
        {"entity_type": "character", "entity_key": "A"},
        {"entity_type": "world_rule", "entity_key": "R1"},
        {"entity_type": "timeline_event", "entity_key": "E1"},
        {"entity_type": "foreshadowing", "entity_key": "F1"},
    ]

    normalized = normalize_changeset(changes)

    assert isinstance(normalized, ChangeSet)
    assert len(normalized.characters) == 1
    assert len(normalized.world_rules) == 1
    assert len(normalized.timeline_events) == 1
    assert len(normalized.foreshadowing_updates) == 1
    assert normalized.all_changes() == changes


def test_verifier_issue_serializes_round_trip() -> None:
    issue = VerifierIssue(
        severity="fatal",
        type="canon",
        reason="角色设定冲突",
        repair_hint="修正人物已知状态",
        location="chapter:1",
    )

    payload = issue.model_dump(mode="json")
    restored = VerifierIssue.model_validate(payload)

    assert restored == issue
