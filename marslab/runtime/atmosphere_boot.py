"""Build the atmosphere snapshot shared by startup and the live loop."""

from dataclasses import dataclass

from marslab.config import MarsLabConfig
from marslab.config.schema import DynamicAtmosphereConfig, SkyDomeConfig
from marslab.environment.diffuse_fraction import compute_diffuse_fraction_1d_approx
from marslab.environment.light_intensity import compute_direct_intensity
from marslab.environment.sky_dome import SkyDomeParams, compute_sky_dome_params
from marslab.environment.sun_position import SunPosition, compute_sun_position


@dataclass(frozen=True)
class AtmosphereInit:
    """Initial sun, irradiance, and sky appearance with validated simulation settings."""

    tau: float
    solar_constant: float
    sun_azimuth_deg: float
    sun_elevation_deg: float
    sol_duration_seconds: float
    gravity: float
    physics_dt: float
    direct_intensity: float
    diffuse_fraction: float
    sky_params: SkyDomeParams
    sun_pos: SunPosition
    hdri_dir: str
    sky_dome_config: SkyDomeConfig
    dynamic: DynamicAtmosphereConfig


def prepare_atmosphere(config: MarsLabConfig) -> AtmosphereInit:
    """Start either sun mode at the configured azimuth and elevation."""
    mars = config.mars_env
    dynamic = mars.dynamic_atmosphere
    sun = compute_sun_position(mars.sun_azimuth_deg, mars.sun_elevation_deg)
    tau = mars.dust_optical_depth
    hdri_dir = str(config.rendering.sky_dome_hdri_dir)
    sky_config = config.rendering.sky_dome
    return AtmosphereInit(
        tau=tau,
        solar_constant=mars.solar_constant,
        sun_azimuth_deg=sun.azimuth_deg,
        sun_elevation_deg=sun.elevation_deg,
        sol_duration_seconds=mars.sol_duration_seconds,
        gravity=mars.gravity,
        physics_dt=mars.physics_dt,
        direct_intensity=compute_direct_intensity(
            mars.solar_constant, tau, sun.zenith_angle_rad
        ),
        diffuse_fraction=compute_diffuse_fraction_1d_approx(tau),
        sky_params=compute_sky_dome_params(tau, hdri_dir, sky_config),
        sun_pos=sun,
        hdri_dir=hdri_dir,
        sky_dome_config=sky_config,
        dynamic=dynamic,
    )


__all__ = ["AtmosphereInit", "prepare_atmosphere"]
