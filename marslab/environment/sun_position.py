"""Compute static sun angles and standalone linear or spherical sweeps."""

import math
from dataclasses import dataclass
from typing import Literal

# Default Mars obliquity (axial tilt) for standalone spherical calculations.
# Allison & McEwen (2000) cite 25.19 deg for the modern Mars epoch.
MARS_OBLIQUITY_DEG: float = 25.19

# Default observer latitude for standalone spherical calculations.
# 18.44 deg N is Jezero crater (rounded from 18.4447 deg N).
DEFAULT_LATITUDE_DEG: float = 18.44


@dataclass
class SunPosition:
    """Sun position in the Mars sky.

    Attributes:
        azimuth_deg: Azimuth angle in degrees (0=N, 90=E, 180=S, 270=W).
        elevation_deg: Elevation angle in degrees above the horizon.
            Clamped to [0, 90] — nighttime samples return 0 so downstream
            lighting code never receives a below-horizon sun.
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


def solar_declination_deg(
    ls_deg: float,
    obliquity_deg: float = MARS_OBLIQUITY_DEG,
) -> float:
    """Solar declination for a given areocentric longitude Ls.

    Uses the first-harmonic Allison & McEwen (2000) form
    ``delta = obliquity * sin(Ls)``. This matches their Table 2 within
    0.5 deg across the full orbit for the modern epoch -- sufficient for
    lighting at the +/- ~1 deg precision targeted here.

    Args:
        ls_deg: Areocentric longitude of the Sun in degrees [0, 360).
            Ls=0 is northern spring equinox, Ls=90 northern summer
            solstice.
        obliquity_deg: Mars axial tilt in degrees. Defaults to the
            modern-epoch value 25.19 deg.

    Returns:
        Declination in degrees.
    """
    return obliquity_deg * math.sin(math.radians(ls_deg))


def _spherical_sun_position(
    time_of_sol_fraction: float,
    latitude_deg: float,
    declination_deg: float,
) -> SunPosition:
    """Spherical-trig diurnal sun path.

    Hour angle ``H = (t - 0.5) * 2*pi`` so that t=0.5 is transit
    (H=0, sun due south in the northern hemisphere). Elevation below
    the horizon is clamped to 0 — the caller uses the result for
    lighting and does not expect a sub-horizon sun.

    Args:
        time_of_sol_fraction: Sol fraction in [0, 1].
        latitude_deg: Observer latitude in degrees. Positive = north.
        declination_deg: Solar declination in degrees.

    Returns:
        SunPosition with azimuth in [0, 360), elevation clamped to
        [0, 90].
    """
    phi = math.radians(latitude_deg)
    delta = math.radians(declination_deg)
    H = (time_of_sol_fraction - 0.5) * 2.0 * math.pi

    sin_el = math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.cos(H)
    # Numerical safety: clamp before asin to cope with FP ± 1e-16 drift.
    sin_el = max(-1.0, min(1.0, sin_el))
    el_rad = math.asin(sin_el)

    # Below-horizon clamp for downstream lighting. Azimuth is still
    # reported so visualisations can plot the full arc if they want.
    elevation_deg = max(0.0, math.degrees(el_rad))

    # Standard formula: A = atan2(-sin(H) cos(delta), cos(phi) sin(delta)
    # - sin(phi) cos(delta) cos(H)). Measured from north, clockwise,
    # matching the SunPosition convention (0=N, 90=E, 180=S, 270=W).
    num = -math.sin(H) * math.cos(delta)
    den = math.cos(phi) * math.sin(delta) - math.sin(phi) * math.cos(delta) * math.cos(H)
    az_rad = math.atan2(num, den)
    azimuth_deg = math.degrees(az_rad) % 360.0

    zenith_angle_rad = math.pi / 2.0 - math.radians(elevation_deg)
    return SunPosition(
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        zenith_angle_rad=zenith_angle_rad,
    )


def _linear_sun_position(
    time_of_sol_fraction: float,
    start_azimuth_deg: float,
    end_azimuth_deg: float,
    max_elevation_deg: float,
) -> SunPosition:
    """Interpolate azimuth with a half-sine elevation envelope."""
    azimuth_deg = start_azimuth_deg + (end_azimuth_deg - start_azimuth_deg) * time_of_sol_fraction
    elevation_deg = max_elevation_deg * math.sin(math.pi * time_of_sol_fraction)
    return compute_sun_position(azimuth_deg, elevation_deg)


def compute_sol_sun_position(
    time_of_sol_fraction: float,
    start_azimuth_deg: float = 90.0,
    end_azimuth_deg: float = 270.0,
    max_elevation_deg: float = 60.0,
    *,
    mode: Literal["spherical", "linear"] = "spherical",
    latitude_deg: float = DEFAULT_LATITUDE_DEG,
    ls_deg: float = 0.0,
    declination_deg: float | None = None,
    obliquity_deg: float = MARS_OBLIQUITY_DEG,
) -> SunPosition:
    """Compute a sweep; the runtime explicitly selects the linear envelope."""
    if not 0.0 <= time_of_sol_fraction <= 1.0:
        raise ValueError(f"time_of_sol_fraction must be in [0, 1], got {time_of_sol_fraction}")
    if not 0.0 <= max_elevation_deg <= 90.0:
        raise ValueError(f"max_elevation_deg must be in [0, 90], got {max_elevation_deg}")

    if mode == "linear":
        return _linear_sun_position(
            time_of_sol_fraction=time_of_sol_fraction,
            start_azimuth_deg=start_azimuth_deg,
            end_azimuth_deg=end_azimuth_deg,
            max_elevation_deg=max_elevation_deg,
        )
    if mode == "spherical":
        if not -90.0 <= latitude_deg <= 90.0:
            raise ValueError(f"latitude_deg must be in [-90, 90], got {latitude_deg}")
        delta = (
            declination_deg
            if declination_deg is not None
            else solar_declination_deg(ls_deg, obliquity_deg=obliquity_deg)
        )
        return _spherical_sun_position(
            time_of_sol_fraction=time_of_sol_fraction,
            latitude_deg=latitude_deg,
            declination_deg=delta,
        )
    raise ValueError(f"mode must be 'spherical' or 'linear', got {mode!r}")
