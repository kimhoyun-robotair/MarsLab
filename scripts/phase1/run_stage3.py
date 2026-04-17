"""Phase 1 Stage 3 runtime: Mars scene + rover + ROS2 + (optional) 2-D LaserScan.

Single entry point that merges the Stage 1 (rover) and Stage 2 (scene +
atmosphere) pipelines behind one YAML scenario file.  Used for every
scenario in ``configs/scenarios/*.yaml`` and as the base for SLAM /
Nav2 launches.

Data flow (P2 unidirectional):

    scenario YAML  ─┐
                    ├─► load_scenario_config (deep-merge)
    rover base YAML ┘
            │
            ▼
    load_terrain_elevation (offline)
            │
            ├─► resolve_spawn_pose (bilinear DEM sample)
            │
            ▼
    SimulationApp → World (Mars gravity) → build_terrain_scene
            → apply_terrain_material → rock placement → atmosphere
            → spawn_rover → attach_rover_sensor_rig → configure_drives
            → world.reset → articulation.initialize → reinforce_pd_gains
            → build_sensor_graph (OmniGraph, /tf_raw)
            → init_rclpy_side (cmd_vel / static TF / odom on /tf)
            → main loop: ackermann + ramps + publish_odometry

Usage:
    scripts/isaac_python.sh scripts/phase1/run_stage3.py \\
        --config configs/scenarios/jezero_flat.yaml
    # scene-only debug (no rover, no ROS2):
    scripts/isaac_python.sh scripts/phase1/run_stage3.py \\
        --config configs/scenarios/cerberus_canyon.yaml --no-rover
    # log to a file: ``2>&1 | tee`` is **shell redirection**, not an
    # argparse argument.  Put it *after* the Python command so it never
    # lands in --config:
    scripts/isaac_python.sh scripts/phase1/run_stage3.py \\
        --config configs/scenarios/jezero_flat.yaml 2>&1 | tee /tmp/stage3.log
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, Tuple

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "configs", "scenarios", "jezero_flat.yaml")

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Scenario YAML (default: jezero_flat).",
    )
    parser.add_argument("--headless", action="store_true", help="Run Isaac Sim without a GUI.")
    parser.add_argument(
        "--no-rover",
        action="store_true",
        help="Skip rover spawn / sensor rig / ROS2 bridge (scene-only debug).",
    )
    parser.add_argument(
        "--no-ros2",
        action="store_true",
        help="Spawn the rover but skip ROS2 (offline diagnostics).",
    )
    parser.add_argument(
        "--spawn-override",
        default=None,
        help='Override spawn position as "x,y,z" (world frame, metres).',
    )
    args = parser.parse_args()
    args.config = args.config.strip()
    return args


def _center_terrain_prim(
    stage: Any, prim_path: str, elevation: np.ndarray, resolution: float
) -> None:
    """Translate a heightmap terrain prim so its centre sits at world origin.

    ``build_terrain_mesh`` anchors the mesh at the SW corner (first vertex
    at world origin, last vertex at ``((cols-1)*res, (rows-1)*res)``).
    ``resolve_spawn_pose`` assumes the mesh is centred, so we shift the
    prim by ``(-center_col*res, -center_row*res, 0)``.
    """
    from pxr import Gf, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return
    h, w = elevation.shape
    cx = -(w - 1) / 2.0 * resolution
    cy = -(h - 1) / 2.0 * resolution
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(Gf.Vec3d(float(cx), float(cy), 0.0))


def _build_terrain_scene(
    stage: Any,
    cfg: Dict[str, Any],
    terrain_cfg: Dict[str, Any],
    mars_cfg: Dict[str, Any],
    elevation: np.ndarray,
    resolution: float,
) -> Tuple[np.ndarray, bool]:
    """Build terrain geometry + material + rock instances.

    Returns:
        Tuple of ``(normalized_elevation, is_cave)``.  ``normalized_elevation``
        is the z-shifted grid used downstream for rock height lookup.
    """
    is_cave = terrain_cfg.get("procedural_preset") == "cave"

    if is_cave:
        from marslab.terrain.cave_mesh_builder import build_cave_scene
        from marslab.terrain.material_applicator import apply_cave_material, apply_terrain_material

        cave_data = terrain_cfg["_cave_data"]
        norm_elevation = build_cave_scene(cave_data, stage)

        cave_cfg = terrain_cfg.get("cave", {})
        cave_albedo = tuple(cave_cfg.get("wall_albedo_range", [0.05, 0.15]))
        cave_seed = int(terrain_cfg.get("seed", 42))
        apply_cave_material(stage, "/World/Cave/Tube", cave_albedo, cave_seed)
        apply_cave_material(stage, "/World/Cave/Floor", cave_albedo, cave_seed + 1)
        for i in range(len(cave_data["skylight_meshes"])):
            apply_cave_material(stage, f"/World/Cave/Skylight_{i}", cave_albedo, cave_seed + 2 + i)

        surface_albedo = tuple(mars_cfg.get("surface_albedo_range", [0.10, 0.40]))
        texture_dir = terrain_cfg.get("texture_dir")
        if texture_dir:
            texture_dir = os.path.join(REPO_ROOT, texture_dir)
        apply_terrain_material(
            stage,
            "/World/Cave/Surface",
            albedo_range=surface_albedo,
            seed=cave_seed,
            texture_dir=texture_dir,
        )
        return norm_elevation, True

    from marslab.terrain.material_applicator import apply_terrain_material
    from marslab.terrain.mesh_builder import build_terrain_mesh

    uv_scale = float(terrain_cfg.get("uv_scale", 1.0))
    terrain_prim_path = "/World/Terrain"
    norm_elevation = build_terrain_mesh(elevation, resolution, stage, terrain_prim_path, uv_scale)
    _center_terrain_prim(stage, terrain_prim_path, elevation, resolution)

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
    del cfg  # unused — reserved for future multi-prim scenes
    return norm_elevation, False


def _place_rocks(
    stage: Any,
    terrain_cfg: Dict[str, Any],
    norm_elevation: np.ndarray,
    resolution: float,
) -> None:
    rock_k = float(terrain_cfg.get("rock_sfd_k", 0))
    if rock_k <= 0:
        return
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


def _configure_atmosphere(
    stage: Any, mars_cfg: Dict[str, Any], rendering_cfg: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply sun + sky + fog.  Returns a state dict for dynamic updates."""
    from marslab.config.schema import RenderingConfig
    from marslab.environment.diffuse_fraction import compute_diffuse_fraction
    from marslab.environment.light_intensity import compute_direct_intensity
    from marslab.environment.sky_dome import compute_sky_dome_params
    from marslab.environment.sun_position import compute_sun_position
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog
    from marslab.rendering.render_settings import set_render_mode
    from marslab.rendering.sky_renderer import configure_sky_dome
    from marslab.rendering.sun_renderer import configure_sun_light

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

    render_config = RenderingConfig(**rendering_cfg)
    set_render_mode(render_config)
    configure_sun_light(stage, sun_pos, direct_intensity, diffuse_frac, render_config)
    configure_sky_dome(stage, sky_params, diffuse_frac, render_config)
    configure_atmosphere_fog(stage, tau, render_config)
    return {
        "tau": tau,
        "solar_constant": solar_constant,
        "render_config": render_config,
        "hdri_dir": hdri_dir,
        "sun_pos": sun_pos,
        "direct_intensity": direct_intensity,
        "diffuse_fraction": diffuse_frac,
    }


