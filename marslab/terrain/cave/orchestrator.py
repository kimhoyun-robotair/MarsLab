"""Procedural Mars lava tube cave mesh orchestrator (thin).

Generates a 3D cave mesh assembly (tube shell, floor, skylight shaft,
surface cap) for Isaac Sim rendering and PhysX collision. Caves cannot
be represented as 2D heightmaps because the ceiling introduces a
second z-value at each (x, y) position.

Science basis: Sauro et al. 2020, Cushing 2007/2012, Theinat 2020,
Blair 2017, Blank 2024 (BRAILLE). Full references in
``work_log/scene_generation/mars_cave.md``.

Design follows P3 (Offline-First Testing):

    Layer 1 (this module): pure numpy + trimesh, no Isaac Sim.
    Layer 2 (``marslab.terrain.cave.usd_builder``): USD prim creation, separate file.

Architecture -- cross-section sweep (ring stacking):

    1. Generate sinusoidal centerline along tube axis
       (:mod:`marslab.terrain.cave.geometry`).
    2. At each station, place a half-ellipse cross-section ring
       (:mod:`marslab.terrain.cave.geometry`).
    3. Stitch adjacent rings into triangle strips for the tube shell
       and floor (:mod:`marslab.terrain.cave.mesh`).
    4. Add skylight shafts and optional debris cones
       (:mod:`marslab.terrain.cave.features` +
       :mod:`marslab.terrain.cave.mesh`).
    5. Add a surface terrain cap with skylight holes
       (:mod:`marslab.terrain.cave.mesh`).
    6. Generate breakdown block positions for the PointInstancer
       (:mod:`marslab.terrain.cave.breakdown`).

R5 (2026-04-23) split the original 884-LOC module into four
submodules plus this orchestrator; the public API -- the single
:func:`generate_cave_mesh` entry point -- is byte-identical to the
pre-split version and the shared RNG is consumed in the same order.
"""

from __future__ import annotations

import numpy as np

