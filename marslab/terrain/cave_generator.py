"""Procedural Mars lava tube cave mesh generator.

Generates a 3D cave mesh assembly (tube shell, floor, skylight shaft,
surface cap) for Isaac Sim rendering and PhysX collision. Caves cannot
be represented as 2D heightmaps because the ceiling introduces a second
z-value at each (x, y) position.

Science basis: Sauro et al. 2020, Cushing 2007/2012, Theinat 2020,
Blair 2017, Blank 2024 (BRAILLE). Full references in
work_log/scene_generation/mars_cave.md.

Design follows P3 (Offline-First Testing):
  Layer 1: This module — pure numpy + trimesh, no Isaac Sim.
  Layer 2: cave_mesh_builder.py — USD prim creation (separate file).

Architecture: Cross-section sweep (ring stacking).
  1. Generate sinusoidal centerline along tube axis
  2. At each station, place a half-ellipse cross-section ring with noise
  3. Stitch adjacent rings into triangle strips (tube shell + floor)
  4. Add skylight shaft as vertical/overhanging cylinder
  5. Add surface terrain cap with skylight holes
  6. Generate breakdown block positions (for PointInstancer)
"""

from __future__ import annotations

import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter


def generate_cave_mesh(
    tube_width_m: float = 200.0,
    tube_height_ratio: float = 0.5,
    cross_section_noise: float = 0.20,
    tube_direction_deg: float = 0.0,
    tube_curvature: float = 0.15,
    ceiling_thickness_m: float = 50.0,
    skylight_count: int = 10,
    skylight_diameter_m: float = 20.0,
    skylight_depth_m: float = 90.0,
    skylight_overhang_deg: float = 5.0,
    debris_cone_present: bool = True,
    debris_cone_count: int = 5,
    debris_cone_angle_deg: float = 30.0,
    breakdown_coverage_pct: float = 25.0,
    breakdown_block_mean_m: float = 0.5,
    breakdown_block_sigma: float = 0.3,
    floor_flat_pct: float = 70.0,
    ring_resolution: int = 40,
    path_resolution: int = 100,
    domain_size: tuple[int, int] = (400, 400),
    resolution: float = 1.0,
    seed: int = 42,
) -> dict:
    """Generate a complete Mars lava tube cave mesh assembly.

    All geometry is generated offline (no Isaac Sim). Returns a dict
    of trimesh objects and metadata for subsequent USD conversion.

    Args:
        tube_width_m: Lava tube width in meters.
        tube_height_ratio: Height / width ratio (half-ellipse).
        cross_section_noise: ±fraction noise on cross-section radius.
        tube_direction_deg: Tube axis direction (0=Y, 90=X).
        tube_curvature: Sinusoidal curvature amplitude factor.
        ceiling_thickness_m: Rock above tube crown.
        skylight_count: Number of skylights (0-2).
        skylight_diameter_m: Skylight opening diameter.
        skylight_depth_m: Depth from surface to tube ceiling.
        skylight_overhang_deg: Inward overhang of shaft walls.
        debris_cone_present: Whether debris cone at skylight base.
        debris_cone_angle_deg: Angle of repose for debris cone.
        breakdown_coverage_pct: Floor area covered by breakdown blocks.
        breakdown_block_mean_m: LogNormal mean block diameter.
        breakdown_block_sigma: LogNormal sigma for block sizes.
        floor_flat_pct: Percentage of floor that is flat.
        ring_resolution: Vertices per cross-section ring.
        path_resolution: Number of cross-sections along tube.
        domain_size: (rows, cols) in pixels.
        resolution: Meters per pixel.
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys:
            tube_mesh: trimesh.Trimesh — ceiling + walls (inward normals)
            floor_mesh: trimesh.Trimesh — tube floor (upward normals)
            surface_mesh: trimesh.Trimesh — ground surface with holes
            skylight_meshes: list[trimesh.Trimesh] — shaft wall(s)
            debris_cones: list[trimesh.Trimesh] — debris pile(s)
            breakdown_positions: list[dict] — {x, y, z, diameter}
            skylight_positions: list[tuple[float, float]] — (x, y)
            metadata: dict — bounds, dimensions, parameter summary
            surface_elevation: np.ndarray — 2D heightmap for spawn z
    """
    rng = np.random.default_rng(seed)
    rows, cols = domain_size
    domain_m = (rows * resolution, cols * resolution)

    tube_height_m = tube_width_m * tube_height_ratio
    surface_z = ceiling_thickness_m + tube_height_m
    floor_z = 0.0  # tube floor at z=0 (normalized)

    # --- 1. Centerline ---
    centerline = _generate_centerline(
        domain_m, tube_direction_deg, tube_curvature, path_resolution, floor_z, rng
    )

    # --- 2. Cross-section profiles ---
    cross_sections = _generate_cross_sections(
        centerline,
        tube_width_m,
        tube_height_ratio,
        cross_section_noise,
        ring_resolution,
        rng,
    )

    # --- 3. Tube shell (ceiling + walls) ---
    tube_mesh = _build_tube_shell(centerline, cross_sections, ring_resolution)

    # --- 4. Tube floor ---
    floor_mesh = _build_tube_floor(
        centerline,
        cross_sections,
        ring_resolution,
        floor_flat_pct,
        rng,
    )

    # --- 5. Skylight positions ---
    skylight_positions = _compute_skylight_positions(
        centerline,
        skylight_count,
        skylight_diameter_m,
        domain_m,
        rng,
    )

    # --- 6. Skylight shafts ---
    skylight_meshes = []
    for sx, sy in skylight_positions:
        shaft = _build_skylight_shaft(
            center_xy=(sx, sy),
            diameter=skylight_diameter_m,
            surface_z=surface_z,
            ceiling_z=tube_height_m,
            overhang_deg=skylight_overhang_deg,
            n_segments=max(ring_resolution // 2, 16),
        )
        skylight_meshes.append(shaft)

    # --- 7. Debris cones (random positions along tube, avoiding centerline) ---
    debris_cones = []
    if debris_cone_present and debris_cone_count > 0:
        cone_diameter = tube_width_m * 0.15  # cone base ~15% of tube width
        exclusion_half = tube_width_m * 0.1  # keep centerline clear for rover
        n_stations = len(centerline)
        station_indices = rng.choice(
            range(2, n_stations - 2), size=min(debris_cone_count, n_stations - 4), replace=False
        )
        for idx in sorted(station_indices):
            cx, cy = centerline[idx, 0], centerline[idx, 1]
            # Offset from centerline to keep passage clear
            sign = rng.choice([-1.0, 1.0])
            offset = rng.uniform(exclusion_half, tube_width_m * 0.35)
            # Perpendicular direction from tangent
            if idx < n_stations - 1:
                dx = centerline[idx + 1, 0] - centerline[idx, 0]
                dy = centerline[idx + 1, 1] - centerline[idx, 1]
            else:
                dx = centerline[idx, 0] - centerline[idx - 1, 0]
                dy = centerline[idx, 1] - centerline[idx - 1, 1]
            length = max(np.sqrt(dx**2 + dy**2), 1e-6)
            perp_x, perp_y = -dy / length, dx / length
            cone_x = cx + sign * offset * perp_x
            cone_y = cy + sign * offset * perp_y
            cone = _build_debris_cone(
                center_xy=(cone_x, cone_y),
                floor_z=floor_z,
                skylight_diameter=cone_diameter,
                angle_of_repose=debris_cone_angle_deg,
                rng=rng,
            )
            debris_cones.append(cone)

    # --- 8. Surface cap ---
    surface_mesh, surface_elevation = _build_surface_cap(
        domain_size,
        resolution,
        surface_z,
        skylight_positions,
        skylight_diameter_m,
        rng,
    )

    # --- 9. Breakdown block positions ---
    breakdown_positions = _generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z,
        ring_resolution,
        breakdown_coverage_pct,
        breakdown_block_mean_m,
        breakdown_block_sigma,
        skylight_positions,
        skylight_diameter_m,
        rng,
    )

    metadata = {
        "tube_width_m": tube_width_m,
        "tube_height_m": tube_height_m,
        "ceiling_thickness_m": ceiling_thickness_m,
        "surface_z": surface_z,
        "floor_z": floor_z,
        "domain_m": domain_m,
        "skylight_count": len(skylight_positions),
        "breakdown_count": len(breakdown_positions),
        "tube_vertices": len(tube_mesh.vertices),
        "floor_vertices": len(floor_mesh.vertices),
        "seed": seed,
    }

    return {
        "tube_mesh": tube_mesh,
        "floor_mesh": floor_mesh,
        "surface_mesh": surface_mesh,
        "skylight_meshes": skylight_meshes,
        "debris_cones": debris_cones,
        "breakdown_positions": breakdown_positions,
        "skylight_positions": skylight_positions,
        "metadata": metadata,
        "surface_elevation": surface_elevation,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_centerline(
    domain_m: tuple[float, float],
    direction_deg: float,
    curvature: float,
    n_points: int,
    floor_z: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate sinusoidal tube centerline across the domain.

    Pattern reused from procedural_generator._generate_canyon() centerline.

    Args:
        domain_m: (height_m, width_m) of the domain.
        direction_deg: Tube axis direction (0=Y, 90=X).
        curvature: Amplitude factor for sinusoidal perturbation.
        n_points: Number of stations along the path.
        floor_z: Z coordinate of the tube floor.
        rng: Numpy random generator.

    Returns:
        (n_points, 3) array of centerline positions.
    """
    height_m, width_m = domain_m
    center_x = width_m / 2.0
    center_y = height_m / 2.0

    # Generate straight path along the tube direction
    t = np.linspace(0, 1, n_points)
    dir_rad = np.radians(direction_deg)

    # Path length = domain diagonal to ensure full coverage
    path_len = max(height_m, width_m) * 1.1

    # Straight path centered at domain center
    along = (t - 0.5) * path_len  # [-half_len, +half_len]
    path_x = center_x + along * np.sin(dir_rad)
    path_y = center_y + along * np.cos(dir_rad)

    # Sinusoidal perturbation perpendicular to path
    freq1 = 2.0 * np.pi / path_len
    freq2 = freq1 * 2.3
    phase1 = rng.uniform(0, 2 * np.pi)
    phase2 = rng.uniform(0, 2 * np.pi)
    amplitude = curvature * min(height_m, width_m) * 0.15

    perturb = amplitude * np.sin(freq1 * along + phase1) + amplitude * 0.3 * np.sin(
        freq2 * along + phase2
    )

    # Perpendicular direction
    perp_x = np.cos(dir_rad)
    perp_y = -np.sin(dir_rad)

    centerline = np.zeros((n_points, 3), dtype=np.float64)
    centerline[:, 0] = path_x + perturb * perp_x
    centerline[:, 1] = path_y + perturb * perp_y
    centerline[:, 2] = floor_z

    return centerline


def _generate_cross_sections(
    centerline: np.ndarray,
    tube_width: float,
    height_ratio: float,
    noise_amp: float,
    ring_pts: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate half-ellipse cross-section profiles at each station.

    Args:
        centerline: (n_stations, 3) centerline positions.
        tube_width: Tube width in meters.
        height_ratio: Height / width ratio.
        noise_amp: ±fraction noise on radius.
        ring_pts: Number of vertices per ring (half-ellipse).
        rng: Numpy random generator.

    Returns:
        (n_stations, ring_pts, 2) array of (local_x, local_z) offsets.
        local_x is horizontal offset from center, local_z is vertical.
    """
    n_stations = len(centerline)
    a = tube_width / 2.0  # semi-major (horizontal)
    b = tube_width * height_ratio  # semi-minor (vertical = height)

    # Half-ellipse: theta from 0 to pi
    theta = np.linspace(0, np.pi, ring_pts)

    # Base profile (no noise)
    base_x = a * np.cos(theta)  # [-a, +a]
    base_z = b * np.sin(theta)  # [0, b, 0]

    # Generate smooth noise field (n_stations x ring_pts)
    raw_noise = rng.standard_normal((n_stations, ring_pts))
    # Smooth along both dimensions for continuity
    smooth_noise = gaussian_filter(raw_noise, sigma=(3.0, 2.0))
    # Normalize to unit variance then scale by noise_amp
    noise_std = np.std(smooth_noise)
    if noise_std > 1e-8:
        smooth_noise = smooth_noise / noise_std * noise_amp
    else:
        smooth_noise = np.zeros_like(smooth_noise)

    # Apply radial perturbation
    profiles = np.zeros((n_stations, ring_pts, 2), dtype=np.float64)
    for i in range(n_stations):
        scale = 1.0 + smooth_noise[i]
        profiles[i, :, 0] = base_x * scale
        profiles[i, :, 1] = base_z * scale

    return profiles


def _tangent_frames(centerline: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute tangent and perpendicular vectors along centerline.

    Returns:
        tangent: (n, 3) unit tangent vectors.
        perp: (n, 3) unit perpendicular vectors (horizontal).
    """
    n = len(centerline)
    tangent = np.zeros((n, 3), dtype=np.float64)

    # Central differences (forward/backward at ends)
    tangent[1:-1] = centerline[2:] - centerline[:-2]
    tangent[0] = centerline[1] - centerline[0]
    tangent[-1] = centerline[-1] - centerline[-2]

    # Normalize
    norms = np.linalg.norm(tangent, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    tangent = tangent / norms

    # Perpendicular in XY plane (rotate tangent 90 deg)
    perp = np.zeros_like(tangent)
    perp[:, 0] = -tangent[:, 1]
    perp[:, 1] = tangent[:, 0]
    perp[:, 2] = 0.0

    perp_norms = np.linalg.norm(perp, axis=1, keepdims=True)
    perp_norms = np.maximum(perp_norms, 1e-8)
    perp = perp / perp_norms

    return tangent, perp


def _build_tube_shell(
    centerline: np.ndarray,
    cross_sections: np.ndarray,
    ring_pts: int,
) -> trimesh.Trimesh:
    """Stitch cross-section rings into tube shell mesh (ceiling + walls).

    Normals point inward (toward tube interior) so robot cameras see
    the inner surface. Winding order is reversed compared to terrain mesh.

    Args:
        centerline: (n_stations, 3) centerline positions.
        cross_sections: (n_stations, ring_pts, 2) local (x, z) offsets.
        ring_pts: Vertices per ring.

    Returns:
        trimesh.Trimesh of the tube shell.
    """
    n_stations = len(centerline)
    _, perp = _tangent_frames(centerline)

    # Place cross-section rings in world space
    vertices = np.zeros((n_stations * ring_pts, 3), dtype=np.float64)
    for i in range(n_stations):
        cx, cy, cz = centerline[i]
        px, py, _ = perp[i]
        for j in range(ring_pts):
            local_x, local_z = cross_sections[i, j]
            # local_x → perpendicular direction, local_z → vertical
            wx = cx + local_x * px
            wy = cy + local_x * py
            wz = cz + local_z
            vertices[i * ring_pts + j] = [wx, wy, wz]

    # Stitch adjacent rings with triangles
    # Reversed winding for INWARD normals
    faces = []
    for i in range(n_stations - 1):
        for j in range(ring_pts - 1):
            v0 = i * ring_pts + j
            v1 = i * ring_pts + j + 1
            v2 = (i + 1) * ring_pts + j
            v3 = (i + 1) * ring_pts + j + 1
            # Reversed winding: [v0, v2, v1] and [v1, v2, v3]
            faces.append([v0, v2, v1])
            faces.append([v1, v2, v3])

    faces = np.array(faces, dtype=np.int32)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _build_tube_floor(
    centerline: np.ndarray,
    cross_sections: np.ndarray,
    ring_pts: int,
    flat_pct: float,
    rng: np.random.Generator,
) -> trimesh.Trimesh:
    """Build tube floor as a strip connecting bottom edges of rings.

    The floor connects the first and last vertices of each half-ellipse
    ring (which are at floor level). Normals point upward (+Z).

    Args:
        centerline: (n_stations, 3) centerline positions.
        cross_sections: (n_stations, ring_pts, 2) local offsets.
        ring_pts: Vertices per ring.
        flat_pct: Percentage of floor that is flat (rest gets noise).
        rng: Numpy random generator.

    Returns:
        trimesh.Trimesh of the floor.
    """
    n_stations = len(centerline)
    _, perp = _tangent_frames(centerline)

    # Floor uses a grid: n_stations rows x floor_width_pts columns
    floor_pts = max(ring_pts // 2, 8)

    vertices = np.zeros((n_stations * floor_pts, 3), dtype=np.float64)
    for i in range(n_stations):
        cx, cy, cz = centerline[i]
        px, py, _ = perp[i]
        # Floor spans between the two bottom endpoints of the half-ellipse
        left_x = cross_sections[i, 0, 0]  # negative (left side)
        right_x = cross_sections[i, -1, 0]  # positive (right side)
        floor_x = np.linspace(left_x, right_x, floor_pts)

        for j in range(floor_pts):
            wx = cx + floor_x[j] * px
            wy = cy + floor_x[j] * py
            wz = cz
            vertices[i * floor_pts + j] = [wx, wy, wz]

    # Add debris noise to non-flat areas
    debris_mask = rng.random(n_stations * floor_pts) > (flat_pct / 100.0)
    noise = rng.standard_normal(n_stations * floor_pts) * 0.3
    noise = gaussian_filter(noise.reshape(n_stations, floor_pts), sigma=1.5).ravel()
    vertices[debris_mask, 2] += np.abs(noise[debris_mask])

    # Faces: quad grid stitching (CCW for +Z normals)
    faces = []
    for i in range(n_stations - 1):
        for j in range(floor_pts - 1):
            v0 = i * floor_pts + j
            v1 = i * floor_pts + j + 1
            v2 = (i + 1) * floor_pts + j
            v3 = (i + 1) * floor_pts + j + 1
            # CCW for upward normals: [v0, v1, v2] and [v1, v3, v2]
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])

    faces = np.array(faces, dtype=np.int32)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _compute_skylight_positions(
    centerline: np.ndarray,
    count: int,
    diameter: float,
    domain_m: tuple[float, float],
    rng: np.random.Generator,
) -> list[tuple[float, float]]:
    """Select skylight positions along the centerline.

    Skylights are placed at evenly-spaced stations along the tube,
    ensuring they stay within the domain and don't overlap.

    Args:
        centerline: (n_stations, 3) centerline positions.
        count: Number of skylights to place.
        diameter: Skylight diameter in meters.
        domain_m: (height_m, width_m).
        rng: Numpy random generator.

    Returns:
        List of (x, y) tuples for skylight centers.
    """
    if count == 0:
        return []

    height_m, width_m = domain_m
    margin = diameter / 2.0 + 10.0  # keep skylight inside domain

    # Filter centerline to points well within domain
    valid = (
        (centerline[:, 0] > margin)
        & (centerline[:, 0] < width_m - margin)
        & (centerline[:, 1] > margin)
        & (centerline[:, 1] < height_m - margin)
    )
    valid_indices = np.where(valid)[0]

    if len(valid_indices) == 0:
        # Fallback: domain center
        return [(width_m / 2.0, height_m / 2.0)]

    positions = []
    min_dist = diameter * 1.5  # minimum separation between skylights

    # Distribute evenly along valid portion of centerline
    step = max(1, len(valid_indices) // (count + 1))
    for k in range(1, count + 1):
        idx = valid_indices[min(k * step, len(valid_indices) - 1)]
        cx, cy = float(centerline[idx, 0]), float(centerline[idx, 1])

        # Skip if too close to an existing skylight
        too_close = False
        for px, py in positions:
            if (cx - px) ** 2 + (cy - py) ** 2 < min_dist**2:
                too_close = True
                break
        if not too_close:
            positions.append((cx, cy))

    return positions


def _build_skylight_shaft(
    center_xy: tuple[float, float],
    diameter: float,
    surface_z: float,
    ceiling_z: float,
    overhang_deg: float,
    n_segments: int,
) -> trimesh.Trimesh:
    """Generate vertical/overhanging skylight shaft mesh.

    The shaft connects the surface to the tube ceiling. For overhang > 0,
    the radius increases with depth (wall leans inward).

    Args:
        center_xy: (x, y) center of the skylight.
        diameter: Opening diameter at surface.
        surface_z: Z coordinate of ground surface.
        ceiling_z: Z coordinate of tube ceiling (top of tube).
        overhang_deg: Inward overhang angle (0=vertical, >0=overhanging).
        n_segments: Vertices per ring.

    Returns:
        trimesh.Trimesh of the shaft walls (inward normals).
    """
    cx, cy = center_xy
    r_surface = diameter / 2.0
    overhang_rad = np.radians(overhang_deg)

    # Shaft from surface_z down to ceiling_z
    n_rings = max(10, int((surface_z - ceiling_z) / 5.0))
    z_levels = np.linspace(surface_z, ceiling_z, n_rings)

    theta = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)

    vertices = np.zeros((n_rings * n_segments, 3), dtype=np.float64)
    for i, z in enumerate(z_levels):
        depth = surface_z - z
        # Radius increases with depth for overhang
        r = r_surface + depth * np.tan(overhang_rad)
        for j in range(n_segments):
            vertices[i * n_segments + j] = [
                cx + r * np.cos(theta[j]),
                cy + r * np.sin(theta[j]),
                z,
            ]

    # Stitch rings (inward normals → reversed winding)
    faces = []
    for i in range(n_rings - 1):
        for j in range(n_segments):
            j_next = (j + 1) % n_segments
            v0 = i * n_segments + j
            v1 = i * n_segments + j_next
            v2 = (i + 1) * n_segments + j
            v3 = (i + 1) * n_segments + j_next
            # Reversed for inward normals
            faces.append([v0, v2, v1])
            faces.append([v1, v2, v3])

    faces = np.array(faces, dtype=np.int32)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _build_debris_cone(
    center_xy: tuple[float, float],
    floor_z: float,
    skylight_diameter: float,
    angle_of_repose: float,
    rng: np.random.Generator,
) -> trimesh.Trimesh:
    """Generate a conical debris pile beneath a skylight.

    Args:
        center_xy: (x, y) center.
        floor_z: Z coordinate of the tube floor.
        skylight_diameter: Diameter of the skylight above.
        angle_of_repose: Slope angle in degrees (~30 for Mars regolith).
        rng: Numpy random generator.

    Returns:
        trimesh.Trimesh of the debris cone.
    """
    cx, cy = center_xy
    base_radius = skylight_diameter / 2.0 * 0.8  # slightly smaller than skylight
    cone_height = base_radius * np.tan(np.radians(angle_of_repose))

    # Parametric cone: rings from apex (top) to base (bottom)
    n_rings = 12
    n_segments = 24
    theta = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)

    vertices = []
    # Apex at (cx, cy, floor_z + cone_height)
    apex_z = floor_z + cone_height

    for i in range(n_rings):
        t = i / (n_rings - 1)  # 0=apex, 1=base
        z = apex_z - t * cone_height
        r = t * base_radius
        # Add noise for natural look
        r_noise = 1.0 + rng.standard_normal(n_segments) * 0.05
        for j in range(n_segments):
            vertices.append(
                [
                    cx + r * r_noise[j] * np.cos(theta[j]),
                    cy + r * r_noise[j] * np.sin(theta[j]),
                    z,
                ]
            )

    vertices = np.array(vertices, dtype=np.float64)

    # Stitch rings (outward normals → CCW)
    faces = []
    for i in range(n_rings - 1):
        for j in range(n_segments):
            j_next = (j + 1) % n_segments
            v0 = i * n_segments + j
            v1 = i * n_segments + j_next
            v2 = (i + 1) * n_segments + j
            v3 = (i + 1) * n_segments + j_next
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])

    faces = np.array(faces, dtype=np.int32)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _build_surface_cap(
    domain_size: tuple[int, int],
    resolution: float,
    surface_z: float,
    skylight_positions: list[tuple[float, float]],
    skylight_diameter: float,
    rng: np.random.Generator,
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """Generate flat surface terrain with skylight holes.

    Uses the same noise pattern as procedural_generator._generate_flat().

    Args:
        domain_size: (rows, cols) in pixels.
        resolution: Meters per pixel.
        surface_z: Z coordinate of the surface.
        skylight_positions: List of (x, y) skylight centers.
        skylight_diameter: Diameter of each skylight.
        rng: Numpy random generator.

    Returns:
        Tuple of (surface_mesh, surface_elevation_2d).
        surface_elevation_2d is (rows, cols) float32 for spawn z.
    """
    rows, cols = domain_size

    # Generate flat terrain noise
    noise = rng.standard_normal((rows, cols))
    smooth_noise = gaussian_filter(noise, sigma=10.0)
    smooth_noise = smooth_noise / (np.std(smooth_noise) + 1e-8) * 2.0
    elevation_2d = (surface_z + smooth_noise).astype(np.float32)

    # Build vertex grid
    n_verts = rows * cols
    col_idx = np.arange(cols, dtype=np.float64)
    row_idx = np.arange(rows, dtype=np.float64)
    col_grid, row_grid = np.meshgrid(col_idx, row_idx)

    vertices = np.zeros((n_verts, 3), dtype=np.float64)
    vertices[:, 0] = (col_grid * resolution).ravel()
    vertices[:, 1] = (row_grid * resolution).ravel()
    vertices[:, 2] = elevation_2d.ravel()

    # Build faces (CCW for +Z normals)
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

    # Remove faces inside skylight openings
    if skylight_positions:
        skylight_r = skylight_diameter / 2.0
        # Compute face centroids
        face_centroids = vertices[faces].mean(axis=1)  # (n_faces, 3)
        keep = np.ones(len(faces), dtype=bool)
        for sx, sy in skylight_positions:
            dx = face_centroids[:, 0] - sx
            dy = face_centroids[:, 1] - sy
            dist = np.sqrt(dx**2 + dy**2)
            keep &= dist > skylight_r
        faces = faces[keep]

        # Also cut elevation to NaN inside skylights (for spawn z)
        for sx, sy in skylight_positions:
            for r in range(rows):
                for c in range(cols):
                    x = c * resolution
                    y = r * resolution
                    if (x - sx) ** 2 + (y - sy) ** 2 < skylight_r**2:
                        elevation_2d[r, c] = np.nan

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return mesh, elevation_2d


def _generate_breakdown_positions(
    centerline: np.ndarray,
    cross_sections: np.ndarray,
    floor_z: float,
    ring_pts: int,
    coverage_pct: float,
    block_mean: float,
    block_sigma: float,
    skylight_positions: list[tuple[float, float]],
    skylight_diameter: float,
    rng: np.random.Generator,
) -> list[dict]:
    """Generate breakdown block positions on the cave floor.

    Uses lognormal size distribution (Blank 2024 / BRAILLE).
    Blocks are scattered across the floor with rejection sampling
    to stay within the tube footprint.

    Args:
        centerline: (n_stations, 3).
        cross_sections: (n_stations, ring_pts, 2) local offsets.
        floor_z: Z of the floor.
        ring_pts: Vertices per ring.
        coverage_pct: Target floor area coverage.
        block_mean: LogNormal mean diameter.
        block_sigma: LogNormal sigma.
        skylight_positions: Skylight centers (avoid debris cone area).
        skylight_diameter: Diameter of skylights.
        rng: Numpy random generator.

    Returns:
        List of dicts: {x, y, z, diameter}.
    """
    if coverage_pct <= 0:
        return []

    # Estimate tube floor area
    _, perp = _tangent_frames(centerline)
    n_stations = len(centerline)
    total_area = 0.0
    widths = np.zeros(n_stations)
    for i in range(n_stations):
        left_x = cross_sections[i, 0, 0]
        right_x = cross_sections[i, -1, 0]
        widths[i] = abs(right_x - left_x)

    if n_stations > 1:
        segment_lens = np.linalg.norm(centerline[1:, :2] - centerline[:-1, :2], axis=1)
        avg_widths = (widths[:-1] + widths[1:]) / 2.0
        total_area = float(np.sum(segment_lens * avg_widths))
    else:
        total_area = widths[0] * 10.0

    target_area = total_area * (coverage_pct / 100.0)

    # Generate blocks until area coverage is met
    blocks = []
    placed_area = 0.0
    max_attempts = 5000

    for _ in range(max_attempts):
        if placed_area >= target_area:
            break

        diameter = float(
            rng.lognormal(
                mean=np.log(block_mean),
                sigma=block_sigma,
            )
        )
        diameter = min(diameter, 5.0)  # cap at 5m

        # Pick a random station along centerline
        station_idx = rng.integers(0, n_stations)
        cx, cy, cz = centerline[station_idx]
        px, py, _ = perp[station_idx]

        # Random position within floor width (left_x < 0, right_x > 0)
        left_x = cross_sections[station_idx, 0, 0]
        right_x = cross_sections[station_idx, -1, 0]
        lo = min(left_x, right_x) * 0.8
        hi = max(left_x, right_x) * 0.8
        local_x = rng.uniform(lo, hi)

        bx = cx + local_x * px
        by = cy + local_x * py
        bz = floor_z

        # Avoid skylight areas
        skip = False
        for sx, sy in skylight_positions:
            if (bx - sx) ** 2 + (by - sy) ** 2 < (skylight_diameter / 2.0) ** 2:
                skip = True
                break
        if skip:
            continue

        # Centerline exclusion zone: keep rover passage clear
        if abs(local_x) < widths[station_idx] * 0.1:
            continue

        blocks.append({"x": float(bx), "y": float(by), "z": float(bz), "diameter": diameter})
        placed_area += np.pi * (diameter / 2.0) ** 2

    return blocks
