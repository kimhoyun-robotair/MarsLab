"""Sun position computation for Mars.

Three entry points for callers:

* :func:`compute_sun_position` — static azimuth / elevation from YAML.
* :func:`compute_sol_sun_position` — sol-fraction-based diurnal sweep.
* :func:`sun_position_from_utc` — wall-clock UTC + lat/lon -> sun position
  via the Allison & McEwen (2000) JD -> MSD -> Local Mean Solar Time chain.

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
from datetime import datetime, timezone
from typing import Literal

# Default Mars obliquity (axial tilt) used when the caller does not
# inject the value from ``MarsEnvConfig.obliquity_deg``. Allison &
# McEwen (2000) cite 25.19 deg for the modern Mars epoch. Exposed as a
# public name so tests and external callers can reference the canonical
# default; config-driven runtime paths should pass the value through
# ``MarsEnvConfig.obliquity_deg`` instead.
MARS_OBLIQUITY_DEG: float = 25.19

# Default planetographic observer latitude used when the caller does
# not inject ``MarsEnvConfig.default_latitude_deg``. 18.44 deg N is
# Jezero crater (Mars 2020 Perseverance landing site, rounded from
# 18.4447 deg N). Same backward-compat exposure rationale as
# ``MARS_OBLIQUITY_DEG``.
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
            modern-epoch value 25.19 deg. Pass ``MarsEnvConfig.obliquity_deg``
            for config-driven runs.

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

    Pass ``MarsEnvConfig.default_latitude_deg`` and
    ``MarsEnvConfig.obliquity_deg`` for config-driven runs; the defaults
    below match those schema defaults so standalone callers behave
    identically.

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


# ---------------------------------------------------------------------------
# UTC -> Mars Sol Date -> sun position wrapper (Allison & McEwen 2000)
# ---------------------------------------------------------------------------
#
# The chain implemented below follows Allison & McEwen (2000), §A.1, as
# popularised by the NASA GISS Mars24 Sunclock algorithm document
# (https://www.giss.nasa.gov/tools/mars24/help/algorithm.html). The
# constants are the public Mars24 ones; they reproduce the Mars24 sample
# outputs to within < 1e-3 sol once the leap-second correction is
# applied.
#
# Step-by-step:
#   1. UTC -> Julian Date (UT1):  JD_UT = unix_seconds/86400 + 2440587.5
#   2. UT1 -> Terrestrial Time:   JD_TT = JD_UT + (TAI-UTC + 32.184)/86400
#      TAI-UTC = 37 s (post-2017-01-01 leap second) is constant for the
#      modern-epoch UTC range simulated here.
#   3. Days since J2000:          dT = JD_TT - 2451545.0
#   4. Mars Sol Date (MSD):
#         MSD = ((dT - 4.5) / 1.027491252) + 44796.0 - 0.00096
#      The 4.5 offset is the Allison & McEwen reference epoch shift,
#      1.027491252 is the ratio of a Mars sol to an Earth day, and the
#      -0.00096 is the empirical small-angle correction tying MSD to the
#      Airy-0 prime meridian.
#   5. Mars Coordinated Time (MTC), hours:  MTC = (24 * MSD) mod 24
#      This is the mean solar time at Airy-0 (longitude 0).
#   6. Local Mean Solar Time at observer longitude L (positive east):
#         LMST = (MTC + L * 24/360) mod 24
#      A site east of Airy-0 sees the sun cross its meridian *earlier*
#      than Airy-0; the sign convention matches Allison & McEwen Eq. A6.
#   7. sol_fraction = LMST / 24, fed to the spherical-mode helper.
#      Solar declination is derived either from a caller-supplied Ls
#      or, by default, from the same Allison & McEwen formulation:
#         Ls(t) ~ M + 10.691*sin(M) + 0.623*sin(2M) + ... (truncated)
#      This is Allison & McEwen Eq. A12, kept to 5 equation-of-centre
#      harmonics plus 7 PBS perturbation terms. The truncation matches
#      Mars24 within 0.05 deg of Ls.
#
# The leap-second constant is intentionally hard-coded rather than
# read from IERS bulletins: lighting tolerances here are ~1 deg in
# elevation, and a 37 s vs 38 s drift over five years is ~5e-7 sol
# (< 1e-4 deg), well below the precision budget.

_JULIAN_DATE_UNIX_EPOCH: float = 2440587.5
"""Julian Date of the Unix epoch (1970-01-01 00:00:00 UTC)."""

_J2000_JULIAN_DATE: float = 2451545.0
"""Julian Date of the J2000.0 epoch (2000-01-01 12:00:00 TT)."""

_TAI_MINUS_UTC_SECONDS: float = 37.0
"""TAI-UTC offset assumed for the modern Mars epoch (post-2017-01-01).

