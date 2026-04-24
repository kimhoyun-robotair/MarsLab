"""Trimesh ring-stitching for cave tube/floor/shaft/surface meshes.

Extracted from ``marslab/terrain/cave_generator.py`` in R5
(2026-04-23). Every function is pure: it takes numpy arrays and
returns a :class:`trimesh.Trimesh`, with no Isaac Sim dependency.

RNG consumption order preserved from the pre-split module:

    1. :func:`build_tube_shell` uses no RNG.
    2. :func:`build_tube_floor` draws ``rng.random(...)`` then
       ``rng.standard_normal(...)``.
    3. :func:`build_skylight_shaft` uses no RNG.
    4. :func:`build_surface_cap` draws one ``standard_normal``
       tensor of shape ``(rows, cols)``.
"""

from __future__ import annotations

import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter

from marslab.terrain.cave._constants import (
    FLOOR_DEBRIS_HEIGHT_SCALE,
    FLOOR_DEBRIS_SMOOTH_SIGMA,
    FLOOR_WIDTH_MIN_PTS,
    FLOOR_WIDTH_RATIO,
    SKYLIGHT_SHAFT_RING_MIN,
    SKYLIGHT_SHAFT_RING_SPACING_M,
    SURFACE_NOISE_AMPLITUDE_M,
    SURFACE_NOISE_SIGMA,
)
from marslab.terrain.cave.geometry import tangent_frames

__all__ = [
    "build_skylight_shaft",
    "build_surface_cap",
    "build_tube_floor",
    "build_tube_shell",
]


