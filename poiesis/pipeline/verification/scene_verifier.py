"""Scene 校验器。"""

from __future__ import annotations

from poiesis.application.scene_contracts import ChangeSet, ScenePlan, VerifierIssue
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient
from poiesis.pipeline.verification.hub import VerifierHub


class SceneVerifier:
    """把现有 verifier 结果统一收口为 scene 级 issues。"""

    def __init__(self, verifier_hub: VerifierHub) -> None:
        self._verifier_hub = verifier_hub

    def verify(
        self,
        scene_plan: ScenePlan,
        content: str,
        chapter_plan: dict[str, object],
        world: WorldModel,
        changeset: ChangeSet,
        llm: LLMClient,
    ) -> list[VerifierIssue]:
        result = self._verifier_hub.verify(
            chapter_number=scene_plan.chapter_number,
            content=content,
            plan={**chapter_plan, "scene_goal": scene_plan.goal, "scene_title": scene_plan.title},
            world=world,
            proposed_changes=changeset.raw_changes,
            llm=llm,
        )
        return [
            VerifierIssue(
                severity=issue.severity,
                type=issue.type,
                reason=issue.reason,
                repair_hint=issue.repair_hint,
                location=issue.location,
            )
            for issue in result.issues
        ]
