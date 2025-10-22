"""
cam_agent package bootstrap.

Initialises top-level namespaces for the Corpus-Aware Monitor (CAM)
framework as we evolve towards a full compliance agent.
"""

from importlib import metadata


def get_version() -> str:
    """Return the package version if installed, else '0.0.0'."""
    try:
        return metadata.version("cam_agent")
    except metadata.PackageNotFoundError:  # pragma: no cover - best effort only
        return "0.0.0"


__all__ = ["get_version"]

