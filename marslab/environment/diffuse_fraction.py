"""Diffuse irradiance fraction using COMIMART model approximation.

Computes the fraction of total surface irradiance that arrives as diffuse
(scattered) light rather than direct beam, as a function of dust optical
depth (tau).

Reference:
    Vicente-Retortillo, A., et al. (2015). A model to calculate solar
    radiation fluxes on the Martian surface. Journal of Space Weather
    and Space Climate, 5, A33.
"""

import numpy as np

# COMIMART lookup table: (tau, diffuse_fraction)
# Extracted from Vicente-Retortillo et al. (2015) Figure 4.
_COMIMART_TABLE = np.array(
    [
        [0.0, 0.0],
        [0.1, 0.12],
        [0.2, 0.23],
        [0.3, 0.33],
        [0.5, 0.42],
        [0.7, 0.47],
        [1.0, 0.51],
        [1.5, 0.58],
        [2.0, 0.65],
        [2.5, 0.73],
        [3.0, 0.80],
        [4.0, 0.88],
        [5.0, 0.93],
        [6.0, 0.96],
    ]
)


def compute_diffuse_fraction(tau: float) -> float:
    """Compute the diffuse fraction of surface irradiance from dust optical depth.

    Uses linear interpolation of COMIMART model data from
    Vicente-Retortillo et al. (2015).

    Args:
        tau: Dust optical depth (dimensionless, >= 0).

    Returns:
        Fraction of total irradiance arriving as diffuse light [0, 1].

    Raises:
        ValueError: If tau is negative.
    """
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    return float(np.interp(tau, _COMIMART_TABLE[:, 0], _COMIMART_TABLE[:, 1]))
