"""校验子系统的公共结果类型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from poiesis.application.contracts import VerifierIssue


@dataclass
class VerificationResult:
    """兼容层结果，同时暴露新结构化 issues。"""

    passed: bool
    issues: list[VerifierIssue] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
