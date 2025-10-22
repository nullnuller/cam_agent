CAM UI Development Plan
=======================

Purpose
-------
Design and deliver an interactive, animation-first dashboard that showcases the CAM agent workflow for healthcare LLM interactions. The UI must support both realtime and simulated playback, expose judge/model identities, surface compliance metrics, and protect sensitive information by default.

Guiding Objectives
------------------
- Present the end-to-end flow (User → Base LLM → CAM review/judge decision) with clear visual states and model badges.
- Offer live monitoring and historical replay from the same interface, driven by consistent event schemas.
- Provide actionable analytics: latency, violation types, judge agreement, category trends, token/context statistics.
- Enforce privacy controls (PII redaction, role-based reveal) while keeping data grounded in actual CAM outputs.
- Keep configuration flexible so operators can switch judge providers (Ollama, Gemini, other OpenAI-compatible endpoints) without UI changes.

Primary User Journeys
---------------------
- **Operator monitoring live traffic**: Observe new interactions, check judge verdicts, intervene on flagged violations, optionally drill into raw content with appropriate permissions.
- **Stakeholder demo mode**: Play curated scenarios with cinematic animations highlighting system capabilities.
- **Analyst deep dive**: Filter runs by violation category, export metrics, correlate judge disagreements with prompt characteristics.
- **Developer testing**: Submit ad-hoc queries via integrated console, inspect the resulting event stream, verify redaction and categorization logic.

System Architecture (Draft)
---------------------------
- **Frontend (SPA)**: React + TypeScript with state via Zustand/Redux Toolkit. Framer Motion animates timeline transitions; Tailwind or CSS Modules for rapid styling. Component library grouped into Timeline, Metrics, Console, Safety Panels.
- **Visualization Layer**: Recharts for metric dashboards (aggregate bars, trend lines) and a custom event timeline component for animated flow.
- **Backend Services**:
  - Event gateway (FastAPI) exposing REST endpoints for run history and WebSocket/SSE streams for live events.
  - Event transformer enriching payloads with violation categories, question taxonomy tags, and PII metadata before persisting/streaming.
  - Storage adapters reading/writing CAM artifacts (`cam_suite_audit.jsonl`, `cam_suite_report.json`, future database support).
- **Data Model Updates**: Standardize event schema with entities `Run`, `Exchange`, `LLMResponse`, `JudgeVerdict`, `MetricSnapshot`. Include fields for `model_id`, `judge_source`, `violation_type`, `question_category`, `pii_flags`, `redacted_body`.
- **Privacy Layer**: Server-side redaction pipeline (regex + ML-based PII detector) generating redacted/full variants. Access control wrapper logs reveal actions and enforces least privilege.

Feature Breakdown
-----------------
1. **Conversation Timeline**
   - Animated cards for each stage, color-coded by actor.
   - Expandable panels showing redacted text by default; gated reveal button for full content.
   - Badges indicating model/judge identities, response latency, context size.
2. **Metrics & Analysis**
   - Overview KPIs (avg latency, judge agreement %, violation counts).
   - Charts sliced by violation type, question category, model version.
   - Token/context utilization viz (e.g., gauge vs. `num_ctx` limit) to highlight over-length prompts.
3. **Safety & Taxonomy Panel**
   - Table of violations with severity, category, mitigation state.
   - Filters by category/question tags; cross-highlighting with timeline.
4. **Live Console**
   - Input form for realtime queries; selects backend scenario (live vs. sandbox).
   - Shows submission status, queue info, throttle warnings (e.g., Gemini 429).
5. **Playback Controls**
   - Select run from history, play/pause, adjust speed, step-through events.
   - Option to synthesize runs from archived audit logs for offline demos.
6. **Configuration Drawer**
   - Display active judge provider, API endpoints, rate limits.
   - Quick links to `.env` instructions, ability to switch demo datasets.

Implementation Roadmap
----------------------
1. **Foundation (Sprint 1)**
   - Finalize event schema (`Exchange`, `JudgeVerdict`, privacy fields).
   - Build backend adapters to serve historical runs and simulated streams.
   - Create UI scaffolding with routing, global state, and shared theme.
2. **Timeline & Playback (Sprint 2)**
   - Implement animated timeline component with redaction toggles.
   - Integrate playback controls using sample data.
   - Add model/judge badges and core metadata display.
3. **Metrics & Safety Panels (Sprint 3)**
   - Develop KPI widgets and charts using historical metric snapshots.
   - Implement violation taxonomy panel with filtering and drill-down.