from marslab.terrain.cave._constants import (
    DEBRIS_CONE_DIAMETER_RATIO,
    DEBRIS_CONE_EXCLUSION_RATIO,
    DEBRIS_CONE_MAX_OFFSET_RATIO,
    SKYLIGHT_SHAFT_SEG_MIN,
)
from marslab.terrain.cave.breakdown import generate_breakdown_positions
from marslab.terrain.cave.features import (
    build_debris_cone,
    compute_skylight_positions,
)
from marslab.terrain.cave.geometry import (
    build_centerline,
    build_cross_sections,
)
from marslab.terrain.cave.mesh import (
    build_skylight_shaft,
    build_surface_cap,
    build_tube_floor,
    build_tube_shell,
)


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
        cross_section_noise: +/- fraction noise on cross-section radius.
        tube_direction_deg: Tube axis direction (0 = Y, 90 = X).
        tube_curvature: Sinusoidal curvature amplitude factor.
        ceiling_thickness_m: Rock above tube crown.
        skylight_count: Number of skylights (0-20).
        skylight_diameter_m: Skylight opening diameter.
        skylight_depth_m: Depth from surface to tube ceiling.
        skylight_overhang_deg: Inward overhang of shaft walls.
        debris_cone_present: Whether debris cones spawn inside the tube.
        debris_cone_count: Number of debris cones.
        debris_cone_angle_deg: Angle of repose for the debris cone.
        breakdown_coverage_pct: Floor area covered by breakdown blocks.
        breakdown_block_mean_m: Arithmetic mean block diameter in
            meters (Blank 2024: 0.5 m). The underlying lognormal is
            mean-corrected so ``E[diameter] == breakdown_block_mean_m``.
        breakdown_block_sigma: Standard deviation of the underlying
            normal distribution used by ``rng.lognormal``.
        floor_flat_pct: Percentage of floor that is flat.
        ring_resolution: Vertices per cross-section ring.
        path_resolution: Number of cross-sections along the tube.
        domain_size: ``(rows, cols)`` in pixels.
        resolution: Meters per pixel.
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys
            ``tube_mesh``: trimesh.Trimesh -- ceiling + walls (inward normals).
            ``floor_mesh``: trimesh.Trimesh -- tube floor (+Z normals).
            ``surface_mesh``: trimesh.Trimesh -- ground surface with holes.
            ``skylight_meshes``: list[trimesh.Trimesh] -- shaft walls.
            ``debris_cones``: list[trimesh.Trimesh] -- debris piles.
            ``breakdown_positions``: list[dict] -- ``{x, y, z, diameter}``.
            ``skylight_positions``: list[tuple[float, float]] -- ``(x, y)``.
            ``metadata``: dict -- bounds, dimensions, parameter summary.
            ``surface_elevation``: np.ndarray -- 2D heightmap for spawn z.
    """
    rng = np.random.default_rng(seed)
    rows, cols = domain_size
    domain_m = (rows * resolution, cols * resolution)

    tube_height_m = tube_width_m * tube_height_ratio
    surface_z = ceiling_thickness_m + tube_height_m
    floor_z = 0.0  # tube floor at z=0 (normalized)

    # --- 1. Centerline ---
    centerline = build_centerline(
        domain_m, tube_direction_deg, tube_curvature, path_resolution, floor_z, rng
    )

    # --- 2. Cross-section profiles ---
    cross_sections = build_cross_sections(
        centerline,
        tube_width_m,
        tube_height_ratio,
        cross_section_noise,
        ring_resolution,
        rng,
    )

    # --- 3. Tube shell (ceiling + walls) ---
    tube_mesh = build_tube_shell(centerline, cross_sections, ring_resolution)

    # --- 4. Tube floor ---
    floor_mesh = build_tube_floor(
        centerline,
        cross_sections,
        ring_resolution,
        floor_flat_pct,
        rng,
    )

    # --- 5. Skylight positions ---
    skylight_positions = compute_skylight_positions(
        centerline,
        skylight_count,
        skylight_diameter_m,
        domain_m,
        rng,
    )

    # --- 6. Skylight shafts ---
    skylight_meshes = []
    for sx, sy in skylight_positions:
        shaft = build_skylight_shaft(
            center_xy=(sx, sy),
            diameter=skylight_diameter_m,
            surface_z=surface_z,
            ceiling_z=tube_height_m,
            overhang_deg=skylight_overhang_deg,
            n_segments=max(ring_resolution // 2, SKYLIGHT_SHAFT_SEG_MIN),
        )
        skylight_meshes.append(shaft)

    # --- 7. Debris cones (random positions along tube, avoiding centerline) ---
    debris_cones = []
    if debris_cone_present and debris_cone_count > 0:
        cone_diameter = tube_width_m * DEBRIS_CONE_DIAMETER_RATIO
        exclusion_half = tube_width_m * DEBRIS_CONE_EXCLUSION_RATIO
        n_stations = len(centerline)
        station_indices = rng.choice(
            range(2, n_stations - 2),
            size=min(debris_cone_count, n_stations - 4),
            replace=False,
        )
        for idx in sorted(station_indices):
            cx, cy = centerline[idx, 0], centerline[idx, 1]
            sign = rng.choice([-1.0, 1.0])
            offset = rng.uniform(exclusion_half, tube_width_m * DEBRIS_CONE_MAX_OFFSET_RATIO)
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
            cone = build_debris_cone(
                center_xy=(cone_x, cone_y),
                floor_z=floor_z,
                skylight_diameter=cone_diameter,
                angle_of_repose=debris_cone_angle_deg,
                rng=rng,
            )
            debris_cones.append(cone)

    # --- 8. Surface cap ---
    surface_mesh, surface_elevation = build_surface_cap(
        domain_size,
        resolution,
        surface_z,
        skylight_positions,
        skylight_diameter_m,
        rng,
    )

    # --- 9. Breakdown block positions ---
    breakdown_positions = generate_breakdown_positions(
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
