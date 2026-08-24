"""Run pure preflight checks before Isaac Sim boots.
Required files fail early with direct diagnostics.
No simulator or ROS binding is imported here."""

from __future__ import annotations

import os

from marslab.config.schema.rover import RoverConfig


def check_rover_usd(usd_path: os.PathLike[str] | str) -> None:
    """Raise ``FileNotFoundError`` if the rover USD file is missing."""
    if not os.path.isfile(usd_path):
        raise FileNotFoundError(f"Rover USD missing: {usd_path}")


def check_rover_config(rover: RoverConfig) -> None:
    check_rover_usd(rover.usd_path)
    if not rover.urdf_source_path.is_file():
        raise FileNotFoundError(f"Rover URDF source missing: {rover.urdf_source_path}")
