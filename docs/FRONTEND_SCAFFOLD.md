CAM UI Frontend Scaffold
========================

Purpose
-------
Outline the initial project structure and tooling required to boot the animated CAM dashboard frontend.

Tech Stack
----------
- Framework: React 18 + TypeScript.
- State: Zustand for lightweight global store; React Query for data fetching.
- Styling: Tailwind CSS with custom theme tokens for CAM branding.
- Animation: Framer Motion for timeline transitions, react-spring optional for metric widgets.
- Charts: Recharts for KPI visualisations.
- Build tooling: Vite for dev server and bundling.
- Testing: Vitest + React Testing Library; Playwright for smoke E2E.

Scaffold Steps
--------------
1. Create project root `ui/dashboard` with Vite template `npm init vite@latest ui/dashboard -- --template react-ts`.
   - Already generated in repo; run `npm install` inside `ui/dashboard` to bootstrap.
2. Adopt workspace layout:
   ```
   ui/
     dashboard/
       src/
         components/
         features/
           timeline/
           metrics/
           safety/
           console/
         hooks/
         providers/
         routes/
         styles/
         types/
       public/
       package.json
       tsconfig.json
   ```
3. Install dependencies:
   - `react`, `react-dom`, `zustand`, `@tanstack/react-query`, `framer-motion`, `recharts`, `tailwindcss@^3`, `postcss`, `autoprefixer`.
   - Dev tools: `typescript`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `playwright`.
4. Configure Tailwind with CAM-specific colour palette and typography tokens.
5. Define shared TypeScript interfaces mirroring `cam_agent/ui/events.py` schemas (generate from JSON schema).
6. Set up environment handling (`.env.local`) to point at local API gateway (`VITE_CAM_API_BASE`, `VITE_CAM_WS_URL`).

Initial Feature Stubs
---------------------
- `features/timeline`: timeline container with mocked event data and animation via Framer Motion. **Implemented** with demo payloads.
- `features/metrics`: KPI widgets displaying static sample metrics from fixtures. **Implemented** in `src/features/metrics/MetricsPanel.tsx`.
- `features/console`: simple form posting to `/api/console` (stubbed response). **Implemented** as `LiveConsole`.
- `providers/event-stream.tsx`: hook for consuming WebSocket or SSE stream, defaulting to mock data when offline.
- Timeline playback controls with play/pause, scrubber, and adjustable speed are available in `src/features/timeline/PlaybackControls.tsx`, driving incremental reveal during demos.
- Filter chips for question categories and violation taxonomy ship in `src/features/filters/FilterPanel.tsx`; selections update both the timeline and derived metrics.
- KPI cards in `MetricsPanel` consume the currently displayed (and filtered) timeline events, so latency and violation counts refresh as you scrub or filter.
- Timeline cards render a single active turn by default, expanding to full history via “Show All”; judge verdict cards animate with severity cues (green/amber/red) and offer “Show more” toggles for long responses (`src/features/timeline/Timeline.tsx`).

Using Existing Pipeline Results
-------------------------------
- Launch the FastAPI bridge that exposes timeline events from the pipeline audit log:
  ```
  CAM_UI_AUDIT_LOG=project_bundle/cam_suite_audit.jsonl \
  CAM_UI_API_HOST=0.0.0.0 \
  CAM_UI_API_PORT=8080 \
  CAM_UI_API_RELOAD=1 \
  python -m cam_agent.ui.server
  ```
- Copy `.env.example` to `.env.local` under `ui/dashboard` and set `VITE_CAM_API_BASE` to the API URL (defaults to `http://localhost:8000`).
- Run the dashboard with `npm run dev`. The run selector will list available audit runs, and selecting one will stream the enriched timeline and compliance violations.
- If the API is unreachable, the UI falls back to internal demo data and displays an alert so the user can still explore the interaction flow.

Developer Workflows
-------------------
- `npm run dev`: start Vite dev server.
- `npm run lint`: run ESLint (configure with recommended React + TypeScript rules).
- `npm run test`: Vitest unit tests.
- `npm run e2e`: Playwright smoke tests (uses mock API server).

Next Steps
----------
- Generate TypeScript types directly from `get_timeline_event_schema()` using `json-schema-to-typescript`.
- Build mock API server (Node/Express or Python FastAPI runner) to serve historical events during development.
- Establish CI job to run Vitest + Playwright on PRs.
- Implement playback controller and filtering interactions for violation taxonomy dashboard.
