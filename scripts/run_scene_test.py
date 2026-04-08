"""Integration test: full Mars scene assembly.

Run with: ~/isaacsim/python.sh scripts/run_scene_test.py

Tests:
    1. Full scene assembles without error
    2. All prims created (terrain, lights, rover)
    3. Tau variation produces different fog settings
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import carb  # noqa: E402
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
    """Run integration tests."""
    passed = 0
    failed = 0

    stage = omni.usd.get_context().get_stage()

    # TEST 1: Full scene assembly
    print("\n[TEST 1] Full scene assembly...")
    try:
        config = load_config("configs/mars_env.yaml")
        config = propagate_seeds(config)

        # Use procedural terrain (no DEM dependency)
        elevation, meta = generate_terrain("crater", (128, 128), 1.0, seed=42)
        build_terrain_mesh(elevation, 1.0, stage, "/World/Terrain")
        apply_terrain_material(stage, "/World/Terrain", config.mars_env.surface_albedo_range, 42)

        tau = config.mars_env.dust_optical_depth
        sun_pos = compute_sun_position(
            config.mars_env.sun_azimuth_deg, config.mars_env.sun_elevation_deg
        )
        intensity = compute_direct_intensity(
            config.mars_env.solar_constant_mean, tau, sun_pos.zenith_angle_rad
        )
        diffuse = compute_diffuse_fraction(tau)
        sky_params = compute_sky_dome_params(tau, "assets/sky/hdri/")

        set_render_mode(config.rendering.mode)
        configure_sky_dome(stage, sky_params)
        configure_sun_light(stage, sun_pos, intensity, diffuse)
        configure_atmosphere_fog(stage, tau)

        if config.robots:
            spawn_rover(stage, config.robots[0], config.mars_env.gravity)

        for _ in range(30):
            simulation_app.update()

        print("  PASSED: Scene assembled without error")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # TEST 2: Verify prims exist
    print("\n[TEST 2] Verify scene prims...")
    try:
        terrain_prim = stage.GetPrimAtPath("/World/Terrain")
        dome_prim = stage.GetPrimAtPath("/World/DomeLight")
        sun_prim = stage.GetPrimAtPath("/World/SunLight")

        assert terrain_prim.IsValid(), "Terrain prim missing"
        assert dome_prim.IsValid(), "DomeLight prim missing"
        assert sun_prim.IsValid(), "SunLight prim missing"

        print("  PASSED: All prims present (terrain, dome, sun)")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # TEST 3: Tau variation changes fog
    print("\n[TEST 3] Tau variation → fog density changes...")
    try:
        settings = carb.settings.get_settings()

        configure_atmosphere_fog(stage, 0.3)
        fog_low = settings.get("/rtx/fog/fogDistanceDensity")

        configure_atmosphere_fog(stage, 2.0)
        fog_high = settings.get("/rtx/fog/fogDistanceDensity")

        assert fog_high > fog_low, f"fog_low={fog_low}, fog_high={fog_high}"
        print(f"  PASSED: tau=0.3 fog={fog_low:.4f}, tau=2.0 fog={fog_high:.4f}")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # Summary
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*40}")

    simulation_app.close()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
