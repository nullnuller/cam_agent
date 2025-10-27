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
    run_id: str | None = None
    scenario_id: str | None = None
    turn_index: int | None = None
    exchange_id: str | None = None
    run_tags: Dict[str, Any] | None = None


class JsonlAuditLogger:
    """Append-only JSONL logger for CAM interactions."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, request: QueryRequest, response: CAMResponse, metadata: Dict[str, Any] | None = None) -> None:
        meta = dict(metadata or {})
        run_id = meta.get("run_id")
        scenario_id = meta.get("scenario_id")
        turn_index = meta.get("turn_index")
        exchange_id = meta.get("exchange_id")
        run_tags = meta.get("run_tags") if isinstance(meta.get("run_tags"), dict) else None

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
            metadata=meta,
            run_id=str(run_id) if run_id else None,
            scenario_id=str(scenario_id) if scenario_id else None,
            turn_index=int(turn_index) if isinstance(turn_index, (int, float)) else None,
            exchange_id=str(exchange_id) if exchange_id else None,
            run_tags=run_tags,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def log_judge_results(
        self,
        request: QueryRequest,
        *,
        scenario_id: str | None,
        cam_action: str,
        judge_results: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """Append an audit record capturing external judge outcomes."""

        meta = dict(metadata or {})
        payload: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": request.user_id,
            "session_id": request.session_id,
            "channel": request.channel,
            "question": request.question,
            "scenario_id": scenario_id,
            "action": cam_action,
            "event_type": "external_judge",
            "judge_results": judge_results,
            "metadata": meta,
        }
        run_id = meta.get("run_id")
        if run_id:
            payload["run_id"] = str(run_id)
        turn_index = meta.get("turn_index")
        if isinstance(turn_index, (int, float)):
            payload["turn_index"] = int(turn_index)
        exchange_id = meta.get("exchange_id")
        if exchange_id:
            payload["exchange_id"] = str(exchange_id)
        run_tags = meta.get("run_tags")
        if isinstance(run_tags, dict):
            payload["run_tags"] = run_tags
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


__all__ = ["JsonlAuditLogger"]
