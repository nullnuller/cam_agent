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

        if filtered_hits:
            filtered_hits, filtered_scores = self._rebalance_hits(
                query,
                filtered_hits,
                filtered_scores,
            )

        return RetrievalResult(
            hits=filtered_hits,
            scores=filtered_scores,
            query_embedding=embedding[0],
        )

    def _rebalance_hits(
        self,
        query: str,
        hits: Sequence[Dict],
        scores: Sequence[float],
    ) -> tuple[List[Dict], List[float]]:
        """Down-rank research-only chunks for clinical privacy questions."""

        if not _should_bias_clinical(query):
            return list(hits), list(scores)

        reweighted: List[tuple[float, float, Dict]] = []
        for hit, score in zip(hits, scores):
            bonus = _score_adjustment(hit)
            reweighted.append((score + bonus, float(score), hit))

        reweighted.sort(key=lambda item: item[0], reverse=True)
        sorted_hits = [item[2] for item in reweighted]
        sorted_scores = [item[1] for item in reweighted]
        return sorted_hits, sorted_scores


CLINICAL_QUERY_TERMS = (
    "privacy",
    "confidential",
    "notes",
    "app ",
    "app",
    "consent",
    "disclose",
    "record",
    "release",
)

CLINICAL_SOURCE_HINTS = (
    "app_privacy_principles",
    "privacy_act",
    "privacy_principles",
    "health_practitioner_regulation",
    "ahpra",
    "aps_code",
    "oaic",
)

RESEARCH_SOURCE_HINTS = (
    "national_statement",
    "helsinki",
    "research",
    "human_research",
)


def _should_bias_clinical(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in CLINICAL_QUERY_TERMS)


def _score_adjustment(hit: Dict) -> float:
    path = str(hit.get("path", "")).lower()
    label = str(hit.get("metadata", {}).get("label", "")).lower()
    text = str(hit.get("text", "")).lower()

    bonus = 0.0
    if any(term in path or term in label for term in CLINICAL_SOURCE_HINTS):
        bonus += 0.08
    if any(term in text for term in ("app ", "app", "privacy principle")):
        bonus += 0.04
    if any(term in path or term in label for term in RESEARCH_SOURCE_HINTS):
        bonus -= 0.12
    return bonus


__all__ = ["RetrievalManager", "RetrievalResult"]
