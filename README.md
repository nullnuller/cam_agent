# CAM Agent

An end-to-end compliance assurance and monitoring (CAM) agent for healthcare language-model scenarios. This project bundles:

- **RAG-backed question answering** with retrieval of regulatory documents.
- **Judge orchestration** (local MedGemma via Ollama, Gemini Flash, or both) to score safety/compliance.
- **Interactive dashboard** with live timeline playback, KPI metrics, and a realtime console to submit ad‑hoc queries.

The repository contains the Python pipeline, FastAPI UI bridge, and a React + Vite dashboard ready for local demos.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Python Environment](#python-environment)
4. [Configuring Judge Backends](#configuring-judge-backends)
5. [Running the Compliance Pipeline](#running-the-compliance-pipeline)
6. [UI Services](#ui-services)
7. [GPU & Ollama Notes](#gpu--ollama-notes)
8. [Testing](#testing)
9. [Project Structure](#project-structure)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Component | Version / Notes |
|-----------|-----------------|
| **Python** | 3.10+ (developed against 3.12) |
| **Node.js** | 18+ (recommended 20 LTS) |
| **Ollama** | 0.3.12+ with GPU support (for MedGemma judges) |
| **Google Gemini API key** | Required only if enabling the Gemini judge |
| **NVIDIA GPU** | Dual 24 GiB RTX 4090s were used in development. See [GPU & Ollama Notes](#gpu--ollama-notes) if running heavy models. |

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/nullnuller/cam_agent.git
cd cam_agent

# 2. Create and activate a Python environment
python -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install dashboard dependencies
cd ui/dashboard
npm install
cd ../..

# 5. Copy the environment template and customise it
cp .env.example .env
# edit .env to point at your Ollama endpoints, judge models, and Gemini credentials
```

Populate the regulatory knowledge base (optional but recommended) via:

```bash
./download_health_regulations.sh
```

---

## Python Environment

All Python packages live in `requirements.txt`. Activate the virtual environment before running any scripts:

```bash
source .venv/bin/activate
```

The most relevant modules:

- `cam_pipeline.py` – orchestrates ingestion, RAG lookup, model inference, and judge scoring.
- `cam_agent/services` – LLM clients, retrieval managers, and compliance rules.
- `cam_agent/ui/api.py` – FastAPI service that exposes audit logs and a realtime console for the dashboard.

---

## Configuring Judge Backends

We support three judge modes:

1. **Local Ollama (generate)** – default MedGemma judge.
2. **Local Ollama (chat endpoint)** – if you expose `/api/chat`.
3. **OpenAI-compatible REST** – for llama.cpp or hosted OpenAI models.

In `.env` choose the block that matches your setup. Example for Ollama generate endpoint:

```ini
JUDGE_MODE=ollama
JUDGE_MODEL=hf.co/bartowski/google_medgemma-27b-it-GGUF:latest
JUDGE_BASE_URL=http://localhost:11434/api/generate
```

Gemini judge configuration:

```ini
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=models/gemini-2.5-flash
GEMINI_RPM=10
```

> **Tip:** If the 27B judge OOMs on your GPU, create a Modelfile with lower `num_ctx` and `parallel` settings (see [GPU & Ollama Notes](#gpu--ollama-notes)).

---

## Running the Compliance Pipeline

```bash
source .venv/bin/activate

# Evaluate a batch of questions using the MedGemma and Gemini judges
python cam_pipeline.py \
  --questions_file project_bundle/questions.txt \
  --enable-med-judge \
  --enable-gemini-judge
```

Key outputs land under `project_bundle/`:

- `cam_suite_report.html` – interactive report.
- `cam_suite_report.json` – machine-readable summary.
- `cam_suite_audit.jsonl` – timeline audit log (consumed by the UI).

Flags of interest:

| Flag | Purpose |
|------|---------|
| `--skip-ollama-judge` | Disable the local judge while keeping Gemini. |
| `--judge-mode <ollama|gemini|both>` | Override at runtime. |
| `--refresh-store` | Rebuild the RAG store from `health_docs/`. |

---

## UI Services

### 1. FastAPI Bridge

Expose the audit log and realtime console:

```bash
source .venv/bin/activate
CAM_UI_AUDIT_LOG=project_bundle/cam_suite_audit.jsonl \
CAM_UI_API_HOST=0.0.0.0 \
CAM_UI_API_PORT=8080 \
python -m cam_agent.ui.server
```

Environment knobs:

- `CAM_UI_STORE_DIR` – override the RAG store path.
- `CAM_UI_DIGEST_PATH` – specify a digest file for judge context.
- `CAM_UI_API_RELOAD=1` – enable autoreload during development.

### 2. React Dashboard

```bash
cd ui/dashboard
npm run dev   # or npm run build && npm run preview
```

The dashboard expects `VITE_CAM_API_BASE` to point at the FastAPI server (defaults to `http://127.0.0.1:8080`).

Features:

- Animated timeline highlighting user → LLM → judge flow.
- KPI cards with weighted judge agreement, latency, violations.
- Safety panel grouped by severity and category.
- Realtime console with selectable base model and judge backend.

---

## GPU & Ollama Notes

MedGemma 27B is memory hungry. If you see `cudaMalloc failed`:

1. **Reduce concurrency:** set `OLLAMA_NUM_PARALLEL=1` or create a Modelfile with `parameter parallel 1`.
2. **Lower context:** set `num_ctx` to 4096 in the judge Modelfile or pass options with the API.
3. **Split across GPUs:** `parameter num_gpu 2` ensures weights span both 24 GiB cards.
4. **Unload other models:** `ollama ps` then `ollama stop <id>` before starting the judge.
5. **Fallback judge:** use the 4B MedGemma (`hf.co/bartowski/google_medgemma-4b-it-GGUF:latest`) for interactive demos.

Example Modelfile:

```text
FROM hf.co/bartowski/google_medgemma-27b-it-GGUF:latest
PARAMETER num_ctx 4096
PARAMETER parallel 1
PARAMETER num_gpu 2
```

Create it once:

```bash
ollama create medgemma27b-judge -f Modelfile
```

Then point `.env` `JUDGE_MODEL=medgemma27b-judge`.

---

## Testing

Python tests (pytest):

```bash
source .venv/bin/activate
pytest
```

Dashboard lint/build:

```bash
cd ui/dashboard
npm run lint
npm run build
```

---

## Project Structure

```
cam_agent/
├── cam_pipeline.py             # Batch orchestration entry-point
├── cam_agent/
│   ├── evaluation/             # Judge and scenario definitions
│   ├── services/               # LLM clients, retrieval, agent logic
│   ├── ui/                     # FastAPI bridge for the dashboard
│   └── storage/                # Audit logging utilities
├── docs/                       # Developer notes and guides
├── project_bundle/             # Generated reports, audit logs, RAG store
└── ui/dashboard/               # React + Vite SPA (timeline & console)
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Ollama HTTP 500 … cudaMalloc failed` | Apply the [GPU strategies](#gpu--ollama-notes) to reduce VRAM usage. |
| Gemini judge returns 429 | Increase `GEMINI_RPM`, add backoff, or pause before re-running the pipeline. |
| Dashboard shows `pending` judge agreement | Means no judge events were emitted. Check the FastAPI logs for `External judge returned no results`. |
| Realtime console does nothing | Ensure `CAM_UI_AUDIT_LOG` points at a writable JSONL. The UI API logs a message for each submission. |

---

Happy monitoring!
