#!/usr/bin/env python3
"""Production entry point: USDA + Rover + ROS2 with dynamic atmosphere/lighting.

Loads a user-provided Scene USDZ package (with baked materials and
collision) through the pre-S06 ``--usda`` compatibility flag, spawns the
MarsLab M2020 rover on top of it, and runs
the full MarsLab atmosphere / lighting stack (sun + sky dome + fog,
optionally Auto-mode sun sweep) plus the ROS2 bridge.

The scenario YAML (default ``configs/default.yaml``)
supplies ``mars_env`` + ``rendering`` + ``dynamic_atmosphere`` blocks.
The scenario's own ``terrain`` block is still loaded (``boot_atmosphere``
requires it) but the resulting elevation grid is discarded -- the live
stage uses the supplied scene mesh instead.

Run from MarsLab repo root::

    marslab/isaac_python.sh marslab/main.py --usda assets/scene/jezero_plain/jezero_plain.usdz

Spawn position is ``(DEM_center_xy, surface_z + z_offset)`` where
``DEM_center_xy`` is the world-space bbox center of the USDA terrain
mesh and ``surface_z`` is the median Z of mesh points sampled near
that center.

The supplied scene package must satisfy:

* ``upAxis = "Z"`` and ``metersPerUnit = 1``.
* Carries ``UsdPhysics.CollisionAPI`` on at least one mesh under the
  default prim so the rover wheels have something to contact.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# marslab/main.py -> MarsLab/ is one level up.
_THIS_FILE = Path(__file__).resolve()
REPO_ROOT = str(_THIS_FILE.parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Pre-Kit-boot imports (offline-safe; no isaacsim/omni/pxr/rclpy).
from marslab.config import RoverConfig, load_rover_config  # noqa: E402
from marslab.config.schema.rover_sensors import EnabledImuConfig  # noqa: E402
from marslab.robots.drive_api_setup import (  # noqa: E402
    configure_drives,
    reinforce_pd_gains,
)
from marslab.robots.rover import (  # noqa: E402
    resolve_joint_indices,
    spawn_rover,
)
from marslab.robots.rover_control import ackermann_command  # noqa: E402
from marslab.ros2_bridge.rclpy_integration import init_rclpy_side  # noqa: E402
from marslab.ros2_bridge.sensor_graph import build_sensor_graph  # noqa: E402
from marslab.ros2_bridge.tf_nameoverrides import (  # noqa: E402
    DEFAULT_ODOM_ANCHOR_PATH,
)
from marslab.runtime.articulation_setup import (  # noqa: E402
    apply_initial_joint_positions,
    pin_articulation_root_pose,
    zero_steer_joints,
)
from marslab.runtime.atmosphere_boot import boot_atmosphere  # noqa: E402
from marslab.runtime.loop_context import build_loop_context  # noqa: E402
from marslab.runtime.main_loop import (  # noqa: E402
    build_atmosphere_loop_state,
    run_main_loop,
)
from marslab.runtime.precheck import check_rover_usd  # noqa: E402
from marslab.runtime.sensor_frames import (  # noqa: E402
    build_sensor_frames,
    sensor_frames_to_tuples,
)
from marslab.sim.boot import boot_simulation_app  # noqa: E402
from marslab.sim.world_setup import create_world  # noqa: E402

_LOG = logging.getLogger("marslab.main")

_DEFAULT_Z_OFFSET = 0.1
_DEFAULT_SCENARIO = "configs/default.yaml"
_PRE_S05_ROVER_USD_PATH = "assets/robots/rover/m2020.usd"
_TERRAIN_PRIM_PATH = "/World/Terrain"


def _abs_repo_path(p: str) -> str:
    """Resolve a possibly repo-relative path to an absolute path."""
    return p if os.path.isabs(p) else os.path.abspath(os.path.join(REPO_ROOT, p))


def _load_rover_cfg(rover_yaml_abs: str) -> RoverConfig:
    """Load and validate the rover YAML block (precheck before Kit boot)."""
    return load_rover_config(rover_yaml_abs)


def _resolve_spawn_rpy(rover_cfg: RoverConfig) -> Tuple[float, float, float]:
    """Resolve spawn RPY from the rover YAML (mirrors main.py:172-176)."""
    rpy_raw = rover_cfg.spawn.orientation_rpy
    return float(rpy_raw[0]), float(rpy_raw[1]), float(rpy_raw[2])


def _find_terrain_meshes(
    stage: Any,
    terrain_prim_path: str,
) -> Tuple[Any, Any]:
    """Return ``(visible_mesh, collision_mesh)`` prims under ``terrain_prim_path``.

    The visible mesh is the first non-``invisible`` ``UsdGeom.Mesh`` (the
    rendered surface); the collision mesh is the first prim named ``*Collision*``
    or authored ``invisible`` (the surface the rover physically rests on). Either
    may be ``None``.
    """
    from pxr import Usd, UsdGeom  # noqa: PLC0415

    terrain_root = stage.GetPrimAtPath(terrain_prim_path)
    if not terrain_root.IsValid():
        raise RuntimeError(f"Terrain prim not found at {terrain_prim_path}")

    visible = collision = None
    for prim in Usd.PrimRange(terrain_root):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        vis_attr = UsdGeom.Imageable(prim).GetVisibilityAttr()
        invisible = vis_attr.IsValid() and vis_attr.Get() == UsdGeom.Tokens.invisible
        if "Collision" in prim.GetName() or invisible:
            if collision is None:
                collision = prim
        elif visible is None:
            visible = prim
    return visible, collision


def _nearest_k_median_z(
    mesh_prim: Any,
    target_x: float,
    target_y: float,
    k: int = 8,
) -> float:
    """Median world-Z of the ``k`` mesh vertices nearest ``(target_x, target_y)``
    in world XY.

    Evaluates the surface elevation AT the target point rather than averaging a
    size-scaled disk, so spawn Z is unbiased on sloped/curved terrain (a disk
    median sits above the floor of a crater and below the crest of a rise). The
    k-nearest median (vs single nearest) is robust to a stray vertex.
    """
    from pxr import Usd, UsdGeom  # noqa: PLC0415

    points = UsdGeom.Mesh(mesh_prim).GetPointsAttr().Get()
    if points is None or len(points) == 0:
        raise RuntimeError(
            f"Mesh {mesh_prim.GetPath()} has no authored points; cannot sample " "DEM elevation."
        )
    local_to_world = UsdGeom.XformCache(Usd.TimeCode.Default()).GetLocalToWorldTransform(mesh_prim)
    matrix = np.array(local_to_world, dtype=np.float64)  # 4x4, row-vector convention
    pts = np.asarray(points, dtype=np.float64)
    world = pts @ matrix[:3, :3] + matrix[3, :3]
    d2 = (world[:, 0] - target_x) ** 2 + (world[:, 1] - target_y) ** 2
    k = min(k, world.shape[0])
    idx = np.argpartition(d2, k - 1)[:k]
    return float(np.median(world[idx, 2]))


def _sample_dem_surface_z_at(
    stage: Any,
    terrain_prim_path: str,
    target_x: float,
    target_y: float,
) -> float:
    """Return the ground elevation at world XY ``(target_x, target_y)``.

    Samples the median Z of the vertices nearest the exact XY on the collision
    mesh (the surface the rover rests on; falls back to the visible mesh).
    Evaluating at the exact point avoids the regional-average bias that made the
    rover spawn metres above the ground on large, high-relief scenes (craters).
    """
    visible, collision = _find_terrain_meshes(stage, terrain_prim_path)
    mesh_prim = collision if collision is not None else visible
    if mesh_prim is None:
        raise RuntimeError(
            f"No UsdGeom.Mesh under {terrain_prim_path}; cannot sample DEM elevation."
        )
    return _nearest_k_median_z(mesh_prim, target_x, target_y)


def _resolve_spawn(
    stage: Any,
    terrain_prim_path: str,
    rover_cfg: RoverConfig,
    cli_z_offset: float,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Resolve spawn ``(xyz, rpy)`` from the YAML ``spawn:`` block + DEM.

    Supported modes (``spawn.mode``):

    * ``dem_center`` (default, legacy): spawn at DEM bbox centre. ``xy``
      ignored.
    * ``dem_relative``: spawn at ``(dem_center_x + xy[0],
      dem_center_y + xy[1])``.
    * ``absolute``: spawn at ``(xy[0], xy[1])`` in world frame.
    The ground elevation at the resolved XY is sampled from the loaded
    DEM mesh; the rover Z is set to ``surface_z + z_offset``. The
    ``z_offset`` is taken from the YAML ``spawn.z_offset`` if present,
    otherwise falls back to the CLI ``--z-offset`` flag.
    """
    spawn_block = rover_cfg.spawn
    mode = spawn_block.mode
    xy = spawn_block.xy
    z_off = spawn_block.z_offset if spawn_block.z_offset is not None else cli_z_offset

    cx_dem, cy_dem, _ = _sample_dem_elevation(stage, terrain_prim_path)

    if mode == "dem_center":
        sx, sy = cx_dem, cy_dem
    elif mode == "dem_relative":
        sx = cx_dem + float(xy[0])
        sy = cy_dem + float(xy[1])
    elif mode == "absolute":
        sx = float(xy[0])
        sy = float(xy[1])
    else:
        raise RuntimeError(
            f"Unknown spawn.mode='{mode}' in rover YAML; expected one of "
            "dem_center | dem_relative | absolute"
        )

    surface_z = _sample_dem_surface_z_at(stage, terrain_prim_path, sx, sy)
    spawn_xyz = (sx, sy, surface_z + z_off)

    roll, pitch, yaw_yaml = _resolve_spawn_rpy(rover_cfg)
    spawn_rpy = (roll, pitch, yaw_yaml)

    _LOG.info(
        "Resolved spawn: mode=%s xyz=(%.3f, %.3f, %.3f) rpy=(%.3f, %.3f, %.3f) "
        "[dem_center=(%.3f, %.3f), surface_z=%.3f, z_offset=%.3f]",
        mode,
        spawn_xyz[0],
        spawn_xyz[1],
        spawn_xyz[2],
        spawn_rpy[0],
        spawn_rpy[1],
        spawn_rpy[2],
        cx_dem,
        cy_dem,
        surface_z,
        z_off,
    )
    return spawn_xyz, spawn_rpy


