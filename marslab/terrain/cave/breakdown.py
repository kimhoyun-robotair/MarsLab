"""Lognormal rejection-sampled breakdown block placement.

Extracted from the pre-R5 monolithic ``cave_generator.py`` in R5
(2026-04-23); the orchestrator now lives at
:mod:`marslab.terrain.cave.orchestrator`. Pure numpy. No Isaac Sim,
no trimesh.

Size distribution follows Blank 2024 / BRAILLE: lognormal diameters
with a hard cap at :data:`BREAKDOWN_DIAMETER_CAP_M`.

RNG consumption order preserved from the pre-split module: inside the
attempt loop, per iteration the draws are

    1. ``rng.lognormal(mean=log(block_mean) - block_sigma**2/2,
       sigma=block_sigma)``  (mean-corrected so ``E[diameter] = block_mean``)
    2. ``rng.integers(0, n_stations)``
    3. ``rng.uniform(lo, hi)``

which terminates either at ``target_area`` coverage or after
:data:`BREAKDOWN_MAX_ATTEMPTS` iterations.

For a lognormal ``X`` parameterised by the underlying normal's mean
``mu`` and std ``sigma``, ``E[X] = exp(mu + sigma**2 / 2)`` and
``median[X] = exp(mu)``.  Since :data:`block_mean` is a true arithmetic
mean (Blank 2024 reports the mean block diameter), we set
``mu = log(block_mean) - sigma**2/2`` so the draws' expected value equals
the configured ``block_mean``.  The earlier ``mu = log(block_mean)`` form
made ``block_mean`` the *median*, biasing the expected value upward by
``exp(sigma**2/2)``.
"""

from __future__ import annotations

import numpy as np

from marslab.terrain.cave._constants import (
    BREAKDOWN_CENTERLINE_EXCLUSION_RATIO,
    BREAKDOWN_DIAMETER_CAP_M,
    BREAKDOWN_FLOOR_SPAN_RATIO,
    BREAKDOWN_MAX_ATTEMPTS,
)
from marslab.terrain.cave.geometry import tangent_frames

__all__ = ["generate_breakdown_positions"]


def generate_breakdown_positions(
    centerline: np.ndarray,
    cross_sections: np.ndarray,
    floor_z: float,
    ring_pts: int,  # noqa: ARG001 -- retained for back-compat signature
    coverage_pct: float,
    block_mean: float,
    block_sigma: float,
    skylight_positions: list[tuple[float, float]],
    skylight_diameter: float,
    rng: np.random.Generator,
    diameter_cap_m: float = BREAKDOWN_DIAMETER_CAP_M,
    floor_span_ratio: float = BREAKDOWN_FLOOR_SPAN_RATIO,
    centerline_exclusion_ratio: float = BREAKDOWN_CENTERLINE_EXCLUSION_RATIO,
    max_attempts: int = BREAKDOWN_MAX_ATTEMPTS,
) -> list[dict]:
    """Generate breakdown block positions on the cave floor.

    Uses a lognormal diameter distribution (Blank 2024 / BRAILLE) and
    rejection sampling to stay inside the tube footprint while
    skipping a centerline exclusion corridor (rover passage) and
    skylight discs (debris cones live there).

    Args:
        centerline: ``(n_stations, 3)`` centerline positions.
        cross_sections: ``(n_stations, ring_pts, 2)`` local offsets.
        floor_z: Z coordinate of the floor. Used as ``z`` for every
            block.
        ring_pts: Legacy argument retained so the public orchestrator
            signature is identical. Currently unused.
        coverage_pct: Target floor area coverage in percent. ``<= 0``
            short-circuits to an empty list.
        block_mean: Arithmetic mean diameter (meters). The underlying
            normal's ``mu`` is set to ``log(block_mean) - block_sigma**2/2``
            so that ``E[diameter] == block_mean`` exactly (before the
            ``diameter_cap_m`` truncation).
        block_sigma: Standard deviation of the underlying normal
            (``sigma`` argument to ``rng.lognormal``).
        skylight_positions: Skylight centers to avoid.
        skylight_diameter: Diameter of skylights.
        rng: Shared numpy random generator.
        diameter_cap_m: Hard upper bound on block diameter.
        floor_span_ratio: Shrink factor applied to both ``left_x`` and
            ``right_x`` before sampling ``local_x``.
        centerline_exclusion_ratio: Half-width of the centerline
            exclusion corridor expressed as a fraction of the station
            width.
        max_attempts: Rejection-sampling attempt cap.

    Returns:
        List of dicts with keys ``x``, ``y``, ``z``, ``diameter`` (all
        floats).
    """
    if coverage_pct <= 0:
        return []

    _, perp = tangent_frames(centerline)
    n_stations = len(centerline)
    widths = np.abs(cross_sections[:, -1, 0] - cross_sections[:, 0, 0])

    if n_stations > 1:
        segment_lens = np.linalg.norm(centerline[1:, :2] - centerline[:-1, :2], axis=1)
        avg_widths = (widths[:-1] + widths[1:]) / 2.0
        total_area = float(np.sum(segment_lens * avg_widths))
    else:
        total_area = widths[0] * 10.0

    target_area = total_area * (coverage_pct / 100.0)

    blocks: list[dict] = []
    placed_area = 0.0

    for _ in range(max_attempts):
        if placed_area >= target_area:
            break

        # Mean-correction: for lognormal X with underlying normal params
        # (mu, sigma), E[X] = exp(mu + sigma**2 / 2).  Setting
        # mu = log(block_mean) - sigma**2/2 makes E[X] = block_mean so the
        # configured ``block_mean`` is the arithmetic mean, not the median.
        diameter = float(
            rng.lognormal(
                mean=np.log(block_mean) - block_sigma**2 / 2.0,
                sigma=block_sigma,
            )
        )
        diameter = min(diameter, diameter_cap_m)

        station_idx = rng.integers(0, n_stations)
        cx, cy, _cz = centerline[station_idx]
        px, py, _ = perp[station_idx]

        left_x = cross_sections[station_idx, 0, 0]
        right_x = cross_sections[station_idx, -1, 0]
        lo = min(left_x, right_x) * floor_span_ratio
        hi = max(left_x, right_x) * floor_span_ratio
        local_x = rng.uniform(lo, hi)

        bx = cx + local_x * px
        by = cy + local_x * py
        bz = floor_z

        skip = False
        for sx, sy in skylight_positions:
            if (bx - sx) ** 2 + (by - sy) ** 2 < (skylight_diameter / 2.0) ** 2:
                skip = True
                break
        if skip:
            continue

        if abs(local_x) < widths[station_idx] * centerline_exclusion_ratio:
            continue

        blocks.append({"x": float(bx), "y": float(by), "z": float(bz), "diameter": diameter})
        placed_area += np.pi * (diameter / 2.0) ** 2

    return blocks
