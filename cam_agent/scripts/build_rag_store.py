"""
CLI to rebuild the regulatory RAG store and digest.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cam_agent.knowledge import (
    build_faiss_index,
    build_store,
    chunk_documents,
    ensure_documents,
    generate_digest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild CAM regulatory RAG store.")
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("health_docs"),
        help="Directory containing regulatory PDFs (downloaded if missing).",
    )
    parser.add_argument(
        "--store-dir",
        type=Path,
        default=Path("project_bundle") / "rag_store",
        help="Output directory for FAISS index and chunks.json.",
    )
    parser.add_argument(
        "--digest-path",
        type=Path,
        default=Path("project_bundle") / "regulatory_digest.md",
        help="Output path for long-form digest.",
    )
    parser.add_argument(
        "--embed-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformer model id.",
    )
    parser.add_argument(
        "--summariser-model",
        default=None,
        help="Optional Ollama model for digest summarisation.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download of PDFs even if directory is populated.",
    )
    parser.add_argument(
        "--chunk-size-words",
        type=int,
        default=280,
        help="Approximate chunk size (word count).",
    )
    parser.add_argument(
        "--overlap-words",
        type=int,
        default=60,
        help="Approximate overlap between chunks (word count).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ingestion = ensure_documents(args.download_dir, force=args.force_download)
    chunks = chunk_documents(
        ingestion.documents,
        chunk_size_words=args.chunk_size_words,
        overlap_words=args.overlap_words,
    )

    index, _embeddings = build_faiss_index(chunks, embed_model=args.embed_model)
    build_store(args.store_dir, chunks, index)

    generate_digest(
        ingestion.documents,
        digest_path=args.digest_path,
        summariser_model=args.summariser_model,
    )


if __name__ == "__main__":
    main()