4. **Realtime Integration (Sprint 4)**
   - Connect to live WebSocket feed; ensure smooth animation updates.
   - Handle state synchronization between live and historical modes.
   - Implement rate-limit handling and alerting UI elements.
   - _Status_: FastAPI SSE endpoint plus React timeline stream in place with heartbeat/error indicators; future work includes optional WebSocket transport.
5. **Privacy & Access Controls (Sprint 5)**
   - Integrate redaction service, authorization checks for reveal.
   - Audit trail for PII reveal actions; update UI affordances.
   - _Status_: Reveal gating shipped (UI + `/reveal` audit log); evaluate role-based access before production release.
6. **Polish & Documentation (Sprint 6)**
   - UX refinements, responsive layouts, accessibility review.
   - Integration tests (frontend Cypress/Playwright, backend contract tests).
   - Update docs (`docs/`, runbooks) and prepare demo scripts.

Progress Tracker
----------------
- [ ] Sprint 1 – Foundation
  - [x] Draft event schema and Python dataclasses for UI payloads (`cam_agent/ui/events.py`).
  - [x] Define final event JSON schema (versioning, serialization rules).
  - [x] Prototype backend adapter for historical run retrieval.
  - [x] Scaffold frontend project structure and build tooling.
- [ ] Sprint 2 – Timeline & Playback
  - [x] Build animated timeline component with sample data.
  - [x] Connect timeline to audit API with run selector (React Query).
  - [x] Implement playback controls (play/pause/speed).
- [ ] Sprint 3 – Metrics & Safety Panels
  - [x] KPI widgets and charts wired to mock metrics service.
  - [x] Violation taxonomy panel with filtering.
- [x] Sprint 4 – Realtime Integration
  - [x] WebSocket/SSE feed connected to timeline state.
  - [x] Error and throttle handling surfaced in UI.
- [x] Sprint 5 – Privacy & Access Controls
  - [x] Integrate redaction service and authorization checks.
  - [x] Audit logging for sensitive reveals.
- [ ] Sprint 6 – Polish & Documentation
  - [ ] Responsive design & accessibility pass.
  - [ ] End-to-end test coverage and release notes.

Data & Integration Tasks
------------------------
- [x] Surface `violation_type`, `question_category`, and PII metadata in the loader for playback (adds `pii_raw_text` for gated reveals).
- [ ] Normalize judge responses to support multiple providers with differing payloads.
- [ ] Define taxonomy mapping for question categories (manual tags + heuristic classifier).
- [ ] Create data fixtures for simulation, ensuring PII redacted.

Privacy & Compliance Considerations
-----------------------------------
- Default to redacted views in UI; require explicit confirmation to reveal.
- Mask real identifiers in demo datasets via anonymization routines.
- Log all user interactions that expose sensitive data for later auditing.
- Support configurable redaction rules (regex patterns, ML detectors) to adapt to new PII types.

Testing Strategy
----------------
- Backend: schema validation tests, PII redaction unit tests, rate-limit handling integration tests.
- Frontend: component snapshots, animation regression (visual diff) for timeline, end-to-end flows covering replay, live updates, and PII reveal gating.
- Performance: ensure timeline updates remain smooth with >100 exchanges; stress-test WebSocket throughput.

Open Questions & Dependencies
-----------------------------
- Confirm target stack (React vs. Svelte) and hosting constraints.
- Decide on long-term storage (continue JSONL or migrate to DB).
- Clarify authentication/authorization model for UI users.
- Align with devops for deploying WebSocket-capable backend.

Next Update Checklist
---------------------
- [ ] Add tooltip/legend explaining weighted judge agreement KPI (allow=1, warn=0.4, block=0).
- [ ] Regroup safety violations by category/severity to reduce duplication in the sidebar.
- [ ] Tighten responsive layout for tablet/mobile breakpoints (timeline cards widen, filters collapsible).
- [x] Wire realtime `/console` submissions into the pipeline (LLM & judge selectors, live run focus mode).
- [x] Reposition realtime console beneath the conversation timeline with full-width layout for live playback.
- [x] Add stage-based animation for live playback highlighting User → LLM → Judge flow.
- [ ] Add responsive end-to-end tests (Playwright) covering filter drawer + safety history toggle.
- [ ] Document judge option requirements (Gemini API key, Ollama endpoint) in developer guide.
