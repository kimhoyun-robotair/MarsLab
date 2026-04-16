"""Phase 1 Stage 1 runtime: spawn Perseverance on flat ground + ROS2 round-trip.

Loads the offline-converted m2020 USD (produced by convert_urdf_to_usd.py),
spawns it on a flat ground plane under Earth gravity, attaches camera / LiDAR
/ IMU sensors, wires an OmniGraph pipeline that publishes sensor topics via
the Isaac Sim ROS2 bridge, and consumes ``cmd_vel`` on a rclpy Python-side
subscriber that maps linear/angular commands to 6-wheel skid-steer joint
velocity targets.

This module keeps all pure helpers (math, config loading, joint index
resolution) importable without Isaac Sim. Isaac Sim / omni.* / rclpy imports
are lazily performed inside ``main()`` so the helpers can be unit-tested on a
plain Python interpreter.

Usage:
    scripts/isaac_python.sh scripts/phase1/run_stage1.py \
        --config configs/phase1.yaml
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "configs", "phase1.yaml")


def load_config(config_path: str) -> Dict[str, Any]:
    """Load and structurally validate the Stage 1 YAML config.

    Args:
        config_path: Absolute or repo-relative path to the YAML file.

    Returns:
        Parsed config as a nested dict.

    Raises:
        FileNotFoundError: If the config file is missing.
        ValueError: If required keys are missing or joint lists have the
            wrong cardinality for Stage 1 (6 drive joints, 4 steer joints).
    """
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Stage 1 config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)

    if not isinstance(cfg, dict):
        raise ValueError(f"Config root must be a mapping, got {type(cfg).__name__}")

    for required in ("physics", "rover", "ros2", "sensors", "control"):
        if required not in cfg:
            raise ValueError(f"Config missing required section: {required}")

    control = cfg["control"]
    drive = control.get("drive_joint_names")
    if not isinstance(drive, list) or len(drive) != 6:
        raise ValueError(f"control.drive_joint_names must be a list of 6 names, got {drive!r}")
    steer = control.get("steer_joint_names")
    if not isinstance(steer, list) or len(steer) != 4:
        raise ValueError(f"control.steer_joint_names must be a list of 4 names, got {steer!r}")

    for key in ("wheel_radius", "wheel_track", "max_linear_velocity", "max_angular_velocity"):
        if key not in control:
            raise ValueError(f"control.{key} missing from config")
        if not isinstance(control[key], (int, float)) or control[key] <= 0:
            raise ValueError(f"control.{key} must be a positive number, got {control[key]!r}")

    return cfg


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the closed interval ``[low, high]``."""
    if low > high:
        raise ValueError(f"clamp bounds inverted: low={low} > high={high}")
    if value < low:
        return low
    if value > high:
        return high
    return value


def clamp_twist(v: float, w: float, v_max: float, w_max: float) -> Tuple[float, float]:
    """Clamp a 2D twist (linear, angular) to symmetric limits."""
    return clamp(v, -v_max, v_max), clamp(w, -w_max, w_max)


def skid_steer_targets(v: float, w: float, wheel_track: float, wheel_radius: float) -> np.ndarray:
    """Return 6 wheel velocity targets [L,L,L,R,R,R] for a twist (v, w).

    Implements the standard skid-steer approximation:
        omega_L = (v - w * track / 2) / r
        omega_R = (v + w * track / 2) / r

    The first three entries correspond to the three left wheels, the last
    three to the right wheels (LF, LM, LR, RF, RM, RR).

    Args:
        v: Commanded linear velocity (m/s).
        w: Commanded angular velocity (rad/s, +CCW / +Z).
        wheel_track: Left-to-right wheel separation (m).
        wheel_radius: Drive wheel rolling radius (m).

    Returns:
        ``np.ndarray`` of shape (6,) and dtype float32.

    Raises:
        ValueError: If ``wheel_radius`` or ``wheel_track`` is non-positive.
    """
    if wheel_radius <= 0.0:
        raise ValueError(f"wheel_radius must be > 0, got {wheel_radius}")
    if wheel_track <= 0.0:
        raise ValueError(f"wheel_track must be > 0, got {wheel_track}")

    omega_l = (v - w * wheel_track / 2.0) / wheel_radius
    omega_r = (v + w * wheel_track / 2.0) / wheel_radius
    return np.asarray([omega_l, omega_l, omega_l, omega_r, omega_r, omega_r], dtype=np.float32)


