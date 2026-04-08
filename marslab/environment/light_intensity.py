"""Direct solar irradiance on the Martian surface using Beer's Law.

Reference:
    Appelbaum, J. & Flood, D.J. (1990). Solar radiation on Mars.
    NASA TM-102299.
"""

import math


def compute_direct_intensity(solar_constant: float, tau: float, zenith_angle_rad: float) -> float:
    """Compute direct beam irradiance using Beer's Law.

    Beer's Law: I = I_0 * exp(-tau / cos(theta_z))

    Args:
        solar_constant: Top-of-atmosphere irradiance in W/m^2.
            Mars mean at 1.52 AU is ~589 W/m^2.
        tau: Dust optical depth (dimensionless, >= 0).
        zenith_angle_rad: Solar zenith angle in radians [0, pi].

    Returns:
        Direct beam irradiance at the surface in W/m^2.
        Returns 0.0 if the sun is at or below the horizon (zenith >= pi/2).

    Raises:
        ValueError: If solar_constant or tau is negative.
    """
    if solar_constant < 0:
        raise ValueError(f"solar_constant must be >= 0, got {solar_constant}")
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    cos_z = math.cos(zenith_angle_rad)
    if cos_z <= 0:
        return 0.0

    return solar_constant * math.exp(-tau / cos_z)
