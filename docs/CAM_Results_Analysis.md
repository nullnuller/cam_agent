# CAM Results & Judge Analysis

## Data sources
- Generated from `project_bundle/cam_suite_report.json` (`generated_at`: 2025-10-26T19:33:58Z).
- Attempted to rebuild the RAG store via `python cam_pipeline.py --questions_file project_bundle/questions.txt --refresh-store --dry-run`; embedding the new APP digest requires downloading `sentence-transformers/all-MiniLM-L6-v2`, which failed in this sandbox because outbound network access is disabled. Run the same command on a networked workstation to refresh the FAISS index after pulling the latest docs.

## Scenario-level summary

| Scenario | Description | Allow | Warn | Block | Warn % | Block % | Avg Helpfulness | Avg Compliance | Avg Latency (s) | Judges |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | gemma3-4B (no RAG) | 0 | 15 | 0 | 100.0 | 0.0 | 4.12 | 4.04 | 10.33 | gemini-flash-judge, google_medgemma-4b-judge |
| B | gemma3-4B + RAG | 2 | 13 | 0 | 86.7 | 0.0 | 3.89 | 3.69 | 12.62 | gemini-flash-judge, google_medgemma-4b-judge |
| C | medgemma3-4B (no RAG) | 3 | 12 | 0 | 80.0 | 0.0 | 4.28 | 3.91 | 200.28 | gemini-flash-judge, google_medgemma-4b-judge |
| D | medgemma3-4B + RAG | 0 | 15 | 0 | 100.0 | 0.0 | 3.77 | 3.77 | 98.44 | gemini-flash-judge, google_medgemma-4b-judge |
| E | gemma-27B remote (no RAG) | 2 | 11 | 0 | 84.6 | 0.0 | 4.58 | 4.50 | 82.38 | gemini-flash-judge, google_medgemma-4b-judge |
| F | gemma-27B remote + RAG | 0 | 15 | 0 | 100.0 | 0.0 | 4.35 | 4.20 | 24.10 | gemini-flash-judge, google_medgemma-4b-judge |

## MedGemma judge metrics

| Scenario | Description | Count | Failures | Pass Rate % | Avg Helpfulness | Avg Compliance | Avg Latency (s) | Disagreement % | Verdict Breakdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | gemma3-4B (no RAG) | 13 | 2 | 100.0 | 4.50 | 4.58 | 3.52 | 100.0 | allow:13 |
| B | gemma3-4B + RAG | 14 | 1 | 100.0 | 4.43 | 4.36 | 4.54 | 92.9 | allow:14 |
| C | medgemma3-4B (no RAG) | 10 | 4 | 100.0 | 4.50 | 4.50 | 3.08 | 80.0 | allow:10 |
| D | medgemma3-4B + RAG | 14 | 1 | 92.9 | 4.43 | 4.32 | 4.37 | 92.9 | allow:13; warn:1 |
| E | gemma-27B remote (no RAG) | 13 | 0 | 100.0 | 4.54 | 4.50 | 3.55 | 84.6 | allow:13 |
| F | gemma-27B remote + RAG | 15 | 0 | 100.0 | 4.43 | 4.43 | 4.42 | 100.0 | allow:15 |

## Gemini Flash judge metrics

| Scenario | Description | Count | Failures | Pass Rate % | Avg Helpfulness | Avg Compliance | Avg Latency (s) | Disagreement % | Verdict Breakdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | gemma3-4B (no RAG) | 15 | 0 | 66.7 | 3.79 | 3.57 | 13.10 | 100.0 | block:5; allow:10 |
| B | gemma3-4B + RAG | 15 | 0 | 46.7 | 3.39 | 3.06 | 20.79 | 80.0 | block:6; allow:7; warn:2 |
| C | medgemma3-4B (no RAG) | 13 | 1 | 61.5 | 4.12 | 3.46 | 16.44 | 69.2 | block:4; allow:8; warn:1 |
| D | medgemma3-4B + RAG | 14 | 1 | 50.0 | 3.11 | 3.21 | 19.61 | 78.6 | block:4; allow:7; warn:3 |
| E | gemma-27B remote (no RAG) | 13 | 0 | 84.6 | 4.62 | 4.50 | 17.52 | 76.9 | block:1; warn:1; allow:11 |
| F | gemma-27B remote + RAG | 15 | 0 | 60.0 | 4.27 | 3.97 | 19.90 | 73.3 | block:2; allow:9; warn:4 |

