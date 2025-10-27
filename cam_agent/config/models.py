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
    api_mode: Optional[str] = None
    endpoint: Optional[str] = None
    auth_env_var: Optional[str] = None


# Resolve model names from environment (fallback to latest known tags/aliases)
GEMMA_BASE = os.getenv("CAM_MODEL_GEMMA_BASE", "gemma3-4B-128k:latest")
MEDGEMMA_SMALL = os.getenv(
    "CAM_MODEL_MEDGEMMA_SMALL", "hf.co/bartowski/google_medgemma-4b-it-GGUF:latest"
)
MEDGEMMA_LARGE = os.getenv(
    "CAM_MODEL_MEDGEMMA_LARGE", "google_medgemma-27b"
)

MEDGEMMA_SMALL_API_MODE = os.getenv("CAM_MODEL_MEDGEMMA_SMALL_API_MODE")
MEDGEMMA_SMALL_ENDPOINT = os.getenv("CAM_MODEL_MEDGEMMA_SMALL_ENDPOINT")
MEDGEMMA_SMALL_AUTH_ENV_VAR = os.getenv("CAM_MODEL_MEDGEMMA_SMALL_AUTH_ENV_VAR")

MEDGEMMA_LARGE_API_MODE = os.getenv("CAM_MODEL_MEDGEMMA_LARGE_API_MODE")
MEDGEMMA_LARGE_ENDPOINT = os.getenv("CAM_MODEL_MEDGEMMA_LARGE_ENDPOINT")
MEDGEMMA_LARGE_AUTH_ENV_VAR = os.getenv("CAM_MODEL_MEDGEMMA_LARGE_AUTH_ENV_VAR")

# Scenario identifiers aligned with stakeholder brief
SCENARIOS = {
    "A": ModelConfig(name=GEMMA_BASE, use_rag=False),
    "B": ModelConfig(
        name=GEMMA_BASE, use_rag=True, embed_model="sentence-transformers/all-MiniLM-L6-v2"
    ),
    "C": ModelConfig(
        name=MEDGEMMA_SMALL,
        use_rag=False,
        api_mode=MEDGEMMA_SMALL_API_MODE,
        endpoint=MEDGEMMA_SMALL_ENDPOINT,
        auth_env_var=MEDGEMMA_SMALL_AUTH_ENV_VAR,
    ),
    "D": ModelConfig(
        name=MEDGEMMA_SMALL,
        use_rag=True,
        embed_model="sentence-transformers/all-MiniLM-L6-v2",
        api_mode=MEDGEMMA_SMALL_API_MODE,
        endpoint=MEDGEMMA_SMALL_ENDPOINT,
        auth_env_var=MEDGEMMA_SMALL_AUTH_ENV_VAR,
    ),
    "E": ModelConfig(
        name=MEDGEMMA_LARGE,
        use_rag=False,
        api_mode=MEDGEMMA_LARGE_API_MODE,
        endpoint=MEDGEMMA_LARGE_ENDPOINT,
        auth_env_var=MEDGEMMA_LARGE_AUTH_ENV_VAR,
    ),
    "F": ModelConfig(
        name=MEDGEMMA_LARGE,
        use_rag=True,
        embed_model="sentence-transformers/all-MiniLM-L6-v2",
        api_mode=MEDGEMMA_LARGE_API_MODE,
        endpoint=MEDGEMMA_LARGE_ENDPOINT,
        auth_env_var=MEDGEMMA_LARGE_AUTH_ENV_VAR,
    ),
}

__all__ = ["ModelConfig", "SCENARIOS"]
