"""
High-level CAM agent coordinating scenario execution and compliance controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from cam_agent.compliance.rules import DISCLAIMER_HINT, evaluate_compliance
from cam_agent.config.models import ModelConfig, SCENARIOS
from cam_agent.services.orchestrator import ScenarioExecutor
from cam_agent.services.types import CAMResponse, ComplianceIssue, ModelOutput, QueryRequest
from cam_agent.storage.audit import JsonlAuditLogger


BLOCK_MESSAGE = (
    "We’re unable to share the model’s response because it may conflict with safety or regulatory guidance. "
    "A compliance review has been logged."
)

CRISIS_TEMPLATE = (
    "If you or someone else is in immediate danger, contact emergency services (000 within Australia). "
    "You can also call Lifeline on 13 11 14 or Beyond Blue on 1300 22 4636 for urgent support. "
    "Please seek immediate professional help."
)

CRISIS_KEYWORDS = (
    "self-harm",
    "suicidal",
    "kill myself",
    "hurt myself",
    "emergency",
    "crisis",
    "not feeling like myself",
    "depression",
    "panic attack",
)


@dataclass(slots=True)
class CAMAgent:
    """Facade that handles requests end-to-end for configured scenarios."""

    store_dir: Optional[Path]
    audit_log_path: Path
    scenarios: Dict[str, ModelConfig] = field(default_factory=lambda: SCENARIOS.copy())
    min_sim: float = 0.20
    top_k: int = 12
    audit_logger: JsonlAuditLogger = field(init=False)
    _executors: Dict[str, ScenarioExecutor] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.audit_logger = JsonlAuditLogger(self.audit_log_path)

    def get_executor(self, scenario_id: str) -> ScenarioExecutor:
        if scenario_id not in self.scenarios:
            raise KeyError(f"Scenario '{scenario_id}' is not defined.")
        if scenario_id not in self._executors:
            config = self.scenarios[scenario_id]
            store = str(self.store_dir) if config.use_rag else None
            executor = ScenarioExecutor(
                config=config,
                store_dir=store,
                min_sim=self.min_sim,
                top_k=self.top_k,
            )
            self._executors[scenario_id] = executor
        return self._executors[scenario_id]

    def handle_request(
        self,
        scenario_id: str,
        request: QueryRequest,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CAMResponse:
        executor = self.get_executor(scenario_id)
        model_output = executor.execute(request)
        decision = evaluate_compliance(request, model_output)
        final_text = self._apply_decision(
            request,
            model_output,
            decision.issues,
            decision.action,
        )

        response = CAMResponse(
            final_text=final_text,
            action=decision.action,
            issues=decision.issues,
            raw_output=model_output,
        )
        combined_metadata: Dict[str, Any] = {"scenario_id": scenario_id}
        if metadata:
            combined_metadata.update(metadata)
        self.audit_logger.log(request, response, metadata=combined_metadata)
        return response

    def _apply_decision(
        self,
        request: QueryRequest,
        model_output: ModelOutput,
        issues: list[ComplianceIssue],
        action: str,
    ) -> str:
        if action == "block":
            return BLOCK_MESSAGE

        text = model_output.text.strip()
        needs_crisis = self._needs_crisis_template(request.question, text)

        if needs_crisis:
            text = self._inject_crisis_guidance(text)

        has_disclaimer_issue = any(issue.rule_id == "compliance.disclaimer_missing" for issue in issues)

        if has_disclaimer_issue:
            text = f"{text.strip()}\n\n{DISCLAIMER_HINT}"

        if action == "warn":
            warnings = "\n".join(f"⚠️ {issue.message}" for issue in issues if issue.severity == "warn")
            text = f"{warnings}\n\n{text}"

        return text.strip()

    def _needs_crisis_template(self, question: str, text: str) -> bool:
        combined = f"{question}\n{text}".lower()
        if any(marker in combined for marker in ("lifeline", "000", "13 11 14", "beyond blue", "seek immediate professional help")):
            return False
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in CRISIS_KEYWORDS)

    def _inject_crisis_guidance(self, text: str) -> str:
        if CRISIS_TEMPLATE.lower() in text.lower():
            return text
        return f"{CRISIS_TEMPLATE}\n\n{text}".strip()


__all__ = ["CAMAgent", "BLOCK_MESSAGE"]
