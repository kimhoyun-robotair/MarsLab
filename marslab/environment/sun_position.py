"""Sun position computation for Mars.

Phase 1: User-configured azimuth/elevation from YAML.
Phase 2 (future): Allison & McEwen (2000) Ls-based orbital mechanics.
The SunPosition dataclass remains unchanged between phases.
"""

import math
from dataclasses import dataclass


@dataclass
class SunPosition:
    """Sun position in the Mars sky.

    Attributes:
        azimuth_deg: Azimuth angle in degrees (0=N, 90=E, 180=S, 270=W).
        elevation_deg: Elevation angle in degrees above the horizon.
        zenith_angle_rad: Zenith angle in radians (pi/2 - elevation).
    """

    azimuth_deg: float
    elevation_deg: float
    zenith_angle_rad: float


def compute_sun_position(azimuth_deg: float, elevation_deg: float) -> SunPosition:
    """Compute sun position from user-configured azimuth and elevation.

    Args:
        azimuth_deg: Sun azimuth in degrees [0, 360].
        elevation_deg: Sun elevation above horizon in degrees [0, 90].

    Returns:
        SunPosition with computed zenith angle.

    Raises:
        ValueError: If azimuth or elevation is out of range.
    """
    if not 0.0 <= azimuth_deg <= 360.0:
        raise ValueError(f"azimuth_deg must be in [0, 360], got {azimuth_deg}")
    if not 0.0 <= elevation_deg <= 90.0:
        raise ValueError(f"elevation_deg must be in [0, 90], got {elevation_deg}")

    zenith_angle_rad = math.pi / 2.0 - math.radians(elevation_deg)
    return SunPosition(
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        zenith_angle_rad=zenith_angle_rad,
    )
