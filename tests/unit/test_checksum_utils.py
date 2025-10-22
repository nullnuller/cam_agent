from pathlib import Path

from cam_agent.utils.checksum import compute_directory_checksums, verify_checksums, save_checksums, load_checksums


def test_compute_and_verify_checksums(tmp_path):
    file1 = tmp_path / "a.json"
    file1.write_text("{\"key\": \"value\"}", encoding="utf-8")
    file2 = tmp_path / "b.faiss"
    file2.write_bytes(b"binary data")

    checksums = compute_directory_checksums(tmp_path)
    assert "a.json" in checksums and "b.faiss" in checksums

    ok, mismatches = verify_checksums(checksums, checksums)
    assert ok
    assert mismatches == {}

    tampered = dict(checksums)
    tampered["a.json"] = "different"
    ok, mismatches = verify_checksums(checksums, tampered)
    assert not ok
    assert "a.json" in mismatches


def test_save_and_load_checksums(tmp_path):
    payload = {"file": "hash"}
    path = tmp_path / "checksums.json"
    save_checksums(path, payload)
    loaded = load_checksums(path)
    assert loaded == payload
