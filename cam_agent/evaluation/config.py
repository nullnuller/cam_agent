"""
Evaluation scenario definitions and helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from cam_agent.config.models import ModelConfig, SCENARIOS


@dataclass(slots=True)
class Scenario:
    """Single evaluation scenario combining CAM and model settings."""

    id: str
    description: str
    model_config: ModelConfig
    store_dir: Optional[Path] = None


def default_scenarios(store_dir: Path) -> Dict[str, Scenario]:
    """Return scenario mapping aligned with stakeholder brief."""
    return {
        scenario_id: Scenario(
            id=scenario_id,
            description=describe_scenario(scenario_id, model_config.use_rag),
            model_config=model_config,
            store_dir=store_dir if model_config.use_rag else None,
        )
        for scenario_id, model_config in SCENARIOS.items()
    }


def describe_scenario(scenario_id: str, use_rag: bool) -> str:
    label = {
        "A": "gemma3-4B (no RAG)",
        "B": "gemma3-4B + RAG",
        "C": "medgemma3-4B (no RAG)",
        "D": "medgemma3-4B + RAG",
        "E": "medgemma3-27B (no RAG)",
        "F": "medgemma3-27B + RAG",
    }.get(scenario_id, scenario_id)
    if use_rag and "RAG" not in label:
        label += " + RAG"
    return label


__all__ = ["Scenario", "default_scenarios"]

