"""
End-to-end evaluation runner for CAM scenarios.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from jinja2 import Template

from cam_agent.evaluation.config import Scenario, default_scenarios
from cam_agent.evaluation.judges import JudgeManager, JudgeResult
from cam_agent.evaluation.metrics import (
    ScenarioMetrics,
    add_judge_scores,
    record_citation,
    record_latency,
    update_compliance_counts,
)
from cam_agent.services import CAMAgent, QueryRequest


@dataclass(slots=True)
class QuestionResult:
    """Captures raw vs CAM-filtered outputs for a single question."""

    question: str
    raw_text: str
    final_text: str
    action: str
    issues: List[Dict[str, object]]
    retrieval_context: str
    legend: str
    retrieved_hits: List[Dict[str, object]]
    scores: List[float]
    latency_ms: float
    judge_results: Dict[str, Dict[str, object]] = field(default_factory=dict)


@dataclass(slots=True)
class ScenarioRun:
    """Results for one scenario."""

    scenario: Scenario
    metrics: ScenarioMetrics
    questions: List[QuestionResult]


RESULTS_TEMPLATE = Template(
    r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>CAM Scenario Evaluation</title>
  <style>
    body { font-family: ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto; margin:24px; line-height:1.45; }
    h1 { margin-bottom: 0.5rem; }
    h2 { margin-top: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.25rem; }
    .meta { color: #475569; font-size: 12px; }
    .question { margin: 18px 0; padding: 16px; background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; margin-top: 12px; }
    .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; white-space: pre-wrap; }
    .ctx { background: #f1f5f9; border-radius: 8px; border: 1px solid #e2e8f0; padding: 12px; white-space: pre-wrap; font-size: 13px; }
    .issues { color: #b45309; margin: 8px 0; font-size: 13px; }
    code { background:#e2e8f0; padding: 2px 4px; border-radius: 4px; }
    .judge { background:#fef3c7; border-radius:8px; padding:10px; margin-top:10px; font-size:13px; }
  </style>
</head>
<body>
  <h1>CAM Scenario Evaluation</h1>
  <p class="meta">Scenarios: {{ runs|length }} · Questions per scenario: {{ questions_total }}</p>

  {% for run in runs %}
    <h2>Scenario {{ run.scenario.id }} — {{ run.scenario.description }}</h2>
    <p class="meta">
      total={{ run.metrics.total_questions }},
      allow={{ run.metrics.compliance_allow }},
      warn={{ run.metrics.compliance_warn }},
      block={{ run.metrics.compliance_block }},
      avg_latency={{ run.metrics.as_dict()['avg_latency_ms'] or 'n/a' }} ms
    </p>
    {% for row in run.questions %}
      <div class="question">
        <div class="meta">Action: {{ row.action|upper }} · Latency: {{ "%.1f"|format(row.latency_ms) }} ms</div>
        <strong>{{ row.question }}</strong>
        {% if row.issues %}
          <div class="issues">
            {% for issue in row.issues %}
              • [{{ issue['severity'] }}] {{ issue['message'] }} ({{ issue['rule_id'] }})<br/>
            {% endfor %}
          </div>
        {% endif %}
        {% if row.legend %}
          <div class="meta">Context: {{ row.legend }}</div>
        {% endif %}
        {% if row.judge_results %}
          <div class="judge">
            <strong>Judge Scores:</strong><br/>
            {% for judge_id, details in row.judge_results.items() %}
              • {{ judge_id }} → helpfulness={{ details.get('helpfulness') }}, compliance={{ details.get('compliance') }}<br/>
              {% if details.get('reasoning') %}
                <span class="meta">{{ details.get('reasoning') }}</span><br/>
              {% endif %}
            {% endfor %}
          </div>
        {% endif %}
        <details>
          <summary>Show retrieved passages</summary>
          <div class="ctx">{{ row.retrieval_context }}</div>
        </details>
        <div class="grid">
          <div class="card">
            <h3>Raw Model Output</h3>
            {{ row.raw_text }}
          </div>
          <div class="card">
            <h3>CAM Filtered Response</h3>
            {{ row.final_text }}
          </div>
        </div>
      </div>
    {% endfor %}
  {% endfor %}
</body>
</html>
"""
)


