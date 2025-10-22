"""
Evaluation package exposing CAM scenario runners and utilities.
"""

from .config import Scenario, default_scenarios
from .judges import (
    BaseJudge,
    GeminiJudge,
    JudgeManager,
    JudgeResult,
    OllamaJudge,
    build_default_judges,
)
from .metrics import JudgeAggregate, ScenarioMetrics
from .runner import CAMSuiteRunner

__all__ = [
    "CAMSuiteRunner",
    "Scenario",
    "ScenarioMetrics",
    "JudgeAggregate",
    "JudgeManager",
    "JudgeResult",
    "BaseJudge",
    "OllamaJudge",
    "GeminiJudge",
    "build_default_judges",
    "default_scenarios",
]
