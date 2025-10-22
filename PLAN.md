CAM Framework Implementation Plan
=================================

Goal
----
Build a Corpus-Aware Monitor (CAM) agent that intermediates between end-users and healthcare-focused LLM services, enforcing regulatory compliance, logging interactions, and offering automated evaluation across model scenarios.

Milestones & Tasks
------------------

### 1. Repository Setup & Baseline Audit
- [x] Convert existing evaluation script (`project_bundle/run_suite.py`) into reusable modules.
- [x] Document current RAG corpus sources and indexing process.
- [x] Establish project structure (`cam_agent/`) for service code, tests, and configuration.

### 2. Knowledge Base Pipeline
- [x] Script ingestion of regulatory PDFs (builds on `download_health_regulations.sh`).
- [x] Implement chunking + metadata tagging (clause IDs, source titles).
- [x] Build/rebuild FAISS index and persist chunk metadata (JSON/SQLite).
- [x] Generate long-form regulatory digest (≤1 M tokens) with summarisation fallbacks.

### 3. Core CAM Agent Service
- [x] Define request schema (user/session metadata, query text).
- [x] Implement Retrieval Manager wrapping FAISS lookups and context packaging.
- [x] Implement LLM Orchestrator for scenario routing (base vs. RAG, model selection).
- [x] Implement Compliance Engine:
  - [x] Rule definitions mapped to regulatory clauses.
  - [x] Response analysis (pattern checks; extend with LLM-assisted verification later).
  - [x] Decision outputs (allow/warn/block + redaction).
- [x] Implement Response Formatter aligning citations and user-facing messaging.
- [x] Implement Audit Logger (SQLite or append-only JSONL).
  - Note: current audit sink uses append-only JSONL (`cam_agent/storage/audit.py`); evaluate SQLite migration once schema stabilises.

### 4. Scenario Harness & Metrics
- [x] Encode six evaluation scenarios (A–F) with config files.
- [x] Extend harness to capture raw LLM output, CAM-filtered response, retrieval hits.
- [x] Integrate judge models: offline medgemma3-27B and online Gemini Flash 2.5.
- [x] Define and compute metrics: compliance accuracy, suppression rate, citation fidelity, helpfulness, latency.
- [x] Persist scenario reports (HTML + JSON) and aggregate dashboard.

### 5. Automation Runner
- [x] Implement `cam_pipeline.py` CLI:
  - [x] Step-oriented progress logging.
  - [x] Flags for scenario selection, question subsets, dry-run (skip online judge).
  - [x] Error handling for missing endpoints/keys.
- [x] Wire pipeline steps: ingestion → summarisation → scenario runs → judging → reporting.
- Note: pipeline docs available in `docs/PIPELINE.md`; extend with deployment hooks once environments are defined.

### 6. Testing & Validation
- [x] Unit tests for Retrieval Manager, Compliance rules, citation utilities.
- [x] Integration tests simulating end-to-end CAM flow on sample questions.
- [x] Regression tests ensuring rule updates do not break past compliant outputs (e.g., snapshot comparisons).
- [x] Continuous validation hooks for RAG index integrity and digest freshness.

### 7. Documentation & Ops
- [x] Write developer guide (setup, pipeline usage, extending rules).
- [x] Provide compliance reviewer playbook (audit log interpretation).
- [x] Outline deployment considerations (containerisation, environment variables, security).
- [x] Add roadmap for future enhancements (active learning, adaptive thresholds).

Refinement Process
------------------
- Maintain this plan in version control; revisit after each milestone to tick completed tasks and append learnings.
- Add notes on blockers, design decisions, and dependency updates directly under relevant checklist items.
- Ensure plan remains aligned with stakeholder feedback and regulatory updates.
