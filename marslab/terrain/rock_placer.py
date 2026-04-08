"""Rock placement using Golombek & Rapp (1997) size-frequency distribution.

Implements the cumulative fractional area (CFA) model for Mars rock
populations, validated against Viking Lander, Mars Pathfinder, and
InSight landing site data.

Reference:
    Golombek, M.P. & Rapp, D. (1997). Size-frequency distributions of
    rocks on Mars and Earth analog sites. JGR Planets, 102(E2), 4117-4129.
"""

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class RockPlacement:
    """A single rock placed on the terrain surface.

    Attributes:
        x: X position in meters within the placement area.
        y: Y position in meters within the placement area.
        diameter: Rock diameter in meters.
        height: Rock height in meters (derived from diameter).
    """

    x: float
    y: float
    diameter: float
    height: float


def compute_q(k: float) -> float:
    """Compute the q parameter from CFA fraction k.

    Uses the Golombek et al. empirical relation:
        q(k) = 1.79 + 0.152 / k

    This is a general mathematical function. For Mars applications,
    practical k values range from 0.001 to 0.15.

    Args:
        k: Total cumulative fractional area (must be in (0, 1]).

    Returns:
        The q parameter for the exponential SFD model.

    Raises:
        ValueError: If k is not in the valid range.
    """
    if k <= 0 or k > 1:
        raise ValueError(f"k must be in (0, 1], got {k}")
    return 1.79 + 0.152 / k


def compute_cfa(k: float, diameter: float) -> float:
    """Compute cumulative fractional area for rocks >= diameter.

    Golombek & Rapp (1997): F_k(D) = k * exp(-q(k) * D)

    This is a general mathematical function. For Mars applications,
    practical k values range from 0.001 to 0.15.

    Args:
        k: Total CFA fraction (must be in (0, 1]).
        diameter: Rock diameter threshold in meters (>= 0).

    Returns:
        Fraction of area covered by rocks with diameter >= D.

    Raises:
        ValueError: If k is not in valid range or diameter is negative.
    """
    if diameter < 0:
        raise ValueError(f"diameter must be >= 0, got {diameter}")
    q = compute_q(k)
    return k * math.exp(-q * diameter)


def sample_rocks_golombek(
    area_m2: float,
    k: float,
    diameter_range: tuple[float, float],
    seed: int,
    height_ratio: float = 0.5,
) -> list[RockPlacement]:
    """Sample rock placements using the Golombek SFD model.

    Generates a population of rocks within a square area using the
    Golombek & Rapp (1997) cumulative size-frequency distribution.
    Rock positions are uniformly distributed. Rock heights are derived
    from diameters using an empirical ratio.

    Args:
        area_m2: Total area in square meters (must be > 0).
        k: CFA fraction (rock abundance, must be in (0, 0.15]).
            Mars observed range: VL1~0.08, VL2~0.04, MPF~0.06, InSight~0.02.
        diameter_range: (min_diameter, max_diameter) in meters.
        seed: Random seed for reproducibility.
        height_ratio: Rock height/diameter ratio. Default 0.5 per
            Golombek et al. (2012) empirical Mars rock measurements.

    Returns:
        List of RockPlacement instances, sorted by diameter descending.

    Raises:
        ValueError: If parameters are out of valid range.
    """
    if area_m2 <= 0:
        raise ValueError(f"area_m2 must be > 0, got {area_m2}")
    if k <= 0 or k > 0.15:
        raise ValueError(f"k must be in (0, 0.15], got {k}")
    d_min, d_max = diameter_range
    if d_min >= d_max:
        raise ValueError(f"diameter_range must be (min, max) with min < max, got {diameter_range}")
    if d_min <= 0:
        raise ValueError(f"min diameter must be > 0, got {d_min}")

    rng = np.random.default_rng(seed)
    q = compute_q(k)
    side = math.sqrt(area_m2)
    n_bins = 50

    bin_edges = np.logspace(np.log10(d_min), np.log10(d_max), n_bins + 1)
    rocks: list[RockPlacement] = []

    for i in range(n_bins):
        d_lo = bin_edges[i]
        d_hi = bin_edges[i + 1]
        d_mid = (d_lo + d_hi) / 2.0

        # CFA difference: area fraction covered by rocks in this bin
        delta_cfa = k * math.exp(-q * d_lo) - k * math.exp(-q * d_hi)

        # Expected count: total covered area / single rock area
        rock_area = math.pi / 4.0 * d_mid**2
        if rock_area <= 0:
            continue
        expected_count = area_m2 * delta_cfa / rock_area
        if expected_count <= 0:
            continue

        count = rng.poisson(expected_count)

        for _ in range(count):
            d = rng.uniform(d_lo, d_hi)
            x = rng.uniform(0, side)
            y = rng.uniform(0, side)
            h = height_ratio * d
            rocks.append(RockPlacement(x=x, y=y, diameter=d, height=h))

    rocks.sort(key=lambda r: r.diameter, reverse=True)
    return rocks
