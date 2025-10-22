"""
Metrics computation for CAM evaluations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, Iterable, List, Optional


@dataclass(slots=True)
class JudgeAggregate:
    """Stores judge scores for aggregation."""

    helpfulness_scores: List[float] = field(default_factory=list)
    compliance_scores: List[float] = field(default_factory=list)
    rationales: List[str] = field(default_factory=list)

    def add(self, helpfulness: Optional[float], compliance: Optional[float], rationale: Optional[str] = None) -> None:
        if helpfulness is not None:
            self.helpfulness_scores.append(helpfulness)
        if compliance is not None:
            self.compliance_scores.append(compliance)
        if rationale:
            self.rationales.append(rationale)

    def as_dict(self) -> Dict[str, object]:
        passes = [score for score in self.compliance_scores if score is not None and score >= 4.0]
        return {
            "count": max(len(self.helpfulness_scores), len(self.compliance_scores)),
            "avg_helpfulness": mean(self.helpfulness_scores) if self.helpfulness_scores else None,
            "avg_compliance": mean(self.compliance_scores) if self.compliance_scores else None,
            "compliance_pass_rate": (len(passes) / len(self.compliance_scores)) if self.compliance_scores else None,
            "rationales": self.rationales,
        }


@dataclass(slots=True)
class ScenarioMetrics:
    """Aggregated metrics for a single scenario."""

    total_questions: int = 0
    compliance_allow: int = 0
    compliance_warn: int = 0
    compliance_block: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    judge_aggregates: Dict[str, JudgeAggregate] = field(default_factory=dict)
    rag_questions: int = 0
    rag_with_citation: int = 0

    def as_dict(self) -> Dict[str, object]:
        avg_latency = mean(self.latencies_ms) if self.latencies_ms else None
        all_helpfulness = [
            score for agg in self.judge_aggregates.values() for score in agg.helpfulness_scores
        ]
        all_compliance = [
            score for agg in self.judge_aggregates.values() for score in agg.compliance_scores
        ]
        return {
            "total_questions": self.total_questions,
            "compliance_allow": self.compliance_allow,
            "compliance_warn": self.compliance_warn,
            "compliance_block": self.compliance_block,
            "warn_rate": self.compliance_warn / self.total_questions if self.total_questions else 0.0,
            "block_rate": self.compliance_block / self.total_questions if self.total_questions else 0.0,
            "avg_judge_helpfulness": mean(all_helpfulness) if all_helpfulness else None,
            "avg_judge_compliance": mean(all_compliance) if all_compliance else None,
            "avg_latency_ms": avg_latency,
            "citation_success_rate": (self.rag_with_citation / self.rag_questions) if self.rag_questions else None,
            "judges": {judge_id: agg.as_dict() for judge_id, agg in self.judge_aggregates.items()},
        }


def update_compliance_counts(metrics: ScenarioMetrics, action: str) -> None:
    metrics.total_questions += 1
    if action == "allow":
        metrics.compliance_allow += 1
    elif action == "warn":
        metrics.compliance_warn += 1
    elif action == "block":
        metrics.compliance_block += 1


def add_judge_scores(
    metrics: ScenarioMetrics,
    judge_id: str,
    *,
    helpfulness: Optional[float],
    compliance: Optional[float],
    rationale: Optional[str] = None,
) -> None:
    aggregate = metrics.judge_aggregates.setdefault(judge_id, JudgeAggregate())
    aggregate.add(helpfulness, compliance, rationale)


def record_latency(metrics: ScenarioMetrics, latency_ms: float) -> None:
    metrics.latencies_ms.append(latency_ms)


def record_citation(metrics: ScenarioMetrics, *, rag_used: bool, has_citation: bool) -> None:
    if rag_used:
        metrics.rag_questions += 1
        if has_citation:
            metrics.rag_with_citation += 1


__all__ = [
    "JudgeAggregate",
    "ScenarioMetrics",
    "update_compliance_counts",
    "add_judge_scores",
    "record_latency",
    "record_citation",
]