def _sample_dem_elevation(
    stage: Any,
    terrain_prim_path: str,
) -> Tuple[float, float, float]:
    """Return ``(cx, cy, surface_z)`` at the DEM center.

    ``(cx, cy)`` is the visible-mesh world bbox centre. ``surface_z`` is the
    ground elevation sampled at that exact centre XY from the collision mesh
    (falls back to the visible mesh) via :func:`_nearest_k_median_z` -- not a
    regional disk average, so it is unbiased on craters/canyons.
    """
    from pxr import Usd, UsdGeom  # noqa: PLC0415

    visible, collision = _find_terrain_meshes(stage, terrain_prim_path)
    if visible is None and collision is None:
        raise RuntimeError(
            f"No UsdGeom.Mesh under {terrain_prim_path}; cannot sample DEM elevation."
        )

    bbox_ref = visible if visible is not None else collision
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        includedPurposes=[UsdGeom.Tokens.default_],
    )
    bbox = bbox_cache.ComputeWorldBound(bbox_ref).ComputeAlignedRange()
    bmin, bmax = bbox.GetMin(), bbox.GetMax()
    cx = float((bmin[0] + bmax[0]) / 2.0)
    cy = float((bmin[1] + bmax[1]) / 2.0)

    mesh_prim = collision if collision is not None else visible
    surface_z = _nearest_k_median_z(mesh_prim, cx, cy)
    _LOG.info(
        "DEM center=(%.3f, %.3f) surface_z=%.3f (nearest-k median on %s mesh)",
        cx,
        cy,
        surface_z,
        "collision" if collision is not None else "visible",
    )
    return cx, cy, surface_z


