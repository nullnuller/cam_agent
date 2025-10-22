from pathlib import Path
from setuptools import find_packages, setup


def read_requirements() -> list[str]:
    req_path = Path(__file__).parent / "requirements.txt"
    if not req_path.exists():
        return []
    return [line.strip() for line in req_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


setup(
    name="cam-agent",
    version="0.1.0",
    description="Corpus-Aware Monitor (CAM) framework for healthcare compliance",
    packages=find_packages(include=["cam_agent", "cam_agent.*"]),
    install_requires=read_requirements(),
    python_requires=">=3.10",
    include_package_data=True,
)
