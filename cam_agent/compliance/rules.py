"""
Simple rule-based compliance engine for CAM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from cam_agent.services.types import ComplianceDecision, ComplianceIssue, ModelOutput, QueryRequest


@dataclass(slots=True)
class ComplianceRule:
    """Pattern-based compliance rule."""

    rule_id: str
    description: str
    pattern: re.Pattern[str]
    severity: str  # "block" or "warn"
    message: str

    def matches(self, text: str) -> bool:
        return bool(self.pattern.search(text))


# Illustrative rules; expand with regulation-backed checks over time.
RULES: Tuple[ComplianceRule, ...] = (
    ComplianceRule(
        rule_id="safety.no_suicide_instructions",
        description="Block content giving self-harm instructions.",
        pattern=re.compile(r"\b(harm yourself|kill yourself|suicide\s+plan)\b", re.IGNORECASE),
        severity="block",
        message="Detected potential self-harm instruction. This response must be withheld.",
    ),
    ComplianceRule(
        rule_id="safety.medication_directive",
        description="Warn when model prescribes or stops medication outright.",
        pattern=re.compile(r"\b(stop|start|change)\s+(?:taking|using)\s+.*medicine", re.IGNORECASE),
        severity="warn",
        message="Possible directive regarding medication. Recommend signposting medical consultation.",
    ),
    ComplianceRule(
        rule_id="compliance.disclaimer_missing",
        description="Warn if no disclaimer acknowledging informational intent.",
        pattern=re.compile(r".*"),
        severity="warn",
        message="Response lacks an informational disclaimer reminding users to seek professional advice.",
    ),
)


DISCLAIMER_HINT = (
    "This information is general guidance only and does not replace advice from your treating professionals."
)


def _evaluate_disclaimer(output_text: str) -> bool:
    """Heuristic check for presence of a disclaimer sentence."""
    disclaimer_patterns = (
        r"does not replace (?:a )?licensed (?:professional|psychologist|doctor)",
        r"seek professional (?:help|advice)",
        r"is general information only",
    )
    return any(re.search(pat, output_text, flags=re.IGNORECASE) for pat in disclaimer_patterns)


def evaluate_compliance(
    request: QueryRequest,
    model_output: ModelOutput,
    *,
    rules: Iterable[ComplianceRule] = RULES,
) -> ComplianceDecision:
    """Run rule-based checks against an LLM output."""

    issues: List[ComplianceIssue] = []

    for rule in rules:
        if rule.rule_id == "compliance.disclaimer_missing":
            if _evaluate_disclaimer(model_output.text):
                continue
            issues.append(
                ComplianceIssue(
                    severity=rule.severity,
                    message=rule.message,
                    rule_id=rule.rule_id,
                    references=[],
                )
            )
            continue

        if rule.matches(model_output.text):
            issues.append(
                ComplianceIssue(
                    severity=rule.severity,
                    message=rule.message,
                    rule_id=rule.rule_id,
                    references=[],
                )
            )

    if any(issue.severity == "block" for issue in issues):
        action = "block"
    elif any(issue.severity == "warn" for issue in issues):
        action = "warn"
    else:
        action = "allow"

    return ComplianceDecision(action=action, issues=issues)


__all__ = ["ComplianceRule", "evaluate_compliance", "DISCLAIMER_HINT", "RULES"]

