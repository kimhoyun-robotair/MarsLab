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
PHASE1_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "configs", "phase1.yaml")

# Ensure scripts/phase1/ is importable for the ackermann module.
if PHASE1_DIR not in sys.path:
    sys.path.insert(0, PHASE1_DIR)

from ackermann import ackermann_command  # noqa: E402


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

    for key in (
        "wheel_radius",
        "wheelbase",
        "track_steer",
        "track_middle",
        "max_linear_velocity",
        "max_angular_velocity",
    ):
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


# --- skid_steer_targets: replaced by ackermann.ackermann_command() --------
# Kept as commented-out reference per G5 (comment out, don't delete).
#
# def skid_steer_targets(
#     v: float, w: float, wheel_track: float, wheel_radius: float
# ) -> np.ndarray:
#     """Return 6 wheel velocity targets [L,L,L,R,R,R] for a twist (v, w).
#
#     Implements the standard skid-steer approximation:
#         omega_L = (v - w * track / 2) / r
#         omega_R = (v + w * track / 2) / r
#     """
#     if wheel_radius <= 0.0:
#         raise ValueError(f"wheel_radius must be > 0, got {wheel_radius}")
#     if wheel_track <= 0.0:
#         raise ValueError(f"wheel_track must be > 0, got {wheel_track}")
#     omega_l = (v - w * wheel_track / 2.0) / wheel_radius
#     omega_r = (v + w * wheel_track / 2.0) / wheel_radius
#     return np.asarray(
#         [omega_l, omega_l, omega_l, omega_r, omega_r, omega_r],
#         dtype=np.float32,
#     )


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
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics  # noqa: E402

    enable_extension("isaacsim.ros2.bridge")
    simulation_app.update()

    import rclpy  # noqa: E402
    import rclpy.parameter  # noqa: E402
    from geometry_msgs.msg import TransformStamped, Twist  # noqa: E402
    from nav_msgs.msg import Odometry  # noqa: E402
    from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster  # noqa: E402

    world = World(
        stage_units_in_meters=1.0,
        physics_dt=float(physics["time_step"]),
        rendering_dt=float(physics["rendering_dt"]),
    )
    world.scene.add_default_ground_plane()

    # Mars gravity (3.72 m/s²) from config.
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

    # 29 DOF + high-gain drives need more solver iterations than default 4/1.
    # PhysicsContext has no set_solver_*_iteration_count in Isaac Sim 5.x;
    # set via USD PhysxScene attributes instead.
    # Isaac Sim's World + add_default_ground_plane() creates the scene at
    # /physicsScene. Direct path access avoids the Usd.PrimRange+HasAPI
    # search that failed in Stage 1.11.
    physics_scene_prim = stage.GetPrimAtPath("/physicsScene")
    if physics_scene_prim.IsValid():
        physics_scene_prim.CreateAttribute(
            "physxScene:solverPositionIterationCount", Sdf.ValueTypeNames.Int
        ).Set(16)
        physics_scene_prim.CreateAttribute(
            "physxScene:solverVelocityIterationCount", Sdf.ValueTypeNames.Int
        ).Set(4)
        print(
            "[run_stage1] Solver iterations: pos=16, vel=4 on /physicsScene",
            flush=True,
        )
    else:
        print(
            "[run_stage1] WARNING: /physicsScene not found; default solver iterations.",
            file=sys.stderr,
        )

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

    # Apply angular and linear damping to the articulation root body.
    # Angular: suppresses rotational oscillation after landing.
    # Linear: suppresses horizontal rocking that couples from vertical
    #   bounce through the rocker-bogie linkage (observed ±0.3 m/s at idle).
    art_root_path = f"{chassis_path}/Body_Chassis"
    art_root_prim = stage.GetPrimAtPath(art_root_path)
    if art_root_prim.IsValid():
        angular_damping = float(rover_cfg.get("angular_damping", 0.0))
        if angular_damping > 0.0:
            attr = art_root_prim.CreateAttribute(
                "physxRigidBody:angularDamping", Sdf.ValueTypeNames.Float
            )
            attr.Set(angular_damping)
            print(f"[run_stage1] Angular damping {angular_damping} on {art_root_path}")
        linear_damping = float(rover_cfg.get("linear_damping", 0.0))
        if linear_damping > 0.0:
            attr = art_root_prim.CreateAttribute(
                "physxRigidBody:linearDamping", Sdf.ValueTypeNames.Float
            )
            attr.Set(linear_damping)
            print(f"[run_stage1] Linear damping {linear_damping} on {art_root_path}")

    # --- Find the moving rigid body prim ----------------------------------
    # After URDF→USD with merge_fixed_joints=False, the prim tree has:
    #   /World/Rover/Body_Chassis          ← Xform + ArticulationRootAPI (STATIC)
    #   /World/Rover/Body_Chassis/Body_Chassis  ← RigidBodyAPI (MOVES with physics)
    # ALL sensors and ComputeOdom must target the RigidBodyAPI child;
    # parenting under the outer Xform leaves them fixed in world space.
    rigid_body_path = chassis_path  # fallback
    for child in chassis_prim.GetChildren():
        if child.HasAPI(UsdPhysics.RigidBodyAPI):
            rigid_body_path = str(child.GetPath())
            print(f"[run_stage1] Rigid body (moves): {rigid_body_path}")
            break
    else:
        print(
            f"[run_stage1] WARNING: no RigidBodyAPI child under {chassis_path}; "
            f"sensors will be static!",
            file=sys.stderr,
        )

    # --- Sensors (attached as children of the moving rigid body) ----------
    camera_cfg = sensors_cfg["camera"]
    lidar_cfg = sensors_cfg["lidar"]
    imu_cfg = sensors_cfg["imu"]

    from isaacsim.sensors.camera import Camera  # noqa: E402
    from isaacsim.sensors.physics import IMUSensor  # noqa: E402
    from isaacsim.sensors.rtx import LidarRtx  # noqa: E402

    # Camera orientation strategy: ANY xformOp modification on the Camera
    # prim itself corrupts the RTX depth pipeline (vertical striping).
    # Tested and failed: constructor orientation, AddOrientOp, set_local_pose.
    # Fix: place translation + orientation on a PARENT Xform prim. The Camera
    # prim has no xformOps of its own, but inherits the correct world-space
    # transform from the parent chain.
    cam_orient_deg = camera_cfg.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])
    has_cam_orient = any(abs(v) > 0.01 for v in cam_orient_deg)

    if has_cam_orient:
        cam_qw, cam_qx, cam_qy, cam_qz = rpy_to_quat(
            np.radians(float(cam_orient_deg[0])),
            np.radians(float(cam_orient_deg[1])),
            np.radians(float(cam_orient_deg[2])),
        )
        camera_xform_path = f"{rigid_body_path}/stage1_camera_xform"
        camera_xform = UsdGeom.Xform.Define(stage, camera_xform_path)
        camera_xform.ClearXformOpOrder()
        cx_translate = camera_xform.AddTranslateOp()
        cx_translate.Set(Gf.Vec3d(*[float(x) for x in camera_cfg["local_translation"]]))
        cx_orient = camera_xform.AddOrientOp()
        cx_orient.Set(Gf.Quatf(float(cam_qw), float(cam_qx), float(cam_qy), float(cam_qz)))
        camera_prim_path = f"{camera_xform_path}/stage1_camera"
        print(
            f"[run_stage1] Camera parent Xform: {camera_xform_path} " f"rpy_deg={cam_orient_deg}",
            flush=True,
        )
    else:
        camera_prim_path = f"{rigid_body_path}/stage1_camera"

    camera = Camera(
        prim_path=camera_prim_path,
        resolution=tuple(camera_cfg["resolution"]),
        # Translation/orientation on parent Xform if oriented, else on Camera.
        translation=(
            None
            if has_cam_orient
            else np.asarray(camera_cfg["local_translation"], dtype=np.float32)
        ),
    )
    camera.initialize()
    camera.set_focal_length(float(camera_cfg["focal_length"]) / 10.0)
    camera.set_clipping_range(
        float(camera_cfg["clipping_range"][0]), float(camera_cfg["clipping_range"][1])
    )

    lidar_prim_path = f"{rigid_body_path}/stage1_lidar"
    lidar = LidarRtx(
        prim_path=lidar_prim_path,
        config_file_name=lidar_cfg["profile"],
        translation=np.asarray(lidar_cfg["local_translation"], dtype=np.float32),
    )
    lidar.initialize()

    imu_prim_path = f"{rigid_body_path}/stage1_imu"
    imu = IMUSensor(
        prim_path=imu_prim_path,
        translation=np.asarray(imu_cfg["local_translation"], dtype=np.float32),
        frequency=int(ros2_cfg["rates"]["imu"]),
    )
    imu.initialize()

    # --- OmniGraph: clock + TF + IMU/camera/LiDAR ROS2 publishers
    # NOTE: ComputeOdom + PubOdom removed. Odometry is computed and
    # published manually via rclpy in the main loop (see below).
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
                # ComputeOdom + PubOdom removed — odometry via rclpy below.
                ("PubTF", "isaacsim.ros2.bridge.ROS2PublishRawTransformTree"),
                ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
                ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
                ("RPCamera", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                # Separate render product for depth to avoid buffer conflict
                # with RGB sharing the same render product.
                ("RPDepth", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("RPLidar", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("LidarHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "PubClock.inputs:execIn"),
                ("ReadSimTime.outputs:simulationTime", "PubClock.inputs:timeStamp"),
                ("OnTick.outputs:tick", "PubTF.inputs:execIn"),
                ("ReadSimTime.outputs:simulationTime", "PubTF.inputs:timeStamp"),
                ("OnTick.outputs:tick", "ReadIMU.inputs:execIn"),
                ("ReadIMU.outputs:execOut", "PubIMU.inputs:execIn"),
                ("ReadIMU.outputs:angVel", "PubIMU.inputs:angularVelocity"),
                ("ReadIMU.outputs:linAcc", "PubIMU.inputs:linearAcceleration"),
                ("ReadIMU.outputs:orientation", "PubIMU.inputs:orientation"),
                ("ReadSimTime.outputs:simulationTime", "PubIMU.inputs:timeStamp"),
                # RGB: RPCamera → CamRGB
                ("OnTick.outputs:tick", "RPCamera.inputs:execIn"),
                ("RPCamera.outputs:execOut", "CamRGB.inputs:execIn"),
                ("RPCamera.outputs:renderProductPath", "CamRGB.inputs:renderProductPath"),
                # Depth: separate RPDepth → CamDepth
                ("OnTick.outputs:tick", "RPDepth.inputs:execIn"),
                ("RPDepth.outputs:execOut", "CamDepth.inputs:execIn"),
                ("RPDepth.outputs:renderProductPath", "CamDepth.inputs:renderProductPath"),
                # LiDAR
                ("OnTick.outputs:tick", "RPLidar.inputs:execIn"),
                ("RPLidar.outputs:execOut", "LidarHelper.inputs:execIn"),
                ("RPLidar.outputs:renderProductPath", "LidarHelper.inputs:renderProductPath"),
            ],
            keys.SET_VALUES: [
                ("PubClock.inputs:topicName", "/clock"),
                # Articulation joint TF on a separate topic to avoid conflict
                # with the manual odom→base_link publisher on /tf.
                ("PubTF.inputs:topicName", "/tf_raw"),
                ("ReadIMU.inputs:imuPrim", [imu_prim_path]),
                ("PubIMU.inputs:topicName", ns_topic(topics["imu"])),
                ("PubIMU.inputs:frameId", "imu_link"),
                ("RPCamera.inputs:cameraPrim", [camera_prim_path]),
                ("RPCamera.inputs:width", int(camera_cfg["resolution"][0])),
                ("RPCamera.inputs:height", int(camera_cfg["resolution"][1])),
                ("CamRGB.inputs:type", "rgb"),
                ("CamRGB.inputs:topicName", ns_topic(topics["rgb"])),
                ("CamRGB.inputs:frameId", "camera_link"),
                ("RPDepth.inputs:cameraPrim", [camera_prim_path]),
                ("RPDepth.inputs:width", int(camera_cfg["resolution"][0])),
                ("RPDepth.inputs:height", int(camera_cfg["resolution"][1])),
                ("CamDepth.inputs:type", "depth"),
                ("CamDepth.inputs:topicName", ns_topic(topics["depth"])),
                ("CamDepth.inputs:frameId", "camera_link"),
                ("RPLidar.inputs:cameraPrim", [lidar_prim_path]),
                ("LidarHelper.inputs:topicName", ns_topic(topics["lidar"])),
                ("LidarHelper.inputs:frameId", "lidar_link"),
                ("LidarHelper.inputs:type", "point_cloud"),
            ],
        },
    )
    print(f"[run_stage1] Built OmniGraph at {graph_path}", flush=True)

    # --- Pre-reset USD DriveAPI setup ------------------------------------
    # set_effort_modes() only writes to USD, never to PhysX tensors.
    # set_gains() has a PhysX path but set_effort_modes/set_max_efforts do not.
    # Therefore ALL USD DriveAPI attributes (gains, effort type, max force)
    # must be set BEFORE world.reset(), which syncs USD → PhysX cache.
    # After reset, set_gains() overwrites gains in PhysX tensors directly.

    drive_joint_names = list(control_cfg["drive_joint_names"])
    steer_joint_names = list(control_cfg["steer_joint_names"])
    drive_damping = float(control_cfg.get("drive_damping", 100000.0))
    drive_max_force = float(control_cfg.get("drive_max_force", 1000000.0))
    steer_stiffness = float(control_cfg.get("steer_stiffness", 50000.0))
    steer_damping_val = float(control_cfg.get("steer_damping", 5000.0))
    steer_max_force = float(control_cfg.get("steer_max_force", 100000.0))
    suspension_names = control_cfg.get("suspension_joint_names", [])
    suspension_damping_val = float(control_cfg.get("suspension_damping", 0.0))
    drive_type = str(control_cfg.get("drive_type", "acceleration"))
    print(
        f"[run_stage1] Control params from config: drive_damping={drive_damping}, "
        f"drive_type={drive_type}, steer_kp={steer_stiffness}, steer_kd={steer_damping_val}",
        flush=True,
    )

    joints_scope = f"{chassis_path}/joints"
    # Drive joint limits are now baked into the USD by the sanitizer's
    # widening pass (±1e6). Runtime override removed in Stage 1.12 after
    # URDF reconversion confirmed the limits are correct in the USD.
    # drive_limit = 1e6
    # rev_api.GetLowerLimitAttr().Set(-drive_limit)
    # rev_api.GetUpperLimitAttr().Set(drive_limit)
    for jname in drive_joint_names:
        joint_path = f"{joints_scope}/{jname}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            print(
                f"[run_stage1] WARNING: drive joint not found: {joint_path}",
                file=sys.stderr,
            )
            continue
        if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
            UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
        drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
        # Velocity mode: stiffness=0, damping=high.
        joint_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
            drive_damping
        )
        joint_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(
            0.0
        )
        joint_prim.CreateAttribute("drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float).Set(
            drive_max_force
        )
        # Effort type: "acceleration" auto-compensates for mass/inertia.
        if not drive_api.GetTypeAttr():
            drive_api.CreateTypeAttr().Set(drive_type)
        else:
            drive_api.GetTypeAttr().Set(drive_type)

    for jname in steer_joint_names:
        joint_path = f"{joints_scope}/{jname}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            continue
        if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
            UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
        drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
        # Position mode: stiffness=high, damping=moderate.
        joint_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(
            steer_stiffness
        )
        joint_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
            steer_damping_val
        )
        joint_prim.CreateAttribute("drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float).Set(
            steer_max_force
        )
        if not drive_api.GetTypeAttr():
            drive_api.CreateTypeAttr().Set(drive_type)
        else:
            drive_api.GetTypeAttr().Set(drive_type)

    for jname in suspension_names:
        joint_path = f"{joints_scope}/{jname}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            continue
        if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
            UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
        drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
        joint_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
            suspension_damping_val
        )
        joint_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(
            0.0
        )
        if not drive_api.GetTypeAttr():
            drive_api.CreateTypeAttr().Set(drive_type)
        else:
            drive_api.GetTypeAttr().Set(drive_type)

    print(
        f"[run_stage1] USD DriveAPI set (pre-reset): drive_type={drive_type}",
        flush=True,
    )

    # --- Articulation + world.reset (USD → PhysX sync) -------------------
    articulation = Articulation(prim_paths_expr=prim_path)
    world.reset()
    articulation.initialize()

    dof_names = list(articulation.dof_names)
    print(f"[run_stage1] Articulation DOFs ({len(dof_names)}): {dof_names}", flush=True)

    drive_indices = resolve_joint_indices(dof_names, drive_joint_names)
    steer_indices = resolve_joint_indices(dof_names, steer_joint_names)
    susp_indices: List[int] = []
    if suspension_names and suspension_damping_val > 0.0:
        susp_indices = resolve_joint_indices(dof_names, list(suspension_names))

    wheel_radius = float(control_cfg["wheel_radius"])
    wheelbase = float(control_cfg["wheelbase"])
    track_steer = float(control_cfg["track_steer"])
    track_middle = float(control_cfg["track_middle"])
    v_max = float(control_cfg["max_linear_velocity"])
    w_max = float(control_cfg["max_angular_velocity"])

    # Initialize steer joints at zero.
    zero_steer = np.zeros(len(steer_indices), dtype=np.float32)
    try:
        articulation.set_joint_positions(zero_steer, joint_indices=np.asarray(steer_indices))
    except Exception as exc:  # noqa: BLE001
        print(
            f"[run_stage1] Warning: could not init steer joints: {exc}",
            file=sys.stderr,
        )

    # --- Post-reset: set_gains() overwrites gains in PhysX tensors -------
    # set_gains() has a PhysX tensor path (unlike set_effort_modes) so it
    # can reinforce the correct kp/kd values after reset.
    print("[run_stage1] Warming up physics handle ...", flush=True)
    for _ in range(10):
        world.step(render=True)

    import omni.timeline  # noqa: E402

    timeline = omni.timeline.get_timeline_interface()
    if timeline.is_stopped():
        print("[run_stage1] Timeline is stopped — calling play().", flush=True)
        timeline.play()
        for _ in range(5):
            world.step(render=True)

    handle_valid = articulation.is_physics_handle_valid()
    print(
        f"[run_stage1] timeline stopped={timeline.is_stopped()}, "
        f"physics_handle_valid={handle_valid}",
        flush=True,
    )

    num_dof = len(dof_names)
    kps = np.zeros((1, num_dof), dtype=np.float32)
    kds = np.zeros((1, num_dof), dtype=np.float32)

    for idx in drive_indices:
        kds[0, idx] = drive_damping
    for idx in steer_indices:
        kps[0, idx] = steer_stiffness
        kds[0, idx] = steer_damping_val
    for idx in susp_indices:
        kds[0, idx] = suspension_damping_val

    articulation.set_gains(kps=kps, kds=kds)
    print("[run_stage1] PD gains reinforced via set_gains().", flush=True)

    # --- Readback verification ---
    actual_kps, actual_kds = articulation.get_gains()
    check_list = []
    for name, idx in zip(drive_joint_names, drive_indices):
        check_list.append((name, idx, 0.0, drive_damping))
    for name, idx in zip(steer_joint_names, steer_indices):
        check_list.append((name, idx, steer_stiffness, steer_damping_val))
    for name, idx in zip(list(suspension_names), susp_indices):
        check_list.append((name, idx, 0.0, suspension_damping_val))

    print("[run_stage1] Gain readback:", flush=True)
    for name, idx, _exp_kp, _exp_kd in check_list:
        print(
            f"  {name}: kp={actual_kps[0, idx]:.1f}  kd={actual_kds[0, idx]:.1f}",
            flush=True,
        )

    # Effort mode readback (verify USD→PhysX sync worked).
    effort_modes = articulation.get_effort_modes()
    if effort_modes is not None:
        sample_modes = [
            effort_modes[0][drive_indices[0]] if effort_modes[0] else "N/A",
            effort_modes[0][steer_indices[0]] if effort_modes[0] else "N/A",
        ]
        print(
            f"[run_stage1] Effort mode readback: drive={sample_modes[0]}, "
            f"steer={sample_modes[1]}",
            flush=True,
        )

    # --- Capture initial rover pose for manual odometry --------------------
    # The odom frame is anchored at the rover's position at t=0. Every tick
    # we compute the delta (current − initial) and publish it as the
    # odom → base_link transform.
    init_poses = articulation.get_world_poses()
    if init_poses is not None:
        _ip, _iq = init_poses
        odom_init_pos = (_ip[0] if _ip.ndim == 2 else _ip).copy()
        odom_init_quat = (_iq[0] if _iq.ndim == 2 else _iq).copy()
    else:
        odom_init_pos = np.zeros(3, dtype=np.float32)
        odom_init_quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    print(
        f"[run_stage1] Odom origin: pos=({odom_init_pos[0]:.3f},"
        f"{odom_init_pos[1]:.3f},{odom_init_pos[2]:.3f})",
        flush=True,
    )

    # --- rclpy cmd_vel subscriber ----------------------------------------
    rclpy.init(args=None)
    node = rclpy.create_node(
        f"{ns}_stage1_runtime",
        parameter_overrides=[
            rclpy.parameter.Parameter(
                "use_sim_time",
                rclpy.parameter.Parameter.Type.BOOL,
                True,
            )
        ],
    )

    latest_twist = {"v": 0.0, "w": 0.0}

    def cmd_vel_cb(msg: Twist) -> None:
        latest_twist["v"] = float(msg.linear.x)
        latest_twist["w"] = float(msg.angular.z)

    cmd_vel_topic = ns_topic(topics["cmd_vel"])
    node.create_subscription(Twist, cmd_vel_topic, cmd_vel_cb, 10)
    print(f"[run_stage1] Subscribed to {cmd_vel_topic}", flush=True)

    # --- Static TF: base_link → sensor frames ------------------------------
    # PubTF (ROS2PublishRawTransformTree) only publishes joint-chain TF from
    # the articulation. Sensor prims (camera, lidar, imu) are Isaac Sim
    # creations, not part of the URDF kinematic tree, so their frames are
    # absent from /tf. SLAM/Nav2 need these frames to exist.
    #
    # Publish static transforms from base_link to each sensor frame.
    # Config local_translation is in Body_Chassis local frame (180° X-roll).
    # In that frame Z- = up, so config (x, y, z) → world (x, -y, -z).
    static_broadcaster = StaticTransformBroadcaster(node)
    # Frame names match PubOdom's actual output: plain "base_link" (no prefix).
    sensor_tf_configs = [
        ("camera_link", camera_cfg["local_translation"]),
        ("lidar_link", lidar_cfg["local_translation"]),
        ("imu_link", imu_cfg["local_translation"]),
    ]
    static_transforms = []
    for child_frame, local_t in sensor_tf_configs:
        tf_msg = TransformStamped()
        tf_msg.header.frame_id = "base_link"
        tf_msg.child_frame_id = child_frame
        # Convert Body_Chassis local coords to world coords (180° X-roll):
        # local (x, y, z) → world (x, -y, -z)
        tf_msg.transform.translation.x = float(local_t[0])
        tf_msg.transform.translation.y = -float(local_t[1])
        tf_msg.transform.translation.z = -float(local_t[2])
        tf_msg.transform.rotation.w = 1.0
        tf_msg.transform.rotation.x = 0.0
        tf_msg.transform.rotation.y = 0.0
        tf_msg.transform.rotation.z = 0.0
        static_transforms.append(tf_msg)
        print(
            f"[run_stage1] Static TF: {tf_msg.header.frame_id} → {child_frame} "
            f"t=({tf_msg.transform.translation.x:.2f}, "
            f"{tf_msg.transform.translation.y:.2f}, "
            f"{tf_msg.transform.translation.z:.2f})",
            flush=True,
        )
    static_broadcaster.sendTransform(static_transforms)
    print(
        f"[run_stage1] Published {len(static_transforms)} static TF frames on /tf_static",
        flush=True,
    )

    # --- Manual odom publisher (rclpy) ------------------------------------
    # OmniGraph ComputeOdom + PubOdom were unreliable (odom stuck at origin
    # regardless of chassisPrim). Manual publisher uses articulation world
    # pose minus initial pose → odom frame delta.
    odom_tf_broadcaster = TransformBroadcaster(node)
    odom_pub = node.create_publisher(Odometry, ns_topic(topics["odom"]), 10)
    odom_pub_period = 1  # publish every N sim steps (1 = every step ≈ 60 Hz)
    print(
        f"[run_stage1] Manual odom publisher: "
        f"TF odom→base_link + {ns_topic(topics['odom'])} @ ~60 Hz",
        flush=True,
    )

    def quat_inverse(q: np.ndarray) -> np.ndarray:
        """Return inverse of unit quaternion [w, x, y, z]."""
        return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float32)

    def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Hamilton product of two [w, x, y, z] quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array(
            [
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            ],
            dtype=np.float32,
        )

    def quat_rotate_vec(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Rotate vector v by quaternion q ([w,x,y,z])."""
        v_quat = np.array([0.0, v[0], v[1], v[2]], dtype=np.float32)
        q_inv = quat_inverse(q)
        result = quat_multiply(quat_multiply(q, v_quat), q_inv)
        return result[1:4]

    odom_init_quat_inv = quat_inverse(odom_init_quat)

    # --- Main loop --------------------------------------------------------
    drive_idx_arr = np.asarray(drive_indices, dtype=np.int32)
    steer_idx_arr = np.asarray(steer_indices, dtype=np.int32)

    # Sign convention: 180° X-roll inverts steer Z-axis direction.
    negate_steer = bool(control_cfg.get("negate_steer", False))
    if negate_steer:
        print("[run_stage1] negate_steer=True: inverting steer angles.", flush=True)

    # Per-step diagnostic logging (once per second at 60 Hz).
    debug_logging = bool(control_cfg.get("debug_logging", False))
    step_count = 0

    # Velocity ramp: limits per-step change in wheel speed targets to prevent
    # the massive impulse that occurs when set_joint_velocity_targets jumps
    # from 0 to 0.375 with high kd in acceleration mode.
    n_drive = len(drive_indices)
    current_drive_targets = np.zeros(n_drive, dtype=np.float32)
    max_wheel_accel_rate = float(control_cfg.get("max_wheel_accel_rate", 0.5))
    physics_dt = float(cfg.get("physics", {}).get("time_step", 1.0 / 60.0))
    per_step_limit = max_wheel_accel_rate * physics_dt
    decel_multiplier = float(control_cfg.get("decel_multiplier", 1.0))
    if max_wheel_accel_rate > 0:
        print(
            f"[run_stage1] Velocity ramp: max_wheel_accel_rate={max_wheel_accel_rate} rad/s², "
            f"per_step_limit={per_step_limit:.6f} rad/s, decel_mult={decel_multiplier}",
            flush=True,
        )

    # Steer angle limits and ramp: prevents physically impossible angles
    # (rocker-bogie collision) and snap-back when cmd_vel goes to zero.
    max_steer_angle = float(control_cfg.get("max_steer_angle", 0.7))
    steer_ramp_rate = float(control_cfg.get("steer_ramp_rate", 2.0))
    n_steer = len(steer_indices)
    current_steer_targets = np.zeros(n_steer, dtype=np.float32)
    steer_per_step_limit = steer_ramp_rate * physics_dt
    print(
        f"[run_stage1] Steer limits: max_angle={max_steer_angle:.2f} rad "
        f"({np.degrees(max_steer_angle):.1f}°), "
        f"ramp_rate={steer_ramp_rate} rad/s, per_step={steer_per_step_limit:.6f} rad",
        flush=True,
    )

    print("[run_stage1] Entering main loop. Ctrl+C to exit.", flush=True)
    try:
        while simulation_app.is_running():
            rclpy.spin_once(node, timeout_sec=0.0)

            v, w = clamp_twist(latest_twist["v"], latest_twist["w"], v_max, w_max)
            steer_angles, wheel_vels = ackermann_command(
                v, w, wheelbase, track_steer, track_middle, wheel_radius
            )
            if negate_steer:
                steer_angles = -steer_angles

            # Clamp steer angles to mechanical limits. The Ackermann
            # controller can request 87°+ for tight turns (R < wheelbase/2),
            # which causes rocker-bogie legs to collide and fold.
            steer_angles = np.clip(steer_angles, -max_steer_angle, max_steer_angle)

            # Apply steer angle ramp to prevent snap transitions.
            if steer_ramp_rate > 0:
                s_delta = steer_angles - current_steer_targets
                s_delta = np.clip(s_delta, -steer_per_step_limit, steer_per_step_limit)
                current_steer_targets = current_steer_targets + s_delta
                ramped_steer = current_steer_targets
            else:
                ramped_steer = steer_angles

            # Apply drive velocity ramp with asymmetric decel.
            if max_wheel_accel_rate > 0:
                delta = wheel_vels - current_drive_targets
                # Per-element asymmetric limit: use faster rate when decelerating
                # (target magnitude < current magnitude on that wheel).
                is_decel = np.abs(wheel_vels) < np.abs(current_drive_targets)
                step_lim = np.where(is_decel, per_step_limit * decel_multiplier, per_step_limit)
                delta = np.clip(delta, -step_lim, step_lim)
                current_drive_targets = current_drive_targets + delta
                ramped_vels = current_drive_targets
            else:
                ramped_vels = wheel_vels

            try:
                articulation.set_joint_position_targets(ramped_steer, joint_indices=steer_idx_arr)
                articulation.set_joint_velocity_targets(ramped_vels, joint_indices=drive_idx_arr)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[run_stage1] joint target failed: {exc}",
                    file=sys.stderr,
                )

            if debug_logging and step_count % 60 == 0:
                try:
                    actual_pos = articulation.get_joint_positions()
                    actual_vel = articulation.get_joint_velocities()
                    # Handle both 1D and 2D returns (batched vs single).
                    if actual_pos is not None and actual_vel is not None:
                        s_pos = (
                            actual_pos[0, steer_idx_arr]
                            if actual_pos.ndim == 2
                            else actual_pos[steer_idx_arr]
                        )
                        d_vel = (
                            actual_vel[0, drive_idx_arr]
                            if actual_vel.ndim == 2
                            else actual_vel[drive_idx_arr]
                        )
                        d_pos = (
                            actual_pos[0, drive_idx_arr]
                            if actual_pos.ndim == 2
                            else actual_pos[drive_idx_arr]
                        )
                        print(
                            f"[DIAG {step_count}] twist=({v:.3f},{w:.3f}) "
                            f"steer_cmd={steer_angles} steer_act={s_pos} "
                            f"drive_cmd={ramped_vels} drive_act={d_vel}",
                            flush=True,
                        )
                        print(
                            f"[DIAG {step_count}] drive_pos={d_pos}",
                            flush=True,
                        )
                except Exception:  # noqa: BLE001
                    pass
                # Rover body pose: detect lift-off or tipping.
                # Separate try/except so steer/drive DIAG is not lost if this fails.
                try:
                    rover_poses = articulation.get_world_poses()
                    if rover_poses is not None:
                        r_pos, r_quat = rover_poses
                        p = r_pos[0] if r_pos.ndim == 2 else r_pos
                        q = r_quat[0] if r_quat.ndim == 2 else r_quat
                        print(
                            f"[DIAG {step_count}] rover_pos="
                            f"({p[0]:.3f},{p[1]:.3f},{p[2]:.3f}) "
                            f"rover_quat="
                            f"({q[0]:.4f},{q[1]:.4f},{q[2]:.4f},{q[3]:.4f})",
                            flush=True,
                        )
                except Exception as pose_exc:  # noqa: BLE001
                    if step_count < 120:  # Only print first few failures
                        print(
                            f"[DIAG {step_count}] rover_pos FAILED: {pose_exc}",
                            flush=True,
                        )
                # Root body linear velocity: diagnose body overshoot.
                try:
                    body_vel = articulation.get_linear_velocities()
                    if body_vel is not None:
                        bv = body_vel[0] if body_vel.ndim == 2 else body_vel
                        print(
                            f"[DIAG {step_count}] body_vel="
                            f"({bv[0]:.4f},{bv[1]:.4f},{bv[2]:.4f})",
                            flush=True,
                        )
                except Exception as vel_exc:  # noqa: BLE001
                    if step_count < 120:
                        print(
                            f"[DIAG {step_count}] body_vel FAILED: {vel_exc}",
                            flush=True,
                        )
                # IMU linear acceleration: verify Mars gravity (z ≈ ±3.72 m/s²).
                # 180° X-roll may invert the body-frame Z axis.
                try:
                    imu_frame = imu.get_current_frame()
                    if imu_frame is not None and "lin_acc" in imu_frame:
                        la = imu_frame["lin_acc"]
                        print(
                            f"[DIAG {step_count}] imu_acc="
                            f"({la[0]:.4f},{la[1]:.4f},{la[2]:.4f})",
                            flush=True,
                        )
                except Exception:  # noqa: BLE001
                    pass

            # --- Publish odom → base_link TF + Odometry message -----------
            if step_count % odom_pub_period == 0:
                try:
                    rover_poses_odom = articulation.get_world_poses()
                    if rover_poses_odom is not None:
                        _rp, _rq = rover_poses_odom
                        cur_pos = _rp[0] if _rp.ndim == 2 else _rp
                        cur_quat = _rq[0] if _rq.ndim == 2 else _rq

                        # Delta position in world frame, then rotate into
                        # odom frame (which equals initial orientation).
                        delta_pos_world = cur_pos - odom_init_pos
                        delta_pos_odom = quat_rotate_vec(odom_init_quat_inv, delta_pos_world)

                        # Delta orientation: q_delta = q_init_inv * q_cur
                        delta_quat = quat_multiply(odom_init_quat_inv, cur_quat)

                        now = node.get_clock().now().to_msg()

                        # TF: odom → base_link
                        odom_tf = TransformStamped()
                        odom_tf.header.stamp = now
                        odom_tf.header.frame_id = "odom"
                        odom_tf.child_frame_id = "base_link"
                        odom_tf.transform.translation.x = float(delta_pos_odom[0])
                        odom_tf.transform.translation.y = float(delta_pos_odom[1])
                        odom_tf.transform.translation.z = float(delta_pos_odom[2])
                        odom_tf.transform.rotation.w = float(delta_quat[0])
                        odom_tf.transform.rotation.x = float(delta_quat[1])
                        odom_tf.transform.rotation.y = float(delta_quat[2])
                        odom_tf.transform.rotation.z = float(delta_quat[3])
                        odom_tf_broadcaster.sendTransform(odom_tf)

                        # nav_msgs/Odometry
                        odom_msg = Odometry()
                        odom_msg.header.stamp = now
                        odom_msg.header.frame_id = "odom"
                        odom_msg.child_frame_id = "base_link"
                        odom_msg.pose.pose.position.x = float(delta_pos_odom[0])
                        odom_msg.pose.pose.position.y = float(delta_pos_odom[1])
                        odom_msg.pose.pose.position.z = float(delta_pos_odom[2])
                        odom_msg.pose.pose.orientation.w = float(delta_quat[0])
                        odom_msg.pose.pose.orientation.x = float(delta_quat[1])
                        odom_msg.pose.pose.orientation.y = float(delta_quat[2])
                        odom_msg.pose.pose.orientation.z = float(delta_quat[3])

                        # Twist in child (base_link) frame from velocities.
                        try:
                            lin_vel = articulation.get_linear_velocities()
                            ang_vel = articulation.get_angular_velocities()
                            if lin_vel is not None and ang_vel is not None:
                                lv = lin_vel[0] if lin_vel.ndim == 2 else lin_vel
                                av = ang_vel[0] if ang_vel.ndim == 2 else ang_vel
                                # Rotate world-frame velocity into body frame.
                                cur_quat_inv = quat_inverse(cur_quat)
                                body_lv = quat_rotate_vec(cur_quat_inv, lv)
                                body_av = quat_rotate_vec(cur_quat_inv, av)
                                odom_msg.twist.twist.linear.x = float(body_lv[0])
                                odom_msg.twist.twist.linear.y = float(body_lv[1])
                                odom_msg.twist.twist.linear.z = float(body_lv[2])
                                odom_msg.twist.twist.angular.x = float(body_av[0])
                                odom_msg.twist.twist.angular.y = float(body_av[1])
                                odom_msg.twist.twist.angular.z = float(body_av[2])
                        except Exception:  # noqa: BLE001
                            pass

                        odom_pub.publish(odom_msg)
                except Exception as odom_exc:  # noqa: BLE001
                    if step_count < 120:
                        print(
                            f"[run_stage1] odom publish failed: {odom_exc}",
                            file=sys.stderr,
                        )

            step_count += 1

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
