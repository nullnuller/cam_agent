"""
Service layer modules responsible for orchestrating CAM request/response flows.

This package exposes the primary classes via lazy imports to avoid circular
dependencies during test collection (e.g., compliance rules importing
`cam_agent.services.types`).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict

__all__ = [
    "CAMAgent",
    "LLMClient",
    "LLMResponse",
    "ScenarioExecutor",
    "RetrievalManager",
    "RetrievalResult",
    "QueryRequest",
    "ModelOutput",
    "CAMResponse",
    "ComplianceDecision",
    "ComplianceIssue",
]

_MODULE_ATTRS: Dict[str, str] = {
    "CAMAgent": "cam_agent.services.cam_agent",
    "LLMClient": "cam_agent.services.models",
    "LLMResponse": "cam_agent.services.models",
    "ScenarioExecutor": "cam_agent.services.orchestrator",
    "RetrievalManager": "cam_agent.services.retrieval",
    "RetrievalResult": "cam_agent.services.retrieval",
    "QueryRequest": "cam_agent.services.types",
    "ModelOutput": "cam_agent.services.types",
    "CAMResponse": "cam_agent.services.types",
    "ComplianceDecision": "cam_agent.services.types",
    "ComplianceIssue": "cam_agent.services.types",
}


def __getattr__(name: str) -> Any:
    module_path = _MODULE_ATTRS.get(name)
    if not module_path:
        raise AttributeError(f"module 'cam_agent.services' has no attribute '{name}'")  # pragma: no cover
    module = import_module(module_path)
    return getattr(module, name)


def __dir__() -> list[str]:  # pragma: no cover - convenience helper
    return sorted(__all__)