def rpy_to_quat(roll: float, pitch: float, yaw: float) -> Tuple[float, float, float, float]:
    """Convert roll-pitch-yaw (radians) to quaternion (w, x, y, z).

    Uses the ZYX intrinsic convention (yaw around Z, then pitch around Y,
    then roll around X) which is the standard for URDF and ROS.

    Returns:
        ``(w, x, y, z)`` tuple with scalar-first quaternion.
    """
    cr, sr = np.cos(roll / 2.0), np.sin(roll / 2.0)
    cp, sp = np.cos(pitch / 2.0), np.sin(pitch / 2.0)
    cy, sy = np.cos(yaw / 2.0), np.sin(yaw / 2.0)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return float(w), float(x), float(y), float(z)


def resolve_joint_indices(dof_names: List[str], requested: List[str]) -> List[int]:
    """Resolve each requested joint name to its index inside ``dof_names``.

    Args:
        dof_names: Ordered DOF names reported by an Articulation.
        requested: Joint names the caller wants indices for.

    Returns:
        List of int indices, matching the order of ``requested``.

    Raises:
        ValueError: If any requested joint name is not in ``dof_names``.
    """
    name_to_index = {name: idx for idx, name in enumerate(dof_names)}
    missing = [name for name in requested if name not in name_to_index]
    if missing:
        raise ValueError(
            f"Joint(s) not present in articulation DOF list: {missing}. "
            f"Available DOFs: {list(dof_names)}"
        )
    return [name_to_index[name] for name in requested]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Path to Stage 1 YAML config (default: configs/phase1.yaml)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Isaac Sim without the GUI. Default is GUI mode (Stage 1 spec).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    config_path = os.path.abspath(args.config)
    cfg = load_config(config_path)
    print(f"[run_stage1] Loaded config: {config_path}", flush=True)

    physics = cfg["physics"]
    rover_cfg = cfg["rover"]
    ros2_cfg = cfg["ros2"]
    sensors_cfg = cfg["sensors"]
    control_cfg = cfg["control"]

    usd_rel = rover_cfg["usd_path"]
    usd_abs = (
        usd_rel if os.path.isabs(usd_rel) else os.path.abspath(os.path.join(REPO_ROOT, usd_rel))
    )
    if not os.path.isfile(usd_abs):
        print(
            f"[run_stage1] Rover USD missing: {usd_abs}. "
            f"Run scripts/phase1/convert_urdf_to_usd.py first.",
            file=sys.stderr,
        )
        return 2

    # Lazy Isaac Sim import so the pure helpers above remain offline-testable.
    from isaacsim import SimulationApp  # noqa: E402

    simulation_app = SimulationApp(
        {"headless": bool(args.headless), "renderer": "RaytracedLighting"}
    )

    # All omni.* / isaacsim.* / rclpy imports must come AFTER SimulationApp().
    import omni.graph.core as og  # noqa: E402
    import omni.usd  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.prims import Articulation  # noqa: E402
    from isaacsim.core.utils.extensions import enable_extension  # noqa: E402
    from isaacsim.core.utils.stage import (  # noqa: E402
        add_reference_to_stage,
        is_stage_loading,
    )
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics  # noqa: E402

    enable_extension("isaacsim.ros2.bridge")
    simulation_app.update()

    import rclpy  # noqa: E402
    from geometry_msgs.msg import Twist  # noqa: E402

    world = World(
        stage_units_in_meters=1.0,
        physics_dt=float(physics["time_step"]),
        rendering_dt=float(physics["rendering_dt"]),
    )
    world.scene.add_default_ground_plane()

    # Stage 1 uses Earth gravity; Mars 3.72 m/s^2 is deferred to Stage 2.
    physics_ctx = world.get_physics_context()
    physics_ctx.set_gravity(-float(physics["gravity"]))
    physics_ctx.set_solver_type("TGS")

    prim_path = rover_cfg["prim_path"]
    spawn_pos = rover_cfg["spawn_position"]

    add_reference_to_stage(usd_path=usd_abs, prim_path=prim_path)
    # Spin the stage until the referenced layer is fully loaded.
    while is_stage_loading():
        simulation_app.update()

    stage = omni.usd.get_context().get_stage()
    chassis_path = f"{prim_path}/Body_Chassis"
    chassis_prim = stage.GetPrimAtPath(chassis_path)
    if not chassis_prim.IsValid():
        print(
            f"[run_stage1] Expected chassis prim missing: {chassis_path}. "
            f"Inspect converter output.",
            file=sys.stderr,
        )
        simulation_app.close()
        return 3

    # Lift the articulation root to the configured spawn height.
    rover_prim = stage.GetPrimAtPath(prim_path)
    xform = UsdGeom.Xformable(rover_prim)
    xform.ClearXformOpOrder()
    translate_op = xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(float(spawn_pos[0]), float(spawn_pos[1]), float(spawn_pos[2])))

    # Apply spawn orientation (RPY from config → quaternion).
    spawn_rpy = rover_cfg.get("spawn_orientation_rpy", [0.0, 0.0, 0.0])
    qw, qx, qy, qz = rpy_to_quat(float(spawn_rpy[0]), float(spawn_rpy[1]), float(spawn_rpy[2]))
    orient_op = xform.AddOrientOp()
    orient_op.Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))

    # Override center-of-mass on the articulation root body to compensate
    # for uniform-density collision-hull bias (rear-heavy → front lifts).
    com_offset = rover_cfg.get("com_offset")
    if com_offset is not None:
        art_root_path = f"{chassis_path}/Body_Chassis"
        art_root_prim = stage.GetPrimAtPath(art_root_path)
        if art_root_prim.IsValid():
            if not art_root_prim.HasAPI(UsdPhysics.MassAPI):
                UsdPhysics.MassAPI.Apply(art_root_prim)
            mass_api = UsdPhysics.MassAPI(art_root_prim)
            mass_api.GetCenterOfMassAttr().Set(
                Gf.Vec3f(float(com_offset[0]), float(com_offset[1]), float(com_offset[2]))
            )
            print(f"[run_stage1] CoM override on {art_root_path}: {com_offset}")
        else:
            print(
                f"[run_stage1] WARNING: {art_root_path} not found; " f"skipping CoM override.",
                file=sys.stderr,
            )

    # Apply angular damping to the articulation root body to suppress
    # whole-body rotational oscillation after landing.
    angular_damping = float(rover_cfg.get("angular_damping", 0.0))
    if angular_damping > 0.0:
        art_root_path = f"{chassis_path}/Body_Chassis"
        art_root_prim = stage.GetPrimAtPath(art_root_path)
        if art_root_prim.IsValid():
            # Attribute may not exist yet; create with correct type so PhysX
            # picks it up at simulation time.
            attr = art_root_prim.CreateAttribute(
                "physxRigidBody:angularDamping", Sdf.ValueTypeNames.Float
            )
            attr.Set(angular_damping)
            print(f"[run_stage1] Angular damping {angular_damping} on {art_root_path}")

    # --- Sensors (attached as children of Body_Chassis) ------------------
    camera_cfg = sensors_cfg["camera"]
    lidar_cfg = sensors_cfg["lidar"]
    imu_cfg = sensors_cfg["imu"]

    from isaacsim.sensors.camera import Camera  # noqa: E402
    from isaacsim.sensors.physics import IMUSensor  # noqa: E402
    from isaacsim.sensors.rtx import LidarRtx  # noqa: E402

    camera_prim_path = f"{chassis_path}/stage1_camera"
    camera = Camera(
        prim_path=camera_prim_path,
        resolution=tuple(camera_cfg["resolution"]),
        translation=np.asarray(camera_cfg["local_translation"], dtype=np.float32),
    )
    camera.initialize()
    camera.set_focal_length(float(camera_cfg["focal_length"]) / 10.0)
    camera.set_clipping_range(
        float(camera_cfg["clipping_range"][0]), float(camera_cfg["clipping_range"][1])
    )

    lidar_prim_path = f"{chassis_path}/stage1_lidar"
    lidar = LidarRtx(
        prim_path=lidar_prim_path,
        config_file_name=lidar_cfg["profile"],
        translation=np.asarray(lidar_cfg["local_translation"], dtype=np.float32),
    )
    lidar.initialize()

    # IMU requires a parent prim with RigidBodyAPI. Body_Chassis is an Xform
    # with ArticulationRootAPI only (no RigidBodyAPI) after URDF import.
    # Walk its children to find the first rigid-body prim.

    imu_parent_path = chassis_path  # fallback
    for child in chassis_prim.GetChildren():
        if child.HasAPI(UsdPhysics.RigidBodyAPI):
            imu_parent_path = str(child.GetPath())
            print(f"[run_stage1] IMU parent (rigid body): {imu_parent_path}")
            break
    else:
        print(
            f"[run_stage1] WARNING: no RigidBodyAPI child under {chassis_path}; "
            f"IMU may fail to initialize.",
            file=sys.stderr,
        )

    imu_prim_path = f"{imu_parent_path}/stage1_imu"
    imu = IMUSensor(
        prim_path=imu_prim_path,
        translation=np.asarray(imu_cfg["local_translation"], dtype=np.float32),
        frequency=int(ros2_cfg["rates"]["imu"]),
    )
    imu.initialize()

    # ComputeOdom needs the prim with ArticulationRootAPI. After
    # merge_fixed_joints the root lives at Body_Chassis/Body_Chassis (a
    # child with the same name as its parent). Walk the subtree to find it.
    odom_chassis_path = prim_path  # fallback
    for descendant in Usd.PrimRange(rover_prim):
        if descendant.HasAPI(UsdPhysics.ArticulationRootAPI):
            odom_chassis_path = str(descendant.GetPath())
            print(f"[run_stage1] ComputeOdom target (ArticulationRoot): {odom_chassis_path}")
            break
    else:
        print(
            f"[run_stage1] WARNING: no ArticulationRootAPI found under {prim_path}; "
            f"ComputeOdom may fail.",
            file=sys.stderr,
        )

    # --- OmniGraph: clock + odometry + TF + IMU/camera/LiDAR ROS2 publishers
    ns = ros2_cfg["namespace"]
    topics = ros2_cfg["topics"]
    # rates = ros2_cfg["rates"]  # Stage 1 defers per-node rate throttling to
    # Isaac Sim's native sim-time pacing; kept in YAML for Stage 2 consumers.

    def ns_topic(name: str) -> str:
        return f"/{ns}/{name}"

    graph_path = "/World/Stage1ROS2Graph"
    keys = og.Controller.Keys
    graph_handle, _nodes, _prims, _info = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnPlaybackTick"),
                ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("PubClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
                ("ComputeOdom", "isaacsim.core.nodes.IsaacComputeOdometry"),
                ("PubOdom", "isaacsim.ros2.bridge.ROS2PublishOdometry"),
                ("PubTF", "isaacsim.ros2.bridge.ROS2PublishRawTransformTree"),
                ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
                ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
                ("RPCamera", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("RPLidar", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("LidarHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "PubClock.inputs:execIn"),
                ("ReadSimTime.outputs:simulationTime", "PubClock.inputs:timeStamp"),
                ("OnTick.outputs:tick", "ComputeOdom.inputs:execIn"),
                ("ComputeOdom.outputs:execOut", "PubOdom.inputs:execIn"),
                ("ComputeOdom.outputs:linearVelocity", "PubOdom.inputs:linearVelocity"),
                ("ComputeOdom.outputs:angularVelocity", "PubOdom.inputs:angularVelocity"),
                ("ComputeOdom.outputs:position", "PubOdom.inputs:position"),
                ("ComputeOdom.outputs:orientation", "PubOdom.inputs:orientation"),
                ("ReadSimTime.outputs:simulationTime", "PubOdom.inputs:timeStamp"),
                ("OnTick.outputs:tick", "PubTF.inputs:execIn"),
                ("ReadSimTime.outputs:simulationTime", "PubTF.inputs:timeStamp"),
                ("OnTick.outputs:tick", "ReadIMU.inputs:execIn"),
                ("ReadIMU.outputs:execOut", "PubIMU.inputs:execIn"),
                ("ReadIMU.outputs:angVel", "PubIMU.inputs:angularVelocity"),
                ("ReadIMU.outputs:linAcc", "PubIMU.inputs:linearAcceleration"),
                ("ReadIMU.outputs:orientation", "PubIMU.inputs:orientation"),
                ("ReadSimTime.outputs:simulationTime", "PubIMU.inputs:timeStamp"),
                ("OnTick.outputs:tick", "RPCamera.inputs:execIn"),
                ("RPCamera.outputs:execOut", "CamRGB.inputs:execIn"),
                ("RPCamera.outputs:execOut", "CamDepth.inputs:execIn"),
                ("RPCamera.outputs:renderProductPath", "CamRGB.inputs:renderProductPath"),
                ("RPCamera.outputs:renderProductPath", "CamDepth.inputs:renderProductPath"),
                ("OnTick.outputs:tick", "RPLidar.inputs:execIn"),
                ("RPLidar.outputs:execOut", "LidarHelper.inputs:execIn"),
                ("RPLidar.outputs:renderProductPath", "LidarHelper.inputs:renderProductPath"),
            ],
            keys.SET_VALUES: [
                ("PubClock.inputs:topicName", "/clock"),
                ("ComputeOdom.inputs:chassisPrim", [odom_chassis_path]),
                ("PubOdom.inputs:odomFrameId", f"{ns}/odom"),
                ("PubOdom.inputs:chassisFrameId", f"{ns}/base_link"),
                ("PubOdom.inputs:topicName", ns_topic(topics["odom"])),
                ("PubTF.inputs:topicName", "/tf"),
                ("ReadIMU.inputs:imuPrim", [imu_prim_path]),
                ("PubIMU.inputs:topicName", ns_topic(topics["imu"])),
                ("PubIMU.inputs:frameId", f"{ns}/imu_link"),
                ("RPCamera.inputs:cameraPrim", [camera_prim_path]),
                ("RPCamera.inputs:width", int(camera_cfg["resolution"][0])),
                ("RPCamera.inputs:height", int(camera_cfg["resolution"][1])),
                ("CamRGB.inputs:type", "rgb"),
                ("CamRGB.inputs:topicName", ns_topic(topics["rgb"])),
                ("CamRGB.inputs:frameId", f"{ns}/camera_link"),
                ("CamDepth.inputs:type", "depth"),
                ("CamDepth.inputs:topicName", ns_topic(topics["depth"])),
                ("CamDepth.inputs:frameId", f"{ns}/camera_link"),
                ("RPLidar.inputs:cameraPrim", [lidar_prim_path]),
                ("LidarHelper.inputs:topicName", ns_topic(topics["lidar"])),
                ("LidarHelper.inputs:frameId", f"{ns}/lidar_link"),
                ("LidarHelper.inputs:type", "point_cloud"),
            ],
        },
    )
    print(f"[run_stage1] Built OmniGraph at {graph_path}", flush=True)

    # --- Articulation + joint index resolution ---------------------------
    articulation = Articulation(prim_paths_expr=prim_path)
    world.reset()
    articulation.initialize()

    dof_names = list(articulation.dof_names)
    print(f"[run_stage1] Articulation DOFs ({len(dof_names)}): {dof_names}", flush=True)

    drive_joint_names = list(control_cfg["drive_joint_names"])
    steer_joint_names = list(control_cfg["steer_joint_names"])
    drive_indices = resolve_joint_indices(dof_names, drive_joint_names)
    steer_indices = resolve_joint_indices(dof_names, steer_joint_names)

    wheel_radius = float(control_cfg["wheel_radius"])
    wheel_track = float(control_cfg["wheel_track"])
    v_max = float(control_cfg["max_linear_velocity"])
    w_max = float(control_cfg["max_angular_velocity"])

    # Hold steer joints at zero position for Stage 1 (no Ackermann).
    zero_steer = np.zeros(len(steer_indices), dtype=np.float32)
    try:
        articulation.set_joint_positions(zero_steer, joint_indices=np.asarray(steer_indices))
    except Exception as exc:  # noqa: BLE001
        print(f"[run_stage1] Warning: could not lock steer joints: {exc}", file=sys.stderr)

    # Apply damping to suspension joints to suppress post-landing rocking.
    suspension_names = control_cfg.get("suspension_joint_names", [])
    suspension_damping = float(control_cfg.get("suspension_damping", 0.0))
    if suspension_names and suspension_damping > 0.0:
        joints_scope = f"{chassis_path}/joints"
        for jname in suspension_names:
            joint_path = f"{joints_scope}/{jname}"
            joint_prim = stage.GetPrimAtPath(joint_path)
            if not joint_prim.IsValid():
                print(
                    f"[run_stage1] WARNING: joint prim not found: {joint_path}",
                    file=sys.stderr,
                )
                continue
            # Ensure DriveAPI:angular exists, then set damping.
            if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
                UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
            damping_attr = joint_prim.CreateAttribute(
                "drive:angular:physics:damping", Sdf.ValueTypeNames.Float
            )
            damping_attr.Set(suspension_damping)
            stiffness_attr = joint_prim.CreateAttribute(
                "drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float
            )
            stiffness_attr.Set(0.0)
            print(f"[run_stage1] Suspension damping {suspension_damping} on {joint_path}")

    # --- rclpy cmd_vel subscriber ----------------------------------------
    rclpy.init(args=None)
    node = rclpy.create_node(f"{ns}_stage1_runtime")

    latest_twist = {"v": 0.0, "w": 0.0}

    def cmd_vel_cb(msg: Twist) -> None:
        latest_twist["v"] = float(msg.linear.x)
        latest_twist["w"] = float(msg.angular.z)

    cmd_vel_topic = ns_topic(topics["cmd_vel"])
    node.create_subscription(Twist, cmd_vel_topic, cmd_vel_cb, 10)
    print(f"[run_stage1] Subscribed to {cmd_vel_topic}", flush=True)

    # --- Main loop --------------------------------------------------------
    drive_idx_arr = np.asarray(drive_indices, dtype=np.int32)
    print("[run_stage1] Entering main loop. Ctrl+C to exit.", flush=True)
    try:
        while simulation_app.is_running():
            rclpy.spin_once(node, timeout_sec=0.0)

            v, w = clamp_twist(latest_twist["v"], latest_twist["w"], v_max, w_max)
            targets = skid_steer_targets(v, w, wheel_track, wheel_radius)
            try:
                articulation.set_joint_velocity_targets(targets, joint_indices=drive_idx_arr)
            except Exception as exc:  # noqa: BLE001
                print(f"[run_stage1] set_joint_velocity_targets failed: {exc}", file=sys.stderr)

            world.step(render=True)
    except KeyboardInterrupt:
        print("[run_stage1] KeyboardInterrupt -- shutting down.", flush=True)
    finally:
        try:
            node.destroy_node()
        except Exception:  # noqa: BLE001
            pass
        try:
            rclpy.shutdown()
        except Exception:  # noqa: BLE001
            pass
        # Isaac Sim 5.x shutdown path has known heap corruption after certain
        # extensions; fall back to os._exit(0) if simulation_app.close()
        # cannot complete cleanly. Keep the call for documentation.
        try:
            simulation_app.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[run_stage1] simulation_app.close() raised: {exc}", file=sys.stderr)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