Constant within the simulated range. See the module-level UTC chain
notes for the precision budget that justifies the constant assumption.
"""

_TT_MINUS_TAI_SECONDS: float = 32.184
"""TT-TAI offset (fixed by SI definition)."""

_MSD_EPOCH_OFFSET_DAYS: float = 4.5
"""Allison & McEwen (2000) MSD reference offset in TT-J2000 days."""

_EARTH_TO_MARS_DAY_RATIO: float = 1.027491252
"""Ratio of a Mars solar day to an Earth solar day (Mars24)."""

_MSD_BASE: float = 44796.0
"""Allison & McEwen (2000) MSD at the reference epoch."""

_MSD_AIRY_CORRECTION: float = 0.00096
"""Small-angle correction tying MSD to the Airy-0 prime meridian."""


def utc_to_julian_date(utc_dt: datetime) -> float:
    """Convert a timezone-aware UTC ``datetime`` to a Julian Date (UT1).

    Args:
        utc_dt: Aware ``datetime`` with ``tzinfo == timezone.utc``. Naive
            datetimes are rejected because Mars sun positions depend on
            the wall-clock zone and silently assuming UTC has bitten
            users on similar planetary tooling.

    Returns:
        Julian Date in the UT1 (effectively UTC, modulo dUT1 ~ 0.9 s)
        scale, suitable for the Allison & McEwen JD -> MSD chain.

    Raises:
        TypeError: If ``utc_dt`` is not a ``datetime`` or is naive.
        ValueError: If ``utc_dt.tzinfo`` is not UTC.
    """
    if not isinstance(utc_dt, datetime):
        raise TypeError(f"utc_dt must be a datetime, got {type(utc_dt).__name__}")
    if utc_dt.tzinfo is None:
        raise TypeError("utc_dt must be timezone-aware (tzinfo=timezone.utc)")
    if utc_dt.utcoffset() != timezone.utc.utcoffset(utc_dt):
        raise ValueError(f"utc_dt must be in UTC (utcoffset=0), got tzinfo={utc_dt.tzinfo!r}")
    unix_seconds = utc_dt.timestamp()
    return unix_seconds / 86400.0 + _JULIAN_DATE_UNIX_EPOCH


def julian_date_to_mars_sol_date(jd_ut: float) -> float:
    """Convert a UT1 Julian Date to a Mars Sol Date (MSD).

    Implements Allison & McEwen (2000) §A.1 / Mars24 algorithm step C-2:

        JD_TT = JD_UT + (TAI-UTC + TT-TAI) / 86400
        MSD   = ((JD_TT - J2000 - 4.5) / 1.027491252)
                + 44796.0 - 0.00096

    Args:
        jd_ut: Julian Date in UT1.

    Returns:
        Mars Sol Date (continuous count of Mars solar days since the
        Allison & McEwen reference epoch, 1873-12-29 12:00 UTC).
    """
    jd_tt = jd_ut + (_TAI_MINUS_UTC_SECONDS + _TT_MINUS_TAI_SECONDS) / 86400.0
    delta_t_j2000 = jd_tt - _J2000_JULIAN_DATE
    return (
        (delta_t_j2000 - _MSD_EPOCH_OFFSET_DAYS) / _EARTH_TO_MARS_DAY_RATIO
        + _MSD_BASE
        - _MSD_AIRY_CORRECTION
    )


def mars_sol_date_to_local_solar_time_fraction(msd: float, longitude_east_deg: float) -> float:
    """Convert MSD + longitude to a local mean solar time fraction.

    Args:
        msd: Mars Sol Date.
        longitude_east_deg: Observer longitude in degrees, positive east
            of Airy-0. Wrapped into ``[0, 360)`` internally.

    Returns:
        Local mean solar time as a fraction of one Mars sol in [0, 1).
        ``0`` corresponds to local midnight, ``0.5`` to local solar
        transit (sun on the meridian).
    """
    mtc_hours = (24.0 * msd) % 24.0
    longitude_east_deg = longitude_east_deg % 360.0
    lmst_hours = (mtc_hours + longitude_east_deg * 24.0 / 360.0) % 24.0
    return lmst_hours / 24.0


def mars_areocentric_longitude_deg(jd_tt: float) -> float:
    """Compute Mars areocentric longitude Ls from a TT Julian Date.

    Implements the truncated harmonic series from Allison & McEwen
    (2000) Eqs. A5-A7 / Mars24 algorithm steps B-1 -- B-4:

        M     = (19.3871 + 0.52402073 * dT) mod 360       [deg]
        alpha = 270.3863 + 0.52403840 * dT                [deg]
        PBS   = sum of perturbations (Mars24 step B-3)
        v - M = (10.691 + 3.0e-7*dT) sin(M)
                + 0.623 sin(2M) + 0.050 sin(3M)
                + 0.005 sin(4M) + 0.0005 sin(5M) + PBS
        Ls    = (alpha + (v - M)) mod 360                 [deg]

    Args:
        jd_tt: Julian Date in Terrestrial Time.

    Returns:
        Areocentric longitude Ls in degrees, wrapped to [0, 360).
    """
    delta_t_j2000 = jd_tt - _J2000_JULIAN_DATE
    # Mean anomaly (Allison & McEwen Eq. A5; Mars24 step B-2 constants).
    M_deg = (19.3870 + 0.52402075 * delta_t_j2000) % 360.0
    # Angle of fictitious mean Sun (Eq. A6 / Mars24 step B-3).
    alpha_fms = 270.3863 + 0.52403840 * delta_t_j2000
    # Perturbations (Mars24 step B-3 truncated to dominant 7 terms)
    pbs_deg = (
        0.0071 * math.cos(math.radians((0.985626 * delta_t_j2000 / 2.2353) + 49.409))
        + 0.0057 * math.cos(math.radians((0.985626 * delta_t_j2000 / 2.7543) + 168.173))
        + 0.0039 * math.cos(math.radians((0.985626 * delta_t_j2000 / 1.1177) + 191.837))
        + 0.0037 * math.cos(math.radians((0.985626 * delta_t_j2000 / 15.7866) + 21.736))
        + 0.0021 * math.cos(math.radians((0.985626 * delta_t_j2000 / 2.1354) + 15.704))
        + 0.0020 * math.cos(math.radians((0.985626 * delta_t_j2000 / 2.4694) + 95.528))
        + 0.0018 * math.cos(math.radians((0.985626 * delta_t_j2000 / 32.8493) + 49.095))
    )
    M_rad = math.radians(M_deg)
    # Equation of centre (Eq. A7) plus PBS
    e_o_c_deg = (
        (10.691 + 3.0e-7 * delta_t_j2000) * math.sin(M_rad)
        + 0.623 * math.sin(2.0 * M_rad)
        + 0.050 * math.sin(3.0 * M_rad)
        + 0.005 * math.sin(4.0 * M_rad)
        + 0.0005 * math.sin(5.0 * M_rad)
        + pbs_deg
    )
    return (alpha_fms + e_o_c_deg) % 360.0


def sun_position_from_utc(
    utc_dt: datetime,
    latitude_deg: float,
    longitude_deg: float,
    *,
    ls_override_deg: float | None = None,
    obliquity_deg: float = MARS_OBLIQUITY_DEG,
) -> SunPosition:
    """Compute Mars sun position for a wall-clock UTC moment.

    Pipeline:

    1. ``utc_dt`` -> Julian Date (UT1) via :func:`utc_to_julian_date`.
    2. JD_UT -> Mars Sol Date via :func:`julian_date_to_mars_sol_date`.
    3. (MSD, longitude) -> local mean solar time fraction via
       :func:`mars_sol_date_to_local_solar_time_fraction`.
    4. JD_TT -> areocentric longitude Ls via
       :func:`mars_areocentric_longitude_deg` (unless ``ls_override_deg``
       is supplied -- callers running synthetic seasonal sweeps override
       Ls and keep the rest of the chain).
    5. (sol fraction, latitude, declination from Ls) ->
       :func:`compute_sol_sun_position` in spherical mode.

    Algorithm citation: Allison & McEwen (2000), *A post-Pathfinder
    evaluation of areocentric solar coordinates with improved timing
    recipes for Mars seasonal/diurnal climate studies*,
    Planet. Space Sci. 48 (2-3), 215-235. Constants are the public
    Mars24 implementation values
    (https://www.giss.nasa.gov/tools/mars24/help/algorithm.html).

    Args:
        utc_dt: Timezone-aware UTC ``datetime``.
        latitude_deg: Observer latitude in degrees, positive north,
            range ``[-90, 90]``.
        longitude_deg: Observer longitude in degrees, positive east of
            Airy-0. Any real value is accepted and reduced modulo 360.
        ls_override_deg: Optional override for the areocentric longitude
            Ls (degrees, ``[0, 360)``). Lets callers reuse the rest of
            the UTC pipeline while pinning a synthetic season.
        obliquity_deg: Mars axial tilt in degrees. Defaults to the
            modern-epoch value 25.19 deg. Pass
            ``MarsEnvConfig.obliquity_deg`` for config-driven runs.

    Returns:
        :class:`SunPosition` for the observer at the requested wall
        clock. Sub-horizon samples are clamped to ``elevation_deg = 0``
        to match the convention used by the rest of the rendering
        pipeline.

    Raises:
        TypeError: If ``utc_dt`` is naive or not a ``datetime``.
        ValueError: If ``utc_dt`` is not in UTC, ``latitude_deg`` is
            outside ``[-90, 90]``, or ``ls_override_deg`` is outside
            ``[0, 360)``.
    """
    if not -90.0 <= latitude_deg <= 90.0:
        raise ValueError(f"latitude_deg must be in [-90, 90], got {latitude_deg}")
    if ls_override_deg is not None and not 0.0 <= ls_override_deg < 360.0:
        raise ValueError(f"ls_override_deg must be in [0, 360), got {ls_override_deg}")

    jd_ut = utc_to_julian_date(utc_dt)
    msd = julian_date_to_mars_sol_date(jd_ut)
    sol_fraction = mars_sol_date_to_local_solar_time_fraction(msd, longitude_deg)

    if ls_override_deg is None:
        jd_tt = jd_ut + (_TAI_MINUS_UTC_SECONDS + _TT_MINUS_TAI_SECONDS) / 86400.0
        ls_deg = mars_areocentric_longitude_deg(jd_tt)
    else:
        ls_deg = ls_override_deg

    return compute_sol_sun_position(
        time_of_sol_fraction=sol_fraction,
        mode="spherical",
        latitude_deg=latitude_deg,
        ls_deg=ls_deg,
        obliquity_deg=obliquity_deg,
    )
