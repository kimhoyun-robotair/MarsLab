"""Define the static atmosphere snapshot shared by runtime phases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from marslab.config.schema import DynamicAtmosphereConfig, SkyDomeConfig


@dataclass(frozen=True)
class AtmosphereInit:
    """Frozen static atmosphere snapshot produced at boot time."""

    tau: float
    solar_constant: float
    sun_azimuth_deg: float
    sun_elevation_deg: float
    sol_duration_seconds: float
    gravity: float
    physics_dt: float
    direct_intensity: float
    diffuse_fraction: float
    sky_params: Any  # SkyDomeParams (avoid import at module scope to keep offline-first)
    sun_pos: Any  # SunPosition
    hdri_dir: str
    sky_dome_config: SkyDomeConfig
    dynamic: DynamicAtmosphereConfig


__all__ = ["AtmosphereInit"]
