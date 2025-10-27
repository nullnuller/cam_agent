"""
End-to-end evaluation runner for CAM scenarios.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

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
    table { border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 13px; }
    th, td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }
    th { background: #f1f5f9; font-weight: 600; color: #1f2937; }
    .judge-summary, .judge-confusion { margin-top: 16px; }
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
    {% set metrics_data = run.metrics.as_dict() %}
    <h2>Scenario {{ run.scenario.id }} — {{ run.scenario.description }}</h2>
    <p class="meta">
      total={{ run.metrics.total_questions }},
      allow={{ run.metrics.compliance_allow }},
      warn={{ run.metrics.compliance_warn }},
      block={{ run.metrics.compliance_block }},
      avg_latency={{ metrics_data['avg_latency_ms'] or 'n/a' }} ms
    </p>
    {% if metrics_data['judges'] %}
      <div class="judge-summary">
        <h3>Gemini / External Judge Metrics</h3>
        <table>
          <thead>
            <tr>
              <th>Judge</th>
              <th>Avg compliance</th>
              <th>Median</th>
              <th>Std dev</th>
              <th>Pass rate</th>
              <th>Disagreement</th>
              <th>Avg latency</th>
              <th>P95 latency</th>
              <th>Failures</th>
            </tr>
          </thead>
          <tbody>
            {% for judge_id, summary in metrics_data['judges'].items() %}
              <tr>
                <td>{{ judge_id }}</td>
                <td>{{ summary['avg_compliance'] | round(2) if summary['avg_compliance'] is not none else '—' }}</td>
                <td>{{ summary['median_compliance'] | round(2) if summary['median_compliance'] is not none else '—' }}</td>
                <td>{{ summary['std_compliance'] | round(2) if summary['std_compliance'] is not none else '—' }}</td>
                <td>{{ (summary['compliance_pass_rate'] * 100) | round(1) ~ '%' if summary['compliance_pass_rate'] is not none else '—' }}</td>
                <td>{{ (summary['disagreement_rate'] * 100) | round(1) ~ '%' if summary['disagreement_rate'] is not none else '—' }}</td>
                <td>{{ summary['avg_latency_ms'] | round(1) if summary['avg_latency_ms'] is not none else '—' }}</td>
                <td>{{ summary['latency_p95_ms'] | round(1) if summary['latency_p95_ms'] is not none else '—' }}</td>
                <td>{{ summary['failure_count'] }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% if metrics_data['judge_confusion'] %}
        <div class="judge-confusion">
          <h3>CAM vs Judge Outcomes</h3>
          {% for judge_id, matrix in metrics_data['judge_confusion'].items() %}
            <h4>{{ judge_id }}</h4>
            <table>
              <thead>
                <tr>
                  <th>CAM action ↓ / Judge verdict →</th>
                  {% set verdicts = namespace(values=[]) %}
                  {% for row in matrix.values() %}
                    {% for verdict, _ in row.items() %}
                      {% if verdict not in verdicts.values %}
                        {% set verdicts.values = verdicts.values + [verdict] %}
                      {% endif %}
                    {% endfor %}
                  {% endfor %}
                  {% for verdict in verdicts.values %}
                    <th>{{ verdict }}</th>
                  {% endfor %}
                </tr>
              </thead>
              <tbody>
                {% for cam_action, counts in matrix.items() %}
                  <tr>
                    <td>{{ cam_action }}</td>
                    {% for verdict in verdicts.values %}
                      <td>{{ counts.get(verdict, 0) }}</td>
                    {% endfor %}
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          {% endfor %}
        </div>
      {% endif %}
    {% endif %}
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
        resume_cache: Optional[Dict[str, Dict[str, Dict[str, object]]]] = None,
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
        self.resume_cache = resume_cache or {}
        self.run_started_at = datetime.now(timezone.utc)
        seed = self.run_started_at.strftime("%Y%m%d-%H%M%S")
        self.pipeline_run_id = f"cam-eval-{seed}-{uuid4().hex[:6]}"
        self.scenario_run_ids = {
            sid: f"{self.pipeline_run_id}-{sid}" for sid in scenario_map
        }

    def run(self) -> Dict[str, object]:
        runs: List[ScenarioRun] = []
        metrics_summary: Dict[str, Dict[str, object]] = {}

        total_questions = len(self.questions)

        for scenario_id, scenario in self.scenario_map.items():
            print(f"[scenario {scenario_id}] Starting evaluation ({total_questions} questions)")
            metric = ScenarioMetrics()
            question_rows: List[QuestionResult] = []
            scenario_failures: List[Dict[str, object]] = []
            scenario_run_id = self.scenario_run_ids[scenario_id]
            scenario_run_tags = {
                "pipeline_run_id": self.pipeline_run_id,
                "scenario_id": scenario_id,
                "run_started_at": self.run_started_at.isoformat(),
            }

            for idx, question in enumerate(self.questions, start=1):
                print(f"[scenario {scenario_id}] Question {idx}/{total_questions} …", flush=True)

                cached_record = self.resume_cache.get(scenario_id, {}).get(question)
                if cached_record:
                    print(f"[scenario {scenario_id}]  ↳ cached result found, skipping LLM call", flush=True)
                    question_rows.append(QuestionResult(**cached_record))
                    update_compliance_counts(metric, cached_record.get("action", "allow"))
                    record_latency(metric, float(cached_record.get("latency_ms", 0.0)))
                    rag_used_cached = bool((cached_record.get("retrieval_context") or "").strip())
                    has_citation_cached = "(see [" in (cached_record.get("final_text") or "")
                    record_citation(metric, rag_used=rag_used_cached, has_citation=has_citation_cached)
                    judge_results_cached = cached_record.get("judge_results") or {}
                    for judge_id, details in judge_results_cached.items():
                        if isinstance(details, dict) and details.get("status") == "error":
                            add_judge_scores(
                                metric,
                                judge_id,
                                helpfulness=None,
                                compliance=None,
                                rationale=None,
                                latency_ms=float(details.get("latency_ms", 0.0)),
                                verdict=None,
                                cam_action=cached_record.get("action", "allow"),
                                failure=True,
                            )
                            continue
                        add_judge_scores(
                            metric,
                            judge_id,
                            helpfulness=(details or {}).get("helpfulness"),
                            compliance=(details or {}).get("compliance"),
                            rationale=(details or {}).get("reasoning"),
                            latency_ms=float((details or {}).get("latency_ms", 0.0)),
                            verdict=(details or {}).get("verdict"),
                            cam_action=cached_record.get("action", "allow"),
                        )
                    print(
                        f"[scenario {scenario_id}] Finished question {idx}/{total_questions} (cached)",
                        flush=True,
                    )
                    continue

                request = QueryRequest(
                    user_id="evaluation",
                    question=question,
                    session_id=scenario_run_id,
                    extra={
                        "question_index": idx,
                        "run_id": scenario_run_id,
                        "pipeline_run_id": self.pipeline_run_id,
                    },
                )
                turn_index = idx - 1
                exchange_id = f"{scenario_id}-{idx:03d}"
                base_metadata = {
                    "scenario_id": scenario_id,
                    "run_id": scenario_run_id,
                    "run_tags": scenario_run_tags,
                    "turn_index": turn_index,
                    "exchange_id": exchange_id,
                    "question_index": idx,
                    "run_started_at": self.run_started_at.isoformat(),
                }

                start = time.perf_counter()
                try:
                    response = self.agent.handle_request(
                        scenario_id,
                        request,
                        metadata=base_metadata,
                    )
                except Exception as exc:  # pragma: no cover - resilience
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    error_message = str(exc)
                    print(
                        f"[scenario {scenario_id}]  ↳ error: {error_message}",
                        flush=True,
                    )
                    failure_record = {
                        "question_index": idx,
                        "question": question,
                        "error": error_message,
                        "latency_ms": latency_ms,
                    }
                    scenario_failures.append(failure_record)
                    question_rows.append(
                        QuestionResult(
                            question=question,
                            raw_text="",
                            final_text=f"[error] {error_message}",
                            action="error",
                            issues=[],
                            retrieval_context="",
                            legend="",
                            retrieved_hits=[],
                            scores=[],
                            latency_ms=latency_ms,
                            judge_results={},
                        )
                    )
                    continue

                latency_ms = (time.perf_counter() - start) * 1000.0

                update_compliance_counts(metric, response.action)
                record_latency(metric, latency_ms)
                rag_used = bool(response.raw_output.retrieval_context.strip())
                has_citation = "(see [" in response.final_text
                record_citation(metric, rag_used=rag_used, has_citation=has_citation)

                judge_results: Dict[str, Dict[str, object]] = {}
                if self.judge_manager:
                    print(f"[scenario {scenario_id}]  ↳ evaluating judges …", flush=True)
                    judge_model_lookup = {
                        getattr(judge, "judge_id", "unknown-judge"): getattr(judge, "model", "unknown-model")
                        for judge in getattr(self.judge_manager, "judges", [])
                    }
                    judge_outputs = self.judge_manager.evaluate(
                        question=question,
                        final_text=response.final_text,
                        raw_text=response.raw_output.text,
                        retrieval_context=response.raw_output.retrieval_context,
                    )
                    for judge_result in judge_outputs:
                        judge_details = {
                            "helpfulness": judge_result.helpfulness,
                            "compliance": judge_result.compliance,
                            "reasoning": judge_result.reasoning,
                            "model": judge_result.model,
                            "verdict": judge_result.verdict,
                            "latency_ms": judge_result.latency_ms,
                            "payload": judge_result.payload,
                            "raw_text": judge_result.raw_text,
                        }
                        judge_results[judge_result.judge_id] = judge_details
                        add_judge_scores(
                            metric,
                            judge_result.judge_id,
                            helpfulness=judge_result.helpfulness,
                            compliance=judge_result.compliance,
                            rationale=judge_result.reasoning,
                            latency_ms=judge_result.latency_ms,
                            verdict=judge_result.verdict,
                            cam_action=response.action,
                        )
                    for judge_id, latencies in self.judge_manager.failure_stats.items():
                        if not latencies:
                            continue
                        for failure_latency in latencies:
                            add_judge_scores(
                                metric,
                                judge_id,
                                helpfulness=None,
                                compliance=None,
                                rationale=None,
                                latency_ms=failure_latency,
                                verdict=None,
                                cam_action=response.action,
                                failure=True,
                            )
                        judge_results.setdefault(
                            judge_id,
                            {
                                "status": "error",
                                "latency_ms": latencies[-1],
                                "model": judge_model_lookup.get(judge_id, "unknown-model"),
                            },
                        )
                    if judge_results:
                        self.agent.audit_logger.log_judge_results(
                            request,
                            scenario_id=scenario_id,
                            cam_action=response.action,
                            judge_results=judge_results,
                            metadata={
                                **base_metadata,
                                "latency_ms": latency_ms,
                            },
                        )
                    print(
                        f"[scenario {scenario_id}]  ↳ judges complete "
                        f"(success={sum(1 for d in judge_results.values() if d.get('status') != 'error')}; "
                        f"errors={sum(1 for d in judge_results.values() if d.get('status') == 'error')})",
                        flush=True,
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
                print(
                    f"[scenario {scenario_id}] Finished question {idx}/{total_questions} "
                    f"(action={response.action}, latency={latency_ms:.0f} ms)",
                    flush=True,
                )

            runs.append(ScenarioRun(scenario=scenario, metrics=metric, questions=question_rows))
            if scenario_failures:
                metric.failures.extend(scenario_failures)
                print(
                    f"[scenario {scenario_id}] Completed with {len(scenario_failures)} failure(s).",
                    flush=True,
                )
            else:
                print(f"[scenario {scenario_id}] Completed.", flush=True)
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

        def _backup_existing(path: Optional[Path]) -> None:
            if not path or not path.exists():
                return
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            backup = path.with_name(f"{path.stem}_{timestamp}{path.suffix}")
            path.replace(backup)

        _backup_existing(html_path)
        _backup_existing(json_path)
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