## Clarifications & observations
- **What each judge scores:** Both judges evaluate the *final CAM response* (post-RAG, post-rule filtering). The MedGemma judge runs locally via Ollama; Gemini Flash calls the Google API when configured. They do not grade each other.
- **Why the counts differ:** `count` reflects how many responses contained numeric `helpfulness` and `compliance` scores. The MedGemma judge sometimes omitted one or both values (e.g., scenario A questions on dual relationships and boundaries), so only 13 of 15 responses contributed to the averages. Gemini returned numeric scores for every answer, so its counts align with the question totals.
- **Helpfulness vs. compliance vs. pass rate:** Helpfulness and compliance are 0–5 point ratings emitted by the judge. `pass_rate` is the share of compliance scores ≥ 4.0 (the same threshold the pipeline uses for an "allow" verdict). High helpfulness alone does not guarantee a pass if compliance drops below 4.0.
- **Verdicts and disagreement:** The judge also emits an allow/warn/block verdict. `disagreement %` measures how often this verdict differs from the CAM action. Because the CAM agent currently defaults to `warn` for most scenarios, any judge `allow` shows up as a disagreement, which explains the large percentages—even in scenario D where the same base MedGemma model is used. The judge sees the final answer plus retrieval context, so it can permissively rate an answer even when the CAM policy elects to warn.
- **Scenario D agreement:** Even though scenario D uses MedGemma 4B with RAG, the judge runs a separate evaluation prompt without RAG and applies its own policy thresholds. Thus, agreement is not expected to be 100%.
- **Empty judge averages block in UI:** Prior implementation tried to display aggregate judge metrics before the results loader was wired; it now pulls data from `/results/summary`. If the JSON report is missing, the UI shows a “No judge metrics available” notice instead of an empty table.
- **Pipeline progress in the UI:** The dashboard is read-only. It can display completed runs, trigger ad-hoc single queries, and export tables, but it does not execute the batch pipeline nor stream step-by-step progress. Continue to use the terminal command below for run-time feedback.

## Recommended actions
1. **Refresh embeddings (required for new APP digest):**
   ```bash
   python cam_pipeline.py \
     --questions_file project_bundle/questions.txt \
     --refresh-store \
     --dry-run
   ```
   Run this on a machine with Hugging Face access so the MiniLM encoder downloads successfully.
2. **Full evaluation with both judges:**
   ```bash
   python cam_pipeline.py \
     --questions_file project_bundle/questions.txt \
     --enable-med-judge \
     --enable-gemini-judge \
     --refresh-store
   ```
   Supply `OLLAMA_*` settings for the MedGemma judge and `GEMINI_API_KEY` for Gemini before invoking.
3. **Review the updated results tab:** Visit the dashboard’s “Results” tab to compare the scenario table with the side-by-side judge metrics, or download CSV/PDF via the new export buttons for stakeholder sharing.
4. **Stress-test APP retrieval:** Use the new question banks documented in `docs/CAM_New_Scenarios.md` to run “easy” vs. “hard” APP scenarios and confirm the CAM agent blocks or warns when clauses are missing.

## Prompt hardening recap
- `cam_agent/utils/rag.py` now forbids fabricating clause IDs, prioritises APP citations, and enforces suicide-prevention guidance when risk cues appear.
- `cam_agent/services/orchestrator.py` adds a safety fallback message when retrieval finds no compliant answer.
- The APP digest (`health_docs/app_privacy_principles_summary.md`) must be indexed to feed accurate clause wording to the CAM model and judges.
- `cam_agent/services/retrieval.py` boosts clinical privacy sources (APP, Privacy Act, APS Code) and down-ranks research-only passages when the user asks about disclosure or confidentiality.
- `cam_agent/services/formatter.py` sanitises APP/National Law citations, trimming any clause that is not present in the retrieved context.
- `cam_agent/services/cam_agent.py` automatically prepends crisis-helpline guidance for high-risk mental-health prompts so users always see emergency support.
- `cam_agent/evaluation/judges.py` now trims long payloads between Gemini retries, reducing timeout risk for RAG-heavy scenarios.
