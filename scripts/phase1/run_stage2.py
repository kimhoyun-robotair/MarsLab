"""Phase 1 Stage 2 runtime: Mars terrain + atmosphere viewer.

Renders a DEM-based (or procedural) terrain mesh with Mars PBR materials
and atmosphere (sun, sky dome, fog). No rover, no ROS2, no rocks.

The GUI runs indefinitely so the user can freely navigate the scene.
Press Ctrl+C to exit.

Data flow (P2 Unidirectional):
    Config YAML → terrain elevation (offline) → atmosphere params (offline)
    → Isaac Sim launch → World (Mars gravity) → build_terrain_mesh (USD)
    → apply_terrain_material (PBR) → sun/sky/fog → infinite render loop

Usage:
    scripts/isaac_python.sh scripts/phase1/run_stage2.py \\
        --config configs/mars_env.yaml
"""

import argparse
import os
import sys
from typing import Any, Dict

import numpy as np
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "configs", "mars_env.yaml")

# Add repo root to path so marslab package is importable.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def load_stage2_config(config_path: str) -> Dict[str, Any]:
    """Load and validate a Stage 2 YAML config.

    Accepts either ``mars_env.yaml`` format (with mars_env/terrain/rendering
    top-level keys) or a standalone scenario YAML with the same structure.

    Args:
        config_path: Path to YAML config file.

    Returns:
        Parsed config dict.

    Raises:
        FileNotFoundError: If config file is missing.
        ValueError: If required sections are absent.
    """
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        raise ValueError(f"Config root must be a mapping, got {type(cfg).__name__}")

    for key in ("mars_env", "terrain", "rendering"):
        if key not in cfg:
            raise ValueError(f"Config missing required section: '{key}'")

    return cfg


