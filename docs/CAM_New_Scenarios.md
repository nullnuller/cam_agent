# CAM Scenario Additions & Question Banks

To exercise the strengthened APP coverage and retrieval guardrails we introduced two optional question sets that target privacy edge-cases:

| File | Purpose | Notes |
| --- | --- | --- |
| `project_bundle/questions_app_easy.txt` | “Easy miss” checks that require clause-perfect APP references (APP 6.2(b), APP 10, APP 11.2). | Answers should cite the APP digest and demonstrate clause quoting enforced by the prompt. |
| `project_bundle/questions_app_hard.txt` | “Hard miss” scenarios combining cross-border disclosure (APP 8), law-enforcement carve-outs (APP 6.2(d)), and parental access refusals (APP 12.9–12.10). | Designed to fail without the new APP digest or legal citation sanitizer. |

Run them with the standard pipeline:

```bash
source .venv/bin/activate

# Easy APP checks
python cam_pipeline.py \
  --questions_file project_bundle/questions_app_easy.txt \
  --enable-med-judge \
  --enable-gemini-judge

# Hard APP checks
python cam_pipeline.py \
  --questions_file project_bundle/questions_app_hard.txt \
  --enable-med-judge \
  --enable-gemini-judge
```

The runs populate `cam_suite_report.json` as usual, so the dashboard’s *Experiment Results* tab and export buttons reflect the additional scenarios once the report is refreshed.

These question banks rely on:

1. The APP digest (`health_docs/app_privacy_principles_summary.md`) being indexed (`--refresh-store` after pulling).
2. Retrieval biasing (`cam_agent/services/retrieval.py`) to prefer Privacy Act / APS clauses over research-only texts.
3. Legal citation sanitising (`cam_agent/services/formatter.py`) to eliminate fabricated clause IDs.
4. Crisis template injection (`cam_agent/services/cam_agent.py`) protecting wellbeing prompts across all scenarios.
5. Gemini retry payload trimming (`cam_agent/evaluation/judges.py`) so judge verdicts are consistently recorded even with large contexts.
