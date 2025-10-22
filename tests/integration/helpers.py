import json
from pathlib import Path

from cam_agent.utils.checksum import compute_directory_checksums, load_checksums, save_checksums, verify_checksums


class RagStoreValidator:
    def __init__(self, store_dir: Path, snapshot_path: Path):
        self.store_dir = store_dir
        self.snapshot_path = snapshot_path

    def compute(self):
        return compute_directory_checksums(self.store_dir)

    def snapshot(self, data):
        save_checksums(self.snapshot_path, data)

    def validate(self, data):
        expected = load_checksums(self.snapshot_path)
        return verify_checksums(data, expected)
