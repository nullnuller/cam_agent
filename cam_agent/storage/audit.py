"""
Audit logging utilities for CAM.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from cam_agent.services.types import CAMResponse, QueryRequest


@dataclass(slots=True)
class AuditRecord:
    """Structured log entry for a CAM interaction."""

    timestamp: str
    user_id: str
    session_id: str | None
    channel: str | None
    question: str
    action: str
    issues: list[dict[str, Any]]
    raw_model: dict[str, Any]
    final_text: str
    metadata: Dict[str, Any]


class JsonlAuditLogger:
    """Append-only JSONL logger for CAM interactions."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, request: QueryRequest, response: CAMResponse, metadata: Dict[str, Any] | None = None) -> None:
        record = AuditRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=request.user_id,
            session_id=request.session_id,
            channel=request.channel,
            question=request.question,
            action=response.action,
            issues=[asdict(issue) for issue in response.issues],
            raw_model={
                "model": response.raw_output.model,
                "prompt": response.raw_output.prompt,
                "text": response.raw_output.text,
                "retrieval_context": response.raw_output.retrieval_context,
                "legend": response.raw_output.legend,
                "retrieved_hits": response.raw_output.retrieved_hits,
                "metadata": response.raw_output.metadata,
            },
            final_text=response.final_text,
            metadata=metadata or {},
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


__all__ = ["JsonlAuditLogger"]

