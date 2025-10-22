"""
Knowledge-base ingestion and indexing pipeline for CAM.

Utilities here manage document acquisition, chunking, embedding, and digest
generation for regulatory corpora.
"""

from .pipeline import (
    ChunkRecord,
    DigestResult,
    IngestionResult,
    build_faiss_index,
    build_store,
    chunk_documents,
    ensure_documents,
    generate_digest,
)

__all__ = [
    "ChunkRecord",
    "DigestResult",
    "IngestionResult",
    "build_faiss_index",
    "build_store",
    "chunk_documents",
    "ensure_documents",
    "generate_digest",
]