def _reference_user_usda(stage: Any, usda_abs: str) -> None:
    """Reference the supplied legacy ``--usda`` scene input under ``/World/Terrain``.

    The scene's own ``PhysicsScene`` (if any) is deactivated so the
    Mars-gravity ``/physicsScene`` created by :func:`create_world`
    remains the sole active physics scene.
    """
    import omni.kit.app  # noqa: PLC0415
    from isaacsim.core.utils.stage import (  # noqa: PLC0415
        add_reference_to_stage,
        is_stage_loading,
    )

    add_reference_to_stage(usd_path=usda_abs, prim_path=_TERRAIN_PRIM_PATH)
    app = omni.kit.app.get_app()
    while is_stage_loading():
        app.update()

    nested_phys = stage.GetPrimAtPath(f"{_TERRAIN_PRIM_PATH}/PhysicsScene")
    if nested_phys.IsValid():
        nested_phys.SetActive(False)
        _LOG.info(
            "Deactivated nested PhysicsScene at %s/PhysicsScene.",
            _TERRAIN_PRIM_PATH,
        )


_FALLBACK_LIGHT_PATH = "/World/FallbackSun"


def _add_fallback_light_if_missing(stage: Any) -> bool:
    """Add a ``DistantLight`` if the loaded stage carries no lights.

    Used by ``--no-atmosphere`` so the camera does not see a black scene
    when the full MarsLab sun + sky + fog stack is bypassed. Returns
    ``True`` if a fallback was added.
    """
    from pxr import Sdf, UsdLux  # noqa: PLC0415

    light_types = (
        UsdLux.DistantLight,
        UsdLux.DomeLight,
        UsdLux.SphereLight,
        UsdLux.RectLight,
        UsdLux.DiskLight,
        UsdLux.CylinderLight,
    )
    for prim in stage.Traverse():
        if any(prim.IsA(t) for t in light_types):
            _LOG.info("Stage already has a light at %s; skipping fallback.", prim.GetPath())
            return False

    light = UsdLux.DistantLight.Define(stage, Sdf.Path(_FALLBACK_LIGHT_PATH))
    light.CreateIntensityAttr(3000.0)
    light.CreateAngleAttr(0.53)
    light.CreateColorAttr((1.0, 0.85, 0.65))
    _LOG.info("Added fallback DistantLight at %s.", _FALLBACK_LIGHT_PATH)
    return True


