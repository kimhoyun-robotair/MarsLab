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
from marslab.terrain.rock_instancer import place_rocks_on_terrain  # noqa: E402
from marslab.terrain.rock_placer import sample_rocks_golombek  # noqa: E402


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
        if config.terrain.converted_dem_dir is not None:
            from marslab.terrain.dem_loader import load_converted_dem  # noqa: E402

            elevation, meta = load_converted_dem(config.terrain.converted_dem_dir)
        elif config.terrain.dem_path is not None:
            from marslab.terrain.dem_loader import load_hirise_dem  # noqa: E402

            elevation, meta = load_hirise_dem(config.terrain.dem_path)
        else:
            raise ValueError("HiRISE source requires converted_dem_dir or dem_path")
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

    build_terrain_mesh(
        elevation,
        resolution,
        stage,
        "/World/Terrain",
        uv_scale=config.terrain.uv_scale,
    )
    apply_terrain_material(
        stage,
        "/World/Terrain",
        config.mars_env.surface_albedo_range,
        config.terrain.seed,
        texture_dir=config.terrain.texture_dir,
    )

    # --- Rocks ---
    print("[run_scene] Placing rocks...")
    area = elevation.shape[0] * resolution * elevation.shape[1] * resolution
    rocks = sample_rocks_golombek(
        area_m2=area,
        k=config.terrain.rock_sfd_k,
        diameter_range=config.terrain.rock_diameter_range,
        seed=config.terrain.seed,
    )
    place_rocks_on_terrain(
        stage,
        rocks,
        elevation,
        resolution,
        seed=config.terrain.seed,
        rock_color=config.terrain.rock_color,
        rock_roughness=config.terrain.rock_roughness,
        rock_mesh_dir=config.terrain.rock_mesh_dir,
    )
    print(f"  Placed {len(rocks)} rocks on terrain")

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
    set_render_mode(config.rendering)
    configure_sky_dome(stage, sky_params, diffuse, config.rendering)
    configure_sun_light(stage, sun_pos, intensity, diffuse, config.rendering)
    configure_atmosphere_fog(stage, tau, config.rendering)

    # --- Compute terrain reference elevation for spawn/camera ---
    import numpy as np  # noqa: E402

    terrain_rows, terrain_cols = elevation.shape
    terrain_cx = terrain_cols * resolution / 2.0  # center X in meters
    terrain_cy = terrain_rows * resolution / 2.0  # center Y in meters
    terrain_center_elev = float(np.nanmedian(elevation))
    print(
        f"  Terrain center: ({terrain_cx:.0f}, {terrain_cy:.0f}), "
        f"median elev: {terrain_center_elev:.1f}m"
    )

    def _terrain_z_at(x: float, y: float) -> float:
        """Query terrain elevation at (x, y) world coords."""
        c = int(np.clip(x / resolution, 0, terrain_cols - 1))
        r = int(np.clip(y / resolution, 0, terrain_rows - 1))
        z = float(elevation[r, c])
        return 0.0 if np.isnan(z) else z

    # --- Robots ---
    robot_prim_paths = {}  # robot_name → actual prim path from spawn
    if config.robots:
        print(f"[run_scene] Spawning {len(config.robots)} robot(s)...")
        for i, robot_config in enumerate(config.robots):
            # Adjust spawn Z to terrain surface + config offset
            sx, sy, sz_offset = robot_config.spawn_position
            spawn_x = terrain_cx + sx
            spawn_y = terrain_cy + sy
            surface_z = _terrain_z_at(spawn_x, spawn_y)
            robot_config.spawn_position = [spawn_x, spawn_y, surface_z + sz_offset]
            print(
                f"  {robot_config.type} spawn: ({spawn_x:.1f}, {spawn_y:.1f}, "
                f"{surface_z + sz_offset:.1f}) [surface={surface_z:.1f}, offset={sz_offset}]"
            )

            if robot_config.type == "rover":
                path = spawn_rover(stage, robot_config, config.mars_env.gravity)
            elif robot_config.type == "rotorcraft":
                from marslab.robots.rotorcraft import spawn_rotorcraft  # noqa: E402

                path = spawn_rotorcraft(
                    stage, robot_config, config.mars_env.gravity, config.mars_env.atmo_density
                )
            elif robot_config.type == "quadruped":
                from marslab.robots.quadruped import spawn_quadruped  # noqa: E402

                path = spawn_quadruped(stage, robot_config, config.mars_env.gravity)
            else:
                print(f"  Warning: Unknown robot type '{robot_config.type}', skipping")
                continue

            robot_name = f"{robot_config.type}_{i}"
            robot_prim_paths[robot_name] = path
            print(f"  {robot_config.type} prim: {path}")

            # Attach sensors if configured
            if robot_config.sensor_config_paths:
                from marslab.sensors import load_and_attach_sensor  # noqa: E402

                for sensor_path in robot_config.sensor_config_paths:
                    try:
                        sensor = load_and_attach_sensor(stage, path, sensor_path)
                        print(f"    Sensor: {sensor_path} -> {sensor}")
                    except Exception as e:
                        print(f"    Warning: sensor failed: {sensor_path}: {e}")

    # --- ROS2 Bridge (optional) ---
    try:
        import yaml  # noqa: E402

        from marslab.ros2_bridge.publisher import (  # noqa: E402
            enable_ros2_bridge,
            setup_all_publishers,
            setup_clock_publisher,
        )

        enable_ros2_bridge()
        setup_clock_publisher()
        print("[run_scene] ROS2 bridge enabled, clock publisher active")

        for i, robot_config in enumerate(config.robots):
            if not robot_config.sensor_config_paths:
                continue
            robot_name = f"{robot_config.type}_{i}"
            actual_robot_path = robot_prim_paths.get(robot_name)
            if not actual_robot_path:
                continue

            sensor_prim_paths = {}
            sensor_configs = {}
            for sp in robot_config.sensor_config_paths:
                try:
                    with open(sp) as f:
                        cfg = yaml.safe_load(f).get("sensor", {})
                    sname = cfg.get("name", "")
                    mount = cfg.get("mount_link", "base_link")
                    # Use actual robot prim path from spawn
                    prim = stage.GetPrimAtPath(f"{actual_robot_path}/{mount}/{sname}")
                    if prim.IsValid():
                        sensor_prim_paths[sname] = f"{actual_robot_path}/{mount}/{sname}"
                    else:
                        sensor_prim_paths[sname] = f"{actual_robot_path}/{sname}"
                    sensor_configs[sname] = cfg
                except Exception:
                    pass
            if sensor_prim_paths:
                topics = setup_all_publishers(robot_name, sensor_prim_paths, sensor_configs)
                print(f"  [ros2] {robot_name}: {len(topics)} topic(s)")
    except Exception as e:
        print(f"[run_scene] ROS2 bridge not available (non-fatal): {e}")

    # --- Simulate ---
    print("[run_scene] Running simulation (60 steps)...")
    for _ in range(60):
        simulation_app.update()

    # --- Screenshot via Replicator ---
    print("[run_scene] Capturing screenshots...")
    os.makedirs("work_log", exist_ok=True)

    import omni.replicator.core as rep  # noqa: E402
    from PIL import Image  # noqa: E402

    # Camera reference point: first robot or terrain center
    if config.robots:
        rx, ry, rz = config.robots[0].spawn_position
    else:
        rx, ry = terrain_cx, terrain_cy
        rz = _terrain_z_at(rx, ry)

    # Bird's eye view: look straight down at terrain center
    terrain_extent = max(terrain_cols, terrain_rows) * resolution
    bird_eye_height = terrain_center_elev + terrain_extent * 0.8

    shots = [
        {
            "name": "closeup",
            "position": (rx + 3.0, ry + 2.0, rz + 1.5),
            "look_at": (rx, ry, rz),
            "file": "mars_scene_closeup.png",
        },
        {
            "name": "overview",
            "position": (rx + 15.0, ry + 15.0, rz + 12.0),
            "look_at": (rx, ry, rz),
            "file": "mars_scene_overview.png",
        },
        {
            "name": "birdseye",
            "position": (terrain_cx, terrain_cy, bird_eye_height),
            "look_at": (terrain_cx, terrain_cy, terrain_center_elev),
            "file": "mars_scene_birdseye.png",
        },
    ]

    for shot in shots:
        camera = rep.create.camera(
            position=shot["position"],
            look_at=shot["look_at"],
        )
        render_product = rep.create.render_product(camera, tuple(config.rendering.resolution))

        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb_annotator.attach([render_product])

        # Render frames to let image converge
        for _ in range(10):
            rep.orchestrator.step(rt_subframes=4)

        rgb_data = rgb_annotator.get_data()
        shot_path = os.path.join("work_log", shot["file"])
        if rgb_data is not None and rgb_data.size > 0:
            img_array = np.array(rgb_data)
            if img_array.ndim == 3 and img_array.shape[2] == 4:
                img_array = img_array[:, :, :3]
            img = Image.fromarray(img_array)
            img.save(os.path.abspath(shot_path))
            print(f"[run_scene] {shot['name']} saved: {shot_path}")
        else:
            print(f"[run_scene] Warning: No data for {shot['name']}")

    # --- Continuous mode for ROS2 topic verification ---
    if os.environ.get("MARSLAB_PUBLISH") == "1":
        print("[run_scene] MARSLAB_PUBLISH=1: Running continuously with full Mars scene.")
        print("  Open another terminal and run:")
        print("    ros2 topic list")
        print("    ros2 topic echo /rover_0/stereo_rgb/image_raw --once")
        print("  Press Ctrl+C to stop.\n")
        frame = 0
        try:
            while simulation_app.is_running():
                simulation_app.update()
                frame += 1
                if frame % 300 == 0:
                    print(f"  [publish] frame {frame}, sim running...")
        except KeyboardInterrupt:
            print("\n[run_scene] Stopped by user.")
    else:
        print("[run_scene] Done.")

    simulation_app.close()


if __name__ == "__main__":
    main()
