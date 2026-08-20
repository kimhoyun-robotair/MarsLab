"""Prepare the static atmosphere snapshot before scene creation.
Solar and rendering calculations remain pure and terrain-free.
Typed results flow into the live loop without rereading YAML."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from marslab.config import MarsLabConfig, load_config
from marslab.config.schema import DynamicAtmosphereConfig, MarsEnvConfig, RenderingConfig

_LOG = logging.getLogger(__name__)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@dataclass(frozen=True)
class AtmosphereInit:
    """Frozen static atmosphere snapshot produced at boot time."""

    tau: float
    solar_constant: float
    sun_azimuth_deg: float
    sun_elevation_deg: float
    sol_duration_seconds: float
    physics_dt: float
    direct_intensity: float
    diffuse_fraction: float
    sky_params: Any  # SkyDomeParams (avoid import at module scope to keep offline-first)
    sun_pos: Any  # SunPosition
    hdri_dir: str
    dynamic: DynamicAtmosphereConfig


@dataclass(frozen=True)
class AtmosphereBootResult:
    """Frozen result of :func:`boot_atmosphere`."""

    config_path: str
    config: MarsLabConfig
    mars_cfg: MarsEnvConfig
    rendering_cfg: RenderingConfig
    atmosphere_init: AtmosphereInit
    repo_root: str


def boot_atmosphere(
    config_path: str,
    repo_root: str = REPO_ROOT,
    sun_azimuth_deg: float | None = None,
    sun_elevation_deg: float | None = None,
) -> AtmosphereBootResult:
    """Load config and pre-compute the static atmosphere snapshot."""
    from marslab.environment.diffuse_fraction import compute_diffuse_fraction_1d_approx
    from marslab.environment.light_intensity import compute_direct_intensity
    from marslab.environment.sky_dome import compute_sky_dome_params
    from marslab.environment.sun_position import compute_sun_position

    abs_config_path = os.path.abspath(config_path)
    cfg = load_config(abs_config_path)
    _LOG.info("Loaded config: %s", abs_config_path)

    mars_env_model = cfg.mars_env
    rendering_cfg = cfg.rendering
    mars_values = json.loads(mars_env_model.model_dump_json())
    if sun_azimuth_deg is not None:
        mars_values["sun_azimuth_deg"] = sun_azimuth_deg
    if sun_elevation_deg is not None:
        mars_values["sun_elevation_deg"] = sun_elevation_deg
    mars_env_model = MarsEnvConfig.model_validate_json(json.dumps(mars_values, allow_nan=True))

    sun_pos = compute_sun_position(
        azimuth_deg=mars_env_model.sun_azimuth_deg,
        elevation_deg=mars_env_model.sun_elevation_deg,
    )
    tau = mars_env_model.dust_optical_depth
    solar_constant = mars_env_model.solar_constant
    direct_intensity = compute_direct_intensity(solar_constant, tau, sun_pos.zenith_angle_rad)
    diffuse_frac = compute_diffuse_fraction_1d_approx(tau)
    hdri_dir = str(rendering_cfg.sky_dome_hdri_dir)
    sky_params = compute_sky_dome_params(tau, hdri_dir)
    _LOG.info(
        "Atmosphere: tau=%s, direct=%.1f W/m2, diffuse_frac=%.2f",
        tau,
        direct_intensity,
        diffuse_frac,
    )

    dynamic = mars_env_model.dynamic_atmosphere

    atmosphere_init = AtmosphereInit(
        tau=tau,
        solar_constant=solar_constant,
        sun_azimuth_deg=mars_env_model.sun_azimuth_deg,
        sun_elevation_deg=mars_env_model.sun_elevation_deg,
        sol_duration_seconds=float(mars_env_model.sol_duration_seconds),
        physics_dt=mars_env_model.physics_dt,
        direct_intensity=direct_intensity,
        diffuse_fraction=diffuse_frac,
        sky_params=sky_params,
        sun_pos=sun_pos,
        hdri_dir=hdri_dir,
        dynamic=dynamic,
    )

    return AtmosphereBootResult(
        config_path=abs_config_path,
        config=cfg,
        mars_cfg=mars_env_model,
        rendering_cfg=rendering_cfg,
        atmosphere_init=atmosphere_init,
        repo_root=repo_root,
    )


__all__ = [
    "REPO_ROOT",
    "AtmosphereInit",
    "AtmosphereBootResult",
    "boot_atmosphere",
]
