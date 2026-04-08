"""Mars atmosphere fog configuration for Isaac Sim.

Configures RTX fog settings to simulate Mars dust haze based on
dust optical depth (tau). Higher tau = lower visibility.
Requires Isaac Sim runtime.
"""

import carb


def configure_atmosphere_fog(stage, tau: float) -> None:
    """Configure atmospheric fog based on dust optical depth.

    Maps tau to fog density and color to simulate Mars dust haze.
    Uses RTX fog render settings.

    Args:
        stage: USD stage (unused but kept for API consistency).
        tau: Dust optical depth (>= 0).

    Raises:
        ValueError: If tau is negative.
    """
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    settings = carb.settings.get_settings()

    settings.set("/rtx/fog/enabled", True)

    # Fog density scales with tau
    # At tau=0.3 (clear): low density. At tau=3.0 (storm): high density.
    fog_density = tau * 0.002

    # Mars dust haze color (butterscotch-tinted)
    fog_color = [0.78, 0.62, 0.42]

    settings.set("/rtx/fog/fogDistanceDensity", fog_density)
    settings.set("/rtx/fog/fogHeightDensity", fog_density * 0.5)
    settings.set("/rtx/fog/fogColor", fog_color)
    settings.set("/rtx/fog/fogColorAmount", 1.0)
    settings.set("/rtx/fog/fogStartHeight", 0.0)
    settings.set("/rtx/fog/fogHeightFalloff", 0.01)
