Compliance Reviewer Playbook
============================

This playbook explains how to interpret CAM outputs, audit logs, and reports from a compliance perspective.

## 1. Key Artifacts

- **HTML report (`cam_suite_report.html`)** – Human-readable comparison of raw vs. CAM-filtered answers, including retrieved context, compliance actions, and judge scores.
- **JSON report (`cam_suite_report.json`)** – Machine-readable summary for further analysis (BI dashboards, analytics).
- **Audit log (`cam_suite_audit.jsonl`)** – Append-only JSONL entries capturing every question, raw model output, compliance issues, and final response.
- **Digest (`regulatory_digest.md`)** – Condensed reference material provided to judge models; useful when cross-checking clause coverage.

## 2. Understanding Actions

Each question entry can result in:

- `allow` – Response delivered without modification (aside from citation enrichment).
- `warn` – Response prepended with warning(s); CAM may add missing disclaimers.
- `block` – Response suppressed (`BLOCK_MESSAGE` shown to end-user); review required to determine corrective action.

### Interpreting Issues

- `safety.no_suicide_instructions` – Raw model attempted to encourage self-harm. High priority; confirm CAM suppression and consider model retraining.
- `safety.medication_directive` – Model issued direct medication advice. Evaluate wording and ensure warnings are sufficient.
- `compliance.disclaimer_missing` – CAM appended standard disclaimer. Check whether rule logic should be refined or the LLM should be prompted differently.

## 3. Audit Log Fields

Each log entry includes:

- `timestamp`, `user_id`, `session_id`, `channel` – Identify the interaction context.
- `question`, `action`, `issues` – Core compliance decision.
- `raw_model` – Contains `text`, `prompt`, `retrieval_context`, `legend`, `retrieved_hits`, and metadata (including similarity scores).
- `final_text` – Message delivered to the user.
- `metadata.scenario_id` – Which scenario (model + RAG combo) produced the interaction.

### Review Process

1. Filter log for `action = "block"` or high severity issues.
2. Compare `raw_model.text` with `final_text` to measure CAM intervention.
3. Cross-reference `retrieved_hits` with `legend` to ensure citations align.
4. If issues recur, recommend rule adjustments or targeted model fine-tuning.

## 4. Leveraging Judge Scores

- **Helpfulness** (0–5) – Quality/utility of the final response.
- **Compliance** (0–5) – Judge’s assessment of adherence to policy.
- **Reasoning** – Plain-language rationale; check for clause references.

Use judge averages to identify scenarios needing calibration (e.g., low compliance scores on base models).

## 5. Escalation Guidelines

- **Critical**: Self-harm instructions, illegal disclosures, or advice contradicting law → escalate immediately with raw output and retrieved context.
- **High**: Missing confidentiality clauses, incorrect legal references, major medical advice → schedule review with SMEs.
- **Moderate**: Missing disclaimers, vague guidance → consider prompt adjustments or rule tuning.

Document each escalation with scenario details and audit log reference to ensure traceability.

## 6. Checklist for Review Sessions

- [ ] Filter latest audit logs for `block` and `warn` actions.
- [ ] Validate that warnings include sufficient context/disclaimers.
- [ ] Spot-check `allow` actions to catch false negatives.
- [ ] Review judge rationales for patterns (e.g., recurring clause omissions).
- [ ] Update `docs/ROADMAP.md` with any compliance-driven enhancement requests.

By following this playbook, reviewers can efficiently monitor CAM performance and drive continuous improvement in compliance coverage.

