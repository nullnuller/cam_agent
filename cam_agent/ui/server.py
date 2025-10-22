"""
Command-line entry point for running the CAM UI API service.

Usage:
    python -m cam_agent.ui.server

Environment variables:
    CAM_UI_AUDIT_LOG   Path to the audit JSONL file (defaults to project bundle).
    CAM_UI_API_HOST    Host interface to bind (default: 127.0.0.1).
    CAM_UI_API_PORT    Port for the service (default: 8000).
    CAM_UI_API_RELOAD  Set to "1" to enable autoreload (development only).
"""

from __future__ import annotations

import os
from typing import Optional

import uvicorn

from .api import create_ui_api


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def main() -> None:
    """Boot the FastAPI application with configurable host/port."""

    host = os.getenv("CAM_UI_API_HOST", "127.0.0.1")
    port = int(os.getenv("CAM_UI_API_PORT", "8000"))
    reload_flag = _env_bool(os.getenv("CAM_UI_API_RELOAD"), default=False)

    uvicorn.run(
        "cam_agent.ui.api:app",
        host=host,
        port=port,
        reload=reload_flag,
        factory=False,
    )


if __name__ == "__main__":
    main()
