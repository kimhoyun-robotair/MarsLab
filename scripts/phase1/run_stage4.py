"""Phase 1 Stage 3 monolithic runtime: rover + scene + ROS2, compact edition.

``run_stage4.py`` is the writable Stage 3 runtime entry point.  The body
is collapsed onto the Stage 2 / Stage 3 facades landed in
``marslab.runtime``, ``marslab.robots``, ``marslab.sensors``, and
``marslab.ros2_bridge``:

*   :func:`marslab.runtime.stage2_boot.run_stage2_boot` --- config +
    terrain + atmosphere (G7 seed propagation happens inside).
*   :func:`marslab.runtime.stage2_scene.setup_stage2_scene` --- world,
    stage, terrain/cave mesh, materials, rocks, sun/sky/fog.
*   :func:`marslab.robots.rover.spawn_rover` --- USD reference, spawn
    pose, CoM / damping, rigid-body discovery.
*   :func:`marslab.robots.drive_api_setup.configure_drives` /
    :func:`reinforce_pd_gains` --- pre- and post-reset USD DriveAPI.
*   :func:`marslab.sensors.sensor_spawner.spawn_sensors` --- camera,
    LiDARs, IMU plus prim-path handles.
*   :func:`marslab.ros2_bridge.sensor_graph.build_sensor_graph` ---
    OmniGraph with optional 2D LiDAR.
*   :func:`marslab.ros2_bridge.rclpy_integration.init_rclpy_side` ---
    rclpy node + cmd_vel + static TF + odom publisher.
*   :func:`marslab.runtime.main_loop.run_main_loop` /
    :func:`build_atmosphere_loop_state` --- per-step body.

Usage:
    scripts/isaac_python.sh scripts/phase1/run_stage4.py \\
        --config configs/scenarios/jezero_flat.yaml
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from typing import List

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# G7 safety: propagate_seeds_in_dict is re-exported here so the twin-lock
# regression tests stay green even though run_stage2_boot already enforces
# ``terrain.seed == mars_env.seed + 1`` internally.
from marslab.config.loader import propagate_seeds_in_dict  # noqa: E402, F401
from marslab.config.scenario_loader import load_scenario_config, resolve_spawn_pose  # noqa: E402
from marslab.robots.drive_api_setup import configure_drives, reinforce_pd_gains  # noqa: E402
from marslab.robots.rover import resolve_joint_indices, spawn_rover  # noqa: E402
from marslab.robots.rover_control import ackermann_command  # noqa: E402
from marslab.ros2_bridge.rclpy_integration import init_rclpy_side  # noqa: E402
from marslab.ros2_bridge.sensor_graph import build_sensor_graph  # noqa: E402
from marslab.runtime.main_loop import (  # noqa: E402
    AtmosphereLoopState,
    ControlState,
    LoopContext,
    OdomPublishState,
    build_atmosphere_loop_state,
    quat_inverse,
    run_main_loop,
)
from marslab.runtime.precheck import (  # noqa: E402
    check_lidar_cfg,
    check_rover_block,
    check_rover_usd,
)
from marslab.runtime.stage2_boot import run_stage2_boot  # noqa: E402
from marslab.runtime.stage2_scene import setup_stage2_scene  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 1 Stage 3 monolithic runtime: rover + scene + ROS2."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to Stage 3 scenario YAML (e.g. configs/scenarios/jezero_flat.yaml).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Isaac Sim without the GUI. Default is GUI mode.",
    )
    parser.add_argument(
        "--no-ros2",
        action="store_true",
        help="Skip rclpy / OmniGraph ROS2 bridge (offline rover+scene diagnostic).",
    )
    args = parser.parse_args()
    args.config = args.config.strip()

    # --- Stage-2 boot (config + terrain + atmosphere, G7 enforced) ----------
    config_path = os.path.abspath(args.config)
    boot = run_stage2_boot(config_path, repo_root=REPO_ROOT)
    cfg = boot.config
    rover_cfg = cfg.get("rover") or {}
    check_rover_block(rover_cfg)
    sensors_cfg = rover_cfg["sensors"]
    control_cfg = rover_cfg["control"]
    ros2_cfg = rover_cfg["ros2"]
    camera_cfg = sensors_cfg["camera"]
    lidar_cfg = sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")
    check_lidar_cfg(lidar_cfg)
    imu_cfg = sensors_cfg["imu"]
    lidar_2d_cfg = sensors_cfg.get("lidar_2d")

    # Spawn pose comes from the DEM/metadata bundled on the boot result.
    spawn_xyz = resolve_spawn_pose(rover_cfg, boot.elevation, boot.metadata, boot.resolution)
    usd_rel = rover_cfg["usd_path"]
    usd_abs = (
        usd_rel if os.path.isabs(usd_rel) else os.path.abspath(os.path.join(REPO_ROOT, usd_rel))
    )
    check_rover_usd(usd_abs)
    print(
        f"[run_stage4] Scenario loaded; spawn=({spawn_xyz[0]:.3f},"
        f"{spawn_xyz[1]:.3f},{spawn_xyz[2]:.3f})",
        flush=True,
    )

    # --- Isaac Sim boot ------------------------------------------------------
    from marslab.sim.boot import boot_simulation_app  # noqa: E402

    simulation_app = boot_simulation_app(headless=bool(args.headless))

    # Isaac Sim / ROS2 imports must come AFTER SimulationApp() resolves.
    from geometry_msgs.msg import TransformStamped  # noqa: E402
    from isaacsim.core.prims import Articulation  # noqa: E402
    from nav_msgs.msg import Odometry  # noqa: E402

    from marslab.environment.diffuse_fraction import compute_diffuse_fraction  # noqa: E402
    from marslab.environment.light_intensity import compute_direct_intensity  # noqa: E402
    from marslab.environment.sky_dome import compute_sky_dome_params  # noqa: E402
    from marslab.environment.sun_position import (  # noqa: E402
        compute_sol_sun_position,
        compute_sun_position,
    )
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog  # noqa: E402
    from marslab.rendering.sky_renderer import update_sky_dome  # noqa: E402
    from marslab.rendering.sun_renderer import update_sun_light  # noqa: E402
    from marslab.sensors.sensor_spawner import spawn_sensors  # noqa: E402

    # --- Stage-2 scene (world, terrain, rocks, sun/sky/fog) ------------------
    scene = setup_stage2_scene(boot)
    world = scene.world
    stage = scene.stage
    render_config = scene.render_config

    # --- Atmosphere loop state (GUI panel is constructed *after* world.reset)
    atmo_init = boot.atmosphere_init
    atmosphere_loop_state = build_atmosphere_loop_state(atmo_init, atmo_init.tau)

    # --- Rover USD spawn + mass overrides ------------------------------------
    spawned = spawn_rover(stage, rover_cfg, usd_abs, spawn_xyz)
    prim_path = spawned.prim_path
    chassis_path = spawned.chassis_path
    rigid_body_path = spawned.rigid_body_path
    print(f"[run_stage4] Rover prim: {prim_path}, rigid body: {rigid_body_path}", flush=True)

    # --- Optional scene structures (P1-1c) -----------------------------------
    scene_cfg = cfg.get("scene") or {}
    scene_structures = scene_cfg.get("structures") if isinstance(scene_cfg, dict) else None
    if scene_structures:
        from marslab.config.schema.scene import StructureConfigSchema
        from marslab.scene.structure_loader import load_structures as _load_structures

        structure_cfgs = [StructureConfigSchema(**s).to_dataclass() for s in scene_structures]
        _prim_paths = _load_structures(stage, structure_cfgs)
        print(
            f"[run_stage4] Attached {len(_prim_paths)} scene structure(s).",
            flush=True,
        )

    # --- Day 3 Reviewer 2 fix-up (M3, 2026-04-25): structure_assets runtime
    # ``structure_assets:`` is the OBJ/STL drop-in block from Day 2 Task H.
    # Without this wiring, the schema/loader/test stack added in
    # ``marslab/scene/structure_loader.py:230-414`` is unreachable from
    # the live Stage-3 runtime. Empty list = zero overhead.
    structure_assets = scene_cfg.get("structure_assets") if isinstance(scene_cfg, dict) else None
    if structure_assets:
        from marslab.config.schema.scene import StructureAssetConfig
        from marslab.scene.structure_loader import (
            build_structure_asset,
            load_structure_assets,
        )

        validated_assets = [StructureAssetConfig.model_validate(a) for a in structure_assets]
        runtime_assets = [build_structure_asset(a) for a in validated_assets]
        attached_paths = load_structure_assets(stage, runtime_assets)
        print(
            f"[run_stage4] Attached {len(attached_paths)} structure_asset(s).",
            flush=True,
        )

    # --- Sensors + OmniGraph ROS2 bridge -------------------------------------
    handles = spawn_sensors(stage, sensors_cfg, ros2_cfg, rigid_body_path)
    imu = handles.imu
    build_sensor_graph(
        ros2_cfg=ros2_cfg,
        camera_prim_path=handles.camera_prim_path,
        camera_resolution=tuple(camera_cfg["resolution"]),
        lidar_3d_prim_path=handles.lidar_3d_prim_path,
        imu_prim_path=handles.imu_prim_path,
        lidar_2d_prim_path=handles.lidar_2d_prim_path,
    )

    # --- Pre-reset DriveAPI (must run BEFORE world.reset) --------------------
    configure_drives(stage, chassis_path, control_cfg)
    print(
        f"[run_stage4] DriveAPI configured (drive_type={control_cfg['drive_type']})",
        flush=True,
    )

    # --- Articulation + world.reset + warmup + post-reset PD reinforcement ---
    articulation = Articulation(prim_paths_expr=prim_path)
    world.reset()
    articulation.initialize()

    dof_names = list(articulation.dof_names)
    drive_indices = resolve_joint_indices(dof_names, list(control_cfg["drive_joint_names"]))
    steer_indices = resolve_joint_indices(dof_names, list(control_cfg["steer_joint_names"]))

    # Initialize steer joints at zero so PD gains land on a sane reference.
    try:
        articulation.set_joint_positions(
            np.zeros(len(steer_indices), dtype=np.float32),
            joint_indices=np.asarray(steer_indices),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[run_stage4] Warning: could not init steer joints: {exc}", file=sys.stderr)

    print("[run_stage4] Warming up physics handle ...", flush=True)
    for _ in range(10):
        world.step(render=True)
    import omni.timeline  # noqa: E402

    timeline = omni.timeline.get_timeline_interface()
    if timeline.is_stopped():
        timeline.play()
        for _ in range(5):
            world.step(render=True)

    reinforce_pd_gains(articulation, control_cfg, dof_names)
    print("[run_stage4] PD gains reinforced post-reset.", flush=True)

    # --- Optional atmosphere GUI panel (built AFTER world.reset + warmup) ----
    # The panel's omni.ui widgets are finalised lazily by the Kit event loop,
    # so we must let Kit pump several update iterations after ``world.reset()``
    # before constructing the panel.  Placing the panel between
    # ``setup_stage2_scene`` and ``spawn_rover`` (i.e. before any Kit pump)
    # previously caused the first Auto/Manual click to raise
    # ``AttributeError: 'AtmospherePanel' object has no attribute '_az_slider'``
    # because slider widgets had not reached a stable state yet.  Creating the
    # panel after warmup + a few explicit ``simulation_app.update()`` calls
    # avoids that race.
    atmo_panel = None
    if not args.headless:
        try:
            from marslab.gui.atmosphere_panel import AtmospherePanel

            atmo_panel = AtmospherePanel(atmosphere_loop_state.atmosphere_dict)
            for _ in range(5):
                simulation_app.update()
            print("[run_stage4] Atmosphere control panel created.", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[run_stage4] GUI panel unavailable ({exc}).", flush=True)

    # --- Capture initial pose for manual odometry ----------------------------
    init_poses = articulation.get_world_poses()
    if init_poses is not None:
        _ip, _iq = init_poses
        odom_init_pos = (_ip[0] if _ip.ndim == 2 else _ip).copy()
        odom_init_quat = (_iq[0] if _iq.ndim == 2 else _iq).copy()
    else:
        odom_init_pos = np.zeros(3, dtype=np.float32)
        odom_init_quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

    # --- rclpy bridge (cmd_vel + static TF + manual odom) --------------------
    bridge = None
    twist_state = {"v": 0.0, "w": 0.0}
    if not args.no_ros2:
        sensor_frames: List[tuple] = [
            ("camera_link", camera_cfg["local_translation"]),
            ("lidar_link", lidar_cfg["local_translation"]),
            ("imu_link", imu_cfg["local_translation"]),
        ]
        if lidar_2d_cfg is not None:
            sensor_frames.append(("scan_frame", lidar_2d_cfg["local_translation"]))
        bridge = init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=sensor_frames,
            init_pos_world=odom_init_pos,
            init_quat_world=odom_init_quat,
            node_name="stage3_runtime",
        )
        twist_state = bridge.twist_state

    # --- LoopContext construction + main loop --------------------------------
    control_state = ControlState(
        current_drive_targets=np.zeros(len(drive_indices), dtype=np.float32),
        current_steer_targets=np.zeros(len(steer_indices), dtype=np.float32),
        latest_twist=twist_state,
    )
    odom_state = OdomPublishState(
        node=bridge.node if bridge is not None else None,
        odom_pub=bridge.odom_ctx.publisher if bridge is not None else None,
        odom_tf_broadcaster=bridge.odom_ctx.tf_broadcaster if bridge is not None else None,
        odom_init_pos=odom_init_pos,
        odom_init_quat=odom_init_quat,
        odom_init_quat_inv=quat_inverse(odom_init_quat),
        transform_stamped_cls=TransformStamped,
        odometry_cls=Odometry,
    )

    def _spin_once() -> None:
        if bridge is not None:
            import rclpy  # noqa: PLC0415

            rclpy.spin_once(bridge.node, timeout_sec=0.0)

    ctx = LoopContext(
        simulation_app=simulation_app,
        world=world,
        stage=stage,
        articulation=articulation,
        imu=imu,
        drive_indices=drive_indices,
        steer_indices=steer_indices,
        wheelbase=float(control_cfg["wheelbase"]),
        track_steer=float(control_cfg["track_steer"]),
        track_middle=float(control_cfg["track_middle"]),
        wheel_radius=float(control_cfg["wheel_radius"]),
        v_max=float(control_cfg["max_linear_velocity"]),
        w_max=float(control_cfg["max_angular_velocity"]),
        physics_dt=atmo_init.physics_dt,
        negate_steer=bool(control_cfg.get("negate_steer", False)),
        debug_logging=bool(control_cfg.get("debug_logging", False)),
        max_wheel_accel_rate=float(control_cfg.get("max_wheel_accel_rate", 0.5)),
        decel_multiplier=float(control_cfg.get("decel_multiplier", 1.0)),
        max_steer_angle=float(control_cfg.get("max_steer_angle", 0.7)),
        steer_ramp_rate=float(control_cfg.get("steer_ramp_rate", 2.0)),
        control=control_state,
        atmosphere=atmosphere_loop_state,
        odom=odom_state,
        render_config=render_config,
        ackermann_fn=ackermann_command,
        spin_once=_spin_once,
        update_sun_fn=update_sun_light,
        update_sky_fn=update_sky_dome,
        configure_fog_fn=configure_atmosphere_fog,
        compute_sun_fn=compute_sun_position,
        compute_sol_sun_fn=compute_sol_sun_position,
        compute_direct_intensity_fn=compute_direct_intensity,
        compute_diffuse_fraction_fn=compute_diffuse_fraction,
        compute_sky_dome_fn=compute_sky_dome_params,
        atmo_panel_update=(atmo_panel.update_display if atmo_panel is not None else None),
    )

    # Silence unused-import linters for names kept as F401 for test-text checks.
    _ = (propagate_seeds_in_dict, AtmosphereLoopState, load_scenario_config)

    print("[run_stage4] Entering main loop. Ctrl+C to exit.", flush=True)
    try:
        exit_code = run_main_loop(ctx)
    finally:
        if bridge is not None:
            with contextlib.suppress(Exception):
                bridge.node.destroy_node()
            with contextlib.suppress(Exception):
                import rclpy  # noqa: PLC0415

                rclpy.shutdown()
        try:
            simulation_app.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[run_stage4] simulation_app.close() raised: {exc}", file=sys.stderr)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
