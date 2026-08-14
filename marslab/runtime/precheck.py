"""Runtime preflight checks — raise early and clearly before Isaac Sim boots.

Pure Python (no Isaac Sim imports) so the checks run identically under unit
tests and inside the Isaac Sim python context. Error messages live alongside
``marslab/main.py`` for consistent diagnostics.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def check_rover_usd(usd_abs: str) -> None:
    """Raise ``FileNotFoundError`` if the rover USD file is missing.

    Callers wrapping Isaac Sim startup may translate the exception into
    an exit code if they prefer a non-raising behaviour.

    Args:
        usd_abs: Absolute filesystem path to the converted rover USD.

    Raises:
        FileNotFoundError: If ``usd_abs`` does not resolve to a file.
    """
    if not os.path.isfile(usd_abs):
        raise FileNotFoundError(f"Rover USD missing: {usd_abs}")
    if not os.access(usd_abs, os.R_OK):
        raise PermissionError(f"Rover USD is not readable: {usd_abs}")


def check_rover_block(rover_cfg: Optional[Dict[str, Any]]) -> None:
    """Raise ``ValueError`` if the scenario's rover config block is missing.

    Stage 3 monolithic requires a rover block by default; pass
    ``--no-rover`` to ``marslab/main.py`` for scene-only mode
    (DEM + atmosphere + structures, no rover spawn / sensors / ROS2).

    Args:
        rover_cfg: The ``rover`` section from a loaded scenario dict.
            ``None`` or an empty dict both fail this check.

    Raises:
        ValueError: If the rover block is absent or empty.
    """
    if not rover_cfg:
        raise ValueError(
            "Scenario config missing 'rover' block. "
            "Stage 3 requires a 'rover' block (or pass --no-rover for scene-only)."
        )


def check_lidar_cfg(lidar_cfg: Optional[Dict[str, Any]]) -> None:
    """Raise ``ValueError`` if the lidar sensor config block is missing.

    Callers pre-resolve the ``lidar_3d`` / ``lidar`` alias and pass the
    resolved block (or ``None``) to this helper.

    Args:
        lidar_cfg: The resolved lidar sensor config block, or ``None``
            if neither key is present.

    Raises:
        ValueError: If ``lidar_cfg`` is ``None``.
    """
    if lidar_cfg is None:
        raise ValueError(
            "Scenario config missing sensors.lidar block "
            "(expected 'lidar_3d' or 'lidar' key under sensors)."
        )
