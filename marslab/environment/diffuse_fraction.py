"""Diffuse irradiance fraction using COMIMART model approximation.

Computes the fraction of total surface irradiance that arrives as diffuse
(scattered) light rather than direct beam. In the full COMIMART model
(Vicente-Retortillo et al. 2015) this quantity is a 2-D function of
``tau`` and solar zenith angle, and is additionally modulated by surface
albedo and dust single-scattering albedo.

MarsLab v1.0 ships a **1-D cartoon approximation** that collapses the
zenith dependence into a fixed tau->f_diffuse table. This is sufficient
for paper figures where tau sweeps dominate visual change and the
operating zenith range is narrow (mid-latitude Jezero sol, z in
~[30 deg, 60 deg]), but is explicitly NOT the 2-D COMIMART model. The
paper reports this as a "1-D approximation". A full 2-D extension is
deferred to v2.0.

Reference:
    Vicente-Retortillo, A., et al. (2015). A model to calculate solar
    radiation fluxes on the Martian surface. Journal of Space Weather
    and Space Climate, 5, A33.

Notes:
    The CO2-dominant Mars atmosphere still produces a small Rayleigh
    diffuse floor of ~10%, so the ``tau=0`` endpoint of the lookup
    table is ``0.10`` rather than ``0.0`` (the latter implies zero
    Rayleigh/molecular scattering and is unphysical even for a
    dust-free Mars atmosphere).

    The historical name ``compute_diffuse_fraction`` is preserved as a
    deprecated alias that delegates to
    :func:`compute_diffuse_fraction_1d_approx` so existing callers keep
    working. It will be removed in v2.0 when the 2-D model lands.
"""

import warnings
from typing import Optional

import numpy as np

# COMIMART 1-D approximation table: (tau, diffuse_fraction).
# Values derived from Vicente-Retortillo et al. (2015) Figure 4 at a
# representative mid-sol zenith; zenith dependence is discarded in the
# v1.0 1-D approximation. The tau=0 entry is set to the Rayleigh floor
# (~0.10) for a CO2 atmosphere rather than 0.0 to avoid an unphysical
# origin (zero molecular scattering).
_COMIMART_1D_TABLE = np.array(
    [
        [0.0, 0.10],
        [0.1, 0.18],
        [0.2, 0.27],
        [0.3, 0.35],
        [0.5, 0.44],
        [0.7, 0.49],
        [1.0, 0.52],
        [1.5, 0.60],
        [2.0, 0.67],
        [2.5, 0.75],
        [3.0, 0.82],
        [4.0, 0.90],
        [5.0, 0.94],
        [6.0, 0.97],
    ]
)


def compute_diffuse_fraction_1d_approx(
    tau: float,
    zenith_rad: Optional[float] = None,
) -> float:
    """Compute the diffuse fraction of surface irradiance (1-D cartoon).

    This is a 1-D reduction of the COMIMART radiative transfer model: the
    diffuse fraction is obtained by linear interpolation of a fixed
    ``tau -> f_diffuse`` table extracted from Vicente-Retortillo et al.
    (2015) Figure 4 at a representative mid-sol zenith. Zenith angle,
    surface albedo, and single-scattering albedo are intentionally
    discarded in v1.0 (see module docstring).

    Args:
        tau: Dust optical depth (dimensionless, >= 0).
        zenith_rad: Solar zenith angle in radians. **Currently unused**
            and kept only as a forward-compatible hook for the v2.0 2-D
            extension. The argument is accepted so call sites can be
            migrated early without touching signatures again.

    Returns:
        Fraction of total irradiance arriving as diffuse light in [0, 1].

    Raises:
        ValueError: If ``tau`` is negative.

    Notes:
        Endpoint ``tau=0 -> 0.10`` encodes the Rayleigh/molecular
        scattering floor of a dust-free CO2 atmosphere.
    """
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    # zenith_rad is intentionally ignored in v1.0. The hook exists so
    # callers can start passing zenith without a later signature churn.
    del zenith_rad

    return float(np.interp(tau, _COMIMART_1D_TABLE[:, 0], _COMIMART_1D_TABLE[:, 1]))


# ---------------------------------------------------------------------------
# Deprecated alias — retained so existing callers continue to work.
# Remove in v2.0 once the full 2-D COMIMART model is in place.
# ---------------------------------------------------------------------------
def compute_diffuse_fraction(tau: float) -> float:
    """Deprecated alias for :func:`compute_diffuse_fraction_1d_approx`.

    Kept for backward compatibility with existing call sites
    (``runtime.stage2_boot``, etc.). New code should call
    :func:`compute_diffuse_fraction_1d_approx` directly and, when the
    v2.0 2-D model lands, pass ``zenith_rad`` as well.

    Args:
        tau: Dust optical depth (dimensionless, >= 0).

    Returns:
        Fraction of total irradiance arriving as diffuse light in [0, 1].
    """
    warnings.warn(
        "compute_diffuse_fraction is deprecated; use "
        "compute_diffuse_fraction_1d_approx (see module docstring).",
        DeprecationWarning,
        stacklevel=2,
    )
    return compute_diffuse_fraction_1d_approx(tau)
