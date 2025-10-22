"""
Dataclasses describing the event payloads consumed by the CAM UI layer.

These schemas provide a stable contract between the pipeline, any
streaming backend (e.g., WebSocket/SSE service), and the frontend
dashboard. They deliberately mirror the terminology used in the UI plan:
Runs contain Exchanges, and each Exchange is composed of timeline events
such as base LLM responses and judge verdicts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class EventSource:
    """Identifies the model/provider that produced an event payload."""

    model_id: str
    provider: str
    mode: Optional[str] = None  # e.g., "rag", "baseline", "judge"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserPromptEvent:
    """Initial user submission captured prior to model responses."""

    exchange_id: str
    turn_index: int
    source: EventSource
    created_at: datetime
    prompt_text: str
    prompt_redacted: Optional[str] = None
    question_category: Optional[str] = None


@dataclass(frozen=True)
class RunMetadata:
    """Describes a pipeline run shown in the UI."""

    run_id: str
    scenario_id: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ViolationDetail:
    """Captured classification for compliance or policy violations."""

    category: str
    severity: str
    violation_type: Optional[str] = None
    clause_reference: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class LLMResponseEvent:
    """Represents the base LLM answer recorded for an exchange."""

    exchange_id: str
    turn_index: int
    source: EventSource
    created_at: datetime
    prompt_chars: int
    completion_chars: int
    latency_ms: Optional[int] = None
    token_usage: Dict[str, int] = field(default_factory=dict)
    question_category: Optional[str] = None
    context_tokens: Optional[int] = None
    prompt_preview: Optional[str] = None
    pii_redacted_text: Optional[str] = None
    pii_raw_text: Optional[str] = None
    pii_fields: List[str] = field(default_factory=list)

    def redacted_message(self) -> Optional[str]:
        """Return the redacted body prioritising privacy-safe content."""
        return self.pii_redacted_text or self.pii_raw_text


@dataclass(frozen=True)
class JudgeVerdictEvent:
    """Encapsulates the judge model assessment for an exchange."""

    exchange_id: str
    turn_index: int
    source: EventSource
    created_at: datetime
    verdict: str  # e.g., allow/warn/block
    score: Optional[float] = None
    rationale_redacted: Optional[str] = None
    rationale_raw: Optional[str] = None
    violation: Optional[ViolationDetail] = None
    latency_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def redacted_rationale(self) -> Optional[str]:
        """Return the privacy-safe rationale."""
        return self.rationale_redacted or self.rationale_raw


@dataclass(frozen=True)
class MetricSnapshot:
    """Aggregate metrics tied to a run or window of exchanges."""

    run_id: str
    captured_at: datetime
    metrics: Dict[str, Any]
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    breakdowns: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class TimelineEvent:
    """Generic wrapper so the UI can render events chronologically."""

    run: RunMetadata
    exchange_id: str
    turn_index: int
    event_type: str  # "llm_response", "judge_verdict", "metric_snapshot", etc.
    payload: Dict[str, Any]
    created_at: datetime


def build_timeline_event(
    run: RunMetadata,
    exchange_id: str,
    turn_index: int,
    event_type: str,
    payload_obj: Any,
    created_at: Optional[datetime] = None,
) -> TimelineEvent:
    """
    Construct a TimelineEvent from a dataclass payload.

    Args:
        run: Metadata for the parent run.
        exchange_id: Identifier for the exchange the event belongs to.
        turn_index: Index of the user turn within the run.
        event_type: Enum-like string describing the payload.
        payload_obj: Dataclass or mapping to serialise.
        created_at: Optional override for timestamp (defaults to now).

    Returns:
        TimelineEvent: Normalised event ready for streaming or storage.
    """

    if is_dataclass(payload_obj):
        payload = asdict(payload_obj)
    elif isinstance(payload_obj, dict):
        payload = payload_obj
    else:
        raise TypeError(f"Unsupported payload type for timeline event: {type(payload_obj)!r}")

    timestamp = created_at or datetime.now(timezone.utc)

    return TimelineEvent(
        run=run,
        exchange_id=exchange_id,
        turn_index=turn_index,
        event_type=event_type,
        payload=payload,
        created_at=timestamp,
    )


__all__ = [
    "EventSource",
    "UserPromptEvent",
    "RunMetadata",
    "ViolationDetail",
    "LLMResponseEvent",
    "JudgeVerdictEvent",
    "MetricSnapshot",
    "TimelineEvent",
    "build_timeline_event",
]
