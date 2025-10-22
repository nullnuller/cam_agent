from pathlib import Path

import json
import numpy as np
import pytest

faiss = pytest.importorskip("faiss", reason="faiss library is required for retrieval tests")

from cam_agent.services.retrieval import RetrievalManager


@pytest.fixture
def mock_store(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    chunks = [
        {"path": "doc1.pdf", "text": "Confidentiality under APS Code A.5.1", "metadata": {}},
        {"path": "doc2.pdf", "text": "APP 6.2(b) permits disclosure", "metadata": {}},
    ]
    (store_dir / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")

    embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32")
    index = faiss.IndexFlatIP(2)
    index.add(embeddings)
    faiss.write_index(index, str(store_dir / "index.faiss"))

    return store_dir


def test_retrieval_manager_returns_hits(mock_store, monkeypatch):
    monkeypatch.setattr(
        "cam_agent.services.retrieval.SentenceTransformer.encode",
        lambda self, texts, normalize_embeddings=True: np.array([[1.0, 0.0]]),
    )

    rm = RetrievalManager(mock_store, embed_model="dummy-model")
    result = rm.search("confidentiality", top_k=2, min_sim=0.1)
    assert len(result.hits) == 1
    assert result.hits[0]["text"].startswith("Confidentiality")
    assert result.scores[0] == 1.0


def test_retrieval_manager_filters_low_similarity(mock_store, monkeypatch):
    monkeypatch.setattr(
        "cam_agent.services.retrieval.SentenceTransformer.encode",
        lambda self, texts, normalize_embeddings=True: np.array([[0.0, 0.0]]),
    )

    rm = RetrievalManager(mock_store, embed_model="dummy-model")
    result = rm.search("irrelevant", top_k=2, min_sim=0.5)
    assert result.hits == []
    assert result.scores == []
