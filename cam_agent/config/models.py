"""
Model scenario definitions for CAM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ModelConfig:
    """LLM configuration entry."""

    name: str
    use_rag: bool
    embed_model: Optional[str] = None
    num_ctx: int = 8192
    temperature: float = 0.2
    num_predict: Optional[int] = None
    seed: Optional[int] = None


# Resolve model names from environment (fallback to previous defaults)
GEMMA_BASE = os.getenv("CAM_MODEL_GEMMA_BASE", "gemma3:4b")
MEDGEMMA_SMALL = os.getenv("CAM_MODEL_MEDGEMMA_SMALL", "alibayram/medgemma:4b")
MEDGEMMA_LARGE = os.getenv("CAM_MODEL_MEDGEMMA_LARGE", "alibayram/medgemma:27b")

# Scenario identifiers aligned with stakeholder brief
SCENARIOS = {
    "A": ModelConfig(name=GEMMA_BASE, use_rag=False),
    "B": ModelConfig(
        name=GEMMA_BASE, use_rag=True, embed_model="sentence-transformers/all-MiniLM-L6-v2"
    ),
    "C": ModelConfig(name=MEDGEMMA_SMALL, use_rag=False),
    "D": ModelConfig(
        name=MEDGEMMA_SMALL,
        use_rag=True,
        embed_model="sentence-transformers/all-MiniLM-L6-v2",
    ),
    "E": ModelConfig(name=MEDGEMMA_LARGE, use_rag=False),
    "F": ModelConfig(
        name=MEDGEMMA_LARGE,
        use_rag=True,
        embed_model="sentence-transformers/all-MiniLM-L6-v2",
    ),
}

__all__ = ["ModelConfig", "SCENARIOS"]
