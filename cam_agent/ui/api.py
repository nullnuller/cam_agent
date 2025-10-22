"""
FastAPI application exposing CAM UI timeline endpoints.

This lightweight service reads the existing audit JSONL output from the
pipeline and serves it via REST, using the event schemas defined in this
package. It is intentionally stateless so it can run alongside the
pipeline for local demos or be deployed separately for the dashboard.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("cam_agent.ui.api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

from cam_agent.evaluation.config import default_scenarios, describe_scenario
from cam_agent.evaluation.judges import JudgeManager, build_default_judges, resolve_judge_llm_config
from cam_agent.services import CAMAgent, QueryRequest
from cam_agent.ui.events import (
    EventSource,
    JudgeVerdictEvent,
    RunMetadata,
    TimelineEvent,
    UserPromptEvent,
    ViolationDetail,
    build_timeline_event,
)

from .history import AuditLogHistoricalRunLoader
from .schema import serialize_run_metadata, serialize_timeline_event

DEFAULT_AUDIT_PATH = Path("project_bundle/cam_suite_audit.jsonl")
DEFAULT_REVEAL_LOG_PATH = Path("project_bundle/cam_ui_reveals.jsonl")
DEFAULT_STORE_DIR = Path("project_bundle/rag_store")
DEFAULT_DIGEST_PATH = Path("project_bundle/regulatory_digest.md")


def _normalize_event_timestamp(event: TimelineEvent) -> datetime:
    """Convert event timestamps to timezone-aware UTC for ordering."""

    created_at = event.created_at
    if created_at.tzinfo is None:
        return created_at.replace(tzinfo=timezone.utc)
    return created_at.astimezone(timezone.utc)


class ConsoleOptionsResponse(BaseModel):
    scenarios: List[Dict[str, Any]]
    judges: List[Dict[str, Any]]


class PromptRequest(BaseModel):
    prompt: str
    scenario_id: str
    judge_id: str = "none"


class RevealRequest(BaseModel):
    run_id: str
    exchange_id: str
    field: str
    actor: str = "ui-client"
    reason: Optional[str] = None


class InteractiveQueryGateway:
    """Run on-demand CAM queries for the dashboard console."""

    def __init__(self, loader: AuditLogHistoricalRunLoader):
        self.loader = loader
        self.store_dir = Path(os.getenv("CAM_UI_STORE_DIR", str(DEFAULT_STORE_DIR)))
        self.digest_path = Path(os.getenv("CAM_UI_DIGEST_PATH", str(DEFAULT_DIGEST_PATH)))
        self._scenario_map = default_scenarios(self.store_dir)
        self._agent: Optional[CAMAgent] = None

    def scenario_options(self) -> List[Dict[str, Any]]:
        options: List[Dict[str, Any]] = []
        for scenario_id, scenario in self._scenario_map.items():
            options.append(
                {
                    "id": scenario_id,
                    "label": describe_scenario(scenario_id, scenario.model_config.use_rag),
                    "model": scenario.model_config.name,
                    "use_rag": scenario.model_config.use_rag,
                }
            )
        return options

    def judge_options(self) -> List[Dict[str, Any]]:
        options: List[Dict[str, Any]] = [
            {
                "id": "none",
                "label": "No external judge",
                "available": True,
                "description": "Skip additional model-based judging.",
            }
        ]
        cfg = resolve_judge_llm_config()
        options.append(
            {
                "id": "ollama",
                "label": f"Ollama · {cfg.model}",
                "available": bool(cfg.model),
                "description": "Use the local Ollama judge model configured via JUDGE_MODE/JUDGE_MODEL.",
            }
        )
        gemini_available = bool(os.getenv("GEMINI_API_KEY"))
        options.append(
            {
                "id": "gemini",
                "label": os.getenv("GEMINI_MODEL", "Gemini 2.0 Flash"),
                "available": gemini_available,
                "description": "Route verdicts through Google Gemini (requires GEMINI_API_KEY).",
            }
        )
        options.append(
            {
                "id": "both",
                "label": "Dual review (Ollama & Gemini)",
                "available": bool(cfg.model) and gemini_available,
                "description": "Run both judges and display each verdict for side-by-side comparison.",
            }
        )
        return options

    def _ensure_agent(self) -> CAMAgent:
        if self._agent is not None:
            return self._agent
        scenarios = {sid: scenario.model_config for sid, scenario in self._scenario_map.items()}
        store = self.store_dir if self.store_dir.exists() else None
        if store is None:
            for scenario in self._scenario_map.values():
                if scenario.model_config.use_rag:
                    raise HTTPException(
                        status_code=500,
                        detail=f"RAG store missing at {self.store_dir}. Run the pipeline to build it before using the console.",
                    )
        agent = CAMAgent(store_dir=store, audit_log_path=self.loader.path, scenarios=scenarios)
        self._agent = agent
        return agent

    def submit(
        self,
        *,
        prompt: str,
        scenario_id: str,
        judge_id: str,
    ) -> Tuple[RunMetadata, List[TimelineEvent]]:
        prompt = prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt must not be empty.")

        scenario = self._scenario_map.get(scenario_id)
        if not scenario:
            raise HTTPException(status_code=400, detail=f"Unknown scenario '{scenario_id}'.")
        if scenario.model_config.use_rag and not self.store_dir.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Scenario {scenario_id} requires a RAG store at {self.store_dir}.",
            )

        agent = self._ensure_agent()

        session_id = f"{scenario_id}-live-{uuid4().hex[:8]}"
        logger.info(
            "Console submission received",
            extra={
                "scenario_id": scenario_id,
                "judge_mode": judge_id,
                "session_id": session_id,
                "prompt_chars": len(prompt),
            },
        )
        request = QueryRequest(
            user_id="ui",
            question=prompt,
            session_id=session_id,
            channel="ui-dashboard",
            extra={"scenario": scenario_id, "judge": judge_id},
        )

        before_size = self.loader.path.stat().st_size if self.loader.path.exists() else 0
        response = agent.handle_request(scenario_id, request)

        new_records = self._collect_new_records(before_size)
        if not new_records:
            logger.error(
                "Console submission produced no new audit records",
                extra={"session_id": session_id, "offset": before_size},
            )
            raise HTTPException(status_code=500, detail="Failed to capture audit log for the request.")

        timeline_events: List[TimelineEvent] = []
        run_meta: Optional[RunMetadata] = None
        exchange_id = f"{session_id}-turn-0"
        fallback_index = 0

        for record in new_records:
            _, turn_index, events = self.loader.build_events_from_raw_record(
                record=record,
                fallback_turn_index=fallback_index,
            )
            if events:
                run_meta = events[0].run
                exchange_id = events[0].exchange_id
                fallback_index = events[-1].turn_index + 1
            timeline_events.extend(events)

        if run_meta is None:
            logger.error(
                "Console submission failed to parse timeline events",
                extra={"session_id": session_id, "records": len(new_records)},
            )
            raise HTTPException(status_code=500, detail="Timeline parsing failed for the new run.")

        primary_turn_index = timeline_events[0].turn_index if timeline_events else 0
        user_prompt_event = self._build_user_prompt_event(
            run=run_meta,
            exchange_id=exchange_id,
            turn_index=primary_turn_index,
            prompt=prompt,
            timeline_events=timeline_events,
        )
        timeline_events.insert(0, user_prompt_event)

        external_events = self._build_external_judge_events(
            run=run_meta,
            exchange_id=exchange_id,
            turn_index=timeline_events[-1].turn_index if timeline_events else 0,
            judge_mode=judge_id,
            prompt=prompt,
            response_text=response.final_text,
            raw_text=response.raw_output.text,
            retrieval_context=response.raw_output.retrieval_context,
        )
        if external_events:
            timeline_events = [
                event
                for event in timeline_events
                if not (
                    event.event_type == "judge_verdict"
                    and event.payload.get("source", {}).get("provider") == "cam-agent"
                )
            ]
            timeline_events.extend(external_events)

        augmented_run = RunMetadata(
            run_id=run_meta.run_id,
            scenario_id=scenario_id,
            started_at=datetime.now(timezone.utc),
            tags={**run_meta.tags, "ui_live": "true", "judge": judge_id},
        )
        self.loader._run_cache[augmented_run.run_id] = augmented_run

        timeline_events = [replace(event, run=augmented_run) for event in timeline_events]

        logger.info(
            "Console submission completed",
            extra={
                "session_id": session_id,
                "exchange_id": exchange_id,
                "events_emitted": len(timeline_events),
                "judge_mode": judge_id,
            },
        )

        return augmented_run, timeline_events

    def _collect_new_records(self, offset: int) -> List[Dict[str, Any]]:
        if not self.loader.path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with self.loader.path.open("r", encoding="utf-8") as handle:
            handle.seek(offset)
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _build_external_judge_events(
        self,
        *,
        run: RunMetadata,
        exchange_id: str,
        turn_index: int,
        judge_mode: str,
        prompt: str,
        response_text: str,
        raw_text: str,
        retrieval_context: str,
    ) -> List[TimelineEvent]:
        manager = self._build_judge_manager(judge_mode)
        if not manager:
            logger.info(
                "External judge skipped",
                extra={"exchange_id": exchange_id, "judge_mode": judge_mode or "none"},
            )
            return []
        results = manager.evaluate(
            question=prompt,
            final_text=response_text,
            raw_text=raw_text,
            retrieval_context=retrieval_context,
        )
        if not results:
            logger.warning(
                "External judge returned no results",
                extra={"exchange_id": exchange_id, "judge_mode": judge_mode},
            )
            return []

        events: List[TimelineEvent] = []
        for result in results:
            verdict = self._score_to_verdict(result.compliance)
            severity = "info" if verdict == "allow" else verdict
            violation = ViolationDetail(
                category=result.judge_id,
                severity=severity,
                violation_type="external_judge",
                clause_reference=None,
                description=result.reasoning or "",
            )
            payload = JudgeVerdictEvent(
                exchange_id=exchange_id,
                turn_index=turn_index,
                source=EventSource(
                    model_id=result.model,
                    provider="external-judge",
                    mode="judge",
                    metadata={"judge_id": result.judge_id},
                ),
                created_at=datetime.now(timezone.utc),
                verdict=verdict,
                score=result.compliance,
                rationale_redacted=result.reasoning,
                violation=violation,
                metadata={"judge_id": result.judge_id},
            )
            events.append(
                build_timeline_event(
                    run=run,
                    exchange_id=exchange_id,
                    turn_index=turn_index,
                    event_type="judge_verdict",
                    payload_obj=payload,
                    created_at=datetime.now(timezone.utc),
                )
            )
        logger.info(
            "External judge events appended",
            extra={
                "exchange_id": exchange_id,
                "judge_mode": judge_mode,
                "count": len(events),
                "verdicts": [event.payload.get("verdict") for event in events],
            },
        )
        return events

    @staticmethod
    def _score_to_verdict(score: Optional[float]) -> str:
        if score is None:
            return "warn"
        if score >= 4.0:
            return "allow"
        if score >= 2.5:
            return "warn"
        return "block"

    def _build_judge_manager(self, judge_mode: str) -> Optional[JudgeManager]:
        judge_mode = (judge_mode or "none").lower()
        enable_med = judge_mode in {"ollama", "both"}
        enable_gemini = judge_mode in {"gemini", "both"}
        if not enable_med and not enable_gemini:
            return None
        judges = build_default_judges(
            enable_med_judge=enable_med,
            enable_gemini_judge=enable_gemini,
        )
        if not judges:
            return None
        return JudgeManager(judges, digest_path=self.digest_path)

    def _build_user_prompt_event(
        self,
        *,
        run: RunMetadata,
        exchange_id: str,
        turn_index: int,
        prompt: str,
        timeline_events: List[TimelineEvent],
    ) -> TimelineEvent:
        """Create a synthetic user prompt event so the UI can render stage 0."""

        if timeline_events:
            first_time = _normalize_event_timestamp(timeline_events[0])
            created_at = first_time - timedelta(milliseconds=200)
        else:
            created_at = datetime.now(timezone.utc)

        source = EventSource(
            model_id="ui-dashboard",
            provider="user",
            mode="prompt",
            metadata={"scenario_id": run.scenario_id or ""},
        )
        payload = UserPromptEvent(
            exchange_id=exchange_id,
            turn_index=turn_index,
            source=source,
            created_at=created_at,
            prompt_text=prompt,
            prompt_redacted=prompt,
        )
        return build_timeline_event(
            run=run,
            exchange_id=exchange_id,
            turn_index=turn_index,
            event_type="user_prompt",
            payload_obj=payload,
            created_at=created_at,
        )


def _resolve_loader() -> AuditLogHistoricalRunLoader:
    """Resolve the audit log path from environment or defaults."""

    path_str = os.getenv("CAM_UI_AUDIT_LOG", str(DEFAULT_AUDIT_PATH))
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audit log not found at {path}",
        )
    return AuditLogHistoricalRunLoader(path=path)


def _resolve_reveal_log_path() -> Path:
    """Resolve the file used to audit sensitive content reveals."""

    path_str = os.getenv("CAM_UI_REVEAL_LOG", str(DEFAULT_REVEAL_LOG_PATH))
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_reveal_log(entry: Dict[str, str]) -> None:
    """Append a JSONL entry describing a reveal action."""

    path = _resolve_reveal_log_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False))
        handle.write("\n")


def create_ui_api(loader: AuditLogHistoricalRunLoader | None = None) -> FastAPI:
    """
    Build a FastAPI app exposing run summaries and timeline events.

    Args:
        loader: Optional pre-configured loader (useful for tests).

    Returns:
        FastAPI instance with routes registered.
    """

    loader_instance = loader or _resolve_loader()
    interactive_gateway = InteractiveQueryGateway(loader_instance)

    app = FastAPI(title="CAM UI Timeline API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CAM_UI_CORS_ORIGINS", "*").split(","),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_loader() -> AuditLogHistoricalRunLoader:
        return loader_instance

    @app.get("/")
    def root() -> dict:
        """Health endpoint for quick status checks."""

        return {"status": "ok"}

    @app.get("/runs")
    def list_runs(
        limit: int = Query(20, ge=1, le=200),
        offset: int = Query(0, ge=0),
        loader_dep: AuditLogHistoricalRunLoader = Depends(get_loader),
    ) -> List[dict]:
        runs = list(loader_dep.iter_runs())
        slice_runs = runs[offset : offset + limit]
        return [serialize_run_metadata(run) for run in slice_runs]

    @app.get("/runs/{run_id}/timeline")
    def get_run_timeline(
        run_id: str,
        limit: Optional[int] = Query(None, ge=1, le=500),
        loader_dep: AuditLogHistoricalRunLoader = Depends(get_loader),
    ) -> List[dict]:
        events_iter = loader_dep.iter_timeline_events(run_id)
        events = []
        for event in events_iter:
            events.append(serialize_timeline_event(event))
            if limit and len(events) >= limit:
                break
        if not events:
            raise HTTPException(status_code=404, detail=f"No timeline events for run '{run_id}'")
        return events

    @app.get("/stream")
    async def stream_run_timeline(
        run_id: str = Query(..., description="Run identifier to stream."),
        replay: bool = Query(
            True, description="Replay existing timeline events before following new entries."
        ),
        poll_interval: float = Query(
            0.5,
            ge=0.1,
            le=5.0,
            description="Interval (seconds) to poll the audit log for new events.",
        ),
        loader_dep: AuditLogHistoricalRunLoader = Depends(get_loader),
    ) -> StreamingResponse:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required for streaming")

        def format_sse(event: str, data: str, event_id: Optional[int] = None) -> bytes:
            parts = []
            if event_id is not None:
                parts.append(f"id: {event_id}")
            if event:
                parts.append(f"event: {event}")
            for line in data.splitlines() or [""]:
                parts.append(f"data: {line}")
            parts.append("")
            return ("\n".join(parts) + "\n").encode("utf-8")

        async def event_generator() -> AsyncIterator[bytes]:
            event_id = 0
            turn_counters: Dict[str, int] = {}
            heartbeat_interval = max(1.0, poll_interval * 6)
            idle_elapsed = 0.0

            if replay:
                for event in loader_dep.iter_timeline_events(run_id):
                    event_id += 1
                    payload = serialize_timeline_event(event)
                    turn_counters[run_id] = max(
                        turn_counters.get(run_id, 0), event.turn_index + 1
                    )
                    yield format_sse(
                        event=event.event_type,
                        data=json.dumps(payload),
                        event_id=event_id,
                    )

            tail_start = loader_dep.path.stat().st_size

            try:
                with loader_dep.path.open("r", encoding="utf-8") as handle:
                    handle.seek(tail_start)
                    while True:
                        position = handle.tell()
                        line = handle.readline()
                        if not line:
                            await asyncio.sleep(poll_interval)
                            idle_elapsed += poll_interval
                            if idle_elapsed >= heartbeat_interval:
                                idle_elapsed = 0.0
                                event_id += 1
                                yield format_sse("heartbeat", "{}", event_id=event_id)
                            handle.seek(position)
                            continue

                        idle_elapsed = 0.0
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        record_run_id = loader_dep._extract_run_id(record)
                        if record_run_id != run_id:
                            continue

                        fallback_index = turn_counters.get(record_run_id, 0)
                        _, actual_index, events = loader_dep.build_events_from_raw_record(
                            record=record,
                            fallback_turn_index=fallback_index,
                        )
                        turn_counters[record_run_id] = actual_index + 1

                        for event in events:
                            event_id += 1
                            yield format_sse(
                                event=event.event_type,
                                data=json.dumps(serialize_timeline_event(event)),
                                event_id=event_id,
                            )
            except asyncio.CancelledError:
                raise

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/console/options", response_model=ConsoleOptionsResponse)
    def console_options() -> ConsoleOptionsResponse:
        return ConsoleOptionsResponse(
            scenarios=interactive_gateway.scenario_options(),
            judges=interactive_gateway.judge_options(),
        )

    @app.post("/console", status_code=201)
    def submit_prompt(payload: PromptRequest) -> dict:
        """
        Execute an interactive CAM query and return timeline events.
        """

        run_meta, events = interactive_gateway.submit(
            prompt=payload.prompt,
            scenario_id=payload.scenario_id,
            judge_id=payload.judge_id,
        )
        sorted_events = sorted(events, key=_normalize_event_timestamp)
        return {
            "status": "ok",
            "run": serialize_run_metadata(run_meta),
            "events": [serialize_timeline_event(event) for event in sorted_events],
        }

    @app.post("/reveal", status_code=202)
    def log_reveal(payload: RevealRequest) -> dict:
        """
        Record that a user has requested access to sensitive content.

        This allows downstream auditing of privacy controls.
        """

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": payload.run_id,
            "exchange_id": payload.exchange_id,
            "field": payload.field,
            "actor": payload.actor,
        }
        if payload.reason:
            entry["reason"] = payload.reason

        _append_reveal_log(entry)
        return {"status": "logged"}

    return app


app = create_ui_api()


__all__ = ["create_ui_api", "app"]
