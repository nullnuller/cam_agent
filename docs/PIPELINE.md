CAM Automation Pipeline
=======================

Run the end-to-end CAM workflow with the `cam_pipeline.py` CLI. It coordinates:

1. Ensuring regulatory PDFs are present (optionally re-downloading via `download_health_regulations.sh`).
2. Chunking and embedding to rebuild the FAISS-backed RAG store.
3. Generating a long-form digest for judge prompts.
4. Executing CAM evaluation scenarios (A–F) with optional judge scoring.
5. Writing HTML/JSON reports and appending detailed audit logs.

## Basic usage

```bash
python cam_pipeline.py \
  --questions_file project_bundle/questions.txt \
  --refresh-store \
  --enable_med_judge \
  --enable_gemini_judge
```

Key outputs (defaults can be overridden with CLI flags):

- RAG store: `project_bundle/rag_store/`
- Digest: `project_bundle/regulatory_digest.md`
- Reports: `project_bundle/cam_suite_report.html` and `.json`
- Audit log: `project_bundle/cam_suite_audit.jsonl`

## Useful flags

- `--refresh-store` rebuilds FAISS index + chunk metadata before evaluation.
- `--force-download` re-fetches PDFs even if `health_docs/` already exists.
- `--summariser-model <ollama-model>` uses a local model to condense documents while staying under token limits.
- `--scenarios B,D,F` restricts evaluation to selected scenario IDs.
- `--enable_med_judge` and `--enable_gemini_judge` toggle judge integrations.
- `--no-judges` runs CAM without judge scoring.
- `--dry-run` performs ingestion/digest steps only, skipping scenario runs.

## Error handling

The pipeline surfaces clear error messages if prerequisites are missing (e.g., questions file, FAISS store). Each stage exits early on failure to avoid partial state. Judge execution is optional, so missing API credentials will simply disable the corresponding judge with a warning.

Refer to `python cam_pipeline.py --help` for the full list of options.

