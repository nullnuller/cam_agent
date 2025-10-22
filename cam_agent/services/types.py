"""
Dataclasses describing CAM request/response payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class QueryRequest:
    """Incoming user query metadata."""

    user_id: str
    question: str
    session_id: Optional[str] = None
    channel: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelOutput:
    """Represents an LLM answer before compliance filtering."""

    text: str
    model: str
    prompt: str
    retrieval_context: str
    legend: str
    retrieved_hits: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ComplianceIssue:
    """Single compliance finding with severity."""

    severity: str  # e.g., "block", "warn", "info"
    message: str
    rule_id: str
    references: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ComplianceDecision:
    """Outcome from compliance evaluation."""

    action: str  # "allow", "warn", "block"
    issues: List[ComplianceIssue] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass(slots=True)
class CAMResponse:
    """Payload returned to users after compliance filtering."""

    final_text: str
    action: str
    issues: List[ComplianceIssue]
    raw_output: ModelOutput


__all__ = [
    "QueryRequest",
    "ModelOutput",
    "ComplianceIssue",
    "ComplianceDecision",
    "CAMResponse",
]