def _parse_spawn_override(spec: str) -> Tuple[float, float, float]:
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 3:
        raise ValueError(f"--spawn-override must be 'x,y,z', got {spec!r}")
    return float(parts[0]), float(parts[1]), float(parts[2])


def main() -> int:
    args = parse_args()
    config_path = os.path.abspath(args.config)

    from marslab.config.scenario_loader import load_scenario_config, resolve_spawn_pose
    from marslab.terrain.elevation_loader import load_terrain_elevation

    cfg = load_scenario_config(config_path)
    print(f"[run_stage3] Loaded scenario: {config_path}", flush=True)

    mars_cfg = cfg["mars_env"]
    terrain_cfg = cfg["terrain"]
    rendering_cfg = cfg["rendering"]
    rover_cfg = cfg.get("rover", {})
    rover_enabled = bool(rover_cfg.get("enabled", True)) and not args.no_rover

    elevation, metadata, resolution = load_terrain_elevation(terrain_cfg)
    print(
        f"[run_stage3] Terrain: {elevation.shape} @ {resolution} m/px, "
        f"z=[{elevation.min():.1f}, {elevation.max():.1f}]",
        flush=True,
    )

    # Resolve spawn pose offline; still valid even when --no-rover.
    spawn_xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    if rover_enabled:
        if args.spawn_override:
            spawn_xyz = _parse_spawn_override(args.spawn_override)
        else:
            spawn_xyz = resolve_spawn_pose(rover_cfg, elevation, metadata, resolution)
        print(
            "[run_stage3] Spawn xyz = "
            f"({spawn_xyz[0]:.2f}, {spawn_xyz[1]:.2f}, {spawn_xyz[2]:.2f})",
            flush=True,
        )

    # --- Isaac Sim launch (all omni/pxr imports after this) ------------------
    from isaacsim import SimulationApp  # noqa: E402

    simulation_app = SimulationApp(
        {"headless": bool(args.headless), "renderer": "RaytracedLighting"}
    )

    try:
        import omni.usd  # noqa: E402
        from isaacsim.core.api import World  # noqa: E402

        physics_dt = float(cfg.get("physics", {}).get("time_step", 1.0 / 60.0))
        world = World(
            stage_units_in_meters=1.0,
            physics_dt=physics_dt,
            rendering_dt=physics_dt,
        )
        gravity = float(mars_cfg.get("gravity", 3.72))
        physics_ctx = world.get_physics_context()
        physics_ctx.set_gravity(-gravity)
        physics_ctx.set_solver_type("TGS")
        stage = omni.usd.get_context().get_stage()

        # --- Terrain + rocks ---
        norm_elevation, is_cave = _build_terrain_scene(
            stage, cfg, terrain_cfg, mars_cfg, elevation, resolution
        )
        if not is_cave:
            _place_rocks(stage, terrain_cfg, norm_elevation, resolution)

        # --- Atmosphere ---
        _configure_atmosphere(stage, mars_cfg, rendering_cfg)

        # --- Rover ---
        rig = None
        articulation = None
        if rover_enabled:
            from isaacsim.core.prims import Articulation

            from marslab.robots.rover import (
                configure_drives,
                reinforce_pd_gains,
                spawn_rover,
            )
            from marslab.sensors.rover_rig import attach_rover_sensor_rig

            usd_rel = str(rover_cfg["usd_path"])
            usd_abs = usd_rel if os.path.isabs(usd_rel) else os.path.join(REPO_ROOT, usd_rel)
            spawned = spawn_rover(stage, rover_cfg, usd_abs, spawn_xyz)
            print(
                f"[run_stage3] Rover spawned at {spawned.prim_path}; "
                f"rigid_body={spawned.rigid_body_path}",
                flush=True,
            )

            print("[run_stage3] Attaching sensor rig (camera+lidar_3d+imu)...", flush=True)
            rig = attach_rover_sensor_rig(
                stage=stage,
                sensors_cfg=rover_cfg["sensors"],
                rigid_body_path=spawned.rigid_body_path,
                ros2_rates=rover_cfg.get("ros2", {}).get("rates", {}),
            )
            print(
                f"[run_stage3] Sensor rig: camera={rig.camera_prim_path}, "
                f"lidar3d={rig.lidar_3d_prim_path}, imu={rig.imu_prim_path}",
                flush=True,
            )

            control_cfg = rover_cfg["control"]
            configure_drives(stage, spawned.chassis_path, control_cfg)

            # Build the ROS2 OmniGraph BEFORE world.reset().  Adding
            # IsaacCreateRenderProduct nodes into an already-active hydra
            # context (i.e. after the first rendered step) causes the
            # texture plugin to double-release per frame, which manifests
            # as a silent Kit abort after ~20 rendered frames.
            # run_stage1.py uses the same pre-reset ordering.
            if not args.no_ros2:
                from marslab.ros2_bridge import build_sensor_graph

                ros2_cfg = rover_cfg["ros2"]
                camera_cfg = rover_cfg["sensors"]["camera"]
                print(
                    "[run_stage3] Building OmniGraph sensor graph (pre-reset)...",
                    flush=True,
                )
                build_sensor_graph(
                    ros2_cfg=ros2_cfg,
                    camera_prim_path=rig.camera_prim_path,
                    camera_resolution=tuple(camera_cfg["resolution"]),
                    lidar_3d_prim_path=rig.lidar_3d_prim_path,
                    imu_prim_path=rig.imu_prim_path,
                )
                print("[run_stage3] OmniGraph sensor graph built.", flush=True)

            articulation = Articulation(prim_paths_expr=spawned.prim_path)
            world.reset()
            articulation.initialize()
            dof_names = list(articulation.dof_names)
            print(f"[run_stage3] Articulation DOFs ({len(dof_names)}): {dof_names}", flush=True)

            # Warm physics + play timeline so set_gains sees a valid handle.
            for _ in range(10):
                world.step(render=True)

            import omni.timeline  # noqa: E402

            timeline = omni.timeline.get_timeline_interface()
            if timeline.is_stopped():
                timeline.play()
                for _ in range(5):
                    world.step(render=True)

            reinforce_pd_gains(articulation, control_cfg, dof_names)
            print("[run_stage3] PD gains reinforced.", flush=True)
        else:
            # Scene-only mode: reset so rendering steps cleanly.
            world.reset()

        # --- ROS2 (rclpy side — after articulation.initialize for get_world_poses) ---
        bridge_ctx = None
        if rover_enabled and rig is not None and not args.no_ros2:
            from marslab.ros2_bridge import init_rclpy_side

            # Initial world pose for the odom origin.
            init_poses = articulation.get_world_poses()
            if init_poses is not None:
                _ip, _iq = init_poses
                init_pos = (_ip[0] if _ip.ndim == 2 else _ip).copy()
                init_quat = (_iq[0] if _iq.ndim == 2 else _iq).copy()
            else:
                init_pos = np.asarray(spawn_xyz, dtype=np.float32)
                init_quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

            sensor_frames = [
                ("camera_link", rover_cfg["sensors"]["camera"]["local_translation"]),
                ("lidar_link", rover_cfg["sensors"]["lidar_3d"]["local_translation"]),
                ("imu_link", rover_cfg["sensors"]["imu"]["local_translation"]),
            ]
            print("[run_stage3] Initialising rclpy bridge side...", flush=True)
            bridge_ctx = init_rclpy_side(
                ros2_cfg=rover_cfg["ros2"],
                sensor_frames=sensor_frames,
                init_pos_world=init_pos,
                init_quat_world=init_quat,
            )
            print("[run_stage3] ROS2 bridge up (cmd_vel, /tf, odom, static TFs).", flush=True)

        # --- Main loop ---------------------------------------------------------
        _run_main_loop(
            simulation_app=simulation_app,
            world=world,
            articulation=articulation,
            rover_cfg=rover_cfg if rover_enabled else None,
            bridge_ctx=bridge_ctx,
            physics_dt=physics_dt,
        )
    finally:
        try:
            if "bridge_ctx" in locals() and bridge_ctx is not None:
                import rclpy

                try:
                    bridge_ctx.node.destroy_node()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    if rclpy.ok():
                        rclpy.shutdown()
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
        try:
            simulation_app.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[run_stage3] simulation_app.close() raised: {exc}", file=sys.stderr)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0)
    return 0


