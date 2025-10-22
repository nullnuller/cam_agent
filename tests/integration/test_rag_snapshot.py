import json
from pathlib import Path

import pytest

from cam_agent.utils.checksum import compute_directory_checksums, load_checksums, verify_checksums


@pytest.fixture
def sample_store(tmp_path):
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    (store_dir / "chunks.json").write_text(json.dumps([{"path": "doc.pdf", "text": "Sample"}]), encoding="utf-8")
    (store_dir / "index.faiss").write_bytes(b"faiss")
    return store_dir


def test_rag_snapshot_validation(sample_store, tmp_path):
    snapshot = tmp_path / "snapshot.json"
    computed = compute_directory_checksums(sample_store)
    snapshot.write_text(json.dumps(computed), encoding="utf-8")

    stored = load_checksums(snapshot)
    ok, mismatches = verify_checksums(computed, stored)
    assert ok
    assert mismatches == {}

    stored["chunks.json"] = "tampered"
    ok, mismatches = verify_checksums(computed, stored)
    assert not ok
    assert "chunks.json" in mismatches
