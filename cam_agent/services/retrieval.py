"""
Retrieval manager providing FAISS-based lookups for CAM.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

try:
    import faiss  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "faiss is required for retrieval operations. Install with `pip install faiss-cpu`."
    ) from exc
import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass(slots=True)
class RetrievalResult:
    """Retrieval payload including raw hits and similarity scores."""

    hits: List[Dict]
    scores: List[float]
    query_embedding: Optional[np.ndarray] = None


class RetrievalManager:
    """Loads sentence-transformer embeddings and performs FAISS searches."""

    def __init__(
        self,
        store_dir: Path,
        *,
        embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.store_dir = store_dir
        self.embed_model = embed_model
        self.index = self._load_index()
        self.chunks = self._load_chunks()
        self.encoder = SentenceTransformer(embed_model)

    def _load_index(self) -> faiss.Index:
        index_path = self.store_dir / "index.faiss"
        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {index_path}")
        return faiss.read_index(str(index_path))

    def _load_chunks(self) -> List[Dict]:
        chunks_path = self.store_dir / "chunks.json"
        if not chunks_path.exists():
            raise FileNotFoundError(f"Chunk metadata not found at {chunks_path}")
        return json.loads(chunks_path.read_text(encoding="utf-8"))

    def search(
        self,
        query: str,
        *,
        top_k: int = 12,
        min_sim: float = 0.2,
        normalize: bool = True,
    ) -> RetrievalResult:
        """Return best-matching passages for the query."""
        embedding = self.encoder.encode([query], normalize_embeddings=normalize)
        distances, indices = self.index.search(embedding.astype("float32"), top_k)

        scores = distances[0].tolist() if len(distances) else []
        hits: List[Dict] = []
        for idx in indices[0]:
            if idx == -1:
                continue
            hits.append(self.chunks[int(idx)])

        filtered_hits = []
        filtered_scores = []
        for score, hit in zip(scores, hits):
            if score >= min_sim:
                filtered_hits.append(hit)
                filtered_scores.append(float(score))

        return RetrievalResult(
            hits=filtered_hits,
            scores=filtered_scores,
            query_embedding=embedding[0],
        )


__all__ = ["RetrievalManager", "RetrievalResult"]
