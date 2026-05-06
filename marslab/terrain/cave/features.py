"""Skylight placement and debris cone construction.

Pure numpy + trimesh. No Isaac Sim. The orchestrator entry point lives
at :mod:`marslab.terrain.cave.orchestrator`.

:func:`compute_skylight_positions` is deterministic given its inputs and
makes no RNG draws. :func:`build_debris_cone` draws one
``rng.standard_normal`` per ring, for a total of
``DEBRIS_CONE_RINGS`` draws of length ``DEBRIS_CONE_SEGMENTS``.
"""

from __future__ import annotations

import numpy as np
import trimesh

from marslab.terrain.cave._constants import (
    DEBRIS_CONE_NOISE_SIGMA,
    DEBRIS_CONE_RADIUS_SHRINK,
    DEBRIS_CONE_RINGS,
    DEBRIS_CONE_SEGMENTS,
    SKYLIGHT_MARGIN_EXTRA_M,
    SKYLIGHT_SEPARATION_RATIO,
)

__all__ = ["build_debris_cone", "compute_skylight_positions"]


def compute_skylight_positions(
    centerline: np.ndarray,
    count: int,
    diameter: float,
    domain_m: tuple[float, float],
    separation_ratio: float = SKYLIGHT_SEPARATION_RATIO,
    margin_extra_m: float = SKYLIGHT_MARGIN_EXTRA_M,
) -> list[tuple[float, float]]:
    """Select skylight positions evenly along the centerline.

    Positions are spaced uniformly along the in-domain portion of the
    centerline, with an inter-skylight separation check so that
    closely-spaced stations never collapse into overlapping openings.

    Args:
        centerline: ``(n_stations, 3)`` centerline positions.
        count: Number of skylights requested. ``0`` returns an empty
            list.
        diameter: Skylight diameter in meters.
        domain_m: ``(height_m, width_m)``.
        separation_ratio: Minimum center-to-center distance expressed
            as a multiple of ``diameter``.
        margin_extra_m: Extra margin beyond ``diameter/2`` to keep
            skylights from kissing the domain edge.

    Returns:
        List of ``(x, y)`` tuples for skylight centers, length exactly
        ``count``.

    Raises:
        ValueError: If the requested ``count`` cannot be satisfied for
            the given domain (no valid centerline indices, or the
            separation check rejects too many candidates). Cave SLAM
            benchmarks rely on exact count so the function fails fast
            rather than silently returning fewer items.
    """
    if count == 0:
        return []

    height_m, width_m = domain_m
    margin = diameter / 2.0 + margin_extra_m

    valid = (
        (centerline[:, 0] > margin)
        & (centerline[:, 0] < width_m - margin)
        & (centerline[:, 1] > margin)
        & (centerline[:, 1] < height_m - margin)
    )
    valid_indices = np.where(valid)[0]

    if len(valid_indices) == 0:
        raise ValueError(
            f"compute_skylight_positions: no centerline station fits the "
            f"in-domain margin (diameter={diameter}, margin_extra_m={margin_extra_m}, "
            f"domain={domain_m}); cannot place {count} skylight(s)"
        )

    positions: list[tuple[float, float]] = []
    min_dist = diameter * separation_ratio

    step = max(1, len(valid_indices) // (count + 1))
    for k in range(1, count + 1):
        idx = valid_indices[min(k * step, len(valid_indices) - 1)]
        cx, cy = float(centerline[idx, 0]), float(centerline[idx, 1])

        too_close = False
        for px, py in positions:
            if (cx - px) ** 2 + (cy - py) ** 2 < min_dist**2:
                too_close = True
                break
        if not too_close:
            positions.append((cx, cy))

    if len(positions) < count:
        raise ValueError(
            f"compute_skylight_positions: requested count={count} but only "
            f"{len(positions)} position(s) satisfied the separation check "
            f"(min_dist={min_dist:.2f} m, valid_indices={len(valid_indices)}); "
            f"reduce skylight_count, shrink skylight_diameter_m, or enlarge the domain"
        )

    return positions


def build_debris_cone(
    center_xy: tuple[float, float],
    floor_z: float,
    skylight_diameter: float,
    angle_of_repose: float,
    rng: np.random.Generator,
    n_rings: int = DEBRIS_CONE_RINGS,
    n_segments: int = DEBRIS_CONE_SEGMENTS,
    radius_shrink: float = DEBRIS_CONE_RADIUS_SHRINK,
    noise_sigma: float = DEBRIS_CONE_NOISE_SIGMA,
) -> trimesh.Trimesh:
    """Generate a conical debris pile beneath a skylight.

    The cone apex sits above ``floor_z`` by ``base_radius *
    tan(angle_of_repose)``. Each ring radius is jittered by a small
    Gaussian factor to break the perfect cone silhouette.

    Args:
        center_xy: ``(x, y)`` ground center of the pile.
        floor_z: Z coordinate of the tube floor beneath the apex.
        skylight_diameter: Diameter of the skylight above (the cone
            base inherits a shrunk version of this).
        angle_of_repose: Slope angle in degrees (Mars regolith ~30).
        rng: Shared numpy random generator. Draws one
            ``standard_normal(n_segments)`` per ring.
        n_rings: Ring count from apex (inclusive) to base (inclusive).
        n_segments: Vertices per ring.
        radius_shrink: Base radius as a fraction of ``skylight_diameter/2``.
        noise_sigma: Multiplier on the standard-normal radial jitter.

    Returns:
        :class:`trimesh.Trimesh` of the debris cone (outward normals).
    """
    cx, cy = center_xy
    base_radius = skylight_diameter / 2.0 * radius_shrink
    cone_height = base_radius * np.tan(np.radians(angle_of_repose))

    theta = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)
    apex_z = floor_z + cone_height

    t = np.arange(n_rings) / (n_rings - 1)  # (n_rings,)
    r_noise = 1.0 + rng.standard_normal((n_rings, n_segments)) * noise_sigma
    r_scaled = (t * base_radius)[:, None] * r_noise  # (n_rings, n_segments)
    vertex_array = np.empty((n_rings * n_segments, 3), dtype=np.float64)
    vertex_array[:, 0] = (cx + r_scaled * np.cos(theta)).ravel()
    vertex_array[:, 1] = (cy + r_scaled * np.sin(theta)).ravel()
    vertex_array[:, 2] = np.repeat(apex_z - t * cone_height, n_segments)

    i, j = np.meshgrid(np.arange(n_rings - 1), np.arange(n_segments), indexing="ij")
    j_next = (j + 1) % n_segments
    v0 = (i * n_segments + j).ravel()
    v1 = (i * n_segments + j_next).ravel()
    v2 = ((i + 1) * n_segments + j).ravel()
    v3 = ((i + 1) * n_segments + j_next).ravel()
    face_array = np.empty((v0.size * 2, 3), dtype=np.int32)
    face_array[0::2] = np.stack([v0, v1, v2], axis=1)
    face_array[1::2] = np.stack([v1, v3, v2], axis=1)
    return trimesh.Trimesh(vertices=vertex_array, faces=face_array, process=False)
