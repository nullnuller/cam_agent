CAM Developer Guide
===================

This guide outlines how to set up, extend, and contribute to the CAM framework.

## 1. Environment Setup

1. **Python** – Use Python 3.11+ (project currently tested on 3.12). Create a virtualenv and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Optional libraries** – Some features (FAISS, sentence transformers, Ollama) require native dependencies.
   - *FAISS*: Install via `pip install faiss-cpu` or follow platform-specific instructions.
   - *Sentence Transformers*: Managed through `pip install sentence-transformers`.
   - *Ollama*: Install the service and ensure `OLLAMA_ENDPOINT` is reachable if running locally.

3. **Environment variables**:
   - Judge backend (see `.env.example` for ready-to-copy blocks):
     - `JUDGE_MODE` (`ollama`, `ollama_chat`, or `openai`)
     - `JUDGE_BASE_URL`, `JUDGE_MODEL`, and either `JUDGE_BEARER` or `JUDGE_API_KEY`
   - CAM runtime LLM:
     - `LLM_API_MODE` plus any provider-specific settings (`OLLAMA_ENDPOINT`, `OPENAI_ENDPOINT`, etc.)
   - Gemini evaluation (optional): `GEMINI_API_KEY`

## 2. Project Layout

- `cam_agent/` – Source packages.
  - `knowledge/` – RAG ingestion pipeline.
  - `services/` – Orchestration, compliance agent, retrieval manager.
  - `evaluation/` – Scenario harnesses, metrics, judges.
  - `utils/` – Shared helpers (citations, checksums, etc.).
- `project_bundle/` – Legacy assets (questions, default CLI wrappers).
- `docs/` – Documentation, including pipeline usage and playbooks.
- `tests/` – Unit + integration suites.

## 3. Typical Workflow

1. Refresh the RAG store if documents changed:
   ```bash
   python cam_agent/scripts/build_rag_store.py --questions_file project_bundle/questions.txt
   ```
2. Run end-to-end pipeline:
   ```bash
   python cam_pipeline.py \
     --questions_file project_bundle/questions.txt \
     --refresh-store \
     --enable_med_judge
   ```
3. Start the OpenAI-compatible proxy (optional):
   ```bash
   python -m cam_agent.scripts.openai_proxy --host 127.0.0.1 --port 8000
   ```
   Then point OpenAI SDKs to `http://127.0.0.1:8000/v1`.
   > Requires `fastapi` and `uvicorn` (`pip install fastapi uvicorn`).
4. Update `.env` (copy from `.env.example`) with model names matching the `ollama list` output on *your* machine and Gemini config (e.g., `GEMINI_MODEL=models/gemini-2.0-flash`, `GEMINI_RPM=10`).
   - To route generation through Ollama's chat endpoint (recommended), set `LLM_API_MODE=ollama_chat` (default in `.env.example`). For an OpenAI-compatible endpoint, set `LLM_API_MODE=openai` and optionally `OPENAI_ENDPOINT` / `OPENAI_API_KEY`.
   - Choose the judge backend by selecting the appropriate `JUDGE_MODE` block (Ollama, Ollama chat, or OpenAI-compatible) and setting `JUDGE_BASE_URL` / auth variables accordingly.
   - If your GPU runs out of memory with MedGemma 27B, set `JUDGE_NUM_CTX=4096` (or similar) in `.env` to shrink the context window before falling back to smaller models.
3. Execute tests before committing:
   ```bash
   pytest
   ```

## 4. Extending CAM

### Compliance Rules

1. Add new rule definitions in `cam_agent/compliance/rules.py`.
2. Map rule IDs to regulation clauses where possible.
3. Update tests in `tests/unit/test_compliance_rules.py` to cover new logic.

### Retrieval & Sources

1. Add new PDFs to `health_docs/` (or adjust the download script).
2. Rebuild the RAG store via `build_rag_store.py` or the pipeline.
3. Verify new chunks with the checksum snapshot tests.

### LLM Scenarios

1. Extend `cam_agent/config/models.py` with additional `ModelConfig` entries.
2. Ensure `default_scenarios` picks up new IDs, and update documentation accordingly.
3. Modify `cam_agent/evaluation/runner.py` if scenario-specific behavior is required.

## 5. Coding Standards

- **Type hints**: Mandatory for new public functions/classes.
- **Logging**: Use straightforward `print` for CLI progress; reserve structured logging for future integration.
- **Tests**: For each new module, add unit tests; integration tests should cover critical paths.
- **Style**: Follow existing patterns (PEP8, dataclass usage, minimal inline comments unless complexity warrants).

## 6. UI Dashboard (Realtime Playback)

1. **Start the UI API service** (FastAPI + SSE):
   ```bash
   CAM_UI_AUDIT_LOG=project_bundle/cam_suite_audit.jsonl \
   CAM_UI_REVEAL_LOG=project_bundle/cam_ui_reveals.jsonl \
   CAM_UI_STORE_DIR=project_bundle/rag_store \
   CAM_UI_DIGEST_PATH=project_bundle/regulatory_digest.md \
   CAM_UI_API_HOST=0.0.0.0 \
   CAM_UI_API_PORT=8080 \
   python -m cam_agent.ui.server
   ```
   - `CAM_UI_AUDIT_LOG` defaults to `project_bundle/cam_suite_audit.jsonl`.
   - `CAM_UI_REVEAL_LOG` records audit entries when operators reveal PII-rich content (optional).
   - Set `CAM_UI_API_RELOAD=1` during development for auto-reload.
2. **Run the React dashboard** (Tailwind + Vite):
   ```bash
   cd ui/dashboard
   npm install
   VITE_CAM_API_BASE=http://localhost:8080 npm run dev
   ```
   Use `npm run build` for production bundles (already wired to TypeScript `tsc -b`).
3. **Key endpoints & behaviours**
   - `/stream?run_id=<id>` emits Server-Sent Events with heartbeat + auto-reconnect; the UI merges these with historical audits.
   - `/reveal` accepts POST payloads and appends JSONL entries to the reveal log for privacy auditing.
   - The timeline renders redacted text by default; clicking "Reveal full response" logs the action before showing raw content when available.
   - `/console/options` advertises available base scenarios and judge providers; `/console` runs a live query (requires RAG store + any selected judge credentials).
     - **llama.cpp judge** runs via `JUDGE_MODE=openai` with endpoints like `http://localhost:8678/v1/chat/completions`.
     - **Ollama judge** uses `JUDGE_MODE=ollama`/`ollama_chat` (`OLLAMA_*` overrides honoured).
     - **Gemini judge** needs `GEMINI_API_KEY` (and optional `GEMINI_MODEL` / `GEMINI_RPM`).
   - Ensure your `.env` aligns base model names with the runtime:
     ```env
     CAM_MODEL_GEMMA_BASE=gemma3-4B-128k:latest
     CAM_MODEL_MEDGEMMA_SMALL=hf.co/bartowski/google_medgemma-4b-it-GGUF:latest
     CAM_MODEL_MEDGEMMA_LARGE=google_medgemma-27b
     CAM_MODEL_MEDGEMMA_LARGE_API_MODE=openai
     CAM_MODEL_MEDGEMMA_LARGE_ENDPOINT=http://localhost:8678/v1/chat/completions
     ```

## 7. Checklist Before PR

- [ ] `pytest` passes (with optional dependencies installed where applicable).
- [ ] Docs updated if user-facing behavior changes.
- [ ] `cam_pipeline.py` runs on sample questions without errors.
- [ ] No lingering TODOs unless tracked in roadmap.
- [ ] Plan (`PLAN.md`) updated to reflect task status.