def _capture_odom_init_pose(articulation: Any) -> Tuple[np.ndarray, np.ndarray]:
    """Capture the initial PhysX world pose to anchor the odom frame.

    Position from PhysX, quaternion pinned to identity so odom -> base_link
    is a pure yaw integration in REP-103 axes (mirrors main.py:418-427).
    """
    pos = np.zeros(3, dtype=np.float32)
    poses = articulation.get_world_poses()
    if poses is not None:
        _ip, _ = poses
        if _ip is not None:
            arr = _ip[0] if _ip.ndim == 2 else _ip
            pos = np.asarray(arr, dtype=np.float32).copy()
    quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    return pos, quat


def _build_wheel_odom_params(
    rover_cfg: RoverConfig,
    dof_names: List[str],
) -> Optional[Dict[str, Any]]:
    """Resolve wheel-odometry YAML block into init_rclpy_side params, or None."""
    wheel_cfg = rover_cfg.wheel_odometry
    if not wheel_cfg.enabled:
        return None
    left_names = list(wheel_cfg.left_wheel_joints)
    right_names = list(wheel_cfg.right_wheel_joints)
    left_indices = resolve_joint_indices(dof_names, left_names)
    right_indices = resolve_joint_indices(dof_names, right_names)
    control_cfg = rover_cfg.control
    params: Dict[str, Any] = {
        "left_indices": left_indices,
        "right_indices": right_indices,
        "wheel_radius": control_cfg.wheel_radius,
        "track_width": wheel_cfg.track_width,
        "slip_left": wheel_cfg.slip_left,
        "slip_right": wheel_cfg.slip_right,
        "sigma_omega": wheel_cfg.sigma_omega,
        "seed": 0,
    }
    if wheel_cfg.pose_diag is not None:
        params["pose_diag"] = list(wheel_cfg.pose_diag)
    if wheel_cfg.twist_diag is not None:
        params["twist_diag"] = list(wheel_cfg.twist_diag)
    return params


