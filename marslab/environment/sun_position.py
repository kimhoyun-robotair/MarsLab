"""Sun position computation for Mars.

Phase 1: User-configured azimuth/elevation from YAML.
Phase 1 dynamic: Sol-fraction-based sun sweep (east-to-west arc).
Phase 2 (future): Allison & McEwen (2000) Ls-based orbital mechanics.
The SunPosition dataclass remains unchanged between phases.

Scientific basis for the dynamic sun sweep:
    - Mars sol = 88,642 seconds (24h 37m 22s) — IAU standard.
    - Solar azimuth: sunrise (~90 deg E) -> noon (~180 deg S) -> sunset (~270 deg W).
      Linear interpolation is a reasonable first-order approximation for
      Jezero crater latitude 18.4 deg N (Allison & McEwen 2000).
    - Solar elevation: follows a sinusoidal arc peaking at local noon,
      max elevation ~60-70 deg depending on Ls (season). Configurable.
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


def compute_sol_sun_position(
    time_of_sol_fraction: float,
    start_azimuth_deg: float = 90.0,
    end_azimuth_deg: float = 270.0,
    max_elevation_deg: float = 60.0,
) -> SunPosition:
    """Compute sun position from a fractional time-of-sol (0=sunrise, 1=sunset).

    Models a simplified diurnal sun arc for Mars:
    - Azimuth: linear sweep from start (east, sunrise) to end (west, sunset).
    - Elevation: sinusoidal arc peaking at t=0.5 (local noon).
      ``elevation = max_elevation * sin(pi * t)``

    This is a first-order approximation valid for equatorial/low-latitude
    sites such as Jezero crater (18.4 deg N). A full Ls-parameterised
    model (Allison & McEwen 2000) is deferred to v2.0.

    Args:
        time_of_sol_fraction: Fraction of the sol [0, 1] where 0=sunrise
            and 1=sunset.
        start_azimuth_deg: Azimuth at sunrise in degrees (default 90 = east).
        end_azimuth_deg: Azimuth at sunset in degrees (default 270 = west).
        max_elevation_deg: Peak elevation at noon in degrees (default 60).

    Returns:
        SunPosition for the given time of sol.

    Raises:
        ValueError: If time_of_sol_fraction is outside [0, 1] or
            max_elevation_deg is outside (0, 90].
    """
    if not 0.0 <= time_of_sol_fraction <= 1.0:
        raise ValueError(f"time_of_sol_fraction must be in [0, 1], got {time_of_sol_fraction}")
    if not 0.0 < max_elevation_deg <= 90.0:
        raise ValueError(f"max_elevation_deg must be in (0, 90], got {max_elevation_deg}")

    azimuth_deg = start_azimuth_deg + (end_azimuth_deg - start_azimuth_deg) * time_of_sol_fraction
    elevation_deg = max_elevation_deg * math.sin(math.pi * time_of_sol_fraction)

    return compute_sun_position(azimuth_deg, elevation_deg)
