"""Map tau to RTX simple fog appearance, without a scattering or visibility calibration."""

import carb

from marslab.config.schema import RenderingConfig


def configure_atmosphere_fog(stage, tau: float, rendering_config: RenderingConfig) -> None:
    """Set Isaac Sim 5.1 simple fog density, distance range, and Z-up height controls."""
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")
    settings = carb.settings.get_settings()
    fog = rendering_config.fog
    density = tau * rendering_config.fog_density_scale
    settings.set("/rtx/fog/enabled", fog.enabled)
    settings.set("/rtx/fog/fogDistanceDensity", density)
    settings.set("/rtx/fog/fogHeightDensity", density * fog.height_density_ratio)
    settings.set("/rtx/fog/fogColor", rendering_config.fog_color)
    settings.set("/rtx/fog/fogColorIntensity", fog.color_amount)
    settings.set("/rtx/fog/fogZup/enabled", True)
    settings.set("/rtx/fog/fogStartDist", fog.start_distance_m)
    settings.set("/rtx/fog/fogEndDist", fog.end_distance_m)
    settings.set("/rtx/fog/fogStartHeight", fog.start_height)
    settings.set("/rtx/fog/fogHeightFalloff", fog.height_falloff)
