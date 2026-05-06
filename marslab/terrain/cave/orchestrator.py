"""Procedural Mars lava tube cave mesh orchestrator (thin).

Generates a 3D cave mesh assembly (tube shell, floor, skylight shaft,
surface cap) for Isaac Sim rendering and PhysX collision. Caves cannot
be represented as 2D heightmaps because the ceiling introduces a
second z-value at each (x, y) position.

Science basis: Sauro et al. (2020, Earth-Science Reviews 209, 103288),
Cushing et al. (2007, GRL 34, L17201; 2012, JGR Planets 117, E03007),
Theinat et al. (2020, Acta Astronautica 170, 480-491),
Blair et al. (2017, Icarus 282, 300-317),
Blank et al. (2024, BRAILLE program reports).

Design is offline-first: pure numpy + trimesh in this layer, no Isaac
Sim. USD prim creation lives in
:mod:`marslab.terrain.cave.usd_builder`.

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
"""

from __future__ import annotations

import numpy as np

from marslab.config.schema.terrain import CaveConfig
from marslab.terrain.cave._constants import (
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


def generate_cave_mesh(seed: int, cfg: CaveConfig) -> dict:
    """Generate a complete Mars lava tube cave mesh assembly.

    All geometry is generated offline (no Isaac Sim). Returns a dict
    of trimesh objects and metadata for subsequent USD conversion.

    Args:
        seed: Random seed for reproducibility.
        cfg: Validated :class:`CaveConfig` carrying every cave geometry
            parameter (tube geometry, skylight layout, debris/breakdown
            statistics, domain size, and resolution). Construct via
            :class:`CaveConfig` directly or load from YAML through
            :class:`marslab.config.schema.TerrainConfig`.

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
    rows, cols = cfg.domain_size
    resolution = cfg.resolution
    domain_m = (rows * resolution, cols * resolution)
    geom = cfg.geometry

    tube_width_m = cfg.tube_width_m
    tube_height_ratio = cfg.tube_height_ratio
    tube_height_m = tube_width_m * tube_height_ratio
    floor_z = 0.0  # tube floor at z=0 (normalized)
    skylight_depth_m = cfg.skylight_depth_m
    skylight_diameter_m = cfg.skylight_diameter_m
    # ``skylight_depth_m`` controls the actual shaft length: surface
    # sits ``skylight_depth_m`` above the tube ceiling. ``ceiling_thickness_m``
    # is retained in metadata for downstream tooling that asks for the
    # rock thickness above the tube crown for areas without a skylight.
    surface_z = floor_z + tube_height_m + skylight_depth_m

    ring_resolution = cfg.ring_resolution

    # --- 1. Centerline ---
    centerline = build_centerline(
        domain_m,
        cfg.tube_direction_deg,
        cfg.tube_curvature,
        cfg.path_resolution,
        floor_z,
        rng,
        path_length_factor=geom.centerline_path_length_factor,
        freq_ratio_secondary=geom.centerline_freq_ratio_secondary,
        secondary_amp_ratio=geom.centerline_secondary_amp_ratio,
        amp_domain_ratio=geom.centerline_amp_domain_ratio,
    )

    # --- 2. Cross-section profiles ---
    cross_sections = build_cross_sections(
        centerline,
        tube_width_m,
        tube_height_ratio,
        cfg.cross_section_noise,
        ring_resolution,
        rng,
        smooth_sigma=geom.cross_section_smooth_sigma,
    )

    # --- 3. Tube shell (ceiling + walls) ---
    tube_mesh = build_tube_shell(centerline, cross_sections, ring_resolution)

    # --- 4. Tube floor ---
    floor_mesh = build_tube_floor(
        centerline,
        cross_sections,
        ring_resolution,
        cfg.floor_flat_pct,
        rng,
        debris_height_scale=geom.floor_debris_height_scale,
    )

    # --- 5. Skylight positions ---
    skylight_positions = compute_skylight_positions(
        centerline,
        cfg.skylight_count,
        skylight_diameter_m,
        domain_m,
    )

    # --- 6. Skylight shafts ---
    # Shaft spans from ``surface_z`` down to the tube ceiling. With
    # ``surface_z = floor_z + tube_height_m + skylight_depth_m`` and
    # ``floor_z = 0``, ``surface_z - skylight_depth_m`` reduces to
    # ``tube_height_m`` -- the geometric tube ceiling level.
    skylight_meshes = []
    for sx, sy in skylight_positions:
        shaft = build_skylight_shaft(
            center_xy=(sx, sy),
            diameter=skylight_diameter_m,
            surface_z=surface_z,
            ceiling_z=surface_z - skylight_depth_m,
            overhang_deg=cfg.skylight_overhang_deg,
            n_segments=max(ring_resolution // 2, SKYLIGHT_SHAFT_SEG_MIN),
        )
        skylight_meshes.append(shaft)

    # --- 7. Debris cones (random positions along tube, avoiding centerline) ---
    debris_cones = []
    if cfg.debris_cone_present and cfg.debris_cone_count > 0:
        cone_diameter = tube_width_m * geom.debris_cone_diameter_ratio
        exclusion_half = tube_width_m * DEBRIS_CONE_EXCLUSION_RATIO
        n_stations = len(centerline)
        station_indices = rng.choice(
            range(2, n_stations - 2),
            size=min(cfg.debris_cone_count, n_stations - 4),
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
                angle_of_repose=cfg.debris_cone_angle_deg,
                rng=rng,
            )
            debris_cones.append(cone)

    # --- 8. Surface cap ---
    surface_mesh, surface_elevation = build_surface_cap(
        (rows, cols),
        resolution,
        surface_z,
        skylight_positions,
        skylight_diameter_m,
        rng,
        noise_sigma=geom.surface_noise_sigma,
        noise_amplitude_m=geom.surface_noise_amplitude_m,
    )

    # --- 9. Breakdown block positions ---
    breakdown_positions = generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z,
        cfg.breakdown_coverage_pct,
        cfg.breakdown_block_mean_m,
        cfg.breakdown_block_sigma,
        skylight_positions,
        skylight_diameter_m,
        rng,
    )

    metadata = {
        "tube_width_m": tube_width_m,
        "tube_height_m": tube_height_m,
        "ceiling_thickness_m": cfg.ceiling_thickness_m,
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
