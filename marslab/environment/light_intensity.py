"""Direct solar irradiance on the Martian surface using Beer's Law.

Reference:
    Appelbaum, J. & Flood, D.J. (1990). Solar radiation on Mars.
    NASA TM-102299. Equation 2 (Mars relative optical air mass).

Notes:
    Mars eccentricity (Ls-dependent) and the orbital correction to the
    top-of-atmosphere (TOA) irradiance are intentionally left to the caller
    in v1.0. Callers pass ``solar_constant`` set to the mean Mars TOA value
    (~589 W/m^2 at 1.524 AU semi-major axis). Per-Ls TOA scaling is deferred
    to a future seasonal-variation milestone.
"""

import math


def _appelbaum_airmass(zenith_angle_rad: float) -> float:
    """Relative optical air mass per Appelbaum & Flood (1990), Eq. 2.

    The classical "flat-earth" air mass ``1 / cos(z)`` diverges as the sun
    approaches the horizon and exceeds the empirical Mars value by >10% for
    ``z > 80 deg`` (a factor of ~2 at ``z = 89 deg``). The Appelbaum formula
    restores a finite, physically plausible path length up to the horizon.

    Formula:
        m(z) = 1 / (cos(z) + 0.15 * (93.885 - z_deg)^(-1.253))

    Args:
        zenith_angle_rad: Solar zenith angle in radians. Must be in ``[0, pi/2)``;
            values outside this range are handled by
            :func:`compute_direct_intensity` before this helper is called.

    Returns:
        Dimensionless relative optical air mass ``m(z)``.

    Notes:
        Appelbaum Eq. 2 is defined for ``z_deg < 93.885``. Within the public
        Beer's Law entry point we clamp ``z_deg <= 90`` (sun above horizon),
        so the ``(93.885 - z_deg)`` term stays strictly positive.
    """
    zenith_deg = math.degrees(zenith_angle_rad)
    cos_z = math.cos(zenith_angle_rad)
    # Eq. 2 of NASA TM-102299. The additive term replaces the divergent
    # ``1 / cos`` limb with an empirical fit to Mars atmosphere tables.
    return 1.0 / (cos_z + 0.15 * (93.885 - zenith_deg) ** (-1.253))


def compute_direct_intensity(solar_constant: float, tau: float, zenith_angle_rad: float) -> float:
    """Compute direct beam irradiance at the Martian surface via Beer's Law.

    Beer's Law (Mars form, NASA TM-102299 Eq. 1-2):
        I(z) = I_0 * exp(-tau * m(z))

    where ``m(z)`` is the relative optical air mass from Appelbaum &
    Flood (1990) Eq. 2. The Appelbaum form replaces the flat-earth
    approximation ``m = 1 / cos(z)`` which overestimates attenuation
    for ``z > 70 deg`` and diverges at the horizon.

    Args:
        solar_constant: Top-of-atmosphere irradiance in W/m^2. Mars mean at
            1.524 AU semi-major axis is ~589 W/m^2. Ls-dependent eccentricity
            scaling is the caller's responsibility (deferred to a future
            seasonal-variation milestone).
        tau: Dust optical depth (dimensionless, >= 0).
        zenith_angle_rad: Solar zenith angle in radians in ``[0, pi]``.
            Values at or below the horizon (``zenith >= pi/2``) return 0.

    Returns:
        Direct beam irradiance at the surface in W/m^2. Returns 0.0 if the
        sun is at or below the horizon (``zenith >= pi/2``).

    Raises:
        ValueError: If ``solar_constant`` or ``tau`` is negative.
    """
    if solar_constant < 0:
        raise ValueError(f"solar_constant must be >= 0, got {solar_constant}")
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    # Horizon cutoff uses the angle directly rather than ``cos(z) <= 0`` because
    # ``math.cos(pi/2)`` evaluates to ~6e-17 in IEEE-754, which would otherwise
    # slip past a ``cos_z <= 0`` guard and feed a near-zero cosine into the
    # Appelbaum air mass — producing a tiny but nonzero residual irradiance for
    # a sun at or below the horizon. Comparing the radian value directly avoids
    # that footgun.
    if zenith_angle_rad >= 0.5 * math.pi:
        return 0.0

    airmass = _appelbaum_airmass(zenith_angle_rad)
    return solar_constant * math.exp(-tau * airmass)
