"""Sun position computation for Mars.

Two entry points for callers:

* :func:`compute_sun_position` — static azimuth / elevation from YAML.
* :func:`compute_sol_sun_position` — sol-fraction-based diurnal sweep.

The sweep defaults to ``mode="spherical"``, which evaluates the standard
astronomy identities

    sin(el) = sin(phi) sin(delta) + cos(phi) cos(delta) cos(H)
    sin(az) = -cos(delta) sin(H) / cos(el)

where ``phi`` is the observer latitude, ``delta`` the solar declination,
and ``H`` the hour angle (``H = (t_frac - 0.5) * 2*pi``). A linear
azimuth + half-sine elevation sweep (``mode="linear"``) is preserved for
callers that explicitly want the sunrise-azimuth / sunset-azimuth /
peak-elevation envelope; it is a first-order approximation off by
20-40 deg in azimuth near transit for Jezero crater (18.44 deg N) and
is not used by paper figures.

Scientific basis:

* Mars sol = 88,642 s (IAU).
* Mars obliquity ~ 25.19 deg. Declination over an orbit is
  ``delta ~ obliquity * sin(Ls)`` where Ls is the areocentric longitude.
* Jezero (phi ~ 18.44 deg N) at Ls=90 (northern summer solstice) peaks
  near ``90 - (phi - obliquity) ~ 83.25`` deg elevation.
* At Ls=0 / Ls=180 (equinoxes) the peak is ``90 - phi ~ 71.56`` deg.

References:
    Allison & McEwen (2000). A post-Pathfinder evaluation of areocentric
    solar coordinates with improved timing recipes for Mars seasonal/diurnal
    climate studies. Planet. Space Sci. 48 (2-3), 215-235.
"""

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
    """Legacy first-order diurnal approximation.

    Azimuth: linear sweep from ``start`` to ``end``. Elevation: half-sine
    peaking at t=0.5. Kept for backward-compat with pre-refactor
    callers/tests that assert on the envelope parameters directly.
    """
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
    """Compute sun position from a fractional time-of-sol.

    The default ``mode="spherical"`` evaluates the standard spherical
    astronomy identities for altitude and azimuth. This is the
    physically correct path-of-the-sun and is what the paper figures
    render. ``mode="linear"`` preserves a first-order approximation
    (linear azimuth + half-sine elevation) for callers that want an
    explicit envelope; the ``start_azimuth_deg`` / ``end_azimuth_deg`` /
    ``max_elevation_deg`` arguments are ignored in ``"spherical"`` mode
    but retained for signature stability.

    The spherical inputs are explicit function arguments and are not part of
    the canonical runtime YAML. The MarsLab runtime currently calls this API
    with ``mode="linear"``.

    Args:
        time_of_sol_fraction: Fraction of the sol [0, 1] where 0 is
            local midnight-to-sunrise (``mode="linear"`` treats 0 as
            sunrise; ``mode="spherical"`` treats 0.5 as solar transit
            and 0/1 as local midnight).
        start_azimuth_deg: Linear-mode sunrise azimuth. Ignored in
            spherical mode.
        end_azimuth_deg: Linear-mode sunset azimuth. Ignored in
            spherical mode.
        max_elevation_deg: Linear-mode peak elevation. Ignored in
            spherical mode.
        mode: ``"spherical"`` (default, physically correct) or
            ``"linear"`` (envelope approximation).
        latitude_deg: Observer latitude, degrees (spherical mode only).
            Defaults to Jezero crater 18.44 deg N.
        ls_deg: Areocentric longitude of the Sun, degrees (spherical
            mode only). 0 = northern spring equinox, 90 = northern
            summer solstice. Ignored if ``declination_deg`` is given.
        declination_deg: Solar declination override, degrees (spherical
            mode only). If ``None``, derived from ``ls_deg`` and
            ``obliquity_deg``.
        obliquity_deg: Mars axial tilt in degrees, used only when
            ``declination_deg`` is ``None`` and ``mode == "spherical"``.
            Defaults to the modern-epoch value 25.19 deg.

    Returns:
        SunPosition for the requested time of sol. Sub-horizon
        spherical-mode samples have ``elevation_deg == 0`` (clamped).

    Raises:
        ValueError: If ``time_of_sol_fraction`` is outside [0, 1],
            ``max_elevation_deg`` is outside (0, 90], or ``mode`` is
            unknown.
    """
    if not 0.0 <= time_of_sol_fraction <= 1.0:
        raise ValueError(f"time_of_sol_fraction must be in [0, 1], got {time_of_sol_fraction}")
    if not 0.0 < max_elevation_deg <= 90.0:
        raise ValueError(f"max_elevation_deg must be in (0, 90], got {max_elevation_deg}")

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
