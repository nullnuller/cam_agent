"""
Support utilities for the frontend UI layer.

This package exposes shared event schemas and helpers that backend
services can reuse when streaming CAM interactions to the dashboard.
"""

from .events import (
    EventSource,
    JudgeVerdictEvent,
    LLMResponseEvent,
    MetricSnapshot,
    RunMetadata,
    TimelineEvent,
    ViolationDetail,
    build_timeline_event,
)
from .history import AuditLogHistoricalRunLoader
from .schema import (
    get_timeline_event_schema,
    serialize_run_metadata,
    serialize_timeline_event,
)

__all__ = [
    "EventSource",
    "JudgeVerdictEvent",
    "LLMResponseEvent",
    "MetricSnapshot",
    "RunMetadata",
    "TimelineEvent",
    "ViolationDetail",
    "build_timeline_event",
    "get_timeline_event_schema",
    "serialize_run_metadata",
    "serialize_timeline_event",
    "AuditLogHistoricalRunLoader",
]