def build_tube_shell(
    centerline: np.ndarray,
    cross_sections: np.ndarray,
    ring_pts: int,
) -> trimesh.Trimesh:
    """Stitch cross-section rings into a tube shell (ceiling + walls).

    Winding is reversed so face normals point inward (toward the tube
    interior) -- cameras inside the tube see the inner surface.

    Args:
        centerline: ``(n_stations, 3)`` centerline positions.
        cross_sections: ``(n_stations, ring_pts, 2)`` local ``(x, z)``
            offsets produced by :func:`build_cross_sections`.
        ring_pts: Vertices per ring.

    Returns:
        :class:`trimesh.Trimesh` of the tube shell.
    """
    n_stations = len(centerline)
    _, perp = tangent_frames(centerline)

    local_x = cross_sections[..., 0]  # (n_stations, ring_pts)
    local_z = cross_sections[..., 1]
    vertices = np.empty((n_stations * ring_pts, 3), dtype=np.float64)
    vertices[:, 0] = (centerline[:, 0:1] + local_x * perp[:, 0:1]).ravel()
    vertices[:, 1] = (centerline[:, 1:2] + local_x * perp[:, 1:2]).ravel()
    vertices[:, 2] = (centerline[:, 2:3] + local_z).ravel()

    i, j = np.meshgrid(np.arange(n_stations - 1), np.arange(ring_pts - 1), indexing="ij")
    v0 = (i * ring_pts + j).ravel()
    v1 = v0 + 1
    v2 = v0 + ring_pts
    v3 = v2 + 1
    faces = np.empty((v0.size * 2, 3), dtype=np.int32)
    faces[0::2] = np.stack([v0, v2, v1], axis=1)
    faces[1::2] = np.stack([v1, v2, v3], axis=1)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def build_tube_floor(
    centerline: np.ndarray,
    cross_sections: np.ndarray,
    ring_pts: int,
    flat_pct: float,
    rng: np.random.Generator,
    debris_height_scale: float = FLOOR_DEBRIS_HEIGHT_SCALE,
    debris_smooth_sigma: float = FLOOR_DEBRIS_SMOOTH_SIGMA,
    floor_width_ratio: float = FLOOR_WIDTH_RATIO,
    floor_width_min_pts: int = FLOOR_WIDTH_MIN_PTS,
) -> trimesh.Trimesh:
    """Build the tube floor as a strip connecting the ring bottoms.

    The floor spans between the first and last vertex of each
    half-ellipse ring (both at floor level). Winding is CCW so face
    normals point in the +Z direction.

    Args:
        centerline: ``(n_stations, 3)`` centerline positions.
        cross_sections: ``(n_stations, ring_pts, 2)`` local offsets.
        ring_pts: Vertices per ring.
        flat_pct: Percentage of floor vertices that stay flat; the
            remainder receives a positive debris displacement.
        rng: Shared numpy random generator. Draws
            ``rng.random(n_stations * floor_pts)`` then
            ``rng.standard_normal(n_stations * floor_pts)``.
        debris_height_scale: Scale factor on the smoothed noise field.
        debris_smooth_sigma: Sigma for gaussian-smoothing the noise.
        floor_width_ratio: Fraction of ``ring_pts`` used for the floor
            grid width before clamping.
        floor_width_min_pts: Minimum floor grid width.

    Returns:
        :class:`trimesh.Trimesh` of the floor.
    """
    n_stations = len(centerline)
    _, perp = tangent_frames(centerline)

    floor_pts = max(int(ring_pts * floor_width_ratio), floor_width_min_pts)

    vertices = np.zeros((n_stations * floor_pts, 3), dtype=np.float64)
    for i in range(n_stations):
        cx, cy, cz = centerline[i]
        px, py, _ = perp[i]
        floor_x = np.linspace(cross_sections[i, 0, 0], cross_sections[i, -1, 0], floor_pts)
        base = i * floor_pts
        vertices[base : base + floor_pts, 0] = cx + floor_x * px
        vertices[base : base + floor_pts, 1] = cy + floor_x * py
        vertices[base : base + floor_pts, 2] = cz

    debris_mask = rng.random(n_stations * floor_pts) > (flat_pct / 100.0)
    noise = rng.standard_normal(n_stations * floor_pts) * debris_height_scale
    noise = gaussian_filter(noise.reshape(n_stations, floor_pts), sigma=debris_smooth_sigma).ravel()
    vertices[debris_mask, 2] += np.abs(noise[debris_mask])

    i, j = np.meshgrid(np.arange(n_stations - 1), np.arange(floor_pts - 1), indexing="ij")
    v0 = (i * floor_pts + j).ravel()
    v1 = v0 + 1
    v2 = v0 + floor_pts
    v3 = v2 + 1
    faces = np.empty((v0.size * 2, 3), dtype=np.int32)
    faces[0::2] = np.stack([v0, v1, v2], axis=1)
    faces[1::2] = np.stack([v1, v3, v2], axis=1)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def build_skylight_shaft(
    center_xy: tuple[float, float],
    diameter: float,
    surface_z: float,
    ceiling_z: float,
    overhang_deg: float,
    n_segments: int,
    ring_spacing_m: float = SKYLIGHT_SHAFT_RING_SPACING_M,
    ring_min: int = SKYLIGHT_SHAFT_RING_MIN,
) -> trimesh.Trimesh:
    """Generate a vertical or inward-overhanging skylight shaft mesh.

    The shaft connects the surface plane down to the tube ceiling.
    For ``overhang_deg > 0`` the radius grows linearly with depth so
    the walls lean inward toward the axis.

    Args:
        center_xy: ``(x, y)`` center of the shaft.
        diameter: Opening diameter at the surface.
        surface_z: Z coordinate of the ground surface.
        ceiling_z: Z coordinate of the tube ceiling.
        overhang_deg: Inward overhang angle (0 = vertical).
        n_segments: Vertices per ring.
        ring_spacing_m: Target vertical spacing between rings (clamped
            to at least ``ring_min`` rings).
        ring_min: Minimum ring count.

    Returns:
        :class:`trimesh.Trimesh` of the shaft wall (inward normals).
    """
    cx, cy = center_xy
    r_surface = diameter / 2.0
    overhang_rad = np.radians(overhang_deg)

    n_rings = max(ring_min, int((surface_z - ceiling_z) / ring_spacing_m))
    z_levels = np.linspace(surface_z, ceiling_z, n_rings)

    theta = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)

    radii = r_surface + (surface_z - z_levels) * np.tan(overhang_rad)  # (n_rings,)
    vertices = np.empty((n_rings * n_segments, 3), dtype=np.float64)
    vertices[:, 0] = (cx + radii[:, None] * np.cos(theta)).ravel()
    vertices[:, 1] = (cy + radii[:, None] * np.sin(theta)).ravel()
    vertices[:, 2] = np.repeat(z_levels, n_segments)

    i, j = np.meshgrid(np.arange(n_rings - 1), np.arange(n_segments), indexing="ij")
    j_next = (j + 1) % n_segments
    v0 = (i * n_segments + j).ravel()
    v1 = (i * n_segments + j_next).ravel()
    v2 = ((i + 1) * n_segments + j).ravel()
    v3 = ((i + 1) * n_segments + j_next).ravel()
    faces = np.empty((v0.size * 2, 3), dtype=np.int32)
    faces[0::2] = np.stack([v0, v2, v1], axis=1)
    faces[1::2] = np.stack([v1, v2, v3], axis=1)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def build_surface_cap(
    domain_size: tuple[int, int],
    resolution: float,
    surface_z: float,
    skylight_positions: list[tuple[float, float]],
    skylight_diameter: float,
    rng: np.random.Generator,
    noise_sigma: float = SURFACE_NOISE_SIGMA,
    noise_amplitude_m: float = SURFACE_NOISE_AMPLITUDE_M,
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Generate a flat surface terrain cap with skylight holes.

    The noise pattern mirrors ``procedural_generator._generate_flat``.
    Faces whose centroid falls inside any skylight disc are removed so
    the cap has a clean opening for the shaft mesh to meet.

    Args:
        domain_size: ``(rows, cols)`` in pixels.
        resolution: Meters per pixel.
        surface_z: Mean Z coordinate of the surface.
        skylight_positions: ``(x, y)`` centers of skylights.
        skylight_diameter: Diameter of each skylight.
        rng: Shared numpy random generator. Draws one
            ``standard_normal`` tensor of shape ``(rows, cols)``.
        noise_sigma: Gaussian sigma for the elevation noise.
        noise_amplitude_m: Peak-ish amplitude (sigma-normalized) of
            the noise in meters.

    Returns:
        Tuple ``(mesh, elevation_2d)``. ``elevation_2d`` is a
        ``float32`` heightmap with ``NaN`` inside skylight footprints
        so downstream spawn logic skips those cells.
    """
    rows, cols = domain_size

    noise = rng.standard_normal((rows, cols))
    smooth_noise = gaussian_filter(noise, sigma=noise_sigma)
    smooth_noise = smooth_noise / (np.std(smooth_noise) + 1e-8) * noise_amplitude_m
    elevation_2d = (surface_z + smooth_noise).astype(np.float32)

    n_verts = rows * cols
    col_idx = np.arange(cols, dtype=np.float64)
    row_idx = np.arange(rows, dtype=np.float64)
    col_grid, row_grid = np.meshgrid(col_idx, row_idx)

    vertices = np.zeros((n_verts, 3), dtype=np.float64)
    vertices[:, 0] = (col_grid * resolution).ravel()
    vertices[:, 1] = (row_grid * resolution).ravel()
    vertices[:, 2] = elevation_2d.ravel()

    r, c = np.meshgrid(np.arange(rows - 1), np.arange(cols - 1), indexing="ij")
    v00 = (r * cols + c).ravel()
    v01 = v00 + 1
    v10 = v00 + cols
    v11 = v10 + 1
    faces = np.empty((v00.size * 2, 3), dtype=np.int32)
    faces[0::2] = np.stack([v00, v01, v10], axis=1)
    faces[1::2] = np.stack([v01, v11, v10], axis=1)

    if skylight_positions:
        skylight_r = skylight_diameter / 2.0
        face_centroids = vertices[faces].mean(axis=1)
        keep = np.ones(len(faces), dtype=bool)
        x_grid = col_grid * resolution
        y_grid = row_grid * resolution
        for sx, sy in skylight_positions:
            keep &= np.hypot(face_centroids[:, 0] - sx, face_centroids[:, 1] - sy) > skylight_r
            elevation_2d[(x_grid - sx) ** 2 + (y_grid - sy) ** 2 < skylight_r**2] = np.nan
        faces = faces[keep]

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return mesh, elevation_2d