def load_terrain_elevation(
    terrain_cfg: Dict[str, Any],
) -> tuple[np.ndarray, dict, float]:
    """Load terrain elevation from config (procedural or HiRISE DEM).

    Args:
        terrain_cfg: The ``terrain`` section of the config.

    Returns:
        Tuple of (elevation, metadata, resolution).

    Raises:
        ValueError: If terrain source is unknown or misconfigured.
    """
    source = terrain_cfg.get("source", "procedural")
    resolution = float(terrain_cfg.get("terrain_resolution", 1.0))

    if source == "procedural":
        from marslab.terrain.procedural_generator import generate_terrain

        preset = terrain_cfg.get("procedural_preset", "flat")
        size = tuple(terrain_cfg.get("terrain_size", [256, 256]))
        seed = int(terrain_cfg.get("seed", 42))
        elevation, metadata = generate_terrain(preset, size, resolution, seed)

    elif source == "hirise":
        from marslab.terrain.dem_loader import crop_dem, load_converted_dem

        converted_dir = terrain_cfg.get("converted_dem_dir")
        if converted_dir is None:
            raise ValueError("terrain.converted_dem_dir required for source='hirise'")

        dem_dir = os.path.join(REPO_ROOT, converted_dir)
        elevation, metadata = load_converted_dem(dem_dir)
        resolution = float(metadata.get("resolution_x", resolution))

        # Apply optional crop
        crop = terrain_cfg.get("dem_crop")
        if crop is not None:
            elevation, metadata = crop_dem(
                elevation,
                metadata,
                row=int(crop["row"]),
                col=int(crop["col"]),
                height=int(crop["height"]),
                width=int(crop["width"]),
            )
    else:
        raise ValueError(f"Unknown terrain source: '{source}'")

    return elevation, metadata, resolution


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Path to Stage 2 YAML config (default: configs/mars_env.yaml)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Isaac Sim without the GUI.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    config_path = os.path.abspath(args.config)
    cfg = load_stage2_config(config_path)
    print(f"[run_stage2] Loaded config: {config_path}", flush=True)

    mars_cfg = cfg["mars_env"]
    terrain_cfg = cfg["terrain"]
    rendering_cfg = cfg["rendering"]

    # --- Load terrain elevation (offline, no Isaac Sim) ---------------------
    elevation, metadata, resolution = load_terrain_elevation(terrain_cfg)
    print(
        f"[run_stage2] Terrain: {elevation.shape} @ {resolution} m/px, "
        f"z=[{elevation.min():.1f}, {elevation.max():.1f}] m",
        flush=True,
    )

    # --- Compute atmosphere parameters (offline) ----------------------------
    from marslab.environment.diffuse_fraction import compute_diffuse_fraction
    from marslab.environment.light_intensity import compute_direct_intensity
    from marslab.environment.sky_dome import compute_sky_dome_params
    from marslab.environment.sun_position import compute_sol_sun_position, compute_sun_position

    sun_pos = compute_sun_position(
        azimuth_deg=float(mars_cfg.get("sun_azimuth_deg", 180)),
        elevation_deg=float(mars_cfg.get("sun_elevation_deg", 45)),
    )
    tau = float(mars_cfg.get("dust_optical_depth", 0.3))
    solar_constant = float(mars_cfg.get("solar_constant_mean", 589))
    direct_intensity = compute_direct_intensity(solar_constant, tau, sun_pos.zenith_angle_rad)
    diffuse_frac = compute_diffuse_fraction(tau)
    hdri_dir = os.path.join(REPO_ROOT, rendering_cfg.get("sky_dome_hdri_dir", "assets/sky/hdri/"))
    sky_params = compute_sky_dome_params(tau, hdri_dir)
    print(
        f"[run_stage2] Atmosphere: tau={tau}, direct={direct_intensity:.1f} W/m2, "
        f"diffuse_frac={diffuse_frac:.2f}",
        flush=True,
    )

    # --- Launch Isaac Sim ---------------------------------------------------
    from isaacsim import SimulationApp  # noqa: E402

    simulation_app = SimulationApp(
        {"headless": bool(args.headless), "renderer": "RaytracedLighting"}
    )

    # All omni/pxr imports after SimulationApp()
    import omni.usd  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402

    # --- Physics world (Mars gravity from config) ---------------------------
    physics_dt = 1.0 / 60.0
    world = World(
        stage_units_in_meters=1.0,
        physics_dt=physics_dt,
        rendering_dt=physics_dt,
    )

    gravity = float(mars_cfg.get("gravity", 3.72))
    physics_ctx = world.get_physics_context()
    physics_ctx.set_gravity(-gravity)
    physics_ctx.set_solver_type("TGS")
    print(f"[run_stage2] Gravity: {gravity} m/s^2", flush=True)

    stage = omni.usd.get_context().get_stage()

    # --- Build terrain mesh -------------------------------------------------
    from marslab.terrain.mesh_builder import build_terrain_mesh

    uv_scale = float(terrain_cfg.get("uv_scale", 1.0))
    terrain_prim_path = "/World/Terrain"
    norm_elevation = build_terrain_mesh(elevation, resolution, stage, terrain_prim_path, uv_scale)
    print(
        f"[run_stage2] Terrain mesh: {terrain_prim_path}, "
        f"normalized z=[{norm_elevation.min():.2f}, {norm_elevation.max():.2f}]",
        flush=True,
    )

    # --- Apply terrain material (PBR) ---------------------------------------
    from marslab.terrain.material_applicator import apply_terrain_material

    albedo_range = tuple(mars_cfg.get("surface_albedo_range", [0.10, 0.40]))
    texture_dir = terrain_cfg.get("texture_dir")
    if texture_dir:
        texture_dir = os.path.join(REPO_ROOT, texture_dir)
    apply_terrain_material(
        stage,
        terrain_prim_path,
        albedo_range=albedo_range,
        seed=int(terrain_cfg.get("seed", 42)),
        texture_dir=texture_dir,
    )
    print("[run_stage2] Terrain material applied.", flush=True)

    # --- Rock placement (Golombek SFD) ----------------------------------------
    rock_k = float(terrain_cfg.get("rock_sfd_k", 0))
    if rock_k > 0:
        from marslab.terrain.rock_instancer import place_rocks_on_terrain
        from marslab.terrain.rock_placer import sample_rocks_golombek

        d_range = tuple(terrain_cfg.get("rock_diameter_range", [0.20, 3.0]))
        area_m2 = float(norm_elevation.shape[0] * resolution * norm_elevation.shape[1] * resolution)
        rocks = sample_rocks_golombek(
            area_m2=area_m2,
            k=rock_k,
            diameter_range=d_range,
            seed=int(terrain_cfg.get("seed", 42)),
        )
        rock_mesh_dir = terrain_cfg.get("rock_mesh_dir")
        if rock_mesh_dir:
            rock_mesh_dir = os.path.join(REPO_ROOT, rock_mesh_dir)
        rock_texture_dir = terrain_cfg.get("rock_texture_dir")
        if rock_texture_dir:
            rock_texture_dir = os.path.join(REPO_ROOT, rock_texture_dir)
        place_rocks_on_terrain(
            stage=stage,
            rocks=rocks,
            elevation=norm_elevation,
            resolution=resolution,
            seed=int(terrain_cfg.get("seed", 42)),
            rock_color=tuple(terrain_cfg.get("rock_color", [0.42, 0.28, 0.20])),
            rock_roughness=float(terrain_cfg.get("rock_roughness", 0.92)),
            rock_mesh_dir=rock_mesh_dir,
            rock_texture_dir=rock_texture_dir,
        )
        print(f"[run_stage2] Placed {len(rocks)} rocks (k={rock_k}).", flush=True)
    else:
        print("[run_stage2] Rock placement skipped (rock_sfd_k=0).", flush=True)

    # --- Configure atmosphere rendering -------------------------------------
    from marslab.config.schema import RenderingConfig
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog
    from marslab.rendering.render_settings import set_render_mode
    from marslab.rendering.sky_renderer import configure_sky_dome, update_sky_dome
    from marslab.rendering.sun_renderer import configure_sun_light, update_sun_light

    render_config = RenderingConfig(**rendering_cfg)
    set_render_mode(render_config)
    configure_sun_light(stage, sun_pos, direct_intensity, diffuse_frac, render_config)
    configure_sky_dome(stage, sky_params, diffuse_frac, render_config)
    configure_atmosphere_fog(stage, tau, render_config)
    print("[run_stage2] Atmosphere configured (sun + sky + fog).", flush=True)

    # --- Dynamic atmosphere setup ------------------------------------------
    dyn_cfg = mars_cfg.get("dynamic_atmosphere", {})
    dynamic_enabled = bool(dyn_cfg.get("enabled", False))

    if dynamic_enabled:
        from marslab.environment.tau_profile import compute_tau

        sol_duration = float(mars_cfg.get("sol_duration_seconds", 88642))
        time_scale = float(dyn_cfg.get("time_scale", 200.0))
        update_interval = int(dyn_cfg.get("update_interval_frames", 10))

        sun_sweep_cfg = dyn_cfg.get("sun_sweep", {})
        sweep_start_az = float(sun_sweep_cfg.get("start_azimuth_deg", 90.0))
        sweep_end_az = float(sun_sweep_cfg.get("end_azimuth_deg", 270.0))
        sweep_max_el = float(sun_sweep_cfg.get("max_elevation_deg", 60.0))

        tau_profile_name = str(dyn_cfg.get("tau_profile", "constant"))
        tau_kwargs: Dict[str, float] = {}
        tau_profile_cfg = dyn_cfg.get(f"tau_{tau_profile_name}", {})
        if tau_profile_cfg:
            tau_kwargs.update(tau_profile_cfg)

        print(
            f"[run_stage2] Dynamic atmosphere ON: time_scale={time_scale}x, "
            f"tau_profile={tau_profile_name}, update_interval={update_interval}",
            flush=True,
        )
    else:
        print("[run_stage2] Dynamic atmosphere OFF (static).", flush=True)

    # --- Infinite render loop -----------------------------------------------
    world.reset()
    print("[run_stage2] Scene ready. Explore in GUI. Ctrl+C to exit.", flush=True)
    frame = 0
    elapsed = 0.0
    try:
        while simulation_app.is_running():
            world.step(render=True)
            frame += 1

            if dynamic_enabled and frame % update_interval == 0:
                elapsed += physics_dt * update_interval * time_scale
                t = (elapsed % sol_duration) / sol_duration

                # Recompute sun position for this time of sol
                dyn_sun_pos = compute_sol_sun_position(
                    time_of_sol_fraction=t,
                    start_azimuth_deg=sweep_start_az,
                    end_azimuth_deg=sweep_end_az,
                    max_elevation_deg=sweep_max_el,
                )

                # Recompute tau
                dyn_tau = compute_tau(tau_profile_name, t, **tau_kwargs)

                # Recompute irradiance and diffuse fraction
                dyn_intensity = compute_direct_intensity(
                    solar_constant, dyn_tau, dyn_sun_pos.zenith_angle_rad
                )
                dyn_diffuse = compute_diffuse_fraction(dyn_tau)
                dyn_sky = compute_sky_dome_params(dyn_tau, hdri_dir)

                # Update renderers in-place (no flicker)
                update_sun_light(stage, dyn_sun_pos, dyn_intensity, dyn_diffuse, render_config)
                update_sky_dome(stage, dyn_sky, dyn_diffuse, render_config)
                configure_atmosphere_fog(stage, dyn_tau, render_config)

    except KeyboardInterrupt:
        print("[run_stage2] KeyboardInterrupt -- shutting down.", flush=True)
    finally:
        try:
            simulation_app.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[run_stage2] simulation_app.close() raised: {exc}", file=sys.stderr)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
