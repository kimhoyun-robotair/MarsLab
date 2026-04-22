"""Runtime preflight checks — raise early and clearly before Isaac Sim boots.

All checks are pure Python (no Isaac Sim imports) so they can run inside
unit tests and inside the Isaac Sim python context with identical
behaviour. Error messages mirror the original inline ``print`` + ``return``
patterns from ``scripts/phase1/run_stage3_monolithic.py`` (Oracle) so
operators see the same diagnostic text whether the migration is wired in
or not.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def check_rover_usd(usd_abs: str) -> None:
    """Raise ``FileNotFoundError`` if the rover USD file is missing.

    Derived from ``scripts/phase1/run_stage3_monolithic.py`` L322-332
    (Oracle copy). The Oracle prints and returns exit code 3 rather than
    raising; callers wrapping Isaac Sim startup should translate the
    exception accordingly.

    Args:
        usd_abs: Absolute filesystem path to the converted rover USD.

    Raises:
        FileNotFoundError: If ``usd_abs`` does not resolve to a file. The
            message mirrors the Oracle's operator hint about running
            ``scripts/phase1/convert_urdf_to_usd.py``.
    """
    if not os.path.isfile(usd_abs):
        raise FileNotFoundError(
            f"Rover USD missing: {usd_abs}. " f"Run scripts/phase1/convert_urdf_to_usd.py first."
        )


def check_rover_block(rover_cfg: Optional[Dict[str, Any]]) -> None:
    """Raise ``ValueError`` if the scenario's rover config block is missing.

    Derived from ``scripts/phase1/run_stage3_monolithic.py`` L272-279
    (Oracle copy). Stage 3 requires a rover block; scene-only scenarios
    should use ``run_stage2.py``.

    Args:
        rover_cfg: The ``rover`` section from a loaded scenario dict.
            ``None`` or an empty dict both fail this check.

    Raises:
        ValueError: If the rover block is absent or empty.
    """
    if not rover_cfg:
        raise ValueError(
            "Scenario config missing 'rover' block. "
            "Stage 3 monolithic requires a rover; use run_stage2.py for scene-only."
        )


def check_lidar_cfg(lidar_cfg: Optional[Dict[str, Any]]) -> None:
    """Raise ``ValueError`` if the lidar sensor config block is missing.

    Derived from ``scripts/phase1/run_stage3_monolithic.py`` L705-712
    (Oracle copy). Callers pre-resolve the ``lidar_3d`` / ``lidar`` alias
    and pass the resolved block (or ``None``) to this helper.

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


def check_dem_assets(converted_dir: str) -> None:
    """Raise ``FileNotFoundError`` if DEM assets are missing.

    Derived from ``marslab/terrain/dem_loader.py`` L132-141 — abstracted
    so runtime scripts can pre-check before attempting the full DEM load
    and reporting both missing files together.

    Args:
        converted_dir: Directory that should contain ``elevation.npy``
            and ``metadata.json`` produced by ``scripts/convert_dem.py``.

    Raises:
        FileNotFoundError: If either asset is absent. The message lists
            every missing path so operators can fix in a single pass.
    """
    elev = os.path.join(converted_dir, "elevation.npy")
    meta = os.path.join(converted_dir, "metadata.json")
    missing = [p for p in (elev, meta) if not os.path.isfile(p)]
    if missing:
        raise FileNotFoundError(
            "DEM assets missing: "
            + ", ".join(missing)
            + ". Run 'python scripts/convert_dem.py' first."
        )
