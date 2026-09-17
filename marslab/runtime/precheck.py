"""Run pure preflight checks before Isaac Sim boots.
Required files fail early with direct diagnostics.
No simulator or ROS binding is imported here."""

from __future__ import annotations

import os
import runpy
from pathlib import Path

from marslab.config.schema.rover import RoverConfig


def check_rover_usd(usd_path: os.PathLike[str] | str) -> None:
    """Raise ``FileNotFoundError`` if the rover USD file is missing."""
    if not os.path.isfile(usd_path):
        raise FileNotFoundError(f"Rover USD missing: {usd_path}")


def check_rover_config(rover: RoverConfig) -> None:
    check_rover_usd(rover.usd_path)
    if not rover.urdf_source_path.is_file():
        raise FileNotFoundError(f"Rover URDF source missing: {rover.urdf_source_path}")
    _check_lidar_profiles(rover)


def _check_lidar_profiles(rover: RoverConfig) -> None:
    isaac_root = Path(os.environ.get("ISAAC_SIM_PATH", str(Path.home() / "isaacsim")))
    catalog_path = (
        isaac_root
        / "exts/isaacsim.sensors.rtx/isaacsim/sensors/rtx/impl/supported_lidar_configs.py"
    )
    if not catalog_path.is_file():
        raise FileNotFoundError(
            f"Installed RTX LiDAR model catalog missing: {catalog_path}; "
            "set ISAAC_SIM_PATH to the supported Isaac Sim installation"
        )
    catalog = runpy.run_path(str(catalog_path))["SUPPORTED_LIDAR_CONFIGS"]
    profiles = (
        ("lidar_3d", rover.sensors.lidar_3d.profile_name, rover.sensors.lidar_3d.variant),
        ("lidar_2d", "Example_Rotary_2D", None),
    )
    for sensor_name, profile, variant in profiles:
        for model_path, variants in catalog.items():
            path = Path(model_path)
            vendor = path.parts[3]
            stem = path.stem
            short_name = stem[len(vendor) + 1 :] if stem.startswith(vendor) else stem
            aliases = (stem, stem.replace("_", " "), short_name, short_name.replace("_", " "))
            if profile in aliases:
                if variant is not None and variant not in variants:
                    raise ValueError(
                        f"{sensor_name}.variant {variant!r} is unsupported for {profile!r}; "
                        f"choose one of {sorted(variants)}"
                    )
                break
        else:
            raise ValueError(
                f"{sensor_name}.profile_name {profile!r} is not an installed RTX LiDAR model"
            )
