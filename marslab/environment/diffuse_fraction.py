"""Uncalibrated tau-only diffuse fraction; not a reproduced COMIMART calculation."""

import math

import numpy as np

# Retained heuristic values; reference conditions and extraction data are unavailable.
_DIFFUSE_FRACTION_TABLE = np.array(
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


def compute_diffuse_fraction_1d_approx(tau: float, zenith_rad: float | None = None) -> float:
    """Interpolate the retained sky fraction and clamp the table endpoints."""
    if not math.isfinite(tau) or tau < 0:
        raise ValueError("tau must be finite and >= 0")
    return float(np.interp(tau, _DIFFUSE_FRACTION_TABLE[:, 0], _DIFFUSE_FRACTION_TABLE[:, 1]))
