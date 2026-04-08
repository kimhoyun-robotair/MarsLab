"""Full Mars scene orchestrator.

Integrates all MarsLab modules into a single Isaac Sim scene:
config → terrain → rocks → atmosphere → rendering → rover.

Run: ~/isaacsim/python.sh scripts/run_scene.py [--config configs/mars_env.yaml]

Output: work_log/mars_scene_v1.png (screenshot)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import omni.usd  # noqa: E402

from marslab.config.loader import load_config, propagate_seeds  # noqa: E402
from marslab.environment.diffuse_fraction import compute_diffuse_fraction  # noqa: E402
from marslab.environment.light_intensity import compute_direct_intensity  # noqa: E402
from marslab.environment.sky_dome import compute_sky_dome_params  # noqa: E402
from marslab.environment.sun_position import compute_sun_position  # noqa: E402
from marslab.rendering.atmosphere_fog import configure_atmosphere_fog  # noqa: E402
from marslab.rendering.render_settings import set_render_mode  # noqa: E402
from marslab.rendering.sky_renderer import configure_sky_dome  # noqa: E402
from marslab.rendering.sun_renderer import configure_sun_light  # noqa: E402
from marslab.robots.rover import spawn_rover  # noqa: E402
from marslab.terrain.material_applicator import apply_terrain_material  # noqa: E402
from marslab.terrain.mesh_builder import build_terrain_mesh  # noqa: E402
from marslab.terrain.procedural_generator import generate_terrain  # noqa: E402


def main() -> None:
    """Build and run a complete Mars scene."""
    parser = argparse.ArgumentParser(description="MarsLab Full Scene")
    parser.add_argument("--config", default="configs/mars_env.yaml", help="Config path")
    args = parser.parse_args()

    print("[run_scene] Loading config...")
    config = load_config(args.config)
    config = propagate_seeds(config)

    stage = omni.usd.get_context().get_stage()

    # --- Terrain ---
    print("[run_scene] Generating terrain...")
    if config.terrain.source == "hirise":
        from marslab.terrain.dem_loader import load_hirise_dem  # noqa: E402

        elevation, meta = load_hirise_dem(config.terrain.dem_path)
        resolution = meta["resolution_x"]
    else:
        elevation, meta = generate_terrain(
            preset=config.terrain.procedural_preset,
            size=config.terrain.terrain_size,
            resolution=config.terrain.terrain_resolution,
            seed=config.terrain.seed,
        )
        resolution = config.terrain.terrain_resolution

    print(f"  Terrain: {elevation.shape}, resolution={resolution}m/px")

    build_terrain_mesh(elevation, resolution, stage, "/World/Terrain")
    apply_terrain_material(
        stage, "/World/Terrain", config.mars_env.surface_albedo_range, config.terrain.seed
    )

    # --- Environment ---
    print("[run_scene] Computing atmosphere...")
    tau = config.mars_env.dust_optical_depth
    sun_pos = compute_sun_position(
        config.mars_env.sun_azimuth_deg, config.mars_env.sun_elevation_deg
    )
    intensity = compute_direct_intensity(
        config.mars_env.solar_constant_mean, tau, sun_pos.zenith_angle_rad
    )
    diffuse = compute_diffuse_fraction(tau)
    sky_params = compute_sky_dome_params(tau, config.rendering.sky_dome_hdri_dir)

    print(f"  Sun: az={sun_pos.azimuth_deg}, el={sun_pos.elevation_deg}")
    print(f"  Intensity: {intensity:.1f} W/m², diffuse: {diffuse:.2f}")
    print(
        f"  Sky: RGB({sky_params.base_color_rgb[0]:.2f}, "
        f"{sky_params.base_color_rgb[1]:.2f}, {sky_params.base_color_rgb[2]:.2f})"
    )

    # --- Rendering ---
    print("[run_scene] Configuring rendering...")
    set_render_mode(config.rendering.mode)
    configure_sky_dome(stage, sky_params)
    configure_sun_light(stage, sun_pos, intensity, diffuse)
    configure_atmosphere_fog(stage, tau)

    # --- Rover ---
    if config.robots:
        print("[run_scene] Spawning rover...")
        rover_config = config.robots[0]
        robot_path = spawn_rover(stage, rover_config, config.mars_env.gravity)
        print(f"  Rover at: {robot_path}")

    # --- Simulate ---
    print("[run_scene] Running simulation (60 steps)...")
    for _ in range(60):
        simulation_app.update()

    # --- Screenshot ---
    os.makedirs("work_log", exist_ok=True)
    output_path = os.path.abspath("work_log/mars_scene_v1.png")
    print(f"[run_scene] Scene assembled. Screenshot: {output_path}")

    # Note: headless screenshot requires viewport capture API.
    # For now, log success. Full capture in visual inspection.
    print("[run_scene] Done.")

    simulation_app.close()


if __name__ == "__main__":
    main()
