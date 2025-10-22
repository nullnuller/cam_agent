import json
from pathlib import Path

import numpy as np
import pytest

faiss = pytest.importorskip("faiss", reason="faiss library is required for integration tests")

from cam_agent.services.cam_agent import CAMAgent
from cam_agent.services.types import QueryRequest


@pytest.fixture
def sample_store(tmp_path):
    store_dir = tmp_path / "rag_store"
    store_dir.mkdir()
    chunks = [
        {
            "path": "doc.pdf",
            "text": "APP 6.2(b) allows disclosure to enforcement bodies.",
            "metadata": {}
        }
    ]
    (store_dir / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")

    import numpy as np

    embeddings = np.array([[1.0, 0.0]], dtype="float32")
    index = faiss.IndexFlatIP(2)
    index.add(embeddings)
    faiss.write_index(index, str(store_dir / "index.faiss"))
    return store_dir


@pytest.fixture
def audit_log(tmp_path):
    return tmp_path / "audit.jsonl"


def test_cam_agent_basic_flow(monkeypatch, sample_store, audit_log):
    from cam_agent.config.models import SCENARIOS

    monkeypatch.setattr(
        "cam_agent.services.models.LLMClient.call",
        lambda self, model, prompt, **kwargs: type("Resp", (), {"text": "Provide general info. Seek professional advice."})(),
    )

    agent = CAMAgent(store_dir=sample_store, audit_log_path=audit_log, scenarios=SCENARIOS)
    request = QueryRequest(user_id="u1", question="What is APP 6.2(b)?")
    response = agent.handle_request("B", request)

    assert response.action in {"allow", "warn"}
    assert response.final_text
    assert audit_log.exists()
