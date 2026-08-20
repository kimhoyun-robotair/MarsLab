"""Runtime preflight checks — raise early and clearly before Isaac Sim boots.

Pure Python (no Isaac Sim imports) so the checks run identically under unit
tests and inside the Isaac Sim python context. Error messages live alongside
``marslab/main.py`` for consistent diagnostics.
"""

from __future__ import annotations

import os

from marslab.config.schema.rover import RoverConfig


def check_rover_usd(usd_path: os.PathLike[str] | str) -> None:
    """Raise ``FileNotFoundError`` if the rover USD file is missing.

    Callers wrapping Isaac Sim startup may translate the exception into
    an exit code if they prefer a non-raising behaviour.

    Args:
        usd_path: Filesystem path to the converted rover USD.

    Raises:
        FileNotFoundError: If ``usd_path`` does not resolve to a file.
    """
    if not os.path.isfile(usd_path):
        raise FileNotFoundError(f"Rover USD missing: {usd_path}")


def check_rover_config(rover: RoverConfig) -> None:
    check_rover_usd(rover.usd_path)
    if not rover.urdf_source_path.is_file():
        raise FileNotFoundError(f"Rover URDF source missing: {rover.urdf_source_path}")


def check_lidar_cfg(lidar_cfg: dict[str, object] | None) -> None:
    if lidar_cfg is None:
        raise ValueError(
            "Scenario config missing sensors.lidar block "
            "(expected 'lidar_3d' or 'lidar' key under sensors)."
        )
