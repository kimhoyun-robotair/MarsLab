"""Mars atmosphere fog configuration for Isaac Sim.

Configures RTX fog settings to simulate Mars dust haze based on
dust optical depth (tau). Higher tau = lower visibility.
All parameters are read from configuration; no values are hardcoded.
Requires Isaac Sim runtime.
"""

import carb

from marslab.config.schema import RenderingConfig


def configure_atmosphere_fog(
    stage,
    tau: float,
    rendering_config: RenderingConfig,
) -> None:
    """Configure atmospheric fog based on dust optical depth.

    Maps tau to fog density and color to simulate Mars dust haze.
    All scaling factors and colors come from ``rendering_config``.

    Args:
        stage: USD stage (unused but kept for API consistency).
        tau: Dust optical depth (>= 0).
        rendering_config: Rendering configuration with fog parameters.

    Raises:
        ValueError: If tau is negative.
    """
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    settings = carb.settings.get_settings()

    fog_cfg = rendering_config.fog
    settings.set("/rtx/fog/enabled", fog_cfg.enabled)

    fog_density = tau * rendering_config.fog_density_scale
    fog_color = rendering_config.fog_color

    settings.set("/rtx/fog/fogDistanceDensity", fog_density)
    settings.set(
        "/rtx/fog/fogHeightDensity",
        fog_density * fog_cfg.height_density_ratio,
    )
    settings.set("/rtx/fog/fogColor", fog_color)
    settings.set("/rtx/fog/fogColorAmount", fog_cfg.color_amount)
    settings.set("/rtx/fog/fogStartHeight", fog_cfg.start_height)
    settings.set("/rtx/fog/fogHeightFalloff", fog_cfg.height_falloff)
