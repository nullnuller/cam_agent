# RAG Corpus Overview

This repository maintains a retrieval store that grounds CAM compliance checks in Australian healthcare regulation, ethics, and privacy guidance. The artefacts live under `project_bundle/rag_store/` and consist of:

- `index.faiss` – a FAISS `IndexFlatIP` (inner-product) matrix of dense embeddings.
- `chunks.json` – metadata for each embedded span, including the source file path, passage text, and auxiliary fields used by the evaluation harness.

## Source Documents

Documents are sourced from authoritative organisations and tracked through the helper script `download_health_regulations.sh`. The current catalogue includes:

1. **Health Practitioner Regulation National Law Act 2009** (Queensland consolidated version).
2. **National Code of Conduct for Health Care Workers** (Queensland).
3. **Ahpra / National Boards Regulatory Guide** (full guide, April 2021 release).
4. **Good Medical Practice** code of conduct for doctors in Australia (2009) and supporting commentary on 2020 updates.
5. **Australian Charter of Healthcare Rights** (2019 revision).
6. **National Statement on Ethical Conduct in Human Research** (2023).
7. **National Safety and Quality Health Service (NSQHS) Standards** (Second edition, 2021).
8. **International Council of Nurses Code of Ethics** (2021 revision).
9. **World Medical Association International Code of Medical Ethics** (2022).
10. **World Medical Association Declaration of Helsinki** (2013).
11. **Allowah Nursing Practice Standards & Code of Conduct** (policy summarising NMBA expectations).

Additional PDFs can be added to `health_docs/` and incorporated into the store during a rebuild.

## Indexing Pipeline

The current store was generated with the following process:

1. **Acquisition** – run `bash download_health_regulations.sh` to populate `health_docs/` with the latest PDF assets.
2. **Pre-processing** – extract text using PDF-to-text tooling (e.g., `pypdf`, `pdfminer.six`) and split into clause-aware chunks (~500 tokens) with overlaps to preserve context.
3. **Metadata tagging** – annotate each chunk with:
   - `path`: absolute or workspace-relative file path.
   - `text`: normalised passage text.
   - `metadata`: optional fields such as page numbers or clause identifiers.
4. **Embedding** – encode passages using `sentence-transformers/all-MiniLM-L6-v2` (normalised vectors for cosine similarity).
5. **Index build** – store embeddings in a FAISS inner-product index (`IndexFlatIP`) saved as `index.faiss`.
6. **Packaging** – write companion metadata to `chunks.json` ensuring consistent ordering with the FAISS vectors.

Rebuilding the store after document updates requires re-running steps 2–6 to keep embeddings aligned with passages. You can now execute the full refresh via:

```bash
python -m cam_agent.scripts.build_rag_store --download-dir health_docs --store-dir project_bundle/rag_store
```

Optional flags include `--force-download` to re-fetch PDFs, `--summariser-model <ollama-model>` for digest generation, and chunk sizing arguments to tune retrieval granularity.

Future milestones will further automate ingestion and validation inside the broader CAM pipeline.
