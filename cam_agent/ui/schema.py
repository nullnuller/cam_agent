"""
JSON schema helpers for the CAM UI event payloads.

These definitions keep the backend and frontend in sync by providing a
single source of truth for the structure of timeline events and related
objects. Serialisation utilities convert the dataclasses defined in
`cam_agent.ui.events` into JSON-friendly dictionaries (ISO 8601
timestamps, nested objects flattened to primitives) suitable for REST or
WebSocket payloads.
"""

from __future__ import annotations

from dataclasses import is_dataclass
from datetime import datetime
from typing import Any, Dict

from .events import (
    EventSource,
    JudgeVerdictEvent,
    LLMResponseEvent,
    MetricSnapshot,
    RunMetadata,
    TimelineEvent,
    UserPromptEvent,
    ViolationDetail,
)


def _to_isoformat(value: datetime) -> str:
    """Return an ISO 8601 string (UTC) for the given datetime."""
    if value.tzinfo:
        return value.astimezone().isoformat()
    return value.isoformat() + "Z"


def _serialize(obj: Any) -> Any:
    """
    Recursively serialise dataclasses, converting datetimes to strings.

    This keeps payloads JSON-compatible without requiring frontend
    consumers to understand Python-specific types.
    """
    if isinstance(obj, datetime):
        return _to_isoformat(obj)
    if is_dataclass(obj):
        return {key: _serialize(getattr(obj, key)) for key in obj.__dataclass_fields__}
    if isinstance(obj, dict):
        return {key: _serialize(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    return obj


def serialize_timeline_event(event: TimelineEvent) -> Dict[str, Any]:
    """
    Convert a TimelineEvent dataclass into a JSON-compatible dict.

    Args:
        event: TimelineEvent produced by `build_timeline_event`.

    Returns:
        dict: Payload ready for JSON encoding.
    """

    return _serialize(event)


def serialize_run_metadata(run: RunMetadata) -> Dict[str, Any]:
    """Serialise RunMetadata to primitive dict."""

    return _serialize(run)


def get_timeline_event_schema() -> Dict[str, Any]:
    """
    Return the JSON Schema definition for a timeline event payload.

    The schema tracks nested objects for run metadata, event sources, and
    judgement details so that both REST and WebSocket APIs can validate
    outbound messages.
    """

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://cam-agent/schema/timeline-event.json",
        "title": "CAMTimelineEvent",
        "type": "object",
        "required": ["run", "exchange_id", "turn_index", "event_type", "payload", "created_at"],
        "properties": {
            "run": {
                "type": "object",
                "required": ["run_id", "started_at"],
                "properties": {
                    "run_id": {"type": "string"},
                    "scenario_id": {"type": ["string", "null"]},
                    "started_at": {"type": "string", "format": "date-time"},
                    "tags": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "default": {},
                    },
                },
                "additionalProperties": False,
            },
            "exchange_id": {"type": "string"},
            "turn_index": {"type": "integer", "minimum": 0},
            "event_type": {"type": "string"},
            "payload": {"type": "object"},
            "created_at": {"type": "string", "format": "date-time"},
        },
        "additionalProperties": False,
        "definitions": {
            "EventSource": {
                "type": "object",
                "required": ["model_id", "provider"],
                "properties": {
                    "model_id": {"type": "string"},
                    "provider": {"type": "string"},
                    "mode": {"type": ["string", "null"]},
                    "metadata": {
                        "type": "object",
                        "additionalProperties": True,
                        "default": {},
                    },
                },
                "additionalProperties": False,
            },
            "ViolationDetail": {
                "type": "object",
                "required": ["category", "severity"],
                "properties": {
                    "category": {"type": "string"},
                    "severity": {"type": "string"},
                    "violation_type": {"type": ["string", "null"]},
                    "clause_reference": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    }


__all__ = [
    "serialize_timeline_event",
    "serialize_run_metadata",
    "get_timeline_event_schema",
    # Re-export dataclasses for callers that only import schema helpers.
    "EventSource",
    "UserPromptEvent",
    "LLMResponseEvent",
    "JudgeVerdictEvent",
    "MetricSnapshot",
    "RunMetadata",
    "TimelineEvent",
    "ViolationDetail",
]
