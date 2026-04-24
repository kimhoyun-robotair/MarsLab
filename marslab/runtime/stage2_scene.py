"""Stage 2 scene construction (Isaac Sim-dependent).

Consumes a :class:`StageTwoBootResult` and populates the live USD stage with
a Mars world: physics gravity, terrain/cave mesh + materials, optional
Golombek rock field, and the static sun/sky/fog atmosphere. Isaac Sim imports
are lazy so unit tests can assert on signatures without a live Kit app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from marslab.runtime.stage2_boot import StageTwoBootResult


@dataclass
class StageTwoScene:
    """Runtime handles returned by :func:`setup_stage2_scene`.

    Attributes:
        world: The live Isaac Sim ``World`` instance.
        stage: The active USD stage.
        norm_elevation: Normalised elevation grid consumed by rock
            placement (shifted so min == 0). Shape matches
            :attr:`StageTwoBootResult.elevation`.
        render_config: Validated :class:`RenderingConfig` reused by the
            loop when it calls ``update_sun_light`` / ``update_sky_dome``.
        is_cave: Whether the scenario used the cave 3D-mesh pipeline.
    """

    world: Any
    stage: Any
    norm_elevation: np.ndarray
    render_config: Any
    is_cave: bool


def setup_stage2_scene(boot: StageTwoBootResult) -> StageTwoScene:
    """Build the Stage 2 USD scene on an already-booted Isaac Sim app.

    Assumes :func:`marslab.runtime.stage2_boot.run_stage2_boot` has
    produced ``boot`` and that the caller has instantiated
    ``SimulationApp`` already (Kit must be alive before any ``omni.*``
    import resolves).

    Args:
        boot: Pre-computed config + terrain + atmosphere snapshot from
            :func:`run_stage2_boot`.

    Returns:
        :class:`StageTwoScene` with the World / stage / render_config
        handles the loop module needs.
    """
    from marslab.config.schema import RenderingConfig
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog
    from marslab.rendering.render_settings import set_render_mode
    from marslab.rendering.sky_renderer import configure_sky_dome
    from marslab.rendering.sun_renderer import configure_sun_light
    from marslab.sim.world_setup import create_world

    mars_cfg = boot.mars_cfg
    terrain_cfg = boot.terrain_cfg
    rendering_cfg = boot.rendering_cfg
    atmo = boot.atmosphere_init

    # --- Physics world (Mars gravity + solver iterations from config) --------
    # 2026-04-24: route World creation through :func:`create_world` so Stage 2
    # and Stage 3 share a single physics setup path (16/4 solver iterations
    # needed for the 29-DOF rover articulation; harmless for Stage-2-only
    # scenes).  Gravity + physics_dt still come from the pydantic-validated
    # MarsEnvConfig via ``boot.atmosphere_init`` / ``boot.mars_cfg``.
    from marslab.config.schema import MarsEnvConfig

    mars_env_model = MarsEnvConfig(**mars_cfg)
    physics_dt = atmo.physics_dt
    gravity = mars_env_model.gravity
    world, stage = create_world(physics_dt=physics_dt, gravity=gravity)
    print(f"[run_stage2] Gravity: {gravity} m/s^2", flush=True)

    # --- Build terrain / cave mesh ------------------------------------------
    is_cave = terrain_cfg.get("procedural_preset") == "cave"
    if is_cave:
        norm_elevation = _build_cave_scene(stage, boot)
    else:
        norm_elevation = _build_heightmap_scene(stage, boot)

    # --- Rock placement (Golombek SFD) --------------------------------------
    _place_rocks_if_enabled(stage, boot, norm_elevation)

    # --- Configure atmosphere rendering -------------------------------------
    render_config = RenderingConfig(**rendering_cfg)
    set_render_mode(render_config)
    configure_sun_light(
        stage,
        atmo.sun_pos,
        atmo.direct_intensity,
        atmo.diffuse_fraction,
        render_config,
    )
    configure_sky_dome(stage, atmo.sky_params, atmo.diffuse_fraction, render_config)
    configure_atmosphere_fog(stage, atmo.tau, render_config)
    print("[run_stage2] Atmosphere configured (sun + sky + fog).", flush=True)

    return StageTwoScene(
        world=world,
        stage=stage,
        norm_elevation=norm_elevation,
        render_config=render_config,
        is_cave=is_cave,
    )


def _build_cave_scene(stage: Any, boot: StageTwoBootResult) -> np.ndarray:
    """Build the cave 3D-mesh scene and apply per-prim materials."""
    from marslab.terrain.cave_mesh_builder import build_cave_scene
    from marslab.terrain.material_applicator import apply_cave_material, apply_terrain_material

    terrain_cfg = boot.terrain_cfg
    mars_cfg = boot.mars_cfg

    cave_data = terrain_cfg["_cave_data"]
    norm_elevation = build_cave_scene(cave_data, stage)
    print(
        f"[run_stage2] Cave scene built: "
        f"tube={len(cave_data['tube_mesh'].vertices)} verts, "
        f"skylights={len(cave_data['skylight_positions'])}, "
        f"breakdown={len(cave_data['breakdown_positions'])} blocks",
        flush=True,
    )

    cave_cfg = terrain_cfg.get("cave", {})
    cave_albedo = tuple(cave_cfg.get("wall_albedo_range", [0.05, 0.15]))
    cave_seed = int(terrain_cfg.get("seed", 42))
    apply_cave_material(stage, "/World/Cave/Tube", cave_albedo, cave_seed)
    apply_cave_material(stage, "/World/Cave/Floor", cave_albedo, cave_seed + 1)
    for i in range(len(cave_data["skylight_meshes"])):
        apply_cave_material(
            stage,
            f"/World/Cave/Skylight_{i}",
            cave_albedo,
            cave_seed + 2 + i,
        )

    surface_albedo = tuple(mars_cfg.get("surface_albedo_range", [0.10, 0.40]))
    texture_dir_path = boot.dem_paths.get("texture_dir")
    texture_dir = str(texture_dir_path) if texture_dir_path is not None else None
    apply_terrain_material(
        stage,
        "/World/Cave/Surface",
        albedo_range=surface_albedo,
        seed=cave_seed,
        texture_dir=texture_dir,
    )
    print("[run_stage2] Cave materials applied.", flush=True)
    return norm_elevation


def _build_heightmap_scene(stage: Any, boot: StageTwoBootResult) -> np.ndarray:
    """Build the standard heightmap-based terrain + PBR material."""
    from marslab.terrain.material_applicator import apply_terrain_material
    from marslab.terrain.mesh_builder import build_terrain_mesh

    terrain_cfg = boot.terrain_cfg
    mars_cfg = boot.mars_cfg

    uv_scale = float(terrain_cfg.get("uv_scale", 1.0))
    terrain_prim_path = "/World/Terrain"
    norm_elevation = build_terrain_mesh(
        boot.elevation,
        boot.resolution,
        stage,
        terrain_prim_path,
        uv_scale,
    )
    print(
        f"[run_stage2] Terrain mesh: {terrain_prim_path}, "
        f"normalized z=[{norm_elevation.min():.2f}, {norm_elevation.max():.2f}]",
        flush=True,
    )

    albedo_range = tuple(mars_cfg.get("surface_albedo_range", [0.10, 0.40]))
    texture_dir_path = boot.dem_paths.get("texture_dir")
    texture_dir = str(texture_dir_path) if texture_dir_path is not None else None
    apply_terrain_material(
        stage,
        terrain_prim_path,
        albedo_range=albedo_range,
        seed=int(terrain_cfg.get("seed", 42)),
        texture_dir=texture_dir,
    )
    print("[run_stage2] Terrain material applied.", flush=True)
    return norm_elevation


def _place_rocks_if_enabled(
    stage: Any,
    boot: StageTwoBootResult,
    norm_elevation: np.ndarray,
) -> None:
    """Sample Golombek SFD rocks and scatter them on the terrain."""
    terrain_cfg = boot.terrain_cfg

    rock_k = float(terrain_cfg.get("rock_sfd_k", 0))
    if rock_k <= 0:
        print("[run_stage2] Rock placement skipped (rock_sfd_k=0).", flush=True)
        return

    from marslab.terrain.rock_instancer import place_rocks_on_terrain
    from marslab.terrain.rock_placer import sample_rocks_golombek

    d_range = tuple(terrain_cfg.get("rock_diameter_range", [0.20, 3.0]))
    area_m2 = float(
        norm_elevation.shape[0] * boot.resolution * norm_elevation.shape[1] * boot.resolution
    )
    rocks = sample_rocks_golombek(
        area_m2=area_m2,
        k=rock_k,
        diameter_range=d_range,
        seed=int(terrain_cfg.get("seed", 42)),
    )
    rock_mesh_dir_path = boot.dem_paths.get("rock_mesh_dir")
    rock_mesh_dir = str(rock_mesh_dir_path) if rock_mesh_dir_path is not None else None
    rock_texture_dir_path = boot.dem_paths.get("rock_texture_dir")
    rock_texture_dir = str(rock_texture_dir_path) if rock_texture_dir_path is not None else None
    place_rocks_on_terrain(
        stage=stage,
        rocks=rocks,
        elevation=norm_elevation,
        resolution=boot.resolution,
        seed=int(terrain_cfg.get("seed", 42)),
        rock_color=tuple(terrain_cfg.get("rock_color", [0.42, 0.28, 0.20])),
        rock_roughness=float(terrain_cfg.get("rock_roughness", 0.92)),
        rock_mesh_dir=rock_mesh_dir,
        rock_texture_dir=rock_texture_dir,
    )
    print(f"[run_stage2] Placed {len(rocks)} rocks (k={rock_k}).", flush=True)


__all__ = ["StageTwoScene", "setup_stage2_scene"]
