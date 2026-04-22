"""Mars atmosphere fog configuration for Isaac Sim.

Configures RTX fog settings to simulate Mars dust haze based on
dust optical depth (tau). Higher tau = lower visibility.
All parameters read from config (G5).
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
    All scaling factors and colors from rendering_config (G5).

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

    # R2-A1 (2026-04-22): flat rendering_config.fog_* fields are now
    # grouped under ``rendering_config.fog`` (FogConfig). Legacy
    # attribute reads kept as comments per feedback_no_delete_comment:
    #   settings.set("/rtx/fog/enabled", rendering_config.fog_enabled)
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
    # Legacy flat-field writes (pre R2-A1), preserved for diffable review:
    #   settings.set("/rtx/fog/fogColorAmount", rendering_config.fog_color_amount)
    #   settings.set("/rtx/fog/fogStartHeight", rendering_config.fog_start_height)
    #   settings.set("/rtx/fog/fogHeightFalloff", rendering_config.fog_height_falloff)
    settings.set("/rtx/fog/fogColorAmount", fog_cfg.color_amount)
    settings.set("/rtx/fog/fogStartHeight", fog_cfg.start_height)
    settings.set("/rtx/fog/fogHeightFalloff", fog_cfg.height_falloff)
