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

    vertices = np.zeros((n_stations * ring_pts, 3), dtype=np.float64)
    for i in range(n_stations):
        cx, cy, cz = centerline[i]
        px, py, _ = perp[i]
        for j in range(ring_pts):
            local_x, local_z = cross_sections[i, j]
            wx = cx + local_x * px
            wy = cy + local_x * py
            wz = cz + local_z
            vertices[i * ring_pts + j] = [wx, wy, wz]

    faces = []
    for i in range(n_stations - 1):
        for j in range(ring_pts - 1):
            v0 = i * ring_pts + j
            v1 = i * ring_pts + j + 1
            v2 = (i + 1) * ring_pts + j
            v3 = (i + 1) * ring_pts + j + 1
            faces.append([v0, v2, v1])
            faces.append([v1, v2, v3])

    faces = np.array(faces, dtype=np.int32)
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
        left_x = cross_sections[i, 0, 0]
        right_x = cross_sections[i, -1, 0]
        floor_x = np.linspace(left_x, right_x, floor_pts)

        for j in range(floor_pts):
            wx = cx + floor_x[j] * px
            wy = cy + floor_x[j] * py
            wz = cz
            vertices[i * floor_pts + j] = [wx, wy, wz]

    debris_mask = rng.random(n_stations * floor_pts) > (flat_pct / 100.0)
    noise = rng.standard_normal(n_stations * floor_pts) * debris_height_scale
    noise = gaussian_filter(noise.reshape(n_stations, floor_pts), sigma=debris_smooth_sigma).ravel()
    vertices[debris_mask, 2] += np.abs(noise[debris_mask])

    faces = []
    for i in range(n_stations - 1):
        for j in range(floor_pts - 1):
            v0 = i * floor_pts + j
            v1 = i * floor_pts + j + 1
            v2 = (i + 1) * floor_pts + j
            v3 = (i + 1) * floor_pts + j + 1
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])

    faces = np.array(faces, dtype=np.int32)
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

    vertices = np.zeros((n_rings * n_segments, 3), dtype=np.float64)
    for i, z in enumerate(z_levels):
        depth = surface_z - z
        r = r_surface + depth * np.tan(overhang_rad)
        for j in range(n_segments):
            vertices[i * n_segments + j] = [
                cx + r * np.cos(theta[j]),
                cy + r * np.sin(theta[j]),
                z,
            ]

    faces = []
    for i in range(n_rings - 1):
        for j in range(n_segments):
            j_next = (j + 1) % n_segments
            v0 = i * n_segments + j
            v1 = i * n_segments + j_next
            v2 = (i + 1) * n_segments + j
            v3 = (i + 1) * n_segments + j_next
            faces.append([v0, v2, v1])
            faces.append([v1, v2, v3])

    faces = np.array(faces, dtype=np.int32)
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

    faces = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            v00 = r * cols + c
            v01 = r * cols + c + 1
            v10 = (r + 1) * cols + c
            v11 = (r + 1) * cols + c + 1
            faces.append([v00, v01, v10])
            faces.append([v01, v11, v10])

    faces = np.array(faces, dtype=np.int32)

    if skylight_positions:
        skylight_r = skylight_diameter / 2.0
        face_centroids = vertices[faces].mean(axis=1)
        keep = np.ones(len(faces), dtype=bool)
        for sx, sy in skylight_positions:
            dx = face_centroids[:, 0] - sx
            dy = face_centroids[:, 1] - sy
            dist = np.sqrt(dx**2 + dy**2)
            keep &= dist > skylight_r
        faces = faces[keep]

        for sx, sy in skylight_positions:
            for r in range(rows):
                for c in range(cols):
                    x = c * resolution
                    y = r * resolution
                    if (x - sx) ** 2 + (y - sy) ** 2 < skylight_r**2:
                        elevation_2d[r, c] = np.nan

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return mesh, elevation_2d
