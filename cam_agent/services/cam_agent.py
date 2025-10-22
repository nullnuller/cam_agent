"""
High-level CAM agent coordinating scenario execution and compliance controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from cam_agent.compliance.rules import DISCLAIMER_HINT, evaluate_compliance
from cam_agent.config.models import ModelConfig, SCENARIOS
from cam_agent.services.orchestrator import ScenarioExecutor
from cam_agent.services.types import CAMResponse, ComplianceIssue, ModelOutput, QueryRequest
from cam_agent.storage.audit import JsonlAuditLogger


BLOCK_MESSAGE = (
    "We’re unable to share the model’s response because it may conflict with safety or regulatory guidance. "
    "A compliance review has been logged."
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
    ) -> CAMResponse:
        executor = self.get_executor(scenario_id)
        model_output = executor.execute(request)
        decision = evaluate_compliance(request, model_output)
        final_text = self._apply_decision(model_output, decision.issues, decision.action)

        response = CAMResponse(
            final_text=final_text,
            action=decision.action,
            issues=decision.issues,
            raw_output=model_output,
        )
        self.audit_logger.log(request, response, metadata={"scenario_id": scenario_id})
        return response

    def _apply_decision(
        self,
        model_output: ModelOutput,
        issues: list[ComplianceIssue],
        action: str,
    ) -> str:
        if action == "block":
            return BLOCK_MESSAGE

        text = model_output.text
        has_disclaimer_issue = any(issue.rule_id == "compliance.disclaimer_missing" for issue in issues)

        if has_disclaimer_issue:
            text = f"{text.strip()}\n\n{DISCLAIMER_HINT}"

        if action == "warn":
            warnings = "\n".join(f"⚠️ {issue.message}" for issue in issues if issue.severity == "warn")
            text = f"{warnings}\n\n{text}"

        return text.strip()


__all__ = ["CAMAgent", "BLOCK_MESSAGE"]
