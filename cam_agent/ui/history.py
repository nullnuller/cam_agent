"""
Utilities for replaying CAM runs from stored audit logs.

The classes defined here adapt raw pipeline outputs (e.g., JSONL audit
records) into the normalised timeline event schema consumed by the UI.
While the current implementation targets the existing
`project_bundle/cam_suite_audit.jsonl` format, the abstraction keeps the
door open for database-backed loaders in future iterations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from .events import (
    EventSource,
    JudgeVerdictEvent,
    LLMResponseEvent,
    RunMetadata,
    TimelineEvent,
    ViolationDetail,
    build_timeline_event,
)


def _parse_timestamp(value: Optional[str]) -> datetime:
    """Parse ISO 8601 timestamps emitted by the pipeline."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _truncate_preview(text: str, limit: int = 400) -> str:
    """Return a trimmed preview string suitable for UI display."""
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rstrip()
    return f"{trimmed}…"


@dataclass
class AuditLogHistoricalRunLoader:
    """
    Read CAM audit JSONL files and yield timeline events.

    Each line should contain a JSON object with at least the following
    fields: `run_id`, `exchange_id` (or `question_id`), `turn_index`,
    `timestamp`, and optionally `event_type`. Additional fields are
    preserved in the payload for downstream consumers.
    """

    path: Path
    _run_cache: Dict[str, RunMetadata] = field(default_factory=dict, init=False, repr=False)

    def iter_timeline_events(self, run_id: str) -> Iterator[TimelineEvent]:
        """
        Stream timeline events for the requested run.

        Args:
            run_id: Identifier as captured in the audit log.

        Yields:
            TimelineEvent objects ready for serialisation.
        """

        turn_counter = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record_run_id = self._extract_run_id(record)
                if record_run_id != run_id:
                    continue
                _, actual_turn, events = self.build_events_from_raw_record(
                    record=record,
                    fallback_turn_index=turn_counter,
                )
                for event in events:
                    yield event
                turn_counter = actual_turn + 1

    def iter_runs(self) -> Iterable[RunMetadata]:
        """
        Iterate through unique run metadata found in the audit log.

        Returns:
            Iterable of RunMetadata entries in discovery order.
        """

        seen = set()
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                run_id = self._extract_run_id(record)
                if not run_id or run_id in seen:
                    continue
                seen.add(run_id)

                started_at = _parse_timestamp(record.get("timestamp"))
                scenario_id = record.get("scenario_id")
                tags = record.get("run_tags") or {}

                meta = RunMetadata(
                    run_id=str(run_id),
                    scenario_id=scenario_id,
                    started_at=started_at,
                    tags=tags if isinstance(tags, dict) else {},
                )
                self._run_cache[meta.run_id] = meta
                yield meta

    def _build_run_metadata(self, run_id: str) -> Optional[RunMetadata]:
        """Locate the first record for a run to seed metadata."""
        cached = self._run_cache.get(run_id)
        if cached:
            return cached
        for meta in self.iter_runs():
            if meta.run_id == run_id:
                self._run_cache[run_id] = meta
                return meta
        return None

    def _resolve_run_metadata_from_record(
        self,
        run_id: str,
        record: dict,
        timestamp: datetime,
    ) -> RunMetadata:
        """Ensure metadata exists for a run, seeding from the record when missing."""

        cached = self._run_cache.get(run_id)
        if cached:
            return cached

        scenario_id = record.get("scenario_id")
        tags = record.get("run_tags") if isinstance(record.get("run_tags"), dict) else {}

        metadata = RunMetadata(
            run_id=str(run_id),
            scenario_id=scenario_id,
            started_at=timestamp,
            tags=tags,
        )
        self._run_cache[metadata.run_id] = metadata
        return metadata

    def build_events_from_raw_record(
        self,
        record: dict,
        fallback_turn_index: int = 0,
    ) -> tuple[str, int, List[TimelineEvent]]:
        """
        Convert a raw audit record into timeline events.

        Returns:
            Tuple containing (run_id, turn_index_used, [TimelineEvent, ...]).
        """

        run_id = self._extract_run_id(record)
        timestamp = _parse_timestamp(record.get("timestamp"))
        exchange_id = (
            record.get("exchange_id")
            or record.get("question_id")
            or f"{run_id}-turn-{fallback_turn_index}"
        )
        turn_index = int(record.get("turn_index", fallback_turn_index))
        event_type = record.get("event_type") or "audit_record"

        run_meta = self._resolve_run_metadata_from_record(
            run_id=run_id,
            record=record,
            timestamp=timestamp,
        )

        events = self._events_from_record(
            run=run_meta,
            exchange_id=str(exchange_id),
            turn_index=turn_index,
            record=record,
            created_at=timestamp,
            event_type=event_type,
        )

        return run_id, turn_index, events

    @staticmethod
    def _extract_run_id(record: dict) -> str:
        """
        Determine the run identifier using fallbacks for legacy audit logs.

        Preference order:
        1. Explicit `run_id`
        2. Combined user/session (`{user_id}-{session_id}`)
        3. Session id
        4. User id
        """

        run_id = record.get("run_id")
        if run_id:
            return str(run_id)

        user_id = record.get("user_id")
        session_id = record.get("session_id") or record.get("session")
        if user_id and session_id:
            return f"{user_id}-{session_id}"
        if session_id:
            return str(session_id)
        if user_id:
            return str(user_id)
        return "unknown-run"

    def _events_from_record(
        self,
        run: RunMetadata,
        exchange_id: str,
        turn_index: int,
        record: dict,
        created_at: datetime,
        event_type: str,
    ) -> List[TimelineEvent]:
        """Construct timeline events derived from a single audit record."""

        events: List[TimelineEvent] = []

        llm_event = self._build_llm_response(
            run=run,
            exchange_id=exchange_id,
            turn_index=turn_index,
            record=record,
            created_at=created_at,
        )
        if llm_event:
            events.append(llm_event)

        judge_events = list(
            self._build_judge_events(
                run=run,
                exchange_id=exchange_id,
                turn_index=turn_index,
                record=record,
                created_at=created_at,
            )
        )
        events.extend(judge_events)

        if events:
            return events

        payload = dict(record)
        payload.pop("run_id", None)
        payload.pop("turn_index", None)
        payload.pop("timestamp", None)

        events.append(
            build_timeline_event(
                run=run,
                exchange_id=exchange_id,
                turn_index=turn_index,
                event_type=event_type,
                payload_obj=payload,
                created_at=created_at,
            )
        )

        return events

    def _build_llm_response(
        self,
        run: RunMetadata,
        exchange_id: str,
        turn_index: int,
        record: dict,
        created_at: datetime,
    ) -> Optional[TimelineEvent]:
        """Convert a raw audit record into an LLM response timeline event."""

        raw_model = record.get("raw_model") or {}
        final_text = record.get("final_text")
        if not raw_model and not final_text:
            return None

        model_id = str(raw_model.get("model") or record.get("model") or "unknown-model")
        provider = record.get("model_provider") or "pipeline"
        mode = record.get("mode") or record.get("route")

        source = EventSource(
            model_id=model_id,
            provider=provider,
            mode=mode,
            metadata={
                "scenario": record.get("scenario_id"),
                "channel": record.get("channel"),
            },
        )

        prompt_text = str(raw_model.get("prompt") or record.get("question") or "")
        raw_completion = raw_model.get("text")
        completion_text = str(raw_completion or final_text or "")
        prompt_preview_raw = record.get("question") or prompt_text
        prompt_preview = str(prompt_preview_raw) if prompt_preview_raw is not None else None
        redacted_text = str(final_text or completion_text)
        raw_text = str(raw_completion) if isinstance(raw_completion, str) else None

        payload = LLMResponseEvent(
            exchange_id=exchange_id,
            turn_index=turn_index,
            source=source,
            created_at=created_at,
            prompt_chars=len(prompt_text),
            completion_chars=len(completion_text),
            latency_ms=record.get("latency_ms"),
            token_usage=record.get("token_usage") or {},
            question_category=record.get("question_category"),
            context_tokens=(record.get("context_tokens") or record.get("context_length")),
            prompt_preview=_truncate_preview(prompt_preview) if prompt_preview else None,
            pii_redacted_text=redacted_text,
            pii_raw_text=raw_text,
            pii_fields=record.get("pii_fields") or [],
        )

        return build_timeline_event(
            run=run,
            exchange_id=exchange_id,
            turn_index=turn_index,
            event_type="llm_response",
            payload_obj=payload,
            created_at=created_at,
        )

    def _build_judge_events(
        self,
        run: RunMetadata,
        exchange_id: str,
        turn_index: int,
        record: dict,
        created_at: datetime,
    ) -> Iterable[TimelineEvent]:
        """Yield judge verdict events based on compliance issues in the record."""

        issues = record.get("issues") or []
        if not isinstance(issues, list) or not issues:
            return

        verdict = str(record.get("action") or "allow").lower()
        judge_model = record.get("judge_model") or record.get("judge") or "cam.compliance"
        judge_provider = record.get("judge_provider") or "cam-agent"

        for index, issue in enumerate(issues):
            severity = str(issue.get("severity") or "warn").lower()
            if severity == "error":
                severity = "block"
            if severity not in {"info", "warn", "block"}:
                severity = "warn"

            violation = ViolationDetail(
                category=str(issue.get("rule_id") or "policy_violation"),
                severity=severity,
                violation_type=issue.get("violation_type") or issue.get("category"),
                clause_reference=issue.get("clause") or issue.get("reference"),
                description=issue.get("message"),
            )

            source = EventSource(
                model_id=str(judge_model),
                provider=str(judge_provider),
                mode="judge",
                metadata={"issue_index": index},
            )

            payload = JudgeVerdictEvent(
                exchange_id=exchange_id,
                turn_index=turn_index,
                source=source,
                created_at=created_at,
                verdict=verdict,
                score=issue.get("score"),
                rationale_redacted=issue.get("message"),
                violation=violation,
                latency_ms=issue.get("latency_ms"),
                metadata={
                    "references": issue.get("references"),
                },
            )

            yield build_timeline_event(
                run=run,
                exchange_id=exchange_id,
                turn_index=turn_index,
                event_type="judge_verdict",
                payload_obj=payload,
                created_at=created_at,
            )