def main() -> int:
    """Boot Isaac Sim, load the legacy-flag scene input, and run the rover loop."""
    parser = argparse.ArgumentParser(
        description="MarsLab: Isaac Sim Mars rover simulation.",
        allow_abbrev=False,
    )
    parser.add_argument("--config", required=True, help="Path to the integrated config YAML.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(levelname)s: %(message)s",
    )

    usda_abs = os.path.abspath(os.path.expanduser(args.usda))
    if not os.path.isfile(usda_abs):
        raise FileNotFoundError(f"USDA terrain file not found: {usda_abs}")

    rover_yaml_abs = _abs_repo_path(args.rover_yaml)
    rover = _load_rover_cfg(rover_yaml_abs)
    rover_cfg = rover.model_dump(mode="python", exclude={"declaring_path"})
    sensors_cfg = rover.sensors.model_dump(mode="python")
    control_cfg = rover.control.model_dump(mode="python")
    ros2_cfg = rover.ros2.model_dump(mode="python")
    camera_cfg = sensors_cfg["camera"]

    rover_usd_abs = _abs_repo_path(_PRE_S05_ROVER_USD_PATH)
    check_rover_usd(rover_usd_abs)

    # spawn_rpy is now resolved together with spawn_xyz inside _resolve_spawn
    # (post-stage-load). Keep this for any logging that runs before the stage
    # is up.
    spawn_rpy_yaml = _resolve_spawn_rpy(rover)
    spawn_rpy = spawn_rpy_yaml

    # Atmosphere boot: resolve atmosphere snapshot (mars_env + rendering +
    # dynamic_atmosphere). Sun position can be overridden via CLI flags;
    scenario_abs = _abs_repo_path(args.scenario)
    boot = boot_atmosphere(
        scenario_abs,
        repo_root=REPO_ROOT,
        sun_azimuth_deg=args.sun_azimuth_deg,
        sun_elevation_deg=args.sun_elevation_deg,
    )
    atmo_init = boot.atmosphere_init
    mars_env_model = boot.mars_cfg
    render_config = boot.rendering_cfg

    _LOG.info("Scenario: %s", scenario_abs)
    _LOG.info("USDA: %s", usda_abs)
    _LOG.info("Rover USD: %s", rover_usd_abs)
    _LOG.info(
        "Atmosphere: tau=%.3f sun_mode=%s dynamic=%s",
        atmo_init.tau,
        "auto" if atmo_init.dynamic.enabled else "manual",
        atmo_init.dynamic.enabled,
    )
    _LOG.info("Spawn rpy=%s z_offset=%.3fm", spawn_rpy, float(args.z_offset))

    # ---- Boot Kit + ROS2 bridge extension -----------------------------------
    simulation_app = boot_simulation_app(headless=bool(args.headless))

    import omni.timeline  # noqa: PLC0415
    from isaacsim.core.prims import Articulation  # noqa: PLC0415

    from marslab.environment.diffuse_fraction import (
        compute_diffuse_fraction_1d_approx,  # noqa: PLC0415
    )
    from marslab.environment.light_intensity import compute_direct_intensity  # noqa: PLC0415
    from marslab.environment.sky_dome import compute_sky_dome_params  # noqa: PLC0415
    from marslab.environment.sun_position import (  # noqa: PLC0415
        compute_sol_sun_position,
        compute_sun_position,
    )
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog  # noqa: PLC0415
    from marslab.rendering.render_settings import set_render_mode  # noqa: PLC0415
    from marslab.rendering.sky_renderer import (  # noqa: PLC0415
        configure_sky_dome,
        update_sky_dome,
    )
    from marslab.rendering.sun_renderer import (  # noqa: PLC0415
        configure_sun_light,
        update_sun_light,
    )
    from marslab.sensors.sensor_spawner import spawn_sensors  # noqa: PLC0415

    bridge = None
    try:
        # ---- World + Mars gravity (REQUIRED for IMU attach-time check) ------
        world, stage = create_world(
            physics_dt=atmo_init.physics_dt,
            gravity=mars_env_model.gravity,
        )

        _reference_user_usda(stage, usda_abs)

        # ---- Atmosphere / lighting (gated by --no-atmosphere) --------------
        if args.no_atmosphere:
            _add_fallback_light_if_missing(stage)
            _LOG.info("--no-atmosphere: skipping sun/sky/fog stack.")
        else:
            # configure_* functions write into /World/* prims independent of
            # the terrain reference, so they coexist cleanly with the USDA.
            set_render_mode(render_config)
            configure_sun_light(
                stage,
                atmo_init.sun_pos,
                atmo_init.direct_intensity,
                atmo_init.diffuse_fraction,
                render_config,
            )
            configure_sky_dome(
                stage,
                atmo_init.sky_params,
                atmo_init.diffuse_fraction,
                render_config,
            )
            configure_atmosphere_fog(stage, atmo_init.tau, render_config)
            _LOG.info("Atmosphere configured (sun + sky + fog).")

        # ---- Resolve spawn XYZ + RPY from the YAML spawn block + DEM --------
        # The YAML ``spawn.mode`` selects between dem_center / dem_relative /
        # absolute. The CLI ``--z-offset`` is used only if
        # ``spawn.z_offset`` is absent from the YAML.
        spawn_xyz, spawn_rpy = _resolve_spawn(
            stage,
            _TERRAIN_PRIM_PATH,
            rover,
            cli_z_offset=float(args.z_offset),
        )

        # ---- Rover spawn ----------------------------------------------------
        spawned = spawn_rover(stage, rover_cfg, rover_usd_abs, spawn_xyz)
        _LOG.info(
            "Rover spawned: prim=%s rigid_body=%s",
            spawned.prim_path,
            spawned.rigid_body_path,
        )

        # ---- Sensors + OmniGraph ROS2 bridge --------------------------------
        handles = spawn_sensors(stage, sensors_cfg, ros2_cfg, spawned.rigid_body_path)
        build_sensor_graph(
            ros2_cfg=ros2_cfg,
            camera_prim_path=handles.camera_prim_path,
            camera_resolution=tuple(camera_cfg["resolution"]),
            lidar_3d_prim_path=handles.lidar_3d_prim_path,
            imu_prim_path=handles.imu_prim_path,
            depth_sensor_cfg=camera_cfg.get("depth_sensor"),
            articulation_root_prim_path=f"{spawned.chassis_path}/Body_Chassis",
            parent_anchor_prim_path=DEFAULT_ODOM_ANCHOR_PATH,
            lidar_2d_prim_path=handles.lidar_2d_prim_path,
        )

        # ---- Pre-reset DriveAPI ---------------------------------------------
        configure_drives(stage, spawned.chassis_path, control_cfg)

        # ---- Articulation + reset + warmup + PD reinforce -------------------
        articulation = Articulation(prim_paths_expr=spawned.prim_path)
        world.reset()
        articulation.initialize()
        pin_articulation_root_pose(articulation, spawn_xyz, spawn_rpy)

        dof_names = list(articulation.dof_names)
        drive_indices = resolve_joint_indices(dof_names, list(control_cfg["drive_joint_names"]))
        steer_indices = resolve_joint_indices(dof_names, list(control_cfg["steer_joint_names"]))
        zero_steer_joints(articulation, steer_indices)
        apply_initial_joint_positions(articulation, dof_names, control_cfg)

        _LOG.info("Warming up physics handle ...")
        for _ in range(10):
            world.step(render=True)
        timeline = omni.timeline.get_timeline_interface()
        if timeline.is_stopped():
            timeline.play()
            for _ in range(5):
                world.step(render=True)
        reinforce_pd_gains(articulation, control_cfg, dof_names)

        # ---- Atmosphere loop state + optional GUI panel ---------------------
        # Panel binds to the same mutable atmosphere_dict the main loop reads,
        # so slider edits propagate without a separate sync step.
        atmo_loop_state = build_atmosphere_loop_state(atmo_init, atmo_init.tau)
        atmo_panel = None
        if not args.headless and not args.no_atmosphere:
            try:
                from marslab.gui.atmosphere_panel import AtmospherePanel  # noqa: PLC0415

                atmo_panel = AtmospherePanel(atmo_loop_state.atmosphere_dict)
                for _ in range(5):
                    simulation_app.update()
                _LOG.info("Atmosphere control panel created.")
            except Exception as exc:  # noqa: BLE001
                _LOG.error("GUI panel unavailable (%s); continuing without it.", exc)

        # ---- Capture initial pose for manual odom ---------------------------
        odom_init_pos, odom_init_quat = _capture_odom_init_pose(articulation)

        # ---- rclpy bridge ---------------------------------------------------
        if not args.no_ros2:
            sensor_frames = sensor_frames_to_tuples(build_sensor_frames(sensors_cfg))
            urdf_abs = str(rover.urdf_source_path)

            # Derive per-sensor seeds from the master seed via SeedSequence so
            # each sensor's RNG stream is independent.  Indices are stable:
            #   0 → wheel odometry, 1 → IMU, 2 → depth camera (future)
            master_seed = rover.sensors.seed
            if master_seed is not None:
                ss = np.random.SeedSequence(int(master_seed))
                child_seeds = ss.spawn(3)
                odom_seed = int(child_seeds[0].generate_state(1)[0])
                imu_seed: Optional[int] = int(child_seeds[1].generate_state(1)[0])
            else:
                odom_seed = None
                imu_seed = None

            wheel_odom_params = _build_wheel_odom_params(rover, dof_names)
            # Override wheel odom seed from master if master seed is set.
            if wheel_odom_params is not None and odom_seed is not None:
                wheel_odom_params["seed"] = odom_seed

            imu_cfg = rover.sensors.imu
            sigma_la = imu_cfg.sigma_lin_acc if isinstance(imu_cfg, EnabledImuConfig) else 0.0
            sigma_av = imu_cfg.sigma_ang_vel if isinstance(imu_cfg, EnabledImuConfig) else 0.0
            imu_noise_params: Optional[Dict[str, Any]] = None
            if sigma_la > 0.0 or sigma_av > 0.0:
                imu_noise_params = {
                    "imu_prim_path": handles.imu_prim_path,
                    "sigma_lin_acc": sigma_la,
                    "sigma_ang_vel": sigma_av,
                    "seed": imu_seed,
                }

            bridge = init_rclpy_side(
                ros2_cfg=ros2_cfg,
                sensor_frames=sensor_frames,
                init_pos_world=odom_init_pos,
                init_quat_world=odom_init_quat,
                node_name="marslab_main_rover",
                urdf_path=urdf_abs,
                wheel_odom_params=wheel_odom_params,
                imu_noise_params=imu_noise_params,
            )

        # ---- LoopContext + main loop ---------------------------------------
        def _spin_once() -> None:
            if bridge is not None:
                import rclpy  # noqa: PLC0415

                rclpy.spin_once(bridge.node, timeout_sec=0.0)

        # Atmosphere callbacks: gated. main_loop short-circuits at the first
        # None check (main_loop.py:686-694) so --no-atmosphere leaves the
        # rover step / odom / sensor read intact.
        if args.no_atmosphere:
            atmo_callbacks: Dict[str, Any] = {
                "update_sun_fn": None,
                "update_sky_fn": None,
                "configure_fog_fn": None,
                "compute_sun_fn": None,
                "compute_sol_sun_fn": None,
                "compute_direct_intensity_fn": None,
                "compute_diffuse_fraction_fn": None,
                "compute_sky_dome_fn": None,
            }
        else:
            atmo_callbacks = {
                "update_sun_fn": update_sun_light,
                "update_sky_fn": update_sky_dome,
                "configure_fog_fn": configure_atmosphere_fog,
                "compute_sun_fn": compute_sun_position,
                "compute_sol_sun_fn": compute_sol_sun_position,
                "compute_direct_intensity_fn": compute_direct_intensity,
                "compute_diffuse_fraction_fn": compute_diffuse_fraction_1d_approx,
                "compute_sky_dome_fn": compute_sky_dome_params,
            }

        ctx = build_loop_context(
            simulation_app=simulation_app,
            world=world,
            stage=stage,
            articulation=articulation,
            imu=handles.imu,
            drive_indices=drive_indices,
            steer_indices=steer_indices,
            control_cfg=control_cfg,
            physics_dt=atmo_init.physics_dt,
            atmosphere=atmo_loop_state,
            render_config=render_config,
            ackermann_fn=ackermann_command,
            bridge=bridge,
            spin_once=_spin_once,
            atmo_panel_update=(atmo_panel.update_display if atmo_panel is not None else None),
            **atmo_callbacks,
        )

        _LOG.info("Entering main loop. Ctrl+C to exit.")
        return run_main_loop(ctx)
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
            _LOG.error("simulation_app.close() raised: %s", exc)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
