"""Centerline, cross-section, tangent frame math for cave generation.

Pure numpy + scipy. No Isaac Sim, no trimesh. Extracted from the
original ``marslab/terrain/cave_generator.py`` in R5 (2026-04-23).

Consumption order of the shared ``rng`` must be preserved bit-exactly
with the pre-split module:

    1. :func:`build_centerline` draws two uniform phases.
    2. :func:`build_cross_sections` draws one ``standard_normal``
       block of shape ``(n_stations, ring_pts)``.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from marslab.terrain.cave._constants import (
    CENTERLINE_AMP_DOMAIN_RATIO,
    CENTERLINE_FREQ_RATIO_SECONDARY,
    CENTERLINE_PATH_LENGTH_FACTOR,
    CENTERLINE_SECONDARY_AMP_RATIO,
    CROSS_SECTION_SMOOTH_SIGMA,
)

__all__ = ["build_centerline", "build_cross_sections", "tangent_frames"]


def build_centerline(
    domain_m: tuple[float, float],
    direction_deg: float,
    curvature: float,
    n_points: int,
    floor_z: float,
    rng: np.random.Generator,
    path_length_factor: float = CENTERLINE_PATH_LENGTH_FACTOR,
    freq_ratio_secondary: float = CENTERLINE_FREQ_RATIO_SECONDARY,
    secondary_amp_ratio: float = CENTERLINE_SECONDARY_AMP_RATIO,
    amp_domain_ratio: float = CENTERLINE_AMP_DOMAIN_RATIO,
) -> np.ndarray:
    """Generate a sinusoidal tube centerline across the domain.

    Pattern mirrors ``procedural_generator._generate_canyon()`` for the
    sweep direction and sinusoidal perturbation.

    Args:
        domain_m: ``(height_m, width_m)`` of the domain in meters.
        direction_deg: Tube axis direction (``0`` = along Y, ``90`` = X).
        curvature: Amplitude factor for the sinusoidal perturbation.
        n_points: Number of stations along the path.
        floor_z: Z coordinate assigned to every centerline point.
        rng: Shared numpy random generator. Two uniform draws are made
            for the two phase offsets of the sinusoidal perturbation.
        path_length_factor: Multiplier on the longest domain side used
            to extend the centerline past the domain edges.
        freq_ratio_secondary: Ratio of the secondary harmonic frequency
            over the primary.
        secondary_amp_ratio: Amplitude of the secondary harmonic as a
            fraction of the primary amplitude.
        amp_domain_ratio: Primary amplitude as a fraction of the short
            domain side.

    Returns:
        ``(n_points, 3)`` array of centerline positions with all
        points at ``z = floor_z``.
    """
    height_m, width_m = domain_m
    center_x = width_m / 2.0
    center_y = height_m / 2.0

    t = np.linspace(0, 1, n_points)
    dir_rad = np.radians(direction_deg)

    path_len = max(height_m, width_m) * path_length_factor

    along = (t - 0.5) * path_len  # [-half_len, +half_len]
    path_x = center_x + along * np.sin(dir_rad)
    path_y = center_y + along * np.cos(dir_rad)

    # Sinusoidal perturbation perpendicular to path
    freq1 = 2.0 * np.pi / path_len
    freq2 = freq1 * freq_ratio_secondary
    phase1 = rng.uniform(0, 2 * np.pi)
    phase2 = rng.uniform(0, 2 * np.pi)
    amplitude = curvature * min(height_m, width_m) * amp_domain_ratio

    perturb = amplitude * np.sin(freq1 * along + phase1) + amplitude * secondary_amp_ratio * np.sin(
        freq2 * along + phase2
    )

    perp_x = np.cos(dir_rad)
    perp_y = -np.sin(dir_rad)

    centerline = np.zeros((n_points, 3), dtype=np.float64)
    centerline[:, 0] = path_x + perturb * perp_x
    centerline[:, 1] = path_y + perturb * perp_y
    centerline[:, 2] = floor_z

    return centerline


def build_cross_sections(
    centerline: np.ndarray,
    tube_width: float,
    height_ratio: float,
    noise_amp: float,
    ring_pts: int,
    rng: np.random.Generator,
    smooth_sigma: tuple[float, float] = CROSS_SECTION_SMOOTH_SIGMA,
) -> np.ndarray:
    """Generate half-ellipse cross-section profiles at each station.

    Args:
        centerline: ``(n_stations, 3)`` centerline positions.
        tube_width: Tube width in meters (major axis, full width).
        height_ratio: Ratio of semi-minor (vertical) to full width.
        noise_amp: +/- fraction of Gaussian noise on radius.
        ring_pts: Number of vertices per ring (half-ellipse).
        rng: Shared numpy random generator. Draws one
            ``standard_normal`` tensor of shape ``(n_stations, ring_pts)``.
        smooth_sigma: ``(sigma_station, sigma_ring)`` for gaussian_filter.

    Returns:
        ``(n_stations, ring_pts, 2)`` array of ``(local_x, local_z)``
        offsets where ``local_x`` is the horizontal offset from center
        and ``local_z`` is the vertical offset.
    """
    n_stations = len(centerline)
    a = tube_width / 2.0
    b = tube_width * height_ratio

    theta = np.linspace(0, np.pi, ring_pts)
    base_x = a * np.cos(theta)
    base_z = b * np.sin(theta)

    raw_noise = rng.standard_normal((n_stations, ring_pts))
    smooth_noise = gaussian_filter(raw_noise, sigma=smooth_sigma)
    noise_std = np.std(smooth_noise)
    if noise_std > 1e-8:
        smooth_noise = smooth_noise / noise_std * noise_amp
    else:
        smooth_noise = np.zeros_like(smooth_noise)

    profiles = np.zeros((n_stations, ring_pts, 2), dtype=np.float64)
    for i in range(n_stations):
        scale = 1.0 + smooth_noise[i]
        profiles[i, :, 0] = base_x * scale
        profiles[i, :, 1] = base_z * scale

    return profiles


def tangent_frames(centerline: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute unit tangent and horizontal perpendicular along centerline.

    Uses central differences in the interior and forward/backward
    differences at the endpoints. The perpendicular is produced by a
    90-degree rotation of the tangent in the XY plane and then
    re-normalized to shield against zero-length tangents.

    Args:
        centerline: ``(n, 3)`` centerline positions.

    Returns:
        Tuple ``(tangent, perp)`` each of shape ``(n, 3)`` with unit
        vectors. ``perp`` has ``z = 0`` by construction.
    """
    n = len(centerline)
    tangent = np.zeros((n, 3), dtype=np.float64)

    tangent[1:-1] = centerline[2:] - centerline[:-2]
    tangent[0] = centerline[1] - centerline[0]
    tangent[-1] = centerline[-1] - centerline[-2]

    norms = np.linalg.norm(tangent, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    tangent = tangent / norms

    perp = np.zeros_like(tangent)
    perp[:, 0] = -tangent[:, 1]
    perp[:, 1] = tangent[:, 0]
    perp[:, 2] = 0.0

    perp_norms = np.linalg.norm(perp, axis=1, keepdims=True)
    perp_norms = np.maximum(perp_norms, 1e-8)
    perp = perp / perp_norms

    return tangent, perp
