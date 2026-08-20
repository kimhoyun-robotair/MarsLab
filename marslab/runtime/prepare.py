"""Resolve and validate the canonical configuration before startup.
Required scene inputs are checked before Kit creation.
The phase stays offline-importable for launch diagnostics."""

from __future__ import annotations

from pathlib import Path

from marslab.config import MarsLabConfig, load_config
from marslab.runtime.precheck import check_rover_config


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")


def prepare_config(config_path: str | Path) -> MarsLabConfig:
    """Load the resolved config and verify its required file inputs."""
    input_path = Path(config_path)
    _require_file(input_path, "Config")

    config = load_config(input_path)
    _require_file(config.scene.usdz_path, "Scene USDZ")
    check_rover_config(config.rover)
    return config
