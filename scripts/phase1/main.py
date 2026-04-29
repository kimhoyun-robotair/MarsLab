"""Stage 3 monolithic runtime: rover + scene + ROS2.

The body delegates to the modular facades exposed by ``marslab.runtime``,
``marslab.robots``, ``marslab.sensors``, and ``marslab.ros2_bridge``:

*   :func:`marslab.runtime.stage2_boot.run_stage2_boot` --- config +
    terrain + atmosphere (seed propagation happens inside).
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
*   :func:`marslab.runtime.articulation_setup.apply_initial_joint_positions`
    --- post-reset arm-stow / RA pose application.
*   :func:`marslab.runtime.sensor_frames.build_sensor_frames` --- pure
    YAML→TF-frame-list helper consumed by the static TF broadcaster.
*   :func:`marslab.runtime.loop_context.build_loop_context` --- factory
    that assembles :class:`LoopContext` from spawn outputs.

The ``--no-rover`` flag enters scene-only mode: rover spawn, sensor
graph, DriveAPI, articulation reset, and the rclpy bridge are all
skipped. The atmosphere panel + DEM mesh + structures still render so
the operator can validate DEM crops and HDRI/fog settings without the
70 kg rover settling on the surface.

Usage:
    scripts/isaac_python.sh scripts/phase1/main.py \\
        --config configs/scenarios/jezero_flat.yaml

    # Scene-only (DEM + atmosphere viewer, no rover, no ROS2):
    scripts/isaac_python.sh scripts/phase1/main.py \\
        --config configs/scenarios/jezero_flat.yaml --no-rover
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ``propagate_seeds_in_dict`` is re-exported here as a safety net so the
# twin-lock regression tests stay green even though ``run_stage2_boot``
# already enforces ``terrain.seed == mars_env.seed + 1`` internally.
from marslab.config.loader import propagate_seeds_in_dict  # noqa: E402, F401
from marslab.config.scenario_loader import load_scenario_config, resolve_spawn_pose  # noqa: E402
from marslab.robots.drive_api_setup import configure_drives, reinforce_pd_gains  # noqa: E402
from marslab.robots.rover import resolve_joint_indices, spawn_rover  # noqa: E402
from marslab.robots.rover_control import ackermann_command  # noqa: E402
from marslab.ros2_bridge.rclpy_integration import init_rclpy_side  # noqa: E402
from marslab.ros2_bridge.sensor_graph import build_sensor_graph  # noqa: E402
from marslab.ros2_bridge.tf_nameoverrides import (  # noqa: E402
    DEFAULT_ODOM_ANCHOR_PATH,
    apply_nameoverride,
    create_odom_anchor,
)
from marslab.runtime.articulation_setup import (  # noqa: E402
    apply_initial_joint_positions,
    pin_articulation_root_pose,
    zero_steer_joints,
)
from marslab.runtime.loop_context import build_loop_context  # noqa: E402
from marslab.runtime.main_loop import (  # noqa: E402
    AtmosphereLoopState,
    LoopContext,
    build_atmosphere_loop_state,
    run_main_loop,
)
from marslab.runtime.precheck import (  # noqa: E402
    check_lidar_cfg,
    check_rover_block,
    check_rover_usd,
)
from marslab.runtime.sensor_frames import build_sensor_frames, sensor_frames_to_tuples  # noqa: E402
from marslab.runtime.stage2_boot import run_stage2_boot  # noqa: E402
from marslab.runtime.stage2_scene import setup_stage2_scene  # noqa: E402

_LOG = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage 3 monolithic runtime: rover + scene + ROS2."
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
    parser.add_argument(
        "--no-rover",
        action="store_true",
        help=(
            "Scene-only mode: skip rover spawn, sensors, DriveAPI, "
            "articulation reset, and ROS2 bridge. DEM + atmosphere + "
            "structures still render so the DEM crop / HDRI / fog can be "
            "verified standalone."
        ),
    )
    args = parser.parse_args()
    args.config = args.config.strip()
    # ``--no-rover`` implies ``--no-ros2`` (no sensors → nothing to publish).
    if args.no_rover:
        args.no_ros2 = True

    # --- Stage-2 boot (config + terrain + atmosphere, seed enforcement) ------
    config_path = os.path.abspath(args.config)
    boot = run_stage2_boot(config_path, repo_root=REPO_ROOT)
    cfg = boot.config
    rover_cfg = cfg.get("rover") or {}

    # Rover-block validation + spawn-pose resolution lives behind the
    # ``--no-rover`` gate. Scene-only mode still needs the boot result
    # (DEM + atmosphere) but skips every rover-block KeyError so configs
    # without ``rover:`` (or with an incomplete sensors/control block)
    # remain runnable.
    if not args.no_rover:
        check_rover_block(rover_cfg)
        sensors_cfg = rover_cfg["sensors"]
        control_cfg = rover_cfg["control"]
        ros2_cfg = rover_cfg["ros2"]
        camera_cfg = sensors_cfg["camera"]
        check_lidar_cfg(sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar"))

        # Spawn pose comes from the DEM/metadata bundled on the boot result.
        spawn_xyz = resolve_spawn_pose(rover_cfg, boot.elevation, boot.metadata, boot.resolution)
        # Resolve the spawn orientation here so it can be reused for both
        # the USD root Xform (via ``spawn_rover``->``apply_spawn_pose``)
        # and the PhysX articulation root pose pin.  Single source of
        # truth: ``rover.spawn.orientation_rpy`` (with Stage-1 fallback
        # ``rover.spawn_orientation_rpy``).
        _spawn_block = rover_cfg.get("spawn", {}) if isinstance(rover_cfg, dict) else {}
        spawn_rpy_for_articulation = tuple(
            _spawn_block.get("orientation_rpy")
            or rover_cfg.get("spawn_orientation_rpy", [0.0, 0.0, 0.0])
        )
        usd_rel = rover_cfg["usd_path"]
        usd_abs = (
            usd_rel if os.path.isabs(usd_rel) else os.path.abspath(os.path.join(REPO_ROOT, usd_rel))
        )
        check_rover_usd(usd_abs)
        print(
            f"[main] Scenario loaded; spawn=({spawn_xyz[0]:.3f},"
            f"{spawn_xyz[1]:.3f},{spawn_xyz[2]:.3f})",
            flush=True,
        )
    else:
        # Scene-only mode stubs. ``control_cfg`` is fed to
        # ``build_loop_context`` further down; ``.get(..., 0.0)`` covers
        # the missing keys so the LoopContext still constructs.
        sensors_cfg = {}
        control_cfg = {}
        ros2_cfg = {}
        camera_cfg = {}
        spawn_xyz = (0.0, 0.0, 0.0)
        spawn_rpy_for_articulation = (0.0, 0.0, 0.0)
        usd_abs = ""
        print("[main] --no-rover: scene-only mode (skip rover spawn).", flush=True)

    # --- Isaac Sim boot ------------------------------------------------------
    from marslab.sim.boot import boot_simulation_app  # noqa: E402

    simulation_app = boot_simulation_app(headless=bool(args.headless))

    # Isaac Sim / ROS2 imports must come AFTER SimulationApp() resolves.
    from isaacsim.core.prims import Articulation  # noqa: E402

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
    # Defaults for the scene-only path; overwritten when ``--no-rover``
    # is absent.
    prim_path = ""
    chassis_path = ""
    rigid_body_path = ""

    if not args.no_rover:
        spawned = spawn_rover(stage, rover_cfg, usd_abs, spawn_xyz)
        prim_path = spawned.prim_path
        chassis_path = spawned.chassis_path
        rigid_body_path = spawned.rigid_body_path
        print(f"[main] Rover prim: {prim_path}, rigid body: {rigid_body_path}", flush=True)

        # Post-spawn: optional ``isaac:nameOverride`` apply + ``odom``
        # anchor creation.  These are gated by the schema flag
        # ``Ros2BridgeConfig.enable_isaac_nameoverride`` (C3 default
        # ``False``) because the C2+ ``robot_state_publisher`` workflow
        # reads frame names directly from the URDF link declarations and
        # never consults ``isaac:nameOverride``.  Set the flag ``True``
        # only when running the legacy ``PubTF``-on-``/tf_raw`` workflow
        # (``publish_joint_states=False``); the sensor graph in that
        # mode references the odom anchor, so these calls must happen
        # before ``build_sensor_graph``.
        ros2_cfg_for_flags = rover_cfg.get("ros2", {}) if isinstance(rover_cfg, dict) else {}
        if bool(ros2_cfg_for_flags.get("enable_isaac_nameoverride", False)):
            apply_nameoverride(stage, rigid_body_path, "base_link")
            create_odom_anchor(stage, DEFAULT_ODOM_ANCHOR_PATH, spawn_xyz, frame_name="odom")

    # --- Optional scene structures ------------------------------------------
    scene_cfg = cfg.get("scene") or {}
    scene_structures = scene_cfg.get("structures") if isinstance(scene_cfg, dict) else None
    if scene_structures:
        from marslab.config.schema.scene import StructureConfigSchema
        from marslab.scene.structure_loader import load_structures as _load_structures

        structure_cfgs = [StructureConfigSchema(**s).to_dataclass() for s in scene_structures]
        _prim_paths = _load_structures(stage, structure_cfgs)
        print(
            f"[main] Attached {len(_prim_paths)} scene structure(s).",
            flush=True,
        )

    # ``structure_assets:`` is the OBJ/STL drop-in block.  Without this
    # wiring, the schema/loader/test stack added in
    # ``marslab/scene/structure_loader.py:230-414`` would be unreachable
    # from the live Stage-3 runtime.  Empty list = zero overhead.
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
            f"[main] Attached {len(attached_paths)} structure_asset(s).",
            flush=True,
        )

    # --- Sensors + OmniGraph ROS2 bridge -------------------------------------
    # Defaults for the scene-only path; ``main_loop`` skips the rover
    # step body when ``ctx.articulation is None``.
    articulation = None
    imu = None
    drive_indices: list[int] = []
    steer_indices: list[int] = []

    if not args.no_rover:
        handles = spawn_sensors(stage, sensors_cfg, ros2_cfg, rigid_body_path)
        imu = handles.imu
        build_sensor_graph(
            ros2_cfg=ros2_cfg,
            camera_prim_path=handles.camera_prim_path,
            camera_resolution=tuple(camera_cfg["resolution"]),
            lidar_3d_prim_path=handles.lidar_3d_prim_path,
            imu_prim_path=handles.imu_prim_path,
            depth_sensor_cfg=camera_cfg.get("depth_sensor"),
            # Pass the prim that actually carries
            # ``PhysxArticulationRootAPI``.  USD inspection shows the
            # import produces a nested layout:
            #   /World/Rover                    (Xform spawn container)
            #     /Body_Chassis                 (Xform-only container)
            #       /Body_Chassis  <-- [ART_ROOT, RIGID] -- this prim
            #       /Body_RockerLeft, /Body_WheelLeftFront, ...
            # The first two ``world->Rover`` / ``world->Body_Chassis``
            # runs confirmed the upper levels are not articulation roots.
            # The canonical sample at ``test_pose_tree.py:103`` showed a
            # single articulation-root path expands to the full link
            # tree, so we point at the deepest path.  ``rover.py:502``
            # also targets this exact prim for ``apply_mass_properties``
            # (CoM + damping), which cross-validates that this is where
            # PhysX recognises the articulation.
            articulation_root_prim_path=f"{chassis_path}/Body_Chassis",
            # The anchor prim is created above by ``create_odom_anchor``
            # at this exact path.  Both call sites import the same
            # constant so they cannot drift.
            parent_anchor_prim_path=DEFAULT_ODOM_ANCHOR_PATH,
            lidar_2d_prim_path=handles.lidar_2d_prim_path,
        )

        # --- Pre-reset DriveAPI (must run BEFORE world.reset) ----------------
        configure_drives(stage, chassis_path, control_cfg)
        print(
            f"[main] DriveAPI configured (drive_type={control_cfg['drive_type']})",
            flush=True,
        )

        # --- Articulation + world.reset + warmup + post-reset PD reinforcement
        articulation = Articulation(prim_paths_expr=prim_path)
        world.reset()
        articulation.initialize()

        # Pin the PhysX articulation root world pose so the YAML
        # ``rover.spawn`` block is the single source of truth (the helper
        # documents the PhysX-vs-USD-parent-Xform subtlety).
        pin_articulation_root_pose(articulation, spawn_xyz, spawn_rpy_for_articulation)

        dof_names = list(articulation.dof_names)
        drive_indices = resolve_joint_indices(dof_names, list(control_cfg["drive_joint_names"]))
        steer_indices = resolve_joint_indices(dof_names, list(control_cfg["steer_joint_names"]))

        # Initialize steer joints at zero so PD gains land on a sane reference.
        zero_steer_joints(articulation, steer_indices)

        # Apply optional RA arm (or any other named joint) initial positions
        # from ``rover.control.initial_joint_positions``.  Empty dict = keep
        # URDF default pose.  Use case: stow the RA arm before ground contact
        # so the 70 kg arm+turret cluster does not drift the chassis during
        # the warmup loop.  Helper logs unknown joint names + PhysX failures.
        apply_initial_joint_positions(articulation, dof_names, control_cfg)

        print("[main] Warming up physics handle ...", flush=True)
        for _ in range(10):
            world.step(render=True)
        import omni.timeline  # noqa: E402

        timeline = omni.timeline.get_timeline_interface()
        if timeline.is_stopped():
            timeline.play()
            for _ in range(5):
                world.step(render=True)

        reinforce_pd_gains(articulation, control_cfg, dof_names)
        print("[main] PD gains reinforced post-reset.", flush=True)
    else:
        # Scene-only path: still call ``world.reset`` and pump Kit so the
        # AtmospherePanel widgets land on a stable state, mirroring the
        # rover path's race-avoidance pattern documented above.
        world.reset()
        for _ in range(10):
            world.step(render=True)
        import omni.timeline  # noqa: E402

        timeline = omni.timeline.get_timeline_interface()
        if timeline.is_stopped():
            timeline.play()
            for _ in range(5):
                world.step(render=True)
        print("[main] --no-rover: world reset + Kit pump complete.", flush=True)

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
            print("[main] Atmosphere control panel created.", flush=True)
        except Exception as exc:  # noqa: BLE001
            # Warning, not fatal: GUI panel is optional, the loop runs without it.
            _LOG.error("[main] GUI panel unavailable (%s).", exc)

    # --- Capture initial pose for manual odometry ----------------------------
    # ``init_pos_world`` is the rover's PhysX-reported spawn position
    # in the world frame -- used as the origin of the published
    # ``odom`` frame so ``odom -> base_link`` translation starts at
    # zero.
    #
    # ``init_quat_world`` is intentionally pinned to identity (1,0,0,0)
    # rather than the PhysX-reported spawn quaternion.  The
    # ``spawn_orientation_rpy = [pi, 0, 0]`` X-roll in the rover YAML
    # makes the articulation root (``Body_Chassis``) USD prim X-rolled
    # in world to compensate for the JPL m2020 URDF's graphics-style
    # link-frame author convention (Z-down).  Feeding that X-rolled
    # spawn quat to ``compute_odom_delta`` would make the published
    # ``odom`` frame itself X-rolled (Z-down), violating REP-103.
    # Identity ``init_quat_world`` keeps ``odom`` aligned with the
    # world Z-up frame; the X-roll then naturally appears on
    # ``odom -> Body_Chassis`` and is cancelled by the static
    # ``base_link -> Body_Chassis`` X-roll wrapper published from
    # ``launch/rover_state_publisher.launch.py``, leaving
    # ``odom -> base_link`` as a pure REP-103 (yaw-only) transform.
    if articulation is not None:
        init_poses = articulation.get_world_poses()
        if init_poses is not None:
            _ip, _ = init_poses
            odom_init_pos = (_ip[0] if _ip.ndim == 2 else _ip).copy()
        else:
            odom_init_pos = np.zeros(3, dtype=np.float32)
    else:
        odom_init_pos = np.zeros(3, dtype=np.float32)
    odom_init_quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

    # --- rclpy bridge (cmd_vel + static TF + manual odom) --------------------
    bridge = None
    if not args.no_ros2:
        # ``build_sensor_frames`` returns the canonical dict-per-sensor
        # list (camera/lidar_3d/lidar_2d/imu) sourced from the
        # validated YAML; ``sensor_frames_to_tuples`` adapts that to the
        # ``(child_frame, xyz)`` shape ``init_rclpy_side`` consumes.
        sensor_frames = sensor_frames_to_tuples(build_sensor_frames(rover_cfg, sensors_cfg))
        urdf_rel = rover_cfg.get("urdf_source_path")
        urdf_abs = (
            urdf_rel
            if urdf_rel is None or os.path.isabs(urdf_rel)
            else os.path.abspath(os.path.join(REPO_ROOT, urdf_rel))
        )
        bridge = init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=sensor_frames,
            init_pos_world=odom_init_pos,
            init_quat_world=odom_init_quat,
            node_name="stage3_runtime",
            urdf_path=urdf_abs,
        )

    # --- LoopContext construction + main loop --------------------------------
    def _spin_once() -> None:
        if bridge is not None:
            import rclpy  # noqa: PLC0415

            rclpy.spin_once(bridge.node, timeout_sec=0.0)

    ctx = build_loop_context(
        simulation_app=simulation_app,
        world=world,
        stage=stage,
        articulation=articulation,
        imu=imu,
        drive_indices=drive_indices,
        steer_indices=steer_indices,
        control_cfg=control_cfg,
        physics_dt=atmo_init.physics_dt,
        atmosphere=atmosphere_loop_state,
        render_config=render_config,
        ackermann_fn=ackermann_command,
        bridge=bridge,
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
    _ = (propagate_seeds_in_dict, AtmosphereLoopState, LoopContext, load_scenario_config)

    print("[main] Entering main loop. Ctrl+C to exit.", flush=True)
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
            _LOG.error("[main] simulation_app.close() raised: %s", exc)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
