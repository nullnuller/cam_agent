"""Checksum helpers for regression validation of RAG assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, Tuple


def compute_directory_checksums(path: Path, patterns: Iterable[str] = ("*.json", "*.faiss")) -> Dict[str, str]:
    """Compute SHA256 checksums for matching files in a directory."""
    checksums: Dict[str, str] = {}
    for pattern in patterns:
        for file_path in sorted(path.glob(pattern)):
            checksums[file_path.name] = sha256_of_file(file_path)
    return checksums


def sha256_of_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checksums(actual: Dict[str, str], expected: Dict[str, str]) -> Tuple[bool, Dict[str, Tuple[str, str]]]:
    """Compare computed checksums with expected mapping."""
    mismatches: Dict[str, Tuple[str, str]] = {}
    success = True
    for name, expected_hash in expected.items():
        actual_hash = actual.get(name)
        if actual_hash != expected_hash:
            mismatches[name] = (expected_hash, actual_hash or "missing")
            success = False
    for name, actual_hash in actual.items():
        if name not in expected:
            mismatches[name] = ("unexpected", actual_hash)
            success = False
    return success, mismatches


def load_checksums(path: Path) -> Dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_checksums(path: Path, data: Dict[str, str]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