class CAMSuiteRunner:
    """Coordinates evaluation across multiple scenarios."""

    def __init__(
        self,
        *,
        store_dir: Path,
        questions: Iterable[str],
        audit_log_path: Path,
        scenario_ids: Optional[List[str]] = None,
        judge_manager: Optional[JudgeManager] = None,
    ):
        scenario_map = default_scenarios(store_dir)
        if scenario_ids:
            missing = [sid for sid in scenario_ids if sid not in scenario_map]
            if missing:
                raise ValueError(f"Unknown scenario ids: {', '.join(missing)}")
            scenario_map = {sid: scenario_map[sid] for sid in scenario_ids}

        self.scenario_map = scenario_map
        self.questions = [q.strip() for q in questions if q.strip()]
        self.judge_manager = judge_manager
        self.agent = CAMAgent(
            store_dir=store_dir,
            audit_log_path=audit_log_path,
            scenarios={sid: sc.model_config for sid, sc in scenario_map.items()},
        )

    def run(self) -> Dict[str, object]:
        runs: List[ScenarioRun] = []
        metrics_summary: Dict[str, Dict[str, object]] = {}

        for scenario_id, scenario in self.scenario_map.items():
            metric = ScenarioMetrics()
            question_rows: List[QuestionResult] = []

            for idx, question in enumerate(self.questions, start=1):
                request = QueryRequest(
                    user_id="evaluation",
                    question=question,
                    session_id=f"{scenario_id}-session",
                    extra={"question_index": idx},
                )

                start = time.perf_counter()
                response = self.agent.handle_request(scenario_id, request)
                latency_ms = (time.perf_counter() - start) * 1000.0

                update_compliance_counts(metric, response.action)
                record_latency(metric, latency_ms)
                rag_used = bool(response.raw_output.retrieval_context.strip())
                has_citation = "(see [" in response.final_text
                record_citation(metric, rag_used=rag_used, has_citation=has_citation)

                judge_results: Dict[str, Dict[str, object]] = {}
                if self.judge_manager:
                    for judge_result in self.judge_manager.evaluate(
                        question=question,
                        final_text=response.final_text,
                        raw_text=response.raw_output.text,
                        retrieval_context=response.raw_output.retrieval_context,
                    ):
                        judge_details = {
                            "helpfulness": judge_result.helpfulness,
                            "compliance": judge_result.compliance,
                            "reasoning": judge_result.reasoning,
                            "model": judge_result.model,
                        }
                        judge_results[judge_result.judge_id] = judge_details
                        add_judge_scores(
                            metric,
                            judge_result.judge_id,
                            helpfulness=judge_result.helpfulness,
                            compliance=judge_result.compliance,
                            rationale=judge_result.reasoning,
                        )

                question_rows.append(
                    QuestionResult(
                        question=question,
                        raw_text=response.raw_output.text,
                        final_text=response.final_text,
                        action=response.action,
                        issues=[asdict(issue) for issue in response.issues],
                        retrieval_context=response.raw_output.retrieval_context,
                        legend=response.raw_output.legend,
                        retrieved_hits=response.raw_output.retrieved_hits,
                        scores=response.raw_output.metadata.get("scores", []),
                        latency_ms=latency_ms,
                        judge_results=judge_results,
                    )
                )

            runs.append(ScenarioRun(scenario=scenario, metrics=metric, questions=question_rows))
            metrics_summary[scenario_id] = metric.as_dict()

        return {
            "runs": runs,
            "metrics": metrics_summary,
            "questions": self.questions,
        }

    def write_outputs(
        self,
        results: Dict[str, object],
        *,
        html_path: Optional[Path] = None,
        json_path: Optional[Path] = None,
    ) -> None:
        runs: List[ScenarioRun] = results["runs"]
        if html_path:
            html_path.parent.mkdir(parents=True, exist_ok=True)
            rendered = RESULTS_TEMPLATE.render(runs=runs, questions_total=len(self.questions))
            html_path.write_text(rendered, encoding="utf-8")
        if json_path:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_runs = [
                {
                    "scenario_id": run.scenario.id,
                    "description": run.scenario.description,
                    "metrics": run.metrics.as_dict(),
                    "questions": [
                        asdict(question_result) for question_result in run.questions
                    ],
                }
                for run in runs
            ]
            json_payload = {
                "questions": self.questions,
                "runs": json_runs,
            }
            json_path.write_text(
                json.dumps(json_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


__all__ = ["CAMSuiteRunner", "ScenarioRun", "QuestionResult"]