def _run_main_loop(
    simulation_app: Any,
    world: Any,
    articulation: Any,
    rover_cfg: Any,
    bridge_ctx: Any,
    physics_dt: float,
) -> None:
    """Drive the simulation until the user quits.

    Split out so ``main()`` stays short and the control-loop state
    (ramps, step counter, odom publishing cadence) lives in one place.
    """
    from marslab.robots.rover import resolve_joint_indices
    from marslab.robots.rover_control import (
        ackermann_command,
        clamp_steer_angles,
        ramp_steer_angles,
        ramp_wheel_velocities,
    )
    from marslab.ros2_bridge import publish_odometry

    if rover_cfg is None or articulation is None:
        print("[run_stage3] Scene-only loop; Ctrl+C to exit.", flush=True)
        try:
            while simulation_app.is_running():
                world.step(render=True)
        except KeyboardInterrupt:
            print("[run_stage3] KeyboardInterrupt.", flush=True)
        return

    import rclpy

    control_cfg = rover_cfg["control"]
    dof_names = list(articulation.dof_names)
    drive_idx = np.asarray(
        resolve_joint_indices(dof_names, control_cfg["drive_joint_names"]), dtype=np.int32
    )
    steer_idx = np.asarray(
        resolve_joint_indices(dof_names, control_cfg["steer_joint_names"]), dtype=np.int32
    )

    wheel_radius = float(control_cfg["wheel_radius"])
    wheelbase = float(control_cfg["wheelbase"])
    track_steer = float(control_cfg["track_steer"])
    track_middle = float(control_cfg["track_middle"])
    v_max = float(control_cfg["max_linear_velocity"])
    w_max = float(control_cfg["max_angular_velocity"])
    max_steer_angle = float(control_cfg.get("max_steer_angle", 0.7))
    steer_ramp_rate = float(control_cfg.get("steer_ramp_rate", 2.0))
    max_wheel_accel_rate = float(control_cfg.get("max_wheel_accel_rate", 0.5))
    decel_multiplier = float(control_cfg.get("decel_multiplier", 1.0))
    negate_steer = bool(control_cfg.get("negate_steer", False))

    current_drive = np.zeros(len(drive_idx), dtype=np.float32)
    current_steer = np.zeros(len(steer_idx), dtype=np.float32)
    drive_step_lim = max_wheel_accel_rate * physics_dt
    steer_step_lim = steer_ramp_rate * physics_dt

    step_count = 0
    print("[run_stage3] Entering main loop. Ctrl+C to exit.", flush=True)
    try:
        while simulation_app.is_running():
            if bridge_ctx is not None:
                rclpy.spin_once(bridge_ctx.node, timeout_sec=0.0)
                v_raw = float(bridge_ctx.twist_state["v"])
                w_raw = float(bridge_ctx.twist_state["w"])
            else:
                v_raw, w_raw = 0.0, 0.0

            v = float(np.clip(v_raw, -v_max, v_max))
            w = float(np.clip(w_raw, -w_max, w_max))
            steer_angles, wheel_vels = ackermann_command(
                v, w, wheelbase, track_steer, track_middle, wheel_radius
            )
            if negate_steer:
                steer_angles = -steer_angles
            steer_angles = clamp_steer_angles(steer_angles, max_steer_angle)
            current_steer = ramp_steer_angles(current_steer, steer_angles, steer_step_lim)
            current_drive = ramp_wheel_velocities(
                current_drive, wheel_vels, drive_step_lim, decel_multiplier
            )

            try:
                articulation.set_joint_position_targets(current_steer, joint_indices=steer_idx)
                articulation.set_joint_velocity_targets(current_drive, joint_indices=drive_idx)
            except Exception as exc:  # noqa: BLE001
                print(f"[run_stage3] joint target failed: {exc}", file=sys.stderr)

            if bridge_ctx is not None:
                try:
                    poses = articulation.get_world_poses()
                    lin_vel = articulation.get_linear_velocities()
                    ang_vel = articulation.get_angular_velocities()
                    if poses is not None and lin_vel is not None and ang_vel is not None:
                        _rp, _rq = poses
                        cur_pos = _rp[0] if _rp.ndim == 2 else _rp
                        cur_quat = _rq[0] if _rq.ndim == 2 else _rq
                        lv = lin_vel[0] if lin_vel.ndim == 2 else lin_vel
                        av = ang_vel[0] if ang_vel.ndim == 2 else ang_vel
                        publish_odometry(
                            bridge_ctx.odom_ctx,
                            cur_pos,
                            cur_quat,
                            lv,
                            av,
                        )
                except Exception as exc:  # noqa: BLE001
                    if step_count < 120:
                        print(f"[run_stage3] odom publish failed: {exc}", file=sys.stderr)

            step_count += 1
            world.step(render=True)
    except KeyboardInterrupt:
        print("[run_stage3] KeyboardInterrupt.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
