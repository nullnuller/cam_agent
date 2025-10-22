"""
Regulatory knowledge-base pipeline.

Provides utilities to acquire documents, chunk them into retrieval-friendly
passages, embed them with SentenceTransformers, build a FAISS index, and
assemble a long-form digest suitable for judge prompts.
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from cam_agent.services.models import ensure_ollama_endpoint
from cam_agent.utils.sources import make_label, short_title

try:
    from pypdf import PdfReader  # type: ignore
except ImportError:  # pragma: no cover - dependency hint
    PdfReader = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class IngestionResult:
    """Artifacts produced after document acquisition."""

    documents: List[Path]
    download_dir: Path


@dataclass(slots=True)
class ChunkRecord:
    """Single retrieval chunk with metadata."""

    chunk_id: str
    path: str
    text: str
    metadata: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "path": self.path,
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class DigestResult:
    """Summary artifact capturing long-form digest output."""

    digest_text: str
    per_document: Dict[str, str]
    output_path: Optional[Path] = None


def ensure_documents(
    download_dir: Path,
    *,
    download_script: Optional[Path] = None,
    force: bool = False,
) -> IngestionResult:
    """
    Ensure regulatory PDFs exist locally.

    If the directory is empty or `force=True`, runs the shell download script.
    """

    download_dir.mkdir(parents=True, exist_ok=True)

    if download_script is None:
        download_script = REPO_ROOT / "download_health_regulations.sh"

    pdfs = sorted(download_dir.glob("*.pdf"))
    if pdfs and not force:
        invalid = [p for p in pdfs if p.stat().st_size == 0]
        if not invalid:
            return IngestionResult(documents=pdfs, download_dir=download_dir)
        else:
            print(f"[kb] Detected {len(invalid)} zero-byte files; re-downloading corpus …")

    if not download_script.exists():
        raise FileNotFoundError(f"Download script not found at {download_script}")

    print(f"[kb] Downloading regulatory PDFs via {download_script.name} …")
    subprocess.run(
        ["bash", str(download_script)],
        cwd=str(download_script.parent),
        check=True,
    )
    pdfs = sorted(download_dir.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"No PDFs found in {download_dir} after download.")
    invalid = [p for p in pdfs if p.stat().st_size == 0]
    if invalid:
        names = ", ".join(p.name for p in invalid)
        raise RuntimeError(f"The following PDFs appear empty after download: {names}. Check source URLs.")
    return IngestionResult(documents=pdfs, download_dir=download_dir)


def extract_pdf_text(pdf_path: Path) -> List[str]:
    """Extract raw text per page from a PDF file."""
    if PdfReader is None:
        raise RuntimeError(
            "pypdf is required to extract text. Install with `pip install pypdf`."
        )
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"Failed to read PDF {pdf_path.name}: {exc}") from exc
    pages: List[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return pages


def clean_text(text: str) -> str:
    """Light normalisation for extracted PDF text."""
    text = text.replace("\u00a0", " ")
    text = text.replace("•", "-")
    return "\n".join(line.strip() for line in text.splitlines())


def chunk_text(
    paragraphs: Sequence[str],
    *,
    chunk_size_words: int = 280,
    overlap_words: int = 60,
) -> List[Tuple[str, int, int]]:
    """
    Build overlapping chunks from paragraph sequence.

    Returns list of (chunk_text, word_start, word_end) tuples.
    """

    chunks: List[Tuple[str, int, int]] = []
    buffer: List[str] = []
    word_count = 0
    start_word = 0

    def flush_buffer(end_word: int) -> None:
        nonlocal buffer, start_word
        if not buffer:
            return
        chunk = "\n\n".join(buffer).strip()
        if chunk:
            chunks.append((chunk, start_word, end_word))
        start_word = max(end_word - overlap_words, 0)
        buffer = []

    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            continue
        if word_count - start_word + len(words) > chunk_size_words and buffer:
            flush_buffer(word_count)
        buffer.append(paragraph)
        word_count += len(words)
    flush_buffer(word_count)
    return chunks


def chunk_documents(
    documents: Iterable[Path],
    *,
    chunk_size_words: int = 280,
    overlap_words: int = 60,
) -> List[ChunkRecord]:
    """Convert PDFs into chunk records ready for embedding."""
    records: List[ChunkRecord] = []
    skipped: List[Path] = []
    for doc in documents:
        print(f"[kb] Chunking {doc.name}")
        try:
            pages = extract_pdf_text(doc)
        except RuntimeError as exc:
            print(f"[kb] Warning: skipping {doc.name} — {exc}")
            skipped.append(doc)
            continue
        paragraphs = []
        for i, page in enumerate(pages, start=1):
            cleaned = clean_text(page)
            if cleaned:
                paragraphs.extend([p.strip() for p in cleaned.split("\n\n") if p.strip()])
        chunks = chunk_text(paragraphs, chunk_size_words=chunk_size_words, overlap_words=overlap_words)
        for idx, (chunk, word_start, word_end) in enumerate(chunks, start=1):
            title = short_title(doc.name)
            label = make_label(title, chunk)
            metadata = {
                "source_title": title,
                "label": label,
                "word_start": word_start,
                "word_end": word_end,
            }
            records.append(
                ChunkRecord(
                    chunk_id=f"{doc.name}::chunk-{idx}",
                    path=str(doc),
                    text=chunk,
                    metadata=metadata,
                )
            )
    if skipped:
        print("[kb] Skipped documents:")
        for doc in skipped:
            print(f"  - {doc.name}")
    return records


def build_faiss_index(
    chunks: Sequence[ChunkRecord],
    *,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> Tuple[faiss.Index, np.ndarray]:
    """Embed chunks and return FAISS index along with embedding matrix."""
    model = SentenceTransformer(embed_model)
    texts = [record.text for record in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True)
    embeddings = embeddings.astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return index, embeddings


def build_store(
    store_dir: Path,
    chunks: Sequence[ChunkRecord],
    index: faiss.Index,
) -> None:
    """Persist FAISS index and chunk metadata to disk."""
    store_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(store_dir / "index.faiss"))
    chunk_payload = [chunk.to_dict() for chunk in chunks]
    (store_dir / "chunks.json").write_text(
        json.dumps(chunk_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[kb] Store written to {store_dir}")


def make_summary_prompt(title: str, text: str) -> str:
    """Build summarisation prompt for LLM-based digest generation."""
    return textwrap.dedent(
        f"""
        You are preparing a concise regulatory summary for CAM compliance reviewers.
        Source: {title}

        Summarise the key duties, prohibitions, and escalation requirements in bullet points.
        Preserve clause identifiers when present. Keep the summary under 500 words.

        Text:
        {text}
        """
    ).strip()


def call_ollama(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.2,
    num_ctx: int = 8192,
    num_predict: Optional[int] = None,
    timeout: int = 600,
) -> str:
    """Best-effort Ollama wrapper used for summarisation."""
    import requests  # local import to avoid mandatory dependency

    raw_endpoint = os.getenv("OLLAMA_ENDPOINT") or "http://localhost:11434/api/generate"
    endpoint = ensure_ollama_endpoint(raw_endpoint, "api/generate")
    auth = os.getenv("OLLAMA_BEARER")
    headers = {"Authorization": f"Bearer {auth}"} if auth else {}
    headers["Content-Type"] = "application/json"

    options: Dict[str, int | float] = {"temperature": temperature, "num_ctx": num_ctx}
    if num_predict is not None:
        options["num_predict"] = int(num_predict)

    try:
        response = requests.post(
            endpoint,
            json={"model": model, "prompt": prompt, "stream": False, "options": options},
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama request failed for model '{model}' at {endpoint}: {exc}") from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = (response.text or "").strip()
        preview = body[:1000]
        if len(body) > len(preview):
            preview += "…"
        raise RuntimeError(
            f"Ollama HTTP {response.status_code} for model '{model}' at {endpoint}: {preview}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        body = (response.text or "").strip()
        preview = body[:500]
        if len(body) > len(preview):
            preview += "…"
        raise RuntimeError(
            f"Ollama returned non-JSON payload for model '{model}' at {endpoint}: {preview}"
        ) from exc
    return payload.get("response", "")


def generate_digest(
    documents: Iterable[Path],
    *,
    digest_path: Path,
    summariser_model: Optional[str] = None,
    max_tokens: int = 1_000_000,
) -> DigestResult:
    """
    Produce a long-form digest across documents.

    If `summariser_model` is provided, uses Ollama to summarise each document.
    Otherwise falls back to truncation.
    """

    per_document: Dict[str, str] = {}
    token_budget = 0

    for doc in documents:
        print(f"[kb] Summarising {doc.name}")
        try:
            text = "\n\n".join(clean_text(page) for page in extract_pdf_text(doc))
        except RuntimeError as exc:
            print(f"[kb] Warning: skipping digest for {doc.name} — {exc}")
            continue
        title = short_title(doc.name)
        if summariser_model:
            prompt = make_summary_prompt(title, text)
            try:
                summary = call_ollama(summariser_model, prompt)
            except Exception as exc:  # pragma: no cover - best effort fallback
                print(f"[kb] Warning: summariser failed for {doc.name}: {exc}")
                summary = textwrap.shorten(text, width=2000, placeholder="…")
        else:
            summary = textwrap.shorten(text, width=2000, placeholder="…")
        per_document[title] = summary
        token_budget += len(summary.split())

    digest_lines = []
    for title, summary in per_document.items():
        digest_lines.append(f"# {title}\n{summary}\n")

    digest_text = "\n".join(digest_lines)

    if len(digest_text.split()) > max_tokens:
        digest_text = textwrap.shorten(
            digest_text, width=max_tokens * 5, placeholder="\n… [truncated]\n"
        )

    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(digest_text, encoding="utf-8")
    print(f"[kb] Digest written to {digest_path}")
    return DigestResult(digest_text=digest_text, per_document=per_document, output_path=digest_path)


__all__ = [
    "IngestionResult",
    "ChunkRecord",
    "DigestResult",
    "ensure_documents",
    "extract_pdf_text",
    "chunk_documents",
    "build_faiss_index",
    "build_store",
    "generate_digest",
]
