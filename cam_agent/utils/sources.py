"""
Source and citation helpers shared across CAM components.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

SECTION_PATTERNS = (
    r"(A\.\d+(?:\.\d+)?)",  # APS Code: A.5.2 etc.
    r"(APP\s*\d+(?:\.\d+)?(?:\([a-z]\))?)",  # APP 6.2(b) etc.
    r"(s\s*\d+[A-Za-z]?)",  # s 150
    r"(section\s*\d+[A-Za-z]?)",  # section 150
)


def short_title(path: str) -> str:
    """Normalise file stems into readable source titles."""
    stem_raw = Path(path).stem.replace("_", " ").replace("-", " ").strip()
    stem = re.sub(r"\s+", " ", stem_raw)
    mapping = {
        "APS Code of Ethics": "APS Code of Ethics",
        "Ahpra and National Boards  Regulatory guide a full guide": "Ahpra/National Boards Regulatory Guide (Jul 2024)",
        "The Act  2009 045": "Health Practitioner Regulation National Law Act 2009",
        "The australian privacy principles": "Privacy Act 1988 (Cth) — Australian Privacy Principles (APPs)",
    }
    for key, value in mapping.items():
        normalized_key = re.sub(r"\s+", " ", key.lower())
        if normalized_key in stem.lower():
            return value
    return stem


def extract_section(text: str) -> Optional[str]:
    """Extract the first clause/section marker from supplied text."""
    for pattern in SECTION_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def make_label(title: str, passage: str) -> str:
    """Combine source title with clause annotation when available."""
    section = extract_section(passage or "")
    return f"{title} — {section}" if section else title


__all__ = ["short_title", "extract_section", "make_label", "SECTION_PATTERNS"]
